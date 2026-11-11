import unittest,tempfile,pathlib,shutil,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hrm_winter_publication import hrm_winter_files
class WinterGate(unittest.TestCase):
 def test_exact_artifact(self):self.assertEqual(len(hrm_winter_files(ROOT)),2)
 def test_optional_missing_and_corrupt(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);self.assertEqual(hrm_winter_files(root),[])
   dest=root/'data/hrm-winter';shutil.copytree(ROOT/'data/hrm-winter',dest)
   for name in ['records.json','publication-review.json']:
    original=(dest/name).read_bytes();(dest/name).write_text('{}')
    with self.assertRaises(ValueError):hrm_winter_files(root)
    (dest/name).write_bytes(original)
   (dest/'publication-review.json').unlink()
   with self.assertRaises(ValueError):hrm_winter_files(root)
