#!/usr/bin/env python3
"""Run all HalifaxData refresh stages without letting one source/parser block others.

Each collector remains responsible for fail-closed writes in its own domain. This
orchestrator records stage outcomes and continues so independent sources can still
refresh. Repository validators run after this script in CI/workflows; a final
workflow step may mark the run failed if any stage failed *after* valid successful
updates have been committed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/generated/refresh_status.json'

STAGES = [
    ('source_registry_core', 'scripts/augment_sources.py'),
    ('source_registry_external', 'scripts/augment_sources_external.py'),
    ('source_acquisition', 'scripts/acquire_sources.py'),
    ('compensation', 'scripts/ingest_compensation.py'),
    ('current_domains', 'scripts/ingest_domains.py'),
    ('budget_history', 'scripts/ingest_budget_history.py'),
    ('capital_history', 'scripts/ingest_capital_history.py'),
    ('financial_history', 'scripts/ingest_financial_history.py'),
    ('quarterly_spending', 'scripts/ingest_quarterly_spending.py'),
    ('municipal_benchmarks', 'scripts/ingest_municipal_benchmarks.py'),
]


def timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main():
    rows = []
    for name, relative in STAGES:
        path = ROOT / relative
        started = timestamp()
        if not path.exists():
            rows.append({'stage': name, 'script': relative, 'status': 'missing', 'exit_code': None, 'started_at': started, 'finished_at': timestamp()})
            print(f'[refresh] {name}: missing {relative}', file=sys.stderr)
            continue
        print(f'\n[refresh] START {name}: {relative}', flush=True)
        proc = subprocess.run([sys.executable, str(path)], cwd=ROOT)
        status = 'ok' if proc.returncode == 0 else 'error'
        rows.append({'stage': name, 'script': relative, 'status': status, 'exit_code': proc.returncode, 'started_at': started, 'finished_at': timestamp()})
        print(f'[refresh] END {name}: {status} exit={proc.returncode}', flush=True)

    payload = {
        'metadata': {
            'generated_at': timestamp(),
            'stage_count': len(rows),
            'ok': sum(row['status'] == 'ok' for row in rows),
            'failed': sum(row['status'] in {'error', 'missing'} for row in rows),
            'note': 'Stages run independently. A failed stage does not erase successful outputs from other domains; repository validators run separately before publication.',
        },
        'records': rows,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(payload['metadata'], indent=2))
    # Do not fail here: validation and commit must be allowed to preserve valid
    # updates from independent stages. The workflow can fail after committing.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
