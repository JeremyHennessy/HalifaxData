"""Readiness is evidence of an inactive boundary, never collection authorization."""
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('collection_readiness', ROOT / 'pipeline/collection_readiness.py')
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class CollectionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / 'checkout'
        paths = list(readiness.PINS)
        paths += [readiness.PACKAGE + '/' + name for name in
                  json.loads((ROOT / readiness.PACKAGE / 'PACKAGE-MANIFEST.json').read_bytes())['files']]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def tearDown(self):
        self.tmp.cleanup()

    def inspect(self):
        return readiness.inspect(self.root)

    def assert_blocked(self, report):
        self.assertFalse(report['repositoryBoundaryVerified'])
        self.assertEqual(report['status'], 'repository_drift_requires_review')
        self.assertFalse(report['collectionAuthorized'])
        self.assertFalse(report['publicationAllowed'])
        self.assertTrue(report['issues'])

    def test_current_repository_has_checked_inactive_boundary(self):
        result = readiness.inspect(ROOT)
        self.assertTrue(result['repositoryBoundaryVerified'], result['issues'])
        self.assertTrue(result['canonicalCliTransportDisabled'])
        self.assertEqual(result['status'], 'inactive_requires_operational_review')
        self.assertFalse(result['collectionAuthorized'])
        self.assertFalse(result['publicationAllowed'])
        self.assertEqual(result['repositoryWorkflow'], 'reviewed_release_only_no_source_schedule')
        self.assertGreater(result['verifiedFileCount'], 30)

    def test_missing_state_and_elapsed_cadence_never_grant_access(self):
        result = self.inspect()
        self.assertFalse(result['canonicalStatePresent'])
        self.assertIn('unknown', result['endpointHoldHistory'])
        self.assertIn('unknown', result['externalSchedulerStatus'])
        self.assertEqual(result['baselineProvenance']['baselineOnlyCadenceFloor'], '2026-11-04T12:00:04.365699+00:00')
        self.assertIn('not a next-run date', result['baselineProvenance']['cadenceMeaning'])
        self.assertFalse(result['collectionAuthorized'])

    def test_exact_baseline_and_endpoints(self):
        result = self.inspect()['baselineProvenance']
        self.assertEqual(result['datasetId'], 'xpt9-p9is')
        self.assertEqual(result['observations'], 435)
        self.assertEqual(result['proposedEndpoints'], [
            'https://data.novascotia.ca/robots.txt',
            'https://data.novascotia.ca/api/views/xpt9-p9is.json',
            'https://data.novascotia.ca/api/views/xpt9-p9is/rows.csv?accessType=DOWNLOAD'])
        for name, key in [('records.json', 'baselineSha256'), ('publication-review.json', 'reviewReceiptSha256')]:
            self.assertEqual(result[key], hashlib.sha256((self.root / readiness.PACKAGE / 'physician_refresh/baseline' / name).read_bytes()).hexdigest())

    def test_retained_hold_statements_are_not_clearance(self):
        result = self.inspect()
        self.assertEqual([r['sourceId'] for r in result['retainedHoldStatements']], ['guide-001', 'guide-002', 'guide-003', 'fiscal-document-01'])
        self.assertEqual(len({r['url'] for r in result['retainedHoldStatements']}), 2)
        self.assertIn('not a complete or current', result['holdStatementScope'])
        self.assertIn('Absence is not clearance', result['holdStatementScope'])

    def test_deterministic_read_only_and_network_free(self):
        def snapshot():
            return {str(p.relative_to(self.root)): (p.stat().st_mtime_ns, p.read_bytes())
                    for p in self.root.rglob('*') if p.is_file()}
        before = snapshot()
        with patch.object(socket, 'socket', side_effect=AssertionError('Network forbidden')):
            one, two = self.inspect(), self.inspect()
        self.assertEqual(one, two)
        self.assertEqual(before, snapshot())
        self.assertEqual(one['networkRequestsMade'], 0)
        self.assertFalse(one['runtimeStateReadOrWritten'])

    def test_manifest_tamper_stops_before_following_entries(self):
        (self.root / readiness.PACKAGE / 'PACKAGE-MANIFEST.json').write_text('{"files":{"../../secret":"fake"}}')
        result = self.inspect()
        self.assert_blocked(result)
        self.assertIsNone(result['baselineProvenance'])
        self.assertIsNone(result['canonicalCliTransportDisabled'])

    def test_missing_and_malformed_manifest_fail_closed(self):
        path = self.root / readiness.PACKAGE / 'PACKAGE-MANIFEST.json'
        path.unlink()
        self.assert_blocked(self.inspect())
        path.write_text('{broken json')
        self.assert_blocked(self.inspect())

    def test_collector_tamper_is_not_imported_or_called(self):
        path = self.root / readiness.PACKAGE / 'physician_refresh/collector.py'
        path.write_text(path.read_text().replace('MANUAL_TRANSPORT_ENABLED=False', 'MANUAL_TRANSPORT_ENABLED=True') + '\nraise AssertionError("Must never import")\n')
        result = self.inspect()
        self.assert_blocked(result)
        self.assertIsNone(result['canonicalCliTransportDisabled'])

    def test_mutated_receipt_and_baseline_withhold_provenance(self):
        for name in ['records.json', 'publication-review.json']:
            path = self.root / readiness.PACKAGE / 'physician_refresh/baseline' / name
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            result = self.inspect()
            self.assert_blocked(result)
            self.assertIsNone(result['baselineProvenance'])
            path.write_bytes(original)

    def test_foundation_drift_withholds_retained_statements(self):
        for relative in ['data/foundation.json', 'data/publication-review.json']:
            path = self.root / relative
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            result = self.inspect()
            self.assert_blocked(result)
            self.assertIsNone(result['retainedHoldStatements'])
            path.write_bytes(original)

    def test_changed_workflow_is_unverified(self):
        path = self.root / '.github/workflows/verify.yml'
        path.write_text(path.read_text() + '\n# unreviewed change\n')
        result = self.inspect()
        self.assert_blocked(result)
        self.assertEqual(result['repositoryWorkflow'], 'unverified')

    def test_new_workflow_requires_review(self):
        (self.root / '.github/workflows/source.yml').write_text('on:\n  schedule:\n    - cron: "0 0 * * *"\n')
        result = self.inspect()
        self.assert_blocked(result)
        self.assertEqual(result['repositoryWorkflow'], 'unverified')

    def test_symlink_even_to_identical_file_requires_review(self):
        path = self.root / '.github/workflows/verify.yml'
        path.unlink()
        path.symlink_to(ROOT / '.github/workflows/verify.yml')
        self.assert_blocked(self.inspect())

    def test_symlink_directory_requires_review(self):
        path = self.root / readiness.PACKAGE / 'physician_refresh/baseline'
        shutil.rmtree(path)
        path.symlink_to(ROOT / readiness.PACKAGE / 'physician_refresh/baseline', target_is_directory=True)
        result = self.inspect()
        self.assert_blocked(result)
        self.assertIsNone(result['baselineProvenance'])

    def test_state_is_never_read_or_cleared(self):
        state = self.root / readiness.PACKAGE / 'physician_refresh/refresh-state.private'
        state.mkdir()
        sentinel = state / 'hold.json'
        sentinel.write_bytes(b'private content must not enter report')
        original = readiness.read_file
        def guarded(root, relative):
            self.assertNotIn('refresh-state.private', relative)
            return original(root, relative)
        with patch.object(readiness, 'read_file', side_effect=guarded):
            result = self.inspect()
        self.assert_blocked(result)
        self.assertTrue(result['canonicalStatePresent'])
        self.assertNotIn('private content', json.dumps(result))
        self.assertEqual(sentinel.read_bytes(), b'private content must not enter report')

    def test_dangling_state_symlink_is_not_missing_state(self):
        state = self.root / readiness.PACKAGE / 'physician_refresh/refresh-state.private'
        state.symlink_to(self.root / 'nonexistent')
        result = self.inspect()
        self.assert_blocked(result)
        self.assertTrue(result['canonicalStatePresent'])

    def test_path_traversal_and_absolute_paths_rejected(self):
        for value in ['../outside', '/etc/passwd', './data/foundation.json', 'data//foundation.json']:
            with self.assertRaises(ValueError):
                readiness.read_file(self.root, value)

    def test_cli_exit_code_is_boundary_not_authorization(self):
        good = self.inspect()
        bad = dict(good, repositoryBoundaryVerified=False)
        for report, code in [(good, 0), (bad, 2)]:
            output = io.StringIO()
            with patch.object(readiness, 'inspect', return_value=report), contextlib.redirect_stdout(output):
                self.assertEqual(readiness.main(), code)
            self.assertFalse(json.loads(output.getvalue())['collectionAuthorized'])

    def test_command_and_public_build_scope(self):
        scripts = json.loads((ROOT / 'package.json').read_text())['scripts']
        self.assertEqual(scripts['collection:readiness'], 'python3 pipeline/collection_readiness.py')
        # Existing build/foundation tests actually build and inspect the allowlist.
        source = (ROOT / 'scripts/build.py').read_text()
        self.assertNotIn('collection_readiness', source)
        self.assertNotIn('collection-readiness', source)


if __name__ == '__main__':
    unittest.main()
