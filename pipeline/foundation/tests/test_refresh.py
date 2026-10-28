import unittest,json,pathlib,copy,hashlib,tempfile,shutil
from physician_refresh.refresh import assess,Hold,load_baseline,ROOT,CSV_URL,META_URL
CAP=ROOT/'test-inputs'
class RefreshTests(unittest.TestCase):
 def setUp(self):
  self.csv=(CAP/'payments.body').read_bytes();self.meta=(CAP/'metadata.body').read_bytes();self.cr=json.loads((CAP/'payments.receipt.json').read_bytes());self.mr=json.loads((CAP/'metadata.receipt.json').read_bytes())
 def run_case(self):return assess(self.csv,self.meta,self.cr,self.mr)
 def set_csv(self,b):self.csv=b;self.cr.update(bodyBytes=len(b),bodySha256=hashlib.sha256(b).hexdigest())
 def set_meta(self,x):self.meta=json.dumps(x).encode();self.mr.update(bodyBytes=len(self.meta),bodySha256=hashlib.sha256(self.meta).hexdigest())
 def test_same_snapshot_zero_diff(self):
  r=self.run_case();self.assertEqual(r['diff']['candidateRecords'],435);self.assertEqual(r['diff']['changedAmounts'],[]);self.assertEqual(r['diff']['addedKeys'],[]);self.assertEqual(r['diff']['removedKeys'],[]);self.assertFalse(r['publicationAllowed'])
 def test_reproducible(self):self.assertEqual(self.run_case(),self.run_case())
 def test_change_report_no_sum(self):
  self.set_csv(self.csv.replace(b'287075013.00',b'287075014.00',1));r=self.run_case();self.assertEqual(len(r['diff']['changedAmounts']),1);self.assertFalse(r['diff']['financialSumComputed'])
 def test_metadata_changes_explicit(self):
  m=json.loads(self.meta);m['rowsUpdatedAt']+=1;self.set_meta(m);r=self.run_case();self.assertTrue(r['diff']['metadataChanged']);self.assertEqual(r['source']['sourceRowsUpdatedAtUnix'],m['rowsUpdatedAt'])
 def test_local_reads_bounded(self):
  from physician_refresh.prepare_candidate import bounded_read
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'large';p.write_bytes(b'a'*11)
   with self.assertRaises(ValueError):bounded_read(p,10)
 def test_new_known_category_year(self):
  line=self.csv.splitlines()[1].replace(b'2012-2013',b'2025-2026');self.set_csv(self.csv+b'\n'+line+b'\n');self.assertEqual(len(self.run_case()['diff']['addedKeys']),1)
 def test_removed_key_not_deleted_accepted(self):
  before=(ROOT/'baseline/records.json').read_bytes();self.set_csv(b'\n'.join(self.csv.splitlines()[:1]+self.csv.splitlines()[2:])+b'\n');self.assertEqual(len(self.run_case()['diff']['removedKeys']),1);self.assertEqual((ROOT/'baseline/records.json').read_bytes(),before)
 def test_unknown_label_held(self):
  self.set_csv(self.csv.replace(b'Fee for Service,287',b'Personal New Label,287',1))
  with self.assertRaises(Hold):self.run_case()
 def test_duplicate_no_dedup(self):
  self.set_csv(self.csv+b'\n'+self.csv.splitlines()[1]+b'\n')
  with self.assertRaises(Hold):self.run_case()
 def test_bad_amount(self):
  self.set_csv(self.csv.replace(b'287075013.00',b'NaN',1))
  with self.assertRaises(Hold):self.run_case()
 def test_null_not_zero(self):
  self.set_csv(self.csv.replace(b'287075013.00',b'',1))
  with self.assertRaises(Hold):self.run_case()
 def test_failure_no_retry(self):
  for status in (None,301,403,429,503):
   self.cr['status']=status
   with self.assertRaises(Hold):self.run_case()
 def test_exact_csv_media_type_required(self):
  self.cr['headers']['content-type']='application/x-text/csv'
  with self.assertRaises(Hold):self.run_case()
 def test_exact_metadata_media_type_required(self):
  self.mr['headers']['content-type']='application/json-malicious'
  with self.assertRaises(Hold):self.run_case()
 def test_incomplete_held(self):
  self.cr['complete']=False
  with self.assertRaises(Hold):self.run_case()
 def test_wrong_endpoint(self):
  self.cr['url']=CSV_URL+'&alternate=1'
  with self.assertRaises(Hold):self.run_case()
 def test_oversize_held(self):
  self.set_csv(b'a'*(1024*1024+1))
  with self.assertRaises(Hold):self.run_case()
 def test_timeout_budget(self):
  self.cr['completedAt']='2026-10-28T12:01:00+00:00'
  with self.assertRaises(Hold):self.run_case()
 def test_owner_changed(self):
  m=json.loads(self.meta);m['owner']['id']='different';self.set_meta(m)
  with self.assertRaises(Hold):self.run_case()
 def test_owner_name_changed(self):
  m=json.loads(self.meta);m['owner']['displayName']='different';self.set_meta(m)
  with self.assertRaises(Hold):self.run_case()
 def test_over_forty_seconds_held(self):
  self.cr['completedAt']='2026-10-28T12:00:41+00:00'
  with self.assertRaises(Hold):self.run_case()
 def test_metadata_columns_changed(self):
  m=json.loads(self.meta);m['columns'][0]['name']='Person';self.set_meta(m)
  with self.assertRaises(Hold):self.run_case()
 def test_license_changed(self):
  m=json.loads(self.meta);m['licenseId']='unknown';self.set_meta(m)
  with self.assertRaises(Hold):self.run_case()
 def test_missing_baseline_no_bootstrap(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(FileNotFoundError):load_baseline(d)
 def test_drifted_baseline_held(self):
  with tempfile.TemporaryDirectory() as d:
   shutil.copytree(ROOT/'baseline',pathlib.Path(d)/'base');(pathlib.Path(d)/'base/records.json').write_text('{}')
   with self.assertRaises(Hold):load_baseline(pathlib.Path(d)/'base')
if __name__=='__main__':unittest.main()
