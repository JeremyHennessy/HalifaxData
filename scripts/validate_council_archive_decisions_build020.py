#!/usr/bin/env python3
"""Validate the Build 020 full historical Council decision archive candidate."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "artifacts/build020-council-archive-decisions.json"
ARCHIVE_PATH = ROOT / "data/generated/council_archive.json"
CURRENT_DECISIONS = ROOT / "data/generated/council_decisions.json"
SEEDS_PATH = ROOT / "data/council_decision_sources.json"
EXPECTED_PARSER = "build016-council-decisions-v1"
EXPECTED_SOURCE_ID = "hrm-historical-council-table"
EXPECTED_COVERAGE = "historical_halifax_meeting_table"
NO_MOTION_PATH = ROOT / "data/council_no_motion_sources_build020.json"


def eligible(row: dict) -> bool:
    return bool(
        row.get("minutes_url")
        and row.get("has_minutes_pdf") is True
        and not row.get("meeting_date_note_source")
        and row.get("meeting_type") == "Regional Council"
    )


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
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    reviews = json.loads(NO_MOTION_PATH.read_text(encoding="utf-8"))["sources"]
    reviews_by_date = {row["meeting_date"]: row for row in reviews}
    assert len(reviews) == len(reviews_by_date) == 4
    assert set(reviews_by_date) == {"2016-02-03", "2016-11-01", "2020-10-29", "2024-11-05"}
    meta = candidate.get("metadata") or {}
    rows = candidate.get("records") or []

    archive_rows = list(archive.get("records") or [])
    eligible_rows = sorted([row for row in archive_rows if eligible(row)], key=lambda row: (row["meeting_date"], row["archive_meeting_id"]))
    expected_meeting_ids = {row["archive_meeting_id"] for row in eligible_rows}
    expected_dates_by_id = {row["archive_meeting_id"]: row["meeting_date"] for row in eligible_rows}
    assert len(eligible_rows) == 245, len(eligible_rows)

    assert meta.get("build") == "020", meta
    assert meta.get("dataset_status") == "historical_council_decision_archive_candidate", meta
    assert meta.get("parser_version") == EXPECTED_PARSER, meta
    assert meta.get("archive_records") == 249, meta
    assert meta.get("eligible_minutes_sources") == len(eligible_rows) == 245, meta
    assert meta.get("decision_records") == len(rows), (meta.get("decision_records"), len(rows))
    assert meta.get("is_payment_ledger") is False, meta
    assert meta.get("payment_facts") == 0, meta
    assert meta.get("release_status") == "candidate_not_production", meta
    assert "not invoices" in str(meta.get("note") or "").lower(), meta

    statuses = meta.get("source_status") or []
    assert len(statuses) == len(eligible_rows), (len(statuses), len(eligible_rows))
    status_ids = [item.get("meeting_id") for item in statuses]
    assert len(status_ids) == len(set(status_ids)), "Historical candidate source status contains duplicate meeting IDs"
    assert set(status_ids) == expected_meeting_ids, {
        "missing": sorted(expected_meeting_ids - set(status_ids))[:20],
        "unexpected": sorted(set(status_ids) - expected_meeting_ids)[:20],
    }
    status_counts = Counter(item.get("status") for item in statuses)
    assert dict(sorted(status_counts.items())) == meta.get("source_status_counts"), (status_counts, meta.get("source_status_counts"))
    assert not status_counts.get("error"), f"Historical candidate has {status_counts['error']} source errors"
    assert not status_counts.get("parse_gap"), f"Historical candidate has {status_counts['parse_gap']} parser gaps"
    assert set(status_counts) <= {"parsed", "verified_no_motion_outcomes"}, status_counts
    assert status_counts.get("verified_no_motion_outcomes") == len(reviews), status_counts
    assert status_counts.get("parsed") == len(eligible_rows) - len(reviews), status_counts

    decisions_by_status = sum(int(item.get("decision_records") or 0) for item in statuses)
    assert decisions_by_status == len(rows), (decisions_by_status, len(rows))
    for item in statuses:
        meeting_id = item.get("meeting_id")
        assert item.get("status") in {"parsed", "verified_no_motion_outcomes"}, item
        assert item.get("source_id") == EXPECTED_SOURCE_ID, item
        assert item.get("coverage_layer") == EXPECTED_COVERAGE, item
        assert item.get("meeting_date") == expected_dates_by_id[meeting_id], item
        assert item.get("minutes_url") and item.get("source_sha256") and len(item["source_sha256"]) == 64, item
        assert int(item.get("pdf_pages") or 0) >= 2, item
        assert int(item.get("pdf_text_lines") or 0) >= 20, item
        assert int(item.get("unpaired_result_lines") or 0) >= 0, item
        if item["status"] == "verified_no_motion_outcomes":
            review = reviews_by_date[item["meeting_date"]]
            assert all(item.get(key) == review[key] for key in
                       ("minutes_url", "source_sha256", "pdf_pages", "review_note")), item
            assert item.get("review_registry") == "data/council_no_motion_sources_build020.json", item
            assert item.get("decision_records") == 0 and item.get("unpaired_result_lines") == 0, item
        else:
            assert int(item.get("decision_records") or 0) >= 1, item
    assert {item["meeting_date"] for item in statuses if item["status"] == "verified_no_motion_outcomes"} == set(reviews_by_date)

    decision_ids = [row.get("decision_id") for row in rows]
    assert len(decision_ids) == len(set(decision_ids)), "Historical candidate decision IDs are not unique"
    row_counts_by_date = Counter(row.get("meeting_date") for row in rows)
    expected_dates = {row["meeting_date"] for row in eligible_rows}
    expected_decision_dates = expected_dates - set(reviews_by_date)
    assert set(row_counts_by_date) == expected_decision_dates, {
        "dates_without_decisions": sorted(expected_decision_dates - set(row_counts_by_date))[:20],
        "unexpected_dates": sorted(set(row_counts_by_date) - expected_dates)[:20],
    }
    assert all(value >= 1 for value in row_counts_by_date.values())

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

    years = sorted({row["meeting_date"][:4] for row in eligible_rows})
    assert years == [str(year) for year in range(2016, 2025)], years
    parsed_meetings_by_year = Counter(item["meeting_date"][:4] for item in statuses if item["status"] == "parsed")
    expected_meetings_by_year = Counter(row["meeting_date"][:4] for row in eligible_rows if row["meeting_date"] not in reviews_by_date)
    assert parsed_meetings_by_year == expected_meetings_by_year, (parsed_meetings_by_year, expected_meetings_by_year)
    assert meta.get("parsed_meetings_by_year") == dict(sorted(parsed_meetings_by_year.items())), meta.get("parsed_meetings_by_year")
    decisions_by_year = Counter(row["meeting_date"][:4] for row in rows)
    assert meta.get("decisions_by_year") == dict(sorted(decisions_by_year.items())), meta.get("decisions_by_year")
    assert all(decisions_by_year[year] >= parsed_meetings_by_year[year] for year in years), (decisions_by_year, parsed_meetings_by_year)

    # Existing seven seed meetings are exact semantic controls for the unchanged parser.
    # Source URL/SHA/page locator are intentionally excluded so the deterministic 2016
    # current-site relocation can still prove the same motion/result semantics.
    seed_dates = sorted(seed["meeting_date"] for seed in seeds.get("legacy_sources") or [])
    assert len(seed_dates) == 7 and len(set(seed_dates)) == 7, seed_dates
    current_rows = current.get("records") or []
    equivalence = {}
    for date in seed_dates:
        candidate_seed = [row for row in rows if row.get("meeting_date") == date]
        current_seed = [row for row in current_rows if row.get("meeting_date") == date]
        assert candidate_seed and current_seed, (date, len(candidate_seed), len(current_seed))
        candidate_map = {row["decision_id"]: normalized_semantics(row) for row in candidate_seed}
        current_map = {row["decision_id"]: normalized_semantics(row) for row in current_seed}
        assert set(candidate_map) == set(current_map), {
            "meeting_date": date,
            "candidate_only": sorted(set(candidate_map) - set(current_map))[:10],
            "current_only": sorted(set(current_map) - set(candidate_map))[:10],
        }
        mismatches = [decision_id for decision_id in candidate_map if candidate_map[decision_id] != current_map[decision_id]]
        assert not mismatches, f"Parser semantic drift for seed {date}: {mismatches[:10]!r}"
        equivalence[date] = len(candidate_seed)

    # The archive ends before modern eSCRIBE coverage. Therefore overlap with the
    # currently released decision set should consist only of the seven legacy seeds.
    current_dates = {row.get("meeting_date") for row in current_rows}
    candidate_dates = set(row_counts_by_date)
    overlap_dates = sorted(candidate_dates & current_dates)
    assert overlap_dates == seed_dates, (overlap_dates, seed_dates)
    new_dates = candidate_dates - current_dates
    assert len(new_dates) == len(expected_decision_dates) - len(seed_dates), (len(new_dates), len(expected_decision_dates), len(seed_dates))
    assert len(new_dates) >= 230, len(new_dates)

    assert meta.get("fiscal_relevant_records") == sum(1 for row in rows if row.get("fiscal_relevant"))
    assert meta.get("money_mention_records") == sum(1 for row in rows if row.get("money_mentions"))

    print(json.dumps({
        "status": "ok",
        "eligible_minutes_sources": len(eligible_rows),
        "parsed_sources": status_counts.get("parsed"),
        "verified_no_motion_sources": status_counts.get("verified_no_motion_outcomes"),
        "parse_gaps": status_counts.get("parse_gap", 0),
        "errors": status_counts.get("error", 0),
        "decision_records": len(rows),
        "years": years,
        "parsed_meetings_by_year": dict(sorted(parsed_meetings_by_year.items())),
        "decisions_by_year": dict(sorted(decisions_by_year.items())),
        "legacy_seed_equivalence": equivalence,
        "new_historical_meeting_dates": len(new_dates),
        "payment_facts": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
