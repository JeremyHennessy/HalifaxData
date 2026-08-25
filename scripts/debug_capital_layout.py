#!/usr/bin/env python3
"""Temporary Build 008 parser diagnostic for selected project-sheet layouts."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean, fetch_pdf

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/sources.json"
OUT = ROOT / "data/generated/capital_current_layout_debug.json"
SOURCE_ID = "hrm-capital-2025-26"
TARGETS = {"CB210019", "CM210012", "BT37", "CB200014", "CM180008"}


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["id"] == SOURCE_ID)
    session = requests.Session()
    session.headers["User-Agent"] = "HalifaxData/0.8-parser-debug"
    blob = fetch_pdf(session, source)
    output = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            code = next((target for target in TARGETS if target in text), None)
            if not code:
                continue
            tables = []
            for table_index, table in enumerate(page.extract_tables() or [], 1):
                rows = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                tables.append({"table": table_index, "rows": rows})
            output.append({"project_code": code, "page": page_num, "text": text, "tables": tables})
    if {item["project_code"] for item in output} != TARGETS:
        raise RuntimeError(f"Did not locate all target projects: found {[item['project_code'] for item in output]}")
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(output)} capital parser diagnostics to {OUT}")


if __name__ == "__main__":
    main()
