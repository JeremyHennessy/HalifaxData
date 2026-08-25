#!/usr/bin/env python3
import json, sys
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
            warnings.append(f'row {i}: source-reported total mismatch for {r["name"]} {r["fiscal_year_end"]}: delta {delta:+.2f}')
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

if warnings:
    print('DATA VALIDATION WARNINGS',file=sys.stderr)
    print('\n'.join(warnings[:100]),file=sys.stderr)
if errors:
    print('DATA VALIDATION FAILED',file=sys.stderr)
    print('\n'.join(errors[:100]),file=sys.stderr)
    sys.exit(1)
print(f'validated {len(records)} compensation rows and {len(source_ids)} sources with {len(warnings)} source-reported arithmetic warnings')
