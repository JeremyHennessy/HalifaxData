#!/usr/bin/env python3
"""Validate the Build 020 historical Council decision sample candidate."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "artifacts/build020-council-archive-decision-sample.json"
ARCHIVE_PATH = ROOT / "data/generated/council_archive.json"
CURRENT_DECISIONS = ROOT / "data/generated/council_decisions.json"
TARGET_YEARS = [2017, 2018, 2020, 2021, 2024]
CONTROL_DATE = "2023-12-12"
EXPECTED_PARSER = "build016-council-decisions-v1"
EXPECTED_SOURCE_ID = "hrm-historical-council-table"
EXPECTED_COVERAGE = "historical_halifax_meeting_table_sample"


def eligible(row: dict) -> bool:
    return bool(
        row.get("minutes_url")
        and row.get("has_minutes_pdf") is True
        and not row.get("meeting_date_note_source")
        and row.get("meeting_type") == "Regional Council"
    )


def expected_sample_dates(archive: dict) -> list[str]:
    rows = [row for row in archive.get("records") or [] if eligible(row)]
    dates = []
    for year in TARGET_YEARS:
        matches = sorted(
            [row for row in rows if str(row.get("meeting_date") or "").startswith(f"{year}-")],
            key=lambda row: (row["meeting_date"], row["archive_meeting_id"]),
        )
        assert matches, f"Released archive has no eligible sample meeting for {year}"
        dates.append(matches[0]["meeting_date"])
    control = [row for row in rows if row.get("meeting_date") == CONTROL_DATE]
    assert len(control) == 1, f"Released archive control date {CONTROL_DATE} count = {len(control)}"
    dates.append(CONTROL_DATE)
    return sorted(dates)


def normalized_semantics(row: dict) -> dict:
    return {
        "decision_id": row.get("decision_id"),
        "meeting_date": row.get("meeting_date"),
        "item_ref": row.get("item_ref"),
        "item_title": row.get("item_title"),
        "mover": row.get("mover"),
        "seconder": row.get("seconder"),
        "motion_text": row.get("motion_text"),
        "result_source": row.get("result_source"),
        "decision_status": row.get("decision_status"),
        "motion_passed": row.get("motion_passed"),
        "fiscal_relevant": row.get("fiscal_relevant"),
        "money_mentions": row.get("money_mentions"),
        "procurement_refs": row.get("procurement_refs"),
        "case_refs": row.get("case_refs"),
        "capital_account_refs": row.get("capital_account_refs"),
        "source_page": row.get("source_page"),
        "source_locator": row.get("source_locator"),
        "parser_version": row.get("parser_version"),
        "validation_status": row.get("validation_status"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    args = parser.parse_args()

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    current = json.loads(CURRENT_DECISIONS.read_text(encoding="utf-8"))
    meta = candidate.get("metadata") or {}
    rows = candidate.get("records") or []

    assert meta.get("build") == "020", meta
    assert meta.get("dataset_status") == "historical_council_decision_sample_candidate", meta
    assert meta.get("parser_version") == EXPECTED_PARSER, meta
    assert meta.get("target_years") == TARGET_YEARS, meta
    assert meta.get("control_date") == CONTROL_DATE, meta
    assert meta.get("sample_meetings") == 6, meta
    expected_dates = expected_sample_dates(archive)
    assert meta.get("sample_dates") == expected_dates, (meta.get("sample_dates"), expected_dates)
    assert meta.get("decision_records") == len(rows), (meta.get("decision_records"), len(rows))
    assert len(rows) >= 30, f"Historical sample unexpectedly sparse: {len(rows)} decisions"
    assert meta.get("is_payment_ledger") is False, meta
    assert meta.get("payment_facts") == 0, meta
    assert meta.get("release_status") == "candidate_not_production", meta
    assert "not invoices" in str(meta.get("note") or "").lower(), meta

    statuses = meta.get("source_status") or []
    assert len(statuses) == 6, len(statuses)
    status_by_date = {item.get("meeting_date"): item for item in statuses}
    assert sorted(status_by_date) == expected_dates, sorted(status_by_date)
    for date in expected_dates:
        item = status_by_date[date]
        assert item.get("source_id") == EXPECTED_SOURCE_ID, item
        assert item.get("coverage_layer") == EXPECTED_COVERAGE, item
        assert isinstance(item.get("meeting_id"), str) and item["meeting_id"].startswith("hrm-regional-council-archive-"), item
        assert item.get("minutes_url") and item.get("source_sha256") and len(item["source_sha256"]) == 64, item
        assert int(item.get("pdf_pages") or 0) >= 2, item
        assert int(item.get("pdf_text_lines") or 0) >= 20, item
        assert int(item.get("decision_records") or 0) >= 1, item
        assert int(item.get("unpaired_result_lines") or 0) >= 0, item

    decision_ids = [row.get("decision_id") for row in rows]
    assert all(isinstance(value, str) and value.startswith("council-") for value in decision_ids)
    assert len(decision_ids) == len(set(decision_ids)), "Sample decision IDs are not unique"
    row_dates = Counter(row.get("meeting_date") for row in rows)
    assert set(row_dates) == set(expected_dates), row_dates
    assert all(count >= 1 for count in row_dates.values()), row_dates

    for row in rows:
        assert row.get("source_id") == EXPECTED_SOURCE_ID, row
        assert row.get("coverage_layer") == EXPECTED_COVERAGE, row
        assert row.get("parser_version") == EXPECTED_PARSER, row
        assert row.get("validation_status") == "parsed_from_approved_minutes", row
        assert row.get("source_sha256") and len(row["source_sha256"]) == 64, row
        assert row.get("source_url"), row
        assert int(row.get("source_page") or 0) >= 1, row
        assert row.get("motion_text"), row
        assert row.get("decision_status") in {"passed", "passed_unanimously", "defeated", "tied", "withdrawn", "other"}, row
        assert isinstance(row.get("money_mentions"), list), row
        assert isinstance(row.get("procurement_refs"), list), row
        assert isinstance(row.get("case_refs"), list), row
        assert isinstance(row.get("capital_account_refs"), list), row

    current_rows = current.get("records") or []
    current_dates = {row.get("meeting_date") for row in current_rows}
    historical_dates = [date for date in expected_dates if date != CONTROL_DATE]
    overlap_dates = sorted(date for date in historical_dates if date in current_dates)
    assert not overlap_dates, f"Historical sample dates already exist in current decisions: {overlap_dates!r}"

    # Exact parser-equivalence control. Decision identity intentionally excludes source
    # URL/SHA/source_id, so the unchanged parser should yield the same decision IDs and
    # semantic fields for the existing 2023-12-12 seed even though source selection now
    # comes from the released historical archive inventory.
    sample_control = [row for row in rows if row.get("meeting_date") == CONTROL_DATE]
    current_control = [row for row in current_rows if row.get("meeting_date") == CONTROL_DATE]
    assert sample_control and current_control, (len(sample_control), len(current_control))
    sample_map = {row["decision_id"]: normalized_semantics(row) for row in sample_control}
    current_map = {row["decision_id"]: normalized_semantics(row) for row in current_control}
    assert set(sample_map) == set(current_map), {
        "sample_only": sorted(set(sample_map) - set(current_map)),
        "current_only": sorted(set(current_map) - set(sample_map)),
    }
    mismatches = {
        decision_id: (sample_map[decision_id], current_map[decision_id])
        for decision_id in sample_map
        if sample_map[decision_id] != current_map[decision_id]
    }
    assert not mismatches, f"Build 016 parser semantic drift on control meeting: {list(mismatches)[:3]!r}"

    assert meta.get("fiscal_relevant_records") == sum(1 for row in rows if row.get("fiscal_relevant"))
    assert meta.get("money_mention_records") == sum(1 for row in rows if row.get("money_mentions"))

    print(json.dumps({
        "status": "ok",
        "sample_dates": expected_dates,
        "decision_records": len(rows),
        "decisions_by_date": dict(sorted(row_dates.items())),
        "new_historical_dates": historical_dates,
        "control_date": CONTROL_DATE,
        "control_decisions": len(sample_control),
        "control_parser_equivalence": "exact_decision_id_and_semantic_match",
        "payment_facts": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
