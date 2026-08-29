#!/usr/bin/env python3
"""Validate Build 019 deterministic lifecycle-reconciliation semantics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/generated/lifecycle_reconciliation.json"

ALLOWED_IDENTIFIER_TYPES = {"capital_project_account", "procurement_reference", "purchase_order"}
ALLOWED_IDENTIFIER_METHODS = {
    "exact_structured_identifier",
    "exact_structured_previous_identifier",
    "exact_parser_extracted_identifier",
    "exact_procurement_identifier_format_normalization",
    "exact_known_identifier_in_structured_reference_field",
    "exact_parser_extracted_identifier_format_normalization",
    "exact_parser_extracted_identifier_intersection",
}
ALLOWED_DIRECT_METHODS = {"exact_document_id", "exact_meeting_id_and_item_ref"}


def fail(message: str) -> None:
    raise SystemExit(f"Build 019 lifecycle validation failed: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    summary = payload.get("summary") or {}
    identifier_links = payload.get("identifier_links") or []
    direct_links = payload.get("direct_links") or []
    chains = payload.get("reconciled_chains") or []

    if meta.get("build") != "019" or meta.get("parser_version") != "build019-deterministic-lifecycle-v1":
        fail("unexpected build/parser identity")
    if meta.get("baseline_sha") != "93fd8b769a48271b5f1f12782a3fa4a25a1d38d9":
        fail("Build 018 production baseline changed")
    if meta.get("uses_fuzzy_name_matching") is not False:
        fail("fuzzy-name matching must remain disabled")
    if meta.get("uses_dollar_value_matching") is not False:
        fail("dollar-value matching must remain disabled")
    if meta.get("is_accounts_payable_ledger") is not False or meta.get("has_vendor_payment_facts") is not False:
        fail("reconciliation artifact must not claim AP/payment evidence")
    if summary.get("capital_schedule_ids") != 52:
        fail(f"Build 018 capital schedule identifier control changed: {summary.get('capital_schedule_ids')}")

    link_ids = set()
    evidence_keys = set()
    by_link_id = {}
    for link in identifier_links:
        link_id = link.get("link_id")
        if not link_id or link_id in link_ids:
            fail(f"duplicate/missing identifier link id {link_id!r}")
        link_ids.add(link_id)
        by_link_id[link_id] = link
        if link.get("identifier_type") not in ALLOWED_IDENTIFIER_TYPES:
            fail(f"unapproved identifier type on {link_id}: {link.get('identifier_type')}")
        if not str(link.get("identifier_value") or "").strip():
            fail(f"blank identifier value on {link_id}")
        if link.get("match_method") not in ALLOWED_IDENTIFIER_METHODS:
            fail(f"unapproved identifier match method on {link_id}: {link.get('match_method')}")
        if link.get("authoritative") is not True:
            fail(f"identifier link is not marked authoritative: {link_id}")
        if link.get("used_name_for_matching") is not False or link.get("used_amount_for_matching") is not False:
            fail(f"forbidden matching basis on {link_id}")
        method = str(link.get("match_method") or "").lower()
        if "fuzzy" in method or "amount" in method or "dollar" in method or "name_similarity" in method:
            fail(f"forbidden method wording on {link_id}: {method}")
        evidence = link.get("evidence") or {}
        if evidence.get("domain") not in {"capital", "procurement", "amendment", "council"}:
            fail(f"unapproved evidence domain on {link_id}: {evidence.get('domain')}")
        if not evidence.get("record_type") or not evidence.get("record_key"):
            fail(f"incomplete evidence identity on {link_id}")
        if not evidence.get("source_id"):
            fail(f"missing source_id on {link_id}")
        if not evidence.get("source_locator"):
            fail(f"missing source locator on {link_id}")
        evidence_keys.add((evidence.get("domain"), evidence.get("record_type"), evidence.get("record_key")))

    direct_ids = set()
    for link in direct_links:
        link_id = link.get("link_id")
        if not link_id or link_id in direct_ids:
            fail(f"duplicate/missing direct link id {link_id!r}")
        direct_ids.add(link_id)
        if link.get("match_method") not in ALLOWED_DIRECT_METHODS:
            fail(f"unapproved direct-link method on {link_id}: {link.get('match_method')}")
        if link.get("authoritative") is not True:
            fail(f"direct link is not marked authoritative: {link_id}")
        if link.get("used_name_for_matching") is not False or link.get("used_amount_for_matching") is not False:
            fail(f"forbidden direct-link matching basis on {link_id}")
        for side in ("left", "right"):
            evidence = link.get(side) or {}
            if not evidence.get("domain") or not evidence.get("record_type") or not evidence.get("record_key"):
                fail(f"incomplete {side} evidence on {link_id}")
            if not evidence.get("source_id"):
                fail(f"missing {side} source_id on {link_id}")
        if not str(link.get("key_value") or "").strip():
            fail(f"blank direct-link key on {link_id}")

    chain_ids = set()
    for chain in chains:
        chain_id = chain.get("chain_id")
        if not chain_id or chain_id in chain_ids:
            fail(f"duplicate/missing chain id {chain_id!r}")
        chain_ids.add(chain_id)
        if chain.get("identifier_type") not in ALLOWED_IDENTIFIER_TYPES:
            fail(f"unapproved chain identifier type on {chain_id}")
        domains = chain.get("domains") or []
        if len(set(domains)) < 2 or chain.get("domain_count") != len(set(domains)):
            fail(f"chain is not genuinely cross-domain: {chain_id} {domains}")
        if chain.get("authoritative") is not True or chain.get("join_rule") != "same explicit identifier only":
            fail(f"chain policy changed on {chain_id}")
        refs = chain.get("evidence_link_ids") or []
        if not refs:
            fail(f"chain has no evidence links: {chain_id}")
        missing = [link_id for link_id in refs if link_id not in by_link_id]
        if missing:
            fail(f"chain references missing evidence links: {chain_id} {missing[:3]}")
        actual_domains = {by_link_id[link_id]["evidence"]["domain"] for link_id in refs}
        if actual_domains != set(domains):
            fail(f"chain domain summary does not match evidence: {chain_id}")
        identifier_values = {(by_link_id[link_id]["identifier_type"], by_link_id[link_id]["identifier_value"]) for link_id in refs}
        if identifier_values != {(chain.get("identifier_type"), chain.get("identifier_value"))}:
            fail(f"chain mixes identifiers: {chain_id}")

    if summary.get("identifier_links") != len(identifier_links):
        fail("identifier-link summary count mismatch")
    if summary.get("direct_documentary_links") != len(direct_links):
        fail("direct-link summary count mismatch")
    if summary.get("reconciled_chain_count") != len(chains):
        fail("chain summary count mismatch")
    if len(chains) < 1:
        fail("no deterministic cross-domain chains were produced")
    if len(direct_links) < 1:
        fail("no direct documentary links were produced")

    forbidden_blob = json.dumps(payload.get("metadata") or {}).lower() + " " + json.dumps(payload.get("unresolved_boundaries") or []).lower()
    if "payment facts" in forbidden_blob and meta.get("has_vendor_payment_facts") is not False:
        fail("payment semantics changed")

    print(json.dumps({
        "status": "ok",
        "identifier_links": len(identifier_links),
        "direct_links": len(direct_links),
        "chains": len(chains),
        "capital_chains": summary.get("capital_identifier_chains"),
        "procurement_chains": summary.get("procurement_identifier_chains"),
        "purchase_order_chains": summary.get("purchase_order_chains"),
        "linked_build018_capital_ids": summary.get("linked_build018_capital_ids"),
        "chain_domain_count_distribution": summary.get("chain_domain_count_distribution"),
    }, indent=2))


if __name__ == "__main__":
    main()
