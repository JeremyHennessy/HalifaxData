#!/usr/bin/env python3
"""Validate the Build 020 Halifax Regional Council historical archive candidate."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "artifacts/build020-council-archive.json"
SEEDS_PATH = ROOT / "data/council_decision_sources.json"
EXPECTED_CATEGORY = "931"
EXPECTED_RESULT_COUNT = 249
EXPECTED_MIN_DATE = "2016-01-12"
EXPECTED_MAX_DATE = "2024-11-05"
EXPECTED_BY_YEAR = {
    "2016": 31,
    "2017": 29,
    "2018": 26,
    "2019": 31,
    "2020": 30,
    "2021": 25,
    "2022": 28,
    "2023": 26,
    "2024": 23,
}
EXPECTED_DATE_NOTES = {"Cancelled": 3, "Rescheduled": 1}
EXPECTED_MINUTES = 245
EXPECTED_MISSING_MINUTES = 4
OFFICIAL_HOSTS = {"halifax.ca", "www.halifax.ca", "cdn.halifax.ca"}


def minutes_identity(url: str | None) -> str | None:
    if not url:
        return None
    return urlparse(url).path.lower().rstrip("/")


def clean_date_source(value: str | None, iso_date: str, note: str | None) -> bool:
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    expected_date = f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    expected = expected_date if not note else f"{expected_date} {note}"
    return str(value or "") == expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    args = parser.parse_args()

    payload = json.loads(args.candidate.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    rows = payload.get("records") or []
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))

    assert meta.get("build") == "020", meta
    assert meta.get("dataset_status") == "official_halifax_regional_council_historical_meeting_inventory_candidate", meta
    assert meta.get("source_category") == EXPECTED_CATEGORY, meta
    assert meta.get("advertised_result_count") == EXPECTED_RESULT_COUNT, meta
    assert meta.get("records") == EXPECTED_RESULT_COUNT == len(rows), (meta.get("records"), len(rows))
    assert meta.get("page_size") == 15, meta
    assert meta.get("pages_fetched") == 17, meta
    assert meta.get("min_meeting_date") == EXPECTED_MIN_DATE, meta
    assert meta.get("max_meeting_date") == EXPECTED_MAX_DATE, meta
    assert meta.get("records_by_year") == EXPECTED_BY_YEAR, meta
    assert meta.get("date_status_notes") == EXPECTED_DATE_NOTES, meta
    assert meta.get("minutes_pdf_records") == EXPECTED_MINUTES, meta
    assert meta.get("missing_minutes_records") == EXPECTED_MISSING_MINUTES, meta
    assert meta.get("release_status") == "candidate_not_production", meta
    assert "not Council decision extraction" in str(meta.get("scope") or ""), meta
    boundary = str(meta.get("earlier_archive_boundary") or "").lower()
    assert "2016-01-12" in boundary and "does not assert completeness before" in boundary, meta

    years = sorted({row["meeting_date"][:4] for row in rows})
    assert years == list(EXPECTED_BY_YEAR), years
    assert sum(EXPECTED_BY_YEAR.values()) == len(rows)

    ids = set()
    agenda_urls = set()
    date_minutes_pairs = set()
    missing_minutes_rows = []
    note_counts: dict[str, int] = {}
    for index, row in enumerate(rows):
        meeting_id = row.get("archive_meeting_id")
        assert isinstance(meeting_id, str) and meeting_id.startswith("hrm-regional-council-archive-"), (index, meeting_id)
        assert meeting_id not in ids, (index, meeting_id)
        ids.add(meeting_id)
        assert row.get("meeting_type") == "Regional Council", (index, row.get("meeting_type"))
        assert row.get("source_category") == EXPECTED_CATEGORY, index
        assert row.get("publisher") == "Halifax Regional Municipality", index
        assert row.get("source_kind") == "official_historical_meeting_table", index
        date = str(row.get("meeting_date") or "")
        assert len(date) == 10 and date[:4] in years, (index, date)
        date_note = row.get("meeting_date_note_source")
        if date_note:
            note_counts[date_note] = note_counts.get(date_note, 0) + 1
            assert date_note in EXPECTED_DATE_NOTES, (index, date_note)
        assert clean_date_source(row.get("meeting_date_source"), date, date_note), (index, row.get("meeting_date_source"))

        agenda = row.get("agenda_url")
        assert agenda and (urlparse(agenda).hostname or "").lower() in OFFICIAL_HOSTS, (index, agenda)
        assert "/city-hall/regional-council/" in urlparse(agenda).path.lower(), (index, agenda)
        assert agenda not in agenda_urls, f"duplicate agenda/details URL: {agenda}"
        agenda_urls.add(agenda)

        minutes = row.get("minutes_url")
        if minutes:
            assert row.get("has_minutes_pdf") is True, index
            assert (urlparse(minutes).hostname or "").lower() in OFFICIAL_HOSTS, (index, minutes)
            assert urlparse(minutes).path.lower().endswith(".pdf"), (index, minutes)
            assert row.get("minutes_identity") == minutes_identity(minutes), (index, minutes)
            pair = (date, row.get("minutes_identity"))
            assert pair not in date_minutes_pairs, f"duplicate date/minutes identity: {pair}"
            date_minutes_pairs.add(pair)
        else:
            assert row.get("has_minutes_pdf") is False, index
            assert row.get("minutes_identity") is None, index
            missing_minutes_rows.append(row)

        page_index = row.get("source_page_index")
        row_index = row.get("source_row_index")
        assert isinstance(page_index, int) and 0 <= page_index < meta.get("pages_fetched"), (index, page_index)
        assert isinstance(row_index, int) and row_index >= 1, (index, row_index)
        assert f"category={EXPECTED_CATEGORY}" in str(row.get("source_search_url") or ""), (index, row.get("source_search_url"))

    assert note_counts == EXPECTED_DATE_NOTES, note_counts
    assert len(missing_minutes_rows) == EXPECTED_MISSING_MINUTES, len(missing_minutes_rows)
    assert all(row.get("meeting_date_note_source") in EXPECTED_DATE_NOTES for row in missing_minutes_rows), missing_minutes_rows

    # Existing hand-picked seeds are independent controls. The six 2019-2023 seeds
    # retain the same official PDF path in the current table. The 2016 seed has moved
    # from the legacy /council/agendasc path to a different current-site official PDF;
    # reconcile that one by exact date and require a single minutes-bearing Council row.
    legacy = seeds.get("legacy_sources") or []
    assert len(legacy) == 7, len(legacy)
    seed_2016 = [seed for seed in legacy if seed.get("meeting_date") == "2016-06-14"]
    assert len(seed_2016) == 1, seed_2016
    rows_2016_seed_date = [row for row in rows if row.get("meeting_date") == "2016-06-14"]
    assert len(rows_2016_seed_date) == 1, rows_2016_seed_date
    relocated_2016 = rows_2016_seed_date[0]
    assert relocated_2016.get("minutes_url") and relocated_2016.get("has_minutes_pdf") is True, relocated_2016
    assert relocated_2016.get("minutes_identity") != minutes_identity(seed_2016[0].get("minutes_url")), "2016 source relocation unexpectedly disappeared"

    exact_seeds = [seed for seed in legacy if seed.get("meeting_date") != "2016-06-14"]
    assert len(exact_seeds) == 6, len(exact_seeds)
    row_pairs = {(row["meeting_date"], row.get("minutes_identity")) for row in rows if row.get("minutes_identity")}
    missing_seeds = []
    for seed in exact_seeds:
        expected = (seed["meeting_date"], minutes_identity(seed.get("minutes_url")))
        if expected not in row_pairs:
            missing_seeds.append(expected)
    assert not missing_seeds, f"Known 2019-2023 seed minutes missing from official archive inventory: {missing_seeds!r}"

    page_status = meta.get("page_status") or []
    assert len(page_status) == meta.get("pages_fetched"), len(page_status)
    assert sum(int(item.get("rows") or 0) for item in page_status) == len(rows), page_status
    for item in page_status[:-1]:
        assert item.get("rows") == meta.get("page_size"), item
    assert page_status[-1].get("rows") == 9, page_status[-1]

    print(json.dumps({
        "status": "ok",
        "records": len(rows),
        "date_range": [meta["min_meeting_date"], meta["max_meeting_date"]],
        "years": years,
        "records_by_year": EXPECTED_BY_YEAR,
        "date_status_notes": note_counts,
        "minutes_pdf_records": meta["minutes_pdf_records"],
        "missing_minutes_records": meta["missing_minutes_records"],
        "exact_seed_path_matches": len(exact_seeds),
        "relocated_2016_seed_match": {
            "meeting_date": relocated_2016["meeting_date"],
            "legacy_minutes_identity": minutes_identity(seed_2016[0].get("minutes_url")),
            "current_minutes_identity": relocated_2016["minutes_identity"],
        },
        "pages_fetched": meta["pages_fetched"],
    }, indent=2))


if __name__ == "__main__":
    main()
