using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEngine;
using UnityEngine.SceneManagement;
using Zio;
using Zio.FileSystems;

// Execute only the original routine's first yield and its reviewed PreFrame phase.
public class StartupSegmentProbe : MonoBehaviour {
 [Serializable] public class Config {public string attempt;public bool loadingScene,applicationAwake;}
 [Serializable] public class Report {
  public string attempt,phase,error,profileRoot,contentRoot,applicationDataPath;
  public bool recoveredAwakeCompleted,loadingFlagBeforeAwake,realSingleton,assemblyTypesReady; public string buildId; public int pid,loadingUiYields; public string[] preFrameTargets,enableTargets; public bool loadingSceneReady,loadingCanvasReady,percentageReady,sceneApplicationInactive; public string activeScene;
  public bool success,profileRoundTrip,profileReopen,contentReadOnly,pathEscapeRejected,profileCleaned,rootsSeparate,profileGlobalsUntouched,firstYieldReached,preFrameCompleted;
  public string stopBoundary="Before resuming InitializeGameRoutine after PreFrame; no audio/platform/save initialization";
 }
 Config cfg;Report report;
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("StartupSegmentProbe"))new GameObject("Original startup segment probe").AddComponent<StartupSegmentProbe>();}
 void Save(){File.WriteAllText(Path.Combine(Application.persistentDataPath,"startup-segment-probe.json"),JsonUtility.ToJson(report,true));}
 void Phase(string phase){report.phase=phase;Save();}
 static void Require(bool condition,string message){if(!condition)throw new Exception(message);}
 IEnumerator Start(){
  cfg=JsonUtility.FromJson<Config>(Resources.Load<TextAsset>("StartupSegmentProbe").text);report=new Report{attempt=cfg.attempt};
  if(cfg.loadingScene)report.stopBoundary="After two original loading-UI frame yields, before EnableBehaviours and Wwise";
  if(cfg.applicationAwake)report.stopBoundary="After explicitly invoked original Awake on inactive recovered application; no Start/Update/component enabling/audio";
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))report.pid=process.CallStatic<int>("myPid");
#endif
  yield return new WaitForSeconds(6);
  if(!File.Exists(Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab")))yield break;
  var priorPriority=Application.backgroundLoadingPriority;var run=Run();
  while(true){bool more;object next=null;try{more=run.MoveNext();if(more)next=run.Current;}catch(Exception e){report.error=e.ToString();report.success=false;Application.backgroundLoadingPriority=priorPriority;Save();yield break;}if(!more)break;yield return next;}
  Application.backgroundLoadingPriority=priorPriority;
 }
 void TestProfileRoots(){
  report.applicationDataPath=Application.dataPath;report.profileRoot=Path.Combine(Application.persistentDataPath,"profile-probe",cfg.attempt+"-"+Guid.NewGuid().ToString("N"));report.contentRoot=Path.Combine(Application.persistentDataPath,"payload");
  Require(!Directory.Exists(report.profileRoot),"Profile candidate already exists");Directory.CreateDirectory(report.profileRoot);
  using(var physical=new PhysicalFileSystem())
  using(var profiles=new SubFileSystem(physical,physical.ConvertPathFromInternal(report.profileRoot),false))
  using(var contentBase=new SubFileSystem(physical,physical.ConvertPathFromInternal(report.contentRoot),false))
  using(var content=new ReadOnlyFileSystem(contentBase,false)){
   UPath file=new UPath("/UserProfiles/probe.txt");profiles.CreateDirectory(new UPath("/UserProfiles"));string expected="ANDROID_PROFILE_PROBE "+cfg.attempt;
   using(var writer=new StreamWriter(profiles.OpenFile(file,FileMode.CreateNew,FileAccess.Write,FileShare.None)))writer.Write(expected);
   using(var reader=new StreamReader(profiles.OpenFile(file,FileMode.Open,FileAccess.Read,FileShare.Read)))report.profileRoundTrip=reader.ReadToEnd()==expected;
   using(var reopened=new SubFileSystem(physical,physical.ConvertPathFromInternal(report.profileRoot),false))using(var reader=new StreamReader(reopened.OpenFile(file,FileMode.Open,FileAccess.Read,FileShare.Read)))report.profileReopen=reader.ReadToEnd()==expected;
   report.rootsSeparate=profiles.ConvertPathToInternal(file)==Path.Combine(report.profileRoot,"UserProfiles","probe.txt")&&!content.FileExists(file);
   try{var escaped=new UPath("/../outside.txt");report.pathEscapeRejected=profiles.ConvertPathToInternal(escaped).StartsWith(report.profileRoot+Path.DirectorySeparatorChar,StringComparison.Ordinal);}catch(ArgumentException){report.pathEscapeRejected=true;}
   UPath denied=new UPath("/profile-write-denied-"+cfg.attempt+".txt");Require(!content.FileExists(denied),"Write-test target exists");
   try{using(var stream=content.OpenFile(denied,FileMode.CreateNew,FileAccess.Write,FileShare.None)){} }catch(IOException){report.contentReadOnly=true;}
   if(contentBase.FileExists(denied))contentBase.DeleteFile(denied);
   profiles.DeleteFile(file);report.profileCleaned=!profiles.FileExists(file);
  }
  report.profileGlobalsUntouched=RoR2.RoR2Application.fileSystem==null&&RoR2.RoR2Application.cloudStorage==null;
  Require(report.profileRoundTrip&&report.profileReopen&&report.rootsSeparate&&report.pathEscapeRejected&&report.contentReadOnly&&report.profileCleaned&&report.profileGlobalsUntouched,"Profile filesystem boundary assertions failed");
 }
 IEnumerator Run(){
  Phase("profile-filesystems");TestProfileRoots();Phase("original-first-yield");
  var host=new GameObject("Inactive original startup host");host.SetActive(false);var app=host.AddComponent<RoR2.RoR2Application>();Require(RoR2.RoR2Application.instance==null,"Unexpected application Awake");
  var method=typeof(RoR2.RoR2Application).GetMethod("InitializeGameRoutine",BindingFlags.Instance|BindingFlags.NonPublic);Require(method!=null,"Original routine missing");
  var routine=(IEnumerator)method.Invoke(app,null);Require(routine.MoveNext(),"Original startup ended before first yield");report.firstYieldReached=true;
  var phase=routine.Current as IEnumerator;Require(phase!=null,"First yield is not expected phase enumerator");
  var attributes=HG.Reflection.SearchableAttribute.GetInstances<RoR2.InitDuringStartupPhaseAttribute>();Require(attributes!=null,"No original startup attributes discovered");
  report.preFrameTargets=attributes.OfType<RoR2.InitDuringStartupPhaseAttribute>().Where(x=>x.InitPhase==RoR2.GameInitPhase.PreFrame).Select(x=>{var m=(MethodInfo)x.target;return m.DeclaringType.FullName+"."+m.Name;}).OrderBy(x=>x).ToArray();
  Require(report.preFrameTargets.SequenceEqual(new[]{"FlashWindow.Init"}),"Unreviewed or missing PreFrame targets");Phase("original-preframe");
  while(phase.MoveNext())yield return phase.Current;
  report.preFrameCompleted=true;Require(RoR2.RoR2Application.instance==null&&RoR2.RoR2Application.fileSystem==null&&RoR2.RoR2Application.cloudStorage==null,"Startup escaped selected boundary");
  if(cfg.loadingScene){
   Phase("recovered-loading-scene");
   var bundle=AssetBundle.LoadFromFile(Path.Combine(Application.persistentDataPath,"payload","loadingbasic-lab"));Require(bundle,"Loading scene bundle unavailable");
   var scenes=bundle.GetAllScenePaths();Require(scenes.Length==1,"Expected one recovered scene");var cameras=Camera.allCameras;
   yield return SceneManager.LoadSceneAsync(scenes[0],LoadSceneMode.Additive);
   var scene=SceneManager.GetSceneByPath(scenes[0]);Require(scene.IsValid()&&scene.isLoaded,"Recovered scene failed to load");SceneManager.SetActiveScene(scene);
   report.activeScene=SceneManager.GetActiveScene().name;report.loadingSceneReady=report.activeScene=="loadingbasic";Require(report.loadingSceneReady,"Original scene name mismatch");
   foreach(var camera in cameras)camera.enabled=false;
   var apps=scene.GetRootGameObjects().SelectMany(x=>x.GetComponentsInChildren<RoR2.RoR2Application>(true)).ToArray();Require(apps.Length==1,"Expected one recovered application component");
   report.sceneApplicationInactive=!apps[0].gameObject.activeInHierarchy&&RoR2.RoR2Application.instance==null;Require(report.sceneApplicationInactive,"Recovered application activated unexpectedly");
   var enable=apps[0].BehavioursToEnableDuringStartup;Require(enable!=null&&enable.All(x=>x),"Missing startup enable-list reference");
   report.enableTargets=enable.Select(x=>x.GetType().FullName+":"+x.name+":enabled="+x.enabled+":active="+x.gameObject.activeInHierarchy).ToArray();
   report.loadingCanvasReady=LoadingScreenCanvas.Instance;Require(report.loadingCanvasReady,"Original LoadingScreenCanvas instance missing");
   report.percentageReady=LoadingScreenCanvas.Instance.percentage;Require(report.percentageReady,"Original percentage reference missing");Phase("original-loading-ui");
   // Pinned routine yields exactly twice here before enabling components. Never request a third MoveNext.
   for(int i=0;i<2;i++){Require(routine.MoveNext()&&routine.Current is WaitForEndOfFrame,"Unexpected original loading-UI yield");report.loadingUiYields++;Save();yield return routine.Current;}
   Require(RoR2.RoR2Application.instance==null&&RoR2.RoR2Application.fileSystem==null&&RoR2.RoR2Application.cloudStorage==null,"Startup escaped selected loading-UI boundary");
   if(cfg.applicationAwake){
    Phase("recovered-application-awake");report.loadingFlagBeforeAwake=RoR2.RoR2Application.isLoading;Require(report.loadingFlagBeforeAwake,"Original routine has not established loading state");
    var awake=typeof(RoR2.RoR2Application).GetMethod("Awake",BindingFlags.Instance|BindingFlags.NonPublic);Require(awake!=null,"Original Awake missing");awake.Invoke(apps[0],null);
    report.realSingleton=RoR2.RoR2Application.instance==apps[0];report.buildId=RoR2.RoR2Application.GetBuildId();report.assemblyTypesReady=RoR2.RoR2Application.AssemblyTypes!=null&&RoR2.RoR2Application.AssemblyTypes.Contains(typeof(RoR2.CharacterBody));
    Require(report.realSingleton&&report.buildId==Application.version&&report.assemblyTypesReady,"Original application identity assertions failed");
    Require(!apps[0].gameObject.activeInHierarchy&&enable.All(x=>!x.enabled)&&RoR2.RoR2Application.isLoading&&RoR2.RoR2Application.fileSystem==null&&RoR2.RoR2Application.cloudStorage==null,"Awake escaped selected boundary");report.recoveredAwakeCompleted=true;
   }
  }
  // Never advance into component enabling/audio/platform/profile initialization.
  report.success=true;Phase("segment-complete");Debug.Log("LAB_STARTUP_SEGMENT_PASS");
 }
}
