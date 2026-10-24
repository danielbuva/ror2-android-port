"""Execute production file/log publication and returned-hit cleanup contracts."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_portable_diagnostic_input import extract_method

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")

HOST = r"""
using System;
using System.IO;
using System.Reflection;
using System.Collections.Generic;
using UnityEngine;
namespace UnityEngine {
 public class Object { public bool destroyed; public static implicit operator bool(Object x){return !ReferenceEquals(x,null)&&!x.destroyed;} }
 public static class Debug { public static List<string> logs=new List<string>(); public static void Log(string value){logs.Add(value);} }
 public static class JsonUtility { public static string ToJson(object value,bool pretty=false){return new System.Web.Script.Serialization.JavaScriptSerializer().Serialize(value);} }
}
class LabDiagnostics {
 public class Snapshot { public string checkpoint,payload; }
 string root;
 PUBLICATION
 public static void Verify(string root){
  var owner=new LabDiagnostics {root=root};
  owner.PublishSnapshot("LAB_READY",new Snapshot {checkpoint="LAB_READY",payload="startup"});
  for(int i=0;i<400;i++)owner.PublishSnapshot("periodic",new Snapshot {checkpoint="periodic",payload=new string('x',10000)+i});
  var file=File.ReadAllText(Path.Combine(root,"snapshot.json"));
  if(!file.Contains("399")||file.Contains("startup")||Debug.logs.Count!=1||!Debug.logs[0].StartsWith("LAB_SNAPSHOT "))throw new Exception("Periodic JSON retained in console or fresh file lost");
  if(Directory.GetFiles(root).Length!=1)throw new Exception("Unbounded snapshot files");
 }
}
class HurtBox : UnityEngine.Object {}
class PoolBase<T> { private Stack<T> items=new Stack<T>(); public Stack<T> Returned {get{return items;}} }
class HitPool : PoolBase<BulletAttack.BulletHit> {}
class BulletAttack {
 public class BulletHit { public HurtBox hitHurtBox; public object other; }
 private static HitPool bulletHitPool=new HitPool();
 public static Stack<BulletHit> Returned {get{return bulletHitPool.Returned;}}
}
static class Run {public static UnityEngine.Object instance;}
static class NetworkServer {public static bool active;}
static class NetworkClient {public static bool active;}
class ResourceOwner {
 public class World {public bool cleaned=true;}
 public class Report {public World world=new World();}
 public Report r=new Report();
 void Check(bool pass,string message){if(!pass)throw new InvalidOperationException(message);}
 CLEANUP
 public static void Verify(){
  var owner=new ResourceOwner();var dead=new HurtBox {destroyed=true};var live=new HurtBox();var other=new object();
  var returned=new BulletAttack.BulletHit {hitHurtBox=dead,other=other};var active=new BulletAttack.BulletHit {hitHurtBox=live};var empty=new BulletAttack.BulletHit();var rented=new BulletAttack.BulletHit {hitHurtBox=dead};
  var stack=BulletAttack.Returned;stack.Push(returned);stack.Push(active);stack.Push(empty);var before=stack.ToArray();
  for(int flag=0;flag<4;flag++){
   owner.r.world.cleaned=flag!=0;Run.instance=flag==1?new UnityEngine.Object():null;NetworkServer.active=flag==2;NetworkClient.active=flag==3;
   bool refused=false;try{owner.ReleaseDestroyedPooledHitTargets();}catch(InvalidOperationException){refused=true;}
   if(!refused||!ReferenceEquals(returned.hitHurtBox,dead))throw new Exception("Live-world cleanup mutated a target");
  }
  owner.r.world.cleaned=true;Run.instance=null;NetworkServer.active=NetworkClient.active=false;
  if(owner.ReleaseDestroyedPooledHitTargets()!=1||!ReferenceEquals(returned.hitHurtBox,null)||!ReferenceEquals(active.hitHurtBox,live)||!ReferenceEquals(rented.hitHurtBox,dead)||!ReferenceEquals(returned.other,other))throw new Exception("Cleanup exceeded destroyed returned target");
  var after=stack.ToArray();if(before.Length!=after.Length)throw new Exception("Pool resized");for(int i=0;i<before.Length;i++)if(!ReferenceEquals(before[i],after[i]))throw new Exception("Pool order changed");
  if(owner.ReleaseDestroyedPooledHitTargets()!=0)throw new Exception("Cleanup not idempotent");
 }
}
class Program {static void Main(string[] args){if(args[0]=="publication")LabDiagnostics.Verify(args[1]);else ResourceOwner.Verify();Console.WriteLine(args[0]+": PASS");}}
"""


class DiagnosticRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mono = EDITOR / "bin/mono"
        compiler = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not cls.mono.is_file() or not compiler.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="diagnostic-retention-")
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        code = HOST.replace("PUBLICATION", extract_method((ROOT / "android/Assets/LabDiagnostics.cs").read_text(), " void PublishSnapshot("))
        code = code.replace(
            "CLEANUP",
            extract_method((ROOT / "tools/unity/runtime/session/SessionResourceBoundary.cs").read_text(), "    int ReleaseDestroyedPooledHitTargets()"),
        )
        source = directory / "Production.cs"
        source.write_text(code)
        cls.exe = directory / "retention.exe"
        result = subprocess.run(
            [
                str(cls.mono),
                str(compiler),
                "-nologo",
                "-langversion:9",
                "-r:" + str(EDITOR / "lib/mono/net_4_x-macos/System.Web.Extensions.dll"),
                "-out:" + str(cls.exe),
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def case(self, name):
        with tempfile.TemporaryDirectory(prefix="diagnostic-files-") as directory:
            result = subprocess.run(
                [str(self.mono), str(self.exe), name, directory],
                env=dict(os.environ, MONO_PATH=str(EDITOR / "lib/mono/net_4_x-macos")),
                capture_output=True,
                text=True,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ": PASS", result.stdout)

    def test_periodic_large_snapshots_replace_one_file_without_console_retention(self):
        self.case("publication")

    def test_teardown_releases_only_destroyed_targets_of_returned_hits(self):
        self.case("cleanup")
