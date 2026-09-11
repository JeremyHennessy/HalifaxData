#!/usr/bin/env python3
"""Build deterministic cross-domain lifecycle reconciliation for HalifaxData Build 019.

This builder is deliberately offline and conservative. It links checked-in evidence only
when the same explicit identifier is present in structured source fields or has already
been extracted by a source-specific parser. It never creates authoritative links from
vendor/project-name similarity, dollar values, or other fuzzy heuristics.

The output is an evidence graph, not an accounts-payable ledger. Award, amendment,
budget and approval records must retain their own source semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/generated/lifecycle_reconciliation.json"

PATHS = {
    "current_budget": ROOT / "data/generated/current_budget_2026_27.json",
    "capital_schedule": ROOT / "data/generated/current_capital_2026_27_multiyear.json",
    "current_capital": ROOT / "data/generated/current_capital.json",
    "procurement_public": ROOT / "data/generated/procurement.json",
    "procurement_quarterly": ROOT / "data/generated/procurement_quarterly.json",
    "contract_amendments": ROOT / "data/generated/contract_amendments.json",
    "council_decisions": ROOT / "data/generated/council_decisions.json",
    "council_documents": ROOT / "data/generated/council_documents.json",
}

PROCUREMENT_RE = re.compile(r"\b(?:HRM-)?((?:20)?\d{2})\s*-\s*(\d{3,5})\b", re.I)
TOKEN_BOUNDARY = r"[A-Z0-9]"
PARSER_VERSION = "build019-deterministic-lifecycle-v1"


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected object payload at {path}")
    return payload


def text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def upper(value: Any) -> str:
    return text(value).upper()


def stable_hash(*parts: Any, length: int = 20) -> str:
    raw = "||".join(text(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def canonical_procurement_ref(value: Any) -> str | None:
    """Normalize only the identifier's source-formatting differences.

    Rules:
    - optional literal HRM- prefix is ignored;
    - whitespace around the hyphen is ignored;
    - two-digit years are expanded to 20YY;
    - no name/value inference is performed.
    """
    match = PROCUREMENT_RE.search(text(value))
    if not match:
        return None
    year, number = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    year_num = int(year)
    if year_num < 2000 or year_num > 2099:
        return None
    return f"{year_num:04d}-{number}"


def procurement_refs(values: Iterable[Any]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    seen = set()
    for value in values:
        raw = text(value)
        for match in PROCUREMENT_RE.finditer(raw):
            token = match.group(0)
            canonical = canonical_procurement_ref(token)
            if not canonical:
                continue
            key = (canonical, token)
            if key not in seen:
                seen.add(key)
                output.append(key)
    return output


def exact_known_tokens(value: Any, known: set[str]) -> list[str]:
    """Return literal whole-token intersections with a known identifier set."""
    raw = upper(value)
    found = []
    for token in sorted(known, key=lambda item: (-len(item), item)):
        pattern = rf"(?<!{TOKEN_BOUNDARY}){re.escape(token)}(?!{TOKEN_BOUNDARY})"
        if re.search(pattern, raw):
            found.append(token)
    return found


def source_locator(row: dict[str, Any]) -> str | None:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    for value in (
        provenance.get("locator_value"),
        row.get("source_locator"),
        row.get("source_row_id"),
    ):
        if text(value):
            return text(value)
    parts = []
    for key in ("source_page", "source_table", "source_row"):
        if row.get(key) is not None:
            parts.append(f"{key}={row[key]}")
    return "/".join(parts) or None


def source_url(row: dict[str, Any]) -> str | None:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    for value in (
        provenance.get("source_url_resolved"),
        provenance.get("source_url"),
        row.get("source_url_resolved"),
        row.get("source_url"),
        row.get("url"),
    ):
        if text(value):
            return text(value)
    return None


def evidence_ref(
    *,
    domain: str,
    record_type: str,
    record_key: str,
    row: dict[str, Any],
    label: str | None = None,
    source_id: str | None = None,
    locator: str | None = None,
    url: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "domain": domain,
        "record_type": record_type,
        "record_key": record_key,
        "label": label,
        "source_id": source_id or row.get("source_id") or (row.get("provenance") or {}).get("source_id"),
        "source_locator": locator or source_locator(row),
        "source_url": url or source_url(row),
    }
    if extra:
        result.update(extra)
    return result


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
    links.append({
        "link_id": f"b19-{stable_hash(identifier_type, identifier_value, evidence['domain'], evidence['record_type'], evidence['record_key'], source_field)}",
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


def add_direct_link(
    links: list[dict[str, Any]],
    *,
    link_type: str,
    left: dict[str, Any],
    right: dict[str, Any],
    match_method: str,
    key_type: str,
    key_value: str,
    interpretation: str,
) -> None:
    links.append({
        "link_id": f"b19-direct-{stable_hash(link_type, left['record_key'], right['record_key'], key_type, key_value)}",
        "link_type": link_type,
        "left": left,
        "right": right,
        "match_method": match_method,
        "key_type": key_type,
        "key_value": key_value,
        "interpretation": interpretation,
        "authoritative": True,
        "used_name_for_matching": False,
        "used_amount_for_matching": False,
    })


def build() -> dict[str, Any]:
    inputs = {name: load(path) for name, path in PATHS.items()}
    schedule_rows = inputs["capital_schedule"].get("records") or []
    current_projects = inputs["current_capital"].get("current_projects") or []
    prior_projects = inputs["current_capital"].get("prior_projects") or []
    adjustments = inputs["current_capital"].get("adjustments") or []
    public_awards = inputs["procurement_public"].get("records") or []
    quarterly_awards = inputs["procurement_quarterly"].get("alternative_procurement") or []
    amendments = inputs["contract_amendments"].get("observations") or []
    decisions = inputs["council_decisions"].get("records") or []
    documents = inputs["council_documents"].get("records") or []

    schedule_ids = {upper(row.get("project_account_id")) for row in schedule_rows if text(row.get("project_account_id"))}
    sheet_ids = {upper(row.get("project_code")) for row in [*current_projects, *prior_projects] if text(row.get("project_code"))}
    previous_ids = {upper(row.get("previous_code")) for row in [*current_projects, *prior_projects] if text(row.get("previous_code"))}
    known_capital_ids = schedule_ids | sheet_ids | previous_ids

    identifier_links: list[dict[str, Any]] = []
    direct_links: list[dict[str, Any]] = []

    # Capital schedule — authoritative structured project account field.
    for row in schedule_rows:
        project_id = upper(row.get("project_account_id"))
        if not project_id:
            continue
        evidence = evidence_ref(
            domain="capital",
            record_type="current_capital_multiyear_schedule",
            record_key=project_id,
            row=row,
            label=row.get("project_name"),
            extra={"fiscal_year": row.get("fiscal_year"), "schedule_class": row.get("schedule_class")},
        )
        add_identifier_link(
            identifier_links,
            identifier_type="capital_project_account",
            identifier_value=project_id,
            raw_identifier=text(row.get("project_account_id")),
            evidence=evidence,
            match_method="exact_structured_identifier",
            source_field="project_account_id",
        )

    # Current/prior project sheets — exact project code and explicitly published previous code.
    for layer, rows in (("current_capital_project_sheet", current_projects), ("prior_capital_project_sheet", prior_projects)):
        for row in rows:
            project_code = upper(row.get("project_code"))
            if project_code:
                evidence = evidence_ref(
                    domain="capital",
                    record_type=layer,
                    record_key=f"{row.get('plan_year')}:{project_code}",
                    row=row,
                    label=row.get("project_name"),
                    extra={"plan_year": row.get("plan_year")},
                )
                add_identifier_link(
                    identifier_links,
                    identifier_type="capital_project_account",
                    identifier_value=project_code,
                    raw_identifier=text(row.get("project_code")),
                    evidence=evidence,
                    match_method="exact_structured_identifier",
                    source_field="project_code",
                )
            previous_code = upper(row.get("previous_code"))
            if previous_code:
                evidence = evidence_ref(
                    domain="capital",
                    record_type=layer,
                    record_key=f"{row.get('plan_year')}:{project_code or previous_code}",
                    row=row,
                    label=row.get("project_name"),
                    extra={"plan_year": row.get("plan_year"), "current_project_code": project_code},
                )
                add_identifier_link(
                    identifier_links,
                    identifier_type="capital_project_account",
                    identifier_value=previous_code,
                    raw_identifier=text(row.get("previous_code")),
                    evidence=evidence,
                    match_method="exact_structured_previous_identifier",
                    source_field="previous_code",
                )

    # Current capital adjustments — exact project code already parsed from the approved report.
    for index, row in enumerate(adjustments):
        project_code = upper(row.get("project_code"))
        if not project_code:
            continue
        record_key = f"adjustment:{project_code}:{row.get('adjustment_type')}:{row.get('source_page')}:{index}"
        evidence = evidence_ref(
            domain="capital",
            record_type="approved_capital_budget_adjustment",
            record_key=record_key,
            row=row,
            label=row.get("project_name"),
            extra={"adjustment_type": row.get("adjustment_type")},
        )
        add_identifier_link(
            identifier_links,
            identifier_type="capital_project_account",
            identifier_value=project_code,
            raw_identifier=text(row.get("project_code")),
            evidence=evidence,
            match_method="exact_parser_extracted_identifier",
            source_field="project_code",
        )

    # Public tender awards — exact tender/solicitation identifier.
    for index, row in enumerate(public_awards):
        raw = row.get("solicitation") or row.get("award_id")
        canonical = canonical_procurement_ref(raw)
        if not canonical:
            continue
        record_key = f"public-award:{stable_hash(row.get('award_id'), row.get('vendor_name'), row.get('awarded_date'), index)}"
        evidence = evidence_ref(
            domain="procurement",
            record_type="public_tender_award",
            record_key=record_key,
            row=row,
            label=row.get("description"),
            extra={"vendor_name": row.get("vendor_name"), "awarded_date": row.get("awarded_date")},
        )
        add_identifier_link(
            identifier_links,
            identifier_type="procurement_reference",
            identifier_value=canonical,
            raw_identifier=text(raw),
            evidence=evidence,
            match_method="exact_procurement_identifier_format_normalization",
            source_field="solicitation",
        )

    # Quarterly HRM awards — solicitation/project number plus structured internal project reference.
    for row in quarterly_awards:
        record_key = (
            f"quarterly-award:doc{row.get('report_document_id')}:p{row.get('source_page')}:"
            f"t{row.get('source_table')}:r{row.get('source_row')}"
        )
        evidence = evidence_ref(
            domain="procurement",
            record_type="quarterly_alternative_procurement_award",
            record_key=record_key,
            row=row,
            label=row.get("award_title"),
            extra={
                "vendor_name": row.get("vendor_display_name") or row.get("vendor_name"),
                "report_document_id": row.get("report_document_id"),
                "report_meeting_id": row.get("report_meeting_id"),
            },
        )
        refs = procurement_refs([row.get("solicitation"), row.get("project_number")])
        for canonical, raw in refs:
            add_identifier_link(
                identifier_links,
                identifier_type="procurement_reference",
                identifier_value=canonical,
                raw_identifier=raw,
                evidence=evidence,
                match_method="exact_procurement_identifier_format_normalization",
                source_field="solicitation/project_number",
            )
        for capital_id in exact_known_tokens(row.get("account_project_codes"), known_capital_ids):
            add_identifier_link(
                identifier_links,
                identifier_type="capital_project_account",
                identifier_value=capital_id,
                raw_identifier=capital_id,
                evidence=evidence,
                match_method="exact_known_identifier_in_structured_reference_field",
                source_field="account_project_codes",
            )

    # CAO amendment observations — parser-extracted PO and procurement/contract references only.
    for row in amendments:
        evidence = evidence_ref(
            domain="amendment",
            record_type="cao_contract_amendment_observation",
            record_key=text(row.get("id")),
            row=row,
            label=row.get("name_source"),
            extra={"report_date": row.get("report_date"), "contract_key": row.get("contract_key")},
        )
        for canonical, raw in procurement_refs(row.get("procurement_refs") or []):
            add_identifier_link(
                identifier_links,
                identifier_type="procurement_reference",
                identifier_value=canonical,
                raw_identifier=raw,
                evidence=evidence,
                match_method="exact_parser_extracted_identifier_format_normalization",
                source_field="procurement_refs",
            )
        po = text(row.get("po"))
        if po:
            add_identifier_link(
                identifier_links,
                identifier_type="purchase_order",
                identifier_value=po,
                raw_identifier=po,
                evidence=evidence,
                match_method="exact_parser_extracted_identifier",
                source_field="po",
            )

    # Council decisions — source parser already extracts explicit procurement/capital references.
    for row in decisions:
        evidence = evidence_ref(
            domain="council",
            record_type="approved_council_decision",
            record_key=text(row.get("decision_id")),
            row=row,
            label=row.get("item_title"),
            extra={
                "meeting_id": row.get("meeting_id"),
                "meeting_date": row.get("meeting_date"),
                "item_ref": row.get("item_ref"),
                "decision_status": row.get("decision_status"),
            },
        )
        for canonical, raw in procurement_refs(row.get("procurement_refs") or []):
            add_identifier_link(
                identifier_links,
                identifier_type="procurement_reference",
                identifier_value=canonical,
                raw_identifier=raw,
                evidence=evidence,
                match_method="exact_parser_extracted_identifier_format_normalization",
                source_field="procurement_refs",
            )
        for capital_id in (upper(value) for value in (row.get("capital_account_refs") or [])):
            if capital_id and capital_id in known_capital_ids:
                add_identifier_link(
                    identifier_links,
                    identifier_type="capital_project_account",
                    identifier_value=capital_id,
                    raw_identifier=capital_id,
                    evidence=evidence,
                    match_method="exact_parser_extracted_identifier_intersection",
                    source_field="capital_account_refs",
                )

    # Exact document provenance: quarterly award row -> checked Council document.
    documents_by_id = {text(row.get("document_id")): row for row in documents if text(row.get("document_id"))}
    quarterly_evidence_by_locator: dict[str, dict[str, Any]] = {}
    for link in identifier_links:
        evidence = link["evidence"]
        if evidence["record_type"] == "quarterly_alternative_procurement_award":
            quarterly_evidence_by_locator[evidence["record_key"]] = evidence
    for row in quarterly_awards:
        doc_id = text(row.get("report_document_id"))
        document = documents_by_id.get(doc_id)
        if not document:
            continue
        record_key = (
            f"quarterly-award:doc{row.get('report_document_id')}:p{row.get('source_page')}:"
            f"t{row.get('source_table')}:r{row.get('source_row')}"
        )
        left = quarterly_evidence_by_locator.get(record_key) or evidence_ref(
            domain="procurement", record_type="quarterly_alternative_procurement_award", record_key=record_key,
            row=row, label=row.get("award_title")
        )
        right = evidence_ref(
            domain="council_document",
            record_type="council_document",
            record_key=f"document:{doc_id}",
            row=document,
            label=document.get("title"),
            source_id=document.get("source_id"),
            locator=f"document_id={doc_id}",
            url=document.get("url"),
            extra={"meeting_id": document.get("meeting_id")},
        )
        add_direct_link(
            direct_links,
            link_type="award_report_document_provenance",
            left=left,
            right=right,
            match_method="exact_document_id",
            key_type="document_id",
            key_value=doc_id,
            interpretation="The award row is parsed from this exact checked Council document. This link is provenance, not a claim that Council separately approved the award.",
        )

    # Exact Council approval for Build 010 capital-adjustment report: meeting + item reference.
    adjustment_decision = inputs["current_capital"].get("decision") or {}
    meeting_id = text(adjustment_decision.get("meeting_id"))
    if meeting_id:
        candidates = [
            row for row in decisions
            if text(row.get("meeting_id")) == meeting_id
            and text(row.get("item_ref")) == "15.2.1"
            and "capital budget adjustments" in text(row.get("item_title")).lower()
        ]
        if len(candidates) > 1:
            raise RuntimeError(f"Build 019 expected at most one Council decision for capital adjustments; found {len(candidates)}")
        if len(candidates) == 1:
            decision_row = candidates[0]
            right = evidence_ref(
                domain="council",
                record_type="approved_council_decision",
                record_key=text(decision_row.get("decision_id")),
                row=decision_row,
                label=decision_row.get("item_title"),
                extra={"meeting_id": meeting_id, "item_ref": decision_row.get("item_ref")},
            )
            for index, row in enumerate(adjustments):
                left = evidence_ref(
                    domain="capital",
                    record_type="approved_capital_budget_adjustment",
                    record_key=f"adjustment:{upper(row.get('project_code'))}:{row.get('adjustment_type')}:{row.get('source_page')}:{index}",
                    row=row,
                    label=row.get("project_name"),
                )
                add_direct_link(
                    direct_links,
                    link_type="capital_adjustment_council_approval",
                    left=left,
                    right=right,
                    match_method="exact_meeting_id_and_item_ref",
                    key_type="meeting_item",
                    key_value=f"{meeting_id}:15.2.1",
                    interpretation="The capital-adjustment artifact explicitly identifies this Council decision as its approval evidence.",
                )

    # De-duplicate links by their deterministic IDs and reject collisions with different payloads.
    unique_identifier_links: dict[str, dict[str, Any]] = {}
    for link in identifier_links:
        existing = unique_identifier_links.get(link["link_id"])
        if existing and existing != link:
            raise RuntimeError(f"Identifier-link hash collision: {link['link_id']}")
        unique_identifier_links[link["link_id"]] = link
    identifier_links = sorted(unique_identifier_links.values(), key=lambda row: (row["identifier_type"], row["identifier_value"], row["evidence"]["domain"], row["evidence"]["record_key"], row["link_id"]))

    unique_direct_links: dict[str, dict[str, Any]] = {}
    for link in direct_links:
        existing = unique_direct_links.get(link["link_id"])
        if existing and existing != link:
            raise RuntimeError(f"Direct-link hash collision: {link['link_id']}")
        unique_direct_links[link["link_id"]] = link
    direct_links = sorted(unique_direct_links.values(), key=lambda row: (row["link_type"], row["key_value"], row["left"]["record_key"], row["link_id"]))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for link in identifier_links:
        grouped[(link["identifier_type"], link["identifier_value"])].append(link)

    reconciled_chains = []
    for (identifier_type, identifier_value), links in sorted(grouped.items()):
        domains = sorted({link["evidence"]["domain"] for link in links})
        record_types = sorted({link["evidence"]["record_type"] for link in links})
        if len(domains) < 2:
            continue
        reconciled_chains.append({
            "chain_id": f"b19-chain-{stable_hash(identifier_type, identifier_value)}",
            "identifier_type": identifier_type,
            "identifier_value": identifier_value,
            "domains": domains,
            "domain_count": len(domains),
            "record_types": record_types,
            "evidence_link_ids": [link["link_id"] for link in links],
            "evidence_record_count": len({(link["evidence"]["domain"], link["evidence"]["record_type"], link["evidence"]["record_key"]) for link in links}),
            "authoritative": True,
            "join_rule": "same explicit identifier only",
        })

    chain_distribution = defaultdict(int)
    for chain in reconciled_chains:
        chain_distribution[str(chain["domain_count"])] += 1

    linked_capital_ids = {
        chain["identifier_value"] for chain in reconciled_chains
        if chain["identifier_type"] == "capital_project_account"
    }
    linked_procurement_refs = {
        chain["identifier_value"] for chain in reconciled_chains
        if chain["identifier_type"] == "procurement_reference"
    }

    source_snapshot = {}
    for name, payload in inputs.items():
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        source_snapshot[name] = {
            "path": str(PATHS[name].relative_to(ROOT)),
            "parser_version": meta.get("parser_version"),
            "generated_at": meta.get("generated_at"),
            "dataset_status": meta.get("dataset_status"),
        }

    return {
        "metadata": {
            "dataset_status": "deterministic_cross_domain_lifecycle_reconciliation",
            "parser_version": PARSER_VERSION,
            "build": "019",
            "baseline_sha": "93fd8b769a48271b5f1f12782a3fa4a25a1d38d9",
            "match_policy": "Authoritative links require exact structured identifiers, parser-extracted identifiers, exact identifier intersection in a structured reference field, or direct document/meeting identifiers. Fuzzy names and dollar-only matches are forbidden.",
            "uses_fuzzy_name_matching": False,
            "uses_dollar_value_matching": False,
            "is_accounts_payable_ledger": False,
            "has_vendor_payment_facts": False,
            "operating_budget_to_procurement_status": "not_linked_without_shared_deterministic_identifier",
            "source_snapshot": source_snapshot,
        },
        "summary": {
            "capital_schedule_ids": len(schedule_ids),
            "known_capital_ids_all_layers": len(known_capital_ids),
            "identifier_links": len(identifier_links),
            "direct_documentary_links": len(direct_links),
            "reconciled_chain_count": len(reconciled_chains),
            "capital_identifier_chains": sum(1 for row in reconciled_chains if row["identifier_type"] == "capital_project_account"),
            "procurement_identifier_chains": sum(1 for row in reconciled_chains if row["identifier_type"] == "procurement_reference"),
            "purchase_order_chains": sum(1 for row in reconciled_chains if row["identifier_type"] == "purchase_order"),
            "chain_domain_count_distribution": dict(sorted(chain_distribution.items(), key=lambda item: int(item[0]))),
            "linked_build018_capital_ids": len(schedule_ids & linked_capital_ids),
            "linked_procurement_refs": len(linked_procurement_refs),
        },
        "reconciled_chains": reconciled_chains,
        "identifier_links": identifier_links,
        "direct_links": direct_links,
        "unresolved_boundaries": [
            "Current 2026/27 operating-budget service-area rows do not expose a shared project/solicitation identifier sufficient for deterministic award linkage.",
            "The public procurement sources are award evidence, not AP/vendor-payment evidence.",
            "CAO amendment reports are a public aggregate reporting series and may exclude Private & Confidential records.",
            "A shared vendor name or equal dollar value is never sufficient to create an authoritative Build 019 edge.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": payload["metadata"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
