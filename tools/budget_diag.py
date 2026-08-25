#!/usr/bin/env python3
from __future__ import annotations
import io, re
import requests, pdfplumber

URL='https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2025-26-budget-business-plan.pdf'
UA='HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'
r=requests.get(URL,headers={'User-Agent':UA},timeout=90)
print('DOWNLOAD',r.status_code,len(r.content),r.headers.get('content-type'))
r.raise_for_status()
assert r.content.startswith(b'%PDF')

def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()

def print_page(page,pno):
    text=page.extract_text() or ''
    print(f'\n=== PAGE {pno} ===')
    words=page.extract_words(x_tolerance=1,y_tolerance=2,keep_blank_chars=False,use_text_flow=False)
    rows=[]
    for w in words:
        placed=False
        for row in rows:
            if abs(row[0]['top']-w['top']) <= 2.0:
                row.append(w); placed=True; break
        if not placed: rows.append([w])
    for row in sorted(rows,key=lambda rr: rr[0]['top']):
        row=sorted(row,key=lambda ww:ww['x0'])
        txt=' '.join(w['text'] for w in row)
        if any(k in txt for k in ['Service Area','Actual','Budget','Projections','Net Total','Office Of The Fire','Professional Development','Operations','Community Risk','Chief\'s Office','Support Division','Operations Division','Access-A-Bus','Conventional Service','Ferry Service','Transit Facilities','Fiscal Transit']):
            print('ROW',round(row[0]['top'],1),[(round(w['x0'],1),round(w['x1'],1),w['text']) for w in row])

with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    print('PAGES',len(pdf.pages))
    for pno,page in enumerate(pdf.pages,1):
        text=page.extract_text() or ''
        if 'SERVICE AREA BUDGET OVERVIEW' in text:
            print_page(page,pno)
