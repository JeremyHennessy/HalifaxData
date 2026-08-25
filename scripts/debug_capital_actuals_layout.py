#!/usr/bin/env python3
"""Temporary diagnostic for 2025/26 quarterly capital projection summary layouts."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean
from ingest_capital_actuals_current import SOURCES, fetch_pdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/capital_actuals_layout_debug.json"


def main() -> None:
    session = requests.Session()
    session.headers["User-Agent"] = "HalifaxData/0.8-capital-actuals-debug"
    output = []
    for source in SOURCES:
        matched_pages = []
        error = None
        try:
            blob = fetch_pdf(session, source["url"])
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if not any(marker in text for marker in ["Capital Projection Summary", "Budget Category", "Projected Spend", "Capital Budget"]):
                        continue
                    tables = []
                    for table_num, table in enumerate(page.extract_tables() or [], 1):
                        rows = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                        tables.append({"table": table_num, "rows": rows})
                    # Also preserve text-strategy extraction because the source
                    # tables are visually ruled but not always encoded as cells.
                    text_tables = []
                    settings = {"vertical_strategy": "text", "horizontal_strategy": "text", "intersection_tolerance": 8, "snap_tolerance": 4}
                    for table_num, table in enumerate(page.extract_tables(table_settings=settings) or [], 1):
                        rows = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                        text_tables.append({"table": table_num, "rows": rows})
                    matched_pages.append({"page": page_num, "text": text, "tables": tables, "text_tables": text_tables})
        except Exception as exc:  # diagnostic must preserve earlier source output
            error = f"{type(exc).__name__}: {exc}"
        output.append({
            "source_id": source["source_id"],
            "quarter": source["quarter"],
            "matched_pages": matched_pages,
            "error": error,
        })
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(" | ".join(f"{item['quarter']}:{len(item['matched_pages'])} pages error={item['error']}" for item in output))


if __name__ == "__main__":
    main()
