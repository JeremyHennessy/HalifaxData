#!/usr/bin/env python3
"""Fail-closed validation for Build 005 domain artifacts.

This is intentionally separate from validate_data.py, which remains authoritative
for compensation and the current Build 004 budget/audited-actual contract.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / 'data/generated'
errors: list[str] = []
warnings: list[str] = []

sources = json.loads((ROOT / 'data/sources.json').read_text(encoding='utf-8'))
source_ids = {s.get('id') for s in sources.get('sources', []) if s.get('id')}
if len(source_ids) < 46:
    errors.append(f'source registry has {len(source_ids)} ids; expected at least 46 after Build 005 integration')

def load(name: str) -> dict:
    path = GEN / name
    if not path.exists():
        errors.append(f'missing generated artifact: {name}')
        return {'metadata': {}, 'records': []}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'{name}: invalid JSON: {exc}')
        return {'metadata': {}, 'records': []}
    if not isinstance(payload, dict) or not isinstance(payload.get('metadata', {}), dict) or not isinstance(payload.get('records', []), list):
        errors.append(f'{name}: expected object with metadata object and records array')
        return {'metadata': {}, 'records': []}
    return payload

def require_source(name: str, index: int, row: dict):
    sid = row.get('source_id')
    if not sid or sid not in source_ids:
        errors.append(f'{name} row {index}: unresolved source_id {sid!r}')

def metadata_count(name: str, payload: dict, key: str = 'records'):
    expected = payload.get('metadata', {}).get(key)
    actual = len(payload.get('records', []))
    if expected is not None and expected != actual:
        errors.append(f'{name}: metadata.{key}={expected} != actual {actual}')

# Procurement: public tender awards, not AP transactions.
proc = load('procurement.json'); metadata_count('procurement.json', proc)
prows = proc['records']
if len(prows) < 100:
    errors.append(f'procurement.json: only {len(prows)} rows')
seen = set()
for i, row in enumerate(prows):
    require_source('procurement.json', i, row)
    for key in ('award_id', 'vendor_name', 'entity'):
        if not row.get(key): errors.append(f'procurement.json row {i}: missing {key}')
    key = (row.get('award_id'), row.get('vendor_name'), row.get('awarded_date'), row.get('original_award_value'))
    if key in seen: errors.append(f'procurement.json row {i}: duplicate award tuple {key}')
    seen.add(key)
if 'accounts-payable' not in str(proc.get('metadata', {}).get('note', '')).lower() and 'accounts payable' not in str(proc.get('metadata', {}).get('note', '')).lower():
    warnings.append('procurement.json metadata note does not explicitly mention accounts-payable scope limitation')

# Capital: official layer is historical; history augmentation may add additional historical records.
capital = load('capital.json'); metadata_count('capital.json', capital)
crows = capital['records']
if len(crows) < 50: errors.append(f'capital.json: only {len(crows)} rows')
for i, row in enumerate(crows):
    require_source('capital.json', i, row)
    if not (row.get('project_id') or row.get('project_code') or row.get('project_name')):
        errors.append(f'capital.json row {i}: no project identifier/name')
    status = str(row.get('status', '')).lower()
    source_status = str(row.get('source_status', '')).lower()
    if row.get('source_id') == 'hrm-open-capital' and 'histor' not in status and 'histor' not in source_status and not capital.get('metadata', {}).get('historical'):
        errors.append(f'capital.json row {i}: HRM open-capital row lacks historical scope marker')

# Historical budget is separate from current Build 004 budget.json.
bhist = load('budget_history.json'); metadata_count('budget_history.json', bhist)
brows = bhist['records']
if len(brows) < 10: errors.append(f'budget_history.json: only {len(brows)} rows')
for i, row in enumerate(brows):
    require_source('budget_history.json', i, row)
    if not row.get('source_page'):
        errors.append(f'budget_history.json row {i}: missing source_page')
    if row.get('source_id', '').startswith('hrm-budget-') and 'source_status' not in row:
        warnings.append(f'budget_history.json row {i}: pre-Build-005 row lacks source_status; regenerate before merge')
        break

# Audited financial history.
financials = load('financials.json'); metadata_count('financials.json', financials)
frows = financials['records']
if len(frows) < 100: errors.append(f'financials.json: only {len(frows)} rows')
for i, row in enumerate(frows):
    require_source('financials.json', i, row)
    for key in ('fiscal_year_end', 'line_item', 'source_page'):
        if row.get(key) in (None, ''): errors.append(f'financials.json row {i}: missing {key}')
    if row.get('source_unit_multiplier') not in (1, 1000):
        errors.append(f'financials.json row {i}: invalid source_unit_multiplier {row.get("source_unit_multiplier")}')

# Council meeting index.
council = load('council.json'); metadata_count('council.json', council)
meetings = council['records']
if len(meetings) < 50: errors.append(f'council.json: only {len(meetings)} meetings')
meeting_ids = set()
for i, row in enumerate(meetings):
    require_source('council.json', i, row)
    mid = row.get('meeting_id')
    if not mid: errors.append(f'council.json row {i}: missing meeting_id')
    elif mid in meeting_ids: errors.append(f'council.json row {i}: duplicate meeting_id {mid}')
    meeting_ids.add(mid)

# Council attachment graph: evidence/search aids only.
docs = load('council_documents.json')
drows = docs['records']
if len(drows) < 100: errors.append(f'council_documents.json: only {len(drows)} document edges')
edges = set()
for i, row in enumerate(drows):
    require_source('council_documents.json', i, row)
    edge = (row.get('meeting_id'), row.get('document_id'))
    if not all(edge): errors.append(f'council_documents.json row {i}: missing meeting/document id')
    elif edge in edges: errors.append(f'council_documents.json row {i}: duplicate meeting-document edge {edge}')
    edges.add(edge)
    if not row.get('url'): errors.append(f'council_documents.json row {i}: missing document URL')
if 'search aids' not in str(docs.get('metadata', {}).get('note', '')).lower():
    errors.append('council_documents.json: metadata must state finance tags are search aids')

# Quarterly/report-level spending summaries, explicitly not transactions/AP ledger.
spending = load('spending.json'); metadata_count('spending.json', spending)
srows = spending['records']
if not srows: errors.append('spending.json has no records')
if spending.get('metadata', {}).get('is_transaction_ledger') is not False:
    errors.append('spending.json: metadata.is_transaction_ledger must be false')
if 'not a complete transaction-level' not in str(spending.get('metadata', {}).get('note', '')).lower():
    errors.append('spending.json: metadata must preserve transaction-ledger limitation')
for i, row in enumerate(srows):
    require_source('spending.json', i, row)
    if row.get('granularity') != 'official_summary_table_row':
        errors.append(f'spending.json row {i}: invalid granularity {row.get("granularity")!r}')
    for key in ('record_type', 'posting_date', 'amount'):
        if row.get(key) in (None, ''): errors.append(f'spending.json row {i}: missing {key}')

# External benchmarks/funding require explicit scope.
for filename in ('benchmarks.json', 'external_funding.json'):
    payload = load(filename); metadata_count(filename, payload)
    if not payload['records']: warnings.append(f'{filename}: zero records')
    scope_counts = Counter()
    for i, row in enumerate(payload['records']):
        require_source(filename, i, row)
        scope = row.get('scope')
        if scope not in {'hrm', 'regional_type_comparator', 'province_program_context'}:
            errors.append(f'{filename} row {i}: invalid/missing scope {scope!r}')
        scope_counts[scope] += 1
    if payload.get('metadata', {}).get('hrm_records') is not None and payload['metadata']['hrm_records'] != scope_counts['hrm']:
        errors.append(f'{filename}: metadata.hrm_records mismatch')

# Acquisition/index artifacts must remain structurally readable if present.
for filename in ('source_acquisition.json', 'domain_ingestion_status.json'):
    path = GEN / filename
    if path.exists():
        try: json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc: errors.append(f'{filename}: invalid JSON: {exc}')

print('DOMAIN COVERAGE')
print(f'sources={len(source_ids)} procurement={len(prows)} capital={len(crows)} budget_history={len(brows)} financials={len(frows)} council={len(meetings)} council_docs={len(drows)} spending={len(srows)}')
if warnings:
    print('DOMAIN VALIDATION WARNINGS', file=sys.stderr)
    print('\n'.join(warnings[:100]), file=sys.stderr)
if errors:
    print('DOMAIN VALIDATION FAILED', file=sys.stderr)
    print('\n'.join(errors[:100]), file=sys.stderr)
    sys.exit(1)
print(f'validated Build 005 domain contracts with {len(warnings)} warning(s)')
