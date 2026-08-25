#!/usr/bin/env python3
from __future__ import annotations
import io,re
import requests,pdfplumber
URL='https://cdn.halifax.ca/sites/default/files/documents/city-hall/budget-finances/financialstatementsmarch312025_0.pdf'
UA='HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'
r=requests.get(URL,headers={'User-Agent':UA},timeout=90); print('DOWNLOAD',r.status_code,len(r.content)); r.raise_for_status(); assert r.content.startswith(b'%PDF')
def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    print('PAGES',len(pdf.pages))
    for pno,page in enumerate(pdf.pages,1):
        text=page.extract_text() or ''
        if 'Consolidated Statement of Operations' in text or ('Total revenue' in text and 'Total expenses' in text):
            print(f'=== PAGE {pno} ===')
            for line in [clean(x) for x in text.splitlines() if clean(x)]: print(line)
            words=page.extract_words(x_tolerance=1,y_tolerance=2,keep_blank_chars=False,use_text_flow=False)
            rows=[]
            for w in words:
                for row in rows:
                    if abs(row[0]['top']-w['top'])<=2:
                        row.append(w); break
                else: rows.append([w])
            for row in sorted(rows,key=lambda rr:rr[0]['top']):
                row=sorted(row,key=lambda ww:ww['x0']); txt=' '.join(w['text'] for w in row)
                if any(k.lower() in txt.lower() for k in ['Taxation','Total revenue','General government','Protective services','Transportation services','Total expenses','Annual surplus']):
                    print('ROW',round(row[0]['top'],1),[(round(w['x0'],1),round(w['x1'],1),w['text']) for w in row])
