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
struct ResourceAvailability {
 public bool available;
 private event Action onAvailable;
 public void Add(Action callback){onAvailable+=callback;}
 public Delegate Callbacks {get{return onAvailable;}}
}
class CharacterSpawnCard : UnityEngine.Object {
 private static ResourceAvailability loadoutAvailability;
 public void Callback(){}
 public static ResourceAvailability Availability {get{return loadoutAvailability;}set{loadoutAvailability=value;}}
}
static class CompletedSessionRootWalk { REMOVE_TARGETS }
class HurtBox : UnityEngine.Object {}
class OverlapAttack {
 private static readonly List<HurtBox> discoveredHurtboxes=new List<HurtBox>();
 public static List<HurtBox> Targets {get{return discoveredHurtboxes;}}
}
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
 OVERLAP_METHOD
 SPAWN_METHOD
 public static void VerifyOverlap(){
  var owner=new ResourceOwner();var dead=new HurtBox {destroyed=true};var live=new HurtBox();var second=new HurtBox();
  var list=OverlapAttack.Targets;list.Add(dead);list.Add(live);list.Add(null);list.Add(dead);list.Add(second);int capacity=list.Capacity;
  for(int flag=0;flag<4;flag++){
   owner.r.world.cleaned=flag!=0;Run.instance=flag==1?new UnityEngine.Object():null;NetworkServer.active=flag==2;NetworkClient.active=flag==3;
   bool refused=false;try{owner.PruneDestroyedOverlapTargets();}catch(InvalidOperationException){refused=true;}
   if(!refused||list.Count!=5)throw new Exception("Live-world overlap targets mutated");
  }
  owner.r.world.cleaned=true;Run.instance=null;NetworkServer.active=NetworkClient.active=false;
  if(owner.PruneDestroyedOverlapTargets()!=3||list.Count!=2||!ReferenceEquals(list[0],live)||!ReferenceEquals(list[1],second)||list.Capacity!=capacity)throw new Exception("Destroyed overlap retained or live order/capacity changed");
  if(owner.PruneDestroyedOverlapTargets()!=0)throw new Exception("Overlap cleanup not idempotent");
 }
 public static void VerifySpawn(){
  var owner=new ResourceOwner();var dead=new CharacterSpawnCard {destroyed=true};var live=new CharacterSpawnCard();
  Action foreign=()=>{};var state=new ResourceAvailability {available=true};state.Add(dead.Callback);state.Add(live.Callback);state.Add(foreign);state.Add(dead.Callback);CharacterSpawnCard.Availability=state;
  for(int flag=0;flag<4;flag++){
   owner.r.world.cleaned=flag!=0;Run.instance=flag==1?new UnityEngine.Object():null;NetworkServer.active=flag==2;NetworkClient.active=flag==3;
   bool refused=false;try{owner.PruneDestroyedSpawnCardCallbacks();}catch(InvalidOperationException){refused=true;}
   if(!refused||CharacterSpawnCard.Availability.Callbacks.GetInvocationList().Length!=4)throw new Exception("Live-world callbacks mutated");
  }
  owner.r.world.cleaned=true;Run.instance=null;NetworkServer.active=NetworkClient.active=false;
  if(owner.PruneDestroyedSpawnCardCallbacks()!=2)throw new Exception("Destroyed callbacks retained");
  var after=CharacterSpawnCard.Availability;var callbacks=after.Callbacks.GetInvocationList();
  if(!after.available||callbacks.Length!=2||!ReferenceEquals(callbacks[0].Target,live)||!callbacks[1].Equals(foreign))throw new Exception("Availability/live callback/order changed");
  if(owner.PruneDestroyedSpawnCardCallbacks()!=0)throw new Exception("Cleanup not idempotent");
 }
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
class Program {static void Main(string[] args){if(args[0]=="publication")LabDiagnostics.Verify(args[1]);else if(args[0]=="overlap")ResourceOwner.VerifyOverlap();else if(args[0]=="spawn")ResourceOwner.VerifySpawn();else ResourceOwner.Verify();Console.WriteLine(args[0]+": PASS");}}
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
        resource = (ROOT / "tools/unity/runtime/session/SessionResourceBoundary.cs").read_text()
        code = code.replace("OVERLAP_METHOD", extract_method(resource, "    int PruneDestroyedOverlapTargets()"))
        code = code.replace("SPAWN_METHOD", extract_method(resource, "    int PruneDestroyedSpawnCardCallbacks()"))
        code = code.replace("REMOVE_TARGETS", extract_method(resource, "    public static Delegate RemoveTargets("))
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

    def test_teardown_releases_only_destroyed_spawn_card_callbacks(self):
        self.case("spawn")

    def test_teardown_releases_only_destroyed_overlap_discovery_targets(self):
        self.case("overlap")
