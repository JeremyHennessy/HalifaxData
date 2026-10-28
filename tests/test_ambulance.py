import pathlib,sys,tempfile,shutil,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from ambulance_publication import ambulance_files
ROOT=pathlib.Path(__file__).resolve().parents[1]
class AmbulanceTests(unittest.TestCase):
 def test_accept(self):self.assertEqual(len(ambulance_files(ROOT)),4)
 def test_missing(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(ambulance_files(pathlib.Path(d)),[])
 def test_mutation(self):
  for name in ['data/ambulance/compensation.json','data/ambulance/compensation-review.json','data/ambulance/service.json','data/ambulance/service-review.json','data/audits/records.json']:
   with tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d)
    for folder in ['ambulance','audits']:shutil.copytree(ROOT/'data'/folder,root/'data'/folder)
    (root/name).chmod(0o644);(root/name).write_text('{}')
    with self.assertRaises(ValueError):ambulance_files(root)
 def test_optional_service_absent(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   for folder in ['ambulance','audits']:shutil.copytree(ROOT/'data'/folder,root/'data'/folder)
   (root/'data/ambulance/service.json').unlink();self.assertEqual(len(ambulance_files(root)),2)
