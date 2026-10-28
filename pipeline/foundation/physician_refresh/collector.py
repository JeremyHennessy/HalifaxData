"""Bounded manual candidate collector. No scheduler, retries or publication."""
import argparse,datetime,hashlib,json,os,pathlib,re,time,urllib.request,urllib.error,urllib.parse,multiprocessing
from physician_refresh.refresh import CSV_URL,META_URL,MAX_BYTES,assess,load_baseline,Hold,require,BASELINE_SHA,REVIEW_SHA
ROBOTS='https://data.novascotia.ca/robots.txt'
ENDPOINTS=[('robots',ROBOTS,200000),('metadata',META_URL,MAX_BYTES),('payments',CSV_URL,MAX_BYTES)]
WEEK=7*24*60*60
MANUAL_TRANSPORT_ENABLED=False
CANONICAL_STATE=pathlib.Path(__file__).resolve().parent/'refresh-state.private'

def encode(x):return (json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode()
def digest(b):return hashlib.sha256(b).hexdigest()
def fsync_dir(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def immutable(path,body):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
 fsync_dir(path.parent)
def utc(timestamp):return datetime.datetime.fromtimestamp(timestamp,datetime.timezone.utc).isoformat()

def robots_delay(body):
 from source_policies.robots import decide
 decisions=[decide(body,url,'HalifaxDataResearch') for url in (META_URL,CSV_URL)]
 require(all(d['status']=='allow' for d in decisions),'Robots policy denies target or requires review')
 delay=max([1.1]+[d['crawlDelaySeconds'] for d in decisions])
 require(delay<=10,'Crawl delay exceeds this bounded collector scope')
 return delay

class Clock:
 def wall(self):return time.time()
 def monotonic(self):return time.monotonic()
 def sleep(self,n):time.sleep(n)

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

class HTTPTransport:
 """One request only; retains bounded error diagnostics. Invoked only by explicit CLI."""
 def request(self,url,cap,timeout):
  require(url in {e[1] for e in ENDPOINTS},'Endpoint not admitted')
  # Separate process bounds DNS/TLS/open as well as body reads; never retry a killed request.
  ctx=multiprocessing.get_context('spawn');parent,child=ctx.Pipe(duplex=False)
  process=ctx.Process(target=_http_worker,args=(url,cap,timeout,child),daemon=True)
  start=time.monotonic();last={'status':None,'headers':{},'responseURL':None,'complete':False,'error':None,'headersComplete':False,'body':b''}
  try:
   process.start();child.close()
   while True:
    remaining=timeout-(time.monotonic()-start)
    if remaining<=0 or not parent.poll(remaining):
     last.update(complete=False,error='Absolute request deadline; transport completion unknown');return last
    try:kind,result=parent.recv()
    except EOFError:
     last.update(complete=False,error='Transport worker ended without terminal receipt');return last
    last=result
    if kind=='final':return last
  finally:
   if process.pid is not None:
    process.join(timeout=0.1)
    if process.is_alive():process.terminate();process.join(timeout=1)
    if process.is_alive():process.kill();process.join(timeout=1)
    if process.is_alive():last.update(complete=False,error='Worker termination unresolved; persistent hold required',workerTermination='unknown')
    else:last['workerTermination']='confirmed'
   parent.close();child.close()
 def _request_sync(self,url,cap,timeout,progress=lambda value:None):
  require(url in {e[1] for e in ENDPOINTS},'Endpoint not admitted')
  start=time.monotonic();body=b'';result={'status':None,'headers':{},'responseURL':None,'complete':False,'error':None,'headersComplete':False}
  try:
   op=urllib.request.build_opener(NoRedirect())
   request=urllib.request.Request(url,headers={'User-Agent':'HalifaxDataResearch/1.0 (manual bounded aggregate refresh)','Accept-Encoding':'identity'})
   try:response=op.open(request,timeout=timeout)
   except urllib.error.HTTPError as e:response=e
   with response:
    headers=dict((k.lower(),v) for k,v in response.headers.items())
    result.update(status=response.status,responseURL=response.geturl(),headersReceivedAt=utc(time.time()))
    if len(encode(headers))>32768:
     result.update(headers={'diagnostic':'Headers exceeded 32KiB; values withheld'},headersTruncated=True);raise Hold('Headers exceed cap')
    result['headers']=headers;result['headersComplete']=True;progress(dict(result,body=body))
    require(headers.get('content-encoding','identity')=='identity','Unexpected encoding')
    stream=response.fp if isinstance(response,urllib.error.HTTPError) else response
    while True:
     if stream.isclosed():result['complete']=True;break
     remaining=timeout-(time.monotonic()-start);require(remaining>0,'Request deadline exceeded')
     # Socket timeout decreases with the absolute request deadline, not each chunk.
     sock=getattr(getattr(getattr(stream,'fp',None),'raw',None),'_sock',None)
     require(sock is not None,'Cannot verify bounded response socket')
     sock.settimeout(remaining)
     chunk=stream.read1(min(65536,cap+1-len(body)))
     if not chunk:result['complete']=True;break
     body+=chunk;progress(dict(result,body=body[:cap]));require(len(body)<=cap,'Response exceeds cap')
    length=headers.get('content-length')
    require(length is None or (length.isdigit() and int(length)==len(body)),'Content length mismatch')
  except Exception as e:result.update(complete=False,error=type(e).__name__+': '+str(e))
  result['body']=body[:cap];return result

def _http_worker(url,cap,timeout,connection):
 try:
  result=HTTPTransport()._request_sync(url,cap,timeout,lambda r:connection.send(('progress',r)))
  connection.send(('final',result))
 finally:connection.close()

def seed_baseline_history(state,baseline):
 state=pathlib.Path(state);source=baseline['source'];captured=source['capturedAt']
 timestamp=datetime.datetime.fromisoformat(captured.replace('Z','+00:00'))
 require(timestamp.tzinfo is not None,'Baseline retrieval lacks timezone')
 history={'schemaVersion':'accepted-baseline-retrieval-v1','baselineSha256':BASELINE_SHA,'reviewReceiptSha256':REVIEW_SHA,'sourceURL':source['downloadUrl'],'retrievedAt':captured,'sourceBodySha256':source['sourceBodySha256'],'captureReceiptSha256':source['captureReceiptSha256'],'role':'Original accepted successful retrieval; cadence floor, not a new collector request'}
 payload=encode(history);path=state/'baseline-retrieval.json'
 if path.exists():require(path.read_bytes()==payload,'Baseline history drift; do not reset cadence')
 else:immutable(path,payload)
 return timestamp.timestamp()

def collect(state,transport,clock=None):
 clock=clock or Clock();state=pathlib.Path(state).resolve();baseline=load_baseline()
 require(not any(p.lower() in {'public','dist','data','baseline'} for p in state.parts),'State cannot be public/baseline data')
 state.mkdir(mode=0o700,parents=True,exist_ok=True);fsync_dir(state.parent)
 require(not (state/'hold.json').exists(),'Persistent hold requires review; no retry')
 # Exclusive lock also treats an interrupted run as unresolved, not retryable.
 require(not (state/'active.lock').exists(),'Unresolved/concurrent attempt; no retry')
 attempts=state/'attempts';attempts.mkdir(mode=0o700,exist_ok=True)
 last=[seed_baseline_history(state,baseline)]
 for run in attempts.iterdir():
  require(run.is_dir() and (run/'outcome.json').is_file(),'Unresolved prior attempt; stop')
  outcome=json.loads((run/'outcome.json').read_bytes());require(outcome.get('status')=='candidate_prepared','Prior failure requires review')
  last.append(outcome['completedAtEpoch'])
 if last:require(clock.wall()-max(last)>=WEEK,'Weekly cadence not elapsed')
 immutable(state/'active.lock',encode({'startedAt':utc(clock.wall()),'baselineRequired':True}))
 run=attempts/str(time.time_ns());run.mkdir(mode=0o700);fsync_dir(attempts)
 immutable(run/'admission.json',encode({'endpoints':ENDPOINTS,'retries':0,'redirects':False,'maxElapsedSeconds':150,'publicationAllowed':False}))
 started=clock.monotonic();responses={};bodies={};delay=1.1
 try:
  for index,(name,url,cap) in enumerate(ENDPOINTS):
   if index:require(clock.monotonic()-started+delay<150,'Whole attempt deadline before next request');clock.sleep(delay)
   remaining=150-(clock.monotonic()-started);require(remaining>0,'Whole attempt deadline')
   attempted=clock.wall();before=clock.monotonic()
   immutable(run/(name+'.attempt.json'),encode({'url':url,'attemptedAt':utc(attempted),'cap':cap,'timeoutSeconds':min(40,remaining)}))
   try:r=transport.request(url,cap,min(40,remaining))
   except Exception as e:r={'body':b'','status':None,'headers':{},'responseURL':None,'complete':False,'error':type(e).__name__+': '+str(e)}
   body=r.pop('body',b'');require(type(body) is bytes,'Invalid transport body type')
   receipt={'url':url,'attemptedAt':utc(attempted),'headersReceivedAt':r.get('headersReceivedAt'),'completedAt':utc(clock.wall()),'status':r.get('status'),'complete':r.get('complete') is True,'headers':r.get('headers',{}),'responseURL':r.get('responseURL'),'transportError':r.get('error'),'workerTermination':r.get('workerTermination'),'headersComplete':r.get('headersComplete') is True,'retryAfterKnown':r.get('headersComplete') is True,'retryAfter':r.get('headers',{}).get('retry-after'),'bodyBytes':len(body),'bodySha256':digest(body),'headersReceivedAtBasis':'transport_observed' if r.get('headersReceivedAt') else 'unknown_no_header_observation','disposition':'received_for_semantic_review'}
   if len(body)>cap:receipt['complete']=False;receipt['disposition']='held_no_retry';body=body[:cap];receipt.update(bodyBytes=len(body),bodySha256=digest(body))
   immutable(run/(name+'.body'),body);immutable(run/(name+'.receipt.json'),encode(receipt))
   require(receipt['status']==200 and receipt['complete'] and receipt['headersComplete'] and receipt['responseURL']==url and not receipt['transportError'],'Unsuccessful/redirected/uncertain response; no retry')
   require(clock.monotonic()-before<=40 and clock.monotonic()-started<=150,'Time budget exceeded')
   require(not re.search(rb'captcha|access.denied|request rejected|challenge-platform|cf-chl',body,re.I),'Challenge/access body')
   if name=='robots':
    require(receipt['headers'].get('content-type','').split(';',1)[0].strip().lower()=='text/plain','Robots media type not verified')
    delay=robots_delay(body)
    from source_policies.robots import decide
    immutable(run/'robots-decisions.json',encode({'policySha256':digest(body),'policyResponseReceiptSha256':digest(encode(receipt)),'policySourceURL':ROBOTS,'evaluatedDuringSameAttempt':True,'productToken':'HalifaxDataResearch','decisions':[decide(body,u,'HalifaxDataResearch') for u in (META_URL,CSV_URL)],'doesNotOverrideExistingHolds':True}))
   if name=='metadata':
    from physician_refresh.refresh import validate_receipt,FIELDS,API_FIELDS
    validate_receipt(body,receipt,META_URL,'application/json');m=json.loads(body);owner=m.get('owner',{})
    require(m.get('id')=='xpt9-p9is' and m.get('provenance')=='official' and m.get('licenseId')=='OGL_NOVA_SCOTIA' and m.get('publicationStage')=='published' and m.get('assetType')=='dataset','Metadata identity/licence gate')
    require(owner.get('id')=='9pyy-md4w' and owner.get('displayName')=='Open Data Nova Scotia' and owner.get('screenName')=='Open Data Nova Scotia','Owner gate')
    require([c.get('name') for c in m.get('columns',[])]==FIELDS and [c.get('fieldName') for c in m['columns']]==API_FIELDS and [c.get('dataTypeName') for c in m['columns']]==['text','text','text','number'],'Metadata schema gate')
   responses[name]=receipt;bodies[name]=body
  candidate=assess(bodies['payments'],bodies['metadata'],responses['payments'],responses['metadata'])
  immutable(run/'candidate.private.json',encode(candidate));outcome={'status':'candidate_prepared','completedAtEpoch':clock.wall(),'publicationAllowed':False,'candidateSha256':digest(encode(candidate))}
  immutable(run/'outcome.json',encode(outcome));(state/'active.lock').unlink();fsync_dir(state);return run
 except Exception as e:
  outcome={'status':'held_no_retry','completedAtEpoch':clock.wall(),'error':type(e).__name__+': '+str(e),'publicationAllowed':False}
  immutable(run/'outcome.json',encode(outcome));immutable(state/'hold.json',encode(outcome));raise

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=pathlib.Path,required=True);p.add_argument('--manual-reviewed-capture',action='store_true',required=True);a=p.parse_args()
 require(a.state.absolute()==CANONICAL_STATE and not CANONICAL_STATE.is_symlink(),'Manual CLI requires the canonical reviewed state directory; no alternate journal')
 require(MANUAL_TRANSPORT_ENABLED,'Repository transport is disabled; hosted state and endpoint holds need separate reviewed registration')
 print(collect(a.state,HTTPTransport()))
if __name__=='__main__':main()
