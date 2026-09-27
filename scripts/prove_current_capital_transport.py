#!/usr/bin/env python3
"""Separate fresh reproduction from a blocked source and valid retained evidence."""
import hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
out=Path('artifacts/current_capital.json');out.parent.mkdir(exist_ok=True)
result=subprocess.run([sys.executable,'scripts/ingest_current_capital_v5.py','--output',str(out)],capture_output=True,text=True)
print(result.stdout);print(result.stderr)
status='fresh_reproduction'
if result.returncode:
 if '403 Client Error' not in result.stderr:raise SystemExit(result.returncode)
 status='blocked_403_checked_artifact_validated'
 shutil.copyfile('data/generated/current_capital.json',out)
subprocess.run([sys.executable,'scripts/validate_current_capital.py',str(out)],check=True)
report={'last_attempt':datetime.now(timezone.utc).isoformat(),'status':status,'fresh_reproduction':result.returncode==0,'artifact_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'owner':'repository-maintainer','next_action':None if not result.returncode else 'Obtain permitted official PDF transport; retained evidence is not a fresh reproduction.'}
Path('artifacts/current_capital_transport.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
