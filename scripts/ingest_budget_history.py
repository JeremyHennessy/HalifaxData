#!/usr/bin/env python3
"""Normalize historical budget tables without touching Build 004 budget.json.

Historical budget PDFs vary considerably. This collector fails closed on source
errors, rejects merged/malformed numeric cells through the strict table helper,
and removes only exact same-page semantic duplicates caused by PDF table
extraction overlap.
"""
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
REGISTRY = ROOT / "data/sources.json"
OUT = ROOT / "data/generated"
UA = "HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)"
PARSER_VERSION = "build005-budget-history-v2"


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


def fact_key(row: dict) -> tuple:
    return (
        row.get("source_id"),
        row.get("source_page"),
        clean(row.get("business_unit")).casefold(),
        clean(row.get("service_area")).casefold(),
        row.get("prior_actual"),
        row.get("prior_budget"),
        row.get("projection"),
        row.get("current_budget"),
    )


def main():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = [
        source
        for source in registry["sources"]
        if source["id"].startswith("hrm-budget-") and str(source.get("status", "")).startswith("ready")
    ]
    session = requests.Session()
    session.headers["User-Agent"] = UA
    records = []
    tables = []
    source_status = []
    total_rejected_invalid_numeric_rows = 0
    total_duplicates_removed = 0

    for src in sources:
        try:
            blob = fetch_pdf(session, src)
            source_records = []
            parse_stats: dict[str, int] = {}
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    context = infer_page_context(text)
                    for table_num, table in enumerate(page.extract_tables() or [], 1):
                        normalized = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                        if not normalized:
                            continue
                        tables.append({
                            "source_id": src["id"],
                            "fiscal_year": fiscal_label(src),
                            "page": page_num,
                            "table": table_num,
                            "context": context,
                            "rows": len(normalized),
                            "header": normalized[:3],
                        })
                        parsed = budget_records_from_table(
                            normalized,
                            page_num,
                            context,
                            src["id"],
                            src["url"],
                            fiscal_label(src),
                            table_num=table_num,
                            parse_stats=parse_stats,
                        )
                        for row in parsed:
                            row["source_status"] = src.get("status")
                            row["source_is_final"] = src.get("status") == "ready"
                        source_records.extend(parsed)

            deduped = []
            seen = set()
            duplicates_removed = 0
            for row in source_records:
                key = fact_key(row)
                if key in seen:
                    duplicates_removed += 1
                    continue
                seen.add(key)
                deduped.append(row)

            rejected = parse_stats.get("rejected_invalid_numeric_rows", 0)
            total_rejected_invalid_numeric_rows += rejected
            total_duplicates_removed += duplicates_removed
            if not deduped:
                source_status.append({
                    "source_id": src["id"],
                    "status": "parse_gap",
                    "records": 0,
                    "rejected_invalid_numeric_rows": rejected,
                    "duplicates_removed": duplicates_removed,
                    "note": "Source downloaded but no conservative historical budget rows were normalized.",
                })
            else:
                source_status.append({
                    "source_id": src["id"],
                    "status": "ok",
                    "records": len(deduped),
                    "rejected_invalid_numeric_rows": rejected,
                    "duplicates_removed": duplicates_removed,
                })
                records.extend(deduped)
        except Exception as exc:
            source_status.append({
                "source_id": src["id"],
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            })

    if any(item.get("status") != "ok" for item in source_status):
        raise RuntimeError(f"One or more historical budget sources failed conservative extraction: {source_status!r}")
    if len(records) < 10:
        raise RuntimeError(f"Only {len(records)} historical budget rows extracted; refusing to replace artifact")

    records.sort(key=lambda row: (
        row.get("source_id") or "",
        row.get("source_page") or 0,
        row.get("source_table") or 0,
        row.get("source_row") or 0,
        row.get("service_area") or "",
    ))
    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "conservative_historical_budget_table_extraction",
            "parser_version": PARSER_VERSION,
            "records": len(records),
            "source_count": len(sources),
            "source_status": source_status,
            "rejected_invalid_numeric_rows": total_rejected_invalid_numeric_rows,
            "duplicates_removed": total_duplicates_removed,
            "note": (
                "Historical budget extraction includes only tables with explicit actual/budget headers and "
                "single-value numeric cells. Proposed/pre-COVID source states are retained and never silently "
                "promoted to final approved budgets. Current Build 004 budget.json remains a separate authoritative contract."
            ),
        },
        "records": records,
    }
    index = {
        "metadata": {
            "generated_at": now(),
            "parser_version": PARSER_VERSION,
            "tables": len(tables),
            "source_count": len(sources),
        },
        "records": tables,
    }
    (OUT / "budget_history.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "budget_document_tables.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"budget history: {len(records)} conservative rows from {len(sources)} registered budget sources; "
        f"rejected_invalid_numeric_rows={total_rejected_invalid_numeric_rows}; "
        f"duplicates_removed={total_duplicates_removed}"
    )
    print(json.dumps(source_status, indent=2))


if __name__ == "__main__":
    main()
