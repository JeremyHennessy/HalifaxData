"""Synthetic-only migration rehearsals. Never invoke collection or read live state."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
import collection_migration as migration


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / 'snapshot'
        self.path.mkdir()
        self.provenance = migration.readiness.inspect(ROOT)['baselineProvenance']
        source = json.loads((ROOT / migration.readiness.PACKAGE / 'physician_refresh/baseline/records.json').read_bytes())['source']
        self.baseline = {
            'schemaVersion': 'accepted-baseline-retrieval-v1',
            'baselineSha256': self.provenance['baselineSha256'],
            'reviewReceiptSha256': self.provenance['reviewReceiptSha256'],
            'sourceURL': source['downloadUrl'], 'retrievedAt': source['capturedAt'],
            'sourceBodySha256': source['sourceBodySha256'], 'captureReceiptSha256': source['captureReceiptSha256'],
            'role': 'Original accepted successful retrieval; cadence floor, not a new collector request',
        }
        self.write('baseline-retrieval.json', self.baseline)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, value):
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value if isinstance(value, bytes) else encoded(value))

    def plan(self, *paths):
        return migration.plan(ROOT, paths or [self.path])

    def codes(self, result):
        return {f['code'] for s in result['snapshots'] for f in s['findings']}

    def attempt(self):
        prefix = 'attempts/synthetic-1/'
        self.write(prefix + 'admission.json', {'synthetic': True})
        self.write(prefix + 'robots-decisions.json', {'synthetic': True})
        candidate = b'{"synthetic":true,"publicationAllowed":false}\n'
        self.write(prefix + 'candidate.private.json', candidate)
        self.write(prefix + 'outcome.json', {
            'status': 'candidate_prepared', 'completedAtEpoch': 1794355200,
            'publicationAllowed': False, 'candidateSha256': hashlib.sha256(candidate).hexdigest(),
        })
        for name, url in zip(migration.KINDS, self.provenance['proposedEndpoints']):
            self.write(prefix + name + '.attempt.json', {'url': url, 'attemptedAt': '2026-11-11T00:00:00Z'})
            body = b'synthetic response only'
            self.write(prefix + name + '.body', body)
            self.write(prefix + name + '.receipt.json', {
                'url': url, 'attemptedAt': '2026-11-11T00:00:00Z', 'completedAt': '2026-11-11T00:00:01Z',
                'bodySha256': hashlib.sha256(body).hexdigest(), 'bodyBytes': len(body),
                'status': 200, 'complete': True, 'headersComplete': True,
                'responseURL': url, 'transportError': None, 'workerTermination': 'confirmed',
            })
        return prefix

    def edit(self, relative, **fields):
        value = json.loads((self.path / relative).read_bytes())
        value.update(fields)
        self.write(relative, value)

    def assert_non_authorizing(self, result):
        for field in ['collectionAuthorized', 'publicationAllowed', 'migrationAuthorized', 'runtimeStateWritten']:
            self.assertIs(result[field], False)
        self.assertEqual(result['networkRequestsMade'], 0)
        self.assertIn('unknown', result['completePriorHistory'])
        self.assertEqual(result['durableDestination'], 'not_selected_or_registered')

    def test_no_snapshot_retains_unknown_history_original_floor_and_holds(self):
        result = migration.plan(ROOT)
        self.assertEqual(result['snapshots'], [])
        self.assertEqual(result['historicalCadenceLowerBound'], '2026-11-04T12:00:04.365699+00:00')
        self.assertEqual(len(result['retainedHoldStatements']), 4)
        self.assertEqual(len({h['url'] for h in result['retainedHoldStatements']}), 2)
        self.assert_non_authorizing(result)

    def test_baseline_only_copy_does_not_establish_complete_history(self):
        result = self.plan()
        self.assertEqual(result['status'], 'review_plan_only')
        self.assertEqual(result['snapshots'][0]['fileCount'], 1)
        self.assert_non_authorizing(result)

    def test_success_shaped_history_advances_only_historical_floor(self):
        self.attempt()
        result = self.plan()
        self.assertEqual(result['status'], 'review_plan_only')
        self.assertEqual(result['historicalCadenceLowerBound'], '2026-11-18T00:00:01+00:00')
        self.assertIn('not a next-run date', result['cadenceMeaning'])
        self.assert_non_authorizing(result)

    def test_exact_inventory_preserves_unknown_bytes_without_outputting_them(self):
        secret = b'synthetic private secret must never be output'
        self.write('unclassified.bin', secret)
        result = self.plan()
        self.assertIn('unrecognized_artifact_preserved', self.codes(result))
        artifact = next(a for a in result['snapshots'][0]['artifacts'] if a['path'] == 'unclassified.bin')
        self.assertEqual(artifact['sha256'], hashlib.sha256(secret).hexdigest())
        self.assertNotIn(secret.decode(), json.dumps(result))
        self.assertNotIn(str(self.path), json.dumps(result))

    def test_duplicate_snapshot_is_preserved_without_conflict(self):
        result = self.plan(self.path, self.path)
        self.assertEqual(result['conflicts'], [])
        self.assertEqual(len(result['snapshots']), 2)

    def test_conflicting_versions_remain_separate(self):
        other = self.path.parent / 'other'
        shutil.copytree(self.path, other)
        (other / 'baseline-retrieval.json').write_bytes(b'{}')
        result = self.plan(self.path, other)
        self.assertEqual(result['status'], 'input_requires_review')
        self.assertEqual(result['conflicts'][0]['path'], 'baseline-retrieval.json')
        self.assertEqual(len(result['conflicts'][0]['versions']), 2)
        self.assertIn('accepted_baseline_history_mismatch', self.codes(result))

    def test_file_directory_conflict_is_not_equal(self):
        other = self.path.parent / 'other'
        shutil.copytree(self.path, other)
        self.write('unknown', b'')
        (other / 'unknown').mkdir()
        result = self.plan(self.path, other)
        self.assertEqual(result['conflicts'][0]['path'], 'unknown')

    def test_hold_and_lock_are_preserved_even_if_malformed(self):
        self.write('hold.json', b'not json private hold')
        self.write('active.lock', b'')
        result = self.plan()
        self.assertTrue({'persistent_hold_preserved', 'unresolved_lock_preserved'} <= self.codes(result))
        self.assertEqual((self.path / 'hold.json').read_bytes(), b'not json private hold')

    def test_missing_baseline_requires_review(self):
        (self.path / 'baseline-retrieval.json').unlink()
        self.assertIn('missing_journal_record', self.codes(self.plan()))

    def test_incomplete_empty_attempt_directory_requires_review(self):
        (self.path / 'attempts/interrupted').mkdir(parents=True)
        result = self.plan()
        self.assertIn('missing_journal_record', self.codes(result))
        self.assertEqual(result['snapshots'][0]['directoryCount'], 2)

    def test_failed_outcome_remains_held(self):
        prefix = self.attempt()
        self.edit(prefix + 'outcome.json', status='held_no_retry')
        self.assertIn('failed_or_unknown_outcome_preserved', self.codes(self.plan()))

    def test_claimed_success_does_not_hide_uncertain_response(self):
        prefix = self.attempt()
        changes = [{'status': 403}, {'complete': False}, {'headersComplete': False},
                   {'responseURL': 'https://example.invalid/redirect'}, {'transportError': 'timeout'},
                   {'workerTermination': 'unknown'}, {'status': True}]
        path = prefix + 'payments.receipt.json'
        original = (self.path / path).read_bytes()
        for change in changes:
            with self.subTest(change=change):
                self.write(path, original)
                self.edit(path, **change)
                self.assertIn('failed_or_uncertain_response_preserved', self.codes(self.plan()))

    def test_body_and_candidate_hash_mismatch_require_review(self):
        prefix = self.attempt()
        self.write(prefix + 'payments.body', b'mutated')
        self.write(prefix + 'candidate.private.json', b'{}')
        result = self.plan()
        self.assertTrue({'response_body_binding_unverified', 'candidate_outcome_binding_unverified'} <= self.codes(result))

    def test_unexpected_endpoint_is_not_mapped_or_cleared(self):
        prefix = self.attempt()
        self.edit(prefix + 'payments.attempt.json', url='https://example.invalid/other')
        self.assertIn('unexpected_endpoint_preserved', self.codes(self.plan()))

    def test_missing_and_naive_request_times_require_review(self):
        prefix = self.attempt()
        for value in [None, '2026-11-11T00:00:00', 'bad time', False]:
            with self.subTest(value=value):
                self.edit(prefix + 'payments.receipt.json', completedAt=value)
                self.assertIn('unknown_request_time', self.codes(self.plan()))

    def test_invalid_epoch_requires_review(self):
        prefix = self.attempt()
        for value in [True, None, '1794441600', 10**100]:
            with self.subTest(value=value):
                self.edit(prefix + 'outcome.json', completedAtEpoch=value)
                self.assertIn('unknown_completion_time', self.codes(self.plan()))

    def test_duplicate_keys_and_nonfinite_json_are_rejected(self):
        for body in [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'null', b'\xff']:
            with self.subTest(body=body):
                self.write('baseline-retrieval.json', body)
                self.assertIn('malformed_journal_record', self.codes(self.plan()))

    def test_symlink_root_parent_file_and_directory_are_not_read(self):
        link = self.path.parent / 'link'
        link.symlink_to(self.path, target_is_directory=True)
        for target in [link, link / 'nested']:
            result = self.plan(target)
            self.assertEqual(result['snapshots'], [])
            self.assertTrue(result['issues'])
        for name, target in [('link-file', self.path / 'baseline-retrieval.json'), ('link-directory', self.path)]:
            path = self.path / name
            path.symlink_to(target)
            result = self.plan()
            self.assertEqual(result['snapshots'], [])
            path.unlink()

    def test_fifo_is_rejected_without_blocking(self):
        os.mkfifo(self.path / 'fifo')
        result = self.plan()
        self.assertTrue(result['issues'])
        self.assertEqual(result['snapshots'], [])

    def test_limits_bound_files_entries_total_bytes_and_depth(self):
        for name, value in [('MAX_FILES', 0), ('MAX_ENTRIES', 0), ('MAX_FILE_BYTES', 1), ('MAX_TOTAL_BYTES', 1)]:
            with self.subTest(name=name), patch.object(migration, name, value):
                self.assertTrue(self.plan()['issues'])
        (self.path / 'a/b/c/d/e').mkdir(parents=True)
        self.assertTrue(self.plan()['issues'])

    def test_missing_snapshot_and_too_many_inputs_fail_closed(self):
        self.assertTrue(self.plan(self.path / 'absent')['issues'])
        result = self.plan(*([self.path] * 9))
        self.assertEqual(result['snapshots'], [])
        self.assertEqual(result['issues'][0]['code'], 'snapshot_count_exceeds_bound')

    def test_snapshot_changes_are_detected(self):
        original = migration.os.fstat
        calls = 0
        def altered(fd):
            nonlocal calls
            calls += 1
            observed = original(fd)
            if calls == 3:
                self.write('baseline-retrieval.json', b'mutated during read')
            return observed
        with patch.object(migration.os, 'fstat', side_effect=altered):
            self.assertTrue(self.plan()['issues'])

    def test_repository_drift_stops_before_snapshot_read(self):
        report = migration.readiness.inspect(ROOT)
        report['repositoryBoundaryVerified'] = False
        with patch.object(migration.readiness, 'inspect', return_value=report), patch.object(migration, 'inventory', side_effect=AssertionError('Must not read')):
            result = self.plan()
        self.assertEqual(result['status'], 'input_requires_review')
        self.assertEqual(result['snapshots'], [])

    def test_deterministic_read_only_network_free(self):
        self.attempt()
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.path.rglob('*') if p.is_file()}
        with patch.object(socket, 'socket', side_effect=AssertionError('No network')):
            one, two = self.plan(), self.plan()
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.path.rglob('*') if p.is_file()}
        self.assertEqual(one, two)
        self.assertEqual(before, after)
        self.assert_non_authorizing(one)

    def test_cli_exit_codes_never_authorize(self):
        for snapshots, code in [([], 0), (['--snapshot', str(self.path / 'absent')], 2)]:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(migration.main(snapshots), code)
            self.assert_non_authorizing(json.loads(output.getvalue()))

    def test_later_hold_and_lock_clocks_do_not_reset_cadence(self):
        self.write('hold.json', {'completedAtEpoch': 1794441600})
        self.write('active.lock', {'startedAt': '2026-11-13T00:00:00Z'})
        result = self.plan()
        self.assertEqual(result['historicalCadenceLowerBound'], '2026-11-20T00:00:00+00:00')
        self.assertTrue({'persistent_hold_preserved', 'unresolved_lock_preserved'} <= self.codes(result))
        self.assert_non_authorizing(result)

    def test_invalid_hold_and_lock_clocks_remain_unknown(self):
        self.write('hold.json', {'completedAtEpoch': True})
        self.write('active.lock', {'startedAt': '2026-11-13'})
        self.assertIn('unknown_hold_or_lock_time', self.codes(self.plan()))

    def test_reserved_attempts_path_must_be_a_directory(self):
        self.write('attempts', b'not a directory')
        self.assertIn('journal_directory_type_invalid', self.codes(self.plan()))

    def test_deep_json_is_a_finding_not_a_crash(self):
        self.write('baseline-retrieval.json', b'{"nested":' + b'[' * 20000 + b'0' + b']' * 20000 + b'}')
        result = self.plan(self.path, self.path)
        self.assertEqual(len(result['snapshots']), 2)
        self.assertIn('malformed_journal_record', self.codes(result))

    def test_baseline_change_after_pin_check_stops_snapshot_read(self):
        report = migration.readiness.inspect(ROOT)
        with patch.object(migration.readiness, 'inspect', return_value=report), \
                patch.object(migration.readiness, 'read_file', return_value=b'{"source":{}}'), \
                patch.object(migration, 'inventory', side_effect=AssertionError('Must not read')):
            result = self.plan()
        self.assertFalse(result['repositoryBoundaryVerified'])
        self.assertIsNone(result['baselineProvenance'])
        self.assertEqual(result['issues'][0]['code'], 'pinned_baseline_reread_changed')

    def test_no_collector_import_or_public_build_inclusion(self):
        self.assertNotIn('physician_refresh.collector', sys.modules)
        source = (ROOT / 'scripts/build.py').read_text()
        self.assertNotIn('collection_migration', source)
        scripts = json.loads((ROOT / 'package.json').read_text())['scripts']
        self.assertEqual(scripts['collection:migration-plan'], 'python3 pipeline/collection_migration.py')


if __name__ == '__main__':
    unittest.main()
