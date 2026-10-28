import unittest,tempfile,pathlib,shutil,json,hashlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from capital_publication import capital_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class CapitalTests(unittest.TestCase):
 def test_accepted_snapshot(self):self.assertEqual(len(capital_files(ROOT)),2)
 def test_rehashed_semantic_changes_are_not_accepted(self):
  for field,value in [('currency','CAD'),('asOf','2026-03-31'),('value','999')]:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/municipal-capital',root/'data/municipal-capital');p=root/'data/municipal-capital/records.json';p.chmod(0o600);b=json.loads(p.read_text());b['records'][0]['values'][0][field]=value;p.write_text(json.dumps(b));r=root/'data/municipal-capital/publication-review.json';v=json.loads(r.read_text());v['bundleSha256']=hashlib.sha256(p.read_bytes()).hexdigest();r.write_text(json.dumps(v))
    with self.assertRaises(ValueError):capital_files(root)
