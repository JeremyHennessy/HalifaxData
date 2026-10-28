import unittest,tempfile,pathlib,json,copy
from physician_refresh.collector import collect,robots_delay,ENDPOINTS,Hold,WEEK,utc
from test_refresh import CAP
class FakeClock:
 def __init__(self):self.t=1800000000
 def wall(self):return self.t
 def monotonic(self):return self.t
 def sleep(self,n):self.t+=n
class FakeTransport:
 def __init__(self,clock):self.clock=clock;self.calls=[];self.override={}
 def request(self,url,cap,timeout):
  self.calls.append(url);self.clock.t+=1;name=next(n for n,u,c in ENDPOINTS if u==url)
  r={'headersReceivedAt':utc(self.clock.wall()),'headersComplete':True,'status':200,'responseURL':url,'complete':True,'error':None,'headers':{'content-type':'text/plain' if name=='robots' else 'application/json' if name=='metadata' else 'text/csv'},'body':(CAP/(name+'.body')).read_bytes()}
  r.update(self.override.get(name,{}));return r
class CollectorTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.state=pathlib.Path(self.tmp.name)/'state';self.clock=FakeClock();self.t=FakeTransport(self.clock)
 def tearDown(self):self.tmp.cleanup()
 def test_success_no_publication(self):
  p=collect(self.state,self.t,self.clock);self.assertEqual(len(self.t.calls),3);x=json.loads((p/'candidate.private.json').read_bytes());self.assertFalse(x['publicationAllowed']);self.assertEqual(x['diff']['changedAmounts'],[])
 def test_fresh_state_does_not_reset_baseline_cadence(self):
  import datetime
  self.clock.t=datetime.datetime.fromisoformat('2026-10-28T14:00:00+00:00').timestamp()
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(self.t.calls,[]);history=json.loads((self.state/'baseline-retrieval.json').read_bytes());self.assertEqual(history['retrievedAt'],'2026-10-28T12:00:04.365699+00:00')
 def test_history_change_held(self):
  import datetime
  self.clock.t=datetime.datetime.fromisoformat('2026-10-28T14:00:00+00:00').timestamp()
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  (self.state/'baseline-retrieval.json').write_text('{}');self.clock.t+=WEEK*2
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(self.t.calls,[])
 def test_weekly_cadence(self):
  collect(self.state,self.t,self.clock)
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(len(self.t.calls),3);self.clock.t+=WEEK;collect(self.state,self.t,self.clock);self.assertEqual(len(self.t.calls),6)
 def test_failure_persistent_hold(self):
  self.t.override['robots']={'status':503,'body':b'service unavailable'}
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.clock.t+=WEEK*2
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(len(self.t.calls),1);self.assertTrue((self.state/'hold.json').exists())
 def test_unknown_transport_retained(self):
  def fail(*a):raise TimeoutError('unknown completion')
  self.t.request=fail
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  p=next((self.state/'attempts').iterdir());r=json.loads((p/'robots.receipt.json').read_bytes());self.assertIsNone(r['status']);self.assertFalse(r['complete']);self.assertIsNone(r['headersReceivedAt']);self.assertFalse(r['retryAfterKnown'])
 def test_redirect_stops(self):
  self.t.override['robots']={'status':302,'responseURL':'https://other.invalid/'}
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(len(self.t.calls),1)
 def test_metadata_owner_stops_before_csv(self):
  m=json.loads((CAP/'metadata.body').read_bytes());m['owner']['id']='changed';self.t.override['metadata']={'body':json.dumps(m).encode()}
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(len(self.t.calls),2)
 def test_schema_stops_before_csv(self):
  m=json.loads((CAP/'metadata.body').read_bytes());m['columns'][0]['name']='Person';self.t.override['metadata']={'body':json.dumps(m).encode()}
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(len(self.t.calls),2)
 def test_denied_policy_stops(self):
  self.t.override['robots']={'body':b'User-agent: *\nAllow: /\nDisallow: /api/\n'}
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(len(self.t.calls),1)
 def test_interrupted_reservation_stops(self):
  self.state.mkdir();(self.state/'active.lock').write_text('{}')
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(self.t.calls,[])
 def test_partial_record_no_retry(self):
  self.t.override['payments']={'complete':False,'body':b'partial'}
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  p=next((self.state/'attempts').iterdir());self.assertEqual((p/'payments.body').read_bytes(),b'partial');self.assertFalse((p/'candidate.private.json').exists())
 def test_oversized_body_bounded(self):
  self.t.override['robots']={'body':b'x'*200001}
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  p=next((self.state/'attempts').iterdir());self.assertEqual((p/'robots.body').stat().st_size,200000)
 def test_elapsed_stops(self):
  orig=self.t.request
  def slow(*a):r=orig(*a);self.clock.t+=41;return r
  self.t.request=slow
  with self.assertRaises(Hold):collect(self.state,self.t,self.clock)
  self.assertEqual(len(self.t.calls),1)
 def test_policy_repeated_groups_merge_denial(self):
  with self.assertRaises(Hold):robots_delay(b'User-agent: *\nAllow: /\nUser-agent: *\nDisallow: /api/\n')
 def test_relative_policy_denial_held(self):
  with self.assertRaises(Hold):robots_delay(b'User-agent: *\nDisallow: api/views/\n')
 def test_policy_rule_before_agent_held(self):
  with self.assertRaises(Hold):robots_delay(b'Disallow: /api/\nUser-agent: *\n')
 def test_known_policy_two_wildcard_forms(self):
  self.assertEqual(robots_delay((CAP/'robots.body').read_bytes()),1.1)
 def test_no_public_state(self):
  with self.assertRaises(Hold):collect(pathlib.Path(self.tmp.name)/'dist',self.t,self.clock)
  self.assertEqual(self.t.calls,[])
