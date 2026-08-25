#!/usr/bin/env python3
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
comp=json.loads((ROOT/'data/generated/compensation.json').read_text())
sources=json.loads((ROOT/'data/sources.json').read_text())
source_ids={s['id'] for s in sources['sources']}
seen=set()
for i,r in enumerate(comp['records']):
    req=['fiscal_year_end','entity','name','person_key','wages','benefits','total','source_id']
    missing=[k for k in req if k not in r]
    if missing: errors.append(f'row {i}: missing {missing}'); continue
    if r['source_id'] not in source_ids: errors.append(f'row {i}: unknown source {r["source_id"]}')
    if r['total'] < 100000: errors.append(f'row {i}: total below disclosure threshold: {r["total"]}')
    if abs((r['wages']+r['benefits'])-r['total']) > 1.05: errors.append(f'row {i}: wages + benefits != total for {r["name"]} {r["fiscal_year_end"]}')
    key=(r['fiscal_year_end'],r['entity'],r['person_key'],r['total'])
    if key in seen: errors.append(f'row {i}: duplicate {key}')
    seen.add(key)
if errors:
    print('DATA VALIDATION FAILED',file=sys.stderr)
    print('\n'.join(errors[:100]),file=sys.stderr); sys.exit(1)
print(f'validated {len(comp["records"])} compensation rows and {len(source_ids)} sources')
