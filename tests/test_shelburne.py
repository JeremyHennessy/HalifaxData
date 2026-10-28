import pathlib,sys,tempfile,shutil,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from shelburne_publication import shelburne_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ShelburneTests(unittest.TestCase):
 def test_accept(self):self.assertEqual(len(shelburne_files(ROOT)),4)
 def test_missing(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(shelburne_files(pathlib.Path(d)),[])
 def test_tampered(self):
  for name in ['paid','decision','paid-review','decision-review']:
   with tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d);shutil.copytree(ROOT/'data/shelburne',root/'data/shelburne');p=root/f'data/shelburne/{name}.json';p.chmod(0o644);p.write_text('{}')
    with self.assertRaises(ValueError):shelburne_files(root)
 def test_each_projection_stands_alone(self):
  for name in ['paid','decision']:
   with tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d);shutil.copytree(ROOT/'data/shelburne',root/'data/shelburne');(root/f'data/shelburne/{name}.json').unlink();self.assertEqual(len(shelburne_files(root)),2)
