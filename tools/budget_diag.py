#!/usr/bin/env python3
from __future__ import annotations
import io,re
import requests,pdfplumber
URL='https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2025-26-budget-business-plan.pdf'
UA='HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'
r=requests.get(URL,headers={'User-Agent':UA},timeout=90); r.raise_for_status(); assert r.content.startswith(b'%PDF')
NEEDLES=['Information Technology/Collect','Government Relations & Extern','Infrastructure Maintenance & Operat']
def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    for pno,page in enumerate(pdf.pages,1):
        text=page.extract_text() or ''
        hits=[]
        for line in [clean(x) for x in text.splitlines() if clean(x)]:
            if any(n.lower() in line.lower() for n in NEEDLES): hits.append(line)
        if hits:
            print(f'=== PAGE {pno} ===')
            for line in hits: print(line)
