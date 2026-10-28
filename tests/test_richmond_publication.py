import unittest,tempfile,pathlib,shutil,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from richmond_publication import richmond_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class RichmondPublicationTests(unittest.TestCase):
 def test_exact_public_subset_only(self):self.assertEqual(richmond_files(ROOT),['data/richmond-register/records.json','data/richmond-register/publication-review.json'])
 def test_absent_is_optional(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(richmond_files(pathlib.Path(tmp)),[])
 def test_modified_artifact_or_receipt_fails(self):
  for name in ['records.json','publication-review.json']:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/richmond-register',root/'data/richmond-register');p=root/'data/richmond-register'/name;p.chmod(0o644);p.write_text(p.read_text()+' ')
    with self.assertRaises(ValueError):richmond_files(root)
 def test_missing_receipt_fails(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/richmond-register',root/'data/richmond-register');(root/'data/richmond-register/publication-review.json').unlink()
   with self.assertRaises(FileNotFoundError):richmond_files(root)
