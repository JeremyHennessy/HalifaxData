#!/usr/bin/env python3
"""Verify the deployed commit and every published JS/CSS/data artifact hash."""
import concurrent.futures,hashlib,json,sys,time,urllib.request
base=sys.argv[1].rstrip('/')+'/'
expected=sys.argv[2]
def read(path):
 req=urllib.request.Request(base+path+'?release='+expected,headers={'Cache-Control':'no-cache','User-Agent':'HalifaxData-release-verifier'})
 with urllib.request.urlopen(req,timeout=60) as r:return r.read()
manifest=json.loads(read('release-manifest.json'))
assert manifest['commit']==expected,(manifest['commit'],expected)
def check(item):
 path,digest=item
 assert hashlib.sha256(read(path)).hexdigest()==digest,path
 return path
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 checked=list(pool.map(check,manifest['files'].items()))
print(f"Verified hosted commit {expected}: {len(checked)} hashes")
