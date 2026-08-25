#!/usr/bin/env python3
"""Extract audited HRM financial-statement rows across all registered years."""
from __future__ import annotations
import io,json,re
from datetime import datetime,timezone
from pathlib import Path
import pdfplumber,requests
from ingest_domains import clean,money,fetch_pdf,infer_page_context,provenance

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'data/sources.json'
OUT=ROOT/'data/generated'
UA='HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)'

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def year_from(src):
    m=re.search(r'(20\d{2})',src['id']); return int(m.group(1)) if m else None

def main():
    registry=json.loads(REGISTRY.read_text(encoding='utf-8'))
    sources=[s for s in registry['sources'] if s['id'].startswith('hrm-financials-') and str(s.get('status','')).startswith('ready')]
    session=requests.Session(); session.headers['User-Agent']=UA
    records=[]; tables=[]; source_status=[]
    for src in sources:
        try:
            blob=fetch_pdf(session,src); src_rows=0
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                for page_num,page in enumerate(pdf.pages,1):
                    text=page.extract_text() or ''; context=infer_page_context(text)
                    for table_num,table in enumerate(page.extract_tables() or [],1):
                        normalized=[[clean(c) for c in (r or [])] for r in (table or [])]
                        if not normalized: continue
                        tables.append({'source_id':src['id'],'fiscal_year_end':year_from(src),'page':page_num,'table':table_num,'context':context,'rows':len(normalized),'header':normalized[:3]})
                        for row_num,row in enumerate(normalized):
                            label=next((c for c in row if c and money(c) is None and len(c)>1), '')
                            nums=[money(c) for c in row]; nums=[n for n in nums if n is not None]
                            if not label or len(nums)<2: continue
                            records.append({
                              'fiscal_year_end':year_from(src),'statement':context or None,'line_item':label,
                              'current_year':nums[-2],'prior_year':nums[-1],
                              'source_id':src['id'],'source_page':page_num,'raw_cells':row,
                              'provenance':provenance(src['id'],src['url'],'page/table/row',f'p{page_num}/t{table_num}/r{row_num}')
                            }); src_rows+=1
            source_status.append({'source_id':src['id'],'status':'ok','records':src_rows})
        except Exception as exc:
            source_status.append({'source_id':src['id'],'status':'error','error':f'{type(exc).__name__}: {exc}'})
    payload={'metadata':{'generated_at':now(),'records':len(records),'source_count':len(sources),'source_status':source_status,'note':'Audited financial-statement table rows retain source page and raw cells because statement layouts vary by year.'},'records':records}
    index={'metadata':{'generated_at':now(),'tables':len(tables),'source_count':len(sources)},'records':tables}
    (OUT/'financials.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (OUT/'financials_document_tables.json').write_text(json.dumps(index,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'financial history: {len(records)} rows from {len(sources)} audited sources')

if __name__=='__main__': main()
