#!/usr/bin/env python3
"""Validate Build 022 source-freshness display contract."""
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"data/current_source_refresh_status.json"


def fail(message:str)->None:
    raise SystemExit(f"Build 022 source-status validation failed: {message}")


def main()->None:
    data=json.loads(PATH.read_text(encoding="utf-8"))
    meta=data.get("metadata") or {}
    rows=data.get("domains") or []
    if meta.get("build")!="022" or meta.get("researched_at")!="2026-09-22":
        fail("build/research date is not the accepted September 22 Build 022 state")
    candidate=meta.get("release_candidate") or {}
    if candidate.get("validated_data_commit")!="ec629697d1048b604ee3448e8829d13f86f260a0":
        fail("validated Build 022 data commit changed")
    if candidate.get("controlled_refresh_result")!="success" or candidate.get("domain_monitor_result")!="all seven independent jobs passed":
        fail("release/monitor evidence no longer reports the validated successful runs")
    by={}
    for row in rows:
        domain=row.get("domain")
        if not domain or domain in by:
            fail(f"blank or duplicate domain {domain!r}")
        by[domain]=row
    required={
        "operating_budget","capital_plan","quarterly_financial_reports","procurement_awards",
        "procurement_quarterly_awards","cao_contract_amendments","compensation_disclosure",
        "council_decisions","audited_financial_statements","accounts_payable_vendor_payments",
        "provincial_context",
    }
    if set(by)!=required:
        fail(f"domain set changed: expected {sorted(required)!r}, got {sorted(by)!r}")
    council=by["council_decisions"]
    if council.get("status")!="verified_current" or "1,040 checked decisions" not in str(council.get("production_through")):
        fail("Council freshness does not describe the accepted 1,040-decision release")
    if council.get("verified_current_period")!="2026-08-25 approved Regional Council minutes":
        fail("Council verified period changed")
    if "September 15, 2026" not in str(council.get("current_calendar_boundary")) or "no approved/PostMinutes URL" not in str(council.get("current_calendar_boundary")):
        fail("September 15 draft/approved-minutes boundary is missing")
    procurement=by["procurement_awards"]
    if procurement.get("status")!="verified_new_source":
        fail("live procurement candidate must remain a held-back newer-source state")
    check=str(procurement.get("latest_check") or "")
    if "5,517" not in check or "18 new normalized keys" not in check or "3 checked keys absent" not in check:
        fail("procurement candidate counts changed")
    for domain in ("capital_plan","procurement_quarterly_awards"):
        status=str(by[domain].get("source_transport_status") or "")
        if "blocked_403" not in status:
            fail(f"{domain}: eSCRIBE PDF transport block is not explicit")
        if "checked_artifact_validated" not in status:
            fail(f"{domain}: checked-evidence validity is not explicit")
    ap=by["accounts_payable_vendor_payments"]
    if ap.get("payment_facts_available_to_halifaxdata")!=0 or ap.get("public_transaction_ledger") is not False:
        fail("AP/payment source boundary changed")
    if ap.get("internal_evidence_status")!="verified_internal_transaction_records_exist":
        fail("verified internal AP record evidence was lost")
    provincial=by["provincial_context"]
    if "$102,533,872.55" not in str(provincial.get("latest_check") or ""):
        fail("provincial exact-payee context control changed")
    if "did not verify 2025/26 Public Accounts" not in str(provincial.get("latest_check") or ""):
        fail("provincial freshness boundary is missing")
    q=by["quarterly_financial_reports"]
    if q.get("production_through")!="2025/26 Q3 (period ended December 31, 2025)":
        fail("quarterly-financial checked period changed")
    audited=by["audited_financial_statements"]
    if "1,243" not in str(audited.get("latest_check") or ""):
        fail("audited registered-history reproduction control changed")
    print(json.dumps({
        "status":"ok",
        "researched_at":meta["researched_at"],
        "domains":len(rows),
        "council_decisions":1040,
        "procurement_live_candidate":5517,
        "payment_facts":0,
        "blocked_transport_domains":["capital_plan","procurement_quarterly_awards"],
    },indent=2))


if __name__=="__main__":
    main()
