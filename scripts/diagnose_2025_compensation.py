#!/usr/bin/env python3
"""Temporary Build 002 diagnostic for the 2025 compensation PDF."""
import io, json, re
from pathlib import Path
import requests, pdfplumber

ROOT=Path(__file__).resolve().parents[1]
sources=json.loads((ROOT/'data/sources.json').read_text())['sources']
src=next(s for s in sources if s['id']=='hrm-comp-2025')
r=requests.get(src['url'],timeout=60,headers={'User-Agent':'HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'})
r.raise_for_status()
print(f'bytes={len(r.content)}')
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    print(f'pages={len(pdf.pages)}')
    for n,page in enumerate(pdf.pages,1):
        text=page.extract_text() or ''
        low=text.lower()
        markers=[]
        for marker in ['halifax regional water commission','halifax water','halifax public librar','healy, kevin']:
            if marker in low: markers.append(marker)
        tables=page.extract_tables() or []
        rows=sum(len(t or []) for t in tables)
        candidates=0
        samples=[]
        for table in tables:
            for row in table or []:
                cells=[re.sub(r'\s+',' ',str(c or '')).strip() for c in (row or [])]
                if cells and ',' in cells[0]:
                    candidates+=1
                    if len(samples)<2: samples.append(cells)
        if markers or tables or n >= len(pdf.pages)-5:
            head=' | '.join(line.strip() for line in text.splitlines()[:4])[:320]
            print(f'PAGE {n}: markers={markers} tables={len(tables)} rows={rows} candidates={candidates} head={head!r}')
            for sample in samples: print('  SAMPLE',sample)
        if n >= 28 and n <= 31:
            print(f'--- PAGE {n} TEXT START ---')
            print(text)
            print(f'--- PAGE {n} TEXT END ---')
