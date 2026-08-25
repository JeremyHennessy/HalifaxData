#!/usr/bin/env python3
"""Collect Nova Scotia awarded public tenders for Halifax municipal bodies.

The source query is counted first, then retrieved in deterministic Socrata pages.
The collector refuses to publish if the number of source rows retrieved does not
match the count observed at the start of the run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from ingest_domains import clean, money, now, provenance

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data/generated/procurement.json"
SODA_AWARDED = "https://data.novascotia.ca/resource/m6ps-8j6u.json"
SOURCE_ID = "ns-awarded-tenders-socrata"
UA = "HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)"
WHERE = "upper(entity) like '%HALIFAX%'"
PAGE_SIZE = 5000
HALIFAX_ENTITY_TOKENS = (
    "halifax regional municipality",
    "halifax water",
    "halifax public libraries",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def fetch_source_count(session: requests.Session) -> int:
    response = session.get(
        SODA_AWARDED,
        params={"$select": "count(*) as count", "$where": WHERE},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or len(payload) != 1:
        raise RuntimeError(f"Unexpected Socrata count response: {payload!r}")
    try:
        count = int(payload[0]["count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid Socrata count response: {payload!r}") from exc
    if count < 0:
        raise RuntimeError(f"Invalid negative Socrata source count: {count}")
    return count


def fetch_source_rows(session: requests.Session, expected_count: int) -> tuple[list[dict], int]:
    raw: list[dict] = []
    offset = 0
    page_count = 0
    while offset < expected_count:
        response = session.get(
            SODA_AWARDED,
            params={
                "$limit": PAGE_SIZE,
                "$offset": offset,
                "$where": WHERE,
                "$order": ":id ASC",
            },
            timeout=120,
        )
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected Socrata page response at offset {offset}: {batch!r}")
        if not batch:
            break
        raw.extend(batch)
        page_count += 1
        offset += len(batch)
        if len(batch) < PAGE_SIZE:
            break

    if len(raw) != expected_count:
        raise RuntimeError(
            f"Socrata source count changed or pagination was incomplete: "
            f"expected {expected_count}, retrieved {len(raw)}; refusing to replace artifact"
        )
    return raw, page_count


def normalize_rows(raw: list[dict]) -> tuple[list[dict], int, int]:
    rows = []
    seen = set()
    retained_before_dedup = 0
    duplicates_removed = 0

    for item in raw:
        entity = clean(item.get("entity"))
        entity_norm = entity.lower()
        if not any(token in entity_norm for token in HALIFAX_ENTITY_TOKENS):
            continue
        retained_before_dedup += 1
        award_id = clean(item.get("tender_id"))
        vendor = clean(item.get("vendor"))
        key = (award_id, vendor, clean(item.get("awarded_date")), clean(item.get("awarded_amount")))
        if key in seen:
            duplicates_removed += 1
            continue
        seen.add(key)
        amount = money(item.get("awarded_amount"))
        categories = [clean(item.get(k)) for k in ("goods", "service", "construction") if clean(item.get(k))]
        rows.append(
            {
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
                "provenance": provenance(
                    SOURCE_ID,
                    SODA_AWARDED,
                    "api-record",
                    award_id or vendor,
                    "build005-procurement-v2",
                ),
            }
        )
    return rows, retained_before_dedup, duplicates_removed


def main() -> None:
    args = parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = UA

    source_count = fetch_source_count(session)
    raw, page_count = fetch_source_rows(session, source_count)
    rows, retained_before_dedup, duplicates_removed = normalize_rows(raw)

    if len(rows) < 100:
        raise RuntimeError(f"Only {len(rows)} Halifax procurement rows collected; refusing to replace artifact")

    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "official_awarded_tenders_collection",
            "source_dataset_id": "m6ps-8j6u",
            "source_query_record_count": source_count,
            "source_query_collection_complete": len(raw) == source_count,
            "query_page_size": PAGE_SIZE,
            "query_page_count": page_count,
            "source_rows_retained_before_dedup": retained_before_dedup,
            "source_rows_filtered_out": source_count - retained_before_dedup,
            "duplicates_removed": duplicates_removed,
            "records": len(rows),
            "note": (
                "Public-tender awards are not a complete accounts-payable ledger and do not "
                "include every alternative procurement or later contract amendment."
            ),
        },
        "records": rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(
        f"Wrote {len(rows)} Halifax awarded-tender rows from {source_count} source-query rows "
        f"across {page_count} page(s) to {args.output}"
    )


if __name__ == "__main__":
    main()
