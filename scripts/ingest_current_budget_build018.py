#!/usr/bin/env python3
"""Collect the ratified-current 2026/27 HRM service-area budget layer.

Build 018 is deliberately additive. It does not modify or overwrite Build 004's
source-specific 2025/26 `budget.json` contract. The March 25, 2026 post-BAL staff
package is the amount/table source; the March 31 Regional Council record is kept
separately as approval evidence.

The collector scans the official final staff package for pages that actually contain
a `SERVICE AREA BUDGET OVERVIEW` table. It preserves the source heading instead of
forcing current organization names onto the older Build 004 business-unit taxonomy.
Budget authority is not payment, invoice, commitment or final-cost evidence.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import time
from pathlib import Path

import pdfplumber
import requests

import ingest_budget as base

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "current_budget_sources.json"
OUTPUT = ROOT / "data" / "generated" / "current_budget_2026_27.json"
UA = "HalifaxData/0.18 (+https://github.com/JeremyHennessy/HalifaxData)"
PARSER_VERSION = "build018-current-budget-v1"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def source_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def fetch_pdf(url: str, referer: str) -> bytes:
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
        "Referer": referer,
    })
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=180)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise RuntimeError(
                    f"expected PDF from {url}; got {response.headers.get('content-type')!r}"
                )
            return response.content
        except Exception as exc:  # pragma: no cover - live network retry
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"unable to fetch current budget PDF after 3 attempts: {last_error}")


def source_heading(text: str, page_number: int) -> str:
    lines = [clean(line) for line in (text or "").splitlines() if clean(line)]
    marker = "2026/27 Budget and Business Plan"
    for index, line in enumerate(lines):
        if marker.lower() not in line.lower():
            continue
        before = clean(re.sub(re.escape(marker), "", line, flags=re.I).strip(" -|"))
        if before:
            return before
        if index > 0:
            previous = lines[index - 1]
            if previous and "P.O. Box" not in previous and not re.fullmatch(r"\d+", previous):
                return previous
    raise RuntimeError(f"budget page {page_number}: could not identify source business-unit heading")


def parse_bucket(words: list[dict], *, percent: bool, bucket_name: str, page_number: int, heading: str, visual_row: list[dict]):
    try:
        return base.parse_numeric_words(words, percent=percent)
    except RuntimeError as exc:
        coordinates = [(str(word.get("text") or ""), round(float(word.get("x0") or 0), 1)) for word in visual_row]
        raise RuntimeError(
            f"budget page {page_number} ({heading}) failed {bucket_name}; visual row={coordinates}"
        ) from exc


def parse_service_area_page(page, page_number: int, heading: str, stable_retrieved_at: str) -> list[dict]:
    text = page.extract_text() or ""
    if "SERVICE AREA BUDGET OVERVIEW" not in text.upper():
        return []
    if "2026/27" not in text or "2025/26" not in text or "2024/25" not in text:
        raise RuntimeError(f"budget page {page_number}: current/prior fiscal table headers not found")

    visual = base.visual_rows(page)
    header_index = None
    for index, row in enumerate(visual):
        row_text = clean(" ".join(str(word.get("text") or "") for word in row))
        low = row_text.lower()
        if "service area" in low and "actual" in low and "budget" in low and ("projection" in low or "projections" in low):
            header_index = index
            break
    if header_index is None:
        raise RuntimeError(f"budget page {page_number}: service-area column header not found")

    records: list[dict] = []
    pending_label: list[str] = []
    for visual_row in visual[header_index + 1:]:
        buckets = base.budget_buckets(visual_row)
        label = clean(" ".join(str(word.get("text") or "") for word in buckets["label"]))
        values = {
            "prior_actual": parse_bucket(buckets["prior_actual"], percent=False, bucket_name="prior_actual", page_number=page_number, heading=heading, visual_row=visual_row),
            "prior_budget": parse_bucket(buckets["prior_budget"], percent=False, bucket_name="prior_budget", page_number=page_number, heading=heading, visual_row=visual_row),
            "projection": parse_bucket(buckets["projection"], percent=False, bucket_name="projection", page_number=page_number, heading=heading, visual_row=visual_row),
            "current_budget": parse_bucket(buckets["current_budget"], percent=False, bucket_name="current_budget", page_number=page_number, heading=heading, visual_row=visual_row),
            "source_delta": parse_bucket(buckets["source_delta"], percent=False, bucket_name="source_delta", page_number=page_number, heading=heading, visual_row=visual_row),
            "source_delta_pct": parse_bucket(buckets["source_delta_pct"], percent=True, bucket_name="source_delta_pct", page_number=page_number, heading=heading, visual_row=visual_row),
        }
        has_financial_value = any(
            values[key] is not None
            for key in ("prior_actual", "prior_budget", "projection", "current_budget")
        )
        if not has_financial_value:
            if label and not any(marker in label.upper() for marker in ("SUMMARY OF", "EXPENDITURES", "REVENUES")):
                pending_label.append(label)
            continue

        raw_label = clean(" ".join([*pending_label, label]))
        pending_label = []
        if not raw_label:
            raise RuntimeError(f"budget page {page_number}: numeric row without a service-area label")

        service_area, alias = base.normalize_service_area(raw_label)
        record = {
            "record_type": "current_service_area_budget",
            "fiscal_year": "2026/27",
            "fiscal_year_end": 2027,
            "business_unit_source_heading": heading,
            "service_area": service_area,
            "source_service_area_label": raw_label,
            "prior_actual": values["prior_actual"],
            "prior_actual_period": "2024/25",
            "prior_budget": values["prior_budget"],
            "prior_budget_period": "2025/26",
            "projection": values["projection"],
            "projection_period": "2025/26",
            "current_budget": values["current_budget"],
            "current_budget_period": "2026/27",
            "source_reported_budget_change": values["source_delta"],
            "source_reported_budget_change_pct": values["source_delta_pct"],
            "is_total": service_area.lower() == "net total",
            "source_id": "hrm-budget-2026-27-final-package",
            "source_page": page_number,
            "approval_status": "ratified",
            "approval_source_id": "hrm-council-2026-03-31-budget-ratification",
            "provenance": {
                "source_id": "hrm-budget-2026-27-final-package",
                "source_page": page_number,
                "locator_type": "service-area-budget-overview-row",
                "locator_value": f"p{page_number}/{clean(heading)}/{raw_label}",
                "parser_version": PARSER_VERSION,
                "retrieved_at": stable_retrieved_at,
                "validation_status": "parsed",
            },
        }
        if alias:
            record["label_normalization_basis"] = alias["basis"]
            record["label_normalization_evidence"] = alias["evidence"]
        base.annotate_budget_arithmetic(record)
        records.append(record)
        if record["is_total"]:
            break

    totals = [record for record in records if record["is_total"]]
    if len(totals) != 1:
        raise RuntimeError(
            f"budget page {page_number} ({heading}): expected exactly one Net Total, found {len(totals)}"
        )
    return records


def extract_report_controls(pdf, expected: dict) -> dict:
    front_text = "\n".join((pdf.pages[index].extract_text() or "") for index in range(min(20, len(pdf.pages))))
    normalized = clean(front_text)
    spending_match = re.search(r"municipal expenditures of \$?\s*([\d,.]+)\s*million", normalized, re.I)
    capital_match = re.search(r"gross capital spending of \$?\s*([\d,.]+)\s*million", normalized, re.I)
    if not spending_match or not capital_match:
        raise RuntimeError("final budget executive-summary expenditure/capital controls not found")

    municipal_expenditures = int(round(float(spending_match.group(1).replace(",", "")) * 1_000_000))
    gross_capital_spending = int(round(float(capital_match.group(1).replace(",", "")) * 1_000_000))
    if municipal_expenditures != int(expected["municipal_expenditures"]):
        raise RuntimeError(
            f"municipal expenditure control mismatch: {municipal_expenditures} != {expected['municipal_expenditures']}"
        )
    if gross_capital_spending != int(expected["gross_capital_spending"]):
        raise RuntimeError(
            f"gross capital control mismatch: {gross_capital_spending} != {expected['gross_capital_spending']}"
        )
    return {
        "municipal_expenditures": municipal_expenditures,
        "gross_capital_spending": gross_capital_spending,
    }


def main() -> None:
    config = source_config()
    budget_source = config["budget_source"]
    approval_source = config["approval_source"]
    stable_retrieved_at = config["metadata"]["last_researched"] + "T00:00:00Z"
    blob = fetch_pdf(budget_source["url"], approval_source["url"])
    source_sha256 = hashlib.sha256(blob).hexdigest()

    records: list[dict] = []
    overview_pages: list[dict] = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        controls = extract_report_controls(pdf, budget_source["published_controls"])
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if "SERVICE AREA BUDGET OVERVIEW" not in text.upper():
                continue
            heading = source_heading(text, page_number)
            page_records = parse_service_area_page(page, page_number, heading, stable_retrieved_at)
            overview_pages.append({
                "source_page": page_number,
                "business_unit_source_heading": heading,
                "record_count": len(page_records),
                "net_total": next(record["current_budget"] for record in page_records if record["is_total"]),
            })
            records.extend(page_records)
        page_count = len(pdf.pages)

    if len(overview_pages) < 12:
        raise RuntimeError(
            f"only {len(overview_pages)} 2026/27 service-area overview pages found; refusing publication"
        )
    if len(records) < 45:
        raise RuntimeError(f"only {len(records)} current service-area rows found; refusing publication")

    expected_hrp = int(budget_source["published_controls"]["halifax_regional_police_net_budget"])
    hrp_controls = [
        page for page in overview_pages
        if "halifax regional police" in page["business_unit_source_heading"].lower()
        and page["net_total"] == expected_hrp
    ]
    if len(hrp_controls) != 1:
        raise RuntimeError(
            f"expected exactly one Halifax Regional Police net-total control {expected_hrp}; found {len(hrp_controls)}"
        )

    payload = {
        "metadata": {
            "dataset_status": "ratified_current_budget_service_area_tables",
            "parser_version": PARSER_VERSION,
            "fiscal_year": "2026/27",
            "source_id": budget_source["id"],
            "source_url": budget_source["url"],
            "source_sha256": source_sha256,
            "source_stage": budget_source["source_stage"],
            "approval_status": "ratified",
            "approval_source_id": approval_source["id"],
            "approval_url": approval_source["url"],
            "approval_date": approval_source["meeting_date"],
            "pdf_page_count": page_count,
            "overview_page_count": len(overview_pages),
            "service_area_record_count": len(records),
            "net_total_count": sum(record["is_total"] for record in records),
            "source_arithmetic_discrepancy_rows": sum(bool(record.get("validation_flags")) for record in records),
            "published_controls": controls,
            "is_accounts_payable_ledger": False,
            "is_payment_evidence": False,
            "is_final_cost_evidence": False,
            "note": "Current 2026/27 budget authority extracted from the final March 25 post-BAL staff package and linked separately to March 31 Council ratification. These are budget facts, not transactions or payments. Source headings are retained rather than force-mapped to the prior-year organization taxonomy.",
        },
        "overview_pages": overview_pages,
        "records": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(
        f"Wrote {len(records)} current budget rows across {len(overview_pages)} overview pages to {OUTPUT}"
    )


if __name__ == "__main__":
    main()
