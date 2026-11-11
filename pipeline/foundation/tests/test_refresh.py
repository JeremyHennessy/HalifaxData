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
  self.cr['completedAt']='2026-10-28T12:00:43.000001+00:00'
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
 def set_times(self,receipt,start,headers,end):
  import datetime
  origin=datetime.datetime(2026,10,28,12,tzinfo=datetime.timezone.utc)
  for key,seconds in zip(('attemptedAt','headersReceivedAt','completedAt'),(start,headers,end)):
   receipt[key]=(origin+datetime.timedelta(seconds=seconds)).isoformat()
 def test_pair_boundary_and_overlap(self):
  self.set_times(self.cr,2,3,4);self.assertFalse(self.run_case()['publicationAllowed'])
  self.set_times(self.cr,1.999999,3,4)
  with self.assertRaises(Hold):self.run_case()
 def test_reversed_and_distant_pairs(self):
  for start in (-10,86400):
   with self.subTest(start=start):
    self.set_times(self.cr,start,start+1,start+2)
    with self.assertRaises(Hold):self.run_case()
 def test_pair_150_second_boundary(self):
  self.set_times(self.cr,148,149,150);self.assertEqual(self.run_case()['captureComparison']['elapsedSeconds'],150)
  self.set_times(self.cr,148,149,150.000001)
  with self.assertRaises(Hold):self.run_case()
 def test_individual_40_second_boundary(self):
  for receipt in (self.mr,self.cr):
   with self.subTest(url=receipt['url']):
    self.set_times(self.mr,0,1,40);self.set_times(self.cr,40,41,80)
    self.assertFalse(self.run_case()['publicationAllowed'])
    receipt['completedAt']=receipt['completedAt'].replace('+00:00','.000001+00:00')
    with self.assertRaises(Hold):self.run_case()
 def test_timezone_equivalence_and_missing_timezone(self):
  self.cr.update(attemptedAt='2026-10-28T08:00:02-04:00',headersReceivedAt='2026-10-28T13:00:03+01:00',completedAt='2026-10-28T12:00:04Z')
  self.assertEqual(self.run_case()['captureComparison']['elapsedSeconds'],4)
  self.cr['attemptedAt']='2026-10-28T12:00:02'
  with self.assertRaises(Hold):self.run_case()
 def test_adverse_optional_transport_fields(self):
  for receipt in (self.mr,self.cr):
   for field,value in [('responseURL','https://example.invalid'),('responseURL',None),('headersComplete',False),('transportError','failure'),('transportError',''),('workerTermination','unknown'),('workerTermination',None)]:
    with self.subTest(url=receipt['url'],field=field,value=value):
     receipt[field]=value
     with self.assertRaises(Hold):self.run_case()
     del receipt[field]
 def test_missing_and_positive_transport_fields(self):
  result=self.run_case();self.assertIn('unknown',result['captureComparison']['optionalTransportEvidence'])
  for receipt in (self.mr,self.cr):receipt.update(responseURL=receipt['url'],headersComplete=True,transportError=None,workerTermination='confirmed')
  self.assertFalse(self.run_case()['publicationAllowed'])
 def coverage(self):return self.run_case()['coverageComparison']
 def test_year_union_removed_new_unchanged(self):
  rows=self.csv.splitlines();year=rows[1].split(b',')[0];replacement=b'2025-2026'
  self.set_csv(b'\n'.join([rows[0]]+[r.replace(year,replacement,1) if r.startswith(year+b',') else r for r in rows[1:]])+b'\n')
  r=self.run_case();years=r['coverageComparison']['years'];by_year={x['reportingYearLabel']:x for x in years}
  self.assertEqual(list(by_year),sorted(by_year));old=by_year[year.decode()];new=by_year[replacement.decode()]
  self.assertEqual(old['candidateRecords'],0);self.assertEqual(len(old['removedKeys']),old['baselineRecords']);self.assertEqual(new['baselineRecords'],0);self.assertEqual(len(new['addedKeys']),new['candidateRecords'])
  for y in years:
   if y not in (old,new):self.assertEqual(y['addedKeys']+y['removedKeys']+y['changedKeys'],[])
  self.assertEqual(sum(y['baselineRecords'] for y in years),r['diff']['baselineRecords']);self.assertEqual(sum(y['candidateRecords'] for y in years),r['diff']['candidateRecords'])
  for local,glob in [('addedKeys','addedKeys'),('removedKeys','removedKeys')]:self.assertEqual([k for y in years for k in y[local]],r['diff'][glob])
  self.assertFalse(r['coverageComparison']['sourceCompletenessEstablished']);self.assertFalse(r['coverageComparison']['financialSumComputed']);self.assertFalse(r['captureComparison']['atomicSnapshotEstablished']);self.assertFalse(r['captureComparison']['wholeAttemptBudgetVerified']);self.assertFalse(r['captureComparison']['robotsAdmissionVerified']);self.assertFalse(r['publicationAllowed'])
 def test_year_changed_amount_and_reordered_rows(self):
  self.set_csv(self.csv.replace(b'287075013.00',b'287075014.00',1));r=self.run_case();coverage=r['coverageComparison']
  self.assertEqual([k for y in coverage['years'] for k in y['changedKeys']],[x['key'] for x in r['diff']['changedAmounts']])
  self.assertEqual(sum(len(y['changedKeys']) for y in coverage['years']),1)
  lines=self.csv.splitlines();self.set_csv(b'\n'.join(lines[:1]+list(reversed(lines[1:])))+b'\n');self.assertEqual(self.coverage(),coverage)
 def test_equal_year_count_key_replacement(self):
  import unittest.mock
  baseline=copy.deepcopy(load_baseline());record=baseline['records'][0];year=record['reportingYearLabel'];original=record['paymentSubcategory'];record['paymentSubcategory']='Baseline-only reviewed subcategory'
  # This synthetic baseline models a historical key replaced by another already-known key.
  with unittest.mock.patch('physician_refresh.refresh.load_baseline',return_value=baseline):
   result=self.run_case();y=next(x for x in result['coverageComparison']['years'] if x['reportingYearLabel']==year)
   self.assertEqual(y['baselineRecords'],y['candidateRecords']);self.assertEqual(len(y['addedKeys']),1);self.assertEqual(len(y['removedKeys']),1);self.assertEqual(y['changedKeys'],[])

if __name__=='__main__':unittest.main()
