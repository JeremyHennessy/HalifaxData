#!/usr/bin/env python3
"""Independent structural/semantic validation for capital_current.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data/generated/capital_current.json"
HISTORICAL = ROOT / "data/generated/capital.json"

CODE_RE = re.compile(r"^[A-Za-z0-9-]+$")
ANNUAL_KEYS = {"unspent_previous_budget", "2025_26", "2026_27", "2027_28", "2028_29"}


def fail(message: str) -> None:
    raise SystemExit(f"current-capital validation failed: {message}")


def finite_or_none(value) -> bool:
    return value is None or (isinstance(value, (int, float)) and abs(value) < 50_000_000_000)


def main() -> None:
    if not CURRENT.exists():
        fail("capital_current.json missing")
    payload = json.loads(CURRENT.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    rows = payload.get("records") or []

    if meta.get("dataset_status") != "final_2025_26_capital_plan_project_extraction":
        fail("unexpected dataset status")
    if meta.get("exact_join_only") is not True:
        fail("exact_join_only must be true")
    if len(rows) != meta.get("records"):
        fail("metadata record count mismatch")
    if len(rows) < 175:
        fail(f"only {len(rows)} project rows")
    if meta.get("project_marker_pages", 0) < len(rows):
        fail("project marker page count is smaller than normalized record count")

    codes = set()
    for index, row in enumerate(rows):
        code = str(row.get("project_code") or "").strip()
        if not code or not CODE_RE.fullmatch(code):
            fail(f"row {index} invalid project code {code!r}")
        if code in codes:
            fail(f"duplicate project code {code}")
        codes.add(code)
        if row.get("source_id") != "hrm-capital-2025-26":
            fail(f"row {index} wrong source_id")
        if not isinstance(row.get("source_page"), int) or row["source_page"] < 1:
            fail(f"row {index} missing source page")
        provenance = row.get("provenance") or {}
        if provenance.get("source_id") != "hrm-capital-2025-26" or provenance.get("locator_value") != f"p{row['source_page']}":
            fail(f"row {index} provenance mismatch")

        annual = row.get("annual_budget")
        if annual is not None:
            if set(annual) != ANNUAL_KEYS:
                fail(f"row {index} annual budget keys invalid")
            if not all(finite_or_none(value) for value in annual.values()):
                fail(f"row {index} implausible annual budget")
        for field in [
            "previously_approved_budget", "four_year_budget", "estimated_remaining_budget_required",
            "total_estimated_project_cost", "work_in_process_subtotal", "new_activities_subtotal", "total_work_2025_26",
        ]:
            if not finite_or_none(row.get(field)):
                fail(f"row {index} implausible {field}")

    historical_codes = {}
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    for row in historical.get("records", []):
        code = str(row.get("project_code") or "").strip()
        if code:
            historical_codes.setdefault(code, []).append(str(row.get("project_id") or "").strip())

    exact_match_count = 0
    for row in rows:
        expected_ids = historical_codes.get(row["project_code"], [])
        if bool(expected_ids) != bool(row.get("historical_exact_match")):
            fail(f"historical exact-match flag wrong for {row['project_code']}")
        if sorted(expected_ids) != sorted(row.get("historical_project_object_ids") or []):
            fail(f"historical object IDs wrong for {row['project_code']}")
        exact_match_count += int(bool(expected_ids))

    if exact_match_count != meta.get("historical_exact_project_code_matches"):
        fail("historical exact-match metadata count mismatch")
    if meta.get("annual_budget_rows", 0) < 150:
        fail("too few project rows contain annual budget structure")
    if meta.get("summary_budget_rows", 0) < 150:
        fail("too few project rows contain project-summary budget structure")

    print(
        f"Current capital validated: {len(rows)} projects, annual={meta.get('annual_budget_rows')}, "
        f"summary={meta.get('summary_budget_rows')}, historical_exact={exact_match_count}"
    )


if __name__ == "__main__":
    main()
