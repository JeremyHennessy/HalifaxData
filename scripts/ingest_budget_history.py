#!/usr/bin/env python3
"""Normalize budget tables across every registered HRM budget book that can be fetched."""
from __future__ import annotations
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import budget_records_from_table, clean, fetch_pdf, infer_page_context

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sources.json"
OUT = ROOT / "data" / "generated"
UA = "HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fiscal_label(src):
    match = re.search(r"(20\d{2})[/_-](\d{2,4})", src.get("name", "") + " " + src.get("coverage", ""))
    if match:
        first = match.group(1)
        second = match.group(2)
        if len(second) == 4:
            second = second[-2:]
        return f"{first}/{second}"
    return src["id"].replace("hrm-budget-", "")


def main():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = [s for s in registry["sources"] if s["id"].startswith("hrm-budget-") and str(s.get("status", "")).startswith("ready")]
    session = requests.Session(); session.headers["User-Agent"] = UA
    records = []
    tables = []
    source_status = []
    for src in sources:
        try:
            blob = fetch_pdf(session, src)
            src_rows = 0
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    context = infer_page_context(text)
                    for table_num, table in enumerate(page.extract_tables() or [], 1):
                        normalized = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                        if not normalized:
                            continue
                        tables.append({"source_id": src["id"], "fiscal_year": fiscal_label(src), "page": page_num, "table": table_num, "context": context, "rows": len(normalized), "header": normalized[:3]})
                        parsed = budget_records_from_table(normalized, page_num, context, src["id"], src["url"], fiscal_label(src))
                        for row in parsed:
                            row["source_status"] = src.get("status")
                            row["source_is_final"] = src.get("status") == "ready"
                        records.extend(parsed); src_rows += len(parsed)
            source_status.append({"source_id": src["id"], "status": "ok", "records": src_rows})
        except Exception as exc:
            source_status.append({"source_id": src["id"], "status": "error", "error": f"{type(exc).__name__}: {exc}"})
    payload = {
        "metadata": {
            "generated_at": now(),
            "records": len(records),
            "source_count": len(sources),
            "source_status": source_status,
            "note": "Historical budget extraction includes only tables with explicit actual/budget headers. Proposed/pre-COVID source states are retained and never silently promoted to final approved budgets."
        },
        "records": records,
    }
    index = {"metadata": {"generated_at": now(), "tables": len(tables), "source_count": len(sources)}, "records": tables}
    (OUT / "budget.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "budget_document_tables.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"budget history: {len(records)} rows from {len(sources)} registered budget sources")


if __name__ == "__main__":
    main()
