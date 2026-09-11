#!/usr/bin/env python3
"""Independently validate the conservative audited-financial history artifact.

Build 020 preserves all Build 005/017 rules for standard PDF-parsed sources and adds
one narrowly bounded exception: HRM 2018 primary statements may use the proven
source-specific OCR adapter. OCR is forbidden for all later source years, and corrected
2018 current-year values must preserve raw OCR values plus independent 2019 comparative
validation provenance.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/generated/financials.json"
STANDARD_DATASET_STATUS = "conservative_audited_statement_extraction"
BUILD020_DATASET_STATUS = "build020_combined_audited_statement_history"
EXPECTED_PARSER_VERSION = "build005-financials-v4"
EXPECTED_OCR_ADAPTER = "build020-financials-2018-ocr-v4"
ALLOWED_FAMILIES = {
    "financial_position",
    "operations",
    "net_financial_assets",
    "cash_flows",
    "schedule",
}
STANDARD_METHODS = {"pdf_table_row", "pdf_text_line"}
HEADING_RE = re.compile(r"^(?:halifax regional municipality\s+)?consolidated (?:statement|schedule)s?\b", re.I)
OBVIOUS_NONFINANCIAL = [
    re.compile(r"^page\s+\d+", re.I),
    re.compile(r"\byear ended march\b", re.I),
    re.compile(r"\btelephone\b", re.I),
    re.compile(r"\bfax\b", re.I),
    re.compile(r"^halifax nova scotia\s+[A-Z]\d[A-Z]", re.I),
    re.compile(r"^notes? to consolidated financial statements$", re.I),
    re.compile(r"\(note\s*$", re.I),
]

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def as_number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def close_enough(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=0.011)


def validate_2018_correction(index: int, row: dict, current: float | None, current_raw: float | None, multiplier: float | None, provenance: dict) -> None:
    correction = row.get("ocr_correction")
    if not correction:
        if multiplier is not None and current_raw is not None and current is not None:
            expected = round(current_raw * multiplier, 2)
            if not close_enough(current, expected):
                fail(f"row {index}: uncorrected 2018 current_year {current} != OCR source value * multiplier {expected}")
        return

    if correction.get("status") != "validated_against_next_year_audited_comparative":
        fail(f"row {index}: invalid 2018 OCR correction status")
    if correction.get("validation_source_id") != "hrm-financials-2019":
        fail(f"row {index}: 2018 OCR correction lacks 2019 validation source")
    raw_ocr = as_number(row.get("ocr_current_year"))
    raw_presented = as_number(row.get("ocr_source_presented_current_year"))
    validated = as_number(correction.get("validated_current_year"))
    correction_raw = as_number(correction.get("raw_ocr_current_year"))
    if None in {raw_ocr, raw_presented, validated, correction_raw, multiplier, current}:
        fail(f"row {index}: incomplete numeric 2018 OCR correction evidence")
        return
    if not close_enough(raw_ocr, raw_presented * multiplier):
        fail(f"row {index}: preserved raw 2018 OCR value does not reconcile to source-presented OCR value")
    if not close_enough(raw_ocr, correction_raw):
        fail(f"row {index}: correction raw OCR value does not match preserved raw value")
    if not close_enough(current, validated):
        fail(f"row {index}: corrected current_year does not match validated comparator value")
    if close_enough(current, raw_ocr):
        fail(f"row {index}: correction block present but normalized value equals raw OCR value")
    if provenance.get("validation_source_id") != "hrm-financials-2019" or provenance.get("ocr_correction_applied") is not True:
        fail(f"row {index}: corrected 2018 row lacks correction provenance")


def main() -> None:
    if not PATH.exists():
        raise SystemExit(f"Financial history artifact is missing: {PATH.relative_to(ROOT)}")

    try:
        payload = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Could not parse {PATH.relative_to(ROOT)}: {type(exc).__name__}: {exc}") from exc

    metadata = payload.get("metadata") or {}
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise SystemExit("financials.json records must be a list")

    dataset_status = metadata.get("dataset_status")
    is_build020 = dataset_status == BUILD020_DATASET_STATUS
    if dataset_status not in {STANDARD_DATASET_STATUS, BUILD020_DATASET_STATUS}:
        fail(f"unsupported dataset_status {dataset_status!r}")
    if metadata.get("parser_version") != EXPECTED_PARSER_VERSION:
        fail(f"parser_version {metadata.get('parser_version')!r} != {EXPECTED_PARSER_VERSION!r}")
    if metadata.get("records") != len(rows):
        fail(f"metadata records {metadata.get('records')!r} != actual {len(rows)}")
    scope = str(metadata.get("scope") or "").lower()
    if "heading-anchored" not in scope:
        fail("metadata scope must explicitly retain heading-anchored standard extraction")
    if is_build020:
        if metadata.get("ocr_adapter_version") != EXPECTED_OCR_ADAPTER:
            fail(f"Build 020 ocr_adapter_version {metadata.get('ocr_adapter_version')!r} is stale")
        if metadata.get("source_years") != list(range(2018, 2026)):
            fail(f"Build 020 source_years {metadata.get('source_years')!r} != 2018-2025")
        if metadata.get("2018_schedule_coverage") != "not_released":
            fail("Build 020 must keep 2018 schedule coverage explicitly unreleased")
        if metadata.get("release_status") != "released_checked_in":
            fail(f"Build 020 release_status {metadata.get('release_status')!r} != 'released_checked_in'")

    statuses = metadata.get("source_status")
    if not isinstance(statuses, list) or not statuses:
        fail("source_status must be a non-empty list")
        statuses = []
    if metadata.get("source_count") != len(statuses):
        fail(f"source_count {metadata.get('source_count')!r} != source_status count {len(statuses)}")

    status_ids = []
    for item in statuses:
        source_id = item.get("source_id")
        if not source_id:
            fail(f"source_status entry missing source_id: {item!r}")
            continue
        status_ids.append(source_id)
        expected_status = "ok_ocr_primary_statements" if source_id == "hrm-financials-2018" and is_build020 else "ok"
        if item.get("status") != expected_status:
            fail(f"source {source_id}: status is {item.get('status')!r}, expected {expected_status!r}")
        if not isinstance(item.get("records"), int) or item.get("records", 0) < 10:
            fail(f"source {source_id}: fewer than 10 validated rows")
        if not isinstance(item.get("eligible_statement_pages"), int) or item.get("eligible_statement_pages", 0) < 1:
            fail(f"source {source_id}: no eligible audited statement pages recorded")
        if source_id == "hrm-financials-2018" and is_build020:
            if item.get("records") != 79 or item.get("eligible_statement_pages") != 4:
                fail(f"source {source_id}: unexpected proven OCR row/page counts")
            if item.get("validated_ocr_corrections") != 8:
                fail(f"source {source_id}: expected exactly 8 validated OCR corrections")
            if item.get("schedule_coverage") != "not_released":
                fail(f"source {source_id}: schedules must remain unreleased")
    if len(status_ids) != len(set(status_ids)):
        fail("source_status contains duplicate source IDs")

    source_counts: Counter[str] = Counter()
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    seen_facts: set[tuple] = set()
    corrected_2018 = 0

    for index, row in enumerate(rows):
        source_id = str(row.get("source_id") or "")
        if not source_id.startswith("hrm-financials-"):
            fail(f"row {index}: invalid source_id {source_id!r}")
        if status_ids and source_id not in status_ids:
            fail(f"row {index}: source_id {source_id!r} absent from source_status")
        source_counts[source_id] += 1

        fiscal_year = row.get("fiscal_year_end")
        if not isinstance(fiscal_year, int) or not (1996 <= fiscal_year <= 2100):
            fail(f"row {index}: invalid fiscal_year_end {fiscal_year!r}")

        page = row.get("source_page")
        if not isinstance(page, int) or page < 1:
            fail(f"row {index}: invalid source_page {page!r}")

        family = row.get("statement_family")
        if family not in ALLOWED_FAMILIES:
            fail(f"row {index}: unsupported statement_family {family!r}")
        else:
            family_counts[source_id][family] += 1

        statement = str(row.get("statement") or "").strip()
        if not statement or not HEADING_RE.search(statement):
            fail(f"row {index}: statement is not a heading-anchored consolidated title: {statement!r}")

        label = str(row.get("line_item") or "").strip()
        if not label:
            fail(f"row {index}: missing line_item")
        elif any(pattern.search(label) for pattern in OBVIOUS_NONFINANCIAL):
            fail(f"row {index}: obvious non-financial/truncated label survived extraction: {label!r}")

        multiplier = as_number(row.get("source_unit_multiplier"))
        if multiplier not in {1, 1000}:
            fail(f"row {index}: unsupported source_unit_multiplier {row.get('source_unit_multiplier')!r}")
            multiplier = None

        current_raw = as_number(row.get("source_presented_current_year"))
        prior_raw = as_number(row.get("source_presented_prior_year"))
        current = as_number(row.get("current_year"))
        prior = as_number(row.get("prior_year"))
        for field, value in (
            ("source_presented_current_year", current_raw),
            ("source_presented_prior_year", prior_raw),
            ("current_year", current),
            ("prior_year", prior),
        ):
            if value is None or not math.isfinite(value):
                fail(f"row {index}: {field} is not a finite numeric value")

        provenance = row.get("provenance") or {}
        method = row.get("extraction_method")
        if source_id == "hrm-financials-2018" and is_build020:
            if fiscal_year != 2018:
                fail(f"row {index}: 2018 OCR source has fiscal_year_end {fiscal_year!r}")
            if method != "ocr_text_line":
                fail(f"row {index}: 2018 Build 020 row must use ocr_text_line, got {method!r}")
            if row.get("ocr_adapter_version") != EXPECTED_OCR_ADAPTER or provenance.get("ocr_adapter_version") != EXPECTED_OCR_ADAPTER:
                fail(f"row {index}: stale/missing 2018 OCR adapter version")
            if family == "schedule":
                fail(f"row {index}: 2018 schedules are not released")
            validate_2018_correction(index, row, current, current_raw, multiplier, provenance)
            if row.get("ocr_correction"):
                corrected_2018 += 1
        else:
            if method not in STANDARD_METHODS:
                fail(f"row {index}: unsupported standard extraction_method {method!r}")
            if row.get("ocr_adapter_version") or provenance.get("ocr_adapter_version"):
                fail(f"row {index}: OCR metadata leaked into standard source {source_id}")
            if multiplier is not None and current_raw is not None and current is not None:
                expected = round(current_raw * multiplier, 2)
                if not close_enough(current, expected):
                    fail(f"row {index}: current_year {current} != source value * multiplier {expected}")

        if multiplier is not None and prior_raw is not None and prior is not None:
            expected = round(prior_raw * multiplier, 2)
            if not close_enough(prior, expected):
                fail(f"row {index}: prior_year {prior} != source value * multiplier {expected}")

        if provenance.get("source_id") != source_id:
            fail(f"row {index}: provenance source_id mismatch")
        if provenance.get("parser_version") != EXPECTED_PARSER_VERSION:
            fail(f"row {index}: provenance parser_version {provenance.get('parser_version')!r} is stale")
        if provenance.get("validation_status") != "parsed":
            fail(f"row {index}: provenance validation_status must be 'parsed'")
        if not provenance.get("source_url") or not provenance.get("locator_value"):
            fail(f"row {index}: incomplete provenance")

        fact_key = (
            source_id,
            page,
            family,
            " ".join(label.casefold().split()),
            current,
            prior,
        )
        if fact_key in seen_facts:
            fail(f"row {index}: duplicate normalized comparative fact {fact_key!r}")
        seen_facts.add(fact_key)

    for status in statuses:
        source_id = status.get("source_id")
        if source_id and status.get("records") != source_counts[source_id]:
            fail(
                f"source {source_id}: source_status records {status.get('records')!r} "
                f"!= actual {source_counts[source_id]}"
            )

    for source_id in status_ids:
        for family in ("financial_position", "operations"):
            if family_counts[source_id][family] < 1:
                fail(f"source {source_id}: no rows from required statement family {family!r}")

    if is_build020:
        expected_ids = {f"hrm-financials-{year}" for year in range(2018, 2026)}
        if set(status_ids) != expected_ids:
            fail(f"Build 020 source IDs {sorted(status_ids)!r} != expected 2018-2025 set")
        if corrected_2018 != 8:
            fail(f"Build 020 corrected 2018 row count {corrected_2018} != 8")
        if source_counts["hrm-financials-2018"] != 79:
            fail(f"Build 020 2018 row count {source_counts['hrm-financials-2018']} != 79")
        expected_2018_families = {"financial_position": 16, "operations": 24, "net_financial_assets": 12, "cash_flows": 27}
        if dict(family_counts["hrm-financials-2018"]) != expected_2018_families:
            fail(f"Build 020 2018 family counts {dict(family_counts['hrm-financials-2018'])!r} != {expected_2018_families!r}")

    if errors:
        print("FINANCIAL HISTORY VALIDATION FAILED", file=sys.stderr)
        for message in errors[:100]:
            print(message, file=sys.stderr)
        if len(errors) > 100:
            print(f"... {len(errors) - 100} additional errors", file=sys.stderr)
        raise SystemExit(1)

    print(f"validated {len(rows)} conservative audited-financial rows across {len(status_ids)} sources")
    for source_id in sorted(status_ids):
        families = ", ".join(f"{name}={count}" for name, count in sorted(family_counts[source_id].items()))
        print(f"{source_id}: rows={source_counts[source_id]}; {families}")


if __name__ == "__main__":
    main()
