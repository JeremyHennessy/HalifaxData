import copy, hashlib, json, unittest
from pathlib import Path
from build_foundation import build,load,dump,compare,publish_case,require_url

ROOT=Path(__file__).parent
class FoundationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.seed=load(ROOT/'research-seed.json');cls.data=build(cls.seed)
 def test_catalogue_exact(self):
  guide=[s for s in self.data['sources'] if s['inventoryId']]
  self.assertEqual(len(guide),139);self.assertEqual(len(set(s['url'] for s in guide)),121)
  self.assertEqual([s['inventoryRow'] for s in guide],list(range(2,141)))
 def test_catalogue_not_integration(self):
  for s in self.data['sources'][:139]:self.assertFalse(s['status']['acquired']);self.assertFalse(s['status']['normalized']);self.assertFalse(s['status']['monitored'])
 def test_exact_decimal_values(self):
  self.assertEqual(len(self.data['moneyFacts']),29)
  for f in self.data['moneyFacts']:self.assertIsInstance(f['rawValue'],str)
 def test_dash_not_zero(self):self.assertIsNone(self.data['reportedSymbols'][0]['rawValue'])
 def test_no_source_hash_invention(self):
  for r in self.data['evidenceRecords']:self.assertIsNone(r['sourceSnapshotHash'])
 def test_traceable(self):
  sources={s['id'] for s in self.data['sources']};ev={e['id'] for e in self.data['evidenceRecords']}
  for f in self.data['moneyFacts']:self.assertIn(f['sourceId'],sources);self.assertIn(f['evidenceId'],ev);self.assertTrue(f['sourceLocator'])
 def pair(self):
  c=self.data['investigations'][0];d={f['id']:f for f in self.data['moneyFacts']};return copy.deepcopy(d[c['moneyFactIds'][0]]),copy.deepcopy(d[c['moneyFactIds'][1]])
 def test_difference(self):
  a,b=self.pair();self.assertEqual(compare(a,b),'53592')
 def test_dimensions_fail_closed(self):
  for key in ['currency','metric','unit','multiplier','accountingBasis','reportingPerimeter','measureType','entity']:
   a,b=self.pair();b[key]=None
   with self.subTest(key=key),self.assertRaises(ValueError):compare(a,b)
 def test_period_fails_closed(self):
  a,b=self.pair();b['period']['start']='2025-04-01'
  with self.assertRaises(ValueError):compare(a,b)
 def test_missing_not_zero(self):
  a,b=self.pair();b['rawValue']=None
  with self.assertRaises(ValueError):compare(a,b)
 def test_stock_not_flow(self):
  a,b=self.pair();a['measureType']=b['measureType']='stock'
  with self.assertRaises(ValueError):compare(a,b)
 def test_private_case_blocked(self):
  for status in ['automatically_flagged_unreviewed','under_investigation']:
   c=copy.deepcopy(self.data['investigations'][0]);c['status']=status
   with self.assertRaises(ValueError):publish_case(c)
 def test_allegation_gate(self):
  c=copy.deepcopy(self.data['investigations'][0]);c['publication']['consequentialAllegation']=True
  with self.assertRaises(ValueError):publish_case(c)
 def test_missing_clearance(self):
  c=copy.deepcopy(self.data['investigations'][0]);c['publication']={}
  with self.assertRaises(ValueError):publish_case(c)
 def test_unsafe_url(self):
  for u in ['javascript:alert(1)','https://ok.test/" onclick="x','http://not-secure.test','https://x.test/\\evil']:
   with self.assertRaises(ValueError):require_url(u)
 def test_schema_drift(self):
  s=copy.deepcopy(self.seed);s['inventory'][0]['values'].append('new')
  with self.assertRaises(ValueError):build(s)
 def test_unverified_fact(self):
  s=copy.deepcopy(self.seed);s['verifiedFacts'][0]['status']='unknown'
  with self.assertRaises(ValueError):build(s)
 def test_determinism(self):self.assertEqual(dump(build(self.seed)),dump(build(load(ROOT/'research-seed.json'))))
 def test_no_old_import(self):
  code=(ROOT/'build_foundation.py').read_text();self.assertNotIn('/tmp/',code);self.assertNotIn('build024',code);self.assertNotIn('public-award:',code)
 def test_no_named_private_cases(self):
  text=dump(self.data)
  for token in ['PO2070887247','PO2070837342','Slayter','Fathom']:self.assertNotIn(token,text)
if __name__=='__main__':unittest.main()

class HardenedInputTests(unittest.TestCase):
 setUpClass=classmethod(FoundationTests.setUpClass.__func__)
 pair=FoundationTests.pair
 def test_nonfinite(self):
  for value in ['NaN','Infinity','-Infinity']:
   a,b=self.pair();b['rawValue']=value
   with self.assertRaises(ValueError):compare(a,b)
 def test_unknown_unit(self):
  s=copy.deepcopy(self.seed);s['verifiedFacts'][0]['unit']='unknown'
  with self.assertRaises(ValueError):build(s)
 def test_duplicate_source(self):
  s=copy.deepcopy(self.seed);s['documents'].append(s['documents'][0])
  with self.assertRaises(ValueError):build(s)
 def test_duplicate_fact(self):
  s=copy.deepcopy(self.seed);s['verifiedFacts'][-1]=s['verifiedFacts'][0]
  with self.assertRaises(ValueError):build(s)
 def test_missing_source(self):
  s=copy.deepcopy(self.seed);s['verifiedFacts'][0]['source_id']='missing'
  with self.assertRaises(ValueError):build(s)
 def test_unknown_status(self):
  c=copy.deepcopy(self.data['investigations'][0]);c['status']='anything'
  with self.assertRaises(ValueError):publish_case(c)
 def test_missing_review(self):
  c=copy.deepcopy(self.data['investigations'][0]);del c['publication']['reviewId']
  with self.assertRaises(ValueError):publish_case(c)
 def test_bool_multiplier(self):
  a,b=self.pair();a['multiplier']=b['multiplier']=True
  with self.assertRaises(ValueError):compare(a,b)
