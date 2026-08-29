#!/usr/bin/env python3
"""Pin the measured Build 019 release controls after source-level review.

These are release controls, not coverage/completeness claims. Any future source refresh
that legitimately changes them should do so in a later build with a documented review.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "data/generated/lifecycle_reconciliation.json"
INVESTIGATIONS = ROOT / "data/generated/lifecycle_investigations.json"
PAYMENT_RESEARCH = ROOT / "data/payment_source_research_build019.json"

EXPECTED_LIFECYCLE = {
    "capital_schedule_ids": 52,
    "known_capital_ids_all_layers": 258,
    "authoritative_capital_ids": 258,
    "excluded_capital_identifier_links": 431,
    "identifier_links": 2811,
    "direct_documentary_links": 98,
    "reconciled_chain_count": 53,
    "capital_identifier_chains": 33,
    "procurement_identifier_chains": 20,
    "purchase_order_chains": 0,
    "chain_domain_count_distribution": {"2": 52, "3": 1},
    "linked_build018_capital_ids": 16,
    "linked_procurement_refs": 20,
    "quarantined_council_identifier_links": 0,
    "identifier_bridges": 40,
    "bridge_review_queue": 0,
    "lifecycle_components": 31,
    "lifecycle_component_domain_profiles": {
        "amendment": 2,
        "amendment+procurement": 8,
        "capital+council+council_document+procurement": 3,
        "capital+council_document+procurement": 18,
    },
    "components_with_capital_and_procurement": 21,
    "components_with_procurement_and_amendment": 8,
    "components_with_capital_procurement_and_council": 3,
    "components_with_payment": 0,
}

EXPECTED_INVESTIGATIONS = {
    "investigations": 29,
    "priority_review": 2,
    "review": 2,
    "context": 25,
    "capital_procurement": 21,
    "procurement_amendment": 8,
    "council_linked": 3,
    "with_payment_evidence": 0,
    "reason_counts": {
        "approved_council_motion_in_lifecycle_evidence": 3,
        "capital_account_linked_to_procurement_award_evidence": 21,
        "multiple_procurement_references_linked_to_same_capital_component": 7,
        "multiple_purchase_orders_linked_to_same_procurement_reference": 1,
        "procurement_reference_linked_to_public_cao_amendment_evidence": 8,
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"Build 019 release-control validation failed: {message}")


def main() -> None:
    lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    investigations = json.loads(INVESTIGATIONS.read_text(encoding="utf-8"))
    payment = json.loads(PAYMENT_RESEARCH.read_text(encoding="utf-8"))

    lifecycle_summary = lifecycle.get("summary") or {}
    for key, expected in EXPECTED_LIFECYCLE.items():
        actual = lifecycle_summary.get(key)
        if actual != expected:
            fail(f"lifecycle control {key!r} changed: expected {expected!r}, got {actual!r}")

    investigation_summary = investigations.get("summary") or {}
    for key, expected in EXPECTED_INVESTIGATIONS.items():
        actual = investigation_summary.get(key)
        if actual != expected:
            fail(f"investigation control {key!r} changed: expected {expected!r}, got {actual!r}")

    lifecycle_meta = lifecycle.get("metadata") or {}
    if lifecycle_meta.get("baseline_sha") != "93fd8b769a48271b5f1f12782a3fa4a25a1d38d9":
        fail("lifecycle artifact no longer identifies the verified Build 018 production baseline")
    if lifecycle_meta.get("previous_code_authoritative") is not False:
        fail("previous_code became authoritative")
    if lifecycle_meta.get("uses_fuzzy_name_matching") is not False or lifecycle_meta.get("uses_dollar_value_matching") is not False:
        fail("forbidden fuzzy/dollar lifecycle matching enabled")
    if lifecycle_meta.get("has_vendor_payment_facts") is not False or lifecycle_meta.get("is_accounts_payable_ledger") is not False:
        fail("lifecycle artifact claims payment/AP evidence")

    inv_meta = investigations.get("metadata") or {}
    if inv_meta.get("baseline_sha") != lifecycle_meta.get("baseline_sha"):
        fail("investigation and lifecycle baseline identities diverged")
    if inv_meta.get("has_payment_evidence") is not False:
        fail("investigation queue claims payment evidence")
    if inv_meta.get("operating_budget_bridge_status") != "not_available_without_shared_deterministic_identifier":
        fail("investigation queue claims an unsupported operating-budget bridge")
    if inv_meta.get("audited_psas_bridge_status") != "not_available_without_validated_crosswalk":
        fail("investigation queue claims an unsupported audited-PSAS bridge")

    payment_meta = payment.get("metadata") or {}
    if payment_meta.get("status") != "not_yet_verified_public_transaction_source":
        fail("payment-source research status changed")
    if payment_meta.get("ready_for_transaction_analysis") is not False:
        fail("payment transaction analysis was enabled")
    if payment_meta.get("is_evidence_of_source_absence") is not False:
        fail("payment research was promoted to an unsupported source-absence claim")

    print(json.dumps({
        "status": "ok",
        "lifecycle_release_controls": EXPECTED_LIFECYCLE,
        "investigation_release_controls": EXPECTED_INVESTIGATIONS,
        "payment_source_status": payment_meta.get("status"),
        "payment_analysis_enabled": False,
    }, indent=2))


if __name__ == "__main__":
    main()
