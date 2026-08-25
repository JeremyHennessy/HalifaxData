#!/usr/bin/env python3
"""Build the final Build 005 entity index across every approved data artifact.

The existing v3 builder remains the trusted core join implementation. This v4
layer adds only joins with defensible official keys/scopes and records context
artifacts without attributing them to HRM when their scope is not HRM-specific.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_entity_index as core

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / 'data/generated'
DEFAULT_OUT = GENERATED / 'entity_index.json'
NORMALIZATION_VERSION = 'build005-entity-index-v4'
HRM_ORG = 'org:halifax-regional-municipality'
EXTRA_INPUTS = {
    'budget_history': GENERATED / 'budget_history.json',
    'benchmarks': GENERATED / 'benchmarks.json',
    'external_funding': GENERATED / 'external_funding.json',
    'council': GENERATED / 'council.json',
    'council_documents': GENERATED / 'council_documents.json',
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--check', action='store_true')
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f'Required Build 005 input is missing: {path.relative_to(ROOT)}')
    return json.loads(path.read_text(encoding='utf-8'))


def artifact_info(path: Path, payload: dict) -> dict:
    metadata = payload.get('metadata') or {}
    return {
        'path': str(path.relative_to(ROOT)),
        'sha256': core.sha256_file(path),
        'records': len(payload.get('records') or []),
        'generated_at': metadata.get('generated_at'),
    }


def extra_ref(dataset: str, row: dict, index: int) -> str:
    if dataset == 'budget_history':
        provenance = row.get('provenance') or {}
        identity = [row.get('source_id'), provenance.get('locator_value'), row.get('fiscal_year')]
    elif dataset in {'benchmarks', 'external_funding'}:
        identity = [row.get('source_id'), row.get('source_row_index')]
    elif dataset == 'council':
        identity = [row.get('meeting_id')]
    elif dataset == 'council_documents':
        identity = [row.get('meeting_id'), row.get('document_id')]
    else:
        identity = [index, row]
    return f'{dataset}:{core.stable_digest(identity)}'


def build_payload() -> dict:
    core_inputs = core.load_inputs()
    payload = core.build_payload(core_inputs)
    extras = {name: load_json(path) for name, path in EXTRA_INPUTS.items()}

    metadata = payload['metadata']
    metadata['schema_version'] = '1.1.0'
    metadata['normalization_version'] = NORMALIZATION_VERSION
    metadata['approved_input_count'] = len(core.INPUTS) + len(EXTRA_INPUTS)
    metadata['join_policy']['historical_budget_business_unit_match'] = 'none; organization scope only'
    metadata['join_policy']['benchmark_context_attribution'] = 'none unless source row scope=hrm'
    metadata['join_policy']['external_funding_context_attribution'] = 'none unless source row scope=hrm'
    metadata['join_policy']['council_meeting_match'] = 'official eSCRIBE meeting_id exact only'
    metadata['join_policy']['forbidden_joins'].extend([
        'historical_budget_context_to_current_business_unit',
        'province_program_context_to_hrm',
        'regional_type_comparator_to_hrm',
        'council_title_fuzzy_to_financial_fact',
    ])
    metadata['join_policy']['forbidden_joins'] = sorted(set(metadata['join_policy']['forbidden_joins']))

    input_artifacts = metadata['input_artifacts']
    for name, path in EXTRA_INPUTS.items():
        input_artifacts[name] = artifact_info(path, extras[name])
    metadata['source_record_counts'] = {name: info['records'] for name, info in input_artifacts.items()}
    times = [info.get('generated_at') for info in input_artifacts.values() if info.get('generated_at')]
    metadata['generated_at'] = max(times) if times else None

    links = payload['record_links']
    council_dimensions: list[dict] = []
    council_ids: set[str] = set()

    budget_history_rows = extras['budget_history'].get('records') or []
    for index, row in enumerate(budget_history_rows):
        links.append({
            'source_dataset': 'budget_history',
            'source_record_ref': extra_ref('budget_history', row, index),
            'organization_id': HRM_ORG,
            'join_methods': {'organization': 'official_hrm_budget_document_scope'},
        })

    benchmark_hrm = 0
    benchmark_context = 0
    for index, row in enumerate(extras['benchmarks'].get('records') or []):
        if row.get('scope') == 'hrm':
            benchmark_hrm += 1
            links.append({
                'source_dataset': 'benchmarks',
                'source_record_ref': extra_ref('benchmarks', row, index),
                'organization_id': HRM_ORG,
                'join_methods': {'organization': 'explicit_hrm_source_scope'},
            })
        else:
            benchmark_context += 1

    funding_hrm = 0
    funding_context = 0
    for index, row in enumerate(extras['external_funding'].get('records') or []):
        if row.get('scope') == 'hrm':
            funding_hrm += 1
            links.append({
                'source_dataset': 'external_funding',
                'source_record_ref': extra_ref('external_funding', row, index),
                'organization_id': HRM_ORG,
                'join_methods': {'organization': 'explicit_hrm_source_scope'},
            })
        else:
            funding_context += 1

    council_rows = extras['council'].get('records') or []
    for index, row in enumerate(council_rows):
        meeting_id = str(row.get('meeting_id') or '').strip()
        if not meeting_id or meeting_id in council_ids:
            raise RuntimeError(f'Council meeting ID is blank/non-unique: {meeting_id!r}')
        council_ids.add(meeting_id)
        dimension_id = f'council-meeting:{meeting_id}'
        council_dimensions.append({
            'council_meeting_id': dimension_id,
            'official_meeting_id': meeting_id,
            'meeting_name': row.get('meeting_name'),
            'meeting_type': row.get('meeting_type'),
            'start_date': row.get('start_date'),
            'identity_method': 'official_escribe_meeting_id_exact',
        })
        links.append({
            'source_dataset': 'council',
            'source_record_ref': extra_ref('council', row, index),
            'organization_id': HRM_ORG,
            'council_meeting_id': dimension_id,
            'join_methods': {
                'organization': 'official_source_scope',
                'council_meeting': 'official_escribe_meeting_id_exact',
            },
        })

    council_document_rows = extras['council_documents'].get('records') or []
    for index, row in enumerate(council_document_rows):
        meeting_id = str(row.get('meeting_id') or '').strip()
        if meeting_id not in council_ids:
            raise RuntimeError(f'Council document references unknown meeting_id {meeting_id!r}')
        links.append({
            'source_dataset': 'council_documents',
            'source_record_ref': extra_ref('council_documents', row, index),
            'organization_id': HRM_ORG,
            'council_meeting_id': f'council-meeting:{meeting_id}',
            'join_methods': {
                'organization': 'official_source_scope',
                'council_meeting': 'official_escribe_meeting_id_exact',
            },
        })

    links.sort(key=lambda row: (row['source_dataset'], row['source_record_ref']))
    council_dimensions.sort(key=lambda row: row['council_meeting_id'])
    payload['council_meetings'] = council_dimensions

    metadata['record_link_count'] = len(links)
    metadata['council_meeting_count'] = len(council_dimensions)
    metadata['budget_history_rows_linked'] = len(budget_history_rows)
    metadata['benchmark_hrm_rows_linked'] = benchmark_hrm
    metadata['benchmark_context_rows_intentionally_unlinked'] = benchmark_context
    metadata['external_funding_hrm_rows_linked'] = funding_hrm
    metadata['external_funding_context_rows_intentionally_unlinked'] = funding_context
    metadata['council_rows_linked'] = len(council_rows)
    metadata['council_document_rows_linked'] = len(council_document_rows)
    return payload


def main() -> None:
    args = parse_args()
    payload = build_payload()
    rendered = core.serialize(payload)
    if args.check:
        if not args.output.exists():
            raise SystemExit(f'Normalized entity index missing: {args.output.relative_to(ROOT)}')
        current = args.output.read_text(encoding='utf-8')
        if current != rendered:
            raise SystemExit('Normalized entity index is stale relative to approved Build 005 inputs')
        print(f'entity index v4 is current: {payload["metadata"]["record_link_count"]} links')
        return
    tmp = args.output.with_suffix(args.output.suffix + '.tmp')
    tmp.write_text(rendered, encoding='utf-8')
    tmp.replace(args.output)
    metadata = payload['metadata']
    print(
        f"Wrote entity index v4: links={metadata['record_link_count']}; "
        f"business_units={metadata['business_unit_count']}; people={metadata['person_name_cluster_count']}; "
        f"vendors={metadata['vendor_name_cluster_count']}; capital_projects={metadata['capital_project_cluster_count']}; "
        f"council_meetings={metadata['council_meeting_count']}"
    )


if __name__ == '__main__':
    main()
