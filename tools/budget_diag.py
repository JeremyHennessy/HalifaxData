#!/usr/bin/env python3
from __future__ import annotations
import io,re
import requests,pdfplumber
URL='https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2025-26-budget-business-plan.pdf'
UA='HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'
r=requests.get(URL,headers={'User-Agent':UA},timeout=90); print('DOWNLOAD',r.status_code,len(r.content)); r.raise_for_status(); assert r.content.startswith(b'%PDF')
TARGETS={
    119:['Information Technology','Eng. Lang.','Net Total'],
    223:['Engineering & Building','Net Total'],
    248:['Infrastructure Maintenance','Net Total'],
    286:['Government Relations','Net Total'],
    324:['Service Management','Net Total'],
    341:['Employee Relations','Net Total'],
}
def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    for pno,needles in TARGETS.items():
        page=pdf.pages[pno-1]
        print(f'=== PAGE {pno} ===')
        for line in [clean(x) for x in (page.extract_text() or '').splitlines() if clean(x)]:
            if any(n.lower() in line.lower() for n in needles): print('TXT',line)
        words=page.extract_words(x_tolerance=1,y_tolerance=2,keep_blank_chars=False,use_text_flow=False)
        rows=[]
        for w in words:
            for row in rows:
                if abs(row[0]['top']-w['top'])<=2.2:
                    row.append(w); break
            else: rows.append([w])
        for row in sorted(rows,key=lambda rr:rr[0]['top']):
            row=sorted(row,key=lambda ww:ww['x0']); txt=' '.join(w['text'] for w in row)
            if any(n.lower() in txt.lower() for n in needles):
                print('ROW',round(row[0]['top'],1),[(round(w['x0'],1),round(w['x1'],1),w['text']) for w in row])
