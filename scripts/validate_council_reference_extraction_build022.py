#!/usr/bin/env python3
"""Regression controls for Build 022 Council procurement-reference extraction.

The validator parses the collector source with AST instead of importing it, so bare CI
does not need the PDF collector's pdfplumber dependency.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts/ingest_council_decisions.py"


def load_procurement_pattern() -> re.Pattern[str]:
    tree = ast.parse(COLLECTOR.read_text(encoding="utf-8"), filename=str(COLLECTOR))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "PROCUREMENT_RE" for target in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or call.func.attr != "compile":
            raise SystemExit("PROCUREMENT_RE is no longer a direct re.compile(...) assignment")
        if not call.args:
            raise SystemExit("PROCUREMENT_RE has no regex argument")
        pattern = ast.literal_eval(call.args[0])
        flags = 0
        if len(call.args) > 1:
            flag_node = call.args[1]
            if isinstance(flag_node, ast.Attribute) and isinstance(flag_node.value, ast.Name) and flag_node.value.id == "re":
                flags = getattr(re, flag_node.attr)
            else:
                flags = ast.literal_eval(flag_node)
        return re.compile(pattern, flags)
    raise SystemExit("PROCUREMENT_RE not found in ingest_council_decisions.py")


PROCUREMENT_RE = load_procurement_pattern()


def refs(value: str) -> list[str]:
    seen = set()
    output = []
    for token in PROCUREMENT_RE.findall(value):
        normalized = " ".join(str(token or "").split()).upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


FALSE_POSITIVES = [
    "Council approved the policy update.",
    "A portion of Robert Burns Drive will be closed.",
    "Permission for alcohol service at Porters Lake Community Centre.",
    "The portal system access is renewed.",
]
TRUE_CASES = [
    ("RFP 2026-0329 was awarded.", "2026-0329"),
    ("Contract No. 2025-0204 was discussed.", "2025-0204"),
    ("PO #123456 supports the amendment.", "123456"),
    ("Tender HRM-2026-0184 was referenced.", "HRM-2026-0184"),
]

for value in FALSE_POSITIVES:
    extracted = refs(value)
    if extracted:
        raise SystemExit(f"false procurement reference extracted from {value!r}: {extracted!r}")

for value, expected in TRUE_CASES:
    extracted = refs(value)
    if expected not in extracted:
        raise SystemExit(f"expected procurement reference {expected!r} missing from {value!r}: {extracted!r}")

print("Council reference extraction validated from collector source: word-prefix false positives rejected; explicit references retained.")
