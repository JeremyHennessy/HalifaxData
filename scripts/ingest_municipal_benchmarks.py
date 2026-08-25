#!/usr/bin/env python3
"""Pull Nova Scotia municipal machine datasets with source-specific scope rules.

The collector separates:
1. HRM-specific rows from datasets that explicitly identify a municipality/region,
2. municipality-type comparator rows, and
3. province-wide program context that is not attributed to HRM.

Derived Socrata chart IDs are intentionally not used as row APIs. The registry
points the affected source IDs at verified base datasets instead.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'data/sources.json'
OUT = ROOT / 'data/generated'
UA = 'HalifaxData/0.3 (+https://github.com/JeremyHennessy/HalifaxData)'

DATASETS = {
    'ns-municipal-operating-expenses': 'benchmark_operating_expenses',
    'ns-municipal-operating-revenues': 'benchmark_operating_revenues',
    'ns-municipal-operating-totals': 'benchmark_operating_totals',
    'ns-municipal-consolidated': 'benchmark_consolidated_revenues_expenses',
    'ns-municipal-fci': 'financial_condition_indicators',
    'ns-uniform-assessment-regional': 'uniform_assessment',
    'ns-municipal-funding-programs': 'municipal_funding_programs',
    'ns-municipal-capacity-grants': 'municipal_capacity_grants',
}

HRM_IDENTIFIERS = {
    'hrm',
    'halifax',
    'halifax regional municipality',
    'halifax regional municipal',
}
ENTITY_KEYS = (
    'region', 'municipality', 'municipality_name', 'municipal_unit', 'entity',
    'area_name', 'community', 'name', 'region_name',
)


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm(value):
    return ' '.join(str(value or '').strip().lower().split())


def hrm_identity(row):
    """Return the matching field/value when a row explicitly identifies HRM."""
    for key in ENTITY_KEYS:
        if key not in row:
            continue
        value = norm(row.get(key))
        if value in HRM_IDENTIFIERS or 'halifax regional municipality' in value:
            return key, row.get(key)
    return None


def nonempty_rows(raw):
    return [row for row in raw if isinstance(row, dict) and any(v not in (None, '') for v in row.values())]


def classify(source_id, raw):
    """Return (selected_rows, selection_mode, note)."""
    raw = nonempty_rows(raw)

    if source_id in {
        'ns-municipal-fci',
        'ns-municipal-capacity-grants',
        'ns-uniform-assessment-regional',
        'ns-municipal-operating-totals',
        'ns-municipal-consolidated',
    }:
        selected = [row for row in raw if hrm_identity(row)]
        return selected, 'explicit_hrm_identity', (
            'Rows retained only when a source field explicitly identifies HRM/Halifax Regional Municipality.'
        )

    if source_id in {'ns-municipal-operating-expenses', 'ns-municipal-operating-revenues'}:
        return raw, 'regional_type_comparator', (
            'Dataset is municipality-type aggregate context, not HRM-specific operating facts.'
        )

    if source_id == 'ns-municipal-funding-programs':
        return raw, 'province_program_context', (
            'Program totals are contextual and must not be interpreted as funding received by HRM.'
        )

    selected = [row for row in raw if hrm_identity(row)]
    return selected, 'explicit_hrm_identity', 'Default explicit HRM identity filter.'


def main():
    reg = json.loads(REGISTRY.read_text(encoding='utf-8'))
    by_id = {s['id']: s for s in reg['sources']}
    session = requests.Session()
    session.headers['User-Agent'] = UA

    facts = []
    funding = []
    status = []

    for source_id, dataset_type in DATASETS.items():
        src = by_id.get(source_id)
        if not src:
            status.append({'source_id': source_id, 'status': 'missing_registry'})
            continue
        try:
            response = session.get(src['url'], params={'$limit': 50000}, timeout=120)
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, list):
                raise RuntimeError(f'expected list response, got {type(raw).__name__}')

            nonempty = nonempty_rows(raw)
            selected, selection_mode, note = classify(source_id, raw)
            for index, row in enumerate(selected):
                identity = hrm_identity(row)
                scope = (
                    'hrm'
                    if selection_mode == 'explicit_hrm_identity'
                    else 'regional_type_comparator'
                    if selection_mode == 'regional_type_comparator'
                    else 'province_program_context'
                )
                fact = {
                    'dataset_type': dataset_type,
                    'scope': scope,
                    'source_id': source_id,
                    'raw': row,
                    'source_row_index': index,
                }
                if identity:
                    fact['identity_field'] = identity[0]
                    fact['identity_value'] = identity[1]

                if dataset_type.startswith('municipal_'):
                    funding.append(fact)
                else:
                    facts.append(fact)

            status.append({
                'source_id': source_id,
                'status': 'ok' if nonempty else 'empty_shape',
                'downloaded_rows': len(raw),
                'nonempty_rows': len(nonempty),
                'selected_rows': len(selected),
                'selection_mode': selection_mode,
                'note': note,
            })
        except Exception as exc:
            status.append({
                'source_id': source_id,
                'status': 'error',
                'error': f'{type(exc).__name__}: {exc}',
            })

    benchmarks = {
        'metadata': {
            'generated_at': now(),
            'records': len(facts),
            'hrm_records': sum(r['scope'] == 'hrm' for r in facts),
            'comparator_records': sum(r['scope'] != 'hrm' for r in facts),
            'source_status': status,
            'note': (
                'HRM-specific rows and external comparator rows are explicitly scoped. '
                'Raw API fields are retained until source-specific semantic mappings are verified.'
            ),
        },
        'records': facts,
    }
    extfund = {
        'metadata': {
            'generated_at': now(),
            'records': len(funding),
            'hrm_records': sum(r['scope'] == 'hrm' for r in funding),
            'context_records': sum(r['scope'] != 'hrm' for r in funding),
            'source_status': status,
            'note': (
                'Only scope=hrm rows are recipient-level HRM facts. Province-program rows are '
                'retained strictly as context and are not attributed to Halifax.'
            ),
        },
        'records': funding,
    }

    (OUT / 'benchmarks.json').write_text(
        json.dumps(benchmarks, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    (OUT / 'external_funding.json').write_text(
        json.dumps(extfund, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    print(
        f"municipal benchmarks={len(facts)} (HRM={benchmarks['metadata']['hrm_records']}) "
        f"external funding={len(funding)} (HRM={extfund['metadata']['hrm_records']})"
    )
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()
