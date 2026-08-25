#!/usr/bin/env python3
"""Build conservative cross-domain joins without fuzzy identity assumptions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data/generated"
DEFAULT_OUT = GENERATED / "entity_index.json"
NORMALIZATION_VERSION = "build005-entity-index-v2"
INPUTS = {
    "budget": GENERATED / "budget.json",
    "compensation": GENERATED / "compensation.json",
    "procurement": GENERATED / "procurement.json",
    "capital": GENERATED / "capital.json",
    "spending": GENERATED / "spending.json",
}
ORGANIZATION_ALIASES = {
    "org:halifax-regional-municipality": {
        "name": "Halifax Regional Municipality",
        "aliases": ["Halifax Regional Municipality"],
    },
    "org:halifax-water": {"name": "Halifax Water", "aliases": ["Halifax Water"]},
    "org:halifax-public-libraries": {
        "name": "Halifax Public Libraries",
        "aliases": ["Halifax Public Libraries"],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def lexical_key(value: Any) -> str:
    """Normalize case/spacing/punctuation only; never perform fuzzy matching."""
    text = unicodedata.normalize("NFKC", str(value or "").strip()).casefold()
    text = text.replace("&", " and ")
    chars = [ch if ch.isalnum() else " " for ch in text]
    return " ".join("".join(chars).split())


def stable_digest(parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def slug(value: Any) -> str:
    key = lexical_key(value)
    ascii_key = unicodedata.normalize("NFKD", key)
    ascii_key = "".join(ch for ch in ascii_key if (ch.isascii() and ch.isalnum()) or ch == " ")
    return "-".join(ascii_key.split()) or stable_digest(key or "unknown")[:12]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def record_ref(dataset: str, row: dict, index: int) -> str:
    if row.get("record_id"):
        return f"{dataset}:{row['record_id']}"
    if dataset == "compensation":
        identity = [row.get("fiscal_year_end"), row.get("entity"), row.get("person_key"), row.get("total"), row.get("source_id")]
    elif dataset == "budget":
        identity = [row.get("record_type"), row.get("fiscal_year"), row.get("business_unit"), row.get("service_area"), row.get("statement_section"), row.get("category"), row.get("source_id")]
    elif dataset == "procurement":
        identity = [row.get("award_id"), row.get("vendor_name"), row.get("awarded_date"), row.get("current_contract_value"), row.get("source_id")]
    elif dataset == "capital":
        identity = [row.get("project_id"), row.get("project_code"), row.get("fiscal_year"), row.get("source_id")]
    elif dataset == "spending":
        prov = row.get("provenance") or {}
        identity = [row.get("source_id"), prov.get("locator_value"), row.get("posting_date"), row.get("business_unit"), row.get("account"), row.get("amount")]
    else:
        identity = [index, row]
    return f"{dataset}:{stable_digest(identity)}"


def load_inputs() -> dict[str, dict]:
    missing = [str(path.relative_to(ROOT)) for path in INPUTS.values() if not path.exists()]
    if missing:
        raise RuntimeError(f"Required generated inputs are missing: {missing}")
    return {name: json.loads(path.read_text(encoding="utf-8")) for name, path in INPUTS.items()}


def input_generated_at(payload: dict) -> str | None:
    value = (payload.get("metadata") or {}).get("generated_at")
    return value if isinstance(value, str) and value else None


def build_organization_index() -> tuple[list[dict], dict[str, str]]:
    organizations = []
    aliases: dict[str, str] = {}
    for org_id, spec in ORGANIZATION_ALIASES.items():
        approved = sorted(set(spec["aliases"]))
        for alias in approved:
            key = lexical_key(alias)
            prior = aliases.get(key)
            if prior and prior != org_id:
                raise RuntimeError(f"Organization alias collision for {alias!r}: {prior} vs {org_id}")
            aliases[key] = org_id
        organizations.append({
            "organization_id": org_id,
            "name": spec["name"],
            "approved_aliases": approved,
            "identity_method": "explicit_exact_alias",
        })
    return sorted(organizations, key=lambda x: x["organization_id"]), aliases


def build_business_units(rows: list[dict]) -> tuple[list[dict], dict[str, str]]:
    labels_by_key: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("record_type") != "service_area_budget":
            continue
        label = str(row.get("business_unit") or "").strip()
        if label:
            labels_by_key[lexical_key(label)].add(label)
    output = []
    key_to_id = {}
    for key, labels in labels_by_key.items():
        if len(labels) != 1:
            raise RuntimeError(f"Budget business-unit lexical collision: {key!r} -> {sorted(labels)!r}")
        label = next(iter(labels))
        unit_id = f"business-unit:{slug(label)}"
        key_to_id[key] = unit_id
        output.append({
            "business_unit_id": unit_id,
            "name": label,
            "join_key": key,
            "anchor_dataset": "budget",
            "identity_method": "budget_book_anchor",
        })
    if not output:
        raise RuntimeError("No operational business units were found in budget.json")
    return sorted(output, key=lambda x: x["business_unit_id"]), key_to_id


def build_payload(inputs: dict[str, dict]) -> dict:
    budget_rows = inputs["budget"].get("records") or []
    comp_rows = inputs["compensation"].get("records") or []
    procurement_rows = inputs["procurement"].get("records") or []
    capital_rows = inputs["capital"].get("records") or []
    spending_rows = inputs["spending"].get("records") or []

    organizations, org_alias_to_id = build_organization_index()
    business_units, bu_key_to_id = build_business_units(budget_rows)
    links: list[dict] = []
    bu_source_counts: dict[str, Counter] = defaultdict(Counter)
    org_source_counts: dict[str, Counter] = defaultdict(Counter)
    unmatched_bus: Counter = Counter()
    unmatched_sources: dict[str, Counter] = defaultdict(Counter)
    people: dict[str, dict] = {}
    vendors: dict[str, dict] = {}
    projects: dict[str, dict] = {}

    def match_org(raw: Any) -> str | None:
        key = lexical_key(raw)
        return org_alias_to_id.get(key) if key else None

    def match_bu(raw: Any) -> str | None:
        key = lexical_key(raw)
        return bu_key_to_id.get(key) if key else None

    def observe_bu(dataset: str, raw: Any, unit_id: str | None) -> None:
        label = str(raw or "").strip()
        if not label:
            return
        if unit_id:
            bu_source_counts[unit_id][dataset] += 1
        else:
            unmatched_bus[label] += 1
            unmatched_sources[label][dataset] += 1

    for i, row in enumerate(budget_rows):
        if row.get("record_type") != "service_area_budget":
            continue
        unit_id = match_bu(row.get("business_unit"))
        if not unit_id:
            raise RuntimeError(f"Budget anchor failed to match itself: {row.get('business_unit')!r}")
        bu_source_counts[unit_id]["budget"] += 1
        links.append({
            "source_dataset": "budget",
            "source_record_ref": record_ref("budget", row, i),
            "business_unit_id": unit_id,
            "join_methods": {"business_unit": "budget_book_anchor"},
        })

    for i, row in enumerate(comp_rows):
        link = {"source_dataset": "compensation", "source_record_ref": record_ref("compensation", row, i), "join_methods": {}}
        org_id = match_org(row.get("entity"))
        if org_id:
            link["organization_id"] = org_id
            link["join_methods"]["organization"] = "explicit_exact_alias"
            org_source_counts[org_id]["compensation"] += 1
        unit_id = match_bu(row.get("business_unit"))
        observe_bu("compensation", row.get("business_unit"), unit_id)
        if unit_id:
            link["business_unit_id"] = unit_id
            link["join_methods"]["business_unit"] = "lexical_exact_to_budget_anchor"
        person_key = str(row.get("person_key") or "").strip()
        if person_key:
            if not org_id:
                raise RuntimeError(
                    f"Compensation row {i} has person_key {person_key!r} but no exact recognized reporting entity"
                )
            cluster_id = f"person-entity:{stable_digest([org_id, person_key])[:16]}"
            cluster = people.setdefault(cluster_id, {
                "person_name_cluster_id": cluster_id,
                "organization_id": org_id,
                "person_key": person_key,
                "observed_names": set(),
                "fiscal_year_ends": set(),
                "record_count": 0,
                "identity_status": "entity_scoped_person_key",
            })
            if cluster["organization_id"] != org_id or cluster["person_key"] != person_key:
                raise RuntimeError(f"Compensation identity collision for {cluster_id}")
            name = str(row.get("name") or "").strip()
            if name:
                cluster["observed_names"].add(name)
            if row.get("fiscal_year_end") is not None:
                cluster["fiscal_year_ends"].add(row.get("fiscal_year_end"))
            cluster["record_count"] += 1
            link["person_name_cluster_id"] = cluster_id
            link["join_methods"]["person_name_cluster"] = "entity_scoped_person_key"
        if link["join_methods"]:
            links.append(link)

    for i, row in enumerate(procurement_rows):
        link = {"source_dataset": "procurement", "source_record_ref": record_ref("procurement", row, i), "join_methods": {}}
        org_id = match_org(row.get("entity"))
        if org_id:
            link["organization_id"] = org_id
            link["join_methods"]["organization"] = "explicit_exact_alias"
            org_source_counts[org_id]["procurement"] += 1
        vendor_name = str(row.get("vendor_name") or "").strip()
        vendor_key = lexical_key(vendor_name)
        if vendor_key:
            cluster_id = f"vendor-name:{stable_digest(vendor_key)[:16]}"
            cluster = vendors.setdefault(cluster_id, {
                "vendor_name_cluster_id": cluster_id,
                "join_key": vendor_key,
                "observed_names": set(),
                "award_count": 0,
                "known_award_value": 0.0,
                "identity_status": "provisional_name_key_only",
            })
            cluster["observed_names"].add(vendor_name)
            cluster["award_count"] += 1
            amount = row.get("current_contract_value")
            if isinstance(amount, (int, float)):
                cluster["known_award_value"] += amount
            link["vendor_name_cluster_id"] = cluster_id
            link["join_methods"]["vendor_name_cluster"] = "lexical_exact_provisional"
        if link["join_methods"]:
            links.append(link)

    for i, row in enumerate(capital_rows):
        code = str(row.get("project_code") or "").strip()
        object_id = str(row.get("project_id") or "").strip()
        if code:
            project_key = lexical_key(code)
            cluster_id = f"capital-project:{slug(code)}"
            method = "official_project_code_exact"
        elif object_id:
            project_key = f"objectid {object_id}"
            cluster_id = f"capital-object:{slug(object_id)}"
            method = "source_objectid_only"
        else:
            raise RuntimeError(f"Capital row {i} has neither project_code nor project_id")
        cluster = projects.setdefault(cluster_id, {
            "capital_project_id": cluster_id,
            "join_key": project_key,
            "project_codes": set(),
            "project_names": set(),
            "source_object_ids": set(),
            "fiscal_years": set(),
            "record_count": 0,
            "identity_method": method,
        })
        if cluster["identity_method"] != method or cluster["join_key"] != project_key:
            raise RuntimeError(f"Capital identity collision for {cluster_id}")
        if code:
            cluster["project_codes"].add(code)
        if row.get("project_name"):
            cluster["project_names"].add(str(row["project_name"]).strip())
        if object_id:
            cluster["source_object_ids"].add(object_id)
        if row.get("fiscal_year") is not None:
            cluster["fiscal_years"].add(row.get("fiscal_year"))
        cluster["record_count"] += 1
        org_id = "org:halifax-regional-municipality"
        org_source_counts[org_id]["capital"] += 1
        links.append({
            "source_dataset": "capital",
            "source_record_ref": record_ref("capital", row, i),
            "organization_id": org_id,
            "capital_project_id": cluster_id,
            "join_methods": {"organization": "official_source_scope", "capital_project": method},
        })

    for i, row in enumerate(spending_rows):
        org_id = "org:halifax-regional-municipality"
        org_source_counts[org_id]["spending"] += 1
        link = {
            "source_dataset": "spending",
            "source_record_ref": record_ref("spending", row, i),
            "organization_id": org_id,
            "join_methods": {"organization": "official_source_scope"},
        }
        unit_id = match_bu(row.get("business_unit"))
        observe_bu("spending", row.get("business_unit"), unit_id)
        if unit_id:
            link["business_unit_id"] = unit_id
            link["join_methods"]["business_unit"] = "lexical_exact_to_budget_anchor"
        links.append(link)

    person_output = []
    for cluster in people.values():
        names = sorted(cluster.pop("observed_names"))
        years = sorted(cluster.pop("fiscal_year_ends"))
        cluster["observed_names"] = names
        cluster["first_fiscal_year_end"] = years[0] if years else None
        cluster["last_fiscal_year_end"] = years[-1] if years else None
        cluster["observed_name_variant_count"] = len(names)
        cluster["collision_review_recommended"] = len(names) > 1
        person_output.append(cluster)

    vendor_output = []
    for cluster in vendors.values():
        cluster["observed_names"] = sorted(cluster.pop("observed_names"))
        cluster["known_award_value"] = round(cluster["known_award_value"], 2)
        cluster["observed_name_variant_count"] = len(cluster["observed_names"])
        cluster["collision_review_recommended"] = len(cluster["observed_names"]) > 1
        vendor_output.append(cluster)

    project_output = []
    for cluster in projects.values():
        for field in ("project_codes", "project_names", "source_object_ids", "fiscal_years"):
            cluster[field] = sorted(cluster[field], key=lambda x: str(x))
        project_output.append(cluster)

    business_unit_output = [{**unit, "record_counts_by_dataset": dict(sorted(bu_source_counts[unit["business_unit_id"]].items()))} for unit in business_units]
    organization_output = [{**org, "record_counts_by_dataset": dict(sorted(org_source_counts[org["organization_id"]].items()))} for org in organizations]
    unmatched_output = [{
        "source_label": label,
        "record_count": count,
        "datasets": dict(sorted(unmatched_sources[label].items())),
        "status": "unmapped_no_exact_budget_anchor",
    } for label, count in unmatched_bus.most_common()]

    input_hashes = {
        name: {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "records": len(inputs[name].get("records") or []),
            "generated_at": input_generated_at(inputs[name]),
        }
        for name, path in INPUTS.items()
    }
    input_times = [item["generated_at"] for item in input_hashes.values() if item["generated_at"]]
    links.sort(key=lambda x: (x["source_dataset"], x["source_record_ref"]))
    person_output.sort(key=lambda x: x["person_name_cluster_id"])
    vendor_output.sort(key=lambda x: x["vendor_name_cluster_id"])
    project_output.sort(key=lambda x: x["capital_project_id"])
    service_count = sum(row.get("record_type") == "service_area_budget" for row in budget_rows)
    audited_count = sum(row.get("record_type") == "audited_psas" for row in budget_rows)

    return {
        "metadata": {
            "schema_version": "1.0.0",
            "normalization_version": NORMALIZATION_VERSION,
            "generated_at": max(input_times) if input_times else None,
            "generation_time_semantics": "freshest_input_generated_at_for_deterministic_build",
            "input_artifacts": input_hashes,
            "join_policy": {
                "fuzzy_matching": False,
                "business_unit_anchor": "current budget-book operational business units",
                "business_unit_match": "lexical exact only",
                "organization_match": "explicit approved alias exact only or official source scope",
                "person_identity": "reporting organization + existing person_key; no cross-entity merge",
                "vendor_identity": "provisional lexical name cluster; not guaranteed legal entity",
                "capital_identity": "official project code exact; OBJECTID fallback stays isolated",
            },
            "forbidden_joins": [
                "audited_psas_category_to_operational_business_unit",
                "cross_entity_person_key",
                "fuzzy_name_to_business_unit",
                "fuzzy_vendor_identity",
                "project_name_only_to_capital_project",
            ],
            "source_record_counts": {name: info["records"] for name, info in input_hashes.items()},
            "record_link_count": len(links),
            "business_unit_count": len(business_unit_output),
            "person_name_cluster_count": len(person_output),
            "vendor_name_cluster_count": len(vendor_output),
            "capital_project_cluster_count": len(project_output),
            "budget_operational_rows_linked": service_count,
            "budget_audited_rows_intentionally_not_business_unit_linked": audited_count,
            "unmatched_business_unit_label_count": len(unmatched_output),
            "unmatched_business_unit_record_count": sum(item["record_count"] for item in unmatched_output),
        },
        "organizations": organization_output,
        "business_units": business_unit_output,
        "person_name_clusters": person_output,
        "vendor_name_clusters": vendor_output,
        "capital_projects": project_output,
        "unmatched_business_unit_labels": unmatched_output,
        "record_links": links,
    }


def serialize(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    args = parse_args()
    rendered = serialize(build_payload(load_inputs()))
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"Normalized artifact is missing: {args.output}")
        if args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"Normalized artifact is stale: regenerate with python {Path(__file__).name}")
        print(f"Normalized artifact is current: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(rendered, encoding="utf-8")
    tmp.replace(args.output)
    payload = json.loads(rendered)
    print(
        "Wrote normalized entity index: "
        f"{payload['metadata']['record_link_count']} record links, "
        f"{payload['metadata']['business_unit_count']} business units, "
        f"{payload['metadata']['person_name_cluster_count']} person-name clusters, "
        f"{payload['metadata']['vendor_name_cluster_count']} vendor-name clusters, "
        f"{payload['metadata']['capital_project_cluster_count']} capital project clusters"
    )


if __name__ == "__main__":
    main()
