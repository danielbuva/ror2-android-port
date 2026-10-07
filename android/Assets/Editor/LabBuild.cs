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
 [Serializable] class Request {public string request_id,api,output;public bool presentationOnly,stagePresentation;public string[] reflectionTextureGuids;}
 [Serializable] class Result {public bool success; public string result,apk,backend,request_id;public double seconds;public int errors;}
 [InitializeOnLoadMethod] static void ResumeQueuedBuild(){if(!string.IsNullOrEmpty(SessionState.GetString(PendingBuild,""))){EditorApplication.update-=DispatchBuild;EditorApplication.update+=DispatchBuild;}}
 [MenuItem("Porting Lab/Build ARM64")]
 public static void QueueBuild(){
  Enqueue("build-request.json");
 }
 [MenuItem("Porting Lab/Build Android Presentation Payload")]
 public static void QueuePresentation(){Enqueue("presentation-build-request.json");}
 static void Enqueue(string filename){
  if(BuildPipeline.isBuildingPlayer||!string.IsNullOrEmpty(SessionState.GetString(PendingBuild,""))||!string.IsNullOrEmpty(SessionState.GetString(RunningBuild,"")))throw new InvalidOperationException("A lab build is already active or queued");
  var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));var request=File.ReadAllText(Path.Combine(root,filename));
  if(string.IsNullOrEmpty(JsonUtility.FromJson<Request>(request).request_id))throw new InvalidOperationException("Missing lab build request identity");
  SessionState.SetString(PendingBuild,request);ResumeQueuedBuild();
 }
 static void DispatchBuild(){
  if(EditorApplication.isCompiling||EditorApplication.isUpdating||BuildPipeline.isBuildingPlayer)return;
  var request=SessionState.GetString(PendingBuild,"");EditorApplication.update-=DispatchBuild;if(string.IsNullOrEmpty(request))return;
  SessionState.SetString(PendingBuild,"");SessionState.SetString(RunningBuild,JsonUtility.FromJson<Request>(request).request_id);
  var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));var cfg=JsonUtility.FromJson<Request>(request);
  if(cfg.presentationOnly){BuildPresentation(root,cfg);return;}
  Directory.CreateDirectory(Path.Combine(root,"lab-build"));File.WriteAllText(Path.Combine(root,"lab-build/started.json"),request);Build();
 }
 static void BuildPresentation(string root,Request cfg){
  var result=new Result{request_id=cfg.request_id};var start=DateTime.UtcNow;
  try{
   string output=Path.GetFullPath(cfg.output),allowed=Path.Combine(root,"experiments/android-presentation")+Path.DirectorySeparatorChar;
   if(!output.StartsWith(allowed,StringComparison.Ordinal)||cfg.api!="vulkan")throw new Exception("Unexpected Android presentation output/target");
   Directory.CreateDirectory(output);File.WriteAllText(Path.Combine(output,"started.json"),JsonUtility.ToJson(cfg,true));
   var assets=new[]{"AndroidSurfacePresentation","AndroidTerrainPresentation","AndroidParticlePresentation","AndroidWaterPresentation","AndroidColorGrade","AndroidBillboardPresentation","AndroidOpaqueParticlePresentation","AndroidDistortionPresentation","AndroidIntersectionPresentation"}.Select(name=>"Assets/LabLoadingScene/Resources/"+name+".shader").ToArray();
   if(!assets.All(File.Exists))throw new Exception("Presentation shader input missing");
   var builds=new System.Collections.Generic.List<AssetBundleBuild>();
   if(cfg.stagePresentation){
    PreserveReflectionRange(output,cfg.reflectionTextureGuids);
    var sceneCfg=JsonUtility.FromJson<SceneProbeConfig>(File.ReadAllText(Path.Combine(root,"scene-probe-build.json")));
    var paths=new[]{sceneCfg.stageScene}.Concat(sceneCfg.nextStageScenes??new string[0]).ToArray();
    foreach(var name in new[]{"golemplains","foggyswamp","frozenwall","dampcavesimple","skymeadow"}){
     var path=paths.Single(x=>Path.GetFileNameWithoutExtension(x)==name);
     if(!path.StartsWith("Assets/LabLoadingScene/StageGeometry/",StringComparison.Ordinal)||!File.Exists(path))throw new Exception("Unexpected stage presentation path");
     builds.Add(new AssetBundleBuild{assetBundleName=name+"-spine-lab",assetNames=new[]{path}});
    }
   }else builds.Add(new AssetBundleBuild{assetBundleName="android-presentation-lab",assetNames=assets});
   if(!BuildPipeline.BuildAssetBundles(output,builds.ToArray(),BuildAssetBundleOptions.ChunkBasedCompression,BuildTarget.Android))throw new Exception("Android presentation bundle build failed");
   foreach(var path in assets){var shader=AssetDatabase.LoadAssetAtPath<Shader>(path);if(ShaderUtil.GetShaderMessages(shader).Any(x=>x.severity==UnityEditor.Rendering.ShaderCompilerMessageSeverity.Error))throw new Exception("Presentation shader compile error: "+path);}
   result.success=true;result.result="Android presentation bundle built; device rendering unverified";
  }catch(Exception e){result.result=e.ToString();Debug.LogException(e);}
  result.seconds=(DateTime.UtcNow-start).TotalSeconds;File.WriteAllText(Path.Combine(root,"presentation-build-result.json"),JsonUtility.ToJson(result,true));SessionState.SetString(RunningBuild,"");
 }
 [Serializable] class ReflectionImport {public string guid,path,before,after;public int size,mips;public bool readable,sRGB;}
 [Serializable] class ReflectionImports {public ReflectionImport[] textures;}
 static void PreserveReflectionRange(string output,string[] guids){
  if(guids==null||guids.Length==0||guids.Distinct().Count()!=guids.Length)throw new Exception("Missing or duplicate exact reflection texture identities");
  var rows=new System.Collections.Generic.List<ReflectionImport>();
  foreach(var guid in guids){
   var path=AssetDatabase.GUIDToAssetPath(guid);
   if(!path.StartsWith("Assets/LabLoadingScene/",StringComparison.Ordinal)||!path.EndsWith(".exr",StringComparison.OrdinalIgnoreCase))throw new Exception("Reflection texture outside generated lab assets");
   var importer=AssetImporter.GetAtPath(path) as TextureImporter;var before=AssetDatabase.LoadAssetAtPath<Cubemap>(path);
   if(importer==null||before==null||importer.textureShape!=TextureImporterShape.TextureCube||importer.sRGBTexture)throw new Exception("Unexpected source reflection importer");
   var row=new ReflectionImport{guid=guid,path=path,before=before.format.ToString(),size=before.width,mips=before.mipmapCount,readable=importer.isReadable,sRGB=importer.sRGBTexture};
   var platform=importer.GetPlatformTextureSettings("Android");platform.overridden=true;platform.format=TextureImporterFormat.RGBAHalf;importer.SetPlatformTextureSettings(platform);importer.SaveAndReimport();
   var after=AssetDatabase.LoadAssetAtPath<Cubemap>(path);row.after=after.format.ToString();
   if(after.format!=TextureFormat.RGBAHalf||after.width!=row.size||after.mipmapCount!=row.mips||importer.isReadable!=row.readable||importer.sRGBTexture!=row.sRGB)throw new Exception("Reflection range repair changed source shape/readability/color space");
   rows.Add(row);
  }
  File.WriteAllText(Path.Combine(output,"reflection-imports.json"),JsonUtility.ToJson(new ReflectionImports{textures=rows.ToArray()},true));
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
   var presentationShaders=new[]{"AndroidSurfacePresentation","AndroidTerrainPresentation","AndroidParticlePresentation","AndroidWaterPresentation","AndroidColorGrade","AndroidBillboardPresentation","AndroidOpaqueParticlePresentation","AndroidDistortionPresentation","AndroidIntersectionPresentation"}.Select(name=>"Assets/LabLoadingScene/Resources/"+name+".shader").ToArray();
   if(presentationShaders.All(File.Exists))bundleBuilds.Add(new AssetBundleBuild{assetBundleName="android-presentation-lab",assetNames=presentationShaders});
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
     if(!nextStage.StartsWith("Assets/LabLoadingScene/StageGeometry/")||!File.Exists(nextStage)||!new[]{"foggyswamp","frozenwall","dampcavesimple","skymeadow","moon2"}.Contains(name))throw new Exception("Unexpected composed next-stage path");
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
     if((cfg.objectiveSupportAssets.Length!=4&&cfg.objectiveSupportAssets.Length!=5&&cfg.objectiveSupportAssets.Length!=7&&cfg.objectiveSupportAssets.Length!=8&&cfg.objectiveSupportAssets.Length!=10&&cfg.objectiveSupportAssets.Length!=12&&cfg.objectiveSupportAssets.Length!=13&&cfg.objectiveSupportAssets.Length!=14&&cfg.objectiveSupportAssets.Length!=17&&cfg.objectiveSupportAssets.Length!=18)||cfg.objectiveSupportAssets.Any(x=>!x.StartsWith("Assets/LabLoadingScene/")||!File.Exists(x)))throw new Exception("Unexpected original objective support paths");
     if(cfg.objectiveSupportAssets.Length==14&&!cfg.objectiveSupportAssets.Any(x=>x.EndsWith("/Items/Feather/FeatherEffect.prefab",StringComparison.OrdinalIgnoreCase)))throw new Exception("Expanded support closure lacks original Feather effect");
     if(cfg.objectiveSupportAssets.Length>=17&&new[]{"/Items/Feather/FeatherEffect.prefab","/Items/Tooth/HealPack.prefab","/Items/BonusGoldPackOnKill/BonusMoneyPack.prefab","/Items/SlowOnHit/SlowDownTime.prefab"}.Any(suffix=>!cfg.objectiveSupportAssets.Any(x=>x.EndsWith(suffix,StringComparison.OrdinalIgnoreCase))))throw new Exception("Expanded loot closure lacks a required original provider");
     if(cfg.objectiveSupportAssets.Length==18&&!cfg.objectiveSupportAssets.Any(x=>x.EndsWith("/Items/StunChanceOnHit/ImpactStunGrenade.prefab",StringComparison.OrdinalIgnoreCase)))throw new Exception("Expanded loot closure lacks the original stun impact");
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
