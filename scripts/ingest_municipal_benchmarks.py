#!/usr/bin/env python3
"""Pull Nova Scotia municipal machine datasets and retain Halifax-related rows."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'data/sources.json'
OUT=ROOT/'data/generated'
UA='HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)'
DATASETS={
 'ns-municipal-operating-expenses':'benchmark_operating_expenses',
 'ns-municipal-operating-totals':'benchmark_operating_totals',
 'ns-municipal-fci':'financial_condition_indicators',
 'ns-uniform-assessment-regional':'uniform_assessment',
 'ns-municipal-funding-programs':'municipal_funding_programs',
 'ns-municipal-capacity-grants':'municipal_capacity_grants',
}

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def is_halifax(row):
    joined=' | '.join(str(v) for v in row.values() if v is not None).lower()
    return 'halifax' in joined

def main():
    reg=json.loads(REGISTRY.read_text(encoding='utf-8')); by_id={s['id']:s for s in reg['sources']}
    session=requests.Session(); session.headers['User-Agent']=UA
    facts=[]; funding=[]; status=[]
    for source_id,dataset_type in DATASETS.items():
        src=by_id.get(source_id)
        if not src:
            status.append({'source_id':source_id,'status':'missing_registry'}); continue
        try:
            response=session.get(src['url'],params={'$limit':50000},timeout=120); response.raise_for_status()
            raw=response.json(); selected=[row for row in raw if is_halifax(row)]
            for index,row in enumerate(selected):
                fact={'dataset_type':dataset_type,'source_id':source_id,'raw':row,'source_row_index':index}
                if dataset_type.startswith('municipal_'):
                    funding.append(fact)
                else:
                    facts.append(fact)
            status.append({'source_id':source_id,'status':'ok','downloaded_rows':len(raw),'halifax_rows':len(selected)})
        except Exception as exc:
            status.append({'source_id':source_id,'status':'error','error':f'{type(exc).__name__}: {exc}'})
    benchmarks={'metadata':{'generated_at':now(),'records':len(facts),'source_status':status,'note':'Halifax-filtered rows from Nova Scotia municipal machine datasets. Raw API fields are retained until a source-specific semantic mapper is verified.'},'records':facts}
    extfund={'metadata':{'generated_at':now(),'records':len(funding),'source_status':status,'note':'Halifax-related rows from Nova Scotia municipal funding/grant datasets. Raw fields retained for provenance-safe normalization.'},'records':funding}
    (OUT/'benchmarks.json').write_text(json.dumps(benchmarks,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (OUT/'external_funding.json').write_text(json.dumps(extfund,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'municipal benchmarks={len(facts)} external funding={len(funding)}')
    print(json.dumps(status,indent=2))

if __name__=='__main__': main()
