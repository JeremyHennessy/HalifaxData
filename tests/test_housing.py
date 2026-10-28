import pathlib,sys,tempfile,shutil,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from housing_publication import housing_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class HousingTests(unittest.TestCase):
 def test_accept(self):self.assertEqual(len(housing_files(ROOT)),2)
 def test_missing(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(housing_files(pathlib.Path(d)),[])
 def test_mutation(self):
  for name in ['data/housing-audit/progression.json','data/housing-audit/publication-review.json','data/audits/records.json']:
   with tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d)
    for folder in ['housing-audit','audits']:shutil.copytree(ROOT/'data'/folder,root/'data'/folder)
    (root/name).chmod(0o644);(root/name).write_text('{}')
    with self.assertRaises(ValueError):housing_files(root)
