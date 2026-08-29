#!/usr/bin/env python3
"""Build 019 finalizer: authoritative capital IDs are structured project codes only.

Build 010's raw `previous_code` field is useful source context but is not a safe
cross-domain identity key in its current parser output: some values are parser labels,
some contain multiple codes, and some are reused across records. Build 019 therefore
excludes `previous_code` edges from the authoritative lifecycle graph.

Authoritative capital identifiers for this milestone are limited to:
- Build 018 `project_account_id`; and
- Build 010 current/prior `project_code` plus approved adjustment `project_code`.

Quarterly/Council capital references survive only when they exactly intersect that safe
structured-code set. No syntax heuristic, name similarity, or monetary match is used.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import build_lifecycle_reconciliation_build019 as base
import build_lifecycle_reconciliation_build019_v3 as v3


def safe_capital_ids() -> set[str]:
    schedule = base.load(base.PATHS["capital_schedule"])
    current = base.load(base.PATHS["current_capital"])
    values = {
        base.upper(row.get("project_account_id"))
        for row in (schedule.get("records") or [])
        if base.text(row.get("project_account_id"))
    }
    for row in [*(current.get("current_projects") or []), *(current.get("prior_projects") or []), *(current.get("adjustments") or [])]:
        code = base.upper(row.get("project_code"))
        if code:
            values.add(code)
    return values


def rebuild_same_identifier_chains(payload: dict[str, Any]) -> None:
    links = payload.get("identifier_links") or []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        grouped[(link["identifier_type"], link["identifier_value"])].append(link)

    chains = []
    for (identifier_type, identifier_value), rows in sorted(grouped.items()):
        domains = sorted({row["evidence"]["domain"] for row in rows})
        if len(domains) < 2:
            continue
        chains.append({
            "chain_id": f"b19-chain-{base.stable_hash(identifier_type, identifier_value)}",
            "identifier_type": identifier_type,
            "identifier_value": identifier_value,
            "domains": domains,
            "domain_count": len(domains),
            "record_types": sorted({row["evidence"]["record_type"] for row in rows}),
            "evidence_link_ids": [row["link_id"] for row in rows],
            "evidence_record_count": len({
                (row["evidence"]["domain"], row["evidence"]["record_type"], row["evidence"]["record_key"])
                for row in rows
            }),
            "authoritative": True,
            "join_rule": "same explicit identifier only",
        })
    payload["reconciled_chains"] = chains

    schedule_ids = {
        base.upper(row.get("project_account_id"))
        for row in (base.load(base.PATHS["capital_schedule"]).get("records") or [])
        if base.text(row.get("project_account_id"))
    }
    distribution: dict[str, int] = defaultdict(int)
    for row in chains:
        distribution[str(row["domain_count"])] += 1
    linked_capital = {row["identifier_value"] for row in chains if row["identifier_type"] == "capital_project_account"}
    linked_procurement = {row["identifier_value"] for row in chains if row["identifier_type"] == "procurement_reference"}
    summary = payload["summary"]
    summary.update({
        "identifier_links": len(links),
        "reconciled_chain_count": len(chains),
        "capital_identifier_chains": sum(1 for row in chains if row["identifier_type"] == "capital_project_account"),
        "procurement_identifier_chains": sum(1 for row in chains if row["identifier_type"] == "procurement_reference"),
        "purchase_order_chains": sum(1 for row in chains if row["identifier_type"] == "purchase_order"),
        "chain_domain_count_distribution": dict(sorted(distribution.items(), key=lambda item: int(item[0]))),
        "linked_build018_capital_ids": len(schedule_ids & linked_capital),
        "linked_procurement_refs": len(linked_procurement),
    })


def finalize(payload: dict[str, Any]) -> dict[str, Any]:
    safe = safe_capital_ids()
    kept = []
    excluded = []
    for link in payload.get("identifier_links") or []:
        if link.get("identifier_type") != "capital_project_account":
            kept.append(link)
            continue
        if link.get("source_field") == "previous_code":
            excluded.append({
                "link_id": link.get("link_id"),
                "identifier_value": link.get("identifier_value"),
                "source_field": "previous_code",
                "record_type": (link.get("evidence") or {}).get("record_type"),
                "record_key": (link.get("evidence") or {}).get("record_key"),
                "reason": "previous_code_not_authoritative_in_build019",
            })
            continue
        if link.get("identifier_value") not in safe:
            excluded.append({
                "link_id": link.get("link_id"),
                "identifier_value": link.get("identifier_value"),
                "source_field": link.get("source_field"),
                "record_type": (link.get("evidence") or {}).get("record_type"),
                "record_key": (link.get("evidence") or {}).get("record_key"),
                "reason": "capital_reference_not_in_safe_structured_project_code_set",
            })
            continue
        kept.append(link)

    payload["identifier_links"] = kept
    payload["excluded_capital_identifier_links"] = sorted(
        excluded,
        key=lambda row: (str(row.get("reason")), str(row.get("identifier_value")), str(row.get("record_key"))),
    )
    payload["metadata"]["authoritative_capital_identifier_policy"] = (
        "Build 019 authoritative capital identity uses Build 018 project_account_id and Build 010 current/prior/adjustment project_code only. "
        "Raw previous_code values are retained in their source artifact but excluded from Build 019 authoritative linking until a separate one-to-one continuity parser is validated."
    )
    payload["metadata"]["previous_code_authoritative"] = False
    payload["summary"]["authoritative_capital_ids"] = len(safe)
    payload["summary"]["excluded_capital_identifier_links"] = len(excluded)
    payload["summary"]["known_capital_ids_all_layers"] = len(safe)
    rebuild_same_identifier_chains(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=base.DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = finalize(v3.v2.finalize(base.build()))
    payload["metadata"]["council_procurement_token_policy"] = (
        "Exact canonical procurement references are verified in approved motion_text using the same year-number token; "
        "four- and two-digit year presentations are accepted and adjacent procurement prefixes do not invalidate the token."
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": payload["metadata"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
