#!/usr/bin/env python3
"""Validate Build 017 audited-financial source expansion controls."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FINANCIALS = ROOT / "data/generated/financials.json"
TABLE_INDEX = ROOT / "data/generated/financials_document_tables.json"
BASE_REGISTRY = ROOT / "data/sources.json"
SUPPLEMENTAL = ROOT / "data/audited_financial_sources.json"
EXPECTED_PARSER = "build005-financials-v4"
OFFICIAL_HOSTS = {"www.halifax.ca", "cdn.halifax.ca"}


def source_year(source_id: str) -> int:
    return int(source_id.rsplit("-", 1)[1])


def main() -> None:
    financials = json.loads(FINANCIALS.read_text(encoding="utf-8"))
    table_index = json.loads(TABLE_INDEX.read_text(encoding="utf-8"))
    base = json.loads(BASE_REGISTRY.read_text(encoding="utf-8"))
    supplemental = json.loads(SUPPLEMENTAL.read_text(encoding="utf-8"))

    expected_years = supplemental.get("metadata", {}).get("expected_source_years") or []
    assert expected_years == list(range(2019, 2026)), expected_years
    assert supplemental.get("metadata", {}).get("base_registry_source_ids") == ["hrm-financials-2023", "hrm-financials-2025"]
    assert supplemental.get("metadata", {}).get("documented_parse_gap_source_ids") == ["hrm-financials-2018"]

    source_map = {
        source["id"]: source
        for source in [*(base.get("sources") or []), *(supplemental.get("sources") or [])]
        if source.get("id")
    }
    expected_ids = [f"hrm-financials-{year}" for year in expected_years]
    assert all(source_id in source_map for source_id in expected_ids), "Missing configured Build 017 audited source"

    for source_id in expected_ids:
        source = source_map[source_id]
        assert str(source.get("status") or "").startswith("ready"), (source_id, source.get("status"))
        host = (urlparse(source.get("url") or "").hostname or "").lower()
        assert host in OFFICIAL_HOSTS, (source_id, host)
        assert source_year(source_id) in expected_years

    gap = source_map["hrm-financials-2018"]
    assert gap.get("status") == "research-parse-gap", gap
    assert "zero eligible statement pages" in str(gap.get("ingestion") or "").lower(), gap
    assert (urlparse(gap.get("url") or "").hostname or "").lower() in OFFICIAL_HOSTS

    meta = financials.get("metadata") or {}
    rows = financials.get("records") or []
    statuses = meta.get("source_status") or []
    assert meta.get("dataset_status") == "conservative_audited_statement_extraction"
    assert meta.get("parser_version") == EXPECTED_PARSER, "Build 017 must preserve the established parser semantics"
    assert meta.get("source_count") == 7, meta.get("source_count")
    assert len(statuses) == 7, len(statuses)
    assert len(rows) >= 1100, f"Expanded audited history unexpectedly sparse: {len(rows)} rows"

    status_map = {item.get("source_id"): item for item in statuses}
    assert sorted(status_map) == expected_ids, sorted(status_map)
    assert "hrm-financials-2018" not in status_map, "2018 parse-gap source must not be silently released"
    for source_id in expected_ids:
        item = status_map[source_id]
        assert item.get("status") == "ok", item
        assert int(item.get("records") or 0) >= 10, item
        assert int(item.get("eligible_statement_pages") or 0) >= 1, item

    row_years = sorted({int(row["fiscal_year_end"]) for row in rows})
    assert row_years == expected_years, row_years
    row_source_ids = {row.get("source_id") for row in rows}
    assert row_source_ids == set(expected_ids), sorted(row_source_ids)

    # The 2019 source contains source-presented 2018 comparatives. Those remain
    # prior_year values inside the 2019 source; they are not relabelled as 2018 rows.
    assert any(row.get("source_id") == "hrm-financials-2019" and row.get("prior_year") is not None for row in rows)

    for row in rows:
        source_id = row.get("source_id")
        assert int(row.get("fiscal_year_end")) == source_year(source_id), row
        assert row.get("extraction_method") in {"pdf_table_row", "pdf_text_line"}
        assert (row.get("provenance") or {}).get("parser_version") == EXPECTED_PARSER

    table_meta = table_index.get("metadata") or {}
    assert table_meta.get("parser_version") == EXPECTED_PARSER
    assert table_meta.get("source_count") == 7, table_meta.get("source_count")

    print(
        f"Build 017 audited history validated: {len(rows)} rows, "
        f"7 released annual sources, {expected_years[0]}-{expected_years[-1]} source-year coverage; "
        "2018 official source retained as an explicit parser gap"
    )


if __name__ == "__main__":
    main()
