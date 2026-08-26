#!/usr/bin/env python3
"""Discover recurring procurement/award documents from the checked-in Council graph.

Discovery is intentionally read-only. It identifies source candidates and prints a
machine-readable summary so Build 011 can establish recurring report coverage before
any procurement-lifecycle artifact is published.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "data" / "generated" / "council_documents.json"

PROCUREMENT_RE = re.compile(r"\b(procurement|tender|award|contract)\b", re.I)
RECURRING_RE = re.compile(r"\b(procurement.*report|report.*procurement|award.*report|report.*award)\b", re.I)


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def main() -> None:
    payload = json.loads(DOCS.read_text(encoding="utf-8"))
    rows = payload.get("records") or []
    candidates = []
    recurring = []
    for row in rows:
        title = clean(row.get("title"))
        if not PROCUREMENT_RE.search(title):
            continue
        item = {
            "document_id": row.get("document_id"),
            "meeting_id": row.get("meeting_id"),
            "meeting_start_date": row.get("meeting_start_date"),
            "title": title,
            "url": row.get("url"),
            "finance_tags": row.get("finance_tags") or [],
        }
        candidates.append(item)
        if RECURRING_RE.search(title):
            recurring.append(item)

    candidates.sort(key=lambda row: (str(row.get("meeting_start_date") or ""), row["title"]), reverse=True)
    recurring.sort(key=lambda row: (str(row.get("meeting_start_date") or ""), row["title"]), reverse=True)
    years = Counter(str(row.get("meeting_start_date") or "")[:4] for row in candidates if row.get("meeting_start_date"))

    result = {
        "document_graph_records": len(rows),
        "procurement_title_candidates": len(candidates),
        "recurring_report_title_candidates": len(recurring),
        "candidate_year_counts": dict(sorted(years.items())),
        "recurring_candidates": recurring,
        "all_candidates": candidates,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
