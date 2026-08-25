#!/usr/bin/env python3
"""Validate Build 005 domain-quality gates.

This validator deliberately separates "artifact exists" from "safe for the
analytical UI". Existing Build 004 validation remains authoritative for the
compensation and budget contracts. This file adds domain-specific checks for
new Build 005 artifacts and ensures known-bad artifacts cannot be marked ready.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALITY_PATH = ROOT / "data/domain_quality.json"
GENERATED = ROOT / "data/generated"

errors: list[str] = []
warnings: list[str] = []


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing required file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    return None


def rows(payload):
    if not isinstance(payload, dict):
        return []
    for key in ("records", "rows", "facts", "items", "projects", "awards", "transactions", "signals"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def artifact_path(entry: dict) -> Path | None:
    raw = entry.get("artifact")
    if not isinstance(raw, str) or not raw:
        return None
    normalized = raw[2:] if raw.startswith("./") else raw
    return ROOT / normalized


def validate_manifest(quality: dict) -> dict:
    domains = quality.get("domains") if isinstance(quality, dict) else None
    if not isinstance(domains, dict):
        errors.append("data/domain_quality.json missing domains object")
        return {}
    allowed = {"ready", "hold", "review", "missing"}
    required = {"compensation", "budget", "procurement", "spending", "capital", "financials", "council", "signals"}
    missing = sorted(required - set(domains))
    if missing:
        errors.append(f"domain quality manifest missing: {missing}")
    for key, entry in domains.items():
        if not isinstance(entry, dict):
            errors.append(f"quality entry {key} is not an object")
            continue
        status = entry.get("status")
        if status not in allowed:
            errors.append(f"quality entry {key}: invalid status {status!r}")
        if not entry.get("boundary") or not entry.get("reason"):
            errors.append(f"quality entry {key}: boundary/reason must be explicit")
        path = artifact_path(entry)
        if status in {"ready", "hold", "review"} and (path is None or not path.exists()):
            errors.append(f"quality entry {key}: status={status} but artifact is missing")
        if status == "missing" and path is not None and path.exists():
            warnings.append(f"quality entry {key}: status=missing but artifact exists; reassess before UI activation")
    return domains


def validate_procurement(entry: dict):
    payload = load_json(GENERATED / "procurement.json")
    if payload is None:
        return
    data = rows(payload)
    metadata = payload.get("metadata", {})
    if metadata.get("records") != len(data):
        errors.append(f"procurement: metadata records {metadata.get('records')} != actual {len(data)}")
    if len(data) < 1000:
        errors.append(f"procurement: unexpectedly small artifact ({len(data)} rows)")
    note = str(metadata.get("note", "")).lower()
    if "not a complete accounts-payable ledger" not in note:
        errors.append("procurement: metadata must preserve the explicit non-AP coverage boundary")

    malformed = 0
    missing_provenance = 0
    invalid_values = 0
    negative_values = 0
    published_value_rows = 0
    entities = set()
    vendors = set()
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            malformed += 1
            continue
        for key in ("award_id", "vendor_name", "entity", "method", "description", "source_id"):
            if not str(row.get(key) or "").strip():
                malformed += 1
                break
        if row.get("source_id") != "ns-awarded-tenders-socrata":
            malformed += 1
        provenance = row.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("source_id") != row.get("source_id") or not provenance.get("source_url") or not provenance.get("locator_value"):
            missing_provenance += 1
        for key in ("original_award_value", "current_contract_value"):
            value = row.get(key)
            if value is None:
                continue
            if not finite_number(value):
                invalid_values += 1
            elif value < 0:
                negative_values += 1
        if any(finite_number(row.get(key)) and row.get(key) > 0 for key in ("original_award_value", "current_contract_value")):
            published_value_rows += 1
        entities.add(str(row.get("entity") or "").strip())
        vendors.add(str(row.get("vendor_name") or "").strip())

    if malformed:
        errors.append(f"procurement: {malformed} rows fail required award identity/source fields")
    if missing_provenance:
        errors.append(f"procurement: {missing_provenance} rows lack per-record source provenance")
    if invalid_values:
        errors.append(f"procurement: {invalid_values} award values are not finite numbers")
    if negative_values:
        errors.append(f"procurement: {negative_values} award values are negative")
    if published_value_rows < 10:
        errors.append(f"procurement: only {published_value_rows} rows expose a positive published award/contract value")
    if len(vendors - {""}) < 100:
        errors.append(f"procurement: unexpectedly low vendor diversity ({len(vendors - {''})})")

    status = entry.get("status")
    if status != "ready":
        warnings.append(f"procurement: structural contract passed but manifest status is {status!r}; UI remains blocked")
    print(
        "PROCUREMENT QUALITY "
        f"rows={len(data)} vendors={len(vendors - {''})} entities={len(entities - {''})} "
        f"positive_value_rows={published_value_rows}"
    )


def validate_spending(entry: dict):
    payload = load_json(GENERATED / "spending.json")
    if payload is None:
        return
    data = rows(payload)
    metadata = payload.get("metadata", {})
    if metadata.get("records") != len(data):
        errors.append(f"spending: metadata records {metadata.get('records')} != actual {len(data)}")
    if metadata.get("is_transaction_ledger") is not False:
        errors.append("spending: artifact must explicitly state is_transaction_ledger=false")
    granularity = str(metadata.get("granularity", "")).lower()
    if "quarterly" not in granularity or "summary" not in granularity:
        errors.append(f"spending: unexpected granularity {metadata.get('granularity')!r}")

    extreme = []
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        value = row.get("amount")
        if finite_number(value) and abs(value) > 1_000_000_000_000:
            extreme.append((index, value))
    if extreme and entry.get("status") == "ready":
        errors.append(f"spending: manifest says ready but {len(extreme)} rows exceed $1T, consistent with merged-cell digit concatenation")
    if not extreme and entry.get("status") == "hold":
        warnings.append("spending: known extreme-value signature is no longer present; reassess the quality hold after parser/source review")
    print(f"SPENDING QUALITY rows={len(data)} status={entry.get('status')} extreme_amount_rows={len(extreme)}")


def validate_capital(entry: dict):
    payload = load_json(GENERATED / "capital.json")
    if payload is None:
        return
    data = rows(payload)
    metadata = payload.get("metadata", {})
    if metadata.get("records") != len(data):
        errors.append(f"capital: metadata records {metadata.get('records')} != actual {len(data)}")

    malformed = []
    geocoded = 0
    plan_rows = 0
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        if row.get("status") == "capital plan":
            plan_rows += 1
        code = str(row.get("project_code") or "")
        project_id = str(row.get("project_id") or "")
        if "Previous #:" in code or "Previous #:" in project_id:
            malformed.append(index)
        lat, lon = row.get("latitude"), row.get("longitude")
        if finite_number(lat) and finite_number(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            geocoded += 1

    if malformed and entry.get("status") == "ready":
        errors.append(f"capital: manifest says ready but {len(malformed)} rows have malformed project code/id containing 'Previous #:'")
    if not malformed and entry.get("status") == "hold":
        warnings.append("capital: malformed 'Previous #:' signature is no longer present; reassess quality hold after full regeneration checks")
    print(
        f"CAPITAL QUALITY rows={len(data)} status={entry.get('status')} "
        f"capital_plan_rows={plan_rows} malformed_code_rows={len(malformed)} geocoded_rows={geocoded}"
    )


def validate_financials(entry: dict):
    payload = load_json(GENERATED / "financials.json")
    if payload is None:
        return
    data = rows(payload)
    metadata = payload.get("metadata", {})
    if metadata.get("records") != len(data):
        errors.append(f"financials: metadata records {metadata.get('records')} != actual {len(data)}")

    suspicious_re = re.compile(
        r"(?:telephone|fax|year ended march|halifax nova scotia b3j|september|consolidated schedules of .*\d|notes to consolidated financial statements)",
        re.IGNORECASE,
    )
    suspicious = []
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        label = str(row.get("line_item") or "")
        raw = " ".join(str(cell) for cell in row.get("raw_cells", []) if cell is not None)
        if suspicious_re.search(label) or re.search(r"\b\(?902\)?\s*\d{3}[- ]\d{4}\b", raw):
            suspicious.append(index)

    if suspicious and entry.get("status") == "ready":
        errors.append(f"financials: manifest says ready but {len(suspicious)} rows match known non-financial numeric text patterns")
    if not suspicious and entry.get("status") == "hold":
        warnings.append("financials: known non-financial numeric signature is no longer present; reassess quality hold after statement control checks")
    print(f"FINANCIALS QUALITY rows={len(data)} status={entry.get('status')} suspicious_rows={len(suspicious)}")


def main():
    quality = load_json(QUALITY_PATH)
    if quality is None:
        print("MULTIDOMAIN VALIDATION FAILED", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    domains = validate_manifest(quality)
    if domains:
        validate_procurement(domains.get("procurement", {}))
        validate_spending(domains.get("spending", {}))
        validate_capital(domains.get("capital", {}))
        validate_financials(domains.get("financials", {}))

    if warnings:
        print("MULTIDOMAIN VALIDATION WARNINGS", file=sys.stderr)
        print("\n".join(warnings), file=sys.stderr)
    if errors:
        print("MULTIDOMAIN VALIDATION FAILED", file=sys.stderr)
        print("\n".join(errors[:100]), file=sys.stderr)
        raise SystemExit(1)
    print("multidomain quality gates validated")


if __name__ == "__main__":
    main()
