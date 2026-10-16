using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Linq;
using RoR2;
using RoR2.ContentManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

// Schedules unchanged original clock callbacks on the owned inactive Run, without its startup.
public sealed partial class MovementBatchProbe {
 [Serializable] public class RunClockReport {
  public bool catalogReady,originalCallbacks,stopwatchRunning,cleaned,asyncAssetsReleased;public string scene,error,scope;public int sceneIndex,sceneDefs,convertedDestinations,selectedDifficulty,fixedTicks,frameTicks,asyncAssetTicks,endRunEffectLoansReturned;public float beganFixed,beganStopwatch,fixedTime,frameTime,stampTime,stopwatch,difficulty,compensatedDifficulty,ambient;public bool paused;
 }
 Action<SceneExitController> ownedStageAsyncRelease,nativeStageAsyncRelease;
 Action ownedRunFixed,ownedRunFrame,ownedAsyncAssetFrame;bool ownsRunAsyncLifecycle;Run clockRun;Scene priorClockScene;SceneDef[] priorContentScenes;SceneDef clockSceneDef;SceneDef[] clockSceneDefs;
 readonly Dictionary<FieldInfo,object> clockSceneFields=new Dictionary<FieldInfo,object>();IDictionary clockSceneMap;ResourceAvailability priorSceneAvailability;
 FieldInfo clockFixedStamp,clockFrameStamp;object priorClockFixedStamp,priorClockFrameStamp;bool ownsRunSceneCatalog;
 IEnumerator PrepareRunSceneContext(Result cfg){
  Check(SceneCatalog.sceneDefCount==0&&SceneCatalog.allStageSceneDefs.Length==0&&!SceneCatalog.mostRecentSceneDef,"Existing scene catalog; refuse replacement");
  r.runClock=new RunClockReport{scope="Original source stage metadata and Run Update/FixedUpdate on an inactive owned Run; converted geometry subset only, no full Run startup/menu/profile/stage progression"};r.phase="run-scene-catalog";Save();
  var flags=BindingFlags.NonPublic|BindingFlags.Static;foreach(var name in new[]{"indexToSceneDef","_stageSceneDefs","_baseSceneNames","currentSceneDef","<mostRecentSceneDef>k__BackingField"}){var field=typeof(SceneCatalog).GetField(name,flags);Check(field!=null,"Original scene catalog field missing: "+name);clockSceneFields[field]=field.GetValue(null);}
  clockSceneMap=(IDictionary)typeof(SceneCatalog).GetField("nameToIndex",flags).GetValue(null);Check(clockSceneMap.Count==0,"Existing scene name map");priorSceneAvailability=SceneCatalog.availability;priorContentScenes=ContentManager._sceneDefs;
  var firstSceneAsset=firstStagePolicyConsumed?cfg.runSceneDefAssets.Single(asset=>System.IO.Path.GetFileNameWithoutExtension(asset).Equals(firstStageName,StringComparison.OrdinalIgnoreCase)):cfg.runSceneDefAsset;
  var stagedFirst=artifactBundle.LoadAsset<SceneDef>(firstSceneAsset);
  var sourceScenes=cfg.integratedWorld&&Resources.Load<TextAsset>("WholeCatalogBootstrap")?WholeCatalogComposed.CategoryFamily(AddressablesLabels.sceneDef,Array.Empty<SceneDef>()):null;
  clockSceneDef=sourceScenes==null?stagedFirst:sourceScenes.SingleOrDefault(scene=>scene.cachedName==(firstStageName??"golemplains"));
  Check(stagedFirst&&clockSceneDef&&clockSceneDef.cachedName==(firstStageName??"golemplains")&&clockSceneDef.sceneType==SceneType.Stage&&clockSceneDef.stageOrder==1&&!clockSceneDef.requiredExpansion&&stagedFirst.cachedName==clockSceneDef.cachedName&&stagedFirst.sceneType==clockSceneDef.sceneType&&stagedFirst.stageOrder==clockSceneDef.stageOrder,"Original base stage metadata changed");
  Check(stageGeometryScene.IsValid()&&stageGeometryScene.isLoaded&&stageGeometryScene.name==clockSceneDef.cachedName,"Converted stage scene name must match original metadata");
  priorClockScene=SceneManager.GetActiveScene();ownsRunSceneCatalog=true;Check(SceneManager.SetActiveScene(stageGeometryScene),"Converted stage active-scene selection failed");clockSceneDefs=sourceScenes??(cfg.teleporterLoop?cfg.runSceneDefAssets.Select(x=>artifactBundle.LoadAsset<SceneDef>(x)).Distinct().ToArray():new[]{clockSceneDef});Check(clockSceneDefs.All(x=>x)&&clockSceneDefs.Contains(clockSceneDef),"Converted scene metadata missing: "+(cfg.runSceneDefAssets==null?"first stage":string.Join(",",cfg.runSceneDefAssets.Where(x=>!artifactBundle.LoadAsset<SceneDef>(x)))));
  if(sourceScenes!=null)Check(clockSceneDefs.Select(scene=>scene.cachedName).Distinct(StringComparer.Ordinal).Count()==clockSceneDefs.Length&&cfg.runSceneDefAssets.All(path=>clockSceneDefs.Any(scene=>scene.cachedName==System.IO.Path.GetFileNameWithoutExtension(path))),"Original scene provider identities or staged definitions differ");
  // Older selected-catalog compositions need the original Gold Shores definition;
  // the complete provider family above already contains it.
  if(sourceScenes==null&&cfg.integratedStages!=null&&cfg.integratedStages.Any(stage=>stage.name=="goldshores")){
   var gold=WholeCatalogComposed.LoadOwnedContent<SceneDef>("Assets/WholeGame/RoR2/Base/Scenes/goldshores/goldshores.asset");
   Check(gold.cachedName=="goldshores"&&gold.sceneType==SceneType.Intermission&&gold.stageOrder==96&&!gold.requiredExpansion,"Original Gold Shores scene metadata differs");
   clockSceneDefs=clockSceneDefs.Concat(new[]{gold}).Distinct().ToArray();
  }
  ContentManager._sceneDefs=clockSceneDefs;
  var init=SceneCatalog.Init();while(init.MoveNext())yield return init.Current;
  // Run the shipped scene-policy initializer; never manufacture a waiver.
  StaticCall(typeof(ExpansionWaiver),"Init");Check(!ExpansionWaiver.expansionsWaived,"Original scene policy unexpectedly enabled a waiver");
  r.runClock.scene=SceneManager.GetActiveScene().name;r.runClock.sceneIndex=(int)clockSceneDef.sceneDefIndex;r.runClock.sceneDefs=clockSceneDefs.Length;r.runClock.convertedDestinations=(cfg.integratedStages??new IntegratedStageSpec[0]).Length;r.runClock.catalogReady=SceneCatalog.mostRecentSceneDef==clockSceneDef&&SceneCatalog.GetSceneDefForCurrentScene()==clockSceneDef&&SceneCatalog.GetSceneDef(clockSceneDef.sceneDefIndex)==clockSceneDef&&SceneCatalog.sceneDefCount==clockSceneDefs.Length;
  Check(r.runClock.catalogReady,"Original scene catalog identity/completion failed");Save();
 }
 void StartOriginalRunClock(){
  if(r.runClock==null)return;clockRun=Run.instance;Check(clockRun&&clockRun.GetType()==typeof(Run)&&!clockRun.gameObject.activeInHierarchy&&clockRun.participatingPlayerCount==1&&clockRun.livingPlayerCount==1,"Original inactive Run/live-player clock context missing");
  clockFixedStamp=typeof(Run.FixedTimeStamp).GetField("tNow",BindingFlags.NonPublic|BindingFlags.Static);clockFrameStamp=typeof(Run.TimeStamp).GetField("tNow",BindingFlags.NonPublic|BindingFlags.Static);priorClockFixedStamp=clockFixedStamp.GetValue(null);priorClockFrameStamp=clockFrameStamp.GetValue(null);
  r.runClock.beganFixed=clockRun.fixedTime;r.runClock.beganStopwatch=clockRun.GetRunStopwatch();r.runClock.selectedDifficulty=(int)clockRun.selectedDifficulty;Check(r.runClock.beganFixed==0&&r.runClock.beganStopwatch==0&&clockRun.selectedDifficulty==(r.teleporterLoop?SelectedOfflineDifficulty():DifficultyIndex.Normal),"Measured original Run initial clock/difficulty changed");
  ownedRunFixed=(Action)Delegate.CreateDelegate(typeof(Action),clockRun,typeof(Run).GetMethod("FixedUpdate",BindingFlags.NonPublic|BindingFlags.Instance));ownedRunFrame=(Action)Delegate.CreateDelegate(typeof(Action),clockRun,typeof(Run).GetMethod("Update",BindingFlags.NonPublic|BindingFlags.Instance));r.runClock.originalCallbacks=true;
  Check(!RoR2Application.instance||!RoR2Application.instance.isActiveAndEnabled,"Original application already schedules async assets");
  Check(RewardField(typeof(AssetAsyncLiaison),"asyncOnUpdate").GetValue(null)!=null&&RewardField(typeof(AssetAsyncLiaison),"asyncOnSceneTransitionStarted").GetValue(null)!=null,"Original async asset startup callbacks missing");
  ownedAsyncAssetFrame=(Action)Delegate.CreateDelegate(typeof(Action),typeof(AssetAsyncLiaison).GetMethod("OnUpdate",BindingFlags.NonPublic|BindingFlags.Static));ownsRunAsyncLifecycle=true;
  nativeStageAsyncRelease=AssetAsyncLiaison.OnSceneTransitionStarted;
  ownedStageAsyncRelease=exit=>{if(ownsIntegratedPools)ReturnIntegratedStageEffects();nativeStageAsyncRelease(exit);};
  ReplaceOwnedStageRelease(nativeStageAsyncRelease,ownedStageAsyncRelease);
 }
 void ReplaceOwnedStageRelease(Action<SceneExitController> before,Action<SceneExitController> after){
  // Preserve every listener and its order. The native callback must receive an
  // empty owned effect pool before its synchronous asset-release operation.
  var field=typeof(SceneExitController).GetField("onFinishExit",BindingFlags.Static|BindingFlags.NonPublic);
  var listeners=(Delegate)field.GetValue(null);var entries=listeners==null?new Delegate[0]:listeners.GetInvocationList();
  Check(entries.Count(value=>value.Equals(before))==1,"Native stage asset-release callback ownership changed");
  field.SetValue(null,Delegate.Combine(entries.Select(value=>value.Equals(before)?after:value).ToArray()));
 }
 void TickOriginalRunClock(){if(ownedRunFixed==null)return;try{ownedRunFixed();r.runClock.fixedTicks++;TickMoonTimers();TickStageBossHeat();}catch(Exception e){r.runClock.error=e.ToString();ownedRunFixed=null;ownedRunFrame=null;Save();}}
 void Update(){TickDebugAcceleration();ObserveOfflineApplicationInput();ObserveWorldRestartInput();TickOriginalStage();if(ownedRunFrame==null)return;try{if(ownedAsyncAssetFrame!=null){ownedAsyncAssetFrame();r.runClock.asyncAssetTicks++;}ownedRunFrame();r.runClock.frameTicks++;}catch(Exception e){r.runClock.error=e.ToString();ownedRunFixed=null;ownedRunFrame=null;ownedAsyncAssetFrame=null;Save();}}
 void ReleaseCompletedRunAsyncAssets(){
  if(!ownsRunAsyncLifecycle)return;Check(!Run.instance,"Async end-run release requires completed owned Run teardown");
  // The final stage has no exit callback. Return this world's remaining native
  // effect loans after actor teardown, before the original forced pool release.
  if(ownsIntegratedPools){var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);r.runClock.endRunEffectLoansReturned=pools.Values.Sum(pool=>pool.InUseCount());ReturnIntegratedStageEffects();}
  // The inactive owned Run does not dispatch OnDestroy; use its shipped asset-release callback after actors exit.
  AssetAsyncLiaison.AssetAsyncReleaseAllReferences(true);ownsRunAsyncLifecycle=false;r.runClock.asyncAssetsReleased=true;Save();
 }
 void ObserveOriginalRunClock(){
  if(r.runClock==null||!clockRun)return;Check(string.IsNullOrEmpty(r.runClock.error),"Original Run clock callback failed: "+r.runClock.error);var report=r.runClock;
  report.fixedTime=clockRun.fixedTime;report.frameTime=clockRun.time;report.stampTime=Run.FixedTimeStamp.now.t;report.stopwatch=clockRun.GetRunStopwatch();report.paused=clockRun.NetworkrunStopwatch.isPaused;report.difficulty=clockRun.difficultyCoefficient;report.compensatedDifficulty=clockRun.compensatedDifficultyCoefficient;report.ambient=clockRun.ambientLevel;
  report.stopwatchRunning|=!report.paused&&report.stopwatch>report.beganStopwatch;Check(!clockRun.gameObject.activeInHierarchy&&report.stampTime==report.fixedTime,"Original clock owner/stamp consistency failed");
 }
 void VerifyOriginalRunClock(){
  if(r.runClock==null)return;ObserveOriginalRunClock();var report=r.runClock;Check(report.catalogReady&&report.originalCallbacks&&report.fixedTicks>3000&&report.frameTicks>1000&&report.fixedTime-report.beganFixed>60&&report.stopwatch-report.beganStopwatch>60&&report.stopwatchRunning&&!report.paused,"Original sustained Run clock/stopwatch incomplete");
  Check(Mathf.Abs(report.fixedTime-report.beganFixed-report.fixedTicks*Time.fixedDeltaTime)<.05f&&report.frameTime>=report.fixedTime-.05f&&report.frameTime<=report.fixedTime+Time.fixedDeltaTime+.05f,"Original fixed/frame clock interval failed");
  Check(report.selectedDifficulty==(int)(r.teleporterLoop?SelectedOfflineDifficulty():DifficultyIndex.Normal)&&report.difficulty>1.1f&&report.compensatedDifficulty>1.1f&&report.ambient>1&&clockRun.ambientLevelFloor==1,"Original elapsed-time difficulty/ambient progression failed");Save();
 }
 void CleanupRunClock(){
  if(!ownsRunSceneCatalog)return;if(clockRun&&string.IsNullOrEmpty(r.runClock.error))ObserveOriginalRunClock();ownedRunFixed=null;ownedRunFrame=null;ownedAsyncAssetFrame=null;
  if(ownedStageAsyncRelease!=null){ReplaceOwnedStageRelease(ownedStageAsyncRelease,nativeStageAsyncRelease);ownedStageAsyncRelease=null;nativeStageAsyncRelease=null;}
  SceneManager.activeSceneChanged-=(UnityEngine.Events.UnityAction<Scene,Scene>)Delegate.CreateDelegate(typeof(UnityEngine.Events.UnityAction<Scene,Scene>),typeof(SceneCatalog).GetMethod("OnActiveSceneChanged",BindingFlags.NonPublic|BindingFlags.Static));
  if(priorClockScene.IsValid()&&priorClockScene.isLoaded&&SceneManager.GetActiveScene()!=priorClockScene)Check(SceneManager.SetActiveScene(priorClockScene),"Prior active scene restoration failed");
  if(clockSceneDefs!=null)foreach(var def in clockSceneDefs)if(def)def.sceneDefIndex=SceneIndex.Invalid;ContentManager._sceneDefs=priorContentScenes;clockSceneMap.Clear();foreach(var entry in clockSceneFields)entry.Key.SetValue(null,entry.Value);SceneCatalog.availability=priorSceneAvailability;
  if(clockFixedStamp!=null){clockFixedStamp.SetValue(null,priorClockFixedStamp);clockFrameStamp.SetValue(null,priorClockFrameStamp);}r.runClock.cleaned=SceneManager.GetActiveScene()==priorClockScene&&SceneCatalog.sceneDefCount==0&&SceneCatalog.allStageSceneDefs.Length==0&&!SceneCatalog.mostRecentSceneDef&&clockSceneMap.Count==0&&ContentManager._sceneDefs==priorContentScenes;Check(r.runClock.cleaned,"Original scene/clock scope restoration incomplete");ownsRunSceneCatalog=false;Save();
 }
}
