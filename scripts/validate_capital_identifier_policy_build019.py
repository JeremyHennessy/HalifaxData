#!/usr/bin/env python3
"""Validate Build 019 authoritative capital identifier policy.

Authoritative capital identity is restricted to structured Build 018 `project_account_id`
and Build 010 `project_code`. Raw `previous_code` values are not authoritative in Build 019.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "data/generated/lifecycle_reconciliation.json"
CAPITAL_SCHEDULE = ROOT / "data/generated/current_capital_2026_27_multiyear.json"
CURRENT_CAPITAL = ROOT / "data/generated/current_capital.json"

ALLOWED_CAPITAL_SOURCE_FIELDS = {"project_account_id", "project_code", "account_project_codes", "capital_account_refs"}
ALLOWED_EXCLUSION_REASONS = {
    "previous_code_not_authoritative_in_build019",
    "capital_reference_not_in_safe_structured_project_code_set",
}


def text(value):
    return " ".join(str(value or "").split())


def upper(value):
    return text(value).upper()


def fail(message):
    raise SystemExit(f"Build 019 capital identifier validation failed: {message}")


def safe_ids():
    schedule = json.loads(CAPITAL_SCHEDULE.read_text(encoding="utf-8"))
    capital = json.loads(CURRENT_CAPITAL.read_text(encoding="utf-8"))
    values = {
        upper(row.get("project_account_id"))
        for row in (schedule.get("records") or [])
        if text(row.get("project_account_id"))
    }
    for row in [*(capital.get("current_projects") or []), *(capital.get("prior_projects") or []), *(capital.get("adjustments") or [])]:
        code = upper(row.get("project_code"))
        if code:
            values.add(code)
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    summary = payload.get("summary") or {}
    safe = safe_ids()
    exclusions = payload.get("excluded_capital_identifier_links") or []

    if meta.get("previous_code_authoritative") is not False:
        fail("previous_code must be explicitly non-authoritative")
    if "previous_code" not in str(meta.get("authoritative_capital_identifier_policy") or ""):
        fail("capital identifier policy does not document previous_code exclusion")
    if summary.get("authoritative_capital_ids") != len(safe):
        fail(f"authoritative capital id count mismatch: summary={summary.get('authoritative_capital_ids')} actual={len(safe)}")
    if summary.get("known_capital_ids_all_layers") != len(safe):
        fail("legacy known-capital count does not reflect authoritative safe set")
    if summary.get("excluded_capital_identifier_links") != len(exclusions):
        fail("excluded capital-link summary mismatch")

    for row in payload.get("identifier_links") or []:
        if row.get("identifier_type") != "capital_project_account":
            continue
        if row.get("source_field") == "previous_code":
            fail(f"authoritative previous_code edge survived: {row.get('link_id')}")
        if row.get("source_field") not in ALLOWED_CAPITAL_SOURCE_FIELDS:
            fail(f"unapproved capital source field: {row.get('source_field')} on {row.get('link_id')}")
        if row.get("identifier_value") not in safe:
            fail(f"capital identifier outside safe structured-code set: {row.get('identifier_value')}")

    excluded_ids = set()
    for row in exclusions:
        reason = row.get("reason")
        if reason not in ALLOWED_EXCLUSION_REASONS:
            fail(f"unapproved capital exclusion reason: {reason}")
        if reason == "previous_code_not_authoritative_in_build019" and row.get("source_field") != "previous_code":
            fail("previous_code exclusion reason attached to another source field")
        excluded_ids.add(row.get("link_id"))

    if not exclusions:
        fail("expected raw previous_code/non-safe edges to be explicitly excluded")

    print(json.dumps({
        "status": "ok",
        "authoritative_capital_ids": len(safe),
        "excluded_capital_identifier_links": len(exclusions),
        "previous_code_authoritative": False,
        "build018_schedule_ids": 52,
    }, indent=2))


if __name__ == "__main__":
    main()
