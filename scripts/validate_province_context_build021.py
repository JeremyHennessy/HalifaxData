#!/usr/bin/env python3
from __future__ import annotations
import json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ARTIFACT=ROOT/"data/generated/province_context.json"
TAX=ROOT/"data/tax_transparency_2026.json"
EXPECTED=[{"department":"Communities, Culture, Tourism and Heritage","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":30,"amount":1165206.0},{"department":"Education and Early Childhood Development","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":67,"amount":1200000.0},{"department":"Emergency Management","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":77,"amount":135715.68},{"department":"Emergency Management","recipient":"Halifax Regional Municipality","source_section":"other","page":78,"amount":1830099.47},{"department":"Energy","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":81,"amount":636638.7},{"department":"Energy","recipient":"Halifax Regional Water Commission","source_section":"grants_and_contributions","page":81,"amount":67500.0},{"department":"Environment and Climate Change","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":88,"amount":169941.15},{"department":"Justice","recipient":"Halifax Regional Municipality","source_section":"external_secondments","page":146,"amount":102461.66},{"department":"Justice","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":150,"amount":776909.72},{"department":"Justice","recipient":"Halifax Regional Municipality","source_section":"other","page":153,"amount":5320245.34},{"department":"Justice","recipient":"Halifax Regional Water Commission","source_section":"other","page":153,"amount":165269.68},{"department":"Labour, Skills and Immigration","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":179,"amount":55444.0},{"department":"Labour, Skills and Immigration","recipient":"Halifax Regional Water Commission","source_section":"grants_and_contributions","page":179,"amount":39361.0},{"department":"Municipal Affairs","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":200,"amount":80563357.1},{"department":"Municipal Affairs","recipient":"Halifax Regional Water Commission","source_section":"grants_and_contributions","page":200,"amount":1950819.0},{"department":"Natural Resources","recipient":"Halifax Regional Municipality","source_section":"other","page":220,"amount":21156.15},{"department":"Opportunities and Social Development","recipient":"Halifax Regional Municipality","source_section":"grants_and_contributions","page":268,"amount":2789347.17},{"department":"Opportunities and Social Development","recipient":"Halifax Regional Water Commission","source_section":"grants_and_contributions","page":268,"amount":5630.36},{"department":"Public Service","recipient":"Halifax Regional Municipality","source_section":"other","page":322,"amount":297966.36},{"department":"Public Works","recipient":"Halifax Regional Municipality","source_section":"other","page":370,"amount":3423237.46},{"department":"Public Works","recipient":"Halifax Regional Water Commission","source_section":"other","page":370,"amount":1817566.55}]

def load(p): return json.loads(p.read_text(encoding="utf-8"))
def close(a,b,tol=.01): return math.isclose(float(a),float(b),rel_tol=0,abs_tol=tol)
def fail(msg): raise AssertionError(msg)

def main():
    data,tax=load(ARTIFACT),load(TAX)
    meta=data.get("metadata",{})
    if meta.get("build")!="021" or meta.get("source_basis")!="cash": fail("Build 021 metadata changed")
    for key in ("is_hrm_accounts_payable","is_invoice_level","is_province_wide_complete_extract","creates_investigation_scores"):
        if meta.get(key) is not False: fail(f"Boundary {key} must remain false")
    if meta.get("hrm_payment_fact_count_change")!=0: fail("Provincial context must not create HRM payment facts")
    source={s["id"]:s for s in data.get("sources",[])}
    pa=source.get("ns-public-accounts-2024-25-volume3",{})
    if pa.get("evidence_type")!="cash_basis_accumulated_payee_payments" or pa.get("thresholds",{}).get("other")!=5000: fail("Public Accounts source semantics changed")
    if "ns-budget-2026-27-expense-shares" not in source: fail("Provincial budget source missing")
    rows=data.get("payments",[])
    if len(rows)!=21 or len({r["id"] for r in rows})!=21: fail("Expected 21 unique payment-context rows")
    allowed={"Halifax Regional Municipality","Halifax Regional Water Commission"}
    observed={(r["department"],r["recipient"],r["source_section"],int(r["source_page"])):float(r["amount"]) for r in rows}
    expected={(r["department"],r["recipient"],r["source_section"],int(r["page"])):float(r["amount"]) for r in EXPECTED}
    if set(observed)!=set(expected): fail("Exact department/payee/section/page row set changed")
    for key,value in expected.items():
        if not close(observed[key],value): fail(f"Amount changed for {key}")
    if any(r["recipient"] not in allowed for r in rows): fail("Unexpected payee in Halifax subset")
    summary=data.get("summary",{})
    exact={"payment_rows":21,"departments":12,"recipients":2,"hrm_rows":15,"halifax_water_rows":6}
    for key,value in exact.items():
        if summary.get(key)!=value: fail(f"Summary {key} changed")
    for key,value in {"hrm_amount":98487725.96,"halifax_water_amount":4046146.59,"combined_exact_payee_amount":102533872.55}.items():
        if not close(summary.get(key,0),value): fail(f"Summary {key} changed")
    sections={r["source_section"]:r["amount"] for r in data.get("source_section_totals",[])}
    for key,value in {"grants_and_contributions":89555869.88,"other":12875541.01,"external_secondments":102461.66}.items():
        if not close(sections.get(key,0),value): fail(f"Section total {key} changed")
    if len(data.get("interpretation_boundaries",[]))<6: fail("Interpretation boundaries incomplete")
    alloc=tax.get("nova_scotia_spending_allocation",{})
    if alloc.get("fiscal_year")!="2026-27": fail("Current provincial plan context is not 2026-27")
    shares={r["category"]:r["share_pct"] for r in alloc.get("categories",[])}
    for category,value in {"Health and Wellness":35.5,"Education and Early Childhood Development":12.4}.items():
        if not close(shares.get(category,-1),value,.001): fail(f"Provincial plan share changed for {category}")
    print("Build 021 provincial context validation passed: 21 rows; $102,533,872.55 exact-payee cash-basis context.")

if __name__=="__main__": main()
