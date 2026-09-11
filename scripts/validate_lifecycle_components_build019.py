#!/usr/bin/env python3
"""Validate Build 019 cross-identifier bridges and lifecycle components."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "data/generated/lifecycle_reconciliation.json"

ALLOWED_BRIDGES = {
    "award_procurement_to_capital_account": "same_structured_quarterly_award_row",
    "capital_account_code_continuity": "same_project_sheet_row_current_and_previous_code",
    "amendment_procurement_to_purchase_order": "same_cao_amendment_observation_single_ref_single_po",
    "council_procurement_to_capital_account": "same_specific_approved_motion_exact_identifiers",
}
ALLOWED_REVIEW_REASONS = {
    "more_than_two_capital_identifiers_on_project_sheet_record",
    "ambiguous_multiple_refs_on_amendment_observation",
    "aggregate_or_multi_procurement_council_motion_not_cross_bridged",
}


def fail(message: str) -> None:
    raise SystemExit(f"Build 019 component validation failed: {message}")


def id_key(item):
    return f"{item.get('type')}:{item.get('value')}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    summary = payload.get("summary") or {}
    bridges = payload.get("identifier_bridges") or []
    review = payload.get("bridge_review_queue") or []
    components = payload.get("lifecycle_components") or []
    identifier_links = payload.get("identifier_links") or []
    direct_links = payload.get("direct_links") or []

    if "Aggregate/consent motions" not in str(meta.get("identifier_bridge_policy") or ""):
        fail("bridge policy does not explicitly exclude aggregate consent-motion cross-bridging")
    if "No payment stage" not in str(meta.get("lifecycle_component_payment_semantics") or ""):
        fail("payment-stage boundary missing")

    link_ids = {row.get("link_id") for row in identifier_links}
    direct_ids = {row.get("link_id") for row in direct_links}
    bridge_ids = set()
    bridged_nodes = set()
    for row in bridges:
        bridge_id = row.get("bridge_id")
        if not bridge_id or bridge_id in bridge_ids:
            fail(f"duplicate/missing bridge id {bridge_id!r}")
        bridge_ids.add(bridge_id)
        bridge_type = row.get("bridge_type")
        expected_method = ALLOWED_BRIDGES.get(bridge_type)
        if not expected_method or row.get("match_method") != expected_method:
            fail(f"unapproved bridge type/method: {bridge_type} / {row.get('match_method')}")
        if row.get("authoritative") is not True:
            fail(f"bridge not authoritative: {bridge_id}")
        if row.get("used_name_for_matching") is not False or row.get("used_amount_for_matching") is not False:
            fail(f"bridge used forbidden name/amount basis: {bridge_id}")
        a, b = row.get("identifier_a") or {}, row.get("identifier_b") or {}
        if not a.get("type") or not a.get("value") or not b.get("type") or not b.get("value"):
            fail(f"bridge has incomplete identifier: {bridge_id}")
        if id_key(a) == id_key(b):
            fail(f"bridge does not connect different identifiers: {bridge_id}")
        bridged_nodes.update([id_key(a), id_key(b)])
        refs = row.get("source_identifier_link_ids") or []
        if len(refs) != 2 or any(ref not in link_ids for ref in refs):
            fail(f"bridge source identifier links invalid: {bridge_id}")
        evidence = row.get("source_evidence") or {}
        record_type = evidence.get("record_type")
        if bridge_type == "award_procurement_to_capital_account" and record_type != "quarterly_alternative_procurement_award":
            fail(f"award bridge not sourced from quarterly award row: {bridge_id}")
        if bridge_type == "capital_account_code_continuity" and record_type not in {"current_capital_project_sheet", "prior_capital_project_sheet"}:
            fail(f"capital continuity bridge wrong record type: {bridge_id}")
        if bridge_type == "amendment_procurement_to_purchase_order" and record_type != "cao_contract_amendment_observation":
            fail(f"amendment bridge wrong record type: {bridge_id}")
        if bridge_type == "council_procurement_to_capital_account":
            if record_type != "approved_council_decision":
                fail(f"Council bridge wrong record type: {bridge_id}")
            if not evidence.get("source_item_ref"):
                fail(f"Council bridge uses aggregate/consent motion: {bridge_id}")
            if evidence.get("context_status") != "exact_identifier_present_in_approved_motion_text":
                fail(f"Council bridge lacks exact-motion verification: {bridge_id}")

    for row in review:
        if row.get("reason") not in ALLOWED_REVIEW_REASONS:
            fail(f"unknown bridge review reason: {row.get('reason')}")

    component_ids = set()
    component_nodes = set()
    for row in components:
        cid = row.get("component_id")
        if not cid or cid in component_ids:
            fail(f"duplicate/missing component id {cid!r}")
        component_ids.add(cid)
        identifiers = row.get("identifiers") or []
        nodes = {id_key(item) for item in identifiers}
        if len(nodes) < 2 or row.get("identifier_count") != len(nodes):
            fail(f"component must contain >=2 unique explicit identifiers: {cid}")
        component_nodes.update(nodes)
        brefs = row.get("identifier_bridge_ids") or []
        if not brefs or any(ref not in bridge_ids for ref in brefs):
            fail(f"component bridge references invalid: {cid}")
        if row.get("authoritative") is not True:
            fail(f"component not authoritative: {cid}")
        if row.get("join_policy") != "explicit identifier bridges only; names and amounts are context only":
            fail(f"component join policy changed: {cid}")
        flags = row.get("stage_flags") or {}
        if flags.get("has_payment") is not False:
            fail(f"component claims a payment stage: {cid}")
        if "payment" in (row.get("domains") or []):
            fail(f"payment domain present without validated AP source: {cid}")
        if any(ref not in link_ids for ref in (row.get("evidence_link_ids") or [])):
            fail(f"component references missing identifier evidence: {cid}")
        if any(ref not in direct_ids for ref in (row.get("direct_link_ids") or [])):
            fail(f"component references missing documentary link: {cid}")
        # Vendor names are allowed for display/context but never as bridge keys.
        if not isinstance(row.get("vendor_names_context_only") or [], list):
            fail(f"vendor context field malformed: {cid}")

    if component_nodes != bridged_nodes:
        missing = sorted(bridged_nodes - component_nodes)[:5]
        extra = sorted(component_nodes - bridged_nodes)[:5]
        fail(f"component node coverage does not equal bridge graph; missing={missing} extra={extra}")

    if summary.get("identifier_bridges") != len(bridges):
        fail("bridge summary count mismatch")
    if summary.get("bridge_review_queue") != len(review):
        fail("bridge review summary count mismatch")
    if summary.get("lifecycle_components") != len(components):
        fail("component summary count mismatch")
    if summary.get("components_with_payment") != 0:
        fail("component summary claims payment coverage")
    if not components:
        fail("no deterministic cross-identifier lifecycle components were produced")
    if not any(row.get("stage_flags", {}).get("has_capital") and row.get("stage_flags", {}).get("has_procurement") for row in components):
        fail("no capital-to-procurement lifecycle component produced")

    print(json.dumps({
        "status": "ok",
        "identifier_bridges": len(bridges),
        "bridge_review_queue": len(review),
        "lifecycle_components": len(components),
        "profiles": summary.get("lifecycle_component_domain_profiles"),
        "components_with_capital_and_procurement": summary.get("components_with_capital_and_procurement"),
        "components_with_procurement_and_amendment": summary.get("components_with_procurement_and_amendment"),
        "components_with_capital_procurement_and_council": summary.get("components_with_capital_procurement_and_council"),
        "components_with_payment": summary.get("components_with_payment"),
    }, indent=2))


if __name__ == "__main__":
    main()
