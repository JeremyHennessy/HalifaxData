import pathlib,unittest,tempfile,json,subprocess,sys
from unittest.mock import patch
from physician_refresh import collector
ROOT=pathlib.Path(__file__).resolve().parents[1]
class PackageBoundary(unittest.TestCase):
 def test_repository_transport_disabled_before_state_or_network(self):
  self.assertFalse(collector.MANUAL_TRANSPORT_ENABLED)
  with patch('sys.argv',['collector','--state',str(collector.CANONICAL_STATE),'--manual-reviewed-capture']),patch.object(collector,'collect') as call:
   with self.assertRaises(ValueError):collector.main()
   call.assert_not_called()
 def test_synthetic_receipts_identified(self):
  for p in (ROOT/'physician_refresh/test-inputs').glob('*.receipt.json'):self.assertTrue(json.loads(p.read_bytes())['testFixtureOnly'])
 def test_no_runtime_state_or_outputs_bundled(self):
  self.assertFalse((ROOT/'physician_refresh/refresh-state.private').exists())
  self.assertFalse(any(ROOT.rglob('candidate.private.json')))
 def test_no_network_capability_in_policy_matcher(self):
  text=(ROOT/'source_policies/robots.py').read_text();self.assertNotIn('urllib.request',text);self.assertNotIn('requests.get',text)
