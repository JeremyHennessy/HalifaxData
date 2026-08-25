#!/usr/bin/env python3
"""Refresh all HalifaxData public datasets serially, then validate once.

The order matters: current budget remains the Build 004 authoritative contract;
historical budget writes a separate artifact; capital history augments the base
historical ArcGIS collection. The script stops on the first failed collector.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / 'data/generated'

STEPS = [
    'ingest_compensation.py',
    'ingest_budget.py',
    'ingest_procurement.py',
    'ingest_capital_arcgis.py',
    'ingest_capital_history.py',
    'ingest_financial_history.py',
    'ingest_council.py',
    'ingest_council_documents.py',
    'ingest_budget_history.py',
    'ingest_quarterly_spending.py',
    'ingest_municipal_benchmarks.py',
    'acquire_sources.py',
]

DOMAIN_FILES = {
    'compensation': 'compensation.json',
    'budget': 'budget.json',
    'budget_history': 'budget_history.json',
    'procurement': 'procurement.json',
    'capital': 'capital.json',
    'financials': 'financials.json',
    'council': 'council.json',
    'council_documents': 'council_documents.json',
    'spending': 'spending.json',
    'benchmarks': 'benchmarks.json',
    'external_funding': 'external_funding.json',
}


def run(script: str):
    print(f'\n=== {script} ===', flush=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT, check=True)


def count_records(filename: str):
    path = GEN / filename
    if not path.exists(): return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        records = payload.get('records') if isinstance(payload, dict) else None
        return len(records) if isinstance(records, list) else None
    except Exception:
        return None


def write_status():
    status = {
        'metadata': {
            'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            'dataset_status': 'post_validation_snapshot',
            'note': 'Counts reflect generated artifacts after the serial Build 005 refresh and both validation gates. Presence/count does not imply equal granularity or current-universe completeness across domains.',
        },
        'domains': {name: {'artifact': filename, 'records': count_records(filename)} for name, filename in DOMAIN_FILES.items()},
    }
    (GEN / 'domain_ingestion_status.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')


def main():
    for script in STEPS:
        run(script)
    run('validate_data.py')
    run('validate_domains.py')
    write_status()
    # Re-run domain validator after status serialization so checked-in state is exact.
    run('validate_domains.py')
    print('\nAll public-data collectors and validation gates passed.')


if __name__ == '__main__':
    main()
