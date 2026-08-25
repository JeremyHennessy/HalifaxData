#!/usr/bin/env python3
"""Independently validate the conservative audited-financial history artifact."""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/generated/financials.json"
EXPECTED_DATASET_STATUS = "conservative_audited_statement_extraction"
EXPECTED_PARSER_VERSION = "build005-financials-v3"
ALLOWED_FAMILIES = {
    "financial_position",
    "operations",
    "net_financial_assets",
    "cash_flows",
    "schedule",
}
ALLOWED_METHODS = {"pdf_table_row", "pdf_text_line"}
OBVIOUS_NONFINANCIAL = [
    re.compile(r"^page\b", re.I),
    re.compile(r"^year ended march\b", re.I),
    re.compile(r"\btelephone\b", re.I),
    re.compile(r"\bfax\b", re.I),
    re.compile(r"^halifax nova scotia\s+[A-Z]\d[A-Z]", re.I),
    re.compile(r"^notes? to consolidated financial statements$", re.I),
]

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def as_number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def close_enough(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=0.011)


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

    if metadata.get("dataset_status") != EXPECTED_DATASET_STATUS:
        fail(f"dataset_status {metadata.get('dataset_status')!r} != {EXPECTED_DATASET_STATUS!r}")
    if metadata.get("parser_version") != EXPECTED_PARSER_VERSION:
        fail(f"parser_version {metadata.get('parser_version')!r} != {EXPECTED_PARSER_VERSION!r}")
    if metadata.get("records") != len(rows):
        fail(f"metadata records {metadata.get('records')!r} != actual {len(rows)}")

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
        if item.get("status") != "ok":
            fail(f"source {source_id}: status is {item.get('status')!r}, expected 'ok'")
        if not isinstance(item.get("records"), int) or item.get("records", 0) < 10:
            fail(f"source {source_id}: fewer than 10 validated rows")
        if not isinstance(item.get("eligible_statement_pages"), int) or item.get("eligible_statement_pages", 0) < 1:
            fail(f"source {source_id}: no eligible audited statement pages recorded")
    if len(status_ids) != len(set(status_ids)):
        fail("source_status contains duplicate source IDs")

    source_counts: Counter[str] = Counter()
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    seen_facts: set[tuple] = set()

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
        if not statement or "consolidated" not in statement.lower():
            fail(f"row {index}: statement heading is not explicit/consolidated: {statement!r}")

        label = str(row.get("line_item") or "").strip()
        if not label:
            fail(f"row {index}: missing line_item")
        elif any(pattern.search(label) for pattern in OBVIOUS_NONFINANCIAL):
            fail(f"row {index}: obvious non-financial label survived extraction: {label!r}")

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

        if multiplier is not None and current_raw is not None and current is not None:
            expected = round(current_raw * multiplier, 2)
            if not close_enough(current, expected):
                fail(f"row {index}: current_year {current} != source value * multiplier {expected}")
        if multiplier is not None and prior_raw is not None and prior is not None:
            expected = round(prior_raw * multiplier, 2)
            if not close_enough(prior, expected):
                fail(f"row {index}: prior_year {prior} != source value * multiplier {expected}")

        method = row.get("extraction_method")
        if method not in ALLOWED_METHODS:
            fail(f"row {index}: unsupported extraction_method {method!r}")

        provenance = row.get("provenance") or {}
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

    # Both core statements should be present for every currently registered
    # audited source. If source layout changes, fail closed and inspect it.
    for source_id in status_ids:
        for family in ("financial_position", "operations"):
            if family_counts[source_id][family] < 1:
                fail(f"source {source_id}: no rows from required statement family {family!r}")

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
