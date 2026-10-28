import unittest,tempfile,pathlib,shutil,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from health_publication import health_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class HealthPublicationTests(unittest.TestCase):
 def prepare(self,tmp):
  root=pathlib.Path(tmp)
  for folder in ['physician-categories','nshealth']:shutil.copytree(ROOT/'data'/folder,root/'data'/folder)
  return root
 def test_exact_six_public_files(self):self.assertEqual(len(health_files(ROOT)),6)
 def test_no_health_is_optional(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(health_files(pathlib.Path(tmp)),[])
 def test_each_file_requires_exact_reviewed_bytes(self):
  for name in health_files(ROOT):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    root=self.prepare(tmp);p=root/name;p.chmod(0o644);p.write_text(p.read_text()+' ')
    with self.assertRaises(ValueError):health_files(root)
 def test_annotation_absence_preserves_two_sources(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.prepare(tmp);(root/'data/nshealth/funding-bridge.json').unlink();self.assertEqual(len(health_files(root)),4)
 def test_phsyician_absence_preserves_institution_and_context(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.prepare(tmp);(root/'data/physician-categories/records.json').unlink();self.assertEqual(len(health_files(root)),4)
 def test_annotation_cannot_load_without_accepted_parent(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.prepare(tmp);(root/'data/nshealth/records.json').unlink()
   with self.assertRaises(ValueError):health_files(root)
