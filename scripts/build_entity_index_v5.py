#!/usr/bin/env python3
"""Build HalifaxData entity index v5 with current capital intelligence.

Build 005 v4 remains the trusted base. Build 008 adds only two defensible joins:
- current Capital Plan project sheets -> HRM + exact official project_code
- quarterly capital category actuals -> HRM organization only

Category-level actuals are explicitly forbidden from inheriting project IDs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_entity_index as core
import build_entity_index_v4 as v4

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data/generated"
DEFAULT_OUT = GENERATED / "entity_index.json"
NORMALIZATION_VERSION = "build008-entity-index-v5"
HRM_ORG = "org:halifax-regional-municipality"
EXTRA_INPUTS = {
    "capital_current": GENERATED / "capital_current.json",
    "capital_actuals_current": GENERATED / "capital_actuals_current.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"Required Build 008 input is missing: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_info(path: Path, payload: dict) -> dict:
    metadata = payload.get("metadata") or {}
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": core.sha256_file(path),
        "records": len(payload.get("records") or []),
        "generated_at": metadata.get("generated_at"),
    }


def current_ref(row: dict) -> str:
    identity = [row.get("project_code"), row.get("source_page"), row.get("source_id")]
    return f"capital_current:{core.stable_digest(identity)}"


def actual_ref(row: dict) -> str:
    identity = [
        row.get("source_id"), row.get("quarter"), row.get("budget_category"),
        row.get("source_page"), row.get("source_table"), row.get("source_row"),
    ]
    return f"capital_actuals_current:{core.stable_digest(identity)}"


def build_payload() -> dict:
    payload = v4.build_payload()
    current = load_json(EXTRA_INPUTS["capital_current"])
    actuals = load_json(EXTRA_INPUTS["capital_actuals_current"])

    metadata = payload["metadata"]
    metadata["schema_version"] = "1.2.0"
    metadata["normalization_version"] = NORMALIZATION_VERSION
    metadata["approved_input_count"] = int(metadata.get("approved_input_count") or 0) + len(EXTRA_INPUTS)
    metadata["join_policy"]["current_capital_project_match"] = "official project_code exact only"
    metadata["join_policy"]["current_capital_actual_match"] = "HRM organization scope only; category summaries never inherit project IDs"
    metadata.setdefault("forbidden_joins", []).extend([
        "capital_asset_category_actual_to_capital_project",
        "capital_current_project_name_fuzzy_to_historical_project",
        "capital_current_project_name_only_to_capital_project",
    ])
    metadata["forbidden_joins"] = sorted(set(metadata["forbidden_joins"]))

    for name, path in EXTRA_INPUTS.items():
        source_payload = current if name == "capital_current" else actuals
        metadata["input_artifacts"][name] = artifact_info(path, source_payload)
    metadata["source_record_counts"] = {
        name: info["records"] for name, info in metadata["input_artifacts"].items()
    }
    times = [info.get("generated_at") for info in metadata["input_artifacts"].values() if info.get("generated_at")]
    metadata["generated_at"] = max(times) if times else metadata.get("generated_at")

    projects = {row["capital_project_id"]: row for row in payload["capital_projects"]}
    links = payload["record_links"]
    current_codes: set[str] = set()
    existing_historical_codes = {
        code
        for row in payload["capital_projects"]
        for code in (row.get("project_codes") or [])
        if code
    }
    current_exact_historical = 0
    current_only_clusters = 0

    for project in projects.values():
        project["historical_record_count"] = int(project.get("record_count") or 0)
        project["current_plan_record_count"] = 0
        project["current_plan_present"] = False
        project["current_plan_source_pages"] = []

    for row in current.get("records") or []:
        code = str(row.get("project_code") or "").strip()
        if not code:
            raise RuntimeError("Current capital row is missing project_code")
        if code in current_codes:
            raise RuntimeError(f"Duplicate current capital project_code {code!r}")
        current_codes.add(code)
        cluster_id = f"capital-project:{core.slug(code)}"
        project = projects.get(cluster_id)
        if project is None:
            current_only_clusters += 1
            project = {
                "capital_project_id": cluster_id,
                "join_key": core.lexical_key(code),
                "project_codes": [code],
                "project_names": [str(row.get("project_name") or "").strip()] if row.get("project_name") else [],
                "source_object_ids": [],
                "fiscal_years": [],
                "record_count": 0,
                "historical_record_count": 0,
                "current_plan_record_count": 0,
                "current_plan_present": False,
                "current_plan_source_pages": [],
                "identity_method": "official_project_code_exact",
            }
            projects[cluster_id] = project
        else:
            if core.lexical_key(code) != project.get("join_key"):
                raise RuntimeError(f"Current capital project code collision for {code!r}")
            if project.get("identity_method") != "official_project_code_exact":
                raise RuntimeError(f"Current capital code {code!r} collides with non-code project identity")
            if code not in (project.get("project_codes") or []):
                raise RuntimeError(f"Current project cluster {cluster_id} does not retain exact code {code!r}")
            current_exact_historical += int(code in existing_historical_codes)

        name = str(row.get("project_name") or "").strip()
        if name and name not in project["project_names"]:
            project["project_names"].append(name)
            project["project_names"].sort()
        project["current_plan_record_count"] += 1
        project["current_plan_present"] = True
        project["record_count"] = int(project.get("record_count") or 0) + 1
        project["current_plan_source_pages"].append(row.get("source_page"))
        project["current_plan_source_pages"] = sorted(set(project["current_plan_source_pages"]))

        links.append({
            "source_dataset": "capital_current",
            "source_record_ref": current_ref(row),
            "organization_id": HRM_ORG,
            "capital_project_id": cluster_id,
            "join_methods": {
                "organization": "official_source_scope",
                "capital_project": "official_project_code_exact",
            },
        })

    for row in actuals.get("records") or []:
        if row.get("granularity") != "capital_asset_category_summary":
            raise RuntimeError("Current capital actual row has unexpected granularity")
        links.append({
            "source_dataset": "capital_actuals_current",
            "source_record_ref": actual_ref(row),
            "organization_id": HRM_ORG,
            "join_methods": {"organization": "official_source_scope"},
        })

    # Update organization-level source counts for both Build 008 inputs.
    hrm = next((row for row in payload["organizations"] if row["organization_id"] == HRM_ORG), None)
    if hrm is None:
        raise RuntimeError("HRM organization dimension is missing")
    counts = dict(hrm.get("record_counts_by_dataset") or {})
    counts["capital_current"] = len(current.get("records") or [])
    counts["capital_actuals_current"] = len(actuals.get("records") or [])
    hrm["record_counts_by_dataset"] = dict(sorted(counts.items()))

    payload["capital_projects"] = sorted(projects.values(), key=lambda row: row["capital_project_id"])
    links.sort(key=lambda row: (row["source_dataset"], row["source_record_ref"]))

    metadata["record_link_count"] = len(links)
    metadata["capital_project_cluster_count"] = len(payload["capital_projects"])
    metadata["current_capital_rows_linked"] = len(current.get("records") or [])
    metadata["current_capital_exact_historical_code_matches"] = current_exact_historical
    metadata["current_capital_only_project_clusters"] = current_only_clusters
    metadata["current_capital_actual_rows_linked_to_hrm_only"] = len(actuals.get("records") or [])
    metadata["current_capital_actual_project_links"] = 0
    return payload


def main() -> None:
    args = parse_args()
    payload = build_payload()
    rendered = core.serialize(payload)
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"Normalized entity index missing: {args.output.relative_to(ROOT)}")
        if args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Normalized entity index is stale relative to approved Build 008 inputs")
        print(f"entity index v5 is current: {payload['metadata']['record_link_count']} links")
        return
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(rendered, encoding="utf-8")
    tmp.replace(args.output)
    metadata = payload["metadata"]
    print(
        f"Wrote entity index v5: links={metadata['record_link_count']}; projects={metadata['capital_project_cluster_count']}; "
        f"current={metadata['current_capital_rows_linked']}; exact_historical={metadata['current_capital_exact_historical_code_matches']}; "
        f"current_only={metadata['current_capital_only_project_clusters']}; actual_categories={metadata['current_capital_actual_rows_linked_to_hrm_only']}"
    )


if __name__ == "__main__":
    main()
