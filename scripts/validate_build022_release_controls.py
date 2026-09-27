#!/usr/bin/env python3
"""Build 022 release controls for the approved-minutes freshness release.

Build 019 remains the immutable historical baseline. Build 022 accepts only the
reviewed source-backed deltas:
- current Council calendar/document refresh;
- 54 newly approved PostMinutes decisions (2026-07-14 and 2026-08-25);
- exactly two new capital-account evidence links from the approved 2026-08-25
  $800,000 TMR2 capital transfer motion;
- no procurement artifact publication and no investigation queue mutation.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNCIL = ROOT / "data/generated/council.json"
DECISIONS = ROOT / "data/generated/council_decisions.json"
PROCUREMENT = ROOT / "data/generated/procurement.json"
LIFECYCLE = ROOT / "data/generated/lifecycle_reconciliation.json"
INVESTIGATIONS = ROOT / "data/generated/lifecycle_investigations.json"
PAYMENT_RESEARCH = ROOT / "data/payment_source_research_build020.json"

EXPECTED_LIFECYCLE = {
    "capital_schedule_ids": 52,
    "known_capital_ids_all_layers": 258,
    "authoritative_capital_ids": 258,
    "excluded_capital_identifier_links": 431,
    "identifier_links": 2813,
    "direct_documentary_links": 98,
    "reconciled_chain_count": 55,
    "capital_identifier_chains": 35,
    "procurement_identifier_chains": 20,
    "purchase_order_chains": 0,
    "chain_domain_count_distribution": {"2": 54, "3": 1},
    "linked_build018_capital_ids": 17,
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

EXPECTED_NEW_DECISIONS_BY_DATE = {"2026-07-14": 29, "2026-08-25": 25}
EXPECTED_TRANSFER_DECISION = "council-2026-08-25-2e7d5bef249aae2f18897e33"
EXPECTED_TRANSFER_ACCOUNTS = {"CE240001", "CI250009"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise SystemExit(f"Build 022 release-control validation failed: {message}")


def main() -> None:
    council = load(COUNCIL)
    decisions = load(DECISIONS)
    procurement = load(PROCUREMENT)
    lifecycle = load(LIFECYCLE)
    investigations = load(INVESTIGATIONS)
    payment = load(PAYMENT_RESEARCH)

    council_meta = council.get("metadata") or {}
    if council_meta.get("records") != 80:
        fail(f"Council meeting count changed: {council_meta.get('records')!r}")
    if council_meta.get("with_minutes") != 59:
        fail(f"Council posted-minutes count changed: {council_meta.get('with_minutes')!r}")

    decision_meta = decisions.get("metadata") or {}
    rows = decisions.get("records") or []
    if decision_meta.get("decision_records") != 1040 or len(rows) != 1040:
        fail(f"Council decision count must be 1040, got metadata={decision_meta.get('decision_records')} rows={len(rows)}")
    if decision_meta.get("incremental_adapter_version") != "build022-postminutes-html-v1":
        fail("approved PostMinutes adapter version is missing or changed")
    if decision_meta.get("is_payment_ledger") is not False:
        fail("Council decision evidence became a payment ledger")

    new_rows = [row for row in rows if row.get("meeting_date") >= "2026-07-01"]
    counts = dict(sorted(Counter(row.get("meeting_date") for row in new_rows).items()))
    if counts != EXPECTED_NEW_DECISIONS_BY_DATE:
        fail(f"new approved-decision date distribution changed: expected {EXPECTED_NEW_DECISIONS_BY_DATE}, got {counts}")
    if len(new_rows) != 54:
        fail(f"expected 54 newly released decisions, got {len(new_rows)}")
    if sum(1 for row in new_rows if row.get("fiscal_relevant")) != 17:
        fail("new fiscal-relevant decision count changed")
    if sum(1 for row in new_rows if row.get("money_mentions")) != 2:
        fail("new money-mention decision count changed")

    transfer = next((row for row in rows if row.get("decision_id") == EXPECTED_TRANSFER_DECISION), None)
    if not transfer:
        fail("approved Aug. 25 TMR2 transfer decision is missing")
    if transfer.get("decision_status") != "passed_unanimously":
        fail("TMR2 transfer decision status changed")
    if set(transfer.get("capital_account_refs") or []) != EXPECTED_TRANSFER_ACCOUNTS:
        fail(f"TMR2 transfer capital-account refs changed: {transfer.get('capital_account_refs')!r}")
    mentions = transfer.get("money_mentions") or []
    if len(mentions) != 1 or float(mentions[0].get("amount_cad") or 0) != 800000.0:
        fail(f"TMR2 transfer amount evidence changed: {mentions!r}")
    motion = str(transfer.get("motion_text") or "")
    for token in ("CE240001", "CI250009", "$800,000"):
        if token not in motion:
            fail(f"TMR2 transfer motion no longer explicitly contains {token!r}")

    procurement_meta = procurement.get("metadata") or {}
    procurement_rows = procurement.get("records") or []
    if procurement_meta.get("records") != 5502 or len(procurement_rows) != 5502:
        fail("checked procurement artifact changed during Council-only Build 022 release")
    if procurement_meta.get("source_query_record_count") != 6296:
        fail("checked procurement source snapshot identity changed unexpectedly")

    lifecycle_meta = lifecycle.get("metadata") or {}
    lifecycle_summary = lifecycle.get("summary") or {}
    for key, expected in EXPECTED_LIFECYCLE.items():
        if lifecycle_summary.get(key) != expected:
            fail(f"lifecycle control {key!r} changed: expected {expected!r}, got {lifecycle_summary.get(key)!r}")
    if lifecycle_meta.get("uses_fuzzy_name_matching") is not False or lifecycle_meta.get("uses_dollar_value_matching") is not False:
        fail("forbidden fuzzy/dollar lifecycle matching enabled")
    if lifecycle_meta.get("has_vendor_payment_facts") is not False or lifecycle_meta.get("is_accounts_payable_ledger") is not False:
        fail("lifecycle artifact claims payment/AP evidence")

    new_council_links = [
        link for link in lifecycle.get("identifier_links") or []
        if (link.get("evidence") or {}).get("domain") == "council"
        and (link.get("evidence") or {}).get("meeting_date") >= "2026-07-01"
    ]
    compact = {
        (
            link.get("identifier_type"),
            link.get("identifier_value"),
            (link.get("evidence") or {}).get("record_key"),
            link.get("source_field"),
        )
        for link in new_council_links
    }
    expected_compact = {
        ("capital_project_account", "CE240001", EXPECTED_TRANSFER_DECISION, "capital_account_refs"),
        ("capital_project_account", "CI250009", EXPECTED_TRANSFER_DECISION, "capital_account_refs"),
    }
    if compact != expected_compact:
        fail(f"unexpected new Council lifecycle links: {sorted(compact)!r}")

    investigation_summary = investigations.get("summary") or {}
    for key, expected in EXPECTED_INVESTIGATIONS.items():
        if investigation_summary.get(key) != expected:
            fail(f"investigation control {key!r} changed: expected {expected!r}, got {investigation_summary.get(key)!r}")
    if (investigations.get("metadata") or {}).get("has_payment_evidence") is not False:
        fail("investigation queue claims payment evidence")

    payment_meta = payment.get("metadata") or {}
    if payment_meta.get("status") != "transaction_source_not_yet_acquired_access_path_strengthened":
        fail(f"payment-source research status changed: {payment_meta.get('status')!r}")
    if payment_meta.get("ready_for_transaction_analysis") is not False:
        fail("payment transaction analysis was enabled")
    if payment_meta.get("verified_public_transaction_ledger") is not False:
        fail("payment research incorrectly claims a verified public transaction ledger")
    if payment_meta.get("verified_internal_transaction_records_exist") is not True:
        fail("Build 020 internal AP record-existence evidence was lost")
    if payment_meta.get("payment_facts_available_to_halifaxdata") != 0:
        fail("payment facts became available without a validated transaction source")
    if payment_meta.get("is_evidence_of_source_absence") is not False:
        fail("payment research became an unsupported source-absence claim")

    print(json.dumps({
        "status": "ok",
        "release": "Build 022 approved-minutes freshness + usability context",
        "council_meetings": 80,
        "council_decisions": 1040,
        "new_decisions_by_date": EXPECTED_NEW_DECISIONS_BY_DATE,
        "reviewed_new_lifecycle_links": sorted([list(row) for row in expected_compact]),
        "procurement_artifact_published": False,
        "investigation_queue_changed": False,
        "payment_analysis_enabled": False,
    }, indent=2))


if __name__ == "__main__":
    main()
