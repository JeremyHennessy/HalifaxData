#!/usr/bin/env python3
"""Collect the official HRM historical capital-project ArcGIS layer.

The collector first asks the service for its authoritative feature count, then
pages deterministically by OBJECTID. It refuses to publish a replacement
artifact unless every advertised feature was collected exactly once.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from ingest_domains import clean, now, provenance

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/sources.json"
DEFAULT_OUT = ROOT / "data/generated/capital.json"
SOURCE_ID = "hrm-open-capital"
UA = "HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)"
PAGE_SIZE = 2000
OUT_FIELDS = ",".join(
    [
        "OBJECTID",
        "LOC_ID",
        "LOC_DESC",
        "WORK_DESC",
        "PROJ_NAME",
        "PROJ_NO",
        "CATEGORY",
        "YEAR",
        "LINK",
        "ASSET_TYPE",
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def get_source_count(session: requests.Session, layer_url: str) -> int:
    response = session.get(
        layer_url + "/query",
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"ArcGIS count query failed: {payload['error']}")
    count = payload.get("count")
    if not isinstance(count, int) or count < 0:
        raise RuntimeError(f"ArcGIS returned invalid feature count: {count!r}")
    return count


def fetch_features(session: requests.Session, layer_url: str, expected_count: int) -> tuple[list[dict], int]:
    features: list[dict] = []
    seen_object_ids: set[int | str] = set()
    offset = 0
    page_count = 0

    while offset < expected_count:
        response = session.get(
            layer_url + "/query",
            params={
                "where": "1=1",
                "outFields": OUT_FIELDS,
                "returnGeometry": "true",
                "outSR": "4326",
                "orderByFields": "OBJECTID ASC",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
                "f": "json",
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"ArcGIS page query failed at offset {offset}: {payload['error']}")
        batch = payload.get("features")
        if not isinstance(batch, list):
            raise RuntimeError(f"ArcGIS page at offset {offset} did not contain a feature list")
        if not batch:
            break

        page_count += 1
        new_in_page = 0
        for feature in batch:
            attrs = feature.get("attributes") or {}
            object_id = attrs.get("OBJECTID")
            if object_id is None:
                raise RuntimeError(f"ArcGIS feature at offset {offset} is missing OBJECTID")
            if object_id in seen_object_ids:
                raise RuntimeError(f"ArcGIS pagination repeated OBJECTID {object_id!r}")
            seen_object_ids.add(object_id)
            features.append(feature)
            new_in_page += 1

        if new_in_page != len(batch):
            raise RuntimeError(f"ArcGIS page at offset {offset} did not advance cleanly")
        offset += len(batch)

        if len(batch) < PAGE_SIZE and not payload.get("exceededTransferLimit", False):
            break

    if len(features) != expected_count:
        raise RuntimeError(
            f"ArcGIS advertised {expected_count} features but collector retrieved {len(features)}; "
            "refusing to replace artifact"
        )
    return features, page_count


def build_rows(features: list[dict], source_status: str | None, layer_url: str) -> list[dict]:
    rows = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        geometry = feature.get("geometry") or {}
        object_id = attrs.get("OBJECTID")
        rows.append(
            {
                "project_id": clean(object_id),
                "project_code": clean(attrs.get("PROJ_NO")),
                "project_name": clean(attrs.get("PROJ_NAME")),
                "category": clean(attrs.get("CATEGORY")),
                "asset_type": clean(attrs.get("ASSET_TYPE")),
                "fiscal_year": attrs.get("YEAR"),
                "location_id": clean(attrs.get("LOC_ID")),
                "location_description": clean(attrs.get("LOC_DESC")),
                "work_description": clean(attrs.get("WORK_DESC")),
                "source_link": clean(attrs.get("LINK")),
                "longitude": geometry.get("x"),
                "latitude": geometry.get("y"),
                "status": "historical planned project",
                "source_status": source_status,
                "source_id": SOURCE_ID,
                "provenance": provenance(
                    SOURCE_ID,
                    layer_url,
                    "api-objectid",
                    str(object_id),
                    "build005-capital-arcgis-v2",
                ),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    src = next(item for item in registry["sources"] if item["id"] == SOURCE_ID)
    layer_url = src["url"].rstrip("/")

    session = requests.Session()
    session.headers["User-Agent"] = UA

    source_count = get_source_count(session, layer_url)
    if source_count < 50:
        raise RuntimeError(
            f"ArcGIS source reports only {source_count} features; refusing to replace artifact"
        )

    features, page_count = fetch_features(session, layer_url, source_count)
    rows = build_rows(features, src.get("status"), layer_url)
    years = sorted({row["fiscal_year"] for row in rows if row.get("fiscal_year") is not None})

    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "official_historical_arcgis_collection",
            "records": len(rows),
            "source_record_count": source_count,
            "collection_complete": len(rows) == source_count,
            "query_page_size": PAGE_SIZE,
            "query_page_count": page_count,
            "years": years,
            "historical": True,
            "note": (
                "Official historical project layer only. It must not be represented as the "
                "current capital universe."
            ),
        },
        "records": rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(
        f"Wrote {len(rows)} historical ArcGIS capital rows from {page_count} page(s) "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
