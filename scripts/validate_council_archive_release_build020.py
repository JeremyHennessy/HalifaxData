#!/usr/bin/env python3
"""Validate the checked-in Build 020 Regional Council historical archive release."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/generated/council_archive.json"
SEEDS_PATH = ROOT / "data/council_decision_sources.json"
EXPECTED_BY_YEAR = {
    "2016": 31, "2017": 29, "2018": 26, "2019": 31, "2020": 30,
    "2021": 25, "2022": 28, "2023": 26, "2024": 23,
}
EXPECTED_NOTES = {"Cancelled": 3, "Rescheduled": 1}
OFFICIAL_HOSTS = {"halifax.ca", "www.halifax.ca", "cdn.halifax.ca"}


def minutes_identity(url: str | None) -> str | None:
    return urlparse(url).path.lower().rstrip("/") if url else None


def main() -> None:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    rows = payload.get("records") or []
    assert meta.get("build") == "020", meta
    assert meta.get("dataset_status") == "official_halifax_regional_council_historical_meeting_inventory", meta
    assert meta.get("release_status") == "released_checked_in", meta
    assert meta.get("source_category") == "931", meta
    assert meta.get("advertised_result_count") == 249 == meta.get("records") == len(rows), meta
    assert meta.get("page_size") == 15 and meta.get("pages_fetched") == 17, meta
    assert meta.get("min_meeting_date") == "2016-01-12", meta
    assert meta.get("max_meeting_date") == "2024-11-05", meta
    assert meta.get("records_by_year") == EXPECTED_BY_YEAR, meta
    assert meta.get("date_status_notes") == EXPECTED_NOTES, meta
    assert meta.get("minutes_pdf_records") == 245, meta
    assert meta.get("missing_minutes_records") == 4, meta
    assert "does not expand council_decisions.json" in str(meta.get("note") or ""), meta

    ids = [row.get("archive_meeting_id") for row in rows]
    assert len(ids) == len(set(ids)) == 249
    years = Counter(row.get("meeting_date", "")[:4] for row in rows)
    assert dict(sorted(years.items())) == EXPECTED_BY_YEAR, years
    notes = Counter(row.get("meeting_date_note_source") for row in rows if row.get("meeting_date_note_source"))
    assert dict(sorted(notes.items())) == EXPECTED_NOTES, notes
    missing_minutes = [row for row in rows if not row.get("minutes_url")]
    assert len(missing_minutes) == 4
    assert all(row.get("meeting_date_note_source") in EXPECTED_NOTES for row in missing_minutes), missing_minutes

    for row in rows:
        assert row.get("meeting_type") == "Regional Council", row
        assert row.get("source_category") == "931", row
        assert row.get("source_kind") == "official_historical_meeting_table", row
        agenda = row.get("agenda_url")
        assert agenda and (urlparse(agenda).hostname or "").lower() in OFFICIAL_HOSTS, agenda
        minutes = row.get("minutes_url")
        if minutes:
            assert row.get("has_minutes_pdf") is True, row
            assert (urlparse(minutes).hostname or "").lower() in OFFICIAL_HOSTS, minutes
            assert urlparse(minutes).path.lower().endswith(".pdf"), minutes
            assert row.get("minutes_identity") == minutes_identity(minutes), row
        else:
            assert row.get("has_minutes_pdf") is False, row
            assert row.get("minutes_identity") is None, row

    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8")).get("legacy_sources") or []
    assert len(seeds) == 7, len(seeds)
    exact = [seed for seed in seeds if seed.get("meeting_date") != "2016-06-14"]
    row_pairs = {(row.get("meeting_date"), row.get("minutes_identity")) for row in rows if row.get("minutes_identity")}
    assert all((seed["meeting_date"], minutes_identity(seed.get("minutes_url"))) in row_pairs for seed in exact)
    seed_2016 = [seed for seed in seeds if seed.get("meeting_date") == "2016-06-14"]
    rows_2016 = [row for row in rows if row.get("meeting_date") == "2016-06-14"]
    assert len(seed_2016) == 1 and len(rows_2016) == 1
    assert rows_2016[0].get("minutes_url")
    assert rows_2016[0].get("minutes_identity") != minutes_identity(seed_2016[0].get("minutes_url"))

    page_status = meta.get("page_status") or []
    assert len(page_status) == 17
    assert sum(int(item.get("rows") or 0) for item in page_status) == 249
    assert all(item.get("rows") == 15 for item in page_status[:-1])
    assert page_status[-1].get("rows") == 9
    print("validated Build 020 Council archive release: 249 rows, 2016-2024, 245 minutes PDFs, four source-labelled no-minutes rows")


if __name__ == "__main__":
    main()
