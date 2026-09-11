#!/usr/bin/env python3
"""Build 020 sample proof for historical Council decision extraction.

This script does not modify the Build 016 parser. It selects a deterministic six-meeting
sample from the released historical Regional Council inventory, fetches those approved
minutes, then reuses ingest_council_decisions.py read/parse functions unchanged.

Sample policy:
- earliest minutes-bearing, non-status Regional Council meeting in each of
  2017, 2018, 2020, 2021, and 2024; plus
- 2023-12-12, an existing Build 016 legacy seed, for exact parser-equivalence control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import ingest_council_decisions as base

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = ROOT / "data/generated/council_archive.json"
DEFAULT_OUT = ROOT / "artifacts/build020-council-archive-decision-sample.json"
TARGET_YEARS = [2017, 2018, 2020, 2021, 2024]
CONTROL_DATE = "2023-12-12"
SOURCE_ID = "hrm-historical-council-table"
COVERAGE_LAYER = "historical_halifax_meeting_table_sample"
REQUEST_DELAY_SECONDS = 0.35


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def eligible(row: dict) -> bool:
    return bool(
        row.get("minutes_url")
        and row.get("has_minutes_pdf") is True
        and not row.get("meeting_date_note_source")
        and row.get("meeting_type") == "Regional Council"
    )


def choose_sources(archive: dict) -> list[dict]:
    rows = [row for row in archive.get("records") or [] if eligible(row)]
    selected: list[dict] = []
    for year in TARGET_YEARS:
        matches = sorted(
            [row for row in rows if str(row.get("meeting_date") or "").startswith(f"{year}-")],
            key=lambda row: (row["meeting_date"], row["archive_meeting_id"]),
        )
        if not matches:
            raise RuntimeError(f"No eligible historical Council minutes found for sample year {year}")
        selected.append(matches[0])

    control = [row for row in rows if row.get("meeting_date") == CONTROL_DATE]
    if len(control) != 1:
        raise RuntimeError(f"Expected exactly one eligible control meeting on {CONTROL_DATE}; found {len(control)}")
    selected.append(control[0])

    dates = [row["meeting_date"] for row in selected]
    if len(dates) != len(set(dates)):
        raise RuntimeError(f"Historical decision sample contains duplicate dates: {dates!r}")
    return sorted(selected, key=lambda row: row["meeting_date"])


def source_from_archive(row: dict) -> dict:
    return {
        "source_id": SOURCE_ID,
        "meeting_id": row["archive_meeting_id"],
        "meeting_date": row["meeting_date"],
        "meeting_name": "Halifax Regional Council",
        "minutes_url": row["minutes_url"],
        "coverage_layer": COVERAGE_LAYER,
        "archive_agenda_url": row.get("agenda_url"),
        "archive_source_search_url": row.get("source_search_url"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    if archive.get("metadata", {}).get("dataset_status") != "official_halifax_regional_council_historical_meeting_inventory":
        raise RuntimeError("Historical Council archive is not the released Build 020 inventory")
    selected_rows = choose_sources(archive)

    session = requests.Session()
    session.headers.update({"User-Agent": base.UA, "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.5"})

    all_records: list[dict] = []
    source_status: list[dict] = []
    for archive_row in selected_rows:
        source = source_from_archive(archive_row)
        time.sleep(REQUEST_DELAY_SECONDS)
        content, resolved_url = base.fetch_pdf(session, source["minutes_url"])
        sha = hashlib.sha256(content).hexdigest()
        source = {**source, "minutes_url": resolved_url, "source_sha256": sha}
        lines, page_count = base.read_pdf_lines(content)
        records, diagnostics = base.parse_decisions(lines, source)
        if not records:
            raise RuntimeError(
                f"Build 016 parser produced no paired motion outcomes for sample {source['meeting_date']} {resolved_url}"
            )
        all_records.extend(records)
        source_status.append({
            "source_id": SOURCE_ID,
            "meeting_id": source["meeting_id"],
            "meeting_date": source["meeting_date"],
            "coverage_layer": COVERAGE_LAYER,
            "minutes_url": resolved_url,
            "source_sha256": sha,
            "pdf_pages": page_count,
            "pdf_text_lines": len(lines),
            "decision_records": len(records),
            "archive_agenda_url": source.get("archive_agenda_url"),
            **diagnostics,
        })
        print(
            f"Historical Council sample {source['meeting_date']}: "
            f"{len(records)} paired outcomes from {page_count} pages; "
            f"unpaired={diagnostics.get('unpaired_result_lines', 0)}"
        )

    decision_ids = [row["decision_id"] for row in all_records]
    if len(decision_ids) != len(set(decision_ids)):
        raise RuntimeError("Historical sample produced duplicate decision IDs")
    all_records.sort(key=lambda row: (
        row["meeting_date"],
        row.get("item_ref") or "zzzz",
        int(row.get("source_page") or 0),
        row["decision_id"],
    ))

    payload = {
        "metadata": {
            "build": "020",
            "dataset_status": "historical_council_decision_sample_candidate",
            "generated_at": now(),
            "parser_version": base.PARSER_VERSION,
            "archive_source": str(ARCHIVE_PATH.relative_to(ROOT)),
            "sample_policy": "Earliest eligible minutes-bearing non-status Regional Council meeting in 2017, 2018, 2020, 2021 and 2024 plus exact Build 016 control date 2023-12-12.",
            "target_years": TARGET_YEARS,
            "control_date": CONTROL_DATE,
            "sample_meetings": len(source_status),
            "sample_dates": [item["meeting_date"] for item in source_status],
            "decision_records": len(all_records),
            "fiscal_relevant_records": sum(1 for row in all_records if row.get("fiscal_relevant")),
            "money_mention_records": sum(1 for row in all_records if row.get("money_mentions")),
            "source_status": source_status,
            "is_payment_ledger": False,
            "payment_facts": 0,
            "scope": "Sample-only reuse of the unchanged Build 016 approved-minutes motion/result parser against official historical Halifax Regional Council minutes discovered through the Build 020 archive inventory.",
            "note": "A parsed motion/result is Council decision evidence. Dollar mentions are source text, not invoices, vendor payments, final paid values or findings of wrongdoing.",
            "release_status": "candidate_not_production",
        },
        "records": all_records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["metadata"], indent=2))


if __name__ == "__main__":
    main()
