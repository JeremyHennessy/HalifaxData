#!/usr/bin/env python3
"""Build 019 finalizer for literal procurement refs adjacent to source prefixes.

Council motions sometimes print an explicit procurement identifier as `RFP2024-0662`
without whitespace between the procurement prefix and the year. The canonical identifier
is still literally present as year-number text. This finalizer verifies that exact numeric
identifier token (four- or two-digit year plus the same sequence number) without using
names, vendors, titles, descriptions, or dollar values.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import build_lifecycle_reconciliation_build019 as base
import build_lifecycle_reconciliation_build019_v2 as v2


def exact_procurement_identifier_in_text(identifier_value: str, value: Any) -> bool:
    canonical = base.text(identifier_value)
    match = re.fullmatch(r"(20\d{2})-(\d{3,5})", canonical)
    if not match:
        return False
    year, number = match.groups()
    short_year = year[-2:]
    # Digit boundaries prevent matching a substring of a different numeric identifier;
    # alphabetic procurement prefixes such as RFP may touch the year in the source.
    pattern = rf"(?<!\d)(?:{re.escape(year)}|{re.escape(short_year)})\s*-\s*{re.escape(number)}(?!\d)"
    return bool(re.search(pattern, base.text(value), flags=re.I))


def council_ref_is_in_motion(link: dict[str, Any], decision: dict[str, Any], known_capital_ids: set[str]) -> bool:
    motion = base.text(decision.get("motion_text"))
    identifier_type = link.get("identifier_type")
    identifier_value = link.get("identifier_value")
    if not motion or not identifier_value:
        return False
    if identifier_type == "procurement_reference":
        return exact_procurement_identifier_in_text(str(identifier_value), motion)
    if identifier_type == "capital_project_account":
        return identifier_value in set(base.exact_known_tokens(motion, known_capital_ids))
    return False


v2.council_ref_is_in_motion = council_ref_is_in_motion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=base.DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = v2.finalize(base.build())
    payload["metadata"]["council_procurement_token_policy"] = (
        "Exact canonical procurement references are verified in approved motion_text using the same year-number token; "
        "four- and two-digit year presentations are accepted and adjacent procurement prefixes do not invalidate the token."
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": payload["metadata"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
