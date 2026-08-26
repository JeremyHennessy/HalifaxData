#!/usr/bin/env python3
"""Build 011 procurement collector with exact-title eSCRIBE attachment resolution.

The checked-in Council document graph is historical evidence and is never rewritten
when eSCRIBE replaces a filestream attachment. This entrypoint first tests the graph
URL. If it no longer serves a PDF, it re-reads the owning agenda and requires exactly
one unique filestream href whose visible text exactly matches the checked-in report
title. Both graph and resolved URLs are retained in report/row provenance.

This layer also admits the Apr-Jun 2026 controlled appendix's explicit `Award Total`
header as the same source concept previously labelled `Award Total Project Value` /
`Project Value`. No general competitive table is reclassified by that refinement.
"""
from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

import ingest_procurement_quarterly_reports as base


class AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        self.current = {"href": dict(attrs).get("href") or "", "text": []}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"].append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or self.current is None:
            return
        self.anchors.append({
            "href": self.current["href"],
            "text": base.clean(" ".join(self.current["text"])),
        })
        self.current = None


def enhanced_modern_alt_header(table: list[list[str]]):
    existing = _ORIGINAL_MODERN_ALT_HEADER(table)
    if existing:
        return existing
    for index, row in enumerate(table[:6]):
        headers = [base.normalize_header(cell) for cell in row]
        if any("source published" in h or "actual award amount" in h or "completed submissions" in h for h in headers):
            continue
        mapping = {}
        for col, header in enumerate(headers):
            if header == "project number":
                mapping["project_number"] = col
            elif header == "project name":
                mapping["project_name"] = col
            elif header == "procurement type":
                mapping["procurement_type"] = col
            elif header in {"awarded summary", "supplier", "awarded supplier"}:
                mapping["supplier"] = col
            elif header in {"award total", "award total project value", "project value"}:
                mapping["value"] = col
            elif header in {"internal reference", "cost centre project number", "cost center project number"}:
                mapping["reference"] = col
            elif header == "department":
                mapping["department"] = col
        if {"project_number", "project_name", "procurement_type", "supplier", "value"}.issubset(mapping):
            return index, mapping
    return None


_ORIGINAL_MODERN_ALT_HEADER = base.find_modern_alt_header
base.find_modern_alt_header = enhanced_modern_alt_header


def graph_url_is_live_pdf(session: requests.Session, url: str) -> bool:
    try:
        response = session.get(url, timeout=90)
        return response.ok and response.content.startswith(b"%PDF")
    except Exception:
        return False


def exact_title_live_url(session: requests.Session, report: dict) -> str:
    agenda_url = report.get("agenda_url")
    if not agenda_url:
        raise RuntimeError(f"Graph attachment failed and no owning agenda URL is available: {report['title']}")
    response = session.get(agenda_url, timeout=120)
    response.raise_for_status()
    parser = AnchorCollector()
    parser.feed(response.text)
    target = base.clean(report["title"])
    candidates = []
    for anchor in parser.anchors:
        href = anchor["href"]
        if base.clean(anchor["text"]) != target:
            continue
        absolute = urljoin(agenda_url, href)
        if "filestream.ashx" not in absolute.lower():
            continue
        candidates.append(absolute)
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise RuntimeError(
            f"Expected one exact-title live attachment for {target!r}; found {len(unique)} unique filestream URLs: {unique}"
        )
    if not graph_url_is_live_pdf(session, unique[0]):
        raise RuntimeError(f"Exact-title agenda attachment does not currently serve a PDF: {unique[0]}")
    return unique[0]


def resolve_report(session: requests.Session, report: dict) -> tuple[dict, str]:
    graph_url = report.get("url")
    if not graph_url:
        raise RuntimeError(f"Quarterly report has no checked-in graph URL: {report['title']}")
    if graph_url_is_live_pdf(session, graph_url):
        return report, "checked_in_graph_url_live"
    resolved_url = exact_title_live_url(session, report)
    resolved = dict(report)
    resolved["url"] = resolved_url
    resolved["source_url_registry"] = graph_url
    resolved["source_url_resolved"] = resolved_url
    return resolved, "exact_title_live_agenda_resolution"


