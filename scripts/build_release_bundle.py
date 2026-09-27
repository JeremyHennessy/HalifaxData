#!/usr/bin/env python3
"""Build the exact checked commit into a public-only bundle with a hash manifest."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.site'
if OUT.exists():shutil.rmtree(OUT)
OUT.mkdir()
paths=[p for p in ROOT.iterdir() if p.suffix in {'.html','.js','.css','.svg','.png','.ico'}]
paths += [p for p in (ROOT/'data').rglob('*') if p.is_file()]
for p in paths:
 dest=OUT/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
manifest={'release':'build023','commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
(OUT/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(OUT/'.nojekyll').touch()
print(f"Bundled {len(paths)} public files for {manifest['commit']}")
