#!/usr/bin/env python3
"""Independent validation for 2025/26 capital category actuals/projections."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/generated/capital_actuals_current.json"
EXPECTED = {
    "Q1": {"actual": 60_200_000, "projected": 421_800_000, "wip": 198_700_000},
    "Q2": {"actual": 147_800_000, "projected": 349_100_000, "wip": 219_900_000},
    "Q3": {"actual": 255_400_000, "projected": 109_300_000, "wip": 343_100_000},
}
ROUNDING_TOLERANCE = 100_000
ARITHMETIC_TOLERANCE = 2


def fail(message: str) -> None:
    raise SystemExit(f"current-capital-actuals validation failed: {message}")


def n(value) -> float:
    return float(value or 0)


def main() -> None:
    if not PATH.exists():
        fail("artifact missing")
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    rows = payload.get("records") or []
    if meta.get("dataset_status") != "official_2025_26_capital_projection_summaries":
        fail("unexpected dataset status")
    if meta.get("parser_version") != "build008-capital-actuals-v1":
        fail("unexpected parser version")
    if meta.get("granularity") != "asset_category_summary_not_project_actuals":
        fail("granularity boundary missing")
    if meta.get("project_level_actuals_available") is not False:
        fail("project-level actuals must remain false")
    if len(rows) != meta.get("records") or meta.get("source_count") != 3:
        fail("metadata counts do not match")
    if any("project_code" in row or "vendor_name" in row for row in rows):
        fail("category actuals artifact contains unsupported project/vendor fields")

    quarters = {}
    for index, row in enumerate(rows):
        if row.get("granularity") != "capital_asset_category_summary":
            fail(f"row {index} wrong granularity")
        q = row.get("quarter")
        if q not in EXPECTED:
            fail(f"row {index} unexpected quarter {q!r}")
        quarters.setdefault(q, []).append(row)
        if row.get("fiscal_year") != "2025/26" or not row.get("budget_category"):
            fail(f"row {index} missing fiscal/category identity")
        if not row.get("source_id") or not isinstance(row.get("source_page"), int):
            fail(f"row {index} missing source provenance")
        prov = row.get("provenance") or {}
        if prov.get("source_id") != row.get("source_id"):
            fail(f"row {index} provenance source mismatch")

        available_expected = n(row.get("budget_remaining_at_prior_year_end")) + n(row.get("budget_2025_26")) + n(row.get("budget_increases_decreases"))
        if abs(n(row.get("budget_available_at_period_end")) - available_expected) > ARITHMETIC_TOLERANCE:
            fail(f"row {index} budget-available arithmetic mismatch")
        exp_commit_expected = n(row.get("ytd_expenditures")) + n(row.get("ytd_commitments"))
        if abs(n(row.get("ytd_expenditures_and_commitments")) - exp_commit_expected) > ARITHMETIC_TOLERANCE:
            fail(f"row {index} expenditure/commitment arithmetic mismatch")

    if set(quarters) != set(EXPECTED):
        fail(f"quarter coverage mismatch: {sorted(quarters)}")
    previous_actual = -1.0
    for quarter in ["Q1", "Q2", "Q3"]:
        qrows = quarters[quarter]
        if len(qrows) < 5:
            fail(f"{quarter} has only {len(qrows)} category rows")
        totals = [row for row in qrows if "total" in row["budget_category"].casefold()]
        if len(totals) != 1:
            fail(f"{quarter} must have exactly one total row, found {len(totals)}")
        total = totals[0]
        expected = EXPECTED[quarter]
        actual = n(total.get("ytd_expenditures"))
        projected = n(total.get("projected_spend_remaining_2025_26"))
        wip = n(total.get("projected_work_in_progress_2026_27"))
        for label, observed, target in [("actual", actual, expected["actual"]), ("projected", projected, expected["projected"]), ("wip", wip, expected["wip"])]:
            if abs(observed - target) > ROUNDING_TOLERANCE:
                fail(f"{quarter} {label} {observed} does not reconcile to narrative {target}")
        if actual <= previous_actual:
            fail(f"YTD actual expenditures are not increasing through {quarter}")
        previous_actual = actual

    print(
        "Current capital actuals validated: "
        + ", ".join(f"{q}={len(quarters[q])} rows" for q in ["Q1", "Q2", "Q3"])
    )


if __name__ == "__main__":
    main()
