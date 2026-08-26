#!/usr/bin/env python3
"""Validate Build 012 authority-backed integrity / oversight artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
GENERATED = DATA / "generated"


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    oversight = load(GENERATED / "integrity_oversight.json")
    supplement = load(DATA / "integrity_sources.json")
    base = load(DATA / "sources.json")

    taxonomy = oversight.get("status_taxonomy", [])
    expected_taxonomy = [
        "anomaly",
        "control_weakness",
        "policy_noncompliance",
        "referred_for_investigation",
        "substantiated_wrongdoing",
    ]
    require([row.get("id") for row in taxonomy] == expected_taxonomy, "Build 012 taxonomy changed or is out of order")
    require([row.get("rank") for row in taxonomy] == [1, 2, 3, 4, 5], "Build 012 taxonomy ranks changed")

    base_ids = {row["id"] for row in base.get("sources", [])}
    supplemental = supplement.get("sources", [])
    supplemental_ids = [row.get("id") for row in supplemental]
    require(len(supplemental_ids) == len(set(supplemental_ids)), "Duplicate Build 012 supplemental source IDs")
    require(not (base_ids & set(supplemental_ids)), "Build 012 supplemental source duplicates base data/sources.json")
    require(len(supplemental) == 9, "Expected exactly 9 Build 012 supplemental source definitions")
    combined_ids = base_ids | set(supplemental_ids)

    findings = oversight.get("authority_findings", [])
    require(len(findings) == 6, "Expected exactly 6 authority finding records")
    mayor = [row for row in findings if row.get("group") == "Office of the Mayor Expenses Audit"]
    capital = [row for row in findings if row.get("group") == "Capital Budgeting Audit"]
    require(len(mayor) == 4, "Expected four Mayor Expenses authority records")
    require(all(row.get("status") == "policy_noncompliance" for row in mayor), "Mayor Expenses records must remain policy_noncompliance")
    require(len(capital) == 2, "Expected two Capital Budgeting authority records")
    require(all(row.get("status") == "control_weakness" for row in capital), "Capital Budgeting records must remain control_weakness")
    require(all(row.get("source_id") in combined_ids for row in findings), "Authority finding references an unknown source ID")

    all_statuses = [row.get("status") for row in findings]
    require("referred_for_investigation" not in all_statuses, "Build 012 must not infer a referral record from unsourced context")
    require("substantiated_wrongdoing" not in all_statuses, "Build 012 must not assert substantiated wrongdoing")

    meta = oversight.get("metadata", {})
    require(meta.get("mayor_transactions_examined") == 4, "Mayor transaction control changed")
    require(meta.get("mayor_transactions_noncompliant") == 4, "Mayor noncompliance control changed")
    require(meta.get("capital_projects_tested") == 12, "Capital sample control changed")
    require(meta.get("campaign_relationship_records") == 0, "Campaign relationship records must remain zero until verified joins exist")
    require(meta.get("is_transaction_ledger") is False, "Integrity artifact must not claim transaction-ledger completeness")
    require(meta.get("is_complete_contract_amendment_ledger") is False, "Amendment artifact must remain explicitly incomplete")
    require(meta.get("is_criminal_finding_dataset") is False, "Integrity artifact must not be characterized as a criminal-finding dataset")

    legal2 = next(row for row in findings if row.get("id") == "mayor-legal-invoice-2-2025")
    require(legal2.get("amount") == 6272.0, "Mayor legal invoice 2 amount changed")
    require(legal2.get("facts", {}).get("account_classification") == "Other Goods and Services", "Mayor legal invoice 2 classification changed")
    require(legal2.get("facts", {}).get("reimbursed") is True, "Mayor legal invoice reimbursement context missing")

    consultant1 = next(row for row in findings if row.get("id") == "mayor-consultant-procurement-1-2025")
    require(consultant1.get("amount") == 50000.0, "Consultant procurement 1 initial amount changed")
    require(consultant1.get("approximate_amended_value_semantics") == "source_says_over_90000", "Over-$90k source semantics must remain explicit")
    require(consultant1.get("facts", {}).get("valid_invoice_basis") is True, "Valid-invoice context must remain present")

    capital_quality = next(row for row in findings if row.get("id") == "capital-quality-review-2025-26")
    require(capital_quality.get("facts", {}).get("capital_plan_overstatement") == 1090000.0, "Capital plan overstatement control changed")
    require("not an identified improper payment" in capital_quality.get("caveat", ""), "Capital overstatement caveat must distinguish plan error from payment")

    amendments = oversight.get("contract_amendments", [])
    require(len(amendments) == 5, "Expected exactly five selected contract-amendment records")
    require(all(row.get("status") == "anomaly" for row in amendments), "Contract amendments are screening anomalies, not authority findings")
    require(all(row.get("source_id") in combined_ids for row in amendments), "Contract amendment references an unknown source ID")

    arithmetic_mismatches = 0
    for row in amendments:
        original = float(row["original_contract_value"])
        cumulative = float(row["cumulative_increase"])
        published_new = float(row["new_contract_value"])
        derived_new = round(original + cumulative, 2)
        delta = round(published_new - derived_new, 2)
        require(math.isclose(float(row["derived_new_contract_value"]), derived_new, abs_tol=0.01), f"Derived new value mismatch for {row['id']}")
        require(math.isclose(float(row["source_arithmetic_delta"]), delta, abs_tol=0.01), f"Source arithmetic delta mismatch for {row['id']}")
        consistent = abs(delta) <= 0.01
        require(row.get("source_arithmetic_consistent") is consistent, f"Source arithmetic consistency flag mismatch for {row['id']}")
        arithmetic_mismatches += int(not consistent)
        reported_pct = float(row["cumulative_increase_pct"])
        derived_pct = cumulative / original * 100 if original else 0
        require(abs(reported_pct - derived_pct) <= 0.6, f"Published cumulative percentage differs unexpectedly for {row['id']}")

    require(arithmetic_mismatches == 1, "Expected one preserved contract-amendment source arithmetic mismatch")
    require(meta.get("contract_amendment_source_arithmetic_mismatches") == arithmetic_mismatches, "Amendment arithmetic mismatch metadata control changed")
    fathom = next(row for row in amendments if row.get("id") == "amendment-fathom-24-016")
    require(fathom.get("source_arithmetic_consistent") is False, "Fathom source arithmetic discrepancy must remain explicit")
    require(math.isclose(fathom.get("source_arithmetic_delta"), -95.23, abs_tol=0.01), "Fathom published arithmetic delta changed")

    planned = oversight.get("planned_audits", [])
    require({row.get("subject") for row in planned} == {"Procurement", "Capital Project Performance"}, "Expected planned Auditor General audit subjects changed")
    require(all(row.get("source_id") in combined_ids for row in planned), "Planned audit references an unknown source ID")

    campaign_sources = [row for row in supplemental if row.get("category") == "Campaign finance"]
    require(len(campaign_sources) == 2, "Expected two campaign-finance source definitions")
    require(all("relationship" in (row.get("coverage", "") + supplement.get("metadata", {}).get("principle", "")).lower() or "campaign" in row.get("coverage", "").lower() for row in campaign_sources), "Campaign-finance scope boundary missing")

    print(
        f"Build 012 integrity oversight OK: {len(findings)} authority findings, "
        f"{len(amendments)} amendment examples, {arithmetic_mismatches} preserved source arithmetic mismatch, "
        f"{len(supplemental)} supplemental sources."
    )


if __name__ == "__main__":
    main()
