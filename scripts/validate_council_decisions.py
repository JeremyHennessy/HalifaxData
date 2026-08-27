#!/usr/bin/env python3
"""Validate Build 016 Council decision evidence and interpretation boundaries."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/generated/council_decisions.json"
COUNCIL_PATH = ROOT / "data/generated/council.json"
REGISTRY_PATH = ROOT / "data/council_decision_sources.json"
ALLOWED_RESULTS = {"passed", "passed_unanimously", "defeated", "tied", "withdrawn", "other"}
OFFICIAL_HOSTS = {
    "pub-halifax.escribemeetings.com",
    "www.halifax.ca",
    "cdn.halifax.ca",
    "legacycontent.halifax.ca",
}
FORBIDDEN_RECORD_KEYS = {
    "invoice_id",
    "payment_id",
    "payment_date",
    "vendor_payment",
    "final_paid_value",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    council = json.loads(COUNCIL_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    meta = data.get("metadata") or {}
    rows = data.get("records") or []
    status = data.get("source_status") or []

    if meta.get("dataset_status") != "approved_minutes_motion_outcome_extraction":
        fail("Unexpected Council-decision dataset status")
    if meta.get("parser_version") != "build016-council-decisions-v1":
        fail("Unexpected Council-decision parser version")
    if meta.get("legacy_seed_complete") is not False:
        fail("Legacy seed must remain explicitly incomplete")
    if meta.get("is_payment_ledger") is not False:
        fail("Council decisions must never be represented as a payment ledger")
    if len(rows) < 25:
        fail(f"Only {len(rows)} Council decision rows; refusing weak artifact")
    if meta.get("decision_records") != len(rows):
        fail("Council decision metadata count mismatch")

    ids = [row.get("decision_id") for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        fail("Council decision IDs are missing or duplicated")

    council_ids = {str(row.get("meeting_id")) for row in council.get("records", []) if row.get("meeting_id")}
    legacy_ids = {row["source_id"] for row in registry.get("legacy_sources", [])}
    source_status_by_key = {}
    for item in status:
        key = (item.get("source_id"), item.get("meeting_id"), item.get("meeting_date"))
        if key in source_status_by_key:
            fail(f"Duplicate source-status key {key}")
        source_status_by_key[key] = item
        if int(item.get("decision_records") or 0) < 1:
            fail(f"Source produced no decisions: {key}")
        if int(item.get("pdf_pages") or 0) < 1:
            fail(f"Invalid PDF page count: {key}")
        sha = str(item.get("source_sha256") or "")
        if len(sha) != 64:
            fail(f"Invalid source hash: {key}")

    modern_status = [item for item in status if item.get("coverage_layer") == "modern_escribe_complete_posted_minutes_window"]
    legacy_status = [item for item in status if item.get("coverage_layer") == "legacy_seed_incomplete"]
    if len(legacy_status) != len(legacy_ids):
        fail("Not every registered legacy seed source is represented in source_status")
    if len(modern_status) != int(meta.get("modern_meetings_with_posted_minutes") or -1):
        fail("Modern posted-minutes source count mismatch")

    passed = 0
    fiscal = 0
    money_rows = 0
    modern_rows = 0
    legacy_rows = 0
    for row in rows:
        if FORBIDDEN_RECORD_KEYS.intersection(row):
            fail(f"Unsupported payment-level fields in {row.get('decision_id')}")
        result = row.get("decision_status")
        if result not in ALLOWED_RESULTS:
            fail(f"Unsupported motion result {result!r}")
        motion_text = str(row.get("motion_text") or "").strip()
        if len(motion_text) < 8:
            fail(f"Missing motion text in {row.get('decision_id')}")
        if int(row.get("source_page") or 0) < 1:
            fail(f"Missing source page in {row.get('decision_id')}")
        url = str(row.get("source_url") or "")
        host = (urlparse(url).hostname or "").lower()
        if host not in OFFICIAL_HOSTS:
            fail(f"Non-official Council source host {host!r} in {row.get('decision_id')}")
        sha = str(row.get("source_sha256") or "")
        if len(sha) != 64:
            fail(f"Missing source hash in {row.get('decision_id')}")

        layer = row.get("coverage_layer")
        if layer == "modern_escribe_complete_posted_minutes_window":
            modern_rows += 1
            if str(row.get("meeting_id")) not in council_ids:
                fail(f"Modern decision references unknown eSCRIBE meeting {row.get('meeting_id')}")
            if row.get("source_id") != "hrm-escribe":
                fail("Modern Council decision must retain hrm-escribe source ID")
        elif layer == "legacy_seed_incomplete":
            legacy_rows += 1
            if row.get("source_id") not in legacy_ids:
                fail(f"Legacy decision references unregistered source {row.get('source_id')}")
        else:
            fail(f"Unknown Council coverage layer {layer!r}")

        if bool(row.get("motion_passed")) != (result in {"passed", "passed_unanimously"}):
            fail(f"motion_passed disagrees with canonical result in {row.get('decision_id')}")
        if row.get("motion_passed"):
            passed += 1
        if row.get("fiscal_relevant"):
            fiscal += 1
        mentions = row.get("money_mentions") or []
        if mentions:
            money_rows += 1
        for mention in mentions:
            amount = mention.get("amount_cad")
            if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                fail(f"Invalid dollar mention in {row.get('decision_id')}")

    if modern_rows < 10:
        fail("Modern eSCRIBE decision extraction is unexpectedly sparse")
    if legacy_rows < len(legacy_ids):
        fail("Legacy seed did not produce at least one decision per registered source")
    if passed < 10:
        fail("Too few passed motions for a credible Council decision artifact")
    if fiscal < 5 or money_rows < 1:
        fail("Council artifact lacks expected fiscal/monetary decision evidence")
    if modern_rows != int(meta.get("modern_decision_records") or -1):
        fail("Modern decision metadata mismatch")
    if legacy_rows != int(meta.get("legacy_decision_records") or -1):
        fail("Legacy decision metadata mismatch")
    if passed != int(meta.get("passed_motion_records") or -1):
        fail("Passed-motion metadata mismatch")
    if fiscal != int(meta.get("fiscal_relevant_records") or -1):
        fail("Fiscal-relevant metadata mismatch")
    if money_rows != int(meta.get("money_mention_records") or -1):
        fail("Money-mention metadata mismatch")

    print(
        "Council decisions validated:",
        len(rows), "records;",
        modern_rows, "modern;",
        legacy_rows, "legacy seed;",
        passed, "passed;",
        fiscal, "fiscal relevant;",
        money_rows, "with dollar mentions",
    )


if __name__ == "__main__":
    main()
