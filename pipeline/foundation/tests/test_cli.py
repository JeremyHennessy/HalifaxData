import unittest, tempfile, pathlib, subprocess, sys, shutil, json
ROOT=pathlib.Path(__file__).resolve().parents[1]
class CliTests(unittest.TestCase):
 def invoke(self,*args,cwd=None):return subprocess.run([sys.executable,'-m','watchdog_checks',*map(str,args)],cwd=cwd or ROOT,capture_output=True,text=True)
 def test_explicit_paths_and_determinism(self):
  with tempfile.TemporaryDirectory() as d:
   a,b=pathlib.Path(d)/'a.json',pathlib.Path(d)/'b.json'
   for p in (a,b):self.assertEqual(self.invoke('--input',ROOT/'fixtures','--output',p).returncode,0)
   self.assertEqual(a.read_bytes(),b.read_bytes());self.assertFalse(json.loads(a.read_bytes())['publicationAllowed'])
 def test_relocated_package(self):
  with tempfile.TemporaryDirectory() as d:
   moved=pathlib.Path(d)/'portable';shutil.copytree(ROOT,moved,ignore=shutil.ignore_patterns('__pycache__'));out=pathlib.Path(d)/'out.json'
   r=self.invoke('--input',moved/'fixtures','--output',out,cwd=moved)
   self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(out.read_text())['counts']['explained'],3)
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'x.json';p.write_text('keep')
   self.assertNotEqual(self.invoke('--input',ROOT/'fixtures','--output',p).returncode,0);self.assertEqual(p.read_text(),'keep')
 def test_no_public_write(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'dist'/'x.json';p.parent.mkdir()
   self.assertNotEqual(self.invoke('--input',ROOT/'fixtures','--output',p).returncode,0);self.assertFalse(p.exists())
 def test_tampered_snapshot_no_report(self):
  with tempfile.TemporaryDirectory() as d:
   f=pathlib.Path(d)/'inputs';shutil.copytree(ROOT/'fixtures',f);(f/'shelburne/decision.json').write_text('{}');p=pathlib.Path(d)/'out.json'
   self.assertNotEqual(self.invoke('--input',f,'--output',p).returncode,0);self.assertFalse(p.exists())
 def test_no_implicit_paths(self):self.assertNotEqual(self.invoke().returncode,0)
 def test_package_contains_no_private_paths(self):
  for p in ROOT.rglob('*'):
   if p.is_file() and p.suffix in ('.py','.json','.md'):
    self.assertNotIn('/'+'workspace'+'/',p.read_text());self.assertNotIn('halifaxdata'+'-fresh-private',p.read_text())
