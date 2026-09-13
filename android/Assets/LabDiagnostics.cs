using System;
using System.IO;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Profiling;
public sealed class LabDiagnostics : MonoBehaviour
{
 [Serializable] public class Config { public bool enabled=true; public string subtree=""; public bool fields=false; }
 [Serializable] public class ObjectInfo { public string name; public string parent; public string[] components; public string[] fields; }
 [Serializable] public class Snapshot {
  public string checkpoint,utc,scene,graphicsApi,gpu,persistentDataPath,streamingAssetsPath,privateDataPath,camera;
  public string audio="not initialized: isolated lab",network="not initialized: isolated lab",gameState="no RoR2 gameplay loaded";
  public bool playerExists; public string[] controllers,renderers,assemblies; public ObjectInfo[] hierarchy;
  public float fps,frameMs; public long managedBytes,totalAllocatedBytes;public double cpuFrameMs,gpuFrameMs;
 }
 string root; float elapsed; int frames; float fps; bool ready; Config config=new Config();
 IEnumerator Start() {
  root=Application.persistentDataPath; Directory.CreateDirectory(root); Application.logMessageReceived+=OnLog;
  string proof=SimpleJSON.JSON.Parse("{\"assembly\":\"preserved\"}")["assembly"].Value;
  Debug.Log("LAB_MANAGED_ASSEMBLY_OK "+proof);
  yield return null;
  string bundlePath=Path.Combine(root,"payload/labgeometry");
  if(File.Exists(bundlePath)) {
   var request=AssetBundle.LoadFromFileAsync(bundlePath);yield return request;
   if(request.assetBundle!=null) {
    var asset=request.assetBundle.LoadAllAssets<Mesh>().FirstOrDefault();
    if(asset!=null) {
     var go=new GameObject("RoR2 recovered geometry");go.AddComponent<MeshFilter>().sharedMesh=asset;
     var renderer=go.AddComponent<MeshRenderer>();renderer.sharedMaterial=new Material(Shader.Find("Standard"));renderer.sharedMaterial.color=new Color(0.3f,0.8f,0.95f);
     var b=asset.bounds;go.transform.position=-b.center;float radius=Mathf.Max(b.extents.magnitude,0.1f);
     Camera.main.transform.position=new Vector3(0,radius*.3f,-radius*2.8f);Camera.main.transform.LookAt(Vector3.zero);
     Debug.Log("LAB_GEOMETRY_OK "+asset.name+" vertices="+asset.vertexCount);
    } else Debug.LogError("LAB_ASSET_FAILURE no Mesh in bundle");
   } else Debug.LogError("LAB_ASSET_FAILURE Android bundle failed");
  } else Debug.Log("LAB_G1_ONLY payload not synced");
  // Deliberately test original Windows shader bundle without pretending it is retargeted.
  var raw=Path.Combine(root,"payload/windows-shaders.bundle");
  if(File.Exists(raw)) {
   var br=AssetBundle.LoadFromFileAsync(raw);yield return br;
   if(br.assetBundle==null)Debug.Log("LAB_WINDOWS_BUNDLE_REJECTED");
   else {var shaders=br.assetBundle.LoadAllAssets<Shader>();Debug.Log("LAB_WINDOWS_SHADERS total="+shaders.Length+" supported="+shaders.Count(s=>s.isSupported));}
  }
  ready=true;Dump("LAB_READY");Debug.Log("LAB_READY");
 }
 void Update() {
  frames++;elapsed+=Time.unscaledDeltaTime;FrameTimingManager.CaptureFrameTimings();
  if(elapsed<2 || !ready)return;fps=frames/elapsed;frames=0;elapsed=0;
  var path=Path.Combine(root,"diagnostics.json");try{if(File.Exists(path))config=JsonUtility.FromJson<Config>(File.ReadAllText(path));}catch(Exception e){Debug.LogWarning(e.Message);}
  if(config.enabled)Dump("periodic");
 }
 void OnLog(string message,string stack,LogType type) {
  if(type==LogType.Exception||type==LogType.Error)try{File.AppendAllText(Path.Combine(root,"exceptions.jsonl"),JsonUtility.ToJson(new ErrorRow{message=message,stack=stack,type=type.ToString(),utc=DateTime.UtcNow.ToString("o")})+"\n");}catch{}
 }
 [Serializable] class ErrorRow {public string message,stack,type,utc;}
 void Dump(string checkpoint) {
  var objects=FindObjectsOfType<Transform>(true).Where(x=>string.IsNullOrEmpty(config.subtree)||x.name.Contains(config.subtree)||Ancestors(x).Contains(config.subtree)).Take(1000);
  var snapshot=new Snapshot{checkpoint=checkpoint,utc=DateTime.UtcNow.ToString("o"),scene=SceneManager.GetActiveScene().name,graphicsApi=SystemInfo.graphicsDeviceType.ToString(),gpu=SystemInfo.graphicsDeviceName,persistentDataPath=root,streamingAssetsPath=Application.streamingAssetsPath,camera=Camera.main?Camera.main.name:null,controllers=Input.GetJoystickNames(),fps=fps,frameMs=fps>0?1000/fps:0,managedBytes=Profiler.GetMonoUsedSizeLong(),totalAllocatedBytes=Profiler.GetTotalAllocatedMemoryLong(),playerExists=GameObject.Find("Player")!=null,assemblies=AppDomain.CurrentDomain.GetAssemblies().Select(a=>a.GetName().Name).ToArray(),renderers=FindObjectsOfType<Renderer>(true).SelectMany(r=>r.sharedMaterials.Where(m=>m!=null).Select(m=>r.name+":"+m.shader.name)).ToArray(),hierarchy=objects.Select(t=>new ObjectInfo{name=t.name,parent=t.parent?t.parent.name:null,components=t.GetComponents<Component>().Select(c=>c?c.GetType().FullName:"MISSING SCRIPT").ToArray(),fields=config.fields?t.GetComponents<Component>().Where(c=>c).SelectMany(c=>c.GetType().GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance).Select(f=>c.GetType().Name+"."+f.Name+"="+SafeField(c,f))).Take(100).ToArray():new string[0]}).ToArray()};
 #if UNITY_ANDROID && !UNITY_EDITOR
  using(var unity=new AndroidJavaClass("com.unity3d.player.UnityPlayer"))using(var activity=unity.GetStatic<AndroidJavaObject>("currentActivity"))using(var dir=activity.Call<AndroidJavaObject>("getFilesDir"))snapshot.privateDataPath=dir.Call<string>("getAbsolutePath");
 #endif
  var timings=new FrameTiming[1];if(FrameTimingManager.GetLatestTimings(1,timings)>0){snapshot.cpuFrameMs=timings[0].cpuFrameTime;snapshot.gpuFrameMs=timings[0].gpuFrameTime;}
  File.WriteAllText(Path.Combine(root,"snapshot.json"),JsonUtility.ToJson(snapshot,true));
  Debug.Log("LAB_SNAPSHOT "+JsonUtility.ToJson(snapshot));
 }
 static string SafeField(Component c,System.Reflection.FieldInfo f){try{return Convert.ToString(f.GetValue(c));}catch{return "unavailable";}}
 static string Ancestors(Transform t){return t.parent?t.parent.name+"/"+Ancestors(t.parent):"";}
 void OnGUI(){GUI.Label(new Rect(15,15,950,100),"PORTING LAB | "+SystemInfo.graphicsDeviceType+" | "+fps.ToString("F1")+" FPS\n"+(ready?"LAB READY":"LOADING"));}
}
