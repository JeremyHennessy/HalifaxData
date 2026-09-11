#!/usr/bin/env python3
"""Finalize Build 019 deterministic lifecycle reconciliation semantics.

The core builder discovers explicit identifier-bearing evidence. This layer enforces two
additional release rules discovered during source review:

1. Multiple literal source spellings that normalize to the same explicit identifier on
   one evidence record are retained as raw variants on one canonical evidence edge.
2. A Council identifier edge is authoritative only when the exact identifier occurs in
   the approved motion text itself. Item headings are retained as context but never used
   as the linkage basis because consent-motion bundles can inherit an unrelated nearest
   heading from PDF parsing.

No fuzzy names, descriptions, vendors, or dollar values are used to create links.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import build_lifecycle_reconciliation_build019 as base


def add_identifier_link(
    links: list[dict[str, Any]],
    *,
    identifier_type: str,
    identifier_value: str,
    raw_identifier: str,
    evidence: dict[str, Any],
    match_method: str,
    source_field: str,
) -> None:
    """Use raw spelling in the temporary ID so core discovery cannot collide.

    finalize_identifier_links() later collapses these into one canonical evidence edge
    while retaining every observed raw spelling.
    """
    links.append({
        "link_id": f"b19-discovery-{base.stable_hash(identifier_type, identifier_value, raw_identifier, evidence['domain'], evidence['record_type'], evidence['record_key'], match_method, source_field)}",
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "raw_identifier": raw_identifier,
        "evidence": evidence,
        "match_method": match_method,
        "source_field": source_field,
        "authoritative": True,
        "used_name_for_matching": False,
        "used_amount_for_matching": False,
    })


base.add_identifier_link = add_identifier_link


def load_council_decisions() -> dict[str, dict[str, Any]]:
    payload = base.load(base.PATHS["council_decisions"])
    return {
        base.text(row.get("decision_id")): row
        for row in (payload.get("records") or [])
        if base.text(row.get("decision_id"))
    }


def council_ref_is_in_motion(link: dict[str, Any], decision: dict[str, Any], known_capital_ids: set[str]) -> bool:
    motion = base.text(decision.get("motion_text"))
    identifier_type = link.get("identifier_type")
    identifier_value = link.get("identifier_value")
    if not motion or not identifier_value:
        return False
    if identifier_type == "procurement_reference":
        motion_refs = {canonical for canonical, _raw in base.procurement_refs([motion])}
        return identifier_value in motion_refs
    if identifier_type == "capital_project_account":
        return identifier_value in set(base.exact_known_tokens(motion, known_capital_ids))
    return False


def council_context_evidence(link: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(link["evidence"])
    date = base.text(decision.get("meeting_date")) or "date unavailable"
    item_ref = base.text(decision.get("item_ref"))
    evidence["label"] = f"Council motion · {date}" + (f" · item {item_ref}" if item_ref else " · aggregate/consent motion")
    evidence["source_item_ref"] = decision.get("item_ref")
    evidence["source_item_title"] = decision.get("item_title")
    evidence["context_status"] = "exact_identifier_present_in_approved_motion_text"
    evidence["item_metadata_used_for_matching"] = False
    evidence["motion_text_used_for_identifier_verification"] = True
    return evidence


def finalize_identifier_links(discovered: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions = load_council_decisions()
    known_capital_ids = {
        base.upper(link.get("identifier_value"))
        for link in discovered
        if link.get("identifier_type") == "capital_project_account" and base.text(link.get("identifier_value"))
    }

    accepted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for original in discovered:
        link = dict(original)
        evidence = dict(link.get("evidence") or {})
        if evidence.get("domain") == "council":
            decision_id = base.text(evidence.get("record_key"))
            decision = decisions.get(decision_id)
            if not decision:
                quarantined.append({
                    "identifier_type": link.get("identifier_type"),
                    "identifier_value": link.get("identifier_value"),
                    "record_key": decision_id,
                    "reason": "council_decision_record_not_found",
                })
                continue
            if not council_ref_is_in_motion(link, decision, known_capital_ids):
                quarantined.append({
                    "identifier_type": link.get("identifier_type"),
                    "identifier_value": link.get("identifier_value"),
                    "record_key": decision_id,
                    "meeting_id": decision.get("meeting_id"),
                    "meeting_date": decision.get("meeting_date"),
                    "source_item_ref": decision.get("item_ref"),
                    "source_item_title": decision.get("item_title"),
                    "reason": "identifier_not_present_in_approved_motion_text",
                })
                continue
            evidence = council_context_evidence(link, decision)
            link["evidence"] = evidence
        accepted.append(link)

    # Collapse duplicate raw source spellings onto one canonical evidence edge.
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for link in accepted:
        evidence = link["evidence"]
        key = (
            link["identifier_type"],
            link["identifier_value"],
            evidence["domain"],
            evidence["record_type"],
            evidence["record_key"],
            link["match_method"],
            link["source_field"],
        )
        grouped[key].append(link)

    final: list[dict[str, Any]] = []
    for key, variants in grouped.items():
        first = variants[0]
        raw_identifiers = sorted({base.text(item.get("raw_identifier")) for item in variants if base.text(item.get("raw_identifier"))})
        link_id = f"b19-{base.stable_hash(*key)}"
        final.append({
            "link_id": link_id,
            "identifier_type": first["identifier_type"],
            "identifier_value": first["identifier_value"],
            "raw_identifier": raw_identifiers[0] if raw_identifiers else first.get("identifier_value"),
            "raw_identifiers": raw_identifiers,
            "evidence": first["evidence"],
            "match_method": first["match_method"],
            "source_field": first["source_field"],
            "authoritative": True,
            "used_name_for_matching": False,
            "used_amount_for_matching": False,
        })

    final.sort(key=lambda row: (
        row["identifier_type"], row["identifier_value"], row["evidence"]["domain"],
        row["evidence"]["record_key"], row["match_method"], row["source_field"], row["link_id"]
    ))
    quarantined.sort(key=lambda row: (str(row.get("identifier_type")), str(row.get("identifier_value")), str(row.get("record_key"))))
    return final, quarantined


def rebuild_chains(payload: dict[str, Any]) -> None:
    identifier_links = payload["identifier_links"]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for link in identifier_links:
        grouped[(link["identifier_type"], link["identifier_value"])].append(link)

    chains = []
    for (identifier_type, identifier_value), links in sorted(grouped.items()):
        domains = sorted({link["evidence"]["domain"] for link in links})
        if len(domains) < 2:
            continue
        record_types = sorted({link["evidence"]["record_type"] for link in links})
        chains.append({
            "chain_id": f"b19-chain-{base.stable_hash(identifier_type, identifier_value)}",
            "identifier_type": identifier_type,
            "identifier_value": identifier_value,
            "domains": domains,
            "domain_count": len(domains),
            "record_types": record_types,
            "evidence_link_ids": [link["link_id"] for link in links],
            "evidence_record_count": len({
                (link["evidence"]["domain"], link["evidence"]["record_type"], link["evidence"]["record_key"])
                for link in links
            }),
            "authoritative": True,
            "join_rule": "same explicit identifier only",
        })

    schedule = base.load(base.PATHS["capital_schedule"])
    schedule_ids = {
        base.upper(row.get("project_account_id"))
        for row in (schedule.get("records") or [])
        if base.text(row.get("project_account_id"))
    }
    chain_distribution: dict[str, int] = defaultdict(int)
    for chain in chains:
        chain_distribution[str(chain["domain_count"])] += 1
    linked_capital_ids = {
        chain["identifier_value"] for chain in chains
        if chain["identifier_type"] == "capital_project_account"
    }
    linked_procurement_refs = {
        chain["identifier_value"] for chain in chains
        if chain["identifier_type"] == "procurement_reference"
    }

    summary = payload["summary"]
    summary.update({
        "identifier_links": len(identifier_links),
        "direct_documentary_links": len(payload.get("direct_links") or []),
        "reconciled_chain_count": len(chains),
        "capital_identifier_chains": sum(1 for row in chains if row["identifier_type"] == "capital_project_account"),
        "procurement_identifier_chains": sum(1 for row in chains if row["identifier_type"] == "procurement_reference"),
        "purchase_order_chains": sum(1 for row in chains if row["identifier_type"] == "purchase_order"),
        "chain_domain_count_distribution": dict(sorted(chain_distribution.items(), key=lambda item: int(item[0]))),
        "linked_build018_capital_ids": len(schedule_ids & linked_capital_ids),
        "linked_procurement_refs": len(linked_procurement_refs),
        "quarantined_council_identifier_links": len(payload.get("quarantined_links") or []),
    })
    payload["reconciled_chains"] = chains


def finalize(payload: dict[str, Any]) -> dict[str, Any]:
    links, quarantined = finalize_identifier_links(payload.get("identifier_links") or [])
    payload["identifier_links"] = links
    payload["quarantined_links"] = quarantined
    payload["metadata"]["council_identifier_policy"] = (
        "Council identifier edges require the exact identifier in approved motion_text. "
        "Parsed item_ref/item_title are retained as context only and never create a link."
    )
    payload["metadata"]["council_item_metadata_used_for_matching"] = False
    payload["metadata"]["duplicate_raw_identifier_policy"] = (
        "Multiple literal source spellings that normalize to one explicit identifier on the same evidence record "
        "are retained in raw_identifiers on one canonical edge."
    )
    rebuild_chains(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=base.DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = finalize(base.build())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": payload["metadata"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
