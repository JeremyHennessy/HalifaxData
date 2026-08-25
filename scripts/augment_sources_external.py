#!/usr/bin/env python3
"""Upsert verified quarterly-report and Nova Scotia municipal machine-data sources.

Socrata visualization/chart IDs are not reliable row APIs. This registry updater
therefore points analytical source IDs at the underlying tabular datasets where
those have been verified through Socrata metadata/catalog discovery.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'data/sources.json'
UPSERTS=[
  {"id":"hrm-q2-2024-25","name":"Second Quarter 2024/25 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"Period ended Sep 30, 2024; operating results, district funds, reserves, capital and expense disclosures","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/241211afsc1321.pdf"},
  {"id":"hrm-q1-2023-24","name":"First Quarter 2023/24 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"First quarter 2023/24 financial report and attachments","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/231003rci04.pdf"},
  {"id":"hrm-q2-2023-24","name":"Second Quarter 2023/24 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"Second quarter 2023/24 financial report and attachments","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/231128rci06.pdf"},
  {"id":"hrm-q3-2023-24","name":"Third Quarter 2023/24 Financial Report","publisher":"Halifax Regional Municipality","category":"Budgets & actuals","coverage":"Third quarter 2023/24 financial report and attachments","ingestion":"Council report PDF tables","status":"ready","url":"https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/240305rci05.pdf"},
  {"id":"ns-municipal-operating-expenses","name":"Municipal General Operating Expenses by Source — 10 Year Summary","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"General Operating Fund expenses by category, fiscal years 2014/15–2023/24; municipality-type aggregate comparator","ingestion":"Socrata SODA API yn47-nx5r","status":"ready","url":"https://data.novascotia.ca/resource/yn47-nx5r.json"},
  {"id":"ns-municipal-operating-revenues","name":"Municipal General Operating Revenues by Source — 10 Year Summary","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"General Operating Fund revenues by source for regional, rural and town municipality types","ingestion":"Socrata SODA API 5r87-wtae","status":"ready","url":"https://data.novascotia.ca/resource/5r87-wtae.json"},
  {"id":"ns-municipal-operating-totals","name":"Municipal Fiscal Statistics — Operating Fund Total Revenues and Expenditures by Municipality","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"Consolidated operating-fund revenues and expenditures by municipality from Financial Information Returns","ingestion":"Socrata base dataset SODA API sbzw-ajrm (replaces broken chart thwb-cfp5)","status":"ready","url":"https://data.novascotia.ca/resource/sbzw-ajrm.json"},
  {"id":"ns-municipal-consolidated","name":"Municipal Fiscal Statistics — Consolidated Revenues and Expenses by Municipality","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"Consolidated municipal revenues and expenses by municipality","ingestion":"Socrata SODA API shcq-4v93","status":"ready","url":"https://data.novascotia.ca/resource/shcq-4v93.json"},
  {"id":"ns-municipal-fci","name":"Municipal Fiscal Statistics — Financial Condition Indicators","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"Financial-condition indicators derived from FIRs and audited statements, including HRM history through 2023/24","ingestion":"Socrata SODA API 44ah-ugrd","status":"ready","url":"https://data.novascotia.ca/resource/44ah-ugrd.json"},
  {"id":"ns-municipal-funding-programs","name":"Municipal Affairs Funding Programs","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External funding","coverage":"Province-wide program, area, fiscal-year and actual-funding totals; contextual unless a recipient municipality is explicitly identified","ingestion":"Socrata SODA API 5rgt-der6","status":"ready","url":"https://data.novascotia.ca/resource/5rgt-der6.json"},
  {"id":"ns-municipal-capacity-grants","name":"Municipal Financial Capacity Grant and Transitional Support Program","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External funding","coverage":"Municipal Financial Capacity Grant and transition support by municipality/year, including HRM","ingestion":"Socrata SODA API mi6g-4wz7","status":"ready","url":"https://data.novascotia.ca/resource/mi6g-4wz7.json"},
  {"id":"ns-uniform-assessment-regional","name":"Uniform Assessment","publisher":"Government of Nova Scotia / Open Data Nova Scotia","category":"External benchmarks","coverage":"Uniform assessment by municipality and year, 2006/07–2026/27; HRM selected from Region field","ingestion":"Socrata base dataset SODA API kuu2-92bp (replaces broken chart k8qq-y6un)","status":"ready","url":"https://data.novascotia.ca/resource/kuu2-92bp.json"}
]

def main():
    data=json.loads(PATH.read_text(encoding='utf-8'))
    by_id={row['id']:row for row in data['sources']}
    added=0; updated=0
    for row in UPSERTS:
        existing=by_id.get(row['id'])
        if existing is None:
            data['sources'].append(row); by_id[row['id']]=row; added+=1
        elif existing != row:
            existing.clear(); existing.update(row); updated+=1
    PATH.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'external/quarterly sources: {len(data["sources"])} total, {added} added, {updated} updated')

if __name__=='__main__': main()
