"""Read-only repository diagnostics. Never grants collection or publication access."""
import ast
import datetime
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = 'pipeline/foundation'
# Independently reviewed repository inputs, not proof of current source access.
PINS = {
    PACKAGE + '/PACKAGE-MANIFEST.json': 'f1bb4a5ed874b484fd29b626d33cca23df15336120b8f62f4573eb26f48b238d',
    'data/foundation.json': '9daa91dae039dc3c20e1cab6dc1cedb5951ba3e1af9613f63dacd4c7ef2b2958',
    'data/publication-review.json': '044d6626c4035781c34e3d76bdb42e18b8df18064308b8e0ee58b05b532ed32a',
    '.github/workflows/verify.yml': '40c0867884c43350998f54a85111507536627a92ede357f4619d64130e1591a4',
}


def read_file(root, relative):
    """Read only bounded regular files within the checkout; do not follow links."""
    parts = pathlib.PurePosixPath(relative).parts
    if not parts or relative != '/'.join(parts) or any(p in ('.', '..') for p in parts):
        raise ValueError('Invalid repository-relative path')
    if pathlib.PurePosixPath(relative).is_absolute():
        raise ValueError('Absolute path is not a repository input')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symlink input requires review')
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Missing, non-regular or oversized input')
    return path.read_bytes()


