#!/usr/bin/env python3
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
errors=[]; warnings=[]
comp=json.loads((ROOT/'data/generated/compensation.json').read_text())
sources=json.loads((ROOT/'data/sources.json').read_text())
source_ids={s['id'] for s in sources['sources']}
metadata=comp.get('metadata',{})
records=comp.get('records',[])
seen=set()

for i,r in enumerate(records):
    req=['fiscal_year_end','entity','name','person_key','wages','benefits','total','source_id']
    missing=[k for k in req if k not in r]
    if missing:
        errors.append(f'row {i}: missing {missing}')
        continue
    if r['source_id'] not in source_ids:
        errors.append(f'row {i}: unknown source {r["source_id"]}')
    if r['total'] < 100000:
        errors.append(f'row {i}: total below disclosure threshold: {r["total"]}')
    if r['source_id'].startswith('hrm-comp-'):
        try:
            source_year=int(r['source_id'].rsplit('-',1)[1])
            if r['fiscal_year_end'] != source_year:
                errors.append(f'row {i}: year/source mismatch {r["fiscal_year_end"]} vs {r["source_id"]}')
        except ValueError:
            errors.append(f'row {i}: malformed compensation source id {r["source_id"]}')
    delta=round(r['total']-(r['wages']+r['benefits']),2)
    if abs(delta)>1.05:
        flags=r.get('validation_flags',[])
        recorded_delta=r.get('source_total_delta')
        if 'reported_total_mismatch' not in flags or recorded_delta is None:
            errors.append(f'row {i}: untagged wages + benefits != total for {r["name"]} {r["fiscal_year_end"]}')
        elif abs(recorded_delta-delta)>0.01:
            errors.append(f'row {i}: source_total_delta does not match reported fields for {r["name"]} {r["fiscal_year_end"]}')
        else:
            warnings.append(f'comp row {i}: source-reported total mismatch for {r["name"]} {r["fiscal_year_end"]}: delta {delta:+.2f}')
    key=(r['fiscal_year_end'],r['entity'],r['person_key'],r['total'])
    if key in seen:
        errors.append(f'row {i}: duplicate {key}')
    seen.add(key)

if records:
    actual_years=[r['fiscal_year_end'] for r in records if 'fiscal_year_end' in r]
    if metadata.get('min_year') != min(actual_years):
        errors.append(f'metadata min_year {metadata.get("min_year")} != actual {min(actual_years)}')
    if metadata.get('max_year') != max(actual_years):
        errors.append(f'metadata max_year {metadata.get("max_year")} != actual {max(actual_years)}')
else:
    errors.append('compensation dataset has no records')

status=metadata.get('dataset_status')
if status not in {'partial_verified_seed','automated_full_extraction'}:
    errors.append(f'unknown dataset_status {status!r}')

if status == 'automated_full_extraction':
    configured={s['id'] for s in sources['sources'] if s['id'].startswith('hrm-comp-') and s.get('status')=='ready'}
    actual_counts=Counter(r['source_id'] for r in records)
    hrm_counts=Counter(r['source_id'] for r in records if r['entity']=='Halifax Regional Municipality')
    discrepancy_counts=Counter(r['source_id'] for r in records if 'reported_total_mismatch' in r.get('validation_flags',[]))
    entity_counts=defaultdict(Counter)
    for r in records:
        entity_counts[r['source_id']][r['entity']]+=1

    stats=metadata.get('source_stats')
    if not isinstance(stats,list):
        errors.append('automated extraction missing metadata.source_stats list')
        stats=[]
    stats_by_id={s.get('source_id'):s for s in stats if isinstance(s,dict) and s.get('source_id')}
    if len(stats_by_id) != len(stats):
        errors.append('metadata.source_stats contains duplicate or malformed source entries')

    actual_comp_sources={sid for sid in actual_counts if sid.startswith('hrm-comp-')}
    if actual_comp_sources != configured:
        errors.append(f'configured compensation sources {sorted(configured)} != actual {sorted(actual_comp_sources)}')
    if set(stats_by_id) != configured:
        errors.append(f'metadata source_stats ids {sorted(stats_by_id)} != configured {sorted(configured)}')

    for sid in sorted(configured):
        stat=stats_by_id.get(sid,{})
        if actual_counts[sid] < 25:
            errors.append(f'{sid}: only {actual_counts[sid]} total rows')
        if hrm_counts[sid] < 25:
            errors.append(f'{sid}: only {hrm_counts[sid]} HRM rows')
        if stat.get('records') != actual_counts[sid]:
            errors.append(f'{sid}: metadata records {stat.get("records")} != actual {actual_counts[sid]}')
        if stat.get('hrm_records') != hrm_counts[sid]:
            errors.append(f'{sid}: metadata hrm_records {stat.get("hrm_records")} != actual {hrm_counts[sid]}')
        if stat.get('source_arithmetic_discrepancies',0) != discrepancy_counts[sid]:
            errors.append(f'{sid}: metadata source_arithmetic_discrepancies {stat.get("source_arithmetic_discrepancies",0)} != actual {discrepancy_counts[sid]}')

    actual_discrepancies=sum(discrepancy_counts.values())
    if metadata.get('source_arithmetic_discrepancies') != actual_discrepancies:
        errors.append(f'metadata source_arithmetic_discrepancies {metadata.get("source_arithmetic_discrepancies")} != actual {actual_discrepancies}')
    if sum(actual_counts[sid] for sid in configured) != len(records):
        errors.append('automated extraction contains records outside configured compensation sources')

    print('COMPENSATION SOURCE COVERAGE')
    for sid in sorted(configured):
        entities=', '.join(f'{entity}={count}' for entity,count in sorted(entity_counts[sid].items()))
        print(f'{sid}: total={actual_counts[sid]}, HRM={hrm_counts[sid]}, discrepancies={discrepancy_counts[sid]}; {entities}')

