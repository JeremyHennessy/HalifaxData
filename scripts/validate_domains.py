#!/usr/bin/env python3
"""Structural validation for Build 003 domain artifacts.

Hard gates apply where upstream sources are stable enough to support them. Parser
failures in one domain remain isolated from valid outputs in other domains, but a
checked-in artifact may not silently collapse to an obviously incomplete shape.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "data" / "generated"
registry = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
source_ids = {row["id"] for row in registry["sources"]}
errors = []
warnings = []


def load(name):
    path = GEN / name
    if not path.exists():
        errors.append(f"missing generated artifact: {name}")
        return {"metadata": {}, "records": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{name}: invalid JSON: {exc}")
        return {"metadata": {}, "records": []}


def rows(name):
    data = load(name)
    return data, data.get("records", []) if isinstance(data, dict) else []


acq, acq_rows = rows("source_acquisition.json")
acq_ids = {row.get("source_id") for row in acq_rows}
missing_acq = source_ids - acq_ids
if missing_acq:
    errors.append(f"source acquisition manifest missing registry ids: {sorted(missing_acq)}")
failed = [row for row in acq_rows if row.get("acquisition_status") in {"error", "http_error"}]
if failed:
    warnings.append("source acquisition failures: " + ", ".join(f"{r.get('source_id')}={r.get('http_status') or r.get('error')}" for r in failed))

proc, proc_rows = rows("procurement.json")
if len(proc_rows) < 100:
    errors.append(f"procurement.json unexpectedly small: {len(proc_rows)} rows")
for i, row in enumerate(proc_rows):
    if row.get("source_id") not in source_ids:
        errors.append(f"procurement row {i}: unknown source_id {row.get('source_id')}")
    if not row.get("award_id"):
        errors.append(f"procurement row {i}: missing award_id")

capital, capital_rows = rows("capital.json")
if len(capital_rows) < 50:
    errors.append(f"capital.json unexpectedly small: {len(capital_rows)} rows")
for i, row in enumerate(capital_rows):
    if row.get("source_id") not in source_ids:
        errors.append(f"capital row {i}: unknown source_id {row.get('source_id')}")

budget, budget_rows = rows("budget.json")
if len(budget_rows) < 10:
    errors.append(f"budget.json unexpectedly small: {len(budget_rows)} normalized rows")
for i, row in enumerate(budget_rows):
    if row.get("source_id") not in source_ids:
        errors.append(f"budget row {i}: unknown source_id {row.get('source_id')}")
    if not row.get("source_page"):
        errors.append(f"budget row {i}: missing source_page")

financials, fin_rows = rows("financials.json")
if len(fin_rows) < 10:
    errors.append(f"financials.json unexpectedly small: {len(fin_rows)} rows")
for i, row in enumerate(fin_rows):
    if row.get("source_id") not in source_ids:
        errors.append(f"financial row {i}: unknown source_id {row.get('source_id')}")

council, council_rows = rows("council.json")
if len(council_rows) < 50:
    errors.append(f"council.json unexpectedly small: {len(council_rows)} meetings")
seen_meetings = set()
for i, row in enumerate(council_rows):
    mid = row.get("meeting_id")
    if not mid:
        errors.append(f"council row {i}: missing meeting_id")
    elif mid in seen_meetings:
        errors.append(f"council row {i}: duplicate meeting_id {mid}")
    seen_meetings.add(mid)
    if row.get("source_id") != "hrm-escribe":
        errors.append(f"council row {i}: unexpected source_id {row.get('source_id')}")
    if not row.get("start_date") or not row.get("meeting_type"):
        errors.append(f"council row {i}: missing start_date/meeting_type")
if council_rows and not any(row.get("agenda_html_url") or row.get("agenda_pdf_url") for row in council_rows):
    errors.append("council.json contains no agenda document links")

council_docs, council_doc_rows = rows("council_documents.json")
if len(council_doc_rows) < 100:
    errors.append(f"council_documents.json unexpectedly small: {len(council_doc_rows)} meeting-document edges")
seen_edges = set()
finance_tagged = 0
for i, row in enumerate(council_doc_rows):
    mid = row.get("meeting_id")
    did = str(row.get("document_id") or "")
    title = str(row.get("title") or "").strip()
    url = str(row.get("url") or "")
    edge = (mid, did)
    if not mid or mid not in seen_meetings:
        errors.append(f"council document row {i}: unknown/missing meeting_id {mid}")
    if not did:
        errors.append(f"council document row {i}: missing document_id")
    elif edge in seen_edges:
        errors.append(f"council document row {i}: duplicate meeting/document edge {edge}")
    seen_edges.add(edge)
    if not title:
        errors.append(f"council document row {i}: missing title")
    if not url.startswith("https://pub-halifax.escribemeetings.com/") or "DocumentId=" not in url:
        errors.append(f"council document row {i}: invalid eSCRIBE document URL")
    elif did and f"DocumentId={did}" not in url:
        errors.append(f"council document row {i}: document_id does not match URL ({did})")
    if row.get("source_id") != "hrm-escribe":
        errors.append(f"council document row {i}: unexpected source_id {row.get('source_id')}")
    if row.get("finance_relevant"):
        finance_tagged += 1
if council_doc_rows and finance_tagged < 20:
    errors.append(f"council_documents.json has too few finance-tagged attachment edges: {finance_tagged}")

# These are discovery-health warnings rather than hard gates because attachment
# titles can legitimately change while the underlying meeting/document graph is
# still valid.
finance_titles = [str(row.get("title") or "").lower() for row in council_doc_rows if row.get("finance_relevant")]
if council_doc_rows and not any("2026" in title and "budget" in title for title in finance_titles):
    warnings.append("Council attachment graph did not surface a finance-tagged 2026 budget title; inspect agenda-title changes")
if council_doc_rows and not any("award" in title and "contract" in title for title in finance_titles):
    warnings.append("Council attachment graph did not surface an Award of Contracts title; inspect agenda-title changes")

status, status_rows = rows("domain_ingestion_status.json")
for row in status_rows:
    if row.get("status") == "error":
        warnings.append(f"domain parser failed but was isolated: {row.get('domain')} -> {row.get('error')}")

print(f"registry={len(source_ids)} acquisition={len(acq_rows)} procurement={len(proc_rows)} capital={len(capital_rows)} budget={len(budget_rows)} financials={len(fin_rows)} council={len(council_rows)} council_documents={len(council_doc_rows)} finance_tagged={finance_tagged}")
if warnings:
    print("DOMAIN VALIDATION WARNINGS", file=sys.stderr)
    for warning in warnings:
        print(warning, file=sys.stderr)
if errors:
    print("DOMAIN VALIDATION FAILED", file=sys.stderr)
    for error in errors[:100]:
        print(error, file=sys.stderr)
    sys.exit(1)
print("domain validation passed")