if __name__=='__main__':unittest.main()

class HTTPAdapterTests(unittest.TestCase):
 def test_no_unadmitted_endpoint(self):
  from physician_refresh.collector import HTTPTransport
  with self.assertRaises(Hold):HTTPTransport().request('https://example.invalid',10,1)
 def test_fake_complete_http_response(self):
  from physician_refresh.collector import HTTPTransport,CSV_URL
  from unittest.mock import patch
  class Sock:
   def settimeout(self,n):assert n>0
  class Obj:pass
  class Response:
   status=200;headers={'Content-Type':'text/csv','Content-Length':'3'}
   def __init__(self):self.fp=Obj();self.fp.raw=Obj();self.fp.raw._sock=Sock();self.done=False
   def geturl(self):return CSV_URL
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def isclosed(self):return self.done
   def read1(self,n):self.done=True;return b'abc'
  class Opener:
   def open(self,*a,**kw):return Response()
  with patch('physician_refresh.collector.urllib.request.build_opener',return_value=Opener()):
   r=HTTPTransport()._request_sync(CSV_URL,10,40)
  self.assertTrue(r['complete']);self.assertEqual(r['body'],b'abc');self.assertEqual(r['status'],200)
 def test_fake_access_denial_preserved(self):
  from physician_refresh.collector import HTTPTransport,CSV_URL
  from unittest.mock import patch
  class Response:
   status=403;headers={'Content-Length':'0'}
   def geturl(self):return CSV_URL
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def isclosed(self):return True
  class Opener:
   def open(self,*a,**kw):return Response()
  with patch('physician_refresh.collector.urllib.request.build_opener',return_value=Opener()):r=HTTPTransport()._request_sync(CSV_URL,10,40)
  self.assertEqual(r['status'],403);self.assertTrue(r['complete']);self.assertEqual(r['body'],b'')

class DeadlineTests(unittest.TestCase):
 def test_worker_absolute_deadline_preserves_partial(self):
  from physician_refresh.collector import HTTPTransport,CSV_URL
  from unittest.mock import patch
  class Conn:
   n=0
   def poll(self,seconds):self.n+=1;return self.n==1
   def recv(self):return ('progress',{'status':200,'headers':{},'responseURL':CSV_URL,'complete':False,'error':None,'body':b'partial'})
   def close(self):pass
  class Proc:
   pid=1;terminated=False
   def start(self):pass
   def is_alive(self):return not self.terminated
   def terminate(self):self.terminated=True
   def kill(self):self.terminated=True
   def join(self,timeout):pass
  class Context:
   p=Proc()
   def Pipe(self,duplex=False):return Conn(),Conn()
   def Process(self,**kw):return self.p
  c=Context()
  with patch('physician_refresh.collector.multiprocessing.get_context',return_value=c):r=HTTPTransport().request(CSV_URL,100,40)
  self.assertFalse(r['complete']);self.assertEqual(r['body'],b'partial');self.assertTrue(c.p.terminated);self.assertIn('deadline',r['error'])
 def test_reservation_fsync_failure_no_transport(self):
  from unittest.mock import patch
  clock=FakeClock();t=FakeTransport(clock)
  with tempfile.TemporaryDirectory() as d:
   with patch('physician_refresh.collector.fsync_dir',side_effect=OSError('disk error')):
    with self.assertRaises(OSError):collect(pathlib.Path(d)/'state',t,clock)
   self.assertEqual(t.calls,[])

