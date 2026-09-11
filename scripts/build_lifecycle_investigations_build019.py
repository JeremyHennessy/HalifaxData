#!/usr/bin/env python3
"""Build a review queue from verified Build 019 lifecycle components.

This is a review-priority layer, not a misconduct model. It only promotes components that
already span at least two evidence domains and it never creates a new relationship.
Names and monetary values may be shown as source context but do not create links.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "data/generated/lifecycle_reconciliation.json"
AMENDMENTS = ROOT / "data/generated/contract_amendments.json"
DEFAULT_OUTPUT = ROOT / "data/generated/lifecycle_investigations.json"
PARSER_VERSION = "build019-lifecycle-investigations-v1"


def text(value: Any) -> str:
    return " ".join(str(value or "").split())


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def identifier_values(component: dict[str, Any], kind: str) -> list[str]:
    return sorted({text(row.get("value")) for row in (component.get("identifiers") or []) if row.get("type") == kind and text(row.get("value"))})


def source_evidence_index(lifecycle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["link_id"]: row for row in lifecycle.get("identifier_links") or []}


def amendment_index() -> dict[str, dict[str, Any]]:
    payload = load(AMENDMENTS)
    return {text(row.get("id")): row for row in (payload.get("observations") or []) if text(row.get("id"))}


def priority_score(*, has_council: bool, procurement_count: int, has_amendment: bool, po_count: int, domain_count: int) -> int:
    # Evidence-depth/complexity prioritization only. No wrongdoing probability.
    score = 48 + min(24, domain_count * 6)
    if has_council:
        score += 10
    if procurement_count >= 2:
        score += min(8, (procurement_count - 1) * 4)
    if has_amendment:
        score += 6
    if po_count >= 2:
        score += 3
    return min(96, score)


def priority_label(score: int) -> str:
    return "priority_review" if score >= 85 else "review" if score >= 72 else "context"


def amendment_facts(component: dict[str, Any], links: dict[str, dict[str, Any]], amendments: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    seen = set()
    for link_id in component.get("evidence_link_ids") or []:
        link = links.get(link_id) or {}
        evidence = link.get("evidence") or {}
        if evidence.get("record_type") != "cao_contract_amendment_observation":
            continue
        record_key = text(evidence.get("record_key"))
        row = amendments.get(record_key)
        if not row or record_key in seen:
            continue
        seen.add(record_key)
        output.append({
            "observation_id": record_key,
            "report_date": row.get("report_date"),
            "purchase_order": row.get("po"),
            "procurement_refs": row.get("procurement_refs") or [],
            "name_source": row.get("name_source"),
            "reason_source": row.get("reason_source"),
            "original_value": row.get("original_value"),
            "effective_cumulative_amendment_value": row.get("effective_cumulative_amendment_value"),
            "updated_value_source": row.get("updated_value_source"),
            "derived_updated_value": row.get("derived_updated_value"),
            "increase_pct_source": row.get("increase_pct_source"),
            "derived_increase_pct": row.get("derived_increase_pct"),
            "source_arithmetic_consistent": row.get("source_arithmetic_consistent"),
            "is_final_paid_value": False,
            "is_invoice_or_payment": False,
        })
    output.sort(key=lambda row: (text(row.get("report_date")), text(row.get("observation_id"))))
    return output


def evidence_sources(component: dict[str, Any], links: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    values = {}
    for link_id in component.get("evidence_link_ids") or []:
        evidence = (links.get(link_id) or {}).get("evidence") or {}
        key = (
            text(evidence.get("source_id")),
            text(evidence.get("source_locator")),
            text(evidence.get("source_url")),
        )
        if not key[0]:
            continue
        values[key] = {
            "source_id": key[0],
            "source_locator": key[1] or None,
            "source_url": key[2] or None,
            "domain": evidence.get("domain"),
            "record_type": evidence.get("record_type"),
            "record_key": evidence.get("record_key"),
            "label": evidence.get("label"),
        }
    return sorted(values.values(), key=lambda row: (text(row.get("domain")), text(row.get("source_id")), text(row.get("source_locator"))))


def build() -> dict[str, Any]:
    lifecycle = load(LIFECYCLE)
    links = source_evidence_index(lifecycle)
    amendments = amendment_index()
    queue = []

    for component in lifecycle.get("lifecycle_components") or []:
        flags = component.get("stage_flags") or {}
        has_capital_procurement = flags.get("has_capital") is True and flags.get("has_procurement") is True
        has_procurement_amendment = flags.get("has_procurement") is True and flags.get("has_amendment") is True
        if not (has_capital_procurement or has_procurement_amendment):
            continue

        capital_ids = identifier_values(component, "capital_project_account")
        procurement_refs = identifier_values(component, "procurement_reference")
        purchase_orders = identifier_values(component, "purchase_order")
        has_council = flags.get("has_council") is True
        amendment_rows = amendment_facts(component, links, amendments)
        reasons = []
        if has_capital_procurement:
            reasons.append("capital_account_linked_to_procurement_award_evidence")
        if len(procurement_refs) >= 2 and has_capital_procurement:
            reasons.append("multiple_procurement_references_linked_to_same_capital_component")
        if has_council:
            reasons.append("approved_council_motion_in_lifecycle_evidence")
        if has_procurement_amendment:
            reasons.append("procurement_reference_linked_to_public_cao_amendment_evidence")
        if len(purchase_orders) >= 2:
            reasons.append("multiple_purchase_orders_linked_to_same_procurement_reference")

        score = priority_score(
            has_council=has_council,
            procurement_count=len(procurement_refs),
            has_amendment=has_procurement_amendment,
            po_count=len(purchase_orders),
            domain_count=int(component.get("domain_count") or 0),
        )
        if has_capital_procurement:
            title = f"Capital lifecycle · {', '.join(capital_ids)}"
        else:
            title = f"Procurement amendment lifecycle · {', '.join(procurement_refs)}"

        observed = []
        if capital_ids:
            observed.append(f"Capital account(s): {', '.join(capital_ids)}")
        if procurement_refs:
            observed.append(f"Procurement reference(s): {', '.join(procurement_refs)}")
        if purchase_orders:
            observed.append(f"Purchase order(s): {', '.join(purchase_orders)}")
        if component.get("vendor_names_context_only"):
            observed.append(f"Published vendor name(s), context only: {', '.join(component['vendor_names_context_only'])}")
        observed.append(f"Evidence domains: {', '.join(component.get('domains') or [])}")

        queue.append({
            "investigation_id": f"b19-investigation-{component['component_id'].removeprefix('b19-component-')}",
            "component_id": component["component_id"],
            "title": title,
            "review_priority_score": score,
            "priority": priority_label(score),
            "review_reasons": reasons,
            "domains": component.get("domains") or [],
            "capital_project_accounts": capital_ids,
            "procurement_references": procurement_refs,
            "purchase_orders": purchase_orders,
            "vendor_names_context_only": component.get("vendor_names_context_only") or [],
            "observed_facts": observed,
            "amendment_facts": amendment_rows,
            "source_evidence": evidence_sources(component, links),
            "evidence_record_count": component.get("evidence_record_count"),
            "identifier_count": component.get("identifier_count"),
            "has_payment_evidence": False,
            "has_budget_service_area_bridge": False,
            "has_audited_psas_bridge": False,
            "interpretation": "Review priority reflects deterministic evidence depth and lifecycle complexity only. It is not a probability or finding of waste, corruption, illegality, policy breach, overpayment, or final paid value.",
        })

    queue.sort(key=lambda row: (-row["review_priority_score"], -row["evidence_record_count"], row["investigation_id"]))
    reason_counts = {}
    for row in queue:
        for reason in row["review_reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "metadata": {
            "build": "019",
            "parser_version": PARSER_VERSION,
            "dataset_status": "deterministic_lifecycle_review_queue",
            "baseline_sha": "93fd8b769a48271b5f1f12782a3fa4a25a1d38d9",
            "source_lifecycle_parser_version": (lifecycle.get("metadata") or {}).get("parser_version"),
            "scoring_semantics": "review_priority_score ranks evidence depth and lifecycle complexity; it is not misconduct probability or risk probability",
            "uses_fuzzy_name_matching": False,
            "uses_dollar_value_matching_for_links": False,
            "has_payment_evidence": False,
            "operating_budget_bridge_status": "not_available_without_shared_deterministic_identifier",
            "audited_psas_bridge_status": "not_available_without_validated_crosswalk",
        },
        "summary": {
            "investigations": len(queue),
            "priority_review": sum(1 for row in queue if row["priority"] == "priority_review"),
            "review": sum(1 for row in queue if row["priority"] == "review"),
            "context": sum(1 for row in queue if row["priority"] == "context"),
            "capital_procurement": sum(1 for row in queue if row["capital_project_accounts"] and row["procurement_references"]),
            "procurement_amendment": sum(1 for row in queue if "procurement_reference_linked_to_public_cao_amendment_evidence" in row["review_reasons"]),
            "council_linked": sum(1 for row in queue if "approved_council_motion_in_lifecycle_evidence" in row["review_reasons"]),
            "with_payment_evidence": 0,
            "reason_counts": dict(sorted(reason_counts.items())),
        },
        "investigations": queue,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
