"""Content-addressed code-only bundles. Data clocks and data paths stay unchanged."""
import hashlib,json,pathlib,re
MAX_RELEASES=7
CODE=re.compile(r'app/[a-z0-9-]+\.(?:js|css)\Z')
def digest(body):return hashlib.sha256(body).hexdigest()
def bundle_id(files):return digest(json.dumps(files,sort_keys=True,separators=(',',':')).encode())
def validate_release(entry):
    if set(entry)!={'id','files'} or not re.fullmatch('[a-f0-9]{64}',entry['id']) or not isinstance(entry['files'],dict) or not 1<=len(entry['files'])<=64:raise ValueError('Invalid retained code bundle')
    if any(not CODE.fullmatch(p) or not re.fullmatch('[a-f0-9]{64}',h) for p,h in entry['files'].items()) or bundle_id(entry['files'])!=entry['id']:raise ValueError('Code bundle identity mismatch')
    return entry
def assemble(root,files):
    code={name:(root/name).read_bytes() for name in files if CODE.fullmatch(name)}
    for name,body in code.items():
        if name.endswith('.js'):
            for dependency in re.findall(r'''(?:from\s+|import\s*)['"]([^'"]+)['"]''',body.decode()):
                if not dependency.startswith('./') or 'app/'+dependency[2:] not in code:raise ValueError('Module dependency escapes coherent code bundle')
    hashes={name:digest(body) for name,body in code.items()};current={'id':bundle_id(hashes),'files':hashes};releases=[current];assets={f"code/{current['id']}/{name}":body for name,body in code.items()}
    retained=root/'retained-code';manifest=retained/'manifest.json'
    if manifest.exists():
        prior=json.loads(manifest.read_text())
        if not isinstance(prior,list) or len(prior)>MAX_RELEASES:raise ValueError('Invalid retained release list')
        for entry in prior:
            validate_release(entry)
            if entry['id'] in {r['id'] for r in releases}:continue
            if len(releases)>=MAX_RELEASES:break
            releases.append(entry)
            for name,sha in entry['files'].items():
                path=retained/'code'/entry['id']/name
                if path.is_symlink():raise ValueError('Symlink in retained bundle')
                body=path.read_bytes()
                if len(body)>512000 or digest(body)!=sha:raise ValueError('Retained code changed')
                assets[f"code/{entry['id']}/{name}"]=body
    return current,releases,assets
BOOTSTRAP='''<script type="module">import("./code/{identity}/app/main.js").catch(()=>{{const main=document.getElementById('main');if(main){{main.replaceChildren();const title=document.createElement('h1');title.textContent='This app version could not load.';const text=document.createElement('p');text.textContent='Reload to get the latest verified release. No unavailable evidence should be treated as zero activity.';const button=document.createElement('button');button.textContent='Reload latest app';button.onclick=()=>location.reload();main.append(title,text,button);}}}});</script>'''
def version_html(body,identity):
    html=body.decode();old='<script type="module" src="app/main.js"></script>'
    if old not in html or 'href="app/styles.css"' not in html:raise ValueError('Entry assets not found')
    return html.replace(old,BOOTSTRAP.format(identity=identity)).replace('href="app/styles.css"',f'href="code/{identity}/app/styles.css"').encode()
