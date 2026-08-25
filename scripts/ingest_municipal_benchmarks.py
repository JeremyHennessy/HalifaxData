#!/usr/bin/env python3
"""Pull Nova Scotia municipal machine datasets with fail-closed paging and scope rules."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'data/sources.json'
OUT = ROOT / 'data/generated'
UA = 'HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)'
PARSER_VERSION = 'build005-municipal-v2'
PAGE_SIZE = 5000

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


def socrata_count(session: requests.Session, url: str) -> int:
    response = session.get(url, params={'$select': 'count(*)'}, timeout=120)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, list) or len(body) != 1 or not isinstance(body[0], dict):
        raise RuntimeError(f'count query returned unexpected shape: {type(body).__name__}')
    raw = body[0].get('count')
    try:
        count = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'count query returned non-integer count {raw!r}') from exc
    if count < 1:
        raise RuntimeError(f'count query returned {count}; refusing to publish an empty source')
    return count


def fetch_all_rows(session: requests.Session, url: str) -> tuple[list[dict], list[dict], int]:
    expected = socrata_count(session, url)
    rows: list[dict] = []
    page_stats: list[dict] = []
    offset = 0
    while offset < expected:
        response = session.get(
            url,
            params={'$limit': PAGE_SIZE, '$offset': offset, '$order': ':id'},
            timeout=120,
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise RuntimeError(f'page offset {offset}: expected list, got {type(page).__name__}')
        if not page:
            raise RuntimeError(f'page offset {offset}: source ended before advertised count {expected}')
        if any(not isinstance(row, dict) for row in page):
            raise RuntimeError(f'page offset {offset}: non-object row returned')
        rows.extend(page)
        page_stats.append({'offset': offset, 'returned': len(page)})
        offset += len(page)
        if len(page) > PAGE_SIZE:
            raise RuntimeError(f'page offset {offset}: returned {len(page)} rows > requested {PAGE_SIZE}')
    if len(rows) != expected:
        raise RuntimeError(f'paged retrieval returned {len(rows)} rows, source advertised {expected}')
    return rows, page_stats, expected


def scope_for(selection_mode: str) -> str:
    if selection_mode == 'explicit_hrm_identity':
        return 'hrm'
    if selection_mode == 'regional_type_comparator':
        return 'regional_type_comparator'
    return 'province_program_context'


def main():
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    by_id = {source['id']: source for source in registry['sources']}
    session = requests.Session()
    session.headers['User-Agent'] = UA

    facts: list[dict] = []
    funding: list[dict] = []
    source_status: list[dict] = []
    failures: list[str] = []

    for source_id, dataset_type in DATASETS.items():
        source = by_id.get(source_id)
        if not source:
            failures.append(f'{source_id}: missing registry entry')
            continue
        try:
            raw, pages, expected = fetch_all_rows(session, source['url'])
            nonempty = nonempty_rows(raw)
            if len(nonempty) != len(raw):
                raise RuntimeError(f'{len(raw) - len(nonempty)} empty/non-object rows returned')
            selected, selection_mode, note = classify(source_id, raw)
            if not selected:
                raise RuntimeError(f'scope rule {selection_mode} selected zero rows')
            scope = scope_for(selection_mode)
            for index, row in enumerate(selected):
                identity = hrm_identity(row)
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
            source_status.append({
                'source_id': source_id,
                'status': 'ok',
                'downloaded_rows': len(raw),
                'advertised_rows': expected,
                'selected_rows': len(selected),
                'selection_mode': selection_mode,
                'page_size': PAGE_SIZE,
                'pages': pages,
                'note': note,
            })
            print(f'{source_id}: advertised={expected} downloaded={len(raw)} selected={len(selected)} pages={len(pages)}')
        except Exception as exc:
            failures.append(f'{source_id}: {type(exc).__name__}: {exc}')

    if failures:
        raise RuntimeError('Municipal benchmark/funding refresh failed closed: ' + ' | '.join(failures))
    if len(source_status) != len(DATASETS):
        raise RuntimeError(f'Only {len(source_status)}/{len(DATASETS)} configured sources completed')

    generated_at = now()
    benchmarks = {
        'metadata': {
            'dataset_status': 'complete_paged_source_refresh',
            'parser_version': PARSER_VERSION,
            'generated_at': generated_at,
            'records': len(facts),
            'hrm_records': sum(row['scope'] == 'hrm' for row in facts),
            'comparator_records': sum(row['scope'] != 'hrm' for row in facts),
            'source_status': source_status,
            'note': (
                'All configured Socrata sources are count-checked and paged to the advertised row count. '
                'HRM-specific rows and external comparator rows remain explicitly scoped.'
            ),
        },
        'records': facts,
    }
    external_funding = {
        'metadata': {
            'dataset_status': 'complete_paged_source_refresh',
            'parser_version': PARSER_VERSION,
            'generated_at': generated_at,
            'records': len(funding),
            'hrm_records': sum(row['scope'] == 'hrm' for row in funding),
            'context_records': sum(row['scope'] != 'hrm' for row in funding),
            'source_status': source_status,
            'note': (
                'Only scope=hrm rows are recipient-level HRM facts. Province-program rows remain '
                'context only and are never attributed to Halifax.'
            ),
        },
        'records': funding,
    }

    for path, payload in (
        (OUT / 'benchmarks.json', benchmarks),
        (OUT / 'external_funding.json', external_funding),
    ):
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        tmp.replace(path)

    print(
        f"municipal benchmarks={len(facts)} (HRM={benchmarks['metadata']['hrm_records']}); "
        f"external funding={len(funding)} (HRM={external_funding['metadata']['hrm_records']})"
    )


if __name__ == '__main__':
    main()
