#!/usr/bin/env python3
"""Print source context for selected Build 019 exact identifiers.

Diagnostic only. This script never writes artifacts and never creates links.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC_RE = re.compile(r"\b(?:HRM-)?((?:20)?\d{2})\s*-\s*(\d{3,5})\b", re.I)


def canon(value):
    match = PROC_RE.search(str(value or ""))
    if not match:
        return None
    year, num = match.groups()
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{num}"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def row_refs(row):
    values = []
    for key in ("procurement_refs", "solicitation", "award_id", "project_number"):
        value = row.get(key)
        if isinstance(value, list):
            values.extend(value)
        else:
            values.append(value)
    return {canon(value) for value in values if canon(value)}


def emit(label, rows, wanted):
    print(f"\n## {label}")
    found = 0
    for row in rows:
        overlap = sorted(row_refs(row) & wanted)
        if not overlap:
            continue
        found += 1
        print(json.dumps({
            "refs": overlap,
            "decision_id": row.get("decision_id"),
            "meeting_id": row.get("meeting_id"),
            "meeting_date": row.get("meeting_date"),
            "item_ref": row.get("item_ref"),
            "item_title": row.get("item_title"),
            "motion_text": row.get("motion_text"),
            "decision_status": row.get("decision_status"),
            "award_id": row.get("award_id"),
            "description": row.get("description"),
            "vendor_name": row.get("vendor_name") or row.get("vendor_display_name"),
            "project_number": row.get("project_number"),
            "award_title": row.get("award_title"),
            "report_document_id": row.get("report_document_id"),
            "id": row.get("id"),
            "report_date": row.get("report_date"),
            "name_source": row.get("name_source"),
            "contract_key": row.get("contract_key"),
            "source_id": row.get("source_id"),
            "source_locator": row.get("source_locator") or (row.get("provenance") or {}).get("locator_value"),
            "source_url": row.get("source_url") or (row.get("provenance") or {}).get("source_url"),
        }, ensure_ascii=False, indent=2))
    print(f"matches={found}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("refs", nargs="+")
    args = parser.parse_args()
    wanted = {canon(value) or value for value in args.refs}

    council = load("data/generated/council_decisions.json")
    procurement = load("data/generated/procurement.json")
    quarterly = load("data/generated/procurement_quarterly.json")
    amendments = load("data/generated/contract_amendments.json")

    emit("Council decisions", council.get("records") or [], wanted)
    emit("Public tender awards", procurement.get("records") or [], wanted)
    emit("Quarterly HRM awards", quarterly.get("alternative_procurement") or [], wanted)
    emit("CAO amendments", amendments.get("observations") or [], wanted)


if __name__ == "__main__":
    main()
