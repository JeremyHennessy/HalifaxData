import unittest,tempfile,pathlib,shutil,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from water_publication import water_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class WaterTests(unittest.TestCase):
 def test_accept(self):self.assertEqual(len(water_files(ROOT)),6)
 def test_optional_absence(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(water_files(pathlib.Path(tmp)),[])
 def test_exact_bytes(self):
  for name in ('records.json','publication-review.json','m10687.json','m10687-review.json','m10687-v1.json','m10687-v1-review.json'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/water-projects',root/'data/water-projects');p=root/'data/water-projects'/name;p.chmod(0o644);p.write_bytes(p.read_bytes()+b' ')
    with self.assertRaises(ValueError):water_files(root)
 def test_no_orphan_context(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/water-projects',root/'data/water-projects');(root/'data/water-projects/records.json').unlink()
   with self.assertRaises(ValueError):water_files(root)
 def test_project_report_stands_alone(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/water-projects',root/'data/water-projects')
   for name in ['m10687.json','m10687-v1.json']:(root/'data/water-projects'/name).unlink()
   self.assertEqual(len(water_files(root)),2)
