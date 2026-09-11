#!/usr/bin/env python3
"""Validate Build 017 standard audited-financial source expansion controls.

Build 020 may add a separately proven 2018 OCR layer to the released production
artifact. This validator continues to prove that the Build 017 standard 2019-2025
layer and its original source registry remain unchanged; when a Build 020 production
artifact is present, the extra 2018 rows/status are allowed but are not treated as part
of the Build 017 standard-parser source set.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FINANCIALS = ROOT / "data/generated/financials.json"
TABLE_INDEX = ROOT / "data/generated/financials_document_tables.json"
BASE_REGISTRY = ROOT / "data/sources.json"
SUPPLEMENTAL = ROOT / "data/audited_financial_sources.json"
BUILD020_OVERLAY = ROOT / "data/audited_financial_sources_build020.json"
EXPECTED_PARSER = "build005-financials-v4"
EXPECTED_OCR = "build020-financials-2018-ocr-v4"
OFFICIAL_HOSTS = {"www.halifax.ca", "cdn.halifax.ca"}


def source_year(source_id: str) -> int:
    return int(source_id.rsplit("-", 1)[1])


def main() -> None:
    financials = json.loads(FINANCIALS.read_text(encoding="utf-8"))
    table_index = json.loads(TABLE_INDEX.read_text(encoding="utf-8"))
    base = json.loads(BASE_REGISTRY.read_text(encoding="utf-8"))
    supplemental = json.loads(SUPPLEMENTAL.read_text(encoding="utf-8"))
    overlay = json.loads(BUILD020_OVERLAY.read_text(encoding="utf-8")) if BUILD020_OVERLAY.exists() else None

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

    # Historical Build 017 registry is deliberately preserved. Build 020 closes the
    # primary-statement gap through a separate overlay instead of pretending the old
    # text-layer parser succeeded on the image-backed 2018 source.
    gap = source_map["hrm-financials-2018"]
    assert gap.get("status") == "research-parse-gap", gap
    assert "zero eligible statement pages" in str(gap.get("ingestion") or "").lower(), gap
    assert (urlparse(gap.get("url") or "").hostname or "").lower() in OFFICIAL_HOSTS
    if overlay is not None:
        overlay_map = {item.get("id"): item for item in overlay.get("sources") or []}
        released_2018 = overlay_map.get("hrm-financials-2018") or {}
        assert released_2018.get("status") == "ready-ocr-primary-statements-partial-schedules", released_2018
        assert released_2018.get("ocr_adapter_version") == EXPECTED_OCR, released_2018
        assert released_2018.get("released_records") == 79, released_2018

    meta = financials.get("metadata") or {}
    rows = financials.get("records") or []
    statuses = meta.get("source_status") or []
    is_build020 = meta.get("dataset_status") == "build020_combined_audited_statement_history"
    assert meta.get("dataset_status") in {"conservative_audited_statement_extraction", "build020_combined_audited_statement_history"}
    assert meta.get("parser_version") == EXPECTED_PARSER, "Build 017 standard parser semantics must remain unchanged"
    assert len(rows) >= 1100, f"Expanded audited history unexpectedly sparse: {len(rows)} rows"

    status_map = {item.get("source_id"): item for item in statuses}
    if is_build020:
        assert meta.get("source_count") == 8, meta.get("source_count")
        assert len(statuses) == 8, len(statuses)
        assert set(status_map) == set(expected_ids) | {"hrm-financials-2018"}, sorted(status_map)
        s2018 = status_map["hrm-financials-2018"]
        assert s2018.get("status") == "ok_ocr_primary_statements", s2018
        assert s2018.get("records") == 79, s2018
        assert s2018.get("ocr_adapter_version") == EXPECTED_OCR, s2018
    else:
        assert meta.get("source_count") == 7, meta.get("source_count")
        assert len(statuses) == 7, len(statuses)
        assert set(status_map) == set(expected_ids), sorted(status_map)
        assert "hrm-financials-2018" not in status_map, "2018 must not appear before Build 020 release"

    for source_id in expected_ids:
        item = status_map[source_id]
        assert item.get("status") == "ok", item
        assert int(item.get("records") or 0) >= 10, item
        assert int(item.get("eligible_statement_pages") or 0) >= 1, item

    standard_rows = [row for row in rows if row.get("source_id") in set(expected_ids)]
    standard_years = sorted({int(row["fiscal_year_end"]) for row in standard_rows})
    assert standard_years == expected_years, standard_years
    assert {row.get("source_id") for row in standard_rows} == set(expected_ids)
    assert len(standard_rows) >= 1100

    assert any(row.get("source_id") == "hrm-financials-2019" and row.get("prior_year") is not None for row in standard_rows)

    for row in standard_rows:
        source_id = row.get("source_id")
        assert int(row.get("fiscal_year_end")) == source_year(source_id), row
        assert row.get("extraction_method") in {"pdf_table_row", "pdf_text_line"}, row
        assert not row.get("ocr_adapter_version"), row
        assert not (row.get("provenance") or {}).get("ocr_adapter_version"), row
        assert (row.get("provenance") or {}).get("parser_version") == EXPECTED_PARSER

    if is_build020:
        rows_2018 = [row for row in rows if row.get("source_id") == "hrm-financials-2018"]
        assert len(rows_2018) == 79, len(rows_2018)
        assert all(row.get("fiscal_year_end") == 2018 for row in rows_2018)
        assert all(row.get("extraction_method") == "ocr_text_line" for row in rows_2018)
        assert all(row.get("ocr_adapter_version") == EXPECTED_OCR for row in rows_2018)
        assert not any(row.get("statement_family") == "schedule" for row in rows_2018)

    table_meta = table_index.get("metadata") or {}
    assert table_meta.get("parser_version") == EXPECTED_PARSER
    assert table_meta.get("source_count") == (8 if is_build020 else 7), table_meta.get("source_count")
    if is_build020:
        assert table_meta.get("table_source_count") == 7, table_meta
        assert table_meta.get("ocr_source_count") == 1, table_meta
        assert table_meta.get("2018_table_index_status") == "not_applicable_primary_statements_extracted_from_ocr_text_lines", table_meta

    suffix = "; Build 020 2018 OCR layer separately present and bounded" if is_build020 else "; 2018 remains outside this standard layer"
    print(
        f"Build 017 standard audited layer validated: {len(standard_rows)} rows, "
        f"7 standard annual sources, {expected_years[0]}-{expected_years[-1]} source-year coverage{suffix}"
    )


if __name__ == "__main__":
    main()