def literal(source, name):
    assignments = [n for n in ast.walk(ast.parse(source))
                   if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('Expected exactly one literal assignment: ' + name)
    return ast.literal_eval(assignments[0].value)


def inspect(root=ROOT):
    root = pathlib.Path(root)
    issues, verified, contents = [], [], {}

    def check(relative, expected):
        try:
            body = read_file(root, relative)
            if hashlib.sha256(body).hexdigest() != expected:
                raise ValueError('Pinned bytes changed; separate review required')
            contents[relative] = body
            verified.append(relative)
            return body
        except (OSError, ValueError) as error:
            issues.append({'path': relative, 'reason': str(error)})
            return None

    for relative, expected in PINS.items():
        check(relative, expected)
    manifest = contents.get(PACKAGE + '/PACKAGE-MANIFEST.json')
    if manifest is not None:
        for relative, expected in json.loads(manifest)['files'].items():
            check(PACKAGE + '/' + relative, expected)

    # A changed workflow is unknown, not a heuristic claim that cron is absent.
    try:
        directory = root / '.github/workflows'
        if (root / '.github').is_symlink() or directory.is_symlink():
            raise ValueError('Symlink workflow directory requires review')
        if sorted(p.name for p in directory.iterdir()) != ['verify.yml']:
            raise ValueError('Workflow set changed; source scheduling must be reviewed')
    except (OSError, ValueError) as error:
        issues.append({'path': '.github/workflows', 'reason': str(error)})
    workflow_verified = not any(i['path'].startswith('.github/') for i in issues)

    collector = contents.get(PACKAGE + '/physician_refresh/collector.py')
    disabled = collector is not None and literal(collector, 'MANUAL_TRANSPORT_ENABLED') is False
    if collector is not None and not disabled:
        issues.append({'path': PACKAGE + '/physician_refresh/collector.py',
                       'reason': 'Canonical CLI transport is not disabled'})

    state = root / PACKAGE / 'physician_refresh/refresh-state.private'
    # Presence is only an observation. Do not open, migrate, create or modify state.
    state_present = state.exists() or state.is_symlink()
    if state_present:
        issues.append({'path': PACKAGE + '/physician_refresh/refresh-state.private',
                       'reason': 'Runtime state present; history and holds require separate review'})

    baseline = contents.get(PACKAGE + '/physician_refresh/baseline/records.json')
    receipt = contents.get(PACKAGE + '/physician_refresh/baseline/publication-review.json')
    refresh = contents.get(PACKAGE + '/physician_refresh/refresh.py')
    provenance = None
    if baseline is not None and receipt is not None and refresh is not None:
        review, records = json.loads(receipt), json.loads(baseline)
        if (review['status'] != 'accepted' or review['bundleSha256'] != hashlib.sha256(baseline).hexdigest()
                or literal(refresh, 'BASELINE_SHA') != hashlib.sha256(baseline).hexdigest()
                or literal(refresh, 'REVIEW_SHA') != hashlib.sha256(receipt).hexdigest()):
            issues.append({'path': PACKAGE + '/physician_refresh/baseline', 'reason': 'Baseline review binding failed'})
        else:
            source = records['source']
            first = datetime.datetime.fromisoformat(source['capturedAt']) + datetime.timedelta(days=7)
            provenance = {
                'datasetId': source['datasetId'], 'observations': len(records['records']),
                'baselineSha256': hashlib.sha256(baseline).hexdigest(),
                'reviewReceiptSha256': hashlib.sha256(receipt).hexdigest(),
                'acceptedRetrieval': source['capturedAt'],
                'baselineOnlyCadenceFloor': first.isoformat(),
                'cadenceMeaning': 'Historical lower bound only. Later attempts and holds remain unknown; not a next-run date.',
                'proposedEndpoints': [literal(collector, 'ROBOTS'), source['metadataUrl'], source['downloadUrl']] if collector else None,
            }

    held = None
    foundation = contents.get('data/foundation.json')
    if foundation is not None and 'data/publication-review.json' in contents:
        # Surface exact retained statements only. This is not a complete hold registry.
        held = [{'sourceId': s['id'], 'url': s['url'],
                 'retainedStatements': [v for v in s['limitations'] if 'access hold' in v.lower()]}
                for s in json.loads(foundation)['sources']
                if any('access hold' in v.lower() for v in s['limitations'])]

    return {
        'schemaVersion': 'offline-collection-readiness-v1',
        'status': 'repository_drift_requires_review' if issues else 'inactive_requires_operational_review',
        'repositoryBoundaryVerified': not issues,
        'collectionAuthorized': False, 'publicationAllowed': False,
        'networkRequestsMade': 0, 'runtimeStateReadOrWritten': False,
        'canonicalCliTransportDisabled': disabled if collector is not None else None,
        'repositoryWorkflow': 'reviewed_release_only_no_source_schedule' if workflow_verified else 'unverified',
        'externalSchedulerStatus': 'unknown_not_inspected',
        'canonicalStatePresent': state_present,
        'endpointHoldHistory': 'unknown_not_migrated_or_cleared_by_this_check',
        'retainedHoldStatements': held,
        'holdStatementScope': 'Pinned historical source-register statements, not a complete or current operational hold registry. Absence is not clearance.',
        'baselineProvenance': provenance,
        'verifiedFileCount': len(verified), 'issues': issues,
        'requiredBeforeAnyActivation': [
            'Review exact endpoint access, usage/licence and privacy scope; preserve every unresolved hold.',
            'Select durable private canonical state and review migration of all prior attempts, outcomes, locks, holds and accepted retrieval history without resetting cadence.',
            'Review explicit operational registration, bounded cadence, concurrency, failure stops and ownership; do not infer authorization from this report.',
            'Revalidate same-attempt policy, exact endpoints, provenance, schema and licence before candidate preparation; no redirects or retries after failure or uncertainty.',
            'Keep candidates private and unreviewed until independent exact-byte publication review and application release gates pass.',
        ],
        'limitations': [
            'This diagnostic never imports or invokes the collector, evaluates live robots policy, clears holds or enables a scheduler.',
            'Disabled canonical CLI does not make the reusable transport class impossible to call directly.',
            'Pinned reviewed code and passing tests do not establish current source availability, rights or hosted state.',
            'Exit 0 means the checked inactive repository boundary matches its pins, never ready to collect. Exit 2 means review is required for repository drift.',
        ],
    }


def main():
    report = inspect()
    print(json.dumps(report, indent=2))
    return 0 if report['repositoryBoundaryVerified'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
