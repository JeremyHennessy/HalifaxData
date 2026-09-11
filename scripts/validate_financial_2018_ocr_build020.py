#!/usr/bin/env python3
"""Validate the Build 020 source-specific 2018 OCR audited-financial candidate."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "artifacts/build020-financials-2018-ocr.json"
FINANCIALS = ROOT / "data/generated/financials.json"
EXPECTED_BASE_PARSER = "build005-financials-v4"
EXPECTED_ADAPTER = "build020-financials-2018-ocr-v1"
REQUIRED_FAMILIES = {"financial_position", "operations", "net_financial_assets", "cash_flows"}
ALLOWED_FAMILIES = REQUIRED_FAMILIES | {"schedule"}
NOTE_RE = re.compile(r"\s*\(?notes?\s+\d+[a-z]?(?:\([a-z0-9]+\))?\)?", re.I)
NONWORD_RE = re.compile(r"[^a-z0-9]+")


def norm_label(value: str) -> str:
    text = NOTE_RE.sub(" ", str(value or "").lower())
    return " ".join(NONWORD_RE.sub(" ", text).split())


def close(left: float, right: float, tolerance: float = 1.0) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)


def find_unique(rows: list[dict], family: str, label: str) -> dict:
    target = norm_label(label)
    matches = [row for row in rows if row.get("statement_family") == family and norm_label(row.get("line_item")) == target]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {family!r} row for {label!r}; found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    args = parser.parse_args()

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    metadata = candidate.get("metadata") or {}
    rows = candidate.get("records") or []
    assert metadata.get("dataset_status") == "candidate_2018_source_specific_ocr_extraction", metadata
    assert metadata.get("fiscal_year_end") == 2018, metadata
    assert metadata.get("source_id") == "hrm-financials-2018", metadata
    assert metadata.get("base_parser_version") == EXPECTED_BASE_PARSER, metadata
    assert metadata.get("ocr_adapter_version") == EXPECTED_ADAPTER, metadata
    assert metadata.get("release_status") == "candidate_not_production_until_validated_and_integrated", metadata
    assert isinstance(metadata.get("source_sha256"), str) and len(metadata["source_sha256"]) == 64
    assert metadata.get("records") == len(rows), (metadata.get("records"), len(rows))
    assert len(rows) >= 50, f"2018 OCR candidate unexpectedly sparse: {len(rows)} rows"

    families = Counter(row.get("statement_family") for row in rows)
    assert REQUIRED_FAMILIES.issubset(families), families
    assert not (set(families) - ALLOWED_FAMILIES), families
    assert all(families[name] >= 5 for name in REQUIRED_FAMILIES), families

    seen = set()
    for index, row in enumerate(rows):
        assert row.get("source_id") == "hrm-financials-2018", (index, row.get("source_id"))
        assert row.get("fiscal_year_end") == 2018, (index, row.get("fiscal_year_end"))
        assert row.get("extraction_method") == "ocr_text_line", (index, row.get("extraction_method"))
        assert row.get("ocr_adapter_version") == EXPECTED_ADAPTER, index
        assert row.get("source_unit_multiplier") == 1000, (index, row.get("source_unit_multiplier"))
        assert isinstance(row.get("current_year"), (int, float))
        assert isinstance(row.get("prior_year"), (int, float))
        assert close(row["current_year"], row["source_presented_current_year"] * 1000, 0.011)
        assert close(row["prior_year"], row["source_presented_prior_year"] * 1000, 0.011)
        prov = row.get("provenance") or {}
        assert prov.get("parser_version") == EXPECTED_BASE_PARSER, (index, prov)
        assert prov.get("ocr_adapter_version") == EXPECTED_ADAPTER, (index, prov)
        assert prov.get("source_sha256") == metadata.get("source_sha256"), index
        assert prov.get("locator_type") == "ocr_text_line", (index, prov)
        assert str(prov.get("locator_value") or "").startswith(f"p{row['source_page']}/ocr/"), (index, prov)
        key = (row["source_page"], row["statement_family"], norm_label(row["line_item"]), row["current_year"], row["prior_year"])
        assert key not in seen, f"duplicate OCR fact: {key!r}"
        seen.add(key)

    # Hard source anchors from the OCR proof. These values are in CAD after the
    # source's 'in thousands of dollars' multiplier.
    anchors = [
        ("financial_position", "Cash and short-term deposits", 187_292_000, 235_331_000),
        ("financial_position", "Net financial assets", 163_421_000, 134_397_000),
        ("operations", "Taxation", 736_207_000, 710_941_000),
        ("operations", "Total revenue", 1_037_404_000, 987_465_000),
        ("operations", "Total expenses", 953_587_000, 924_234_000),
        ("operations", "Annual surplus", 83_817_000, 63_231_000),
        ("net_financial_assets", "Net financial assets, end of year", 163_421_000, 134_397_000),
        ("cash_flows", "Cash and short-term deposits, end of year", 187_292_000, 235_331_000),
    ]
    for family, label, current, prior in anchors:
        row = find_unique(rows, family, label)
        assert close(row["current_year"], current), (family, label, row["current_year"], current)
        assert close(row["prior_year"], prior), (family, label, row["prior_year"], prior)

    # Independent consistency check: the 2019 audited source prints 2018 values as
    # its comparative prior-year column. Compare uniquely matching labels/families.
    established = json.loads(FINANCIALS.read_text(encoding="utf-8"))
    rows_2019 = [row for row in established.get("records") or [] if row.get("source_id") == "hrm-financials-2019"]
    prior_index: dict[tuple[str, str], set[float]] = {}
    for row in rows_2019:
        key = (str(row.get("statement_family") or ""), norm_label(row.get("line_item")))
        prior_index.setdefault(key, set()).add(float(row.get("prior_year")))

    overlaps = 0
    matches = 0
    mismatches = []
    for row in rows:
        key = (str(row.get("statement_family") or ""), norm_label(row.get("line_item")))
        expected_values = prior_index.get(key)
        if not expected_values or len(expected_values) != 1:
            continue
        overlaps += 1
        expected = next(iter(expected_values))
        if close(row["current_year"], expected):
            matches += 1
        else:
            mismatches.append((key, row["current_year"], expected))
    assert overlaps >= 20, f"Too few deterministic 2018↔2019 comparative overlaps: {overlaps}"
    assert matches / overlaps >= 0.90, f"2018↔2019 comparative agreement {matches}/{overlaps}; mismatches={mismatches[:10]!r}"

    print(json.dumps({
        "status": "ok",
        "candidate_rows": len(rows),
        "families": dict(sorted(families.items())),
        "2019_comparative_overlaps": overlaps,
        "2019_comparative_matches": matches,
        "2019_comparative_agreement": round(matches / overlaps, 4),
        "source_sha256": metadata["source_sha256"],
        "release_status": metadata["release_status"],
    }, indent=2))


if __name__ == "__main__":
    main()
