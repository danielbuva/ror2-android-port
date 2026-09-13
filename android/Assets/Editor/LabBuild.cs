using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
public static class LabBuild {
 [Serializable] class Result {public bool success; public string result,apk,backend;public double seconds;public int errors;}
 [MenuItem("Porting Lab/Build ARM64")]
 public static void QueueBuild(){EditorApplication.delayCall+=Build;}
 public static void Build(){
  string root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));string outDir=Path.Combine(root,"lab-build");Directory.CreateDirectory(outDir);var start=DateTime.UtcNow;var result=new Result();
  try{
   PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android,"dev.ror2lab.arm64");PlayerSettings.companyName="PortingLab";PlayerSettings.productName="RoR2 Porting Lab";
   PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android,ScriptingImplementation.IL2CPP);PlayerSettings.Android.targetArchitectures=AndroidArchitecture.ARM64;
   PlayerSettings.Android.minSdkVersion=AndroidSdkVersions.AndroidApiLevel23;PlayerSettings.Android.targetSdkVersion=AndroidSdkVersions.AndroidApiLevel30;
   PlayerSettings.Android.preferredInstallLocation=AndroidPreferredInstallLocation.Auto;PlayerSettings.Android.useCustomKeystore=false;PlayerSettings.stripEngineCode=false;
   PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android,ManagedStrippingLevel.Low);
   string api=File.Exists(Path.Combine(root,"graphics-api.txt"))?File.ReadAllText(Path.Combine(root,"graphics-api.txt")).Trim():"gles";
   PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android,false);PlayerSettings.SetGraphicsAPIs(BuildTarget.Android,new[]{api=="vulkan"?GraphicsDeviceType.Vulkan:GraphicsDeviceType.OpenGLES3});
   PlayerSettings.enableFrameTimingStats=true;
   Directory.CreateDirectory(Path.Combine(root,"generated-android-data"));
   var bundleBuilds=new System.Collections.Generic.List<AssetBundleBuild>();
   string sceneProbeConfig=Path.Combine(root,"scene-probe-build.json");
   if(File.Exists(sceneProbeConfig)){
    var cfg=JsonUtility.FromJson<SceneProbeConfig>(File.ReadAllText(sceneProbeConfig));
    if(!cfg.scene.StartsWith("Assets/LabLoadingScene/") || !File.Exists(cfg.scene))throw new Exception("Unexpected loading scene probe path");
    bundleBuilds.Add(new AssetBundleBuild{assetBundleName="loadingbasic-lab",assetNames=new[]{cfg.scene}});
    if(!string.IsNullOrEmpty(cfg.prefab)){
     if(!cfg.prefab.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.prefab))throw new Exception("Unexpected prefab probe path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="commando-prefab-lab",assetNames=new System.Collections.Generic.List<string>(cfg.prefabAssets??new string[0]){cfg.prefab}.ToArray()});
    }
   }
   var mesh=AssetDatabase.LoadAssetAtPath<Mesh>("Assets/Recovered/geometry.obj");
   if(mesh==null)throw new Exception("Recovered mesh missing; prototype preparation required");
   bundleBuilds.Add(new AssetBundleBuild{assetBundleName="labgeometry",assetNames=new[]{"Assets/Recovered/geometry.obj"}});
   if(!BuildPipeline.BuildAssetBundles(Path.Combine(root,"generated-android-data"),bundleBuilds.ToArray(),BuildAssetBundleOptions.ChunkBasedCompression,BuildTarget.Android))throw new Exception("Requested bundle build failed");
   var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
   var camera=new GameObject("Lab Camera").AddComponent<Camera>();camera.tag="MainCamera";camera.backgroundColor=new Color(.04f,.06f,.09f);camera.clearFlags=CameraClearFlags.SolidColor;camera.gameObject.AddComponent<LabDiagnostics>();
   var light=new GameObject("Lab Light").AddComponent<Light>();light.type=LightType.Directional;light.transform.rotation=Quaternion.Euler(35,40,0);
   var cube=GameObject.CreatePrimitive(PrimitiveType.Cube);cube.name="G1 reference cube";cube.transform.position=new Vector3(3,0,0);
   EditorSceneManager.SaveScene(scene,"Assets/Lab.unity");EditorUserBuildSettings.buildAppBundle=false;
   result.apk=Path.Combine(outDir,"lab-"+api+".apk");result.backend="IL2CPP ARM64 "+api;
   var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{"Assets/Lab.unity"},locationPathName=result.apk,target=BuildTarget.Android,options=BuildOptions.Development});
   result.result=report.summary.result.ToString();result.errors=(int)report.summary.totalErrors;result.success=report.summary.result==BuildResult.Succeeded;
  }catch(Exception e){result.result=e.ToString();Debug.LogException(e);}
  result.seconds=(DateTime.UtcNow-start).TotalSeconds;File.WriteAllText(Path.Combine(outDir,"result.json"),JsonUtility.ToJson(result,true));Debug.Log("LAB_BUILD_RESULT "+JsonUtility.ToJson(result));
 }
 [Serializable] class SceneProbeConfig {public string scene,prefab;public string[] prefabAssets;}
 [MenuItem("Porting Lab/Record Backend Constraints")]
 public static void Backend(){
  var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));
  File.WriteAllText(Path.Combine(root,"backend-evidence.json"),"{\"editor\":\""+Application.unityVersion+"\",\"selectedBackend\":\""+PlayerSettings.GetScriptingBackend(BuildTargetGroup.Android)+"\",\"architecture\":\""+PlayerSettings.Android.targetArchitectures+"\"}");
 }
}
