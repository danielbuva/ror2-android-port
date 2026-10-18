using System;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
public static class ReconstructionProbe {
 [Serializable] class Findings{public string scene;public int gameObjects,missingScripts,nullMaterials;public string[] unsupportedShaders;public Plugin[] plugins;}
 [Serializable] class Plugin {public string path;public bool native,android,editor;}
 static string Out {get {var p=Path.GetFullPath(Path.Combine(Application.dataPath,"../../../../..","experiments/reconstruction"));Directory.CreateDirectory(p);return p;}}
 [MenuItem("Porting Lab/Inspect Reconstruction")]
 public static void Inspect(){
  var roots=UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects();var objects=roots.SelectMany(r=>r.GetComponentsInChildren<Transform>(true)).ToArray();var renderers=objects.SelectMany(t=>t.GetComponents<Renderer>()).ToArray();
  var result=new Findings{scene=UnityEngine.SceneManagement.SceneManager.GetActiveScene().path,gameObjects=objects.Length,missingScripts=objects.Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject)),nullMaterials=renderers.Sum(r=>r.sharedMaterials.Count(m=>!m)),unsupportedShaders=renderers.SelectMany(r=>r.sharedMaterials).Where(m=>m&&m.shader&&!m.shader.isSupported).Select(m=>m.shader.name).Distinct().ToArray(),plugins=PluginImporter.GetAllImporters().Select(i=>new Plugin{path=i.assetPath,native=i.isNativePlugin,android=i.GetCompatibleWithPlatform(BuildTarget.Android),editor=i.GetCompatibleWithEditor()}).ToArray()};
  File.WriteAllText(Path.Combine(Out,"inspection.json"),JsonUtility.ToJson(result,true));Debug.Log("RECONSTRUCTION_INSPECTED "+Out);
 }
 [MenuItem("Porting Lab/Build Reconstruction Minimum")]
 public static void QueueBuild(){EditorApplication.delayCall+=Build;}
 [Serializable] class Result{public bool success;public string result;public int errors;public double seconds;}
 public static void Build(){
  var r=new Result();var start=DateTime.UtcNow;string previous=UnityEngine.SceneManagement.SceneManager.GetActiveScene().path;
  try{
   PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android,"dev.ror2lab.reconstruction");PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android,ScriptingImplementation.IL2CPP);PlayerSettings.Android.targetArchitectures=AndroidArchitecture.ARM64;PlayerSettings.Android.targetSdkVersion=AndroidSdkVersions.AndroidApiLevel30;PlayerSettings.Android.useCustomKeystore=false;
   var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);new GameObject("Minimum camera").AddComponent<Camera>();EditorSceneManager.SaveScene(scene,"Assets/LabMinimum.unity");
   var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{"Assets/LabMinimum.unity"},locationPathName=Path.Combine(Out,"reconstruction-minimum.apk"),target=BuildTarget.Android,options=BuildOptions.Development});r.success=report.summary.result==BuildResult.Succeeded;r.result=report.summary.result.ToString();r.errors=(int)report.summary.totalErrors;
  }catch(Exception e){r.result=e.ToString();Debug.LogException(e);}
  r.seconds=(DateTime.UtcNow-start).TotalSeconds;File.WriteAllText(Path.Combine(Out,"build.json"),JsonUtility.ToJson(r,true));if(!string.IsNullOrEmpty(previous))EditorSceneManager.OpenScene(previous);Debug.Log("RECONSTRUCTION_BUILD_RESULT "+JsonUtility.ToJson(r));
 }
}
