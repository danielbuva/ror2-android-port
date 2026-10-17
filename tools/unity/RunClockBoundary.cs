// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareRunSceneContext, StartOriginalRunClock (RunClockSession); teardown CleanupRunClock (Dispose), then ReleaseCompletedRunAsyncAssets.
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
 // Shared with stage transport and the results catalog signature, respectively.
 Scene priorClockScene;SceneDef[] clockSceneDefs;
 RunClockSession runClockSession;
 RunClockSession GetRunClockSession(){if(runClockSession==null)runClockSession=new RunClockSession(this);return runClockSession;}
 IEnumerator PrepareRunSceneContext(SessionConfig cfg){return GetRunClockSession().PrepareRunSceneContext(cfg);}
 void StartOriginalRunClock(){GetRunClockSession().StartOriginalRunClock();}
 void TickOriginalRunClock(){GetRunClockSession().TickOriginalRunClock();}
 void Update(){TickDebugAcceleration();ObserveOfflineApplicationInput();ObserveWorldRestartInput();TickOriginalStage();GetRunClockSession().TickFrame();}
 void ReleaseCompletedRunAsyncAssets(){GetRunClockSession().ReleaseCompletedRunAsyncAssets();}
 void ObserveOriginalRunClock(){GetRunClockSession().ObserveOriginalRunClock();}
 void VerifyOriginalRunClock(){GetRunClockSession().VerifyOriginalRunClock();}
 void CleanupRunClock(){GetRunClockSession().Dispose();}

 // Create on first use, including Unity ticks before setup. Retain after Dispose:
 // final async release runs later, after actor and original Run teardown.
 sealed class RunClockSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  Action<SceneExitController> ownedStageAsyncRelease,nativeStageAsyncRelease;
  Action ownedRunFixed,ownedRunFrame,ownedAsyncAssetFrame;bool ownsRunAsyncLifecycle;Run clockRun;SceneDef[] priorContentScenes;SceneDef clockSceneDef;
  readonly Dictionary<FieldInfo,object> clockSceneFields=new Dictionary<FieldInfo,object>();IDictionary clockSceneMap;ResourceAvailability priorSceneAvailability;
  FieldInfo clockFixedStamp,clockFrameStamp;object priorClockFixedStamp,priorClockFrameStamp;bool ownsRunSceneCatalog;
  public RunClockSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public IEnumerator PrepareRunSceneContext(SessionConfig cfg){
   coordinator.Check(SceneCatalog.sceneDefCount==0&&SceneCatalog.allStageSceneDefs.Length==0&&!SceneCatalog.mostRecentSceneDef,"Existing scene catalog; refuse replacement");
   coordinator.r.runClock=new RunClockReport{scope="Original source stage metadata and Run Update/FixedUpdate on an inactive owned Run; converted geometry subset only, no full Run startup/menu/profile/stage progression"};coordinator.r.phase="run-scene-catalog";coordinator.Save();
   var flags=BindingFlags.NonPublic|BindingFlags.Static;foreach(var name in new[]{"indexToSceneDef","_stageSceneDefs","_baseSceneNames","currentSceneDef","<mostRecentSceneDef>k__BackingField"}){var field=typeof(SceneCatalog).GetField(name,flags);coordinator.Check(field!=null,"Original scene catalog field missing: "+name);clockSceneFields[field]=field.GetValue(null);}
   clockSceneMap=(IDictionary)typeof(SceneCatalog).GetField("nameToIndex",flags).GetValue(null);coordinator.Check(clockSceneMap.Count==0,"Existing scene name map");priorSceneAvailability=SceneCatalog.availability;priorContentScenes=ContentManager._sceneDefs;
   var firstSceneAsset=coordinator.firstStagePolicyConsumed?cfg.runSceneDefAssets.Single(asset=>System.IO.Path.GetFileNameWithoutExtension(asset).Equals(coordinator.firstStageName,StringComparison.OrdinalIgnoreCase)):cfg.runSceneDefAsset;
   var stagedFirst=coordinator.artifactBundle.LoadAsset<SceneDef>(firstSceneAsset);
   var sourceScenes=cfg.integratedWorld&&Resources.Load<TextAsset>("WholeCatalogBootstrap")?WholeCatalogComposed.CategoryFamily(AddressablesLabels.sceneDef,Array.Empty<SceneDef>()):null;
   clockSceneDef=sourceScenes==null?stagedFirst:sourceScenes.SingleOrDefault(scene=>scene.cachedName==(coordinator.firstStageName??"golemplains"));
   coordinator.Check(stagedFirst&&clockSceneDef&&clockSceneDef.cachedName==(coordinator.firstStageName??"golemplains")&&clockSceneDef.sceneType==SceneType.Stage&&clockSceneDef.stageOrder==1&&!clockSceneDef.requiredExpansion&&stagedFirst.cachedName==clockSceneDef.cachedName&&stagedFirst.sceneType==clockSceneDef.sceneType&&stagedFirst.stageOrder==clockSceneDef.stageOrder,"Original base stage metadata changed");
   coordinator.Check(coordinator.stageGeometryScene.IsValid()&&coordinator.stageGeometryScene.isLoaded&&coordinator.stageGeometryScene.name==clockSceneDef.cachedName,"Converted stage scene name must match original metadata");
   coordinator.priorClockScene=SceneManager.GetActiveScene();ownsRunSceneCatalog=true;coordinator.Check(SceneManager.SetActiveScene(coordinator.stageGeometryScene),"Converted stage active-scene selection failed");coordinator.clockSceneDefs=sourceScenes??(cfg.teleporterLoop?cfg.runSceneDefAssets.Select(x=>coordinator.artifactBundle.LoadAsset<SceneDef>(x)).Distinct().ToArray():new[]{clockSceneDef});coordinator.Check(coordinator.clockSceneDefs.All(x=>x)&&coordinator.clockSceneDefs.Contains(clockSceneDef),"Converted scene metadata missing: "+(cfg.runSceneDefAssets==null?"first stage":string.Join(",",cfg.runSceneDefAssets.Where(x=>!coordinator.artifactBundle.LoadAsset<SceneDef>(x)))));
   if(sourceScenes!=null)coordinator.Check(coordinator.clockSceneDefs.Select(scene=>scene.cachedName).Distinct(StringComparer.Ordinal).Count()==coordinator.clockSceneDefs.Length&&cfg.runSceneDefAssets.All(path=>coordinator.clockSceneDefs.Any(scene=>scene.cachedName==System.IO.Path.GetFileNameWithoutExtension(path))),"Original scene provider identities or staged definitions differ");
   // Older selected-catalog compositions need the original Gold Shores definition;
   // the complete provider family above already contains it.
   if(sourceScenes==null&&cfg.integratedStages!=null&&cfg.integratedStages.Any(stage=>stage.name=="goldshores")){
    var gold=WholeCatalogComposed.LoadOwnedContent<SceneDef>("Assets/WholeGame/RoR2/Base/Scenes/goldshores/goldshores.asset");
    coordinator.Check(gold.cachedName=="goldshores"&&gold.sceneType==SceneType.Intermission&&gold.stageOrder==96&&!gold.requiredExpansion,"Original Gold Shores scene metadata differs");
    coordinator.clockSceneDefs=coordinator.clockSceneDefs.Concat(new[]{gold}).Distinct().ToArray();
   }
   ContentManager._sceneDefs=coordinator.clockSceneDefs;
   var init=SceneCatalog.Init();while(init.MoveNext())yield return init.Current;
   // Run the shipped scene-policy initializer; never manufacture a waiver.
   StaticCall(typeof(ExpansionWaiver),"Init");coordinator.Check(!ExpansionWaiver.expansionsWaived,"Original scene policy unexpectedly enabled a waiver");
   coordinator.r.runClock.scene=SceneManager.GetActiveScene().name;coordinator.r.runClock.sceneIndex=(int)clockSceneDef.sceneDefIndex;coordinator.r.runClock.sceneDefs=coordinator.clockSceneDefs.Length;coordinator.r.runClock.convertedDestinations=(cfg.integratedStages??new IntegratedStageSpec[0]).Length;coordinator.r.runClock.catalogReady=SceneCatalog.mostRecentSceneDef==clockSceneDef&&SceneCatalog.GetSceneDefForCurrentScene()==clockSceneDef&&SceneCatalog.GetSceneDef(clockSceneDef.sceneDefIndex)==clockSceneDef&&SceneCatalog.sceneDefCount==coordinator.clockSceneDefs.Length;
   coordinator.Check(coordinator.r.runClock.catalogReady,"Original scene catalog identity/completion failed");coordinator.Save();
  }
  public void StartOriginalRunClock(){
   if(coordinator.r.runClock==null)return;clockRun=Run.instance;coordinator.Check(clockRun&&clockRun.GetType()==typeof(Run)&&!clockRun.gameObject.activeInHierarchy&&clockRun.participatingPlayerCount==1&&clockRun.livingPlayerCount==1,"Original inactive Run/live-player clock context missing");
   clockFixedStamp=typeof(Run.FixedTimeStamp).GetField("tNow",BindingFlags.NonPublic|BindingFlags.Static);clockFrameStamp=typeof(Run.TimeStamp).GetField("tNow",BindingFlags.NonPublic|BindingFlags.Static);priorClockFixedStamp=clockFixedStamp.GetValue(null);priorClockFrameStamp=clockFrameStamp.GetValue(null);
   coordinator.r.runClock.beganFixed=clockRun.fixedTime;coordinator.r.runClock.beganStopwatch=clockRun.GetRunStopwatch();coordinator.r.runClock.selectedDifficulty=(int)clockRun.selectedDifficulty;coordinator.Check(coordinator.r.runClock.beganFixed==0&&coordinator.r.runClock.beganStopwatch==0&&clockRun.selectedDifficulty==(coordinator.r.teleporterLoop?coordinator.SelectedOfflineDifficulty():DifficultyIndex.Normal),"Measured original Run initial clock/difficulty changed");
   ownedRunFixed=(Action)Delegate.CreateDelegate(typeof(Action),clockRun,typeof(Run).GetMethod("FixedUpdate",BindingFlags.NonPublic|BindingFlags.Instance));ownedRunFrame=(Action)Delegate.CreateDelegate(typeof(Action),clockRun,typeof(Run).GetMethod("Update",BindingFlags.NonPublic|BindingFlags.Instance));coordinator.r.runClock.originalCallbacks=true;
   coordinator.Check(!RoR2Application.instance||!RoR2Application.instance.isActiveAndEnabled,"Original application already schedules async assets");
   coordinator.Check(RewardField(typeof(AssetAsyncLiaison),"asyncOnUpdate").GetValue(null)!=null&&RewardField(typeof(AssetAsyncLiaison),"asyncOnSceneTransitionStarted").GetValue(null)!=null,"Original async asset startup callbacks missing");
   ownedAsyncAssetFrame=(Action)Delegate.CreateDelegate(typeof(Action),typeof(AssetAsyncLiaison).GetMethod("OnUpdate",BindingFlags.NonPublic|BindingFlags.Static));ownsRunAsyncLifecycle=true;
   nativeStageAsyncRelease=AssetAsyncLiaison.OnSceneTransitionStarted;
   ownedStageAsyncRelease=exit=>{if(coordinator.ownsIntegratedPools)coordinator.ReturnIntegratedStageEffects();nativeStageAsyncRelease(exit);};
   ReplaceOwnedStageRelease(nativeStageAsyncRelease,ownedStageAsyncRelease);
  }
  void ReplaceOwnedStageRelease(Action<SceneExitController> before,Action<SceneExitController> after){
   // Preserve every listener and its order. The native callback must receive an
   // empty owned effect pool before its synchronous asset-release operation.
   var field=typeof(SceneExitController).GetField("onFinishExit",BindingFlags.Static|BindingFlags.NonPublic);
   var listeners=(Delegate)field.GetValue(null);var entries=listeners==null?new Delegate[0]:listeners.GetInvocationList();
   coordinator.Check(entries.Count(value=>value.Equals(before))==1,"Native stage asset-release callback ownership changed");
   field.SetValue(null,Delegate.Combine(entries.Select(value=>value.Equals(before)?after:value).ToArray()));
  }
  public void TickOriginalRunClock(){if(ownedRunFixed==null)return;try{ownedRunFixed();coordinator.r.runClock.fixedTicks++;coordinator.TickMoonTimers();coordinator.TickStageBossHeat();}catch(Exception e){coordinator.r.runClock.error=e.ToString();ownedRunFixed=null;ownedRunFrame=null;coordinator.Save();}}
  public void TickFrame(){if(ownedRunFrame==null)return;try{if(ownedAsyncAssetFrame!=null){ownedAsyncAssetFrame();coordinator.r.runClock.asyncAssetTicks++;}ownedRunFrame();coordinator.r.runClock.frameTicks++;}catch(Exception e){coordinator.r.runClock.error=e.ToString();ownedRunFixed=null;ownedRunFrame=null;ownedAsyncAssetFrame=null;coordinator.Save();}}
  public void ReleaseCompletedRunAsyncAssets(){
   if(!ownsRunAsyncLifecycle)return;coordinator.Check(!Run.instance,"Async end-run release requires completed owned Run teardown");
   // The final stage has no exit callback. Return this world's remaining native
   // effect loans after actor teardown, before the original forced pool release.
   if(coordinator.ownsIntegratedPools){var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);coordinator.r.runClock.endRunEffectLoansReturned=pools.Values.Sum(pool=>pool.InUseCount());coordinator.ReturnIntegratedStageEffects();}
   // The inactive owned Run does not dispatch OnDestroy; use its shipped asset-release callback after actors exit.
   AssetAsyncLiaison.AssetAsyncReleaseAllReferences(true);ownsRunAsyncLifecycle=false;coordinator.r.runClock.asyncAssetsReleased=true;coordinator.Save();
  }
  public void ObserveOriginalRunClock(){
   if(coordinator.r.runClock==null||!clockRun)return;coordinator.Check(string.IsNullOrEmpty(coordinator.r.runClock.error),"Original Run clock callback failed: "+coordinator.r.runClock.error);var report=coordinator.r.runClock;
   report.fixedTime=clockRun.fixedTime;report.frameTime=clockRun.time;report.stampTime=Run.FixedTimeStamp.now.t;report.stopwatch=clockRun.GetRunStopwatch();report.paused=clockRun.NetworkrunStopwatch.isPaused;report.difficulty=clockRun.difficultyCoefficient;report.compensatedDifficulty=clockRun.compensatedDifficultyCoefficient;report.ambient=clockRun.ambientLevel;
   report.stopwatchRunning|=!report.paused&&report.stopwatch>report.beganStopwatch;coordinator.Check(!clockRun.gameObject.activeInHierarchy&&report.stampTime==report.fixedTime,"Original clock owner/stamp consistency failed");
  }
  public void VerifyOriginalRunClock(){
   if(coordinator.r.runClock==null)return;ObserveOriginalRunClock();var report=coordinator.r.runClock;coordinator.Check(report.catalogReady&&report.originalCallbacks&&report.fixedTicks>3000&&report.frameTicks>1000&&report.fixedTime-report.beganFixed>60&&report.stopwatch-report.beganStopwatch>60&&report.stopwatchRunning&&!report.paused,"Original sustained Run clock/stopwatch incomplete");
   coordinator.Check(Mathf.Abs(report.fixedTime-report.beganFixed-report.fixedTicks*Time.fixedDeltaTime)<.05f&&report.frameTime>=report.fixedTime-.05f&&report.frameTime<=report.fixedTime+Time.fixedDeltaTime+.05f,"Original fixed/frame clock interval failed");
   coordinator.Check(report.selectedDifficulty==(int)(coordinator.r.teleporterLoop?coordinator.SelectedOfflineDifficulty():DifficultyIndex.Normal)&&report.difficulty>1.1f&&report.compensatedDifficulty>1.1f&&report.ambient>1&&clockRun.ambientLevelFloor==1,"Original elapsed-time difficulty/ambient progression failed");coordinator.Save();
  }
  public void Dispose(){
   if(!ownsRunSceneCatalog)return;if(clockRun&&string.IsNullOrEmpty(coordinator.r.runClock.error))ObserveOriginalRunClock();ownedRunFixed=null;ownedRunFrame=null;ownedAsyncAssetFrame=null;
   if(ownedStageAsyncRelease!=null){ReplaceOwnedStageRelease(ownedStageAsyncRelease,nativeStageAsyncRelease);ownedStageAsyncRelease=null;nativeStageAsyncRelease=null;}
   SceneManager.activeSceneChanged-=(UnityEngine.Events.UnityAction<Scene,Scene>)Delegate.CreateDelegate(typeof(UnityEngine.Events.UnityAction<Scene,Scene>),typeof(SceneCatalog).GetMethod("OnActiveSceneChanged",BindingFlags.NonPublic|BindingFlags.Static));
   if(coordinator.priorClockScene.IsValid()&&coordinator.priorClockScene.isLoaded&&SceneManager.GetActiveScene()!=coordinator.priorClockScene)coordinator.Check(SceneManager.SetActiveScene(coordinator.priorClockScene),"Prior active scene restoration failed");
   if(coordinator.clockSceneDefs!=null)foreach(var def in coordinator.clockSceneDefs)if(def)def.sceneDefIndex=SceneIndex.Invalid;ContentManager._sceneDefs=priorContentScenes;clockSceneMap.Clear();foreach(var entry in clockSceneFields)entry.Key.SetValue(null,entry.Value);SceneCatalog.availability=priorSceneAvailability;
   if(clockFixedStamp!=null){clockFixedStamp.SetValue(null,priorClockFixedStamp);clockFrameStamp.SetValue(null,priorClockFrameStamp);}coordinator.r.runClock.cleaned=SceneManager.GetActiveScene()==coordinator.priorClockScene&&SceneCatalog.sceneDefCount==0&&SceneCatalog.allStageSceneDefs.Length==0&&!SceneCatalog.mostRecentSceneDef&&clockSceneMap.Count==0&&ContentManager._sceneDefs==priorContentScenes;coordinator.Check(coordinator.r.runClock.cleaned,"Original scene/clock scope restoration incomplete");ownsRunSceneCatalog=false;coordinator.Save();
  }
 }
}
