"""Offline infrastructure must not enter the public application build."""
import hashlib,json,pathlib,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'pipeline/foundation'
MANIFEST_SHA='38732adf25065844749e14d05f31b61863be263e1e56d68ba2813f0e5651e1c4'
class PipelineFoundationBoundary(unittest.TestCase):
 def test_exact_reviewed_package(self):
  body=(PACKAGE/'PACKAGE-MANIFEST.json').read_bytes();self.assertEqual(hashlib.sha256(body).hexdigest(),MANIFEST_SHA)
  for name,sha in json.loads(body)['files'].items():self.assertEqual(hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest(),sha,name)
 def test_explicit_test_discovery_once(self):
  command=json.loads((ROOT/'package.json').read_bytes())['scripts']['test'];self.assertEqual(command.count('pipeline/foundation/run_tests.py'),1);self.assertIn('node --test tests/*.test.mjs',command);self.assertIn('unittest discover -s pipeline',command)
 def test_transport_remains_disabled(self):
  text=(PACKAGE/'physician_refresh/collector.py').read_text();self.assertIn('MANUAL_TRANSPORT_ENABLED=False',text);self.assertFalse((PACKAGE/'physician_refresh/refresh-state.private').exists())
 def test_public_build_excludes_foundation(self):
  subprocess.run([sys.executable,'scripts/build.py'],cwd=ROOT,check=True,capture_output=True)
  manifest=json.loads((ROOT/'dist/release.json').read_bytes())
  names=set(manifest['files'])|{p.relative_to(ROOT/'dist').as_posix() for p in (ROOT/'dist').rglob('*') if p.is_file()}
  for name in names:
   self.assertFalse(name.startswith(('pipeline/','fixtures/','physician_refresh/','watchdog_checks/','source_policies/')),name);self.assertNotIn('.private',name);self.assertNotIn('PACKAGE-MANIFEST',name)
 def test_accidental_private_dist_file_is_rejected(self):
  out=ROOT/'dist';out.mkdir(exist_ok=True);sentinel=out/'foundation-leak.private.json'
  with sentinel.open('x') as stream:stream.write('{}')
  try:
   result=subprocess.run([sys.executable,'scripts/build.py'],cwd=ROOT,capture_output=True,text=True);self.assertNotEqual(result.returncode,0);self.assertIn('Unexpected file in public output',result.stderr)
  finally:sentinel.unlink()
if __name__=='__main__':unittest.main()
