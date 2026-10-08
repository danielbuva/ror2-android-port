using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Profiling;

// Measurements and reclamation only at an already completed owned session.
// No gameplay pools, live content, process caches or unrelated files are cleared.
public sealed partial class MovementBatchProbe {
 [Serializable] public class SessionResourceSample {
  public string phase;public float seconds;public long allocated,reserved,managed;
  public long managedTotal;public int collections;public string gcMode;public bool incremental;public float collectionSeconds;
  public int trackedCompletedSessions,liveCompletedProbes,liveCompletedReports;public int materials,textures,shaders,gameObjects,bundles;public string[] bundleNames;
  public string[] ownedCallbackRoots,callbackRootReadFailures,callbackOwnerScope;
 }
 static readonly System.Collections.Generic.List<WeakReference[]> completedSessionReferences=new System.Collections.Generic.List<WeakReference[]>();
 void TrackCompletedSessionReferences(){completedSessionReferences.RemoveAll(x=>!x[0].IsAlive&&!x[1].IsAlive);if(completedSessionReferences.Count<128)completedSessionReferences.Add(new[]{new WeakReference(this),new WeakReference(r)});}
 void CollectPriorSessionGarbage(){
  if(completedSessionReferences.Count==0)return;Check(!Run.instance&&!NetworkServer.active&&!NetworkClient.active,"Refuse prior-session collection in live gameplay");
  if(UnityEngine.Scripting.GarbageCollector.GCMode!=UnityEngine.Scripting.GarbageCollector.Mode.Disabled)GC.Collect();
 }
 void ObserveSessionResources(string phase){
  if(r.sessionResources==null)r.sessionResources=new System.Collections.Generic.List<SessionResourceSample>();
  var roots=new System.Collections.Generic.List<string>();var failures=new System.Collections.Generic.List<string>();
  // Read only already-used gameplay callback owners; never initialize unrelated
  // subsystem types, invoke callbacks or remove original handlers diagnostically.
  var callbackOwners=new[]{typeof(RoR2Application),typeof(GlobalEventManager),typeof(Run),typeof(CharacterBody),typeof(CharacterMaster),typeof(SceneCatalog),typeof(Stage),typeof(MasterSummon),typeof(BossGroup),typeof(SceneExitController),typeof(TeleporterInteraction),typeof(Inventory),typeof(DotController)};
  if(completedSessionReferences.Count>0)foreach(var type in callbackOwners)foreach(var field in type.GetFields(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).Where(x=>typeof(Delegate).IsAssignableFrom(x.FieldType))){
   Delegate callback;try{callback=field.GetValue(null) as Delegate;}catch(Exception e){failures.Add(type.FullName+"."+field.Name+":"+e.GetType().Name);continue;}if(callback==null)continue;
   foreach(var entry in callback.GetInvocationList())for(int i=0;i<completedSessionReferences.Count;i++){
    var probe=completedSessionReferences[i][0].Target;var report=completedSessionReferences[i][1].Target;if(probe==null&&report==null)continue;
    var path=FindCompletedCallbackReference(entry.Target,probe,report,0);if(path!=null)roots.Add(type.FullName+"."+field.Name+" -> "+entry.Method.Name+" -> completed["+i+"]"+path);
   }
  }
  // Addressables is already live in this composition. Inspect only delegate fields;
  // do not walk asset graphs, initialize other services or change cached operations.
  if(completedSessionReferences.Count>0){var manager=UnityEngine.AddressableAssets.Addressables.ResourceManager;foreach(var field in manager.GetType().GetFields(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance).Where(x=>typeof(Delegate).IsAssignableFrom(x.FieldType))){
   Delegate callback;try{callback=field.GetValue(manager) as Delegate;}catch(Exception e){failures.Add(manager.GetType().FullName+"."+field.Name+":"+e.GetType().Name);continue;}if(callback==null)continue;
   foreach(var entry in callback.GetInvocationList())for(int i=0;i<completedSessionReferences.Count;i++){var path=FindCompletedCallbackReference(entry.Target,completedSessionReferences[i][0].Target,completedSessionReferences[i][1].Target,0);if(path!=null)roots.Add(manager.GetType().FullName+"."+field.Name+" -> "+entry.Method.Name+" -> completed["+i+"]"+path);}
  }}
  r.sessionResources.Add(new SessionResourceSample{phase=phase,seconds=Time.realtimeSinceStartup,ownedCallbackRoots=roots.ToArray(),callbackRootReadFailures=failures.ToArray(),callbackOwnerScope=callbackOwners.Select(x=>x.FullName).Concat(new[]{"UnityEngine.ResourceManagement.ResourceManager (instance delegates)"}).ToArray(),trackedCompletedSessions=completedSessionReferences.Count,liveCompletedProbes=completedSessionReferences.Count(x=>x[0].IsAlive),liveCompletedReports=completedSessionReferences.Count(x=>x[1].IsAlive),
   allocated=Profiler.GetTotalAllocatedMemoryLong(),reserved=Profiler.GetTotalReservedMemoryLong(),managed=Profiler.GetMonoUsedSizeLong(),managedTotal=GC.GetTotalMemory(false),collections=GC.CollectionCount(0),gcMode=UnityEngine.Scripting.GarbageCollector.GCMode.ToString(),incremental=UnityEngine.Scripting.GarbageCollector.isIncremental,
   materials=Resources.FindObjectsOfTypeAll<Material>().Length,textures=Resources.FindObjectsOfTypeAll<Texture>().Length,
   shaders=Resources.FindObjectsOfTypeAll<Shader>().Length,gameObjects=Resources.FindObjectsOfTypeAll<GameObject>().Length,
   bundles=AssetBundle.GetAllLoadedAssetBundles().Count(),bundleNames=AssetBundle.GetAllLoadedAssetBundles().Select(x=>x.name).OrderBy(x=>x).ToArray()});
 }
 static string FindCompletedCallbackReference(object value,object probe,object report,int depth){
  if(value==null)return null;if(ReferenceEquals(value,probe))return ":probe";if(ReferenceEquals(value,report))return ":report";
  if(depth>=2||!value.GetType().IsDefined(typeof(System.Runtime.CompilerServices.CompilerGeneratedAttribute),false))return null;
  foreach(var field in value.GetType().GetFields(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)){
   var path=FindCompletedCallbackReference(field.GetValue(value),probe,report,depth+1);if(path!=null)return "."+field.Name+path;
  }return null;
 }
 IEnumerator ReclaimCompletedSessionResources(){
  Check(r.world.cleaned&&!Run.instance&&!NetworkServer.active&&!NetworkClient.active,"Refuse resource reclamation in a live session");
  // Let deferred destruction finish before Unity's ordinary unused-asset sweep.
  yield return null;ObserveSessionResources("completed-before-reclaim");
  yield return Resources.UnloadUnusedAssets();
  ObserveSessionResources("completed-after-reclaim");
  // Attribute remaining managed growth after teardown, without changing GC mode.
  if(UnityEngine.Scripting.GarbageCollector.GCMode!=UnityEngine.Scripting.GarbageCollector.Mode.Disabled){var began=Time.realtimeSinceStartup;GC.Collect();var seconds=Time.realtimeSinceStartup-began;yield return null;ObserveSessionResources("completed-after-managed-collection");r.sessionResources.Last().collectionSeconds=seconds;}
  Save();
 }
}
