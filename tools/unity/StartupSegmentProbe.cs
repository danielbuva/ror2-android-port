using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEngine;
using Zio;
using Zio.FileSystems;

// Execute only the original routine's first yield and its reviewed PreFrame phase.
public class StartupSegmentProbe : MonoBehaviour {
 [Serializable] public class Config {public string attempt;}
 [Serializable] public class Report {
  public string attempt,phase,error,profileRoot,contentRoot,applicationDataPath;
  public int pid; public string[] preFrameTargets;
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
  report.applicationDataPath=Application.dataPath;report.profileRoot=Path.Combine(Application.persistentDataPath,"profile-probe",cfg.attempt);report.contentRoot=Path.Combine(Application.persistentDataPath,"payload");
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
  // Do not advance routine: next phases would introduce audio/platform/profile side effects.
  report.success=true;Phase("segment-complete");Debug.Log("LAB_STARTUP_SEGMENT_PASS");
 }
}
