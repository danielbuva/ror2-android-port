using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using RoR2.ContentManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

// Schedules unchanged original clock callbacks on the owned inactive Run, without its startup.
public sealed partial class MovementBatchProbe {
 [Serializable] public class RunClockReport {
  public bool catalogReady,originalCallbacks,stopwatchRunning,cleaned;public string scene,error,scope;public int sceneIndex,selectedDifficulty,fixedTicks,frameTicks;public float beganFixed,beganStopwatch,fixedTime,frameTime,stampTime,stopwatch,difficulty,compensatedDifficulty,ambient;public bool paused;
 }
 Action ownedRunFixed,ownedRunFrame;Run clockRun;Scene priorClockScene;SceneDef[] priorContentScenes;SceneDef clockSceneDef;
 readonly Dictionary<FieldInfo,object> clockSceneFields=new Dictionary<FieldInfo,object>();IDictionary clockSceneMap;ResourceAvailability priorSceneAvailability;
 FieldInfo clockFixedStamp,clockFrameStamp;object priorClockFixedStamp,priorClockFrameStamp;bool ownsRunSceneCatalog;
 IEnumerator PrepareRunSceneContext(Result cfg){
  Check(SceneCatalog.sceneDefCount==0&&SceneCatalog.allStageSceneDefs.Length==0&&!SceneCatalog.mostRecentSceneDef,"Existing scene catalog; refuse replacement");
  r.runClock=new RunClockReport{scope="Original source stage metadata and Run Update/FixedUpdate on an inactive owned Run; converted geometry subset only, no full Run startup/menu/profile/stage progression"};r.phase="run-scene-catalog";Save();
  var flags=BindingFlags.NonPublic|BindingFlags.Static;foreach(var name in new[]{"indexToSceneDef","_stageSceneDefs","_baseSceneNames","currentSceneDef","<mostRecentSceneDef>k__BackingField"}){var field=typeof(SceneCatalog).GetField(name,flags);Check(field!=null,"Original scene catalog field missing: "+name);clockSceneFields[field]=field.GetValue(null);}
  clockSceneMap=(IDictionary)typeof(SceneCatalog).GetField("nameToIndex",flags).GetValue(null);Check(clockSceneMap.Count==0,"Existing scene name map");priorSceneAvailability=SceneCatalog.availability;priorContentScenes=ContentManager._sceneDefs;
  clockSceneDef=artifactBundle.LoadAsset<SceneDef>(cfg.runSceneDefAsset);Check(clockSceneDef&&clockSceneDef.cachedName=="golemplains"&&clockSceneDef.sceneType==SceneType.Stage&&clockSceneDef.stageOrder==1&&!clockSceneDef.requiredExpansion,"Original base stage metadata changed");
  Check(stageGeometryScene.IsValid()&&stageGeometryScene.isLoaded&&stageGeometryScene.name==clockSceneDef.cachedName,"Converted stage scene name must match original metadata");
  priorClockScene=SceneManager.GetActiveScene();ownsRunSceneCatalog=true;Check(SceneManager.SetActiveScene(stageGeometryScene),"Converted stage active-scene selection failed");ContentManager._sceneDefs=new[]{clockSceneDef};
  var init=SceneCatalog.Init();while(init.MoveNext())yield return init.Current;
  r.runClock.scene=SceneManager.GetActiveScene().name;r.runClock.sceneIndex=(int)clockSceneDef.sceneDefIndex;r.runClock.catalogReady=SceneCatalog.mostRecentSceneDef==clockSceneDef&&SceneCatalog.GetSceneDefForCurrentScene()==clockSceneDef&&SceneCatalog.GetSceneDef(clockSceneDef.sceneDefIndex)==clockSceneDef&&SceneCatalog.sceneDefCount==1;
  Check(r.runClock.catalogReady,"Original scene catalog identity/completion failed");Save();
 }
 void StartOriginalRunClock(){
  if(r.runClock==null)return;clockRun=Run.instance;Check(clockRun&&clockRun.GetType()==typeof(Run)&&!clockRun.gameObject.activeInHierarchy&&clockRun.participatingPlayerCount==1&&clockRun.livingPlayerCount==1,"Original inactive Run/live-player clock context missing");
  clockFixedStamp=typeof(Run.FixedTimeStamp).GetField("tNow",BindingFlags.NonPublic|BindingFlags.Static);clockFrameStamp=typeof(Run.TimeStamp).GetField("tNow",BindingFlags.NonPublic|BindingFlags.Static);priorClockFixedStamp=clockFixedStamp.GetValue(null);priorClockFrameStamp=clockFrameStamp.GetValue(null);
  r.runClock.beganFixed=clockRun.fixedTime;r.runClock.beganStopwatch=clockRun.GetRunStopwatch();r.runClock.selectedDifficulty=(int)clockRun.selectedDifficulty;Check(r.runClock.beganFixed==0&&r.runClock.beganStopwatch==0&&clockRun.selectedDifficulty==DifficultyIndex.Normal,"Measured original Run initial clock/difficulty changed");
  ownedRunFixed=(Action)Delegate.CreateDelegate(typeof(Action),clockRun,typeof(Run).GetMethod("FixedUpdate",BindingFlags.NonPublic|BindingFlags.Instance));ownedRunFrame=(Action)Delegate.CreateDelegate(typeof(Action),clockRun,typeof(Run).GetMethod("Update",BindingFlags.NonPublic|BindingFlags.Instance));r.runClock.originalCallbacks=true;
 }
 void TickOriginalRunClock(){if(ownedRunFixed==null)return;try{ownedRunFixed();r.runClock.fixedTicks++;}catch(Exception e){r.runClock.error=e.ToString();ownedRunFixed=null;ownedRunFrame=null;Save();}}
 void Update(){ObserveWorldRestartInput();if(ownedRunFrame==null)return;try{ownedRunFrame();r.runClock.frameTicks++;}catch(Exception e){r.runClock.error=e.ToString();ownedRunFixed=null;ownedRunFrame=null;Save();}}
 void ObserveOriginalRunClock(){
  if(r.runClock==null||!clockRun)return;Check(string.IsNullOrEmpty(r.runClock.error),"Original Run clock callback failed: "+r.runClock.error);var report=r.runClock;
  report.fixedTime=clockRun.fixedTime;report.frameTime=clockRun.time;report.stampTime=Run.FixedTimeStamp.now.t;report.stopwatch=clockRun.GetRunStopwatch();report.paused=clockRun.NetworkrunStopwatch.isPaused;report.difficulty=clockRun.difficultyCoefficient;report.compensatedDifficulty=clockRun.compensatedDifficultyCoefficient;report.ambient=clockRun.ambientLevel;
  report.stopwatchRunning|=!report.paused&&report.stopwatch>report.beganStopwatch;Check(!clockRun.gameObject.activeInHierarchy&&report.stampTime==report.fixedTime,"Original clock owner/stamp consistency failed");
 }
 void VerifyOriginalRunClock(){
  if(r.runClock==null)return;ObserveOriginalRunClock();var report=r.runClock;Check(report.catalogReady&&report.originalCallbacks&&report.fixedTicks>3000&&report.frameTicks>1000&&report.fixedTime-report.beganFixed>60&&report.stopwatch-report.beganStopwatch>60&&report.stopwatchRunning&&!report.paused,"Original sustained Run clock/stopwatch incomplete");
  Check(Mathf.Abs(report.fixedTime-report.beganFixed-report.fixedTicks*Time.fixedDeltaTime)<.05f&&report.frameTime>=report.fixedTime-.05f&&report.frameTime<=report.fixedTime+Time.fixedDeltaTime+.05f,"Original fixed/frame clock interval failed");
  Check(report.selectedDifficulty==1&&report.difficulty>1.1f&&report.compensatedDifficulty>1.1f&&report.ambient>1&&clockRun.ambientLevelFloor==1,"Original elapsed-time difficulty/ambient progression failed");Save();
 }
 void CleanupRunClock(){
  if(!ownsRunSceneCatalog)return;if(clockRun&&string.IsNullOrEmpty(r.runClock.error))ObserveOriginalRunClock();ownedRunFixed=null;ownedRunFrame=null;
  SceneManager.activeSceneChanged-=(UnityEngine.Events.UnityAction<Scene,Scene>)Delegate.CreateDelegate(typeof(UnityEngine.Events.UnityAction<Scene,Scene>),typeof(SceneCatalog).GetMethod("OnActiveSceneChanged",BindingFlags.NonPublic|BindingFlags.Static));
  if(priorClockScene.IsValid()&&priorClockScene.isLoaded)Check(SceneManager.SetActiveScene(priorClockScene),"Prior active scene restoration failed");
  if(clockSceneDef)clockSceneDef.sceneDefIndex=SceneIndex.Invalid;ContentManager._sceneDefs=priorContentScenes;clockSceneMap.Clear();foreach(var entry in clockSceneFields)entry.Key.SetValue(null,entry.Value);SceneCatalog.availability=priorSceneAvailability;
  if(clockFixedStamp!=null){clockFixedStamp.SetValue(null,priorClockFixedStamp);clockFrameStamp.SetValue(null,priorClockFrameStamp);}r.runClock.cleaned=SceneManager.GetActiveScene()==priorClockScene&&SceneCatalog.sceneDefCount==0&&SceneCatalog.allStageSceneDefs.Length==0&&!SceneCatalog.mostRecentSceneDef&&clockSceneMap.Count==0&&ContentManager._sceneDefs==priorContentScenes;Check(r.runClock.cleaned,"Original scene/clock scope restoration incomplete");ownsRunSceneCatalog=false;Save();
 }
}
