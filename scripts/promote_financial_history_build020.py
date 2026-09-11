#!/usr/bin/env python3
"""Promote a validated Build 020 combined audited-history candidate to release form.

This script performs no collection and no parsing. It only changes release metadata on
an already validated combined candidate and writes the two checked-in generated files.
The one-shot branch release workflow validates both candidate and released outputs before
committing them.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "artifacts/build020-financials-combined.json"
DEFAULT_CANDIDATE_TABLES = ROOT / "artifacts/build020-financials-document-tables-combined.json"
DEFAULT_OUT = ROOT / "data/generated/financials.json"
DEFAULT_TABLE_OUT = ROOT / "data/generated/financials_document_tables.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--candidate-tables", type=Path, default=DEFAULT_CANDIDATE_TABLES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUT)
    args = parser.parse_args()

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    candidate_tables = json.loads(args.candidate_tables.read_text(encoding="utf-8"))
    meta = candidate.get("metadata") or {}
    table_meta = candidate_tables.get("metadata") or {}

    if meta.get("dataset_status") != "build020_combined_audited_statement_history_candidate":
        raise RuntimeError(f"Unexpected candidate dataset_status: {meta.get('dataset_status')!r}")
    if meta.get("release_status") != "candidate_not_production":
        raise RuntimeError(f"Unexpected candidate release_status: {meta.get('release_status')!r}")
    if meta.get("source_years") != list(range(2018, 2026)) or meta.get("source_count") != 8:
        raise RuntimeError("Candidate source-year controls are not the proven 2018-2025 shape")
    if meta.get("2018_schedule_coverage") != "not_released_from_ocr_candidate":
        raise RuntimeError("Candidate no longer preserves the 2018 schedule gap")
    if table_meta.get("release_status") != "candidate_not_production":
        raise RuntimeError("Table-index candidate release boundary changed")
    if table_meta.get("source_count") != 8 or table_meta.get("table_source_count") != 7 or table_meta.get("ocr_source_count") != 1:
        raise RuntimeError("Candidate table-index source controls changed")

    released = copy.deepcopy(candidate)
    released_meta = released["metadata"]
    released_meta["dataset_status"] = "build020_combined_audited_statement_history"
    released_meta["release_status"] = "released_checked_in"
    released_meta["2018_schedule_coverage"] = "not_released"
    released_meta["scope"] = (
        "2018 four primary audited statements via source-specific OCR adapter plus unchanged standard "
        "heading-anchored 2019-2025 audited statement/schedule extraction."
    )
    released_meta["note"] = (
        "The standard parser remains unchanged for 2019-2025. The 2018 OCR layer preserves raw OCR "
        "values; eight current-year OCR digit corrections identify the text-native 2019 audited "
        "comparative source used for validation. 2018 image-backed schedules remain explicitly unreleased."
    )

    released_tables = copy.deepcopy(candidate_tables)
    released_tables["metadata"]["release_status"] = "released_checked_in"
    released_tables["metadata"]["2018_table_index_status"] = "not_applicable_primary_statements_extracted_from_ocr_text_lines"

    args.output.write_text(json.dumps(released, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.table_output.write_text(json.dumps(released_tables, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"promoted Build 020 audited history release: {len(released.get('records') or [])} rows, "
        f"{released_meta['source_count']} source years; 2018 schedules remain unreleased"
    )


if __name__ == "__main__":
    main()
