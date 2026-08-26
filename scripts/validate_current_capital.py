#!/usr/bin/env python3
"""Validate Build 010 current-capital evidence without inventing spend-to-date facts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "generated" / "current_capital.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    current = payload.get("current_projects") or []
    prior = payload.get("prior_projects") or []
    comparisons = payload.get("plan_comparisons") or []
    adjustments = payload.get("adjustments") or []
    decision = payload.get("decision") or {}

    assert meta.get("dataset_status") == "current_capital_plan_and_approved_adjustments", meta
    assert meta.get("is_transaction_ledger") is False, meta
    assert meta.get("has_project_spend_to_date") is False, meta
    assert len(current) >= 75, len(current)
    assert len(prior) >= 75, len(prior)
    assert len(comparisons) >= 50, len(comparisons)
    assert len(adjustments) >= 14, len(adjustments)
    assert meta.get("current_projects") == len(current)
    assert meta.get("prior_projects") == len(prior)
    assert meta.get("exact_code_plan_comparisons") == len(comparisons)
    assert meta.get("approved_adjustments") == len(adjustments)

    for rows, plan_year, source_id in [
        (current, "2025/26", "hrm-capital-2025-26"),
        (prior, "2024/25", "hrm-capital-2024-25"),
    ]:
        codes = [row.get("project_code") for row in rows]
        assert all(codes), f"{plan_year}: missing project code"
        assert len(codes) == len(set(codes)), f"{plan_year}: duplicate project code"
        assert all(row.get("plan_year") == plan_year for row in rows)
        assert all(row.get("source_id") == source_id for row in rows)
        assert all(row.get("project_name") for row in rows)
        assert all("actual_spend" not in row and "spend_to_date" not in row for row in rows)

    current_by_code = {row["project_code"]: row for row in current}
    prior_by_code = {row["project_code"]: row for row in prior}
    comparison_by_code = {row["project_code"]: row for row in comparisons}

    assert "CT000007" in current_by_code, "Cogswell missing from 2025/26 current plan"
    assert "CT000007" in prior_by_code, "Cogswell missing from 2024/25 prior plan"
    assert "CT000007" in comparison_by_code, "Cogswell missing from exact-code comparison"
    cogswell = current_by_code["CT000007"]
    assert cogswell.get("total_estimated_project_cost") == 138_160_500, cogswell
    cogswell_prior = prior_by_code["CT000007"]
    assert cogswell_prior.get("total_estimated_project_cost") is not None, cogswell_prior
    assert comparison_by_code["CT000007"].get("comparison_method") == "exact_project_code"

    assert decision.get("decision_status") == "approved", decision
    assert decision.get("decision_date") == "2025-05-27", decision
    assert decision.get("meeting_id") == "d170b0da-a5f9-4e87-80c4-f58ea1f9b47f", decision
    assert decision.get("motion_result") == "MOTION PUT AND PASSED UNANIMOUSLY", decision

    by_type = {}
    for row in adjustments:
        by_type.setdefault(row.get("adjustment_type"), []).append(row)
        assert row.get("source_id") == "hrm-capital-adjustments-2025-26"
        assert (row.get("decision") or {}).get("decision_status") == "approved"
        before = row.get("approved_budget_before")
        change = row.get("adjustment_amount")
        after = row.get("approved_budget_after")
        assert None not in (before, change, after), row
        assert round(before + change - after, 2) == 0, row
        assert "actual_spend" not in row and "spend_to_date" not in row

    external = by_type.get("external_cost_sharing_award") or []
    transfers = by_type.get("capital_budget_transfer") or []
    increases = by_type.get("capital_budget_increase") or []
    assert len(external) == 4, len(external)
    assert len(transfers) == 8, len(transfers)
    assert len(increases) == 2, len(increases)
    assert round(sum(row["adjustment_amount"] for row in transfers), 2) == 0, transfers
    assert round(sum(row["adjustment_amount"] for row in increases), 2) == 9_500_000, increases
    assert round(sum(row["adjustment_amount"] for row in external), 2) == 1_785_000, external

    adjustment_by_code = {row["project_code"]: row for row in adjustments}
    assert adjustment_by_code["CP210013"]["adjustment_amount"] == 1_000_000
    assert adjustment_by_code["CB210018"]["adjustment_amount"] == 4_500_000
    assert adjustment_by_code["CB000080"]["adjustment_amount"] == 5_000_000
    assert adjustment_by_code["CT200003"]["adjustment_amount"] == 1_900_000

    blob = json.dumps(payload).lower()
    forbidden = ["invoice amount", "transaction ledger row", "actual project spend", "spend-to-date"]
    assert not any(token in blob for token in forbidden), "unsupported transaction/spend semantics present"

    print(
        f"validated current capital: {len(current)} current projects, {len(prior)} prior projects, "
        f"{len(comparisons)} exact-code comparisons, {len(adjustments)} approved adjustments"
    )


if __name__ == "__main__":
    main()
