#!/usr/bin/env python3
"""Add newly verified official/public-body sources without deleting existing registry entries."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "sources.json"

ADDITIONS = [
    {
        "id": "ns-awarded-tenders-socrata",
        "name": "Awarded Public Tenders — Nova Scotia Open Data API",
        "publisher": "Government of Nova Scotia / Open Data Nova Scotia",
        "category": "Procurement",
        "coverage": "Awarded public tenders April 2010 to present; vendor, amount, entity, category and dates",
        "ingestion": "Socrata SODA API m6ps-8j6u",
        "status": "ready",
        "url": "https://data.novascotia.ca/resource/m6ps-8j6u.json"
    },
    {
        "id": "hrm-budget-2024-25",
        "name": "2024/25 Budget and Business Plan",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "2024/25 with prior actuals, budget and projections",
        "ingestion": "PDF tables",
        "status": "ready",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/budget-finances/budgetbook_2024-25_final.pdf"
    },
    {
        "id": "hrm-budget-2023-24-draft",
        "name": "2023/24 Draft Budget and Business Plan",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "2023/24 draft plan; explicitly not treated as final approved budget",
        "ingestion": "PDF tables",
        "status": "ready-proposed",
        "url": "https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2023-24-draft-budget-and-business-plan.pdf"
    },
    {
        "id": "hrm-budget-2022-23",
        "name": "2022/23 Budget and Business Plan",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "2022/23 with historical comparison fields",
        "ingestion": "PDF tables",
        "status": "ready",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/budget-finances/BudgetBook_2022_23_FINAL.pdf"
    },
    {
        "id": "hrm-budget-2021-22",
        "name": "2021/22 Budget and Business Plan",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "2021/22 operating budget and business plan",
        "ingestion": "PDF tables",
        "status": "ready",
        "url": "https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/OperatingBudgetBook2122.pdf"
    },
    {
        "id": "hrm-budget-2020-21-precovid",
        "name": "2020/21 Budget and Business Plan — pre-COVID version",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "Pre-COVID 2020/21 plan; historical baseline, not represented as final pandemic-adjusted budget",
        "ingestion": "PDF tables",
        "status": "ready-historical",
        "url": "https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2021_BUDGETBOOK_PRECOVID.pdf"
    },
    {
        "id": "hrm-budget-2017-19-proposed",
        "name": "2017/18–2018/19 Multi-Year Budget and Business Plan — proposed",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "Proposed multi-year 2017/18 and 2018/19 budget with prior actuals",
        "ingestion": "PDF tables",
        "status": "ready-proposed",
        "url": "https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/Multi-Year_Business_and_Capital_Plans_Book.pdf"
    },
    {
        "id": "hrm-financials-2023",
        "name": "Audited Consolidated Financial Statements — 2023",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "Year ended March 31, 2023",
        "ingestion": "PDF tables",
        "status": "ready",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/budget-finances/march-31-2023-financial-statements_cao-approved.pdf"
    },
    {
        "id": "hrm-q3-2024-25",
        "name": "Third Quarter 2024/25 Financial Report",
        "publisher": "Halifax Regional Municipality",
        "category": "Budgets & actuals",
        "coverage": "Operating projection, reserves, capital projection, district funds, hospitality/official expenses and Council approvals through Dec. 31, 2024",
        "ingestion": "Council report PDF tables",
        "status": "ready",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250218afsc1312.pdf"
    },
    {
        "id": "hrm-capital-2024-25",
        "name": "2024/25 Capital Plan",
        "publisher": "Halifax Regional Municipality",
        "category": "Capital",
        "coverage": "2024/25 approved capital plan and multi-year project funding",
        "ingestion": "PDF tables",
        "status": "ready",
        "url": "https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/capitalplan_2024-25_final.pdf"
    },
    {
        "id": "hrm-capital-2023-24-draft",
        "name": "2023/24 Draft Capital Plan",
        "publisher": "Halifax Regional Municipality",
        "category": "Capital",
        "coverage": "2023/24 draft capital projects with multi-year forecasts; explicitly not final approved plan",
        "ingestion": "PDF tables",
        "status": "ready-proposed",
        "url": "https://www.halifax.ca/sites/default/files/documents/city-hall/budget-finances/2023-24-draft-capital-budget-e-book-updated-jan-3-2023.pdf"
    },
    {
        "id": "hrm-capital-2021-22",
        "name": "2021/22 Multi-Year Capital Plan — Budget Committee report",
        "publisher": "Halifax Regional Municipality",
        "category": "Capital",
        "coverage": "2021/22 multi-year capital plan including project codes and planned funding",
        "ingestion": "Council report PDF tables",
        "status": "ready",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/210224bc5-revised.pdf"
    }
]


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in data["sources"]}
    added = 0
    for row in ADDITIONS:
        if row["id"] not in by_id:
            data["sources"].append(row)
            by_id[row["id"]] = row
            added += 1
    data["metadata"]["last_researched"] = "2026-08-25"
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"source registry: {len(data['sources'])} total, {added} added")


if __name__ == "__main__":
    main()