def annotate(meta: dict, rows: list[dict], original: dict, resolved: dict, resolution: str) -> None:
    graph_url = original.get("url")
    resolved_url = resolved.get("url")
    meta["source_url_registry"] = graph_url
    meta["source_url_resolved"] = resolved_url
    meta["source_url_resolution"] = resolution
    meta["source_url_changed_since_graph"] = graph_url != resolved_url
    for row in rows:
        row["source_url_registry"] = graph_url
        row["source_url_resolved"] = resolved_url
        row["source_url_resolution"] = resolution
        row["source_url_changed_since_graph"] = graph_url != resolved_url
        provenance = row.get("provenance") or {}
        provenance["source_url_registry"] = graph_url
        provenance["source_url_resolved"] = resolved_url
        provenance["source_url_resolution"] = resolution
        row["provenance"] = provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=base.DEFAULT_OUT)
    args = parser.parse_args()

    reports = base.report_documents()
    if len(reports) < 8:
        raise RuntimeError(f"Only {len(reports)} recurring quarterly Award of Contracts reports discovered")

    session = requests.Session()
    session.headers["User-Agent"] = base.UA
    report_status = []
    alternatives = []
    changed_urls = 0

    for original in reports:
        resolved, resolution = resolve_report(session, original)
        meta, rows = base.parse_report(session, resolved)
        annotate(meta, rows, original, resolved, resolution)
        if original.get("url") != resolved.get("url"):
            changed_urls += 1
        report_status.append(meta)
        alternatives.extend(rows)
        print(
            f"{original['document_id']} {meta['report_period']}: alternatives={len(rows)} "
            f"value={meta['parsed_alternative_value']:.2f} published_count={meta['alternative_count']} "
            f"published_value={meta['alternative_value']} schema={meta['source_schema']} resolution={resolution}"
        )

    keys = set()
    for row in alternatives:
        key = (row["report_document_id"], row["source_page"], row["source_table"], row["source_row"])
        if key in keys:
            raise RuntimeError(f"Duplicate source locator across final artifact: {key}")
        keys.add(key)

    exact_threshold_rows = sum(1 for row in alternatives if abs(row["award_value"] - 50_000) <= 0.005)
    payload = {
        "metadata": {
            "dataset_status": "official_quarterly_alternative_procurement_report_sections",
            "parser_version": base.PARSER_VERSION,
            "generated_at": base.now(),
            "report_count": len(report_status),
            "alternative_procurement_rows": len(alternatives),
            "alternative_procurement_value": round(sum(row["award_value"] for row in alternatives), 2),
            "alternative_reporting_threshold_wording": "awards exceeding $50,000",
            "source_rows_at_exact_threshold": exact_threshold_rows,
            "reports_with_replaced_attachment_url": changed_urls,
            "attachment_resolution": (
                "Checked-in eSCRIBE attachment URLs are used first. If one no longer serves a PDF, the owning "
                "checked-in agenda URL is re-read and exactly one filestream attachment with an exact visible-title "
                "match is required. Both historical graph URL and live resolved URL are retained."
            ),
            "threshold_handling": (
                "Rows at exactly $50,000 are retained when HRM includes them inside the report-controlled "
                "Alternative Procurement appendix; this preserves exact reconciliation to the source report."
            ),
            "is_accounts_payable_ledger": False,
            "is_complete_procurement_ledger": False,
            "is_final_paid_value": False,
            "note": (
                "HRM quarterly Award of Contracts report evidence. Records are rows placed by HRM inside the "
                "controlled Alternative Awards / Alternative Procurement appendix section. The literal source "
                "procurement type is retained separately because report-section membership and the row's type "
                "field are not always identical. This is not an accounts-payable ledger, does not contain every "
                "purchase or payment, and must not be combined with public-tender award values without preserving "
                "source and classification boundaries."
            ),
        },
        "reports": report_status,
        "alternative_procurement": alternatives,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(
        f"Wrote {len(alternatives)} report-controlled alternative-procurement rows across {len(report_status)} reports; "
        f"{changed_urls} report attachment URL(s) resolved from the live owning agenda"
    )


if __name__ == "__main__":
    main()
