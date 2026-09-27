#!/usr/bin/env python3
"""Prepare reviewable refresh evidence; never publish directly to main."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
report={'last_attempt':datetime.now(timezone.utc).isoformat(),'publication_status':'review_required','owner':'repository-maintainer','domains':[]}
steps=[('compensation','scripts/ingest_compensation.py'),('budget','scripts/ingest_budget.py'),('procurement','scripts/ingest_procurement.py')]
for domain,script in steps:
 path=ROOT/'data/generated'/f'{domain}.json';old=path.read_bytes();before=hashlib.sha256(old).hexdigest()
 result=subprocess.run([sys.executable,script],cwd=ROOT,capture_output=True,text=True)
 if result.returncode:path.write_bytes(old)
 report['domains'].append({'domain':domain,'last_attempt':report['last_attempt'],'last_success':report['last_attempt'] if not result.returncode else None,'status':'fresh_candidate' if not result.returncode else 'refresh_failed_retained_evidence','checked_artifact_sha256_before':before,'candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'error':result.stderr[-1500:] if result.returncode else None})
for args in [ ['scripts/build_lifecycle_reconciliation_build019_v4.py','--output','/tmp/halifax-lifecycle.json'],['scripts/enrich_lifecycle_components_build019.py','/tmp/halifax-lifecycle.json','data/generated/lifecycle_reconciliation.json'],['scripts/build_lifecycle_investigations_build019.py'],['scripts/build_entity_index_v4.py'] ]:
 subprocess.run([sys.executable,*args],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
for script in ['validate_data.py','validate_spending.py','validate_lifecycle_reconciliation_build019.py','validate_lifecycle_components_build019.py','validate_lifecycle_investigations_build019.py','validate_entity_index_v4.py']:
 result=subprocess.run([sys.executable,'scripts/'+script],cwd=ROOT,capture_output=True,text=True)
 report.setdefault('validation',[]).append({'validator':script,'valid':result.returncode==0,'error':result.stderr[-1000:] if result.returncode else None})
(ROOT/'data/refresh_candidate_status.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
