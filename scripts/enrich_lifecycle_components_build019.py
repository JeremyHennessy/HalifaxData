#!/usr/bin/env python3
"""Enrich Build 019 with deterministic cross-identifier lifecycle components.

The base graph groups evidence by one exact identifier. This step adds narrowly defined
bridges between *different* explicit identifiers only when source structure proves that
they belong to the same record-level lifecycle event.

It deliberately does not bridge all identifiers merely because they appear in one parsed
record: consent motions and aggregate amendment rows can contain unrelated references.
Names and monetary values are never used to create a bridge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def text(value: Any) -> str:
    return " ".join(str(value or "").split())


def stable_hash(*parts: Any, length: int = 20) -> str:
    return hashlib.sha256("||".join(text(p) for p in parts).encode("utf-8")).hexdigest()[:length]


def evidence_key(evidence: dict[str, Any]) -> tuple[str, str, str]:
    return (
        text(evidence.get("domain")),
        text(evidence.get("record_type")),
        text(evidence.get("record_key")),
    )


def identifier_key(link: dict[str, Any]) -> str:
    return f"{link['identifier_type']}:{link['identifier_value']}"


def pairwise(left: list[dict[str, Any]], right: list[dict[str, Any]]):
    for a in left:
        for b in right:
            if identifier_key(a) != identifier_key(b):
                yield a, b


def bridge(
    *,
    a: dict[str, Any],
    b: dict[str, Any],
    source_evidence: dict[str, Any],
    bridge_type: str,
    match_method: str,
    interpretation: str,
) -> dict[str, Any]:
    nodes = sorted([identifier_key(a), identifier_key(b)])
    ev_key = evidence_key(source_evidence)
    return {
        "bridge_id": f"b19-bridge-{stable_hash(bridge_type, *nodes, *ev_key)}",
        "bridge_type": bridge_type,
        "identifier_a": {"type": a["identifier_type"], "value": a["identifier_value"]},
        "identifier_b": {"type": b["identifier_type"], "value": b["identifier_value"]},
        "source_evidence": source_evidence,
        "source_identifier_link_ids": sorted({a["link_id"], b["link_id"]}),
        "match_method": match_method,
        "authoritative": True,
        "used_name_for_matching": False,
        "used_amount_for_matching": False,
        "interpretation": interpretation,
    }


def build_bridges(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    links = payload.get("identifier_links") or []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        grouped[evidence_key(link["evidence"])].append(link)

    bridges: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for ev_key, rows in grouped.items():
        evidence = rows[0]["evidence"]
        record_type = evidence.get("record_type")
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_type[row["identifier_type"]].append(row)

        # HRM quarterly award table: solicitation/project number and Internal Reference /
        # Cost Centre Project Number are structured fields on the same award row.
        if record_type == "quarterly_alternative_procurement_award":
            for proc, capital in pairwise(by_type["procurement_reference"], by_type["capital_project_account"]):
                bridges.append(bridge(
                    a=proc,
                    b=capital,
                    source_evidence=evidence,
                    bridge_type="award_procurement_to_capital_account",
                    match_method="same_structured_quarterly_award_row",
                    interpretation="The official quarterly award row publishes both the procurement reference and the internal capital/project reference on the same award record.",
                ))

        # Current/prior capital project sheet explicitly publishes current and previous codes.
        if record_type in {"current_capital_project_sheet", "prior_capital_project_sheet"}:
            capitals = by_type["capital_project_account"]
            values = sorted({row["identifier_value"] for row in capitals})
            if len(values) == 2:
                by_value = {row["identifier_value"]: row for row in capitals}
                a, b = by_value[values[0]], by_value[values[1]]
                bridges.append(bridge(
                    a=a,
                    b=b,
                    source_evidence=evidence,
                    bridge_type="capital_account_code_continuity",
                    match_method="same_project_sheet_row_current_and_previous_code",
                    interpretation="The same official capital project-sheet row explicitly publishes the current project code and previous project code.",
                ))
            elif len(values) > 2:
                review.append({
                    "record_type": record_type,
                    "record_key": evidence.get("record_key"),
                    "reason": "more_than_two_capital_identifiers_on_project_sheet_record",
                    "identifiers": values,
                })

        # CAO amendment: only bridge a PO to a procurement reference when exactly one of
        # each survives on that observation. Aggregate rows with multiple refs are not bridged.
        if record_type == "cao_contract_amendment_observation":
            procs = by_type["procurement_reference"]
            pos = by_type["purchase_order"]
            if len({row["identifier_value"] for row in procs}) == 1 and len({row["identifier_value"] for row in pos}) == 1:
                bridges.append(bridge(
                    a=procs[0],
                    b=pos[0],
                    source_evidence=evidence,
                    bridge_type="amendment_procurement_to_purchase_order",
                    match_method="same_cao_amendment_observation_single_ref_single_po",
                    interpretation="The CAO amendment observation explicitly contains one procurement/contract reference and one purchase-order number.",
                ))
            elif procs and pos:
                review.append({
                    "record_type": record_type,
                    "record_key": evidence.get("record_key"),
                    "reason": "ambiguous_multiple_refs_on_amendment_observation",
                    "procurement_refs": sorted({row["identifier_value"] for row in procs}),
                    "purchase_orders": sorted({row["identifier_value"] for row in pos}),
                })

        # Council: only a specific item motion may bridge capital and procurement IDs.
        # Aggregate/consent motions are valid evidence edges but are not used to connect
        # identifiers across unrelated agenda items.
        if record_type == "approved_council_decision":
            procs = by_type["procurement_reference"]
            capitals = by_type["capital_project_account"]
            item_ref = text(evidence.get("source_item_ref"))
            proc_values = {row["identifier_value"] for row in procs}
            capital_values = {row["identifier_value"] for row in capitals}
            if item_ref and len(proc_values) == 1 and capital_values:
                for proc, capital in pairwise(procs, capitals):
                    bridges.append(bridge(
                        a=proc,
                        b=capital,
                        source_evidence=evidence,
                        bridge_type="council_procurement_to_capital_account",
                        match_method="same_specific_approved_motion_exact_identifiers",
                        interpretation="The same specific approved Council motion explicitly contains the procurement reference and capital project account identifier.",
                    ))
            elif procs and capitals:
                review.append({
                    "record_type": record_type,
                    "record_key": evidence.get("record_key"),
                    "reason": "aggregate_or_multi_procurement_council_motion_not_cross_bridged",
                    "source_item_ref": evidence.get("source_item_ref"),
                    "procurement_refs": sorted(proc_values),
                    "capital_accounts": sorted(capital_values),
                })

    unique = {}
    for row in bridges:
        existing = unique.get(row["bridge_id"])
        if existing and existing != row:
            raise RuntimeError(f"Build 019 identifier bridge collision: {row['bridge_id']}")
        unique[row["bridge_id"]] = row
    bridges = sorted(unique.values(), key=lambda row: (row["bridge_type"], row["identifier_a"]["value"], row["identifier_b"]["value"], row["bridge_id"]))
    review.sort(key=lambda row: (text(row.get("reason")), text(row.get("record_key"))))
    return bridges, review


class UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def build_components(payload: dict[str, Any], bridges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uf = UnionFind()
    for row in bridges:
        a = f"{row['identifier_a']['type']}:{row['identifier_a']['value']}"
        b = f"{row['identifier_b']['type']}:{row['identifier_b']['value']}"
        uf.union(a, b)

    component_nodes: dict[str, set[str]] = defaultdict(set)
    for node in list(uf.parent):
        component_nodes[uf.find(node)].add(node)

    links_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in payload.get("identifier_links") or []:
        links_by_node[identifier_key(link)].append(link)
    bridge_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in bridges:
        a = f"{row['identifier_a']['type']}:{row['identifier_a']['value']}"
        bridge_by_root[uf.find(a)].append(row)

    direct_links = payload.get("direct_links") or []
    components = []
    for root, nodes in sorted(component_nodes.items()):
        if len(nodes) < 2:
            continue
        evidence_links = [link for node in sorted(nodes) for link in links_by_node.get(node, [])]
        evidence_records = {evidence_key(link["evidence"]): link["evidence"] for link in evidence_links}
        attached_direct = []
        attached_external_evidence: dict[tuple[str, str, str], dict[str, Any]] = {}
        for direct in direct_links:
            left_key = evidence_key(direct.get("left") or {})
            right_key = evidence_key(direct.get("right") or {})
            if left_key in evidence_records or right_key in evidence_records:
                attached_direct.append(direct)
                if left_key not in evidence_records:
                    attached_external_evidence[left_key] = direct["left"]
                if right_key not in evidence_records:
                    attached_external_evidence[right_key] = direct["right"]

        all_evidence = {**evidence_records, **attached_external_evidence}
        domains = sorted({key[0] for key in all_evidence if key[0]})
        record_types = sorted({key[1] for key in all_evidence if key[1]})
        vendors = sorted({
            text(link["evidence"].get("vendor_name"))
            for link in evidence_links
            if text(link["evidence"].get("vendor_name"))
        })
        identifiers = []
        for node in sorted(nodes):
            id_type, id_value = node.split(":", 1)
            identifiers.append({"type": id_type, "value": id_value})

        stage_flags = {
            "has_capital": "capital" in domains,
            "has_procurement": "procurement" in domains,
            "has_amendment": "amendment" in domains,
            "has_council": "council" in domains,
            "has_council_document": "council_document" in domains,
            "has_payment": False,
        }
        components.append({
            "component_id": f"b19-component-{stable_hash(*sorted(nodes))}",
            "identifiers": identifiers,
            "identifier_count": len(identifiers),
            "identifier_bridge_ids": sorted(row["bridge_id"] for row in bridge_by_root[root]),
            "domains": domains,
            "domain_count": len(domains),
            "record_types": record_types,
            "evidence_link_ids": sorted({link["link_id"] for link in evidence_links}),
            "direct_link_ids": sorted({row["link_id"] for row in attached_direct}),
            "evidence_record_count": len(all_evidence),
            "vendor_names_context_only": vendors,
            "stage_flags": stage_flags,
            "authoritative": True,
            "join_policy": "explicit identifier bridges only; names and amounts are context only",
        })

    components.sort(key=lambda row: (-row["domain_count"], -row["identifier_count"], row["component_id"]))
    return components


def enrich(payload: dict[str, Any]) -> dict[str, Any]:
    bridges, bridge_review = build_bridges(payload)
    components = build_components(payload, bridges)
    payload["identifier_bridges"] = bridges
    payload["bridge_review_queue"] = bridge_review
    payload["lifecycle_components"] = components

    profiles: dict[str, int] = defaultdict(int)
    for row in components:
        profile = "+".join(row["domains"])
        profiles[profile] += 1
    summary = payload.setdefault("summary", {})
    summary["identifier_bridges"] = len(bridges)
    summary["bridge_review_queue"] = len(bridge_review)
    summary["lifecycle_components"] = len(components)
    summary["lifecycle_component_domain_profiles"] = dict(sorted(profiles.items()))
    summary["components_with_capital_and_procurement"] = sum(
        1 for row in components if row["stage_flags"]["has_capital"] and row["stage_flags"]["has_procurement"]
    )
    summary["components_with_procurement_and_amendment"] = sum(
        1 for row in components if row["stage_flags"]["has_procurement"] and row["stage_flags"]["has_amendment"]
    )
    summary["components_with_capital_procurement_and_council"] = sum(
        1 for row in components
        if row["stage_flags"]["has_capital"] and row["stage_flags"]["has_procurement"] and row["stage_flags"]["has_council"]
    )
    summary["components_with_payment"] = 0

    payload.setdefault("metadata", {})["identifier_bridge_policy"] = (
        "Different identifiers are connected only by source-structure rules: same quarterly award row; same project-sheet current/previous-code row; "
        "same CAO amendment observation with exactly one procurement ref and one PO; or same specific approved Council motion with exact procurement and capital identifiers. "
        "Aggregate/consent motions and ambiguous multi-reference amendment records are not cross-bridged."
    )
    payload["metadata"]["lifecycle_component_payment_semantics"] = "No payment stage is present until a separately acquired and validated AP/vendor-payment source supplies explicit payment identifiers."
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    payload = enrich(payload)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "identifier_bridges": payload["summary"]["identifier_bridges"],
        "bridge_review_queue": payload["summary"]["bridge_review_queue"],
        "lifecycle_components": payload["summary"]["lifecycle_components"],
        "profiles": payload["summary"]["lifecycle_component_domain_profiles"],
        "capital_procurement": payload["summary"]["components_with_capital_and_procurement"],
        "procurement_amendment": payload["summary"]["components_with_procurement_and_amendment"],
        "capital_procurement_council": payload["summary"]["components_with_capital_procurement_and_council"],
    }, indent=2))


if __name__ == "__main__":
    main()
