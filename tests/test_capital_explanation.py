import unittest,tempfile,pathlib,shutil,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from capital_explanation_publication import capital_explanation_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class CapitalExplanationTests(unittest.TestCase):
 def test_accepted(self):self.assertEqual(len(capital_explanation_files(ROOT)),2)
 def test_optional_missing(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(capital_explanation_files(pathlib.Path(d)),[])
 def test_changed_bytes_or_target_rejected(self):
  for target in ['data/capital-explanation/annotation.json','data/municipal-capital/records.json']:
   with tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d)
    for name in ['capital-explanation','municipal-capital']:shutil.copytree(ROOT/'data'/name,root/'data'/name)
    (root/target).chmod(0o644)
    (root/target).write_text('{}')
    with self.assertRaises(ValueError):capital_explanation_files(root)
