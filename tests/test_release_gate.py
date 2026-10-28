import hashlib,importlib.util,json,pathlib,shutil,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build
class ReleaseGate(unittest.TestCase):
 def workspace(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=pathlib.Path(self.temp.name)
  for name in build.FILES:
   target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
  return root
 def test_final_foundation_matches_review_and_reproducible_seed(self):
  receipt=json.loads((ROOT/'data/publication-review.json').read_text());body=(ROOT/'data/foundation.json').read_bytes()
  self.assertEqual(hashlib.sha256(body).hexdigest(),receipt['bundleSha256'])
  spec=importlib.util.spec_from_file_location('fresh_generator',ROOT/'pipeline/build_foundation.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  regenerated=module.dump(module.build(module.load(ROOT/'pipeline/research-seed.json'))).encode()
  self.assertEqual(regenerated,body)
 def test_modified_bundle_bytes_rejected_before_publication(self):
  root=self.workspace();path=root/'data/foundation.json';path.write_bytes(path.read_bytes()+b' ')
  with patch.object(build,'ROOT',root),patch.object(build,'OUT',root/'dist'),self.assertRaises(AssertionError):build.build()
 def test_missing_review_rejected(self):
  root=self.workspace();(root/'data/publication-review.json').unlink()
  with patch.object(build,'ROOT',root),patch.object(build,'OUT',root/'dist'),self.assertRaises(RuntimeError):build.build()
 def test_unexpected_public_output_rejected(self):
  root=self.workspace();(root/'dist').mkdir();(root/'dist/private-case.json').write_text('{}')
  with patch.object(build,'ROOT',root),patch.object(build,'OUT',root/'dist'),patch.dict('os.environ',{'SOURCE_COMMIT_SHA':'a'*40}),self.assertRaises(RuntimeError):build.build()
if __name__=='__main__':unittest.main()

class ReviewReceiptPrivacy(unittest.TestCase):
 def test_private_extra_metadata_rejected(self):
  from review_receipts import validate_receipt
  for kind,path in [('foundation','data/publication-review.json'),('tender','data/tenders/publication-review.json')]:
   receipt=json.loads((ROOT/path).read_text());validate_receipt(receipt,kind);receipt['privateNotes']={'person':'secret'}
   with self.assertRaises(ValueError):validate_receipt(receipt,kind)

class TenderReviewScope(unittest.TestCase):
 def test_receipt_field_scope_must_match_index(self):
  from tender_publication import tender_files
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);folder=root/'data/tenders';folder.mkdir(parents=True)
   shutil.copyfile(ROOT/'data/tenders/tender-index.json',folder/'tender-index.json')
   receipt=json.loads((ROOT/'data/tenders/publication-review.json').read_text());receipt['fieldNames']=['vendor']
   (folder/'publication-review.json').write_text(json.dumps(receipt))
   with self.assertRaisesRegex(ValueError,'Review field scope'):tender_files(root)

class ReportingAdmission(unittest.TestCase):
 def test_case_inputs_and_nested_fields_are_bound_to_public_rows(self):
  from reporting_publication import reporting_files
  self.assertEqual(len(reporting_files(ROOT)),2)
  for change in ('private','input','claim'):
   with tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);folder=root/'data/reporting-question';folder.mkdir(parents=True)
    (root/'data/municipal').mkdir();shutil.copyfile(ROOT/'data/municipal/records.json',root/'data/municipal/records.json')
    b=json.loads((ROOT/'data/reporting-question/case.json').read_text());receipt=json.loads((ROOT/'data/reporting-question/publication-review.json').read_text())
    if change=='private':b['publication']['privateNotes']='unreviewed'
    elif change=='input':b['evidence'][0]['portal']['operatingBalance']='123'
    else:b['consequentialAllegation']=True
    body=json.dumps(b).encode();(folder/'case.json').write_bytes(body);receipt['bundleSha256']=hashlib.sha256(body).hexdigest();(folder/'publication-review.json').write_text(json.dumps(receipt))
    with self.assertRaises(ValueError):reporting_files(root)

class CollectionCoverage(unittest.TestCase):
 def test_coverage_counts_and_receipts_are_rebuilt_without_changing_inventory(self):
  from collection_coverage import build_collection_coverage
  before=(ROOT/'data/foundation.json').read_bytes();coverage=build_collection_coverage(ROOT)
  self.assertEqual(coverage['guideReferenceCount'],139)
  self.assertEqual(len(coverage['collections']),19)
  self.assertEqual(next(c for c in coverage['collections'] if c['id']=='tenders')['count'],33670)
  self.assertEqual((ROOT/'data/foundation.json').read_bytes(),before)
  self.assertTrue(all(not c['scheduledRefreshConfigured'] and not c['completeSourceCoverage'] for c in coverage['collections']))
