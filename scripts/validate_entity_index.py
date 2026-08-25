#!/usr/bin/env python3
"""Validate the normalized HalifaxData cross-domain entity/join index."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from build_entity_index import INPUTS, ROOT, lexical_key, record_ref, sha256_file

INDEX = ROOT / "data/generated/entity_index.json"
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def duplicate_values(rows: list[dict], field: str) -> list[str]:
    counts = Counter(str(row.get(field) or "") for row in rows)
    return [value for value, count in counts.items() if value and count > 1]


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Could not load {path.relative_to(ROOT)}: {type(exc).__name__}: {exc}") from exc


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"Normalized entity index is missing: {INDEX.relative_to(ROOT)}")

    index = load_json(INDEX)
    metadata = index.get("metadata") or {}
    if metadata.get("schema_version") != "1.0.0":
        fail(f"entity index: unexpected schema_version {metadata.get('schema_version')!r}")
    policy = metadata.get("join_policy") or {}
    if policy.get("fuzzy_matching") is not False:
        fail("entity index: fuzzy_matching must be explicitly false")

    organizations = index.get("organizations") or []
    business_units = index.get("business_units") or []
    people = index.get("person_name_clusters") or []
    vendors = index.get("vendor_name_clusters") or []
    projects = index.get("capital_projects") or []
    unmatched = index.get("unmatched_business_unit_labels") or []
    links = index.get("record_links") or []

    dimensions = [
        (organizations, "organization_id"),
        (business_units, "business_unit_id"),
        (people, "person_name_cluster_id"),
        (vendors, "vendor_name_cluster_id"),
        (projects, "capital_project_id"),
    ]
    for rows, field in dimensions:
        duplicates = duplicate_values(rows, field)
        if duplicates:
            fail(f"entity index: duplicate {field} values: {duplicates[:10]}")
        if any(not row.get(field) for row in rows):
            fail(f"entity index: {field} contains blank values")

    org_ids = {row["organization_id"] for row in organizations if row.get("organization_id")}
    bu_ids = {row["business_unit_id"] for row in business_units if row.get("business_unit_id")}
    person_ids = {row["person_name_cluster_id"] for row in people if row.get("person_name_cluster_id")}
    vendor_ids = {row["vendor_name_cluster_id"] for row in vendors if row.get("vendor_name_cluster_id")}
    project_ids = {row["capital_project_id"] for row in projects if row.get("capital_project_id")}

    for row in business_units:
        if row.get("anchor_dataset") != "budget" or row.get("identity_method") != "budget_book_anchor":
            fail(f"business unit {row.get('business_unit_id')}: invalid anchor metadata")
        if row.get("join_key") != lexical_key(row.get("name")):
            fail(f"business unit {row.get('business_unit_id')}: join_key does not match canonical name")

    for row in organizations:
        if row.get("identity_method") != "explicit_exact_alias":
            fail(f"organization {row.get('organization_id')}: identity_method is not explicit_exact_alias")
        aliases = row.get("approved_aliases") or []
        if not aliases:
            fail(f"organization {row.get('organization_id')}: no approved aliases")

    for row in people:
        if row.get("identity_status") != "provisional_name_key_only":
            fail(f"person cluster {row.get('person_name_cluster_id')}: identity must remain provisional_name_key_only")
        if not row.get("person_key"):
            fail(f"person cluster {row.get('person_name_cluster_id')}: missing person_key")

    for row in vendors:
        if row.get("identity_status") != "provisional_name_key_only":
            fail(f"vendor cluster {row.get('vendor_name_cluster_id')}: identity must remain provisional_name_key_only")
        if not row.get("join_key"):
            fail(f"vendor cluster {row.get('vendor_name_cluster_id')}: missing lexical join_key")

    for row in projects:
        method = row.get("identity_method")
        if method not in {"official_project_code_exact", "source_objectid_only"}:
            fail(f"capital project {row.get('capital_project_id')}: unsupported identity_method {method!r}")
        if method == "official_project_code_exact":
            codes = row.get("project_codes") or []
            if not codes:
                fail(f"capital project {row.get('capital_project_id')}: exact-code cluster has no project code")
            elif any(lexical_key(code) != row.get("join_key") for code in codes):
                fail(f"capital project {row.get('capital_project_id')}: project-code lexical collision")
        if method == "source_objectid_only" and len(row.get("source_object_ids") or []) != 1:
            fail(f"capital project {row.get('capital_project_id')}: OBJECTID fallback must remain isolated")

    inputs: dict[str, dict] = {}
    recorded_inputs = metadata.get("input_artifacts") or {}
    for dataset, path in INPUTS.items():
        if not path.exists():
            fail(f"entity index input missing: {path.relative_to(ROOT)}")
            continue
        payload = load_json(path)
        inputs[dataset] = payload
        info = recorded_inputs.get(dataset) or {}
        expected_path = str(path.relative_to(ROOT))
        if info.get("path") != expected_path:
            fail(f"entity index input {dataset}: recorded path {info.get('path')!r} != {expected_path!r}")
        actual_hash = sha256_file(path)
        if info.get("sha256") != actual_hash:
            fail(f"entity index input {dataset}: SHA-256 mismatch; normalized artifact is stale")
        actual_records = len(payload.get("records") or [])
        if info.get("records") != actual_records:
            fail(f"entity index input {dataset}: recorded count {info.get('records')} != {actual_records}")

    known_datasets = set(INPUTS)
    link_by_ref: dict[tuple[str, str], dict] = {}
    for i, link in enumerate(links):
        dataset = link.get("source_dataset")
        ref = link.get("source_record_ref")
        if dataset not in known_datasets:
            fail(f"record link {i}: unknown source_dataset {dataset!r}")
        if not ref:
            fail(f"record link {i}: missing source_record_ref")
            continue
        key = (dataset, ref)
        if key in link_by_ref:
            fail(f"record link {i}: duplicate source reference {key}")
        link_by_ref[key] = link

        methods = link.get("join_methods")
        if not isinstance(methods, dict) or not methods:
            fail(f"record link {i}: missing join_methods")
        else:
            method_text = " ".join(str(value).lower() for value in methods.values())
            if "fuzzy" in method_text or "heuristic" in method_text:
                fail(f"record link {i}: prohibited fuzzy/heuristic join method {methods!r}")

        if link.get("organization_id") and link["organization_id"] not in org_ids:
            fail(f"record link {i}: unknown organization_id {link['organization_id']!r}")
        if link.get("business_unit_id") and link["business_unit_id"] not in bu_ids:
            fail(f"record link {i}: unknown business_unit_id {link['business_unit_id']!r}")
        if link.get("person_name_cluster_id") and link["person_name_cluster_id"] not in person_ids:
            fail(f"record link {i}: unknown person_name_cluster_id {link['person_name_cluster_id']!r}")
        if link.get("vendor_name_cluster_id") and link["vendor_name_cluster_id"] not in vendor_ids:
            fail(f"record link {i}: unknown vendor_name_cluster_id {link['vendor_name_cluster_id']!r}")
        if link.get("capital_project_id") and link["capital_project_id"] not in project_ids:
            fail(f"record link {i}: unknown capital_project_id {link['capital_project_id']!r}")

    budget_rows = (inputs.get("budget") or {}).get("records") or []
    budget_service = 0
    budget_audited = 0
    for i, row in enumerate(budget_rows):
        ref = record_ref("budget", row, i)
        link = link_by_ref.get(("budget", ref))
        if row.get("record_type") == "service_area_budget":
            budget_service += 1
            if not link or not link.get("business_unit_id"):
                fail(f"budget service row {i}: missing required operational business-unit link")
        elif row.get("record_type") == "audited_psas":
            budget_audited += 1
            if link and link.get("business_unit_id"):
                fail(f"budget audited PSAS row {i}: prohibited operational business-unit link")

    comp_rows = (inputs.get("compensation") or {}).get("records") or []
    for i, row in enumerate(comp_rows):
        if not row.get("person_key"):
            continue
        ref = record_ref("compensation", row, i)
        link = link_by_ref.get(("compensation", ref))
        if not link or not link.get("person_name_cluster_id"):
            fail(f"compensation row {i}: person_key is present but provisional person-name cluster link is missing")

    procurement_rows = (inputs.get("procurement") or {}).get("records") or []
    for i, row in enumerate(procurement_rows):
        if not str(row.get("vendor_name") or "").strip():
            continue
        ref = record_ref("procurement", row, i)
        link = link_by_ref.get(("procurement", ref))
        if not link or not link.get("vendor_name_cluster_id"):
            fail(f"procurement row {i}: vendor name is present but provisional vendor-name cluster link is missing")

    capital_rows = (inputs.get("capital") or {}).get("records") or []
    for i, row in enumerate(capital_rows):
        ref = record_ref("capital", row, i)
        link = link_by_ref.get(("capital", ref))
        if not link or not link.get("capital_project_id"):
            fail(f"capital row {i}: missing project identity link")

    spending_rows = (inputs.get("spending") or {}).get("records") or []
    for i, row in enumerate(spending_rows):
        ref = record_ref("spending", row, i)
        link = link_by_ref.get(("spending", ref))
        if not link or link.get("organization_id") != "org:halifax-regional-municipality":
            fail(f"spending row {i}: missing official HRM source-scope organization link")

    count_checks = {
        "record_link_count": len(links),
        "business_unit_count": len(business_units),
        "person_name_cluster_count": len(people),
        "vendor_name_cluster_count": len(vendors),
        "capital_project_cluster_count": len(projects),
        "budget_operational_rows_linked": budget_service,
        "budget_audited_rows_intentionally_not_business_unit_linked": budget_audited,
        "unmatched_business_unit_label_count": len(unmatched),
        "unmatched_business_unit_record_count": sum(int(row.get("record_count") or 0) for row in unmatched),
    }
    for field, actual in count_checks.items():
        if metadata.get(field) != actual:
            fail(f"entity index metadata {field} {metadata.get(field)!r} != actual {actual}")

    if errors:
        print("ENTITY INDEX VALIDATION FAILED", file=sys.stderr)
        print("\n".join(errors[:100]), file=sys.stderr)
        raise SystemExit(1)

    print(
        "validated normalized entity index: "
        f"{len(links)} links; {len(business_units)} business units; "
        f"{len(people)} provisional person-name clusters; "
        f"{len(vendors)} provisional vendor-name clusters; "
        f"{len(projects)} capital project clusters; "
        f"{len(unmatched)} unmatched business-unit labels"
    )


if __name__ == "__main__":
    main()
