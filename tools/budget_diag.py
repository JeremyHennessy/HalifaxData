#!/usr/bin/env python3
from __future__ import annotations
import io, re
import requests, pdfplumber

URLS=[
    ('registry','https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2025-26-budget-business-plan.pdf'),
    ('final','https://cdn.halifax.ca/sites/default/files/documents/city-hall/budget-finances/final-2025-26-budget-business-plan.pdf'),
]
UA='HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'

def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()

blob=None; used=None
for label,url in URLS:
    try:
        r=requests.get(url,headers={'User-Agent':UA},timeout=90)
        print(f'DOWNLOAD {label}: status={r.status_code} bytes={len(r.content)} content_type={r.headers.get("content-type")}')
        if r.ok and r.content.startswith(b'%PDF'):
            blob=r.content; used=(label,url); break
    except Exception as e:
        print(f'DOWNLOAD {label}: ERROR {e!r}')
if blob is None:
    raise SystemExit('No budget PDF downloaded')
print('USING',used)

keywords=('actual','budget','projection','forecast','revenue','expense','expenditure','fiscal services','operating')
with pdfplumber.open(io.BytesIO(blob)) as pdf:
    print('PAGES',len(pdf.pages))
    candidates=[]
    for pno,page in enumerate(pdf.pages,1):
        text=page.extract_text() or ''
        low=text.lower()
        tables=page.extract_tables() or []
        score=sum(k in low for k in keywords)
        if score>=3 or any('2025/26' in clean(c) and ('actual' in clean(c).lower() or 'budget' in clean(c).lower()) for t in tables for row in (t or []) for c in (row or [])):
            candidates.append((pno,score,text,tables))
    print('CANDIDATE_PAGES',[(p,s,len(t)) for p,s,_,t in candidates])
    for pno,score,text,tables in candidates[:40]:
        print(f'\n=== PAGE {pno} score={score} tables={len(tables)} ===')
        lines=[clean(x) for x in text.splitlines() if clean(x)]
        for line in lines[:45]: print('TXT',line[:260])
        for ti,table in enumerate(tables[:8],1):
            print(f'TABLE {ti} rows={len(table or [])}')
            for row in (table or [])[:18]:
                print('ROW', [clean(c) for c in (row or [])])