class UnresolvedWorkerTests(unittest.TestCase):
 def test_unreaped_worker_forces_unknown_hold_result(self):
  from physician_refresh.collector import HTTPTransport,CSV_URL
  from unittest.mock import patch
  class Conn:
   def poll(self,n):return True
   def recv(self):return ('final',{'status':200,'complete':True,'headers':{},'body':b'ok','error':None})
   def close(self):pass
  class Proc:
   pid=1;killed=False
   def start(self):pass
   def is_alive(self):return True
   def join(self,timeout):pass
   def terminate(self):pass
   def kill(self):self.killed=True
  class Context:
   p=Proc()
   def Pipe(self,duplex=False):return Conn(),Conn()
   def Process(self,**kw):return self.p
  c=Context()
  with patch('physician_refresh.collector.multiprocessing.get_context',return_value=c):r=HTTPTransport().request(CSV_URL,10,40)
  self.assertTrue(c.p.killed);self.assertFalse(r['complete']);self.assertEqual(r['workerTermination'],'unknown')
 def test_truncated_headers_retry_after_unknown(self):
  clock=FakeClock();t=FakeTransport(clock);t.override['robots']={'headersComplete':False,'headers':{'diagnostic':'truncated'},'complete':False}
  with tempfile.TemporaryDirectory() as d:
   state=pathlib.Path(d)/'state'
   with self.assertRaises(Hold):collect(state,t,clock)
   p=next((state/'attempts').iterdir());r=json.loads((p/'robots.receipt.json').read_bytes());self.assertFalse(r['retryAfterKnown']);self.assertIsNone(r['retryAfter'])

class PolicyIntegrationTests(unittest.TestCase):
 def test_narrow_allow_is_honored_without_overriding_hold(self):
  policy=b'User-agent: *\nDisallow: /api/\nAllow: /api/views/xpt9-p9is\n'
  self.assertEqual(robots_delay(policy),1.1)
  clock=FakeClock();t=FakeTransport(clock)
  with tempfile.TemporaryDirectory() as d:
   state=pathlib.Path(d)/'state';state.mkdir();(state/'hold.json').write_text('{}')
   with self.assertRaises(Hold):collect(state,t,clock)
   self.assertEqual(t.calls,[])
 def test_wrong_policy_mime_stops(self):
  clock=FakeClock();t=FakeTransport(clock);t.override['robots']={'headers':{'content-type':'text/html'}}
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(Hold):collect(pathlib.Path(d)/'state',t,clock)
   self.assertEqual(len(t.calls),1)
 def test_policy_decision_receipt_bound(self):
  clock=FakeClock();t=FakeTransport(clock)
  with tempfile.TemporaryDirectory() as d:
   p=collect(pathlib.Path(d)/'state',t,clock);x=json.loads((p/'robots-decisions.json').read_bytes())
   self.assertTrue(x['doesNotOverrideExistingHolds']);self.assertTrue(all(not a['accessAuthorized'] for a in x['decisions']))

class ExactPolicyMimeTests(unittest.TestCase):
 def test_substring_types_stop(self):
  for mime in ('application/x-text/plain','text/plain-malicious','text/html; name=text/plain'):
   clock=FakeClock();t=FakeTransport(clock);t.override['robots']={'headers':{'content-type':mime}}
   with tempfile.TemporaryDirectory() as d:
    with self.assertRaises(Hold):collect(pathlib.Path(d)/'state',t,clock)
    self.assertEqual(len(t.calls),1)
 def test_valid_parameterized_type(self):
  clock=FakeClock();t=FakeTransport(clock);t.override['robots']={'headers':{'content-type':' Text/Plain ; charset=UTF-8'}}
  with tempfile.TemporaryDirectory() as d:self.assertTrue(collect(pathlib.Path(d)/'state',t,clock).is_dir())
