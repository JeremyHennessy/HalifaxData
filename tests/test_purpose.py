import unittest,tempfile,pathlib,shutil,json,hashlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from purpose_publication import purpose_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class PurposeTests(unittest.TestCase):
 def test_exact_release(self):self.assertEqual(len(purpose_files(ROOT)),2)
 def test_changed_annotation_even_with_rehashed_receipt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/authorization-purpose',root/'data/authorization-purpose');shutil.copytree(ROOT/'data/authorizations',root/'data/authorizations')
   p=root/'data/authorization-purpose/annotation.json';b=json.loads(p.read_text());b['purpose']['explanation']='Unreviewed claim';p.write_text(json.dumps(b));r=root/'data/authorization-purpose/publication-review.json';v=json.loads(r.read_text());v['bundleSha256']=hashlib.sha256(p.read_bytes()).hexdigest();r.write_text(json.dumps(v))
   with self.assertRaises(ValueError):purpose_files(root)
 def test_changed_target_bytes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);shutil.copytree(ROOT/'data/authorization-purpose',root/'data/authorization-purpose');shutil.copytree(ROOT/'data/authorizations',root/'data/authorizations');p=root/'data/authorizations/records.json';p.write_text(p.read_text()+' ')
   with self.assertRaises(ValueError):purpose_files(root)
