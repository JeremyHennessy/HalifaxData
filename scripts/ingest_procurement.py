#!/usr/bin/env python3
"""Collect Nova Scotia awarded public tenders for Halifax municipal bodies."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from ingest_domains import clean, money, now, provenance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/procurement.json"
SODA_AWARDED = "https://data.novascotia.ca/resource/m6ps-8j6u.json"
SOURCE_ID = "ns-awarded-tenders-socrata"
UA = "HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)"


def main():
    session = requests.Session()
    session.headers["User-Agent"] = UA
    response = session.get(
        SODA_AWARDED,
        params={"$limit": 50000, "$where": "upper(entity) like '%HALIFAX%'", "$order": "awarded_date DESC"},
        timeout=120,
    )
    response.raise_for_status()
    raw = response.json()
    rows = []
    seen = set()
    for item in raw:
        entity = clean(item.get("entity"))
        entity_norm = entity.lower()
        if not any(token in entity_norm for token in ["halifax regional municipality", "halifax water", "halifax public libraries"]):
            continue
        award_id = clean(item.get("tender_id"))
        vendor = clean(item.get("vendor"))
        key = (award_id, vendor, clean(item.get("awarded_date")), clean(item.get("awarded_amount")))
        if key in seen:
            continue
        seen.add(key)
        amount = money(item.get("awarded_amount"))
        categories = [clean(item.get(k)) for k in ("goods", "service", "construction") if clean(item.get(k))]
        rows.append({
            "award_id": award_id,
            "solicitation": award_id,
            "vendor_name": vendor,
            "entity": entity,
            "method": "Public tender",
            "category": " / ".join(categories) or None,
            "description": clean(item.get("tender_description")),
            "tender_start_date": item.get("tender_start_date"),
            "tender_close_date": item.get("tender_close_date"),
            "awarded_date": item.get("awarded_date"),
            "original_award_value": amount,
            "current_contract_value": amount,
            "source_id": SOURCE_ID,
            "provenance": provenance(SOURCE_ID, SODA_AWARDED, "api-record", award_id or vendor, "build005-procurement-v1"),
        })
    if len(rows) < 100:
        raise RuntimeError(f"Only {len(rows)} Halifax procurement rows collected; refusing to replace artifact")
    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "official_awarded_tenders_collection",
            "source_dataset_id": "m6ps-8j6u",
            "records": len(rows),
            "note": "Public-tender awards are not a complete accounts-payable ledger and do not include every alternative procurement or later contract amendment.",
        },
        "records": rows,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(f"Wrote {len(rows)} Halifax awarded-tender rows to {OUT}")


if __name__ == "__main__":
    main()
