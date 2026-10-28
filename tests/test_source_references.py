import unittest,tempfile,pathlib,shutil,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from reference_publication import reference_files,CONTEXT
ROOT=pathlib.Path(__file__).resolve().parents[1]
class SourceContextTests(unittest.TestCase):
 def test_exact_reviewed_allowlist(self):self.assertEqual(len(reference_files(ROOT)),4)
 def test_optional_absence(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(reference_files(pathlib.Path(tmp)),[])
 def test_byte_changes_fail_closed(self):
  for folder in CONTEXT:
   for filename in ('records.json','publication-review.json'):
    with self.subTest(folder=folder,filename=filename),tempfile.TemporaryDirectory() as tmp:
     root=pathlib.Path(tmp);shutil.copytree(ROOT/'data'/folder,root/'data'/folder)
     p=root/'data'/folder/filename;p.write_bytes(p.read_bytes()+b' ')
     with self.assertRaises(ValueError):reference_files(root)
 def test_target_bytes_changed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/procurement-methodology',root/'data/procurement-methodology');p=root/'data/tenders';p.mkdir();(p/'tender-index.json').write_text('{}')
   with self.assertRaises(ValueError):reference_files(root)
