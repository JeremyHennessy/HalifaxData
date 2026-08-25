#!/usr/bin/env python3
"""Extract project-level HRM capital-plan facts and combine with official ArcGIS history."""
from __future__ import annotations
import io,json,re
from datetime import datetime,timezone
from pathlib import Path
import pdfplumber,requests
from ingest_domains import clean,money,fetch_pdf,provenance

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'data/sources.json'
OUT=ROOT/'data/generated'
UA='HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)'

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def grab(pattern,text):
    m=re.search(pattern,text,re.I|re.M); return clean(m.group(1)) if m else None

def project_from_page(text,src,page_num):
    code=grab(r'(?:Capital\s+)?Project\s*#\s*:\s*([^\n]+)',text)
    if not code: return None
    name=grab(r'(?:Capital\s+)?Project\s+Name\s*:\s*([^\n]+)',text)
    previous=grab(r'Previous\s*#\s*:\s*([^\n]+)',text)
    executive=grab(r'Executive\s+Director\s*:\s*([^\n]+)',text)
    category=grab(r'Asset\s+Category\s*:\s*([^\n]+)',text)
    service=grab(r'Service\s+Area\s*:\s*([^\n]+)',text)
    ptype=grab(r'Project\s+Type\s*:\s*([^\n]+)',text)
    status=grab(r'Project\s+Status\s*:\s*([^\n]+)',text)
    total_cost=grab(r'Total\s+Estimated\s+Project\s+Cost\s*\$?\s*([^\n]+)',text)
    previous_budget=grab(r'Previously\s+Approved\s+Budget\s*\$?\s*([^\n]+)',text)
    current_work=grab(r'Total\s+Work\s+to\s+be\s+Completed\s+in\s+(20\d{2}/\d{2})\s*\$?\s*([^\n]+)',text)
    current_budget=None; current_fy=None
    if current_work:
        # `grab` returns only first group, so use a second targeted match for the amount.
        m=re.search(r'Total\s+Work\s+to\s+be\s+Completed\s+in\s+(20\d{2}/\d{2})\s*\$?\s*([\d,(). -]+)',text,re.I)
        if m: current_fy=clean(m.group(1)); current_budget=money(m.group(2))
    if not current_fy:
        current_fy=grab(r'(20\d{2}/\d{2})\s+Capital\s+Project',text)
    return {
      'project_id':code,'project_code':code,'previous_project_code':previous,'project_name':name,
      'business_unit':service,'service_area':service,'asset_category':category,'project_type':ptype,
      'executive_director':executive,'status':status or ('proposed plan' if 'proposed' in str(src.get('status','')) else 'capital plan'),
      'current_budget':current_budget,'fiscal_year':current_fy,'previously_approved_budget':money(previous_budget),
      'total_estimated_project_cost':money(total_cost),
      'source_status':src.get('status'),'source_page':page_num,'source_id':src['id'],
      'provenance':provenance(src['id'],src['url'],'page',str(page_num))
    }

def main():
    reg=json.loads(REGISTRY.read_text(encoding='utf-8'))
    sources=[s for s in reg['sources'] if s['id'].startswith('hrm-capital-') and s['id']!='hrm-open-capital' and str(s.get('status','')).startswith('ready')]
    session=requests.Session(); session.headers['User-Agent']=UA
    plan_rows=[]; status=[]
    for src in sources:
        try:
            blob=fetch_pdf(session,src); src_rows=0
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                for page_num,page in enumerate(pdf.pages,1):
                    rec=project_from_page(page.extract_text() or '',src,page_num)
                    if rec: plan_rows.append(rec); src_rows+=1
            status.append({'source_id':src['id'],'status':'ok','projects':src_rows})
        except Exception as exc:
            status.append({'source_id':src['id'],'status':'error','error':f'{type(exc).__name__}: {exc}'})
    arcgis_path=OUT/'capital.json'; arcgis=[]
    if arcgis_path.exists():
        try: arcgis=json.loads(arcgis_path.read_text(encoding='utf-8')).get('records',[])
        except Exception: arcgis=[]
    combined=arcgis+plan_rows
    payload={'metadata':{
      'generated_at':now(),'records':len(combined),'arcgis_records':len(arcgis),'capital_plan_projects':len(plan_rows),
      'source_status':status,
      'note':'Combines the official historical ArcGIS project layer with project-level records extractable from registered HRM capital plans. Proposed/draft source status is retained and not promoted to approved.'
    },'records':combined}
    arcgis_path.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'capital combined: {len(arcgis)} ArcGIS + {len(plan_rows)} plan project rows')

if __name__=='__main__': main()
