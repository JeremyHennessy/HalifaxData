#!/usr/bin/env python3
"""Validate the Build 020 combined 2018-2025 audited-financial candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "data/generated/financials.json"
DEFAULT_BASE_TABLES = ROOT / "data/generated/financials_document_tables.json"
DEFAULT_COMBINED = ROOT / "artifacts/build020-financials-combined.json"
DEFAULT_COMBINED_TABLES = ROOT / "artifacts/build020-financials-document-tables-combined.json"
EXPECTED_PARSER = "build005-financials-v4"
EXPECTED_OCR = "build020-financials-2018-ocr-v4"
EXPECTED_YEARS = list(range(2018, 2026))
EXPECTED_STANDARD_YEARS = list(range(2019, 2026))


def row_key(row: dict) -> tuple:
    return (
        int(row.get("fiscal_year_end") or 0),
        int(row.get("source_page") or 0),
        str(row.get("statement_family") or ""),
        str(row.get("line_item") or ""),
        float(row.get("current_year") or 0),
        float(row.get("prior_year") or 0),
        str(row.get("source_id") or ""),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--base-tables", type=Path, default=DEFAULT_BASE_TABLES)
    parser.add_argument("--combined", type=Path, default=DEFAULT_COMBINED)
    parser.add_argument("--combined-tables", type=Path, default=DEFAULT_COMBINED_TABLES)
    args = parser.parse_args()

    base = json.loads(args.base.read_text(encoding="utf-8"))
    base_tables = json.loads(args.base_tables.read_text(encoding="utf-8"))
    combined = json.loads(args.combined.read_text(encoding="utf-8"))
    combined_tables = json.loads(args.combined_tables.read_text(encoding="utf-8"))

    base_rows = list(base.get("records") or [])
    rows = list(combined.get("records") or [])
    meta = combined.get("metadata") or {}
    assert meta.get("dataset_status") == "build020_combined_audited_statement_history_candidate", meta
    assert meta.get("parser_version") == EXPECTED_PARSER, meta
    assert meta.get("ocr_adapter_version") == EXPECTED_OCR, meta
    assert meta.get("source_count") == 8, meta
    assert meta.get("standard_parser_source_count") == 7, meta
    assert meta.get("ocr_source_count") == 1, meta
    assert meta.get("source_years") == EXPECTED_YEARS, meta
    assert meta.get("2018_schedule_coverage") == "not_released_from_ocr_candidate", meta
    assert meta.get("release_status") == "candidate_not_production", meta
    assert meta.get("records") == len(rows), (meta.get("records"), len(rows))

    years = sorted({int(row["fiscal_year_end"]) for row in rows})
    assert years == EXPECTED_YEARS, years
    source_ids = {row.get("source_id") for row in rows}
    assert source_ids == {f"hrm-financials-{year}" for year in EXPECTED_YEARS}, sorted(source_ids)

    rows_2018 = [row for row in rows if int(row.get("fiscal_year_end") or 0) == 2018]
    standard_rows = [row for row in rows if int(row.get("fiscal_year_end") or 0) >= 2019]
    assert len(rows_2018) == 79, len(rows_2018)
    assert len(standard_rows) == len(base_rows), (len(standard_rows), len(base_rows))
    assert sorted({int(row["fiscal_year_end"]) for row in standard_rows}) == EXPECTED_STANDARD_YEARS
    assert all(row.get("source_id") == "hrm-financials-2018" for row in rows_2018)
    assert all(row.get("extraction_method") == "ocr_text_line" for row in rows_2018)
    assert all(row.get("ocr_adapter_version") == EXPECTED_OCR for row in rows_2018)
    assert not any(row.get("statement_family") == "schedule" for row in rows_2018), "2018 schedules are not proven"
    corrected = [row for row in rows_2018 if row.get("ocr_correction")]
    assert len(corrected) == 8, len(corrected)
    assert all((row.get("ocr_correction") or {}).get("validation_source_id") == "hrm-financials-2019" for row in corrected)

    # The combined builder must not alter a single standard-parser row. It literally
    # carries forward the freshly reproduced Build 017 output for 2019-2025.
    assert sorted(standard_rows, key=row_key) == sorted(base_rows, key=row_key), "2019-2025 standard rows changed during Build 020 combination"
    assert all(row.get("extraction_method") in {"pdf_table_row", "pdf_text_line"} for row in standard_rows)
    assert not any(row.get("ocr_adapter_version") for row in standard_rows), "OCR metadata leaked into standard source years"

    status = meta.get("source_status") or []
    status_map = {item.get("source_id"): item for item in status}
    assert set(status_map) == {f"hrm-financials-{year}" for year in EXPECTED_YEARS}, sorted(status_map)
    s2018 = status_map["hrm-financials-2018"]
    assert s2018.get("status") == "ok_ocr_primary_statements", s2018
    assert s2018.get("records") == 79, s2018
    assert s2018.get("validated_ocr_corrections") == 8, s2018
    assert s2018.get("schedule_coverage") == "not_released_from_ocr_candidate", s2018
    for year in EXPECTED_STANDARD_YEARS:
        assert status_map[f"hrm-financials-{year}"].get("status") == "ok", status_map[f"hrm-financials-{year}"]

    table_meta = combined_tables.get("metadata") or {}
    table_rows = list(combined_tables.get("records") or [])
    assert table_meta.get("parser_version") == EXPECTED_PARSER, table_meta
    assert table_meta.get("source_count") == 8, table_meta
    assert table_meta.get("table_source_count") == 7, table_meta
    assert table_meta.get("ocr_source_count") == 1, table_meta
    assert table_meta.get("2018_table_index_status") == "not_applicable_primary_statements_extracted_from_ocr_text_lines", table_meta
    assert table_meta.get("release_status") == "candidate_not_production", table_meta
    assert table_rows == list(base_tables.get("records") or []), "Build 020 changed the 2019-2025 table index"

    print(
        f"Build 020 combined audited history validated: {len(rows)} rows, "
        f"8 source years (2018-2025), 79 OCR primary-statement rows for 2018, "
        f"{len(base_rows)} unchanged standard rows for 2019-2025; 2018 schedules remain explicit gap"
    )


if __name__ == "__main__":
    main()
