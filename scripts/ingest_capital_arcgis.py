#!/usr/bin/env python3
"""Collect the official HRM historical capital-project ArcGIS layer."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from ingest_domains import clean, now, provenance

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/sources.json"
OUT = ROOT / "data/generated/capital.json"
SOURCE_ID = "hrm-open-capital"
UA = "HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)"


def main():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    src = next(item for item in registry["sources"] if item["id"] == SOURCE_ID)
    layer_url = src["url"]
    session = requests.Session(); session.headers["User-Agent"] = UA
    response = session.get(
        layer_url + "/query",
        params={"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4326", "f": "geojson"},
        timeout=120,
    )
    response.raise_for_status()
    features = response.json().get("features", [])
    rows = []
    for feature in features:
        attrs = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") if geometry.get("type") == "Point" else None
        rows.append({
            "project_id": clean(attrs.get("GLOBALID")) or clean(attrs.get("OBJECTID")),
            "project_code": clean(attrs.get("PROJ_NO")),
            "project_name": clean(attrs.get("PROJ_NAME")),
            "category": clean(attrs.get("CATEGORY")),
            "asset_type": clean(attrs.get("ASSET_TYPE")),
            "fiscal_year": attrs.get("YEAR"),
            "location_id": clean(attrs.get("LOC_ID")),
            "location_description": clean(attrs.get("LOC_DESC")),
            "work_description": clean(attrs.get("WORK_DESC")),
            "source_link": clean(attrs.get("LINK")),
            "longitude": coords[0] if coords and len(coords) > 1 else None,
            "latitude": coords[1] if coords and len(coords) > 1 else None,
            "status": "historical planned project",
            "source_status": src.get("status"),
            "source_id": SOURCE_ID,
            "provenance": provenance(SOURCE_ID, layer_url, "api-record", str(attrs.get("OBJECTID", "")), "build005-capital-arcgis-v1"),
        })
    if len(rows) < 50:
        raise RuntimeError(f"Only {len(rows)} ArcGIS capital rows collected; refusing to replace artifact")
    years = sorted({row["fiscal_year"] for row in rows if row.get("fiscal_year") is not None})
    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "official_historical_arcgis_collection",
            "records": len(rows),
            "years": years,
            "historical": True,
            "note": "Official historical project layer only. It must not be represented as the current capital universe.",
        },
        "records": rows,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(f"Wrote {len(rows)} historical ArcGIS capital rows to {OUT}")


if __name__ == "__main__":
    main()
