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
    [Serializable] public class Config { public bool enabled=true; public string subtree=""; public bool fields=false; public bool properties=false; }
    [Serializable] public class ObjectInfo { public string name; public string parent; public string[] components; public string[] fields; }
    [Serializable] public class Snapshot {
        public string checkpoint,utc,scene,graphicsApi,gpu,persistentDataPath,streamingAssetsPath,privateDataPath,camera,unityVersion;
        public string audio="not initialized: isolated lab",network="not initialized: isolated lab",gameState="no RoR2 gameplay loaded";
        public bool playerExists; public string[] controllers,renderers,assemblies; public ObjectInfo[] hierarchy;
        public float fps,frameMs; public long managedBytes,totalAllocatedBytes;public double cpuFrameMs,gpuFrameMs;
    }
    string root; float elapsed; int frames; float fps; bool ready; Config config=new Config();
    Renderer referenceGeometry;bool referenceRendering=true;Renderer referenceCube;bool cubeVisibility;
    public bool ReferenceRendering {get{return referenceRendering;}}
    public bool Ready {get{return ready;}}
    public void SetReferenceRendering(bool visible){
        referenceRendering=visible;if(referenceGeometry)referenceGeometry.enabled=visible;
        if(!referenceCube){var cube=GameObject.Find("G1 reference cube");if(cube){referenceCube=cube.GetComponent<Renderer>();}}
        if(referenceCube)cubeVisibility=referenceCube.enabled;
        if(referenceCube)referenceCube.enabled=visible&&cubeVisibility;
    }
    IEnumerator Start() {
        Application.targetFrameRate = 300;
        root=Application.persistentDataPath; Directory.CreateDirectory(root); Application.logMessageReceived+=OnLog;
        yield return null;
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
        var snapshot=new Snapshot{checkpoint=checkpoint,utc=DateTime.UtcNow.ToString("o"),scene=SceneManager.GetActiveScene().name,graphicsApi=SystemInfo.graphicsDeviceType.ToString(),gpu=SystemInfo.graphicsDeviceName,persistentDataPath=root,streamingAssetsPath=Application.streamingAssetsPath,fps=fps,frameMs=fps>0?1000/fps:0,managedBytes=Profiler.GetMonoUsedSizeLong(),totalAllocatedBytes=Profiler.GetTotalAllocatedMemoryLong(),unityVersion=Application.unityVersion};
        File.WriteAllText(Path.Combine(root,"snapshot.json"),JsonUtility.ToJson(snapshot,true));
        if(checkpoint!="periodic")Debug.Log("LAB_SNAPSHOT "+JsonUtility.ToJson(snapshot));
    }
    void OnGUI(){GUI.Label(new Rect(15,15,950,100),"PORTING LAB X64 | "+SystemInfo.graphicsDeviceType+" | "+fps.ToString("F1")+" FPS\n"+(ready?"LAB READY":"LOADING"));}
}
