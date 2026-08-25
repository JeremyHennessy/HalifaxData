#!/usr/bin/env python3
"""Add verified quarterly-report and Nova Scotia municipal machine-data sources."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'data/sources.json'
ADDITIONS=[
  {"id":"hrm-q2-2024-25","name":"Second Quarter 2024/25 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"Period ended Sep 30, 2024; operating results, district funds, reserves, capital and expense disclosures","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/241211afsc1321.pdf"},
  {"id":"hrm-q1-2023-24","name":"First Quarter 2023/24 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"First quarter 2023/24 financial report and attachments","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/231003rci04.pdf"},
  {"id":"hrm-q2-2023-24","name":"Second Quarter 2023/24 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"Second quarter 2023/24 financial report and attachments","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/231128rci06.pdf"},
  {"id":"hrm-q3-2023-24","name":"Third Quarter 2023/24 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"Third quarter 2023/24 financial report and attachments","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/240305rci05.pdf"},
  {"id":"ns-municipal-operating-expenses","name":"Municipal General Operating Expenses by Source — 10 Year Summary","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"General Operating Fund expenses by category, fiscal years 2014/15–2023/24","ingestion":"Socrata SODA API yn47-nx5r","status":"ready","url":"https://data.novascotia.ca/resource/yn47-nx5r.json"},
  {"id":"ns-municipal-operating-totals","name":"Municipal Fiscal Statistics — Operating Fund Revenues and Expenditures by Regional Municipality","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"Consolidated municipal operating revenues and expenses from Financial Information Returns","ingestion":"Socrata SODA API thwb-cfp5","status":"ready","url":"https://data.novascotia.ca/resource/thwb-cfp5.json"},
  {"id":"ns-municipal-fci","name":"Municipal Fiscal Statistics — Financial Condition Indicators","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"Financial-condition indicators derived from FIRs and audited statements, 2016/17–2023/24","ingestion":"Socrata SODA API 44ah-ugrd","status":"ready","url":"https://data.novascotia.ca/resource/44ah-ugrd.json"},
  {"id":"ns-municipal-funding-programs","name":"Municipal Affairs Funding Programs","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External funding","coverage":"Funding program, area, fiscal year and actual funding amount","ingestion":"Socrata SODA API 5rgt-der6","status":"ready","url":"https://data.novascotia.ca/resource/5rgt-der6.json"},
  {"id":"ns-municipal-capacity-grants","name":"Municipal Financial Capacity Grant and Transitional Support Program","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External funding","coverage":"Municipal Financial Capacity Grant and transition support by municipality/year","ingestion":"Socrata SODA API mi6g-4wz7","status":"ready","url":"https://data.novascotia.ca/resource/mi6g-4wz7.json"},
  {"id":"ns-uniform-assessment-regional","name":"Uniform Assessment of Regional Municipality by Year","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"Regional-municipality uniform assessment by year","ingestion":"Socrata SODA API k8qq-y6un","status":"ready","url":"https://data.novascotia.ca/resource/k8qq-y6un.json"}
]

def main():
    data=json.loads(PATH.read_text(encoding='utf-8'))
    ids={row['id'] for row in data['sources']}
    added=0
    for row in ADDITIONS:
        if row['id'] not in ids:
            data['sources'].append(row); ids.add(row['id']); added+=1
    PATH.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'external/quarterly sources: {len(data["sources"])} total, {added} added')

if __name__=='__main__': main()
