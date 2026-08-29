#!/usr/bin/env python3
"""Build 019 diagnostic wrapper preserving distinct raw presentations of one identifier.

The underlying reconciliation semantics remain in build_lifecycle_reconciliation_build019.
This wrapper changes only link identity so one source record can retain two literal source
presentations that normalize to the same explicit identifier without causing a hash collision.
"""
from __future__ import annotations

import argparse
import json
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
    links.append({
        "link_id": f"b19-{base.stable_hash(identifier_type, identifier_value, raw_identifier, evidence['domain'], evidence['record_type'], evidence['record_key'], match_method, source_field)}",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=base.DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = base.build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": payload["metadata"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
