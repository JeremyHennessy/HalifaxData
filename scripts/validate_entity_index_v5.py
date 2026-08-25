#!/usr/bin/env python3
"""Independent semantic validation for Build 008 entity index v5."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data/generated"
INDEX = GENERATED / "entity_index.json"
CURRENT = GENERATED / "capital_current.json"
ACTUALS = GENERATED / "capital_actuals_current.json"
HISTORICAL = GENERATED / "capital.json"
HRM_ORG = "org:halifax-regional-municipality"


def fail(message: str) -> None:
    raise SystemExit(f"entity-index-v5 validation failed: {message}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def lexical_key(value) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKC", str(value or "").strip()).casefold().replace("&", " and ")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def slug(value) -> str:
    import unicodedata
    key = lexical_key(value)
    ascii_key = unicodedata.normalize("NFKD", key)
    ascii_key = "".join(ch for ch in ascii_key if (ch.isascii() and ch.isalnum()) or ch == " ")
    return "-".join(ascii_key.split())


def stable_digest(parts) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def current_ref(row: dict) -> str:
    return f"capital_current:{stable_digest([row.get('project_code'), row.get('source_page'), row.get('source_id')])}"


def actual_ref(row: dict) -> str:
    return f"capital_actuals_current:{stable_digest([row.get('source_id'), row.get('quarter'), row.get('budget_category'), row.get('source_page'), row.get('source_table'), row.get('source_row')])}"


def load(path: Path) -> dict:
    if not path.exists():
        fail(f"missing {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    index = load(INDEX)
    current = load(CURRENT)
    actuals = load(ACTUALS)
    historical = load(HISTORICAL)
    meta = index.get("metadata") or {}

    if meta.get("normalization_version") != "build008-entity-index-v5":
        fail("unexpected normalization version")
    forbidden = set(meta.get("forbidden_joins") or [])
    for required in {
        "capital_asset_category_actual_to_capital_project",
        "capital_current_project_name_fuzzy_to_historical_project",
        "project_name_only_to_capital_project",
    }:
        if required not in forbidden:
            fail(f"missing forbidden join {required}")

    input_artifacts = meta.get("input_artifacts") or {}
    for name, path in {"capital_current": CURRENT, "capital_actuals_current": ACTUALS}.items():
        info = input_artifacts.get(name) or {}
        if info.get("sha256") != sha256(path):
            fail(f"input hash mismatch for {name}")
        if info.get("records") != len(load(path).get("records") or []):
            fail(f"input record count mismatch for {name}")

    links = index.get("record_links") or []
    project_dimensions = {row.get("capital_project_id"): row for row in (index.get("capital_projects") or [])}
    if len(project_dimensions) != meta.get("capital_project_cluster_count"):
        fail("capital project dimension count mismatch")

    historical_codes = {
        str(row.get("project_code") or "").strip()
        for row in historical.get("records") or []
        if str(row.get("project_code") or "").strip()
    }
    current_rows = current.get("records") or []
    current_links = [row for row in links if row.get("source_dataset") == "capital_current"]
    if len(current_links) != len(current_rows) or len(current_links) != meta.get("current_capital_rows_linked"):
        fail("current-capital link count mismatch")
    current_links_by_ref = {row.get("source_record_ref"): row for row in current_links}
    if len(current_links_by_ref) != len(current_links):
        fail("duplicate current-capital source refs")

    exact_historical = 0
    current_only = 0
    current_ids = set()
    for row in current_rows:
        code = str(row.get("project_code") or "").strip()
        expected_id = f"capital-project:{slug(code)}"
        current_ids.add(expected_id)
        link = current_links_by_ref.get(current_ref(row))
        if not link:
            fail(f"missing exact current-capital link for {code}")
        if link.get("organization_id") != HRM_ORG:
            fail(f"current capital {code} not linked to HRM")
        if link.get("capital_project_id") != expected_id:
            fail(f"current capital {code} linked to wrong project dimension")
        methods = link.get("join_methods") or {}
        if methods.get("capital_project") != "official_project_code_exact":
            fail(f"current capital {code} not joined by official code exact")
        dimension = project_dimensions.get(expected_id)
        if not dimension:
            fail(f"missing project dimension for {code}")
        if code not in (dimension.get("project_codes") or []):
            fail(f"project dimension does not retain current code {code}")
        if dimension.get("current_plan_record_count") != 1 or dimension.get("current_plan_present") is not True:
            fail(f"current-plan dimension metadata wrong for {code}")
        if row.get("source_page") not in (dimension.get("current_plan_source_pages") or []):
            fail(f"current-plan source page missing from dimension for {code}")
        if code in historical_codes:
            exact_historical += 1
        else:
            current_only += 1
            if dimension.get("historical_record_count") != 0:
                fail(f"current-only project {code} incorrectly has historical records")

    if exact_historical != meta.get("current_capital_exact_historical_code_matches"):
        fail("exact historical code-match metadata mismatch")
    if current_only != meta.get("current_capital_only_project_clusters"):
        fail("current-only project metadata mismatch")
    if exact_historical + current_only != len(current_rows):
        fail("current project identity partition is incomplete")

    actual_rows = actuals.get("records") or []
    actual_links = [row for row in links if row.get("source_dataset") == "capital_actuals_current"]
    if len(actual_links) != len(actual_rows) or len(actual_links) != meta.get("current_capital_actual_rows_linked_to_hrm_only"):
        fail("capital-actual link count mismatch")
    actual_links_by_ref = {row.get("source_record_ref"): row for row in actual_links}
    if len(actual_links_by_ref) != len(actual_links):
        fail("duplicate capital-actual source refs")
    for row in actual_rows:
        link = actual_links_by_ref.get(actual_ref(row))
        if not link:
            fail(f"missing capital-actual link for {row.get('quarter')} / {row.get('budget_category')}")
        if link.get("organization_id") != HRM_ORG:
            fail("capital actual row not linked to HRM")
        if "capital_project_id" in link:
            fail("capital asset-category actual row illegally inherited a project ID")
        if (link.get("join_methods") or {}) != {"organization": "official_source_scope"}:
            fail("capital actual row has unexpected join method")

    if meta.get("current_capital_actual_project_links") != 0:
        fail("metadata claims capital-actual project links")

    hrm = next((row for row in index.get("organizations") or [] if row.get("organization_id") == HRM_ORG), None)
    if not hrm:
        fail("HRM organization dimension missing")
    counts = hrm.get("record_counts_by_dataset") or {}
    if counts.get("capital_current") != len(current_rows) or counts.get("capital_actuals_current") != len(actual_rows):
        fail("HRM organization source counts do not include Build 008 inputs")

    if meta.get("record_link_count") != len(links):
        fail("record link metadata count mismatch")

    print(
        f"Entity index v5 validated: {len(links)} links; current_projects={len(current_rows)}; "
        f"exact_historical={exact_historical}; current_only={current_only}; category_actuals={len(actual_rows)}; project_actual_links=0"
    )


if __name__ == "__main__":
    main()
