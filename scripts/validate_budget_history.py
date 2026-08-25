#!/usr/bin/env python3
"""Independently validate conservative historical-budget extraction."""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/generated/budget_history.json"
REGISTRY = ROOT / "data/sources.json"
EXPECTED_STATUS = "conservative_historical_budget_table_extraction"
EXPECTED_PARSER = "build005-budget-history-v2"
MAX_ABS_VALUE = 10_000_000_000
MONEY_RE = re.compile(
    r"^\s*(?:"
    r"\(\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*\)"
    r"|-?\s*\$?\s*\d[\d,]*(?:\.\d+)?"
    r")\s*$"
)
BLANKS = {"", "-", "—", "–"}
YEAR_RE = re.compile(r"^20\d{2}/\d{2}$")
VALUE_FIELDS = ("prior_actual", "prior_budget", "projection", "current_budget")
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_source_cell(value):
    text = clean(value)
    if text in BLANKS:
        return None, True
    if not MONEY_RE.fullmatch(text):
        return None, False
    compact = text.replace("$", "").replace(",", "").replace(" ", "")
    negative = compact.startswith("(") and compact.endswith(")")
    if negative:
        compact = compact[1:-1]
    try:
        number = float(compact)
    except ValueError:
        return None, False
    return round(-number if negative else number, 2), True


def fact_key(row: dict) -> tuple:
    return (
        row.get("source_id"),
        row.get("source_page"),
        clean(row.get("business_unit")).casefold(),
        clean(row.get("service_area")).casefold(),
        *(row.get(field) for field in VALUE_FIELDS),
    )