# Build 004 budget validation is optional until the generated artifact exists, but once it
# exists the contract is strict. Source-reported arithmetic discrepancies are warnings only
# when their independently derived deltas/percentages and flags agree exactly.
budget_path=ROOT/'data/generated/budget.json'
if budget_path.exists():
    budget=json.loads(budget_path.read_text())
    bmeta=budget.get('metadata',{})
    brows=budget.get('records',[])
    service=[r for r in brows if r.get('record_type')=='service_area_budget']
    audited=[r for r in brows if r.get('record_type')=='audited_psas']
    unknown=[r for r in brows if r.get('record_type') not in {'service_area_budget','audited_psas'}]

    if bmeta.get('dataset_status')!='automated_structured_extraction':
        errors.append(f'budget: unknown dataset_status {bmeta.get("dataset_status")!r}')
    expected_budget_sources={'hrm-budget-2025-26','hrm-financials-2025'}
    if set(bmeta.get('source_ids',[])) != expected_budget_sources:
        errors.append(f'budget: metadata source_ids {bmeta.get("source_ids")} != {sorted(expected_budget_sources)}')
    if not expected_budget_sources.issubset(source_ids):
        errors.append('budget: required source IDs are missing from source registry')
    if unknown:
        errors.append(f'budget: {len(unknown)} records have unknown record_type')
    if len(service)!=104:
        errors.append(f'budget: expected 104 service-area rows, found {len(service)}')
    if sum(not r.get('is_total') for r in service)!=86:
        errors.append(f'budget: expected 86 service-area detail rows, found {sum(not r.get("is_total") for r in service)}')
    if sum(bool(r.get('is_total')) for r in service)!=18:
        errors.append(f'budget: expected 18 Net Total rows, found {sum(bool(r.get("is_total")) for r in service)}')
    if len(audited)!=20:
        errors.append(f'budget: expected 20 audited rows, found {len(audited)}')
    if len(brows)!=len(service)+len(audited):
        errors.append('budget: record partition does not cover all rows')

    count_checks={
        'service_area_record_count':len(service),
        'service_area_detail_count':sum(not r.get('is_total') for r in service),
        'business_unit_count':sum(bool(r.get('is_total')) for r in service),
        'audited_record_count':len(audited),
    }
    for field,actual in count_checks.items():
        if bmeta.get(field)!=actual:
            errors.append(f'budget: metadata {field} {bmeta.get(field)} != actual {actual}')

    alias_contract={
        'Infrastructure Maintenance & Operatons':('Infrastructure Maintenance & Operations','same_source_section_heading'),
        'Government Relations & Externa':('Government Relations & External Affairs','same_source_section_heading'),
        'Information Technology/Collecti':('Information Technology/Collections','prior_official_budget_label'),
    }
    normalized_count=0
    service_seen=set()
    discrepancy_rows=0; delta_mismatches=0; pct_mismatches=0
    for i,r in enumerate(service):
        req=['fiscal_year','fiscal_year_end','business_unit','service_area','source_service_area_label','prior_actual','prior_budget','projection','current_budget','is_total','source_id','pdf_page']
        missing=[k for k in req if k not in r]
        if missing:
            errors.append(f'budget service row {i}: missing {missing}')
            continue
        if r['source_id']!='hrm-budget-2025-26':
            errors.append(f'budget service row {i}: wrong source {r["source_id"]}')
        if r['fiscal_year']!='2025/26' or r['fiscal_year_end']!=2026:
            errors.append(f'budget service row {i}: wrong fiscal period {r.get("fiscal_year")}/{r.get("fiscal_year_end")}')
        key=(r['business_unit'],r['service_area'])
        if key in service_seen:
            errors.append(f'budget service row {i}: duplicate canonical key {key}')
        service_seen.add(key)
        if bool(r['is_total']) != (r['service_area']=='Net Total'):
            errors.append(f'budget service row {i}: is_total inconsistent for {key}')

        raw=r['source_service_area_label']
        if raw in alias_contract:
            normalized_count+=1
            expected_label,expected_basis=alias_contract[raw]
            if r['service_area']!=expected_label:
                errors.append(f'budget service row {i}: normalized label {r["service_area"]!r} != {expected_label!r}')
            if r.get('label_normalization_basis')!=expected_basis or not r.get('label_normalization_evidence'):
                errors.append(f'budget service row {i}: normalization provenance missing/incorrect for {raw!r}')
        else:
            if r['service_area']!=raw:
                errors.append(f'budget service row {i}: undocumented label normalization {raw!r} -> {r["service_area"]!r}')
            if 'label_normalization_basis' in r or 'label_normalization_evidence' in r:
                errors.append(f'budget service row {i}: normalization metadata present without approved alias for {raw!r}')

        flags=r.get('validation_flags',[])
        has_flag=bool(flags)
        if has_flag: discrepancy_rows+=1
        prior=r.get('prior_budget'); current=r.get('current_budget')
        if prior is not None and current is not None:
            derived=current-prior
            if r.get('derived_budget_change')!=derived:
                errors.append(f'budget service row {i}: derived change {r.get("derived_budget_change")} != {derived}')
            source_delta=r.get('source_reported_budget_change')
            mismatch=(source_delta is not None and source_delta!=derived)
            if mismatch:
                delta_mismatches+=1
                if 'reported_budget_change_mismatch' not in flags:
                    errors.append(f'budget service row {i}: untagged published change mismatch for {key}')
                if r.get('source_budget_change_delta') != source_delta-derived:
                    errors.append(f'budget service row {i}: source_budget_change_delta incorrect for {key}')
            elif 'reported_budget_change_mismatch' in flags:
                errors.append(f'budget service row {i}: false reported_budget_change_mismatch flag for {key}')

            if prior!=0:
                derived_pct=derived/prior*100
                stored_pct=r.get('derived_budget_change_pct')
                if stored_pct is None or not math.isclose(stored_pct,round(derived_pct,4),abs_tol=0.0001):
                    errors.append(f'budget service row {i}: derived pct incorrect for {key}')
                source_pct=r.get('source_reported_budget_change_pct')
                pct_mismatch=(source_pct is not None and abs(source_pct-derived_pct)>0.11)
                if pct_mismatch:
                    pct_mismatches+=1
                    if 'reported_budget_change_pct_mismatch' not in flags:
                        errors.append(f'budget service row {i}: untagged published pct mismatch for {key}')
                    expected_delta=round(source_pct-derived_pct,4)
                    if r.get('source_budget_change_pct_delta') is None or not math.isclose(r['source_budget_change_pct_delta'],expected_delta,abs_tol=0.0001):
                        errors.append(f'budget service row {i}: source_budget_change_pct_delta incorrect for {key}')
                elif 'reported_budget_change_pct_mismatch' in flags:
                    errors.append(f'budget service row {i}: false reported_budget_change_pct_mismatch flag for {key}')

        if has_flag:
            warnings.append(f'budget row {i}: source-reported budget arithmetic warning for {r["business_unit"]} / {r["service_area"]}: {", ".join(flags)}')

    if normalized_count!=3 or bmeta.get('normalized_service_area_labels')!=normalized_count:
        errors.append(f'budget: normalized service labels metadata/actual mismatch: metadata={bmeta.get("normalized_service_area_labels")} actual={normalized_count}')
    meta_discrepancies={
        'budget_source_arithmetic_discrepancy_rows':discrepancy_rows,
        'budget_source_delta_mismatches':delta_mismatches,
        'budget_source_pct_mismatches':pct_mismatches,
    }
    for field,actual in meta_discrepancies.items():
        if bmeta.get(field)!=actual:
            errors.append(f'budget: metadata {field} {bmeta.get(field)} != actual {actual}')

    budget_controls={
        'Halifax Regional Fire & Emergency':98_189_400,
        'Halifax Regional Police':101_255_700,
        'Halifax Transit':63_462_600,
        'Halifax Public Libraries':28_454_700,
        'Finance & Asset Management':17_971_600,
        'Fiscal Services':-689_347_600,
    }
    totals={r['business_unit']:r['current_budget'] for r in service if r.get('is_total')}
    for unit,expected in budget_controls.items():
        if totals.get(unit)!=expected:
            errors.append(f'budget: control total {unit} {totals.get(unit)} != {expected}')

    audited_seen=set()
    for i,r in enumerate(audited):
        req=['fiscal_year','fiscal_year_end','statement_section','category','budget','actual','prior_actual','source_id','pdf_page','printed_page','source_units']
        missing=[k for k in req if k not in r]
        if missing:
            errors.append(f'audited row {i}: missing {missing}')
            continue
        if r['source_id']!='hrm-financials-2025':
            errors.append(f'audited row {i}: wrong source {r["source_id"]}')
        if r['fiscal_year']!='2024/25' or r['fiscal_year_end']!=2025:
            errors.append(f'audited row {i}: wrong fiscal period')
        if r['source_units']!='thousands_of_cad' or r['pdf_page']!=8 or r['printed_page']!=4:
            errors.append(f'audited row {i}: provenance/unit locator drift')
        key=(r['statement_section'],r['category'])
        if key in audited_seen:
            errors.append(f'audited row {i}: duplicate {key}')
        audited_seen.add(key)
        if r['budget'] is not None and r['actual'] is not None and r.get('variance')!=r['actual']-r['budget']:
            errors.append(f'audited row {i}: variance incorrect for {key}')
        if 'business_unit' in r or 'service_area' in r:
            errors.append(f'audited row {i}: PSAS row was incorrectly mapped onto budget-book dimensions')

    audited_by_key={(r['statement_section'],r['category']):r for r in audited}
    audited_controls={
        ('revenue','Total revenue'):(1_347_173_000,1_410_626_000),
        ('expense','Total expenses'):(1_338_192_000,1_350_788_000),
        ('surplus','Annual surplus'):(8_981_000,59_838_000),
    }
    for key,(expected_budget,expected_actual) in audited_controls.items():
        row=audited_by_key.get(key)
        if not row:
            errors.append(f'audited: missing control row {key}')
            continue
        if (row.get('budget'),row.get('actual'))!=(expected_budget,expected_actual):
            errors.append(f'audited: control mismatch {key}: {(row.get("budget"),row.get("actual"))}')
    audited_meta_controls={
        'audited_total_revenue_budget':1_347_173_000,
        'audited_total_revenue_actual':1_410_626_000,
        'audited_total_expenses_budget':1_338_192_000,
        'audited_total_expenses_actual':1_350_788_000,
        'audited_annual_surplus_budget':8_981_000,
        'audited_annual_surplus_actual':59_838_000,
    }
    for field,expected in audited_meta_controls.items():
        if bmeta.get(field)!=expected:
            errors.append(f'budget: metadata {field} {bmeta.get(field)} != {expected}')

    print('BUDGET / ACTUALS COVERAGE')
    print(f'budget service rows={len(service)}; details={sum(not r.get("is_total") for r in service)}; business units={sum(bool(r.get("is_total")) for r in service)}; source arithmetic warning rows={discrepancy_rows}; normalized labels={normalized_count}')
    print(f'audited rows={len(audited)}; revenue budget/actual={bmeta.get("audited_total_revenue_budget")}/{bmeta.get("audited_total_revenue_actual")}; expenses budget/actual={bmeta.get("audited_total_expenses_budget")}/{bmeta.get("audited_total_expenses_actual")}')

if warnings:
    print('DATA VALIDATION WARNINGS',file=sys.stderr)
    print('\n'.join(warnings[:100]),file=sys.stderr)
if errors:
    print('DATA VALIDATION FAILED',file=sys.stderr)
    print('\n'.join(errors[:100]),file=sys.stderr)
    sys.exit(1)
budget_note='; budget artifact validated' if budget_path.exists() else '; budget artifact not present'
print(f'validated {len(records)} compensation rows and {len(source_ids)} sources with {len(warnings)} source-reported arithmetic warnings{budget_note}')
