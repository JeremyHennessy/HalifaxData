#!/usr/bin/env python3
"""Independently validate final Build 005 all-domain entity-index semantics."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import build_entity_index as core
import build_entity_index_v4 as v4

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'data/generated/entity_index.json'
HRM_ORG = 'org:halifax-regional-municipality'
EXPECTED_VERSION = 'build005-entity-index-v4'
ALL_INPUTS = {**core.INPUTS, **v4.EXTRA_INPUTS}
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def core_ref(dataset: str, row: dict, index: int) -> str:
    return core.record_ref(dataset, row, index)


def main() -> None:
    if not PATH.exists():
        raise SystemExit('entity_index.json is missing')
    index = load(PATH)
    metadata = index.get('metadata') or {}
    if metadata.get('normalization_version') != EXPECTED_VERSION:
        fail(f"normalization_version {metadata.get('normalization_version')!r} != {EXPECTED_VERSION!r}")
    if metadata.get('schema_version') != '1.1.0':
        fail(f"schema_version {metadata.get('schema_version')!r} != '1.1.0'")
    if metadata.get('approved_input_count') != len(ALL_INPUTS):
        fail('approved_input_count does not match required input set')
    policy = metadata.get('join_policy') or {}
    if policy.get('fuzzy_matching') is not False:
        fail('fuzzy_matching must be explicitly false')
    forbidden = set(policy.get('forbidden_joins') or [])
    for required in {
        'cross_entity_person_key',
        'fuzzy_name_to_business_unit',
        'fuzzy_vendor_identity',
        'historical_budget_context_to_current_business_unit',
        'province_program_context_to_hrm',
        'regional_type_comparator_to_hrm',
    }:
        if required not in forbidden:
            fail(f'join policy is missing forbidden join {required!r}')

    artifacts = metadata.get('input_artifacts') or {}
    if set(artifacts) != set(ALL_INPUTS):
        fail('input_artifacts does not exactly match approved Build 005 inputs')
    source_counts = metadata.get('source_record_counts') or {}
    loaded_inputs: dict[str, dict] = {}
    for name, path in ALL_INPUTS.items():
        if not path.exists():
            fail(f'input {name}: file is missing')
            continue
        payload = load(path)
        loaded_inputs[name] = payload
        info = artifacts.get(name) or {}
        if info.get('path') != str(path.relative_to(ROOT)):
            fail(f'input {name}: path metadata mismatch')
        if info.get('sha256') != sha256_file(path):
            fail(f'input {name}: SHA-256 is stale')
        rows = payload.get('records') or []
        if info.get('records') != len(rows) or source_counts.get(name) != len(rows):
            fail(f'input {name}: record count metadata mismatch')

    organizations = index.get('organizations') or []
    organization_ids = [row.get('organization_id') for row in organizations]
    if HRM_ORG not in organization_ids or len(organization_ids) != len(set(organization_ids)):
        fail('organization dimension is missing HRM or contains duplicate IDs')
    business_units = index.get('business_units') or []
    business_unit_ids = [row.get('business_unit_id') for row in business_units]
    if len(business_unit_ids) != len(set(business_unit_ids)) or metadata.get('business_unit_count') != len(business_units):
        fail('business-unit dimension/count is invalid')
    people = index.get('person_name_clusters') or []
    person_ids = {row.get('person_name_cluster_id') for row in people}
    vendors = index.get('vendor_name_clusters') or []
    vendor_ids = {row.get('vendor_name_cluster_id') for row in vendors}
    projects = index.get('capital_projects') or []
    project_ids = {row.get('capital_project_id') for row in projects}
    council_meetings = index.get('council_meetings') or []
    council_ids = {row.get('council_meeting_id') for row in council_meetings}
    official_meeting_ids = {row.get('official_meeting_id') for row in council_meetings}
    if len(council_ids) != len(council_meetings) or len(official_meeting_ids) != len(council_meetings):
        fail('Council meeting dimension contains duplicate IDs')
    if metadata.get('council_meeting_count') != len(council_meetings):
        fail('Council meeting metadata count mismatch')

    links = index.get('record_links')
    if not isinstance(links, list):
        raise SystemExit('entity_index record_links must be a list')
    if metadata.get('record_link_count') != len(links):
        fail('record_link_count metadata mismatch')
    link_by_ref: dict[tuple[str, str], dict] = {}
    link_counts: Counter[str] = Counter()
    for number, link in enumerate(links):
        dataset = link.get('source_dataset')
        record_ref = link.get('source_record_ref')
        if not dataset or not record_ref:
            fail(f'link {number}: missing dataset/reference')
            continue
        key = (dataset, record_ref)
        if key in link_by_ref:
            fail(f'link {number}: duplicate source link {key!r}')
        link_by_ref[key] = link
        link_counts[dataset] += 1
        if link.get('organization_id') and link['organization_id'] not in organization_ids:
            fail(f'link {number}: unknown organization_id')
        if link.get('business_unit_id') and link['business_unit_id'] not in business_unit_ids:
            fail(f'link {number}: unknown business_unit_id')
        if link.get('person_name_cluster_id') and link['person_name_cluster_id'] not in person_ids:
            fail(f'link {number}: unknown person_name_cluster_id')
        if link.get('vendor_name_cluster_id') and link['vendor_name_cluster_id'] not in vendor_ids:
            fail(f'link {number}: unknown vendor_name_cluster_id')
        if link.get('capital_project_id') and link['capital_project_id'] not in project_ids:
            fail(f'link {number}: unknown capital_project_id')
        if link.get('council_meeting_id') and link['council_meeting_id'] not in council_ids:
            fail(f'link {number}: unknown council_meeting_id')
        methods = ' '.join(str(value) for value in (link.get('join_methods') or {}).values()).lower()
        if 'fuzzy' in methods:
            fail(f'link {number}: fuzzy join method is forbidden')

    # Core datasets: reconstruct the exact source references and assert critical semantics.
    for dataset in ('budget', 'compensation', 'procurement', 'capital', 'spending', 'financials'):
        rows = (loaded_inputs.get(dataset) or {}).get('records') or []
        for row_index, row in enumerate(rows):
            ref = core_ref(dataset, row, row_index)
            link = link_by_ref.get((dataset, ref))
            if dataset == 'budget' and row.get('record_type') != 'service_area_budget':
                if link and link.get('business_unit_id'):
                    fail(f'budget row {row_index}: non-operational/audited row gained a business-unit join')
                continue
            if dataset == 'budget':
                if not link or not link.get('business_unit_id'):
                    fail(f'budget row {row_index}: operational row is not linked to a budget-anchor business unit')
            elif dataset == 'compensation':
                if row.get('person_key'):
                    if not link or not link.get('person_name_cluster_id') or not link.get('organization_id'):
                        fail(f'compensation row {row_index}: person identity is not entity-scoped')
            elif dataset == 'procurement':
                if row.get('vendor_name') and (not link or not link.get('vendor_name_cluster_id')):
                    fail(f'procurement row {row_index}: vendor name lacks provisional exact-name cluster')
            elif dataset == 'capital':
                if not link or link.get('organization_id') != HRM_ORG or not link.get('capital_project_id'):
                    fail(f'capital row {row_index}: missing official HRM/project linkage')
            elif dataset == 'spending':
                if not link or link.get('organization_id') != HRM_ORG:
                    fail(f'spending row {row_index}: missing HRM organization scope')
            elif dataset == 'financials':
                if not link or link.get('organization_id') != HRM_ORG:
                    fail(f'financial row {row_index}: missing HRM organization scope')
                elif link.get('business_unit_id'):
                    fail(f'financial row {row_index}: audited statement row must not map to operational business unit')

    budget_history = (loaded_inputs.get('budget_history') or {}).get('records') or []
    for row_index, row in enumerate(budget_history):
        ref = v4.extra_ref('budget_history', row, row_index)
        link = link_by_ref.get(('budget_history', ref))
        if not link or link.get('organization_id') != HRM_ORG:
            fail(f'budget_history row {row_index}: missing HRM organization scope')
        elif link.get('business_unit_id'):
            fail(f'budget_history row {row_index}: historical page context must not map to current business unit')
    if metadata.get('budget_history_rows_linked') != len(budget_history):
        fail('budget_history_rows_linked metadata mismatch')

    benchmark_rows = (loaded_inputs.get('benchmarks') or {}).get('records') or []
    benchmark_hrm = benchmark_context = 0
    for row_index, row in enumerate(benchmark_rows):
        ref = v4.extra_ref('benchmarks', row, row_index)
        link = link_by_ref.get(('benchmarks', ref))
        if row.get('scope') == 'hrm':
            benchmark_hrm += 1
            if not link or link.get('organization_id') != HRM_ORG:
                fail(f'benchmark row {row_index}: HRM-scoped fact is not linked to HRM')
        else:
            benchmark_context += 1
            if link:
                fail(f'benchmark row {row_index}: comparator context was incorrectly attributed to HRM')
    if metadata.get('benchmark_hrm_rows_linked') != benchmark_hrm or metadata.get('benchmark_context_rows_intentionally_unlinked') != benchmark_context:
        fail('benchmark link/unlinked metadata mismatch')

    funding_rows = (loaded_inputs.get('external_funding') or {}).get('records') or []
    funding_hrm = funding_context = 0
    for row_index, row in enumerate(funding_rows):
        ref = v4.extra_ref('external_funding', row, row_index)
        link = link_by_ref.get(('external_funding', ref))
        if row.get('scope') == 'hrm':
            funding_hrm += 1
            if not link or link.get('organization_id') != HRM_ORG:
                fail(f'external_funding row {row_index}: HRM-scoped fact is not linked to HRM')
        else:
            funding_context += 1
            if link:
                fail(f'external_funding row {row_index}: province context was incorrectly attributed to HRM')
    if metadata.get('external_funding_hrm_rows_linked') != funding_hrm or metadata.get('external_funding_context_rows_intentionally_unlinked') != funding_context:
        fail('external funding link/unlinked metadata mismatch')

    council_rows = (loaded_inputs.get('council') or {}).get('records') or []
    if {str(row.get('meeting_id')) for row in council_rows} != official_meeting_ids:
        fail('Council dimension does not exactly match council.json meeting IDs')
    for row_index, row in enumerate(council_rows):
        meeting_id = str(row.get('meeting_id'))
        ref = v4.extra_ref('council', row, row_index)
        link = link_by_ref.get(('council', ref))
        if not link or link.get('organization_id') != HRM_ORG or link.get('council_meeting_id') != f'council-meeting:{meeting_id}':
            fail(f'council row {row_index}: exact meeting linkage failed')

    doc_rows = (loaded_inputs.get('council_documents') or {}).get('records') or []
    for row_index, row in enumerate(doc_rows):
        meeting_id = str(row.get('meeting_id'))
        ref = v4.extra_ref('council_documents', row, row_index)
        link = link_by_ref.get(('council_documents', ref))
        if not link or link.get('organization_id') != HRM_ORG or link.get('council_meeting_id') != f'council-meeting:{meeting_id}':
            fail(f'council_documents row {row_index}: exact meeting linkage failed')

    if metadata.get('council_rows_linked') != len(council_rows) or metadata.get('council_document_rows_linked') != len(doc_rows):
        fail('Council link metadata mismatch')

    if errors:
        print('ENTITY INDEX V4 VALIDATION FAILED', file=sys.stderr)
        for message in errors[:120]:
            print(message, file=sys.stderr)
        raise SystemExit(1)

    print(
        f"validated entity index v4: links={len(links)}; inputs={len(ALL_INPUTS)}; "
        f"business_units={len(business_units)}; people={len(people)}; vendors={len(vendors)}; "
        f"capital_projects={len(projects)}; council_meetings={len(council_meetings)}"
    )


if __name__ == '__main__':
    main()
