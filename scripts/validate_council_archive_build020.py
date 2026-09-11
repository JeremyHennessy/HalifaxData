#!/usr/bin/env python3
"""Validate the Build 020 Halifax Regional Council historical archive candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "artifacts/build020-council-archive.json"
SEEDS_PATH = ROOT / "data/council_decision_sources.json"
EXPECTED_CATEGORY = "931"
EXPECTED_RESULT_COUNT = 249
EXPECTED_MAX_DATE = "2024-11-05"
OFFICIAL_HOSTS = {"halifax.ca", "www.halifax.ca", "cdn.halifax.ca"}


def minutes_identity(url: str | None) -> str | None:
    if not url:
        return None
    return urlparse(url).path.lower().rstrip("/")


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
    assert meta.get("max_meeting_date") == EXPECTED_MAX_DATE, meta
    assert str(meta.get("min_meeting_date") or "").startswith("2017-"), meta
    assert meta.get("release_status") == "candidate_not_production", meta
    assert "not Council decision extraction" in str(meta.get("scope") or ""), meta
    assert "pre-2017" in str(meta.get("pre_2017_boundary") or "").lower(), meta

    years = sorted({row["meeting_date"][:4] for row in rows})
    assert years == [str(year) for year in range(2017, 2025)], years
    by_year = meta.get("records_by_year") or {}
    assert sum(int(value) for value in by_year.values()) == len(rows), by_year
    assert sorted(by_year) == years, by_year
    assert meta.get("minutes_pdf_records") + meta.get("missing_minutes_records") == len(rows), meta
    assert meta.get("minutes_pdf_records") >= 240, meta

    ids = set()
    agenda_urls = set()
    date_minutes_pairs = set()
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
        page_index = row.get("source_page_index")
        row_index = row.get("source_row_index")
        assert isinstance(page_index, int) and 0 <= page_index < meta.get("pages_fetched"), (index, page_index)
        assert isinstance(row_index, int) and row_index >= 1, (index, row_index)
        assert f"category={EXPECTED_CATEGORY}" in str(row.get("source_search_url") or ""), (index, row.get("source_search_url"))

    # All six existing post-2016 hand-picked seed minutes must be present in the
    # inventory with the same meeting date and normalized official PDF path. The
    # 2016 seed is intentionally outside the current-site archive boundary.
    legacy = seeds.get("legacy_sources") or []
    post_2016 = [seed for seed in legacy if str(seed.get("meeting_date") or "") >= "2017-01-01"]
    assert len(post_2016) == 6, len(post_2016)
    row_pairs = {(row["meeting_date"], row.get("minutes_identity")) for row in rows if row.get("minutes_identity")}
    missing_seeds = []
    for seed in post_2016:
        expected = (seed["meeting_date"], minutes_identity(seed.get("minutes_url")))
        if expected not in row_pairs:
            missing_seeds.append(expected)
    assert not missing_seeds, f"Known legacy seed minutes missing from official archive inventory: {missing_seeds!r}"

    # Page accounting must reconcile to the exact advertised row count.
    page_status = meta.get("page_status") or []
    assert len(page_status) == meta.get("pages_fetched"), len(page_status)
    assert sum(int(item.get("rows") or 0) for item in page_status) == len(rows), page_status
    for item in page_status[:-1]:
        assert item.get("rows") == meta.get("page_size"), item
    assert 1 <= page_status[-1].get("rows") <= meta.get("page_size"), page_status[-1]

    print(json.dumps({
        "status": "ok",
        "records": len(rows),
        "date_range": [meta["min_meeting_date"], meta["max_meeting_date"]],
        "years": years,
        "records_by_year": by_year,
        "minutes_pdf_records": meta["minutes_pdf_records"],
        "missing_minutes_records": meta["missing_minutes_records"],
        "known_post_2016_seed_matches": len(post_2016),
        "pages_fetched": meta["pages_fetched"],
    }, indent=2))


if __name__ == "__main__":
    main()
