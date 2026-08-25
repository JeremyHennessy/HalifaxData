#!/usr/bin/env python3
"""Extract HRM quarterly financial-report expense/expenditure summary tables.

These records are official financial summary rows, not transaction-level accounts
payable. The distinction is carried in every row and in dataset metadata.
"""
from __future__ import annotations
import io, json, re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber, requests
from ingest_domains import clean, money, provenance

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'data/sources.json'
OUT=ROOT/'data/generated/spending.json'
UA='HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)'
PERIOD_END={
 'hrm-q2-2024-25':'2024-09-30',
 'hrm-q3-2024-25':'2024-12-31',
 'hrm-q1-2023-24':'2023-06-30',
 'hrm-q2-2023-24':'2023-09-30',
 'hrm-q3-2023-24':'2023-12-31',
}
KEYWORDS=('expense','expenditure','district capital','district activity','hospitality','area rate','operating results','capital projection','reserve')

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def context_for(text):
    lines=[clean(x) for x in text.splitlines() if clean(x)]
    for line in lines[:18]:
        low=line.lower()
        if any(k in low for k in KEYWORDS): return line[:200]
    return lines[0][:200] if lines else ''

def classify(text, header):
    s=f'{text} {header}'.lower()
    if 'hospitality' in s: return 'hospitality_expense'
    if 'district capital' in s: return 'district_capital_expenditure'
    if 'district activity' in s: return 'district_activity_expenditure'
    if 'recreation area' in s or 'area rate' in s: return 'area_rate_expenditure'
    if 'capital projection' in s or ('capital' in s and 'actual' in s): return 'capital_summary'
    if 'reserve' in s: return 'reserve_summary'
    if 'expense' in s or 'expenditure' in s: return 'operating_expense_summary'
    return None

def row_label(row):
    for cell in row:
        c=clean(cell)
        if c and money(c) is None and not re.fullmatch(r'\d+(?:\.\d+)?%?',c): return c
    return ''

def main():
    reg=json.loads(REGISTRY.read_text(encoding='utf-8'))
    by_id={s['id']:s for s in reg['sources']}
    session=requests.Session(); session.headers['User-Agent']=UA
    records=[]; source_status=[]
    for source_id, period_end in PERIOD_END.items():
        src=by_id.get(source_id)
        if not src:
            source_status.append({'source_id':source_id,'status':'missing_registry'}); continue
        try:
            response=session.get(src['url'],timeout=120); response.raise_for_status()
            if not response.content.startswith(b'%PDF'): raise RuntimeError('response is not PDF')
            src_rows=0
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                for page_num,page in enumerate(pdf.pages,1):
                    text=page.extract_text() or ''
                    page_context=context_for(text)
                    for table_num,table in enumerate(page.extract_tables() or [],1):
                        normalized=[[clean(c) for c in (r or [])] for r in (table or [])]
                        if len(normalized)<2: continue
                        header=' | '.join(' '.join(r) for r in normalized[:3])
                        record_type=classify(text[:2500],header)
                        if not record_type: continue
                        for row_num,row in enumerate(normalized[1:],1):
                            label=row_label(row)
                            numeric=[money(c) for c in row]
                            numeric=[v for v in numeric if v is not None]
                            if not label or not numeric: continue
                            amount=numeric[-1]
                            # Skip rows that are clearly page/header metadata rather than facts.
                            if label.lower().startswith(('page ','halifax regional municipality','statement of')): continue
                            rec={
                              'record_type':record_type,
                              'posting_date':period_end,
                              'fiscal_year':'2024/25' if '2024-25' in source_id else '2023/24',
                              'business_unit':label if record_type=='operating_expense_summary' else None,
                              'account':page_context or record_type.replace('_',' '),
                              'category':page_context or record_type.replace('_',' '),
                              'amount':amount,
                              'values':numeric,
                              'raw_cells':row,
                              'source_page':page_num,
                              'source_id':source_id,
                              'granularity':'official_summary_table_row',
                              'provenance':provenance(source_id,src['url'],'page/table/row',f'p{page_num}/t{table_num}/r{row_num}')
                            }
                            records.append(rec); src_rows+=1
            source_status.append({'source_id':source_id,'status':'ok','records':src_rows})
        except Exception as exc:
            source_status.append({'source_id':source_id,'status':'error','error':f'{type(exc).__name__}: {exc}'})
    payload={'metadata':{
      'generated_at':now(),'records':len(records),'source_status':source_status,
      'granularity':'quarterly financial summary tables',
      'is_transaction_ledger':False,
      'note':'Official HRM quarterly report rows. This is not a complete transaction-level accounts-payable ledger; missing transaction detail is shown as a source gap rather than inferred.'
    },'records':records}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'quarterly spending summaries: {len(records)} rows')

if __name__=='__main__': main()
