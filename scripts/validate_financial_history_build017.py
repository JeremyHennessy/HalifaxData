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
    assert expected_years == list(range(2018, 2026)), expected_years
    assert supplemental.get("metadata", {}).get("base_registry_source_ids") == ["hrm-financials-2023", "hrm-financials-2025"]

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

    meta = financials.get("metadata") or {}
    rows = financials.get("records") or []
    statuses = meta.get("source_status") or []
    assert meta.get("dataset_status") == "conservative_audited_statement_extraction"
    assert meta.get("parser_version") == EXPECTED_PARSER, "Build 017 must preserve the established parser semantics"
    assert meta.get("source_count") == 8, meta.get("source_count")
    assert len(statuses) == 8, len(statuses)
    assert len(rows) >= 900, f"Expanded audited history unexpectedly sparse: {len(rows)} rows"

    status_map = {item.get("source_id"): item for item in statuses}
    assert sorted(status_map) == expected_ids, sorted(status_map)
    for source_id in expected_ids:
        item = status_map[source_id]
        assert item.get("status") == "ok", item
        assert int(item.get("records") or 0) >= 10, item
        assert int(item.get("eligible_statement_pages") or 0) >= 1, item

    row_years = sorted({int(row["fiscal_year_end"]) for row in rows})
    assert row_years == expected_years, row_years
    row_source_ids = {row.get("source_id") for row in rows}
    assert row_source_ids == set(expected_ids), sorted(row_source_ids)

    # The source-year series is contiguous, but each row still keeps its own annual
    # current/prior comparator semantics rather than being collapsed into one fact.
    for row in rows:
        source_id = row.get("source_id")
        assert int(row.get("fiscal_year_end")) == source_year(source_id), row
        assert row.get("extraction_method") in {"pdf_table_row", "pdf_text_line"}
        assert (row.get("provenance") or {}).get("parser_version") == EXPECTED_PARSER

    table_meta = table_index.get("metadata") or {}
    assert table_meta.get("parser_version") == EXPECTED_PARSER
    assert table_meta.get("source_count") == 8, table_meta.get("source_count")

    print(
        f"Build 017 audited history validated: {len(rows)} rows, "
        f"8 annual sources, {expected_years[0]}-{expected_years[-1]} source-year coverage"
    )


if __name__ == "__main__":
    main()
