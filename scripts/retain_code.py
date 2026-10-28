"""Retain up to seven previous public code bundles, never data or private files."""
import json,pathlib,sys,os,time,urllib.request,urllib.parse
from code_bundles import validate_release,MAX_RELEASES,digest
BASE='https://jeremyhennessy.github.io/HalifaxData/'
class NoRetentionRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Retention redirects are not allowed')
def read_public(url,limit):
    if not url.startswith(BASE):raise ValueError('Unexpected retention origin')
    request=urllib.request.Request(url,headers={'Cache-Control':'no-cache','User-Agent':'HalifaxData-release-retention'})
    with urllib.request.build_opener(NoRetentionRedirects()).open(request,timeout=30) as response:
        if not response.geturl().startswith(BASE):raise ValueError('Unexpected retention redirect')
        body=response.read(limit+1)
    if len(body)>limit:raise ValueError('Retained public response exceeds limit')
    return body
def retain(root,fetch=read_public):
    nonce=os.environ.get('GITHUB_SHA') or str(time.time_ns())
    manifest=json.loads(fetch(BASE+'release.json?retention='+nonce,2000000));entries=manifest.get('codeReleases',[])
    if not isinstance(entries,list) or len(entries)>MAX_RELEASES:raise ValueError('Invalid prior code retention manifest')
    destination=root/'retained-code';destination.mkdir(exist_ok=True);seen=set();total=0
    for entry in entries:
        validate_release(entry)
        if entry['id'] in seen:raise ValueError('Duplicate retained release')
        seen.add(entry['id'])
        for name,sha in entry['files'].items():
            relative=f"code/{entry['id']}/{name}"
            if manifest['files'].get(relative)!=sha:raise ValueError('Code file not in prior verified release')
            body=fetch(BASE+relative,512000);total+=len(body)
            if total>32000000 or digest(body)!=sha:raise ValueError('Prior code checksum or size mismatch')
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
    (destination/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n')
    return len(entries)
if __name__=='__main__':print('Retained prior code-only bundles:',retain(pathlib.Path(__file__).resolve().parents[1]))
