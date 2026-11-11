"""Offline, read-only inventory of explicitly supplied private state snapshots.

This prepares a review manifest, never a migration, collection or hold clearance.
No snapshot is discovered automatically and the collector is never imported.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import stat

try:
    from . import collection_readiness as readiness
except ImportError:
    import collection_readiness as readiness

ROOT = readiness.ROOT
MAX_SNAPSHOTS = 8
MAX_FILES = 4096
MAX_ENTRIES = 8192
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
WEEK = datetime.timedelta(days=7)
KINDS = ('robots', 'metadata', 'payments')


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be an explicit timezone-aware string')
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp lacks a timezone')
    return parsed.astimezone(datetime.timezone.utc)


def epoch(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Completion epoch is not a finite number')
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc)


def signature(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def inventory(snapshot):
    """Bound reads; reject links/special files and observed concurrent changes.

    Callers must supply a frozen copy. Stable observations cannot establish an
    atomic export, complete prior history, or durable destination storage.
    """
    snapshot = pathlib.Path(snapshot).absolute()
    artifacts, bodies, total, file_count = [], {}, 0, 0
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    # Open every path component relative to its already-open parent. A renamed
    # ancestor or racing symlink cannot redirect reads to another directory.
    root_fd = os.open(snapshot.anchor, directory_flags)
    try:
        for part in snapshot.parts[1:]:
            if part in ('.', '..'):
                raise ValueError('Snapshot path must not traverse parents')
            child = os.open(part, directory_flags, dir_fd=root_fd)
            os.close(root_fd)
            root_fd = child

        def visit(directory_fd, prefix='', depth=0):
            nonlocal total, file_count
            before = os.fstat(directory_fd)
            with os.scandir(directory_fd) as iterator:
                names = []
                for entry in iterator:
                    names.append(entry.name)
                    if len(names) + len(artifacts) > MAX_ENTRIES:
                        raise ValueError('Snapshot entry bound exceeded')
            for name in sorted(names):
                relative = prefix + name
                observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISLNK(observed.st_mode):
                    raise ValueError('Snapshot contains a symlink')
                if stat.S_ISDIR(observed.st_mode):
                    if depth >= 4:
                        raise ValueError('Snapshot directory depth exceeds bound')
                    if len(artifacts) >= MAX_ENTRIES:
                        raise ValueError('Snapshot entry bound exceeded')
                    artifacts.append({'path': relative, 'kind': 'directory', 'bytes': 0, 'sha256': None})
                    child = os.open(name, directory_flags, dir_fd=directory_fd)
                    try:
                        if signature(os.fstat(child)) != signature(observed):
                            raise ValueError('Snapshot directory changed before reading')
                        visit(child, relative + '/', depth + 1)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(observed.st_mode):
                    if file_count >= MAX_FILES or observed.st_size > MAX_FILE_BYTES:
                        raise ValueError('Snapshot file bound exceeded')
                    file_count += 1
                    total += observed.st_size
                    if total > MAX_TOTAL_BYTES or len(artifacts) >= MAX_ENTRIES:
                        raise ValueError('Snapshot size bound exceeded')
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
                    with os.fdopen(fd, 'rb') as stream:
                        if signature(os.fstat(stream.fileno())) != signature(observed):
                            raise ValueError('Snapshot changed before reading')
                        body = stream.read(MAX_FILE_BYTES + 1)
                        after = os.fstat(stream.fileno())
                    if len(body) != observed.st_size or signature(after) != signature(observed):
                        raise ValueError('Snapshot changed while reading')
                    artifacts.append({'path': relative, 'kind': 'file', 'bytes': len(body),
                                      'sha256': hashlib.sha256(body).hexdigest()})
                    if name.endswith('.json') or relative == 'active.lock':
                        bodies[relative] = body
                else:
                    raise ValueError('Snapshot contains a non-regular file')
                if signature(os.stat(name, dir_fd=directory_fd, follow_symlinks=False)) != signature(observed):
                    raise ValueError('Snapshot entry changed while reading')
            if signature(os.fstat(directory_fd)) != signature(before):
                raise ValueError('Snapshot directory changed while reading')

        visit(root_fd)
    finally:
        os.close(root_fd)
    return artifacts, bodies


def decode(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    result = json.loads(body, object_pairs_hook=unique,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON value')))
    if not isinstance(result, dict):
        raise ValueError('Journal record must be an object')
    return result


def inspect_snapshot(artifacts, bodies, provenance, expected_baseline):
    files = {item['path']: item for item in artifacts}
    findings, clocks = [], []

    def finding(code, path):
        item = {'code': code, 'path': path}
        if item not in findings:
            findings.append(item)

    def record(path):
        if path not in bodies:
            finding('missing_journal_record', path)
            return None
        try:
            return decode(bodies[path])
        except (ValueError, UnicodeError, RecursionError):
            finding('malformed_journal_record', path)
            return None

    baseline = record('baseline-retrieval.json')
    if baseline is not None and baseline != expected_baseline:
        finding('accepted_baseline_history_mismatch', 'baseline-retrieval.json')
    for path, code in [('hold.json', 'persistent_hold_preserved'),
                       ('active.lock', 'unresolved_lock_preserved')]:
        if path in files:
            finding(code, path)
            item = record(path)
            if item is not None:
                try:
                    clocks.append(epoch(item.get('completedAtEpoch')) if path == 'hold.json'
                                  else timestamp(item.get('startedAt')))
                except (ValueError, OverflowError, OSError):
                    finding('unknown_hold_or_lock_time', path)
    if 'attempts' in files and files['attempts']['kind'] != 'directory':
        finding('journal_directory_type_invalid', 'attempts')
    # Unknown artifacts are retained, not silently dropped or interpreted.
    known = {'baseline-retrieval.json', 'hold.json', 'active.lock', 'attempts'}
    runs = sorted({p.split('/')[1] for p in files if p.startswith('attempts/') and len(p.split('/')) >= 2})
    endpoints = dict(zip(KINDS, provenance['proposedEndpoints']))
    for run in runs:
        prefix = 'attempts/' + run + '/'
        known.add(prefix.rstrip('/'))
        known.update(prefix + suffix for suffix in ['admission.json', 'outcome.json',
                     'robots-decisions.json', 'candidate.private.json'] +
                     [name + suffix for name in KINDS for suffix in ['.attempt.json', '.receipt.json', '.body']])
        outcome = record(prefix + 'outcome.json')
        if outcome is not None:
            try:
                clocks.append(epoch(outcome.get('completedAtEpoch')))
            except (ValueError, OverflowError, OSError):
                finding('unknown_completion_time', prefix + 'outcome.json')
            if outcome.get('status') != 'candidate_prepared':
                finding('failed_or_unknown_outcome_preserved', prefix + 'outcome.json')
            else:
                candidate = files.get(prefix + 'candidate.private.json')
                if (not candidate or candidate['kind'] != 'file' or outcome.get('candidateSha256') != candidate['sha256']
                        or outcome.get('publicationAllowed') is not False):
                    finding('candidate_outcome_binding_unverified', prefix + 'outcome.json')
        for name in KINDS:
            attempt_path = prefix + name + '.attempt.json'
            receipt_path = prefix + name + '.receipt.json'
            attempt, receipt = record(attempt_path), record(receipt_path)
            for path, item, fields in [(attempt_path, attempt, ['attemptedAt']),
                                       (receipt_path, receipt, ['attemptedAt', 'completedAt'])]:
                if item is None:
                    continue
                if item.get('url') != endpoints[name]:
                    finding('unexpected_endpoint_preserved', path)
                for field in fields:
                    try:
                        clocks.append(timestamp(item.get(field)))
                    except (ValueError, OverflowError):
                        finding('unknown_request_time', path)
            if receipt is not None:
                body = files.get(prefix + name + '.body')
                if (not body or body['kind'] != 'file' or receipt.get('bodySha256') != body['sha256']
                        or type(receipt.get('bodyBytes')) is not int or receipt['bodyBytes'] != body['bytes']):
                    finding('response_body_binding_unverified', receipt_path)
                if (type(receipt.get('status')) is not int or receipt['status'] != 200
                        or receipt.get('complete') is not True or receipt.get('headersComplete') is not True
                        or receipt.get('responseURL') != endpoints[name] or receipt.get('transportError') is not None
                        or receipt.get('workerTermination') != 'confirmed'):
                    finding('failed_or_uncertain_response_preserved', receipt_path)
        # Policy/admission are not replayed: their existence is not authorization.
        record(prefix + 'admission.json')
        record(prefix + 'robots-decisions.json')
    for path in sorted(set(files) - known):
        finding('unrecognized_artifact_preserved', path)
    return findings, clocks


def plan(root=ROOT, snapshots=()):
    snapshots = tuple(snapshots)
    report = readiness.inspect(root)
    result = {
        'schemaVersion': 'offline-state-migration-plan-v1',
        'status': 'review_plan_only',
        'collectionAuthorized': False, 'publicationAllowed': False, 'migrationAuthorized': False,
        'networkRequestsMade': 0, 'runtimeStateWritten': False,
        'snapshotScope': 'Only explicitly supplied frozen copies. Canonical runtime state contents are never opened by this planner.',
        'completePriorHistory': 'unknown_not_established_by_snapshot_inventory',
        'durableDestination': 'not_selected_or_registered',
        'repositoryBoundaryVerified': report['repositoryBoundaryVerified'],
        'baselineProvenance': report['baselineProvenance'],
        'retainedHoldStatements': report['retainedHoldStatements'],
        'holdDisposition': 'Every retained hold, lock, uncertain outcome and conflicting artifact remains unresolved. Absence is never clearance.',
        'snapshots': [], 'conflicts': [], 'issues': [],
        'historicalCadenceLowerBound': None,
        'cadenceMeaning': 'Maximum known accepted retrieval, attempt or completion plus seven days. Incomplete history makes the next permitted attempt unknown; this is not a next-run date.',
        'limitations': [
            'Admission and robots-decision objects are only parsed and inventoried; source-access authorization, body content and candidate semantics are not revalidated.',
            'Stable file observations do not prove an atomic export, complete history, source/destination equality or durable storage.',
            'The manifest is private when snapshots are supplied. No file contents, original journals or restrictions are changed.',
        ],
        'requiredReview': [
            'Obtain complete prior journals, endpoint restrictions, reservations and holds from every operational owner; record gaps explicitly.',
            'Preserve all inventoried bytes and their origin. Reconcile conflicts without overwriting or discarding either version.',
            'Review a private durable destination, single owner, atomic migration, exclusive locking, backups and restore/rollback tests before writing any state.',
            'Independently verify the frozen export, target inventory equality and unresolved hold semantics before canonical registration.',
            'Keep migration, activation, endpoint access and publication approvals separate. This report grants none of them.',
        ],
    }
    if not report['repositoryBoundaryVerified']:
        result['issues'].append({'code': 'repository_boundary_unverified'})
    if len(snapshots) > MAX_SNAPSHOTS:
        result['issues'].append({'code': 'snapshot_count_exceeds_bound'})
    if result['issues']:
        result['status'] = 'input_requires_review'
        return result
    provenance = report['baselineProvenance']
    try:
        baseline_bytes = readiness.read_file(pathlib.Path(root), readiness.PACKAGE + '/physician_refresh/baseline/records.json')
        if hashlib.sha256(baseline_bytes).hexdigest() != provenance['baselineSha256']:
            raise ValueError('Pinned baseline changed after inspection')
        source = json.loads(baseline_bytes)['source']
    except (OSError, ValueError):
        result['issues'].append({'code': 'pinned_baseline_reread_changed'})
        result['repositoryBoundaryVerified'] = False
        result['baselineProvenance'] = None
        result['status'] = 'input_requires_review'
        return result
    expected_baseline = {
        'schemaVersion': 'accepted-baseline-retrieval-v1',
        'baselineSha256': provenance['baselineSha256'], 'reviewReceiptSha256': provenance['reviewReceiptSha256'],
        'sourceURL': source['downloadUrl'], 'retrievedAt': source['capturedAt'],
        'sourceBodySha256': source['sourceBodySha256'], 'captureReceiptSha256': source['captureReceiptSha256'],
        'role': 'Original accepted successful retrieval; cadence floor, not a new collector request',
    }
    clocks = [timestamp(provenance['acceptedRetrieval'])]
    origins = {}
    for number, snapshot in enumerate(snapshots, 1):
        label = 'snapshot-' + str(number)
        try:
            artifacts, bodies = inventory(snapshot)
        except (OSError, ValueError):
            # Never leak exception paths or raw private content in the report.
            result['issues'].append({'code': 'snapshot_unreadable_unsafe_or_changed', 'snapshot': label})
            continue
        findings, observed = inspect_snapshot(artifacts, bodies, provenance, expected_baseline)
        clocks.extend(observed)
        result['snapshots'].append({'id': label, 'fileCount': sum(a['kind'] == 'file' for a in artifacts),
                                    'directoryCount': sum(a['kind'] == 'directory' for a in artifacts),
                                    'byteCount': sum(a['bytes'] for a in artifacts),
                                    'artifacts': artifacts, 'findings': findings})
        for artifact in artifacts:
            origins.setdefault(artifact['path'], []).append({'snapshot': label, 'kind': artifact['kind'], 'sha256': artifact['sha256']})
    result['conflicts'] = [{'path': path, 'versions': versions} for path, versions in sorted(origins.items())
                           if len({(v['kind'], v['sha256']) for v in versions}) > 1]
    try:
        result['historicalCadenceLowerBound'] = (max(clocks) + WEEK).isoformat()
    except OverflowError:
        result['issues'].append({'code': 'cadence_timestamp_out_of_range'})
    if result['issues'] or result['conflicts'] or any(s['findings'] for s in result['snapshots']):
        result['status'] = 'input_requires_review'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='append', default=[], type=pathlib.Path,
                        help='Explicit frozen private state copy; repeat to preserve/conflict-check multiple histories. Read-only.')
    args = parser.parse_args(argv)
    report = plan(snapshots=args.snapshot)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'review_plan_only' else 2


if __name__ == '__main__':
    raise SystemExit(main())
