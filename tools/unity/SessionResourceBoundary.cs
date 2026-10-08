using System;
using System.Collections;
using System.Linq;
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
  public int materials,textures,shaders,gameObjects,bundles;public string[] bundleNames;
 }
 void ObserveSessionResources(string phase){
  if(r.sessionResources==null)r.sessionResources=new System.Collections.Generic.List<SessionResourceSample>();
  r.sessionResources.Add(new SessionResourceSample{phase=phase,seconds=Time.realtimeSinceStartup,
   allocated=Profiler.GetTotalAllocatedMemoryLong(),reserved=Profiler.GetTotalReservedMemoryLong(),managed=Profiler.GetMonoUsedSizeLong(),managedTotal=GC.GetTotalMemory(false),collections=GC.CollectionCount(0),gcMode=UnityEngine.Scripting.GarbageCollector.GCMode.ToString(),incremental=UnityEngine.Scripting.GarbageCollector.isIncremental,
   materials=Resources.FindObjectsOfTypeAll<Material>().Length,textures=Resources.FindObjectsOfTypeAll<Texture>().Length,
   shaders=Resources.FindObjectsOfTypeAll<Shader>().Length,gameObjects=Resources.FindObjectsOfTypeAll<GameObject>().Length,
   bundles=AssetBundle.GetAllLoadedAssetBundles().Count(),bundleNames=AssetBundle.GetAllLoadedAssetBundles().Select(x=>x.name).OrderBy(x=>x).ToArray()});
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
