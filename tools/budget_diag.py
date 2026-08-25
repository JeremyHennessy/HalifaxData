#!/usr/bin/env python3
from __future__ import annotations
import io, re
import requests, pdfplumber
URL='https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2025-26-budget-business-plan.pdf'
UA='HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'
r=requests.get(URL,headers={'User-Agent':UA},timeout=90); r.raise_for_status(); assert r.content.startswith(b'%PDF')
PAGES=[31,52,78,100,119,134,147,176,223,248,271,278,286,306,324,341,357,369]
def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    for pno in PAGES:
        text=pdf.pages[pno-1].extract_text() or ''
        lines=[clean(x) for x in text.splitlines() if clean(x)]
        print(f'=== PAGE {pno} ===')
        for line in lines[:18]: print(line)
