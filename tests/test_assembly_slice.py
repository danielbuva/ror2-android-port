"""Safety/closure tests with authored fixtures, never game input."""
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from common import ROOT,WORK
from boundaries import probe_tool

class SliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.command=[str(x) for x in probe_tool()]
        parent=WORK/'tests';parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=parent);cls.folder=Path(cls.temp.name)
        (cls.folder/'Fixture.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        (cls.folder/'Fixture.cs').write_text('public struct Arithmetic { public static int Add(int a,int b) { return a+b; } } public class Other { } public struct HasOther { public Other value; }')
        subprocess.run([str(Path.home()/'.local/share/dotnet/dotnet'),'build',str(cls.folder/'Fixture.csproj'),'-o',str(cls.folder/'compiled'),'--nologo'],check=True,capture_output=True)
        cls.input=cls.folder/'compiled/Fixture.dll'
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def invoke(self,name,selected,output=None):
        return subprocess.run(self.command+['--slice',str(self.input),str(output or self.folder/name),selected],cwd=ROOT,capture_output=True)
    def test_retained_methods_and_source_identity(self):
        before=hashlib.sha256(self.input.read_bytes()).hexdigest()
        p=self.invoke('small.dll','Arithmetic');self.assertEqual(p.returncode,0,p.stderr)
        report=json.loads(p.stdout);self.assertTrue(report['retainedMethodBodiesUnchanged']);self.assertEqual(report['retainedMethods'],1)
        self.assertEqual(report['inputSha256'],before);self.assertEqual(hashlib.sha256(self.input.read_bytes()).hexdigest(),before)
        data=json.loads(subprocess.run(self.command+[str(self.folder/'small.dll')],check=True,capture_output=True).stdout)
        self.assertEqual({t['name'] for t in data['types']},{'<Module>','Arithmetic'})
    def test_rejects_dangling_type_dependency(self):
        p=self.invoke('dangling.dll','HasOther');self.assertNotEqual(p.returncode,0)
        self.assertIn(b'Slice is not closed',p.stderr);self.assertFalse((self.folder/'dangling.dll').exists())
    def test_refuses_output_outside_ignored_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'outside.dll';p=self.invoke('', 'Arithmetic',output)
            self.assertNotEqual(p.returncode,0);self.assertFalse(output.exists())
    def test_rejects_unknown_selected_type(self):
        p=self.invoke('missing.dll','Missing');self.assertNotEqual(p.returncode,0);self.assertFalse((self.folder/'missing.dll').exists())
