import hashlib,json,pathlib,shutil,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from hrm_audit_context_publication import hrm_audit_context_files,HASH,REVIEW_HASH,SOURCE_HASH
import build
class HRMAnnualContextPublication(unittest.TestCase):
 def fixture(self,tmp):
  root=pathlib.Path(tmp)
  for path in ['hrm-audits','hrm-audit-context']:shutil.copytree(ROOT/'data'/path,root/'data'/path)
  return root
 def test_only_two_exact_files_allowed(self):
  self.assertEqual(hrm_audit_context_files(ROOT),['data/hrm-audit-context/context.json','data/hrm-audit-context/publication-review.json']);self.assertIn('app/hrm-audit-context.js',build.FILES)
 def test_absent_context_optional(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(hrm_audit_context_files(pathlib.Path(tmp)),[])
 def test_receipt_artifact_and_parent_fail_closed(self):
  for path in ['hrm-audit-context/context.json','hrm-audit-context/publication-review.json','hrm-audits/records.json','hrm-audits/publication-review.json']:
   with self.subTest(path=path),tempfile.TemporaryDirectory() as tmp:
    root=self.fixture(tmp);p=root/'data'/path;p.write_bytes(p.read_bytes()+b' ')
    with self.assertRaises(ValueError):hrm_audit_context_files(root)
 def test_missing_receipt_or_parent_not_admitted(self):
  for path in ['hrm-audit-context/publication-review.json','hrm-audits/records.json']:
   with tempfile.TemporaryDirectory() as tmp:
    root=self.fixture(tmp);(root/'data'/path).unlink()
    with self.assertRaises((ValueError,FileNotFoundError)):hrm_audit_context_files(root)
 def test_claimed_accepted_hash_cannot_authorize_modified_context(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.fixture(tmp);p=root/'data/hrm-audit-context/context.json';b=json.loads(p.read_text());b['measure']['resultPercent']=44;p.write_text(json.dumps(b));r=root/'data/hrm-audit-context/publication-review.json';review=json.loads(r.read_text());review['bundleSha256']=hashlib.sha256(p.read_bytes()).hexdigest();r.write_text(json.dumps(review))
   with self.assertRaises(ValueError):hrm_audit_context_files(root)
 def test_raw_source_and_private_notes_excluded(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.fixture(tmp)
   for name in ['source.pdf','page.png','notes.json']:(root/'data/hrm-audit-context'/name).write_bytes(b'private')
   self.assertEqual(len(hrm_audit_context_files(root)),2)
 def test_javascript_and_python_pins_match(self):
  js=(ROOT/'app/hrm-audit-context.js').read_text()
  for digest in [HASH,REVIEW_HASH,SOURCE_HASH]:self.assertIn(digest,js)
