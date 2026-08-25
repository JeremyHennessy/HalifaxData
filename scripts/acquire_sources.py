#!/usr/bin/env python3
"""Fetch every mapped non-research source and publish an acquisition manifest.

This stage is intentionally independent from parsing. A source can be acquired and
hashed even when its domain parser is incomplete, so one awkward PDF or web app
cannot block unrelated datasets.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sources.json"
OUTPUT = ROOT / "data" / "generated" / "source_acquisition.json"
UA = "HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)"
READY_PREFIX = "ready"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def acquire(session: requests.Session, source: dict) -> dict:
    result = {
        "source_id": source["id"],
        "category": source.get("category"),
        "publisher": source.get("publisher"),
        "requested_url": source["url"],
        "registry_status": source.get("status"),
        "retrieved_at": utc_now(),
    }
    if not str(source.get("status", "")).startswith(READY_PREFIX):
        result["acquisition_status"] = "skipped_registry_not_ready"
        return result
    try:
        response = session.get(source["url"], timeout=90, allow_redirects=True)
        body = response.content
        result.update(
            {
                "http_status": response.status_code,
                "final_url": response.url,
                "content_type": response.headers.get("content-type", ""),
                "content_length": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "etag": response.headers.get("etag"),
                "last_modified": response.headers.get("last-modified"),
                "acquisition_status": "ok" if response.ok and body else "http_error",
            }
        )
    except Exception as exc:  # capture per-source failure without blocking other domains
        result.update({"acquisition_status": "error", "error": f"{type(exc).__name__}: {exc}"})
    return result


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "*/*"})
    rows = [acquire(session, source) for source in registry["sources"]]
    summary = {
        "total_sources": len(rows),
        "attempted": sum(r["acquisition_status"] not in {"skipped_registry_not_ready"} for r in rows),
        "ok": sum(r["acquisition_status"] == "ok" for r in rows),
        "failed": sum(r["acquisition_status"] in {"error", "http_error"} for r in rows),
        "skipped": sum(r["acquisition_status"] == "skipped_registry_not_ready" for r in rows),
    }
    payload = {
        "metadata": {
            "generated_at": utc_now(),
            "purpose": "Network acquisition evidence. Parsing completeness is tracked separately.",
            **summary,
        },
        "records": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
