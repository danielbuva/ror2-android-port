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
 [Serializable] public class Config {public string attempt;public bool loadingScene,applicationAwake,globalTextures,interpolation,fpsQueue;public TextureExpectation[] textures;}
 [Serializable] public class FpsSample {public float delta,expected,observed;public int index,turn;}
 [Serializable] public class TimingSample {public float previousFixed,currentFixed,renderTime,expected,observed;}
 [Serializable] public class TextureExpectation {public string name,variable;public int width,height;}
 [Serializable] public class Report {
  public string attempt,phase,error,profileRoot,contentRoot,applicationDataPath;
  public FpsSample[] fpsSamples;public bool fpsPassed,fpsRestored,callbackRegistered;public string fpsCallback;public TimingSample[] timingSamples;public bool interpolationPassed,interpolationRestored;public float interpolationFallback;public bool globalTexturesPassed,globalsRestored;public string[] textureBindings;public bool recoveredAwakeCompleted,loadingFlagBeforeAwake,realSingleton,assemblyTypesReady; public string buildId; public int pid,loadingUiYields; public string[] preFrameTargets,enableTargets; public bool loadingSceneReady,loadingCanvasReady,percentageReady,sceneApplicationInactive; public string activeScene;
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
  if(cfg.globalTextures)report.stopBoundary="After explicit original GlobalShaderTextures.Start and binding/restore assertions; application remains inactive";
  if(cfg.interpolation)report.stopBoundary="After original interpolation methods at diagnostic fixed/frame boundaries; application remains inactive";
  if(cfg.fpsQueue)report.stopBoundary="After isolated original FPSQueue callback sampling and state/subscription restoration; no full application Update";
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
 void TestGlobalTextures(RoR2.RoR2Application app){
  Phase("original-global-textures");var target=app.GetComponent<GlobalShaderTextures>();Require(target&&!target.enabled&&!target.gameObject.activeInHierarchy,"Expected inactive recovered texture component");
  var textures=new[]{target.warpRampTexture,target.eliteRampTexture,target.snowMicrofacetTexture};var names=new[]{target.warpRampShaderVariableName,target.eliteRampShaderVariableName,target.snowMicrofacetNoiseVariableName};
  Require(cfg.textures!=null&&cfg.textures.Length==3&&names.Distinct().Count()==3,"Expected three measured texture bindings");
  for(int i=0;i<3;i++){var e=cfg.textures[i];Require(textures[i]&&textures[i].name==e.name&&textures[i].width==e.width&&textures[i].height==e.height&&names[i]==e.variable,"Recovered texture identity mismatch at "+i);}
  var previous=names.Select(n=>Shader.GetGlobalTexture(n)).ToArray();
  try{
   foreach(var name in names)Shader.SetGlobalTexture(name,(Texture)null);
   Require(names.All(n=>!Shader.GetGlobalTexture(n)),"Diagnostic global reset failed");
   var start=typeof(GlobalShaderTextures).GetMethod("Start",BindingFlags.Instance|BindingFlags.NonPublic);Require(start!=null,"Original texture Start missing");start.Invoke(target,null);
   report.textureBindings=Enumerable.Range(0,3).Select(i=>names[i]+"="+textures[i].name+":"+textures[i].width+"x"+textures[i].height).ToArray();
   report.globalTexturesPassed=Enumerable.Range(0,3).All(i=>Shader.GetGlobalTexture(names[i])==textures[i]);Require(report.globalTexturesPassed,"Original texture binding failed");
  }finally{for(int i=0;i<3;i++)Shader.SetGlobalTexture(names[i],previous[i]);report.globalsRestored=Enumerable.Range(0,3).All(i=>Shader.GetGlobalTexture(names[i])==previous[i]);}
  Require(report.globalsRestored&&!target.enabled&&!app.gameObject.activeInHierarchy,"Texture probe restoration or inactive boundary failed");
 }
 IEnumerator TestInterpolation(RoR2.RoR2Application app){
  Phase("original-interpolation");var target=app.GetComponent<InterpolationController>();Require(target&&!target.enabled&&!app.gameObject.activeInHierarchy,"Expected inactive recovered interpolation component");
  var flags=BindingFlags.NonPublic|BindingFlags.Instance;var history=typeof(InterpolationController).GetField("m_lastFixedUpdateTimes",flags);var index=typeof(InterpolationController).GetField("m_newTimeIndex",flags);var factor=typeof(InterpolationController).GetField("m_interpolationFactor",BindingFlags.NonPublic|BindingFlags.Static);
  Require(history!=null&&index!=null&&factor!=null,"Original timing state fields missing");var oldHistory=history.GetValue(target);var oldIndex=index.GetValue(target);var oldFactor=factor.GetValue(null);
  var samples=new System.Collections.Generic.List<TimingSample>();
  try{
   target.Start();target.Update();report.interpolationFallback=InterpolationController.InterpolationFactor;Require(report.interpolationFallback==1f,"Original initial interpolation fallback mismatch");
   float previous=0f;
   for(int i=0;i<9;i++){
    yield return new WaitForFixedUpdate();float current=Time.fixedTime;Require(i==0||current>previous,"No distinct fixed-time sample");target.FixedUpdate();
    yield return null;float render=Time.time;target.Update();
    if(i>0){var sample=new TimingSample{previousFixed=previous,currentFixed=current,renderTime=render,expected=(render-current)/(current-previous),observed=InterpolationController.InterpolationFactor};samples.Add(sample);report.timingSamples=samples.ToArray();Save();Require(!float.IsNaN(sample.observed)&&!float.IsInfinity(sample.observed)&&Mathf.Abs(sample.expected-sample.observed)<0.0001f,"Original interpolation timing mismatch");var times=(float[])history.GetValue(target);Require(times.Length==2&&times.Contains(previous)&&times.Contains(current),"Original history differs from measured fixed ticks");}
    previous=current;
   }
   report.interpolationPassed=samples.Count==8;
  }finally{history.SetValue(target,oldHistory);index.SetValue(target,oldIndex);factor.SetValue(null,oldFactor);report.interpolationRestored=ReferenceEquals(history.GetValue(target),oldHistory)&&index.GetValue(target).Equals(oldIndex)&&factor.GetValue(null).Equals(oldFactor);}
  Require(report.interpolationPassed&&report.interpolationRestored&&!target.enabled&&!app.gameObject.activeInHierarchy,"Interpolation restoration or inactive boundary failed");
 }
 IEnumerator TestFpsQueue(RoR2.RoR2Application app){
  Phase("original-fps-queue");var target=app.GetComponent<FPSQueue>();Require(target&&!target.enabled&&!app.gameObject.activeInHierarchy,"Expected inactive recovered FPSQueue");
  var flags=BindingFlags.Static|BindingFlags.NonPublic|BindingFlags.Public;var fields=new[]{"sampleIndex","unitySamples","waitTurn","waitIndex","currentFPS"}.Select(n=>typeof(FPSQueue).GetField(n,flags)).ToArray();Require(fields.All(f=>f!=null),"FPSQueue state fields missing");var saved=fields.Select(f=>f.GetValue(null)).ToArray();
  var eventField=typeof(RoR2.RoR2Application).GetField("onUpdate",flags);Require(eventField!=null,"Original update event backing field missing");var before=(Action)eventField.GetValue(null);Action added=null;
  var rows=new System.Collections.Generic.List<FpsSample>();
  try{
   Require(FPSQueue.numSamples==30&&(int)saved[0]==0&&(int)saved[2]==0&&(int)saved[3]==0,"Unreviewed initial FPSQueue state");
   typeof(FPSQueue).GetMethod("Start",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(target,null);
   var after=(Action)eventField.GetValue(null);var oldCalls=before==null?new Delegate[0]:before.GetInvocationList();var calls=after.GetInvocationList();Require(calls.Length==oldCalls.Length+1&&calls.Take(oldCalls.Length).SequenceEqual(oldCalls),"Unexpected callback registration change");added=(Action)calls.Last();
   report.fpsCallback=added.Method.DeclaringType.FullName+"."+added.Method.Name;report.callbackRegistered=added.Target==null&&added.Method.DeclaringType==typeof(FPSQueue)&&added.Method.Name=="UpdateFPSLimitVars";Require(report.callbackRegistered,"Unexpected original callback identity");
   var observedRates=new System.Collections.Generic.Queue<float>();
   for(int i=0;i<36;i++){
    yield return null;float delta=Time.unscaledDeltaTime;Require(delta>0f,"Invalid real frame delta");observedRates.Enqueue(1f/delta);if(observedRates.Count>30)observedRates.Dequeue();added();
    var row=new FpsSample{delta=delta,expected=observedRates.Sum()/30f,observed=FPSQueue.currentFPS,index=(int)fields[0].GetValue(null),turn=(int)fields[2].GetValue(null)};rows.Add(row);report.fpsSamples=rows.ToArray();
    Require(!float.IsNaN(row.observed)&&!float.IsInfinity(row.observed)&&Mathf.Abs(row.expected-row.observed)<0.001f&&row.index==(i+1)%30&&row.turn==(i+1)%6,"Original FPS sample/index/turn mismatch");
    int slot=1;bool allowed=FPSQueue.CheckFPSQueue(ref slot);Require(allowed==(row.observed>=FPSQueue.fpsThrottlingCutoff||slot==row.turn),"Original throttling decision mismatch");
   }
   for(int i=1;i<=12;i++)Require(FPSQueue.GetWaitIndex()==i%6,"Original wait slot wrap mismatch");report.fpsPassed=true;
  }finally{if(added!=null)RoR2.RoR2Application.onUpdate-=added;for(int i=0;i<fields.Length;i++)fields[i].SetValue(null,saved[i]);report.fpsRestored=Equals(eventField.GetValue(null),before)&&fields.Select((f,i)=>Equals(f.GetValue(null),saved[i])).All(x=>x);}
  Require(report.fpsPassed&&report.fpsRestored&&!target.enabled&&!app.gameObject.activeInHierarchy,"FPSQueue restoration or inactive boundary failed");
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
    if(cfg.globalTextures)TestGlobalTextures(apps[0]);
    if(cfg.interpolation){var timing=TestInterpolation(apps[0]);while(timing.MoveNext())yield return timing.Current;}
    if(cfg.fpsQueue){var fps=TestFpsQueue(apps[0]);while(fps.MoveNext())yield return fps.Current;}
   }
  }
  // Never advance into component enabling/audio/platform/profile initialization.
  report.success=true;Phase("segment-complete");Debug.Log("LAB_STARTUP_SEGMENT_PASS");
 }
}
