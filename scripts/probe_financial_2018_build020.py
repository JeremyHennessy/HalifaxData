#!/usr/bin/env python3
"""Probe the narrower official 2018 HRM audited-statement attachment.

This is a diagnostic only. It reuses the established Build 005 parser functions
unchanged and writes no production artifact. The probe proves whether the Build 017
2018 gap is source-packaging-specific rather than a parser-semantics defect.
"""
from __future__ import annotations

import io

import pdfplumber
import requests

import ingest_financial_history as base
from ingest_domains import fetch_pdf

SOURCE = {
    "id": "hrm-financials-2018",
    "name": "Audited Consolidated Financial Statements — 2018 Audit & Finance attachment",
    "publisher": "Halifax Regional Municipality",
    "status": "probe-only",
    "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/180718afsc1211.pdf",
}


def main() -> None:
    session = requests.Session()
    session.headers["User-Agent"] = base.UA
    blob = fetch_pdf(session, SOURCE)
    eligible_pages = 0
    records = []
    families: dict[str, int] = {}

    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(layout=True) or page.extract_text() or ""
            family, title = base.statement_context(text)
            if not family:
                continue
            eligible_pages += 1
            families[family] = families.get(family, 0) + 1
            multiplier = base.unit_multiplier(text)
            table_records, _ = base.parse_table_rows(
                SOURCE,
                2018,
                page_num,
                family,
                title,
                page.extract_tables() or [],
                multiplier,
            )
            records.extend(table_records)
            records.extend(
                base.parse_text_rows(
                    SOURCE,
                    2018,
                    page_num,
                    family,
                    title,
                    text,
                    multiplier,
                )
            )

    unique = {}
    priority = {"pdf_table_row": 0, "pdf_text_line": 1}
    records.sort(key=lambda row: priority.get(row["extraction_method"], 9))
    for row in records:
        key = (
            row["source_id"],
            row["source_page"],
            row["statement_family"],
            " ".join(row["line_item"].lower().split()),
            row["current_year"],
            row["prior_year"],
        )
        unique.setdefault(key, row)
    rows = list(unique.values())

    print(
        f"2018 alternate-source probe: eligible_pages={eligible_pages}; "
        f"records={len(rows)}; families={families}"
    )
    if eligible_pages < 1:
        raise SystemExit("2018 alternate official source still has zero eligible statement pages")
    if len(rows) < 10:
        raise SystemExit(f"2018 alternate official source produced only {len(rows)} conservative rows")
    for row in rows[:10]:
        print(
            row["source_page"],
            row["statement_family"],
            row["line_item"],
            row["current_year"],
            row["prior_year"],
            row["extraction_method"],
        )


if __name__ == "__main__":
    main()
