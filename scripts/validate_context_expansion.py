#!/usr/bin/env python3
"""Validate Build 013 contextual funding and contract-amendment evidence."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

DEFAULT = Path("data/generated/context_expansion.json")
CURRENT_GRANTS = Path("data/generated/community_grants_2026.json")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def close(actual: float, expected: float, tolerance: float = 0.02) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance)


def main(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data["metadata"]
    require(meta["is_complete_grants_ledger"] is False, "Build 013 must not claim a complete grants ledger")
    require(meta["is_complete_contract_amendment_ledger"] is False, "Build 013 must not claim a complete amendment ledger")
    require(meta["is_transaction_ledger"] is False, "Build 013 must not claim transaction/AP coverage")
    require(meta["creates_wrongdoing_assertions"] is False, "Build 013 funding context cannot assert wrongdoing")

    grants = data["community_grants_2025"]
    categories = grants["categories"]
    require(len(categories) == 7, "Expected seven Community Grants categories")
    require(sum(row["applications"] for row in categories) == 120, "Community Grants applications do not reconcile")
    require(close(sum(row["requested"] for row in categories), 1224009.14), "Community Grants requested value does not reconcile")
    require(sum(row["recommended_awards"] for row in categories) == 63, "Community Grants category award count does not reconcile")
    require(close(sum(row["recommended_amount"] for row in categories), 480430), "Community Grants category recommendation does not reconcile")
    require(grants["applications_eligible"] + grants["applications_ineligible"] == grants["applications_received"], "Community Grants eligibility counts do not reconcile")
    require(grants["staff_recommended_awards"] == grants["council_approved_awards"] == 63, "Community Grants award count control changed")
    require(close(grants["staff_recommended_total"], 480430), "Unexpected staff recommended total")
    require(close(grants["council_approved_total"], 476430), "Unexpected Council-approved total")
    require(close(grants["council_approved_total"] - grants["staff_recommended_total"], grants["council_adjustment"]), "Council adjustment does not reconcile")

    current = json.loads(CURRENT_GRANTS.read_text(encoding="utf-8"))
    current_meta = current["metadata"]
    require(current_meta["source_stage"] == "staff_recommendation_before_council_approval", "2026 Community Grants stage boundary changed")
    require(current_meta["is_final_council_award"] is False, "2026 Community Grants must not be represented as final")
    require(current_meta["is_payment_data"] is False, "2026 Community Grants must not be represented as payment data")
    require(current_meta["creates_wrongdoing_assertions"] is False, "2026 Community Grants cannot assert wrongdoing")
    current_categories = current["categories"]
    require(len(current_categories) == 7, "Expected seven 2026 Community Grants categories")
    require(sum(row["applications"] for row in current_categories) == current["applications_received"] == 145, "2026 Community Grants application count does not reconcile")
    require(sum(row["proposed_awards"] for row in current_categories) == current["proposed_awards"] == 53, "2026 Community Grants proposed award count does not reconcile")
    require(close(sum(row["proposed_award_value"] for row in current_categories), current["proposed_award_total"]), "2026 Community Grants proposed award value does not reconcile")
    require(close(current["program_budget"] - current["proposed_award_total"], current["balance_after_proposed_awards"]), "2026 Community Grants post-award balance does not reconcile")
    require(close(current["balance_after_proposed_awards"] - current["proposed_transfer_to_M310_8004"], current["balance_after_proposed_transfer"]), "2026 Community Grants transfer/balance does not reconcile")

    museums = data["community_museums_2025"]
    require(len(museums["operating_grants"]) == museums["operating_grant_count"] == 14, "Museum operating grant count mismatch")
    require(len(museums["project_grants"]) == museums["project_grant_count"] == 8, "Museum project grant count mismatch")
    require(close(sum(row["amount"] for row in museums["operating_grants"]), museums["operating_grant_total"]), "Museum operating grants do not reconcile")
    require(close(sum(row["amount"] for row in museums["project_grants"]), museums["project_grant_total"]), "Museum project grants do not reconcile")
    require(close(museums["operating_grant_total"] + museums["project_grant_total"] + museums["balance"], museums["program_budget"]), "Museum program budget does not reconcile")

    transit = data["rural_transit_2025_26"]
    require(len(transit["providers"]) == 4, "Expected four rural-transit providers")
    require(close(sum(row["prior_disbursement"] for row in transit["providers"]), transit["prior_total"]), "Prior rural-transit total does not reconcile")
    require(close(sum(row["projected_grant"] for row in transit["providers"]), transit["projected_total"]), "Projected rural-transit total does not reconcile")

    amendments = data["contract_amendments_2023_11"]
    observations = amendments["observations"]
    require(amendments["public_attachment_table_rows"] == 7, "Expected seven source table rows in Nov. 2023 report")
    require(amendments["financial_observations"] == len(observations) == 8, "Expected eight financial observations after the two-PO source row is split")
    require(amendments["private_confidential_excluded"] is True, "Private/confidential exclusion boundary missing")
    ids = [row["id"] for row in observations]
    require(len(ids) == len(set(ids)), "Duplicate contract-amendment observation IDs")
    mismatches = []
    for row in observations:
        derived = round(float(row["original_value"]) + float(row["published_amendment_value"]), 2)
        delta = round(float(row["updated_value"]) - derived, 2)
        require(close(row["derived_updated_value"], derived), f"Derived updated value mismatch for {row['id']}")
        require(close(row["source_arithmetic_delta"], delta), f"Source arithmetic delta mismatch for {row['id']}")
        if abs(delta) > 0.02:
            mismatches.append((row["id"], delta))
            require(row["source_arithmetic_consistent"] is False, f"Arithmetic mismatch must be flagged for {row['id']}")
        else:
            require(row["source_arithmetic_consistent"] is True, f"Consistent row incorrectly flagged for {row['id']}")
    require(mismatches == [("2023-11-po-2070887247", -180.0)], f"Unexpected source arithmetic mismatch set: {mismatches}")

    print(json.dumps({
        "status": "ok",
        "community_grants_categories": len(categories),
        "community_grants_final_total": grants["council_approved_total"],
        "community_grants_2026_applications": current["applications_received"],
        "community_grants_2026_proposed_awards": current["proposed_awards"],
        "community_grants_2026_proposed_total": current["proposed_award_total"],
        "museum_awards": museums["operating_grant_count"] + museums["project_grant_count"],
        "rural_transit_providers": len(transit["providers"]),
        "amendment_observations": len(observations),
        "source_arithmetic_mismatches": len(mismatches),
    }, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
