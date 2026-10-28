import unittest,copy
from unittest.mock import patch
from watchdog_checks import adapters as fixtures
from watchdog_checks.adapters import build
from watchdog_checks.engine import run,evaluate,number,InvalidDeclaration
class RunnerTests(unittest.TestCase):
 def setUp(self):self.f=build();self.rule=self.f['rules'][0];self.facts={f['id']:f for f in self.f['facts']}
 def test_fixture_outcomes(self):self.assertEqual(run(self.f)['counts'],{'flagged_unreviewed':1,'explained':3,'insufficient_evidence':2})
 def test_exact_decimal_not_float(self):
  r=run(self.f)['results'][0];self.assertEqual(r['calculation']['left'],'68201.98');self.assertEqual(r['calculation']['right'],'67201.98');self.assertEqual(r['calculation']['residual'],'1000.00');self.assertFalse(r['monetaryAmountEstablished'])
 def test_explained_scope_only(self):
  for r in run(self.f)['results'][1:4]:self.assertEqual(r['status'],'explained');self.assertEqual(r['calculation']['residual'],'0');self.assertFalse(r['publicationAllowed'])
 def test_municipal_mapping_fail_closed(self):
  for r in run(self.f)['results'][4:]:self.assertEqual(r['status'],'insufficient_evidence');self.assertIsNone(r['calculation']);self.assertIn('Accounting/field mapping not established',r['reasons'])
 def test_unknown_currency_monetary_blocked(self):
  self.rule['mode']='monetary_comparison';r=evaluate(self.rule,self.facts);self.assertEqual(r['status'],'insufficient_evidence');self.assertIsNone(r['calculation']);self.assertIn('Unknown or incompatible currency',r['reasons'])
 def test_unverified_financial_basis_blocked(self):
  self.rule['mode']='monetary_comparison'
  for f in self.facts.values():f['currency']='CAD'
  r=evaluate(self.rule,self.facts);self.assertEqual(r['status'],'insufficient_evidence');self.assertIn('Financial accounting basis not verified',r['reasons'])
 def test_cross_source_blocked(self):
  self.facts[self.rule['left'][0]['factId']]['sourceSnapshotSha256']='0'*64;r=evaluate(self.rule,self.facts);self.assertEqual(r['status'],'insufficient_evidence');self.assertIsNone(r['calculation'])
 def test_mixed_scope_blocked(self):
  self.facts[self.rule['left'][0]['factId']]['scopeKey']='different-year';self.assertEqual(evaluate(self.rule,self.facts)['status'],'insufficient_evidence')
 def test_unknown_scope_blocked(self):
  self.rule['basis']['scopeKey']=None
  for f in self.facts.values():f['scopeKey']=None
  self.assertEqual(evaluate(self.rule,self.facts)['status'],'insufficient_evidence')
 def test_mixed_units_blocked(self):
  self.facts[self.rule['left'][0]['factId']]['unit']='millions';self.assertEqual(evaluate(self.rule,self.facts)['status'],'insufficient_evidence')
 def test_missing_null_not_zero(self):
  f=self.facts[self.rule['left'][0]['factId']];f['value']=None;f['availability']='missing';self.assertIsNone(evaluate(self.rule,self.facts)['calculation'])
 def test_missing_fact_blocked(self):
  del self.facts[self.rule['left'][0]['factId']];self.assertEqual(evaluate(self.rule,self.facts)['status'],'insufficient_evidence')
 def test_total_cannot_be_component(self):
  self.facts[self.rule['left'][0]['factId']]['role']='printed_total'
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_repeated_term_rejected(self):
  self.rule['left'].append(copy.deepcopy(self.rule['left'][0]))
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_same_source_cell_cannot_alias_duplicate(self):
  first=self.rule['left'][0]['factId'];fake=copy.deepcopy(self.facts[first]);fake['id']='fake';self.facts['fake']=fake;self.rule['left'].append({'factId':'fake','coefficient':1})
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_duplicate_native_cell_across_projections_rejected(self):
  a,b=[self.rule['left'][i]['factId'] for i in (0,1)]
  self.facts[b]['nativeCellLocator']=copy.deepcopy(self.facts[a]['nativeCellLocator']);self.facts[b]['sourceSnapshotSha256']=self.facts[a]['sourceSnapshotSha256'];self.facts[b]['artifactSha256']='f'*64;self.facts[b]['sourceLocator']={'jsonPointer':'/different/projection'}
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_fact_lookup_identity_rejected(self):
  self.facts[self.rule['left'][0]['factId']]['id']='wrong'
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_native_locator_cannot_include_projection_path(self):
  self.facts[self.rule['left'][0]['factId']]['nativeCellLocator']['jsonPointer']='/different'
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_receipt_bytes_pinned(self):
  with patch.dict(fixtures.RECEIPT_SHAS,{'shelburne':'0'*64}):
   with self.assertRaises(ValueError):fixtures.load('shelburne')
 def test_bad_number_rejected(self):
  for v in ['NaN','Infinity','1e9','__import__("os")','1,000','',1.1,True]:
   with self.assertRaises(InvalidDeclaration):number(v)
 def test_missing_provenance_rejected(self):
  self.facts[self.rule['left'][0]['factId']]['sourceLocator']=None
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_unknown_operation_rejected(self):
  self.rule['operation']='eval'
  with self.assertRaises(InvalidDeclaration):evaluate(self.rule,self.facts)
 def test_duplicate_fixture_ids_rejected(self):
  self.f['facts'].append(copy.deepcopy(self.f['facts'][0]))
  with self.assertRaises(InvalidDeclaration):run(self.f)
 def test_deterministic(self):self.assertEqual(run(self.f),run(build()))
 def test_input_unchanged(self):
  before=copy.deepcopy(self.f);run(self.f);self.assertEqual(self.f,before)
if __name__=='__main__':unittest.main()
