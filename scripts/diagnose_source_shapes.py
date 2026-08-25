#!/usr/bin/env python3
"""Temporary Build 003 diagnostic for audited-statement text and NS municipal API schemas."""
from __future__ import annotations
import io, json, re
from pathlib import Path
import requests, pdfplumber

ROOT=Path(__file__).resolve().parents[1]
registry=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))['sources']
by_id={s['id']:s for s in registry}
UA='HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)'
s=requests.Session(); s.headers['User-Agent']=UA

api_ids=['ns-municipal-operating-expenses','ns-municipal-operating-totals','ns-municipal-fci','ns-uniform-assessment-regional','ns-municipal-funding-programs','ns-municipal-capacity-grants']
for source_id in api_ids:
    src=by_id[source_id]
    r=s.get(src['url'],params={'$limit':8},timeout=60); r.raise_for_status(); rows=r.json()
    print(f'=== API {source_id} rows={len(rows)} ===')
    for i,row in enumerate(rows[:3]):
        print(f'row{i} keys={sorted(row.keys())}')
        print(json.dumps(row,ensure_ascii=False,sort_keys=True))

for source_id in ['hrm-financials-2025','hrm-financials-2023']:
    src=by_id[source_id]
    r=s.get(src['url'],timeout=90); r.raise_for_status()
    print(f'=== PDF {source_id} bytes={len(r.content)} ===')
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        print(f'pages={len(pdf.pages)}')
        hits=0
        for pnum,page in enumerate(pdf.pages,1):
            text=page.extract_text(layout=True) or page.extract_text() or ''
            low=text.lower()
            if any(k in low for k in ['consolidated statement of financial position','consolidated statement of operations','consolidated statement of change','consolidated statement of cash flow','consolidated schedule','taxation','government transfers','accounts payable and accrued liabilities']):
                hits+=1
                lines=[re.sub(r'\s+',' ',line).strip() for line in text.splitlines() if line.strip()]
                print(f'--- {source_id} PAGE {pnum} ---')
                for line in lines[:55]: print(line)
                if hits>=8: break
