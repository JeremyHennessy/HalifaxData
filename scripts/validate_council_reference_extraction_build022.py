#!/usr/bin/env python3
"""Regression controls for Build 022 Council reference extraction."""
from __future__ import annotations

import sys
import types

try:
    import pdfplumber  # noqa: F401
except ModuleNotFoundError:
    sys.modules["pdfplumber"] = types.ModuleType("pdfplumber")

from ingest_council_decisions import extract_refs

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
    refs=extract_refs(value)["procurement_refs"]
    if refs:
        raise SystemExit(f"false procurement reference extracted from {value!r}: {refs!r}")

for value, expected in TRUE_CASES:
    refs=extract_refs(value)["procurement_refs"]
    if expected not in refs:
        raise SystemExit(f"expected procurement reference {expected!r} missing from {value!r}: {refs!r}")

print("Council reference extraction validated: word-prefix false positives rejected; explicit references retained.")
