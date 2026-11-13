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
using System.Linq;
using UnityEngine;
namespace UnityEngine {
 public static class Application {public static int targetFrameRate=300;}
 public static class QualitySettings {public static int vSyncCount=1;}
 public struct Resolution {public int refreshRate;}
 public static class Screen {public static Resolution currentResolution=new Resolution{refreshRate=120};}
 public static class Time {public static int captureFramerate=0;public static float fixedDeltaTime=.02f,timeScale=1;}
 public class Object { public bool destroyed; public static int workloadCalls; public static Object[] FindObjectsOfType(Type type){workloadCalls++;return new Object[type.FullName.Contains("Projectile")?3:7];} public static implicit operator bool(Object x){return !ReferenceEquals(x,null)&&!x.destroyed;} }
 public class Component : Object {public int value=7;}
 public class Transform : Component {public string name;public Transform parent;public T[] GetComponents<T>(){return new[]{(T)(object)new Component()};}}
 public class Shader {public string name="shader";}
 public class Material {public Shader shader=new Shader();}
 public class Renderer : Object {public string name="renderer";public Material[] sharedMaterials=new[]{new Material()};}
 public static class Debug { public static List<string> logs=new List<string>(); public static void Log(string value){logs.Add(value);} }
 public static class JsonUtility { public static string ToJson(object value,bool pretty=false){return new System.Web.Script.Serialization.JavaScriptSerializer().Serialize(value);} }
}
namespace UnityEngine.Rendering {public static class OnDemandRendering {public static int renderFrameInterval=2,effectiveRenderFrameRate=60;}}
namespace RoR2 {public class EffectComponent:UnityEngine.Component {}}
namespace RoR2.Projectile {public class ProjectileController:UnityEngine.Component {}}
class LabDiagnostics {
 public class Config {public bool sceneDetails,fields,workloadCounts;public string subtree="";}
 public class ObjectInfo {public string name,parent;public string[] components,fields;}
 public class Snapshot { public string checkpoint,payload;public bool sceneDetails,workloadCounts;public int activeProjectiles=-1,activeEffects=-1;public double workloadCountMs;public string workloadCountError;public string[] assemblies,renderers;public ObjectInfo[] hierarchy;
 public int targetFrameRate,vSyncCount,displayRefreshRate,renderFrameInterval,effectiveRenderFrameRate,captureFramerate;public float fixedDeltaTime,timeScale; }
 Config config=new Config();bool permitCensus;int censusCalls;
 T[] FindObjectsOfType<T>(bool inactive){
  if(!permitCensus||!inactive)throw new Exception("Unrequested/incomplete census");censusCalls++;
  if(typeof(T)==typeof(Transform))return (T[])(object)new[]{new Transform{name="parent"},new Transform{name="child",parent=new Transform{name="parent"}}};
  return (T[])(object)new[]{new Renderer()};
 }
 SCENE_DETAILS
 SAFE_FIELD
 ANCESTORS
 WORKLOAD_COUNTS
 COUNT_COMPONENTS
 PACING
 public static void VerifySceneDetails(){
  var owner=new LabDiagnostics();var scalar=new Snapshot();owner.PopulateSceneDetails("periodic",scalar);
  owner.PopulatePacing(scalar);
  if(scalar.targetFrameRate!=300||scalar.vSyncCount!=1||scalar.displayRefreshRate!=120||scalar.renderFrameInterval!=2||scalar.effectiveRenderFrameRate!=60||scalar.captureFramerate!=0||scalar.fixedDeltaTime!=.02f||scalar.timeScale!=1)throw new Exception("Live pacing unavailable");
  Application.targetFrameRate=60;QualitySettings.vSyncCount=0;UnityEngine.Rendering.OnDemandRendering.renderFrameInterval=1;Time.captureFramerate=30;
  owner.PopulatePacing(scalar);
  if(scalar.targetFrameRate!=60||scalar.vSyncCount!=0||scalar.renderFrameInterval!=1||scalar.captureFramerate!=30)throw new Exception("Cached startup pacing");
  if(scalar.sceneDetails||owner.censusCalls!=0||scalar.hierarchy.Length!=0||scalar.renderers.Length!=0||scalar.assemblies.Length!=0)throw new Exception("Default periodic scan");
  owner.PopulateWorkloadCounts(scalar);
  if(scalar.workloadCounts||UnityEngine.Object.workloadCalls!=0||scalar.activeProjectiles!=-1||scalar.activeEffects!=-1)throw new Exception("Unrequested workload census");
  owner.config.workloadCounts=true;var workload=new Snapshot();owner.PopulateWorkloadCounts(workload);
  if(!workload.workloadCounts||workload.activeProjectiles!=3||workload.activeEffects!=7||UnityEngine.Object.workloadCalls!=2||workload.workloadCountError!=null||workload.workloadCountMs<0)throw new Exception("Requested live component census");
  try{owner.CountActiveComponents("Missing.Component");throw new Exception("Missing type fabricated a count");}catch(InvalidOperationException){}
  owner.permitCensus=true;
  foreach(var mode in new[]{"startup","scene","fields","subtree"}){
   owner.config=new Config{sceneDetails=mode=="scene",fields=mode=="fields",subtree=mode=="subtree"?"parent":""};
   var detail=new Snapshot();int before=owner.censusCalls;owner.PopulateSceneDetails(mode=="startup"?"LAB_READY":"periodic",detail);
   if(!detail.sceneDetails||owner.censusCalls-before!=2||detail.hierarchy.Length!=2||detail.renderers.Single()!="renderer:shader"||detail.assemblies.Length==0)throw new Exception("Requested census lost");
   if((detail.hierarchy[0].fields.Length>0)!=(mode=="fields"))throw new Exception("Field inspection changed");
  }
 }
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
namespace HG {
 public abstract class CollectionPool<T,C> where C:ICollection<T>,new() {
  private static readonly Stack<C> pooledCollections=new Stack<C>();
  public static Stack<C> Returned {get{return pooledCollections;}}
 }
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
 RETURNED_POOLS
 public static void VerifyReturnedPools(){
  var owner=new ResourceOwner();var target=new HurtBox();
  var rentedHit=new BulletAttack.BulletHit {hitHurtBox=target,other=target};
  var rentedList=new List<Renderer> {new Renderer()};
  var returnedHit=new BulletAttack.BulletHit {hitHurtBox=target,other=target};
  var returnedList=new List<Renderer> {rentedList[0]};
  var hits=BulletAttack.Returned;var lists=HG.CollectionPool<Renderer,List<Renderer>>.Returned;
  hits.Push(returnedHit);lists.Push(returnedList);
  for(int flag=0;flag<4;flag++){
   owner.r.world.cleaned=flag!=0;Run.instance=flag==1?new UnityEngine.Object():null;NetworkServer.active=flag==2;NetworkClient.active=flag==3;
   bool refused=false;try{owner.ReclaimReturnedSessionPools();}catch(InvalidOperationException){refused=true;}
   if(!refused||hits.Count!=1||lists.Count!=1)throw new Exception("Live-session returned storage mutated");
  }
  owner.r.world.cleaned=true;Run.instance=null;NetworkServer.active=NetworkClient.active=false;
  for(int session=0;session<3;session++){
   // Fresh deserialized/allocated objects may be returned without an earlier rent.
   for(int i=0;i<100;i++){hits.Push(new BulletAttack.BulletHit());lists.Push(new List<Renderer>());}
   var counts=owner.ReclaimReturnedSessionPools();
   if(hits.Count!=0||lists.Count!=0||!counts[0].EndsWith(session==0?":101/0":":100/0")||!counts[1].EndsWith(session==0?":101/0":":100/0"))throw new Exception("Returned storage retained or counts lost");
   if(((Array)hits.GetType().GetField("_array",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(hits)).Length!=0||((Array)lists.GetType().GetField("_array",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(lists)).Length!=0)throw new Exception("Empty pool backing capacity retained");
  }
  if(!ReferenceEquals(rentedHit.hitHurtBox,target)||!ReferenceEquals(rentedHit.other,target)||rentedList.Count!=1||!ReferenceEquals(returnedHit.hitHurtBox,target)||returnedList.Count!=1||!ReferenceEquals(returnedList[0],rentedList[0]))throw new Exception("Pool reclamation mutated an item or a checked-out list");
  var empty=owner.ReclaimReturnedSessionPools();
  if(!empty[0].EndsWith(":0/0")||!empty[1].EndsWith(":0/0"))throw new Exception("Reclamation not idempotent");
 }
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
class Program {static void Main(string[] args){if(args[0]=="scene-details")LabDiagnostics.VerifySceneDetails();else if(args[0]=="publication")LabDiagnostics.Verify(args[1]);else if(args[0]=="returned-pools")ResourceOwner.VerifyReturnedPools();else if(args[0]=="overlap")ResourceOwner.VerifyOverlap();else if(args[0]=="spawn")ResourceOwner.VerifySpawn();else ResourceOwner.Verify();Console.WriteLine(args[0]+": PASS");}}
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
        diagnostic = (ROOT / "android/Assets/LabDiagnostics.cs").read_text()
        code = code.replace("SCENE_DETAILS", extract_method(diagnostic, " void PopulateSceneDetails("))
        code = code.replace("SAFE_FIELD", extract_method(diagnostic, " static string SafeField("))
        code = code.replace("ANCESTORS", extract_method(diagnostic, " static string Ancestors("))
        code = code.replace("WORKLOAD_COUNTS", extract_method(diagnostic, " void PopulateWorkloadCounts("))
        code = code.replace("COUNT_COMPONENTS", extract_method(diagnostic, " int CountActiveComponents("))
        code = code.replace("PACING", extract_method(diagnostic, " void PopulatePacing("))
        code = code.replace(
            "CLEANUP",
            extract_method((ROOT / "tools/unity/runtime/session/SessionResourceBoundary.cs").read_text(), "    int ReleaseDestroyedPooledHitTargets()"),
        )
        resource = (ROOT / "tools/unity/runtime/session/SessionResourceBoundary.cs").read_text()
        code = code.replace("OVERLAP_METHOD", extract_method(resource, "    int PruneDestroyedOverlapTargets()"))
        code = code.replace("SPAWN_METHOD", extract_method(resource, "    int PruneDestroyedSpawnCardCallbacks()"))
        code = code.replace("RETURNED_POOLS", extract_method(resource, "    string[] ReclaimReturnedSessionPools()"))
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

    def test_periodic_scene_census_requires_explicit_inspection_and_startup_keeps_details(self):
        self.case("scene-details")

    def test_teardown_releases_only_destroyed_targets_of_returned_hits(self):
        self.case("cleanup")

    def test_idle_teardown_reclaims_returned_storage_without_mutating_rentals(self):
        self.case("returned-pools")

    def test_teardown_releases_only_destroyed_spawn_card_callbacks(self):
        self.case("spawn")

    def test_teardown_releases_only_destroyed_overlap_discovery_targets(self):
        self.case("overlap")
