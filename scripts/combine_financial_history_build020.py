#!/usr/bin/env python3
"""Combine proven 2018 OCR primary statements with standard 2019-2025 audited history.

This script does not collect source data. It combines two already-generated candidates:
- the unchanged Build 017 / Build 005 standard-parser output for 2019-2025; and
- the Build 020 source-specific 2018 OCR primary-statement candidate.

The combined output stays in artifacts until a separate release step updates checked-in
production data and the audited-source registry together.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "data/generated/financials.json"
DEFAULT_BASE_TABLES = ROOT / "data/generated/financials_document_tables.json"
DEFAULT_OCR = ROOT / "artifacts/build020-financials-2018-ocr.json"
DEFAULT_OUT = ROOT / "artifacts/build020-financials-combined.json"
DEFAULT_TABLE_OUT = ROOT / "artifacts/build020-financials-document-tables-combined.json"
EXPECTED_STANDARD_PARSER = "build005-financials-v4"
EXPECTED_OCR_ADAPTER = "build020-financials-2018-ocr-v4"
EXPECTED_STANDARD_YEARS = list(range(2019, 2026))
EXPECTED_COMBINED_YEARS = list(range(2018, 2026))


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--base-tables", type=Path, default=DEFAULT_BASE_TABLES)
    parser.add_argument("--ocr", type=Path, default=DEFAULT_OCR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUT)
    args = parser.parse_args()

    base = json.loads(args.base.read_text(encoding="utf-8"))
    tables = json.loads(args.base_tables.read_text(encoding="utf-8"))
    ocr = json.loads(args.ocr.read_text(encoding="utf-8"))

    base_meta = base.get("metadata") or {}
    base_rows = list(base.get("records") or [])
    ocr_meta = ocr.get("metadata") or {}
    ocr_rows = list(ocr.get("records") or [])

    if base_meta.get("parser_version") != EXPECTED_STANDARD_PARSER:
        raise RuntimeError(f"Unexpected standard parser: {base_meta.get('parser_version')!r}")
    standard_years = sorted({int(row["fiscal_year_end"]) for row in base_rows})
    if standard_years != EXPECTED_STANDARD_YEARS:
        raise RuntimeError(f"Standard audited years {standard_years} != {EXPECTED_STANDARD_YEARS}")
    if ocr_meta.get("fiscal_year_end") != 2018 or ocr_meta.get("source_id") != "hrm-financials-2018":
        raise RuntimeError("Unexpected 2018 OCR candidate identity")
    if ocr_meta.get("ocr_adapter_version") != EXPECTED_OCR_ADAPTER:
        raise RuntimeError(f"Unexpected 2018 OCR adapter: {ocr_meta.get('ocr_adapter_version')!r}")
    if ocr_meta.get("release_status") != "candidate_not_production_until_validated_and_integrated":
        raise RuntimeError("2018 OCR candidate release boundary changed unexpectedly")
    if not ocr_rows:
        raise RuntimeError("2018 OCR candidate is empty")
    if any(int(row.get("fiscal_year_end") or 0) != 2018 for row in ocr_rows):
        raise RuntimeError("2018 OCR candidate contains another fiscal year")
    if any(row.get("source_id") != "hrm-financials-2018" for row in ocr_rows):
        raise RuntimeError("2018 OCR candidate contains another source ID")

    combined_rows = [*ocr_rows, *base_rows]
    combined_rows.sort(key=lambda row: (
        int(row.get("fiscal_year_end") or 0),
        int(row.get("source_page") or 0),
        str(row.get("statement_family") or ""),
        str(row.get("line_item") or ""),
    ))
    combined_years = sorted({int(row["fiscal_year_end"]) for row in combined_rows})
    if combined_years != EXPECTED_COMBINED_YEARS:
        raise RuntimeError(f"Combined audited years {combined_years} != {EXPECTED_COMBINED_YEARS}")

    standard_status = list(base_meta.get("source_status") or [])
    source_status = [
        {
            "source_id": "hrm-financials-2018",
            "status": "ok_ocr_primary_statements",
            "records": len(ocr_rows),
            "eligible_statement_pages": 4,
            "base_parser_version": EXPECTED_STANDARD_PARSER,
            "ocr_adapter_version": EXPECTED_OCR_ADAPTER,
            "source_sha256": ocr_meta.get("source_sha256"),
            "validated_ocr_corrections": ocr_meta.get("validated_ocr_corrections"),
            "schedule_coverage": ocr_meta.get("schedule_coverage"),
        },
        *standard_status,
    ]

    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "build020_combined_audited_statement_history_candidate",
            "parser_version": EXPECTED_STANDARD_PARSER,
            "ocr_adapter_version": EXPECTED_OCR_ADAPTER,
            "records": len(combined_rows),
            "source_count": 8,
            "source_years": EXPECTED_COMBINED_YEARS,
            "standard_parser_source_count": 7,
            "ocr_source_count": 1,
            "source_status": source_status,
            "scope": "2018 four primary audited statements via source-specific OCR adapter plus unchanged standard heading-anchored 2019-2025 audited statement/schedule extraction.",
            "2018_schedule_coverage": "not_released_from_ocr_candidate",
            "note": "The standard parser remains unchanged for 2019-2025. 2018 OCR corrections preserve raw OCR values and identify the 2019 audited comparative source used for validation. This combined artifact is not production until checked-in data and source-registry controls are updated together and pass release validation.",
            "release_status": "candidate_not_production",
        },
        "records": combined_rows,
    }

    base_table_rows = list(tables.get("records") or [])
    table_payload = {
        "metadata": {
            **(tables.get("metadata") or {}),
            "generated_at": now(),
            "parser_version": EXPECTED_STANDARD_PARSER,
            "source_count": 8,
            "table_source_count": 7,
            "ocr_source_count": 1,
            "tables": len(base_table_rows),
            "2018_table_index_status": "not_applicable_primary_statements_extracted_from_ocr_text_lines",
            "release_status": "candidate_not_production",
        },
        "records": base_table_rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.table_output.write_text(json.dumps(table_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Build 020 combined audited candidate: {len(combined_rows)} rows, "
        f"years {combined_years[0]}-{combined_years[-1]}, 79-row 2018 OCR layer plus {len(base_rows)} standard rows"
    )


if __name__ == "__main__":
    main()
