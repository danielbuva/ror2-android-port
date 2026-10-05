using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
public static class LabBuild {
 const string PendingBuild="PortingLab.ARM64Pending",RunningBuild="PortingLab.ARM64Running";
 [Serializable] class Request {public string request_id,api;}
 [Serializable] class Result {public bool success; public string result,apk,backend,request_id;public double seconds;public int errors;}
 [InitializeOnLoadMethod] static void ResumeQueuedBuild(){if(!string.IsNullOrEmpty(SessionState.GetString(PendingBuild,""))){EditorApplication.update-=DispatchBuild;EditorApplication.update+=DispatchBuild;}}
 [MenuItem("Porting Lab/Build ARM64")]
 public static void QueueBuild(){
  if(BuildPipeline.isBuildingPlayer||!string.IsNullOrEmpty(SessionState.GetString(PendingBuild,"")))throw new InvalidOperationException("A lab build is already active or queued");
  var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));var request=File.ReadAllText(Path.Combine(root,"build-request.json"));
  if(string.IsNullOrEmpty(JsonUtility.FromJson<Request>(request).request_id))throw new InvalidOperationException("Missing lab build request identity");
  SessionState.SetString(PendingBuild,request);ResumeQueuedBuild();
 }
 static void DispatchBuild(){
  if(EditorApplication.isCompiling||EditorApplication.isUpdating||BuildPipeline.isBuildingPlayer)return;
  var request=SessionState.GetString(PendingBuild,"");EditorApplication.update-=DispatchBuild;if(string.IsNullOrEmpty(request))return;
  SessionState.SetString(PendingBuild,"");SessionState.SetString(RunningBuild,JsonUtility.FromJson<Request>(request).request_id);
  var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));Directory.CreateDirectory(Path.Combine(root,"lab-build"));File.WriteAllText(Path.Combine(root,"lab-build/started.json"),request);
  Build();
 }
 public static void Build(){
  string root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));string outDir=Path.Combine(root,"lab-build");Directory.CreateDirectory(outDir);var start=DateTime.UtcNow;var result=new Result{request_id=SessionState.GetString(RunningBuild,"")};
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
    if(!string.IsNullOrEmpty(cfg.stageScene)){
     if(!cfg.stageScene.StartsWith("Assets/LabLoadingScene/StageGeometry/")||!File.Exists(cfg.stageScene))throw new Exception("Unexpected stage geometry probe path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="golemplains-spine-lab",assetNames=new[]{cfg.stageScene}});
    }
    foreach(var nextStage in (cfg.nextStageScenes??new string[0]).Concat(string.IsNullOrEmpty(cfg.nextStageScene)?new string[0]:new[]{cfg.nextStageScene}).Distinct()){
     string name=Path.GetFileNameWithoutExtension(nextStage);
     if(!nextStage.StartsWith("Assets/LabLoadingScene/StageGeometry/")||!File.Exists(nextStage)||!new[]{"foggyswamp","frozenwall","dampcavesimple","skymeadow"}.Contains(name))throw new Exception("Unexpected composed next-stage path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName=name+"-spine-lab",assetNames=new[]{nextStage}});
    }
    if(!string.IsNullOrEmpty(cfg.prefab)){
     if(!cfg.prefab.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.prefab))throw new Exception("Unexpected prefab probe path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="commando-prefab-lab",assetNames=new System.Collections.Generic.List<string>(cfg.prefabAssets??new string[0]){cfg.prefab}.Distinct(StringComparer.OrdinalIgnoreCase).ToArray()});
    }
    if(!string.IsNullOrEmpty(cfg.teleportMaterial)){
     if(!cfg.teleportMaterial.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.teleportMaterial))throw new Exception("Unexpected teleport material probe path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="teleport-material-lab",assetNames=new[]{cfg.teleportMaterial}});
    }
    if(!string.IsNullOrEmpty(cfg.barrierEffect)){
     if(!cfg.barrierEffect.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.barrierEffect))throw new Exception("Unexpected barrier effect probe path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="barrier-effect-lab",assetNames=new[]{cfg.barrierEffect}});
    }
    if(cfg.objectiveSupportAssets!=null&&cfg.objectiveSupportAssets.Length>0){
     if(cfg.objectiveSupportAssets.Length!=4||cfg.objectiveSupportAssets.Any(x=>!x.StartsWith("Assets/LabLoadingScene/")||!File.Exists(x)))throw new Exception("Unexpected original objective support paths");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="objective-support-lab",assetNames=cfg.objectiveSupportAssets});
    }
    if(!string.IsNullOrEmpty(cfg.objectiveTMPSettings)){
     if(!cfg.objectiveTMPSettings.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.objectiveTMPSettings))throw new Exception("Unexpected original TMP settings path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="objective-ui-lab",assetNames=new[]{cfg.objectiveTMPSettings}});
    }
    if(!string.IsNullOrEmpty(cfg.teleporterIndicator)){
     if(!cfg.teleporterIndicator.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.teleporterIndicator))throw new Exception("Unexpected teleporter indicator path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="teleporter-indicator-lab",assetNames=new[]{cfg.teleporterIndicator}});
    }
    if(!string.IsNullOrEmpty(cfg.playerDeathEffect)){
     if(!cfg.playerDeathEffect.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.playerDeathEffect))throw new Exception("Unexpected player death effect path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="player-death-effect-lab",assetNames=new[]{cfg.playerDeathEffect}});
    }
    // S155 needs an independent provider lease while the character bundle stays loaded.
    if(!string.IsNullOrEmpty(cfg.pickupDroplet)){
     if(!cfg.pickupDroplet.StartsWith("Assets/LabLoadingScene/")||!File.Exists(cfg.pickupDroplet))throw new Exception("Unexpected pickup droplet probe path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="pickup-droplet-lab",assetNames=new[]{cfg.pickupDroplet}});
    }
    if(!string.IsNullOrEmpty(cfg.genericPickup)){
     if(!cfg.genericPickup.StartsWith("Assets/LabLoadingScene/",StringComparison.OrdinalIgnoreCase)||!File.Exists(cfg.genericPickup))throw new Exception("Unexpected generic pickup path");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="generic-pickup-lab",assetNames=new[]{cfg.genericPickup}});
    }
    if(cfg.enemyRewardAssets!=null&&cfg.enemyRewardAssets.Length>0){
     if((cfg.enemyRewardAssets.Length!=3&&cfg.enemyRewardAssets.Length!=5)||cfg.enemyRewardAssets.Any(x=>!x.StartsWith("Assets/LabLoadingScene/")||!File.Exists(x)))throw new Exception("Unexpected enemy reward/team probe paths");
     bundleBuilds.Add(new AssetBundleBuild{assetBundleName="enemy-reward-lab",assetNames=cfg.enemyRewardAssets});
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
  result.seconds=(DateTime.UtcNow-start).TotalSeconds;File.WriteAllText(Path.Combine(outDir,"result.json"),JsonUtility.ToJson(result,true));SessionState.SetString(RunningBuild,"");Debug.Log("LAB_BUILD_RESULT "+JsonUtility.ToJson(result));
 }
 [Serializable] class SceneProbeConfig {public string scene,prefab,teleportMaterial,barrierEffect,stageScene,nextStageScene,playerDeathEffect,pickupDroplet,genericPickup,teleporterIndicator,objectiveTMPSettings;public string[] prefabAssets,enemyRewardAssets,objectiveSupportAssets,nextStageScenes;}
 [MenuItem("Porting Lab/Record Backend Constraints")]
 public static void Backend(){
  var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));
  File.WriteAllText(Path.Combine(root,"backend-evidence.json"),"{\"editor\":\""+Application.unityVersion+"\",\"selectedBackend\":\""+PlayerSettings.GetScriptingBackend(BuildTargetGroup.Android)+"\",\"architecture\":\""+PlayerSettings.Android.targetArchitectures+"\"}");
 }
}
