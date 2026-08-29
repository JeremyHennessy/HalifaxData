#!/usr/bin/env python3
"""Validate Build 019 deterministic lifecycle investigations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "data/generated/lifecycle_investigations.json"
LIFECYCLE = ROOT / "data/generated/lifecycle_reconciliation.json"

ALLOWED_REASONS = {
    "capital_account_linked_to_procurement_award_evidence",
    "multiple_procurement_references_linked_to_same_capital_component",
    "approved_council_motion_in_lifecycle_evidence",
    "procurement_reference_linked_to_public_cao_amendment_evidence",
    "multiple_purchase_orders_linked_to_same_procurement_reference",
}


def fail(message):
    raise SystemExit(f"Build 019 investigation validation failed: {message}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    summary = payload.get("summary") or {}
    rows = payload.get("investigations") or []
    components = {row.get("component_id"): row for row in (lifecycle.get("lifecycle_components") or [])}

    if meta.get("build") != "019" or meta.get("parser_version") != "build019-lifecycle-investigations-v1":
        fail("unexpected build/parser identity")
    if meta.get("baseline_sha") != "93fd8b769a48271b5f1f12782a3fa4a25a1d38d9":
        fail("Build 018 production baseline changed")
    if meta.get("uses_fuzzy_name_matching") is not False or meta.get("uses_dollar_value_matching_for_links") is not False:
        fail("forbidden link semantics enabled")
    if meta.get("has_payment_evidence") is not False:
        fail("queue must not claim payment evidence")
    if "not misconduct probability" not in str(meta.get("scoring_semantics") or ""):
        fail("review score interpretation boundary missing")
    if meta.get("operating_budget_bridge_status") != "not_available_without_shared_deterministic_identifier":
        fail("operating-budget bridge status changed")
    if meta.get("audited_psas_bridge_status") != "not_available_without_validated_crosswalk":
        fail("audited bridge status changed")

    ids = set()
    capital_procurement = 0
    amendment = 0
    council = 0
    reason_counts = {}
    for row in rows:
        iid = row.get("investigation_id")
        if not iid or iid in ids:
            fail(f"duplicate/missing investigation id {iid!r}")
        ids.add(iid)
        component = components.get(row.get("component_id"))
        if not component:
            fail(f"investigation references missing lifecycle component: {iid}")
        flags = component.get("stage_flags") or {}
        is_cap_proc = flags.get("has_capital") is True and flags.get("has_procurement") is True
        is_proc_amend = flags.get("has_procurement") is True and flags.get("has_amendment") is True
        if not (is_cap_proc or is_proc_amend):
            fail(f"investigation promoted a non-cross-domain target: {iid}")
        if row.get("has_payment_evidence") is not False:
            fail(f"investigation claims payment evidence: {iid}")
        if row.get("has_budget_service_area_bridge") is not False or row.get("has_audited_psas_bridge") is not False:
            fail(f"investigation claims unverified budget/audited bridge: {iid}")
        score = row.get("review_priority_score")
        if not isinstance(score, int) or not 0 <= score <= 100:
            fail(f"invalid review score on {iid}: {score}")
        expected_priority = "priority_review" if score >= 85 else "review" if score >= 72 else "context"
        if row.get("priority") != expected_priority:
            fail(f"priority threshold mismatch on {iid}")
        if "not a probability" not in str(row.get("interpretation") or ""):
            fail(f"investigation interpretation boundary missing: {iid}")

        reasons = row.get("review_reasons") or []
        if not reasons or any(reason not in ALLOWED_REASONS for reason in reasons):
            fail(f"invalid review reason on {iid}: {reasons}")
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if is_cap_proc:
            capital_procurement += 1
            if not row.get("capital_project_accounts") or not row.get("procurement_references"):
                fail(f"capital/procurement target missing identifiers: {iid}")
            if "capital_account_linked_to_procurement_award_evidence" not in reasons:
                fail(f"capital/procurement reason missing: {iid}")
        if is_proc_amend:
            amendment += 1
            if "procurement_reference_linked_to_public_cao_amendment_evidence" not in reasons:
                fail(f"procurement/amendment reason missing: {iid}")
            if not row.get("amendment_facts"):
                fail(f"amendment component lacks amendment facts: {iid}")
            for fact in row.get("amendment_facts") or []:
                if fact.get("is_final_paid_value") is not False or fact.get("is_invoice_or_payment") is not False:
                    fail(f"amendment fact mislabelled as payment: {iid}")
        if flags.get("has_council") is True:
            council += 1
            if "approved_council_motion_in_lifecycle_evidence" not in reasons:
                fail(f"Council-linked reason missing: {iid}")

        # Every source record in the queue must already be part of the component evidence set.
        component_link_ids = set(component.get("evidence_link_ids") or [])
        lifecycle_links = {link["link_id"]: link for link in lifecycle.get("identifier_links") or []}
        component_source_keys = {
            (
                (lifecycle_links.get(link_id) or {}).get("evidence", {}).get("source_id"),
                (lifecycle_links.get(link_id) or {}).get("evidence", {}).get("source_locator"),
                (lifecycle_links.get(link_id) or {}).get("evidence", {}).get("record_key"),
            )
            for link_id in component_link_ids
        }
        for source in row.get("source_evidence") or []:
            key = (source.get("source_id"), source.get("source_locator"), source.get("record_key"))
            if key not in component_source_keys:
                fail(f"investigation source not present in component evidence: {iid} {key}")

    if summary.get("investigations") != len(rows):
        fail("investigation summary count mismatch")
    if summary.get("capital_procurement") != capital_procurement:
        fail("capital/procurement summary mismatch")
    if summary.get("procurement_amendment") != amendment:
        fail("procurement/amendment summary mismatch")
    if summary.get("council_linked") != council:
        fail("Council-linked summary mismatch")
    if summary.get("with_payment_evidence") != 0:
        fail("summary claims payment evidence")
    if summary.get("reason_counts") != dict(sorted(reason_counts.items())):
        fail("review-reason counts do not reconcile")

    lifecycle_summary = lifecycle.get("summary") or {}
    if capital_procurement != lifecycle_summary.get("components_with_capital_and_procurement"):
        fail("queue does not cover all verified capital/procurement components")
    if amendment != lifecycle_summary.get("components_with_procurement_and_amendment"):
        fail("queue does not cover all verified procurement/amendment components")

    print(json.dumps({
        "status": "ok",
        "investigations": len(rows),
        "capital_procurement": capital_procurement,
        "procurement_amendment": amendment,
        "council_linked": council,
        "priority_review": summary.get("priority_review"),
        "review": summary.get("review"),
        "context": summary.get("context"),
        "payment_evidence": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
