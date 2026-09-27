#!/usr/bin/env python3
"""Independent regression fixtures for the published numeric and identity defects."""
import copy,hashlib,json,random
from pathlib import Path
from validate_spending import validate
from quarterly_geometry import numeric,typed_operating_fields
ROOT=Path(__file__).resolve().parents[1]
payload=json.loads((ROOT/'data/generated/spending.json').read_text())
validate(payload)
for bad in ('digits','measure','period','eligibility'):
 p=copy.deepcopy(payload);r=next(r for r in p['records'] if r['source_id']=='hrm-q3-2024-25' and r['business_unit']=='Halifax Transit')
 if bad=='digits':r['amount']=11079932;r['financial_fields']['current_ytd_actual']=11079932
 elif bad=='measure':r['measure']='prior_ytd_actual'
 elif bad=='period':r['period_months']=3
 else:r['comparison_eligible']=False
 try:validate(p)
 except AssertionError:pass
 else:raise AssertionError('Failed to reject '+bad)
assert numeric('(1,966,400)')==-1966400 and numeric('—')==0 and numeric('75.3%')==75.3
p=json.loads((ROOT/'data/generated/procurement.json').read_text());rows=p['records']
def identity(r):return 'public-award:'+hashlib.sha256(('ns-awarded-tenders-socrata:'+r['source_row_id']).encode()).hexdigest()[:24]
assert len({r['record_id'] for r in rows})==len(rows)==5517
assert all(identity(r)==r['record_id'] and r['current_contract_value'] is None for r in rows)
shuffled=list(rows);random.Random(23).shuffle(shuffled)
assert {identity(r) for r in shuffled}=={r['record_id'] for r in rows}
corrected={**rows[0],'original_award_value':12345};assert identity(corrected)==rows[0]['record_id']
assert {identity(r) for r in rows[1:]}=={r['record_id'] for r in rows[1:]}
m=json.loads((ROOT/'data/procurement_identity_migration_build023.json').read_text())
assert len(m['record_id_migration'])==5502 and len(set(m['record_id_migration'].values()))==5502
assert len(m['new_awards'])==15 and m['removed']==0
assert set(m['record_id_migration'].values()) <= {r['record_id'] for r in rows}
print('Independent financial mutation tests and reorder/deletion/correction identity tests passed.')
