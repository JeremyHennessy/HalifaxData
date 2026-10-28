import unittest,tempfile,pathlib,shutil,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from water_approvals_publication import water_approval_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class AdditionalWaterTests(unittest.TestCase):
 def test_exact_accept(self):self.assertEqual(len(water_approval_files(ROOT)),4)
 def test_absent_contexts(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(water_approval_files(pathlib.Path(tmp)),[])
 def setup_root(self,tmp):
  root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/water-approvals',root/'data/water-approvals');shutil.copytree(ROOT/'data/water-projects',root/'data/water-projects');return root
 def test_corrupt_bytes(self):
  for n in ['cowie.json','cowie-review.json','akerley.json','akerley-review.json']:
   with self.subTest(name=n),tempfile.TemporaryDirectory() as tmp:
    root=self.setup_root(tmp);p=root/'data/water-approvals'/n;p.chmod(0o644);p.write_text(p.read_text()+' ')
    with self.assertRaises(ValueError):water_approval_files(root)
 def test_independent_optional_contexts(self):
  for name in ['cowie','akerley']:
   with tempfile.TemporaryDirectory() as tmp:
    root=self.setup_root(tmp);(root/f'data/water-approvals/{name}.json').unlink();self.assertEqual(len(water_approval_files(root)),2)
 def test_parent_changed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.setup_root(tmp);p=root/'data/water-projects/records.json';p.chmod(0o644);p.write_text(p.read_text()+' ')
   with self.assertRaises(ValueError):water_approval_files(root)