def main() -> None:
    if not PATH.exists():
        raise SystemExit(f"Historical budget artifact is missing: {PATH.relative_to(ROOT)}")

    payload = json.loads(PATH.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise SystemExit("budget_history.json records must be a list")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    expected_sources = {
        item["id"]: item
        for item in registry.get("sources", [])
        if str(item.get("id", "")).startswith("hrm-budget-")
        and str(item.get("status", "")).startswith("ready")
    }

    if metadata.get("dataset_status") != EXPECTED_STATUS:
        fail(f"dataset_status {metadata.get('dataset_status')!r} != {EXPECTED_STATUS!r}")
    if metadata.get("parser_version") != EXPECTED_PARSER:
        fail(f"parser_version {metadata.get('parser_version')!r} != {EXPECTED_PARSER!r}")
    if metadata.get("records") != len(rows):
        fail(f"metadata records {metadata.get('records')!r} != actual {len(rows)}")
    if metadata.get("source_count") != len(expected_sources):
        fail(f"source_count {metadata.get('source_count')!r} != configured ready budget sources {len(expected_sources)}")
    for field in ("rejected_invalid_numeric_rows", "duplicates_removed"):
        value = metadata.get(field)
        if not isinstance(value, int) or value < 0:
            fail(f"metadata {field} must be a non-negative integer, got {value!r}")

    statuses = metadata.get("source_status")
    if not isinstance(statuses, list):
        fail("source_status must be a list")
        statuses = []
    status_ids = [item.get("source_id") for item in statuses if item.get("source_id")]
    if set(status_ids) != set(expected_sources):
        fail("source_status IDs do not exactly match configured ready historical-budget sources")
    if len(status_ids) != len(set(status_ids)):
        fail("source_status contains duplicate source IDs")
    for item in statuses:
        source_id = item.get("source_id")
        if item.get("status") != "ok":
            fail(f"source {source_id}: status {item.get('status')!r} is not ok")
        if not isinstance(item.get("records"), int) or item.get("records", 0) < 1:
            fail(f"source {source_id}: no validated rows")
        for field in ("rejected_invalid_numeric_rows", "duplicates_removed"):
            value = item.get(field)
            if not isinstance(value, int) or value < 0:
                fail(f"source {source_id}: {field} must be a non-negative integer")

    counts: Counter[str] = Counter()
    seen = set()
    for index, row in enumerate(rows):
        source_id = row.get("source_id")
        source = expected_sources.get(source_id)
        if not source:
            fail(f"row {index}: unknown/non-ready budget source {source_id!r}")
            continue
        counts[source_id] += 1

        fiscal_year = row.get("fiscal_year")
        if not isinstance(fiscal_year, str) or not YEAR_RE.fullmatch(fiscal_year):
            fail(f"row {index}: invalid fiscal_year {fiscal_year!r}")
        if not clean(row.get("service_area")):
            fail(f"row {index}: blank service_area")
        if row.get("row_kind") not in {"detail", "total"}:
            fail(f"row {index}: invalid row_kind {row.get('row_kind')!r}")
        if row.get("source_status") != source.get("status"):
            fail(f"row {index}: source_status does not match registry")
        if row.get("source_is_final") is not (source.get("status") == "ready"):
            fail(f"row {index}: source_is_final does not match registry status {source.get('status')!r}")

        page = row.get("source_page")
        table = row.get("source_table")
        source_row = row.get("source_row")
        if not isinstance(page, int) or page < 1:
            fail(f"row {index}: invalid source_page {page!r}")
        if not isinstance(table, int) or table < 1:
            fail(f"row {index}: invalid source_table {table!r}")
        if not isinstance(source_row, int) or source_row < 0:
            fail(f"row {index}: invalid source_row {source_row!r}")

        cells = row.get("source_value_cells")
        if not isinstance(cells, dict) or set(cells) != set(VALUE_FIELDS):
            fail(f"row {index}: source_value_cells must contain exactly {VALUE_FIELDS!r}")
            cells = {}

        any_value = False
        for field in VALUE_FIELDS:
            value = row.get(field)
            if value is not None:
                any_value = True
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                    fail(f"row {index}: {field} is not finite numeric/null")
                elif abs(value) > MAX_ABS_VALUE:
                    fail(f"row {index}: {field} magnitude {value} exceeds conservative plausibility ceiling")
            if field in cells:
                parsed, valid = parse_source_cell(cells[field])
                if not valid:
                    fail(f"row {index}: {field} source cell is not exactly one monetary value/blank: {cells[field]!r}")
                elif parsed != value:
                    fail(f"row {index}: {field} parsed value {value!r} != independently parsed source cell {parsed!r}")
        if not any_value:
            fail(f"row {index}: no monetary values")

        key = fact_key(row)
        if key in seen:
            fail(f"row {index}: duplicate same-page semantic budget fact {key!r}")
        seen.add(key)

        provenance = row.get("provenance") or {}
        if provenance.get("source_id") != source_id:
            fail(f"row {index}: provenance source_id mismatch")
        if provenance.get("parser_version") != EXPECTED_PARSER:
            fail(f"row {index}: stale provenance parser_version {provenance.get('parser_version')!r}")
        if provenance.get("validation_status") != "parsed":
            fail(f"row {index}: provenance validation_status must be parsed")
        locator = str(provenance.get("locator_value") or "")
        if f"p{page}/t{table}/r{source_row}" != locator:
            fail(f"row {index}: provenance locator {locator!r} does not match row coordinates")
        if not provenance.get("source_url"):
            fail(f"row {index}: provenance missing source_url")

    status_by_id = {item.get("source_id"): item for item in statuses}
    for source_id in expected_sources:
        status = status_by_id.get(source_id) or {}
        if status.get("records") != counts[source_id]:
            fail(f"source {source_id}: status count {status.get('records')!r} != actual {counts[source_id]}")

    if errors:
        print("BUDGET HISTORY VALIDATION FAILED", file=sys.stderr)
        for message in errors[:100]:
            print(message, file=sys.stderr)
        if len(errors) > 100:
            print(f"... {len(errors) - 100} additional errors", file=sys.stderr)
        raise SystemExit(1)

    print(
        f"validated {len(rows)} conservative historical-budget rows across {len(expected_sources)} sources; "
        f"rejected_invalid_numeric_rows={metadata.get('rejected_invalid_numeric_rows')}; "
        f"duplicates_removed={metadata.get('duplicates_removed')}"
    )
    for source_id in sorted(expected_sources):
        status = status_by_id[source_id]
        print(
            f"{source_id}: rows={counts[source_id]}; "
            f"rejected={status.get('rejected_invalid_numeric_rows')}; duplicates_removed={status.get('duplicates_removed')}"
        )


if __name__ == "__main__":
    main()
