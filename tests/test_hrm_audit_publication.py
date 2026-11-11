import hashlib,json,pathlib,shutil,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from hrm_audit_publication import hrm_audit_files,HASH,REVIEW_HASH
from collection_coverage import build_collection_coverage
import build
class HRMAuditPublication(unittest.TestCase):
 def fixture(self,tmp):
  root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/hrm-audits',root/'data/hrm-audits');return root
 def test_exact_reviewed_public_projection_only(self):
  self.assertEqual(hrm_audit_files(ROOT),['data/hrm-audits/records.json','data/hrm-audits/publication-review.json'])
  self.assertIn('app/hrm-audits.js',build.FILES)
  self.assertNotIn('data/hrm-audits/records.json',build.FILES)
 def test_absent_projection_optional(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(hrm_audit_files(pathlib.Path(tmp)),[])
 def test_missing_receipt_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.fixture(tmp);(root/'data/hrm-audits/publication-review.json').unlink()
   with self.assertRaises(FileNotFoundError):hrm_audit_files(root)
 def test_artifact_or_receipt_byte_change_rejected(self):
  for name in ['records.json','publication-review.json']:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    root=self.fixture(tmp);p=root/'data/hrm-audits'/name;p.write_bytes(p.read_bytes()+b' ')
    with self.assertRaisesRegex(ValueError,'Exact independently reviewed HRM bytes'):hrm_audit_files(root)
 def test_self_approved_or_pending_receipts_do_not_authorize_changed_facts(self):
  for status in ['accepted','pending']:
   with self.subTest(status=status),tempfile.TemporaryDirectory() as tmp:
    root=self.fixture(tmp);p=root/'data/hrm-audits/records.json';b=json.loads(p.read_text());b['records'][0]['statusAsReported']='Incomplete';p.write_text(json.dumps(b));r=root/'data/hrm-audits/publication-review.json';review=json.loads(r.read_text());review['status']=status;review['bundleSha256']=hashlib.sha256(p.read_bytes()).hexdigest();r.write_text(json.dumps(review))
    with self.assertRaises(ValueError):hrm_audit_files(root)
 def test_extra_private_files_cannot_enter_the_allowlist(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.fixture(tmp)
   for name in ['raw.pdf','page.png','private-notes.json']:(root/'data/hrm-audits'/name).write_bytes(b'private')
   self.assertEqual(len(hrm_audit_files(root)),2)
 def test_manifest_admission_uses_independent_receipt_pin_not_just_claimed_hash(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.fixture(tmp);shutil.copyfile(ROOT/'data/foundation.json',root/'data/foundation.json')
   p=root/'data/hrm-audits/publication-review.json';p.write_text(p.read_text()+' ')
   with self.assertRaisesRegex(ValueError,'Exact independently reviewed HRM bytes'):build_collection_coverage(root)
 def test_exact_source_and_receipt_hashes_match_javascript(self):
  js=(ROOT/'app/hrm-audits.js').read_text()
  for digest in [HASH,REVIEW_HASH]:self.assertIn(digest,js)
