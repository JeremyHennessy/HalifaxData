#!/usr/bin/env python3
"""Independently validate paged Nova Scotia municipal benchmark/funding artifacts."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / 'data/generated/benchmarks.json'
FUNDING = ROOT / 'data/generated/external_funding.json'
EXPECTED_STATUS = 'complete_paged_source_refresh'
EXPECTED_PARSER = 'build005-municipal-v2'
PAGE_SIZE = 5000
EXPECTED = {
    'ns-municipal-operating-expenses': ('benchmark', 'regional_type_comparator'),
    'ns-municipal-operating-revenues': ('benchmark', 'regional_type_comparator'),
    'ns-municipal-operating-totals': ('benchmark', 'hrm'),
    'ns-municipal-consolidated': ('benchmark', 'hrm'),
    'ns-municipal-fci': ('benchmark', 'hrm'),
    'ns-uniform-assessment-regional': ('benchmark', 'hrm'),
    'ns-municipal-funding-programs': ('funding', 'province_program_context'),
    'ns-municipal-capacity-grants': ('funding', 'hrm'),
}
HRM_IDENTIFIERS = {'hrm', 'halifax', 'halifax regional municipality', 'halifax regional municipal'}
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def norm(value) -> str:
    return ' '.join(str(value or '').strip().lower().split())


def explicit_hrm_identity(row: dict) -> bool:
    field = row.get('identity_field')
    value = row.get('identity_value')
    if not field or value is None:
        return False
    normalized = norm(value)
    return normalized in HRM_IDENTIFIERS or 'halifax regional municipality' in normalized


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f'Missing artifact: {path.relative_to(ROOT)}')
    return json.loads(path.read_text(encoding='utf-8'))


def validate_statuses(metadata: dict, label: str) -> dict[str, dict]:
    if metadata.get('dataset_status') != EXPECTED_STATUS:
        fail(f'{label}: unexpected dataset_status {metadata.get("dataset_status")!r}')
    if metadata.get('parser_version') != EXPECTED_PARSER:
        fail(f'{label}: unexpected parser_version {metadata.get("parser_version")!r}')
    statuses = metadata.get('source_status')
    if not isinstance(statuses, list):
        fail(f'{label}: source_status must be a list')
        return {}
    ids = [item.get('source_id') for item in statuses]
    if set(ids) != set(EXPECTED) or len(ids) != len(EXPECTED):
        fail(f'{label}: source_status must contain all configured sources exactly once')
    by_id = {item.get('source_id'): item for item in statuses if item.get('source_id')}
    for source_id in EXPECTED:
        item = by_id.get(source_id) or {}
        if item.get('status') != 'ok':
            fail(f'{label}/{source_id}: status is not ok')
        advertised = item.get('advertised_rows')
        downloaded = item.get('downloaded_rows')
        if not isinstance(advertised, int) or advertised < 1 or downloaded != advertised:
            fail(f'{label}/{source_id}: downloaded_rows must exactly equal positive advertised_rows')
        if item.get('page_size') != PAGE_SIZE:
            fail(f'{label}/{source_id}: unexpected page_size {item.get("page_size")!r}')
        pages = item.get('pages')
        if not isinstance(pages, list) or not pages:
            fail(f'{label}/{source_id}: pages must be a non-empty list')
            continue
        expected_offset = 0
        page_total = 0
        for page in pages:
            offset = page.get('offset')
            returned = page.get('returned')
            if offset != expected_offset:
                fail(f'{label}/{source_id}: non-contiguous page offset {offset!r}, expected {expected_offset}')
            if not isinstance(returned, int) or returned < 1 or returned > PAGE_SIZE:
                fail(f'{label}/{source_id}: invalid page returned count {returned!r}')
                returned = 0
            expected_offset += returned
            page_total += returned
        if page_total != advertised:
            fail(f'{label}/{source_id}: page total {page_total} != advertised {advertised!r}')
        selected = item.get('selected_rows')
        if not isinstance(selected, int) or selected < 1 or selected > advertised:
            fail(f'{label}/{source_id}: invalid selected_rows {selected!r}')
    return by_id


def validate_rows(payload: dict, artifact_kind: str, statuses: dict[str, dict]) -> None:
    rows = payload.get('records')
    metadata = payload.get('metadata') or {}
    if not isinstance(rows, list):
        fail(f'{artifact_kind}: records must be a list')
        return
    if metadata.get('records') != len(rows):
        fail(f'{artifact_kind}: metadata record count mismatch')
    counts: Counter[str] = Counter()
    seen: set[tuple[str, int]] = set()
    for index, row in enumerate(rows):
        source_id = row.get('source_id')
        expected = EXPECTED.get(source_id)
        if not expected:
            fail(f'{artifact_kind} row {index}: unknown source_id {source_id!r}')
            continue
        expected_kind, expected_scope = expected
        if expected_kind != artifact_kind:
            fail(f'{artifact_kind} row {index}: source {source_id} belongs in {expected_kind}')
        if row.get('scope') != expected_scope:
            fail(f'{artifact_kind} row {index}: scope {row.get("scope")!r} != {expected_scope!r}')
        if expected_scope == 'hrm' and not explicit_hrm_identity(row):
            fail(f'{artifact_kind} row {index}: HRM-scoped row lacks explicit source identity')
        if expected_scope != 'hrm' and row.get('identity_field'):
            fail(f'{artifact_kind} row {index}: context row unexpectedly carries an HRM identity')
        raw = row.get('raw')
        if not isinstance(raw, dict) or not raw:
            fail(f'{artifact_kind} row {index}: raw source row missing')
        source_row_index = row.get('source_row_index')
        if not isinstance(source_row_index, int) or source_row_index < 0:
            fail(f'{artifact_kind} row {index}: invalid source_row_index')
            continue
        key = (source_id, source_row_index)
        if key in seen:
            fail(f'{artifact_kind} row {index}: duplicate source/index key {key!r}')
        seen.add(key)
        counts[source_id] += 1

    for source_id, (kind, _) in EXPECTED.items():
        expected_count = (statuses.get(source_id) or {}).get('selected_rows')
        actual = counts[source_id] if kind == artifact_kind else 0
        if kind == artifact_kind and expected_count != actual:
            fail(f'{artifact_kind}/{source_id}: selected_rows {expected_count!r} != artifact rows {actual}')

    if artifact_kind == 'funding':
        hrm = sum(row.get('scope') == 'hrm' for row in rows)
        context = sum(row.get('scope') != 'hrm' for row in rows)
        if metadata.get('hrm_records') != hrm or metadata.get('context_records') != context:
            fail('funding: HRM/context metadata counts do not match rows')
        if any(row.get('scope') == 'province_program_context' and explicit_hrm_identity(row) for row in rows):
            fail('funding: province-program context must never be attributed to HRM')
    else:
        hrm = sum(row.get('scope') == 'hrm' for row in rows)
        context = sum(row.get('scope') != 'hrm' for row in rows)
        if metadata.get('hrm_records') != hrm or metadata.get('comparator_records') != context:
            fail('benchmark: HRM/comparator metadata counts do not match rows')


def main() -> None:
    benchmarks = load(BENCHMARKS)
    funding = load(FUNDING)
    benchmark_statuses = validate_statuses(benchmarks.get('metadata') or {}, 'benchmarks')
    funding_statuses = validate_statuses(funding.get('metadata') or {}, 'external_funding')
    # Both artifacts are generated from one atomic source refresh; the source
    # status evidence must therefore be byte-for-byte equivalent as JSON data.
    if (benchmarks.get('metadata') or {}).get('source_status') != (funding.get('metadata') or {}).get('source_status'):
        fail('benchmark and funding source_status evidence differs')
    validate_rows(benchmarks, 'benchmark', benchmark_statuses)
    validate_rows(funding, 'funding', funding_statuses)

    if errors:
        print('MUNICIPAL BENCHMARK VALIDATION FAILED', file=sys.stderr)
        for message in errors[:100]:
            print(message, file=sys.stderr)
        raise SystemExit(1)

    print(
        f"validated municipal machine sources: benchmarks={len(benchmarks.get('records') or [])}; "
        f"external_funding={len(funding.get('records') or [])}; sources={len(EXPECTED)}"
    )


if __name__ == '__main__':
    main()
