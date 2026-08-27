#!/usr/bin/env python3
"""Build a normalized longitudinal series from official public HRM CAO contract-amendment reports.

The output is public amendment-report evidence only. It is not an accounts-payable or
transaction ledger, does not represent final paid values, and does not create findings
of wrongdoing. Source arithmetic and source wording are preserved separately from
all derived controls.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pdfplumber
import requests

DEFAULT_SOURCES = Path("data/contract_amendment_sources.json")
DEFAULT_OUTPUT = Path("data/generated/contract_amendments.json")
UA = "HalifaxData/Build014 CAO amendment series (+https://github.com/JeremyHennessy/HalifaxData)"
MONEY_TOLERANCE = 0.02

SCHEMA_STANDARD = "original_amendment_updated"
SCHEMA_LEGACY = "original_updated_total_to_date"
SCHEMA_CUMULATIVE = "original_cumulative_amendment"
SCHEMA_COLUMNS = {SCHEMA_STANDARD: 6, SCHEMA_LEGACY: 4, SCHEMA_CUMULATIVE: 5}
SCHEMA_SEMANTICS = {
    SCHEMA_STANDARD: (
        "Source publishes Original PO Awarded Amount, Value of Amendment and Updated Value of PO. "
        "Value of Amendment is treated as the published cumulative amendment amount used to reach the updated value; "
        "it is not assumed to be the current incremental change-order request."
    ),
    SCHEMA_LEGACY: (
        "Source publishes PO Awarded Amount and Increase Total to Date. The second amount is treated as the published "
        "updated total because the published percent increase reconciles to (total-to-date - original) / original. "
        "The amendment amount is derived, not source-published."
    ),
    SCHEMA_CUMULATIVE: (
        "Source publishes Original PO Value and Cumulative Amendment(s) Value, without an explicit updated-value column. "
        "Updated value is derived as original plus cumulative amendments and is not represented as source-published."
    ),
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split())


def normalized_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def slug(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", clean(value).lower()).strip("-")
    return text[:96] or "row"


def money_values(value: Any) -> list[float]:
    text = clean(value)
    text = re.sub(r",\s+(?=\d)", ",", text)
    values: list[float] = []
    for match in re.finditer(r"(?<!\d)(-?\s*\$?\s*\d[\d,]*(?:\.\d+)?)(?!\d)", text):
        raw = match.group(1)
        compact = raw.replace(" ", "")
        digits = re.sub(r"\D", "", compact.split(".")[0])
        if "$" not in compact and "," not in compact and "." not in compact and len(digits) >= 7:
            continue
        try:
            values.append(float(compact.replace("$", "").replace(",", "")))
        except ValueError:
            continue
    return values


def percent_values(value: Any) -> list[float]:
    return [float(token) for token in re.findall(r"-?\d+(?:\.\d+)?", clean(value))]


def extract_pos(value: Any) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b20\d{8}\b", clean(value))))


def normalize_contract_ref(value: str) -> str:
    value = clean(value).upper()
    value = re.sub(r"\s*-\s*", "-", value)
    value = re.sub(r"\s+", "-", value)
    return value.strip("-")


def extract_procurement_refs(value: Any) -> list[str]:
    text = clean(value)
    refs: list[str] = []
    code = r"(?:\d{2,4}\s*-\s*\d{2,4}|\d{2,4}[A-Z]\d{2,4})"
    prefixed = rf"\b(?:RFP|RFT|RFQ|Tender|Contract(?:\s+Amendment)?|Alternative\s+Procurement|CA)\s*#?\s*({code})\b"
    for match in re.finditer(prefixed, text, flags=re.IGNORECASE):
        ref = normalize_contract_ref(match.group(1))
        if ref not in refs:
            refs.append(ref)
    simple = r"(?:^|[,;(])\s*(\d{2,4}\s*[- ]\s*\d{2,4})\b"
    for match in re.finditer(simple, text):
        ref = normalize_contract_ref(match.group(1))
        if ref not in refs:
            refs.append(ref)
    return refs


def detect_schema(rows: list[list[str]]) -> str | None:
    if not rows:
        return None
    header = " | ".join(clean(cell).lower() for cell in rows[0])
    if "project name" in header and "original po value" in header and "cumulative amendment" in header:
        return SCHEMA_CUMULATIVE
    if "name" in header and "po awarded amount" in header and "increase total to date" in header:
        return SCHEMA_LEGACY
    if (
        "name" in header
        and "original" in header
        and "updated" in header
        and ("value of amendment" in header or "value of amendmen" in header)
    ):
        return SCHEMA_STANDARD
    return None


def is_approval_table(rows: list[list[str]]) -> bool:
    text = " ".join(clean(cell).lower() for row in rows[:3] for cell in row)
    return "approval authority" in text or ("position" in text and "cao" in text and "delegate" in text)


def financial_like(row: list[str], schema: str) -> bool:
    if schema == SCHEMA_STANDARD and len(row) >= 6:
        return bool(money_values(row[1]) and money_values(row[2]) and money_values(row[3]) and percent_values(row[4]))
    if schema == SCHEMA_LEGACY and len(row) >= 4:
        return bool(money_values(row[1]) and money_values(row[2]) and percent_values(row[3]))
    if schema == SCHEMA_CUMULATIVE and len(row) >= 5:
        return bool(money_values(row[1]) and money_values(row[2]) and percent_values(row[3]))
    return False


def contract_identity(name: str, split_index: int, split_count: int) -> tuple[str | None, list[str], str | None, str | None]:
    pos = extract_pos(name)
    refs = extract_procurement_refs(name)
    po = pos[split_index] if split_index < len(pos) else (pos[0] if len(pos) == 1 and split_count == 1 else None)
    split_refs = [refs[split_index]] if split_count > 1 and len(refs) >= split_count else refs
    if po:
        return po, split_refs, f"po:{po}", "exact source PO number"
    if split_refs:
        return None, split_refs, f"contract:{split_refs[0]}", "source procurement/contract reference; whitespace/hyphen normalized only"
    return None, split_refs, None, None


def source_row_id(report_date: str, page: int, table: int, row: int) -> str:
    return f"{report_date}-p{page}-t{table}-r{row}"


def make_observation(
    *,
    source: dict[str, Any],
    schema: str,
    page: int,
    table: int,
    row_number: int,
    source_cells: list[str],
    name: str,
    reason: str | None,
    split_index: int,
    split_count: int,
    original: float,
    amendment_source: float | None,
    updated_source: float | None,
    increase_pct_source: float | None,
) -> dict[str, Any]:
    po, procurement_refs, contract_key, contract_key_basis = contract_identity(name, split_index, split_count)
    original = round(float(original), 2)
    amendment_source = round(float(amendment_source), 2) if amendment_source is not None else None
    updated_source = round(float(updated_source), 2) if updated_source is not None else None

    if schema == SCHEMA_LEGACY:
        derived_amendment = round(updated_source - original, 2) if updated_source is not None else None
        effective_amendment = derived_amendment
        derived_updated = updated_source
    else:
        derived_amendment = None
        effective_amendment = amendment_source
        derived_updated = round(original + amendment_source, 2) if amendment_source is not None else None

    source_arithmetic_delta: float | None = None
    source_arithmetic_consistent: bool | None = None
    if amendment_source is not None and updated_source is not None:
        source_arithmetic_delta = round(updated_source - (original + amendment_source), 2)
        source_arithmetic_consistent = abs(source_arithmetic_delta) <= MONEY_TOLERANCE

    derived_increase_pct = None
    source_pct_delta = None
    if original and effective_amendment is not None:
        derived_increase_pct = round(effective_amendment / original * 100, 4)
        if increase_pct_source is not None:
            source_pct_delta = round(float(increase_pct_source) - derived_increase_pct, 4)

    row_id = source_row_id(source["report_date"], page, table, row_number)
    identity = contract_key or f"{slug(name)}-{split_index + 1}"
    observation_id = f"{source['report_date']}-{slug(identity)}"
    if split_count > 1:
        observation_id = f"{observation_id}-{split_index + 1}"

    return {
        "id": observation_id,
        "report_date": source["report_date"],
        "source_id": source["id"],
        "source_schema": schema,
        "source_amount_semantics": SCHEMA_SEMANTICS[schema],
        "source_row_id": row_id,
        "source_locations": [{"page": page, "table": table, "row": row_number}],
        "source_cells": source_cells,
        "source_group_size": split_count,
        "source_group_index": split_index + 1,
        "name_source": name,
        "reason_source": reason or "",
        "po": po,
        "procurement_refs": procurement_refs,
        "contract_key": contract_key,
        "contract_key_basis": contract_key_basis,
        "original_value": original,
        "amendment_value_source": amendment_source,
        "updated_value_source": updated_source,
        "derived_amendment_value": derived_amendment,
        "derived_updated_value": derived_updated,
        "effective_cumulative_amendment_value": effective_amendment,
        "increase_pct_source": float(increase_pct_source) if increase_pct_source is not None else None,
        "derived_increase_pct": derived_increase_pct,
        "source_pct_delta": source_pct_delta,
        "source_arithmetic_delta": source_arithmetic_delta,
        "source_arithmetic_consistent": source_arithmetic_consistent,
        "is_invoice_or_payment": False,
        "is_final_paid_value": False,
        "creates_wrongdoing_assertion": False,
    }


def parse_data_rows(
    source: dict[str, Any], schema: str, page: int, table: int, rows: list[list[str]], *, has_header: bool
) -> list[dict[str, Any]]:
    data_rows = rows[1:] if has_header else rows
    output: list[dict[str, Any]] = []
    start_row = 2 if has_header else 1
    for offset, raw_row in enumerate(data_rows):
        row_number = start_row + offset
        row = [clean(cell) for cell in raw_row]
        if not row or not any(row) or not financial_like(row, schema):
            continue
        name = row[0]
        reason = row[5] if schema == SCHEMA_STANDARD and len(row) >= 6 else row[4] if schema == SCHEMA_CUMULATIVE and len(row) >= 5 else None

        if schema == SCHEMA_LEGACY:
            originals, updateds, pcts = money_values(row[1]), money_values(row[2]), percent_values(row[3])
            split_count = max(len(originals), len(updateds), len(pcts))
            if not (len(originals) == len(updateds) == split_count and len(pcts) >= split_count):
                continue
            for index in range(split_count):
                output.append(make_observation(
                    source=source, schema=schema, page=page, table=table, row_number=row_number,
                    source_cells=row, name=name, reason=reason, split_index=index, split_count=split_count,
                    original=originals[index], amendment_source=None, updated_source=updateds[index],
                    increase_pct_source=pcts[index],
                ))
            continue

        if schema == SCHEMA_STANDARD:
            originals, amendments, updateds, pcts = (
                money_values(row[1]), money_values(row[2]), money_values(row[3]), percent_values(row[4])
            )
            split_count = max(len(originals), len(amendments), len(updateds), len(pcts))
            if not (
                len(originals) == len(amendments) == len(updateds) == split_count
                and len(pcts) >= split_count
            ):
                continue
            for index in range(split_count):
                output.append(make_observation(
                    source=source, schema=schema, page=page, table=table, row_number=row_number,
                    source_cells=row, name=name, reason=reason, split_index=index, split_count=split_count,
                    original=originals[index], amendment_source=amendments[index], updated_source=updateds[index],
                    increase_pct_source=pcts[index],
                ))
            continue

        originals, amendments, pcts = money_values(row[1]), money_values(row[2]), percent_values(row[3])
        split_count = max(len(originals), len(amendments), len(pcts))
        if not (len(originals) == len(amendments) == split_count and len(pcts) >= split_count):
            continue
        for index in range(split_count):
            original = abs(originals[index])
            output.append(make_observation(
                source=source, schema=schema, page=page, table=table, row_number=row_number,
                source_cells=row, name=name, reason=reason, split_index=index, split_count=split_count,
                original=original, amendment_source=amendments[index], updated_source=None,
                increase_pct_source=pcts[index],
            ))
    return output


def table_rows(table: Iterable[Iterable[Any]]) -> list[list[str]]:
    return [[clean(cell) for cell in row] for row in table if row]


def extract_pdf_tables(content: bytes) -> tuple[int, list[dict[str, Any]]]:
    pages: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        page_count = len(pdf.pages)
        for page_no, page in enumerate(pdf.pages, 1):
            page_tables = []
            for table_no, table in enumerate(page.extract_tables() or [], 1):
                rows = table_rows(table)
                if rows:
                    page_tables.append({"table": table_no, "column_count": max(map(len, rows), default=0), "rows": rows})
            pages.append({"page": page_no, "tables": page_tables})
    return page_count, pages


def extract_primary_section(source: dict[str, Any], pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], int]:
    observations: list[dict[str, Any]] = []
    warnings: list[str] = []
    active_schema: str | None = None
    started = False
    last_data_page: int | None = None
    matched_tables = 0

    for page_item in pages:
        page_no = int(page_item["page"])
        if started and last_data_page is not None and page_no > last_data_page + 1:
            break
        for table_item in page_item.get("tables", []):
            rows = table_item["rows"]
            schema = detect_schema(rows)
            table_no = int(table_item["table"])

            if not started:
                if schema:
                    started = True
                    active_schema = schema
                    parsed = parse_data_rows(source, schema, page_no, table_no, rows, has_header=True)
                    if parsed:
                        observations.extend(parsed)
                        matched_tables += 1
                        last_data_page = page_no
                continue

            if is_approval_table(rows):
                return observations, warnings, matched_tables

            if schema:
                if schema != active_schema:
                    warnings.append(f"schema changed from {active_schema} to {schema} within primary section on page {page_no}")
                    return observations, warnings, matched_tables
                parsed = parse_data_rows(source, schema, page_no, table_no, rows, has_header=True)
                if parsed:
                    observations.extend(parsed)
                    matched_tables += 1
                    last_data_page = page_no
                continue

            expected = SCHEMA_COLUMNS.get(active_schema or "")
            if expected and int(table_item.get("column_count") or 0) == expected and any(financial_like(row, active_schema) for row in rows):
                parsed = parse_data_rows(source, active_schema, page_no, table_no, rows, has_header=False)
                if parsed:
                    observations.extend(parsed)
                    matched_tables += 1
                    last_data_page = page_no

    if not started:
        warnings.append("no recognized public aggregate amendment table found")
    return observations, warnings, matched_tables


def observation_fingerprint(row: dict[str, Any]) -> tuple[Any, ...]:
    identity = row.get("contract_key") or normalized_text(row.get("name_source"))
    return (
        row.get("report_date"), identity, row.get("original_value"), row.get("amendment_value_source"),
        row.get("updated_value_source"), row.get("increase_pct_source")
    )


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = observation_fingerprint(row)
        if key not in deduped:
            deduped[key] = row
            continue
        current = deduped[key]
        current["source_locations"].extend(
            location for location in row["source_locations"] if location not in current["source_locations"]
        )
        if len(row.get("reason_source", "")) > len(current.get("reason_source", "")):
            current["reason_source"] = row["reason_source"]
        if len(row.get("source_cells", [])) > len(current.get("source_cells", [])):
            current["source_cells"] = row["source_cells"]
    result = list(deduped.values())
    seen_ids: dict[str, int] = defaultdict(int)
    for row in sorted(result, key=lambda item: (item["report_date"], item["source_locations"][0]["page"], item["source_row_id"], item["id"])):
        base = row["id"]
        seen_ids[base] += 1
        if seen_ids[base] > 1:
            row["id"] = f"{base}-{seen_ids[base]}"
    return result


def build_trajectories(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("contract_key"):
            grouped[row["contract_key"]].append(row)

    trajectories: list[dict[str, Any]] = []
    for contract_key, items in grouped.items():
        report_dates = sorted({item["report_date"] for item in items})
        if len(report_dates) < 2:
            continue
        items = sorted(items, key=lambda item: (item["report_date"], item["id"]))
        originals = [float(item["original_value"]) for item in items]
        original_stable = max(originals) - min(originals) <= 1.0
        steps = []
        for previous, current in zip(items, items[1:]):
            prior_value = previous.get("effective_cumulative_amendment_value")
            current_value = current.get("effective_cumulative_amendment_value")
            delta = None
            if original_stable and prior_value is not None and current_value is not None:
                delta = round(float(current_value) - float(prior_value), 2)
            steps.append({
                "from_report_date": previous["report_date"],
                "to_report_date": current["report_date"],
                "from_observation_id": previous["id"],
                "to_observation_id": current["id"],
                "published_cumulative_amendment_delta": delta,
                "interpretation": "Change in published cumulative amendment between public reports; not necessarily one change order.",
            })
        latest = items[-1]
        latest_total = latest.get("updated_value_source")
        if latest_total is None:
            latest_total = latest.get("derived_updated_value")
        first_original = originals[0]
        growth_pct = None
        if first_original and latest_total is not None:
            growth_pct = round((float(latest_total) - first_original) / first_original * 100, 4)
        trajectories.append({
            "contract_key": contract_key,
            "contract_key_basis": next((item.get("contract_key_basis") for item in items if item.get("contract_key_basis")), None),
            "report_count": len(report_dates),
            "observation_count": len(items),
            "first_report_date": report_dates[0],
            "last_report_date": report_dates[-1],
            "original_value_stable": original_stable,
            "first_original_value": round(first_original, 2),
            "latest_total_value": round(float(latest_total), 2) if latest_total is not None else None,
            "latest_effective_cumulative_amendment_value": latest.get("effective_cumulative_amendment_value"),
            "latest_increase_pct_source": latest.get("increase_pct_source"),
            "growth_from_first_original_pct": growth_pct,
            "observation_ids": [item["id"] for item in items],
            "steps": steps,
            "caveat": "Trajectory links use only the same exact PO or source procurement/contract reference after whitespace/hyphen normalization. They do not rely on fuzzy vendor or project-name matching.",
        })
    return sorted(trajectories, key=lambda row: (-row["report_count"], row["contract_key"]))


def fetch_source(session: requests.Session, source: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    response = session.get(source["url"], timeout=120)
    meta = {
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
    }
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("source did not return a PDF")
    return response.content, meta


def pages_from_diagnostic(diagnostic: dict[str, Any], report_date: str) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
    item = next((row for row in diagnostic.get("amendment_reports", []) if row.get("name") == report_date), None)
    if not item:
        raise KeyError(f"diagnostic does not contain {report_date}")
    pages = []
    for page in item.get("pages", []):
        tables = []
        for table in page.get("tables", []):
            tables.append({
                "table": table["table"],
                "column_count": table.get("column_count", 0),
                "rows": table.get("sample", []),
            })
        pages.append({"page": page["page"], "tables": tables})
    return int(item.get("page_count") or 0), pages, {
        "http_status": item.get("status"),
        "content_type": item.get("content_type"),
        "bytes": item.get("bytes", 0),
        "diagnostic_sample_mode": True,
    }


def build(sources_path: Path, diagnostic_path: Path | None = None) -> dict[str, Any]:
    source_doc = json.loads(sources_path.read_text(encoding="utf-8"))
    sources = sorted(source_doc.get("sources", []), key=lambda row: row["report_date"])
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8")) if diagnostic_path else None
    session = requests.Session()
    session.headers["User-Agent"] = UA

    reports = []
    all_observations: list[dict[str, Any]] = []
    for source in sources:
        try:
            if diagnostic is not None:
                page_count, pages, fetch_meta = pages_from_diagnostic(diagnostic, source["report_date"])
            else:
                content, fetch_meta = fetch_source(session, source)
                page_count, pages = extract_pdf_tables(content)
            raw_observations, warnings, matched_tables = extract_primary_section(source, pages)
            observations = deduplicate(raw_observations)
            all_observations.extend(observations)
            reports.append({
                "report_date": source["report_date"],
                "source_id": source["id"],
                "url": source["url"],
                "status": "ready" if observations else "no_rows",
                "page_count": page_count,
                "matched_table_count": matched_tables,
                "observation_count": len(observations),
                "schemas": sorted({row["source_schema"] for row in observations}),
                "http_status": fetch_meta.get("http_status"),
                "content_type": fetch_meta.get("content_type"),
                "bytes": fetch_meta.get("bytes"),
                "warnings": warnings,
            })
        except Exception as exc:
            reports.append({
                "report_date": source["report_date"],
                "source_id": source["id"],
                "url": source["url"],
                "status": "error",
                "observation_count": 0,
                "schemas": [],
                "warnings": [f"{type(exc).__name__}: {exc}"],
            })

    observations = deduplicate(all_observations)
    observations.sort(key=lambda row: (row["report_date"], row["source_locations"][0]["page"], row["id"]))
    trajectories = build_trajectories(observations)
    arithmetic_flags = [row for row in observations if row.get("source_arithmetic_consistent") is False]
    pct_flags = [row for row in observations if row.get("source_pct_delta") is not None and abs(float(row["source_pct_delta"])) > 1.0]
    contract_keys = {row["contract_key"] for row in observations if row.get("contract_key")}
    unkeyed = [row for row in observations if not row.get("contract_key")]
    ready_reports = [row for row in reports if row["status"] == "ready"]

    return {
        "metadata": {
            "dataset_status": "official_public_cao_contract_amendment_series",
            "parser_version": "build014-cao-amendment-series-v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "coverage_start": sources[0]["report_date"] if sources else None,
            "coverage_end": sources[-1]["report_date"] if sources else None,
            "identified_public_report_count": len(sources),
            "ready_report_count": len(ready_reports),
            "is_complete_contract_amendment_ledger": False,
            "is_transaction_ledger": False,
            "is_accounts_payable_ledger": False,
            "is_final_paid_value_data": False,
            "creates_wrongdoing_assertions": False,
            "vendor_aliases_auto_merged": False,
            "fuzzy_contract_links_created": False,
            "private_confidential_may_be_excluded": True,
            "scope": "Public CAO contract-amendment aggregate reporting tables identified from May 2023 through November 2025. This does not claim the complete universe of HRM amendments.",
            "amount_semantics": "Source amount semantics are stored per observation. Published cumulative amendments are not assumed to equal a single current change order."
        },
        "summary": {
            "report_count": len(reports),
            "ready_report_count": len(ready_reports),
            "observation_count": len(observations),
            "unique_contract_keys": len(contract_keys),
            "recurring_exact_contract_keys": len(trajectories),
            "unkeyed_observations": len(unkeyed),
            "source_arithmetic_flags": len(arithmetic_flags),
            "source_percentage_flags_gt_1pp": len(pct_flags)
        },
        "reports": reports,
        "observations": observations,
        "trajectories": trajectories,
        "caveats": [
            "A contract amendment can reflect legitimate scope, schedule, site-condition, utility, market, safety or operational changes and is not evidence of corruption, waste or illegality.",
            "This dataset is amendment-report evidence, not invoices, AP transactions or a final-paid-value ledger.",
            "Private & Confidential amendment reports may be excluded from the public reporting sources.",
            "Longitudinal trajectories use exact source identifiers only; vendor/project-name fuzzy matching is not used."
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--diagnostic-input", type=Path, default=None, help="Optional Build 013 table-sample artifact for offline parser checks.")
    args = parser.parse_args()
    payload = build(args.sources, args.diagnostic_input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": payload["metadata"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
