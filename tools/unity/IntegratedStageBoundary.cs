using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Navigation;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Additive converted-stage transport, with a declared continuous-body entry adapter.
// No synthetic stage count, reward, kill, authority, ownership or platform identity.
public sealed partial class MovementBatchProbe {
 [Serializable] public class IntegratedStageSpec {public string name,bundle,scene,groundGraph,airGraph;public int previewCallbacks;public string[] emptyMeshPaths,emptyColliderPaths;}
 [Serializable] public class StageProgressReport {
  public string current,requested,error,scope;public bool transporting,cleaned;public int transitions,stageClearCount,completedBarrels,completedChests;
  public float enteredAt;public uint bodyId,masterId,moneyBefore,moneyAfter;public ulong experienceBefore,experienceAfter;
  public int itemsBefore,itemsAfter;public List<string> completed=new List<string>();
  public List<ObjectiveReport> completedObjectives=new List<ObjectiveReport>();
 }
 AndroidStageTransport worldTransport;GameObject worldTransportHost;Result integratedStageConfig;
 string pendingStage;bool transportingStage;int stagePickupBaseline;float stageEnteredAt;
 HashSet<GameObject> stageStaticRoots=new HashSet<GameObject>();
 void PrepareStageTransport(Result cfg){
  Check(!NetworkManager.singleton&&cfg.integratedStages!=null&&cfg.integratedStages.Length>0,"Unowned scene transport or missing converted stages");
  integratedStageConfig=cfg;r.stageProgress=new StageProgressReport{current=stageGeometryScene.name,bodyId=worldPlayer.netId.Value,masterId=worldPlayer.master.netId.Value,scope="Original Stage.Update, SceneExit and Run.AdvanceStage accounting; additive recovered scene/graph transport. Temporary continuous live-body/master/inventory adapter instead of stock network-user respawn. Stock startup, profiles, unsupported destinations and victory remain unavailable."};
  worldTransportHost=new GameObject("Owned Android additive scene transport");worldTransport=worldTransportHost.AddComponent<AndroidStageTransport>();worldTransport.enabled=false;
  Check(NetworkManager.singleton==worldTransport,"Original NetworkManager singleton registration missing");
  var online=worldTransport.CanPlayOnline();Check(online.MoveNext()&&online.Current==RoR2.Networking.NetworkManagerSystem.CanPlayOnlineState.No,"Android transport must report online capability unavailable");
  worldTransport.requested=name=>{Check(string.IsNullOrEmpty(pendingStage)&&!transportingStage,"Overlapping original stage requests");pendingStage=name;r.stageProgress.requested=name;r.stageProgress.stageClearCount=Run.instance.stageClearCount;Save();};
 }
 void TickOriginalStage(){
  if(r==null||!r.teleporterLoop||!objectiveStage||transportingStage||r.stageProgress==null||!string.IsNullOrEmpty(r.stageProgress.error))return;
  try{Call(objectiveStage,"Update");}catch(Exception e){r.stageProgress.error=e.ToString();Save();}
 }
 int IntegratedInventoryCount(){return ItemCatalog.allItemDefs.Sum(x=>worldPlayer.inventory.GetItemCountPermanent(x.itemIndex));}
 IEnumerator TransportIntegratedStage(NovaInputBridge bridge){
  if(string.IsNullOrEmpty(pendingStage))yield break;
  var next=integratedStageConfig.integratedStages.SingleOrDefault(x=>x.name==pendingStage);
  Check(next!=null,"Original next destination has no accepted converted content: "+pendingStage);
  var report=r.stageProgress;var run=Run.instance;var body=worldPlayer;var master=body.master;
  Check(r.objective.bossDefeated&&r.objective.charged&&r.objective.rewardCollected&&r.objective.exitFinished&&objectiveStage.completed,"Original stage reward/exit/completion missing before scene transport");
  report.completedBarrels+=r.world.openedBarrels;report.completedChests+=r.world.openedChests;report.completed.Add(stageGeometryScene.name+"|boss-defeated|natural-charge|reward-collected|original-exit");report.completedObjectives.Add(r.objective);report.moneyBefore=master.money;report.experienceBefore=TeamManager.instance.GetTeamExperience(TeamIndex.Player);report.itemsBefore=IntegratedInventoryCount();
  transportingStage=true;report.transporting=true;r.phase="integrated-stage-transition";Save();bridge.enabled=false;body.inputBank.moveVector=Vector3.zero;
  if(rewardDirector)rewardDirector.enabled=false;
  var motor=body.characterMotor;var solver=motor.Motor;solver.enabled=false;motor.velocity=Vector3.zero;
  // Old actors must release their original navigation agents before replacing source graphs.
  foreach(var actor in directorActors){if(actor.body)NetworkServer.Destroy(actor.body.gameObject);if(actor.master)NetworkServer.Destroy(actor.master.gameObject);if(actor.model)Destroy(actor.model);}
  foreach(var projectile in FindObjectsOfType<RoR2.Projectile.ProjectileController>())NetworkServer.Destroy(projectile.gameObject);
  foreach(var instance in objectiveSupportInstances)if(instance)NetworkServer.Destroy(instance);objectiveSupportInstances.Clear();
  foreach(var pickup in EjectionPickups().ToArray())NetworkServer.Destroy(pickup.gameObject);foreach(var droplet in EjectionDroplets().ToArray())NetworkServer.Destroy(droplet.gameObject);
  foreach(var obj in worldObjects)if(obj)NetworkServer.Destroy(obj);worldObjects.Clear();worldBarrels.Clear();worldChests.Clear();
  if(objectiveHost)NetworkServer.Destroy(objectiveHost);if(objectiveBossDeck)Destroy(objectiveBossDeck);if(objectiveStage){Call(objectiveStage,"OnDisable");Destroy(objectiveStageHost);}if(enemySceneHost)Destroy(enemySceneHost);
  yield return null;yield return null;
  Check(!SceneInfo.instance&&!Stage.instance&&!TeleporterInteraction.instance&&NavigationAgentCount()==0,"Old original scene context survived transition");
  var old=stageGeometryScene;
  ReturnIntegratedStageEffects(); // Original sceneUnloaded kills pools; release their live loans first.
  ReleaseObjectiveOrbCache(); // Original sceneUnloaded clears its map without releasing leases.
  foreach(var root in old.GetRootGameObjects())if(!stageStaticRoots.Contains(root))SceneManager.MoveGameObjectToScene(root,priorClockScene);
  Check(SceneManager.SetActiveScene(priorClockScene),"Persistent adapter scene missing");
  yield return SceneManager.UnloadSceneAsync(old);foreach(var mat in stageGeometryMaterials)if(mat)Destroy(mat);stageGeometryMaterials.Clear();
  if(stageGeometryBundle){stageGeometryBundle.Unload(true);stageGeometryBundle=null;}
  var geometry=LoadStageGeometry(next.bundle,next.previewCallbacks,next);while(geometry.MoveNext())yield return geometry.Current;
  Check(SceneManager.SetActiveScene(stageGeometryScene)&&SceneCatalog.GetSceneDefForCurrentScene().cachedName==next.name,"Actual next scene catalog/name mismatch");
  enemySceneHost=new GameObject("Owned original next-stage SceneInfo");enemySceneHost.SetActive(false);SceneManager.MoveGameObjectToScene(enemySceneHost,stageGeometryScene);
  var info=enemySceneHost.AddComponent<SceneInfo>();typeof(SceneInfo).GetField("groundNodesAsset",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(info,artifactBundle.LoadAsset<NodeGraph>(next.groundGraph));typeof(SceneInfo).GetField("airNodesAsset",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(info,artifactBundle.LoadAsset<NodeGraph>(next.airGraph));enemySceneHost.SetActive(true);yield return null;
  Check(SceneInfo.instance==info&&info.groundNodes.GetNodeCount()>0&&info.airNodes.GetNodeCount()>0,"Recovered next-stage navigation missing");
  // Explicit temporary entry placement; movement afterward is original motor/state/solver.
  solver.SetPosition(r.stage.spawnPosition);solver.CollidableLayers=LayerIndex.world.mask;solver.StableGroundLayers=LayerIndex.world.mask;solver.SetGroundSolvingActivation(true);solver.ForceUnground();solver.enabled=true;Physics.SyncTransforms();
  yield return new WaitForFixedUpdate();yield return null;
  float deadline=Time.realtimeSinceStartup+5;while((!solver.GroundingStatus.IsStableOnGround||!solver.GroundingStatus.GroundCollider||solver.GroundingStatus.GroundCollider.gameObject.scene!=stageGeometryScene)&&Time.realtimeSinceStartup<deadline)yield return null;
  Check(solver.GroundingStatus.IsStableOnGround&&solver.GroundingStatus.GroundCollider&&solver.GroundingStatus.GroundCollider.gameObject.scene==stageGeometryScene,"Next-stage entry does not land on recovered geometry");
  if(automaticDirectorHost)Destroy(automaticDirectorHost);yield return null;
  automaticDirectorHost=Instantiate(artifactBundle.LoadAsset<GameObject>(integratedStageConfig.enemyDirectorAsset));rewardDirector=automaticDirectorHost.GetComponent<CombatDirector>();rewardDirector.monsterCards=automaticDeck;
  automaticDirectorHost.AddComponent<DirectorCore>();rewardDirector.onSpawnedServer.AddListener(obj=>{RecordRewardSpawn(obj);RecordDirectorActor(obj,worldPlayer);});automaticDirectorHost.SetActive(true);
  Check(DirectorCore.instance&&rewardDirector.enabled&&CombatDirector.instancesList.Contains(rewardDirector),"Next-stage original director missing");
  worldObjective=0;stagePickupBaseline=r.world.pickupMessages;stageEnteredAt=r.nova.seconds;worldLastPress=-1;
  var origin=solver.TransientPosition;var chestSource=artifactBundle.LoadAsset<GameObject>(integratedStageConfig.chestAsset);
  foreach(var offset in new[]{new Vector3(2,0,0),new Vector3(-2,0,0),new Vector3(0,0,3),new Vector3(4,0,3),new Vector3(-4,0,3),new Vector3(0,0,-3)}){var obj=CreateWorldInteractable(artifactBundle.LoadAsset<GameObject>(integratedStageConfig.barrelAsset),origin+offset,false);if(obj)worldBarrels.Add(obj.GetComponent<BarrelInteraction>());}
  foreach(var offset in new[]{new Vector3(5,0,0),new Vector3(-5,0,0),new Vector3(0,0,6),new Vector3(6,0,6)}){var obj=CreateWorldInteractable(chestSource,origin+offset,true);if(obj)worldChests.Add(obj.GetComponent<ChestBehavior>());}
  Check(worldBarrels.Count>=3&&worldChests.Count>=2,"Recovered next-stage layout lacks walkable interactables");r.world.barrels=worldBarrels.Count;r.world.chests=worldChests.Count;
  var objective=SpawnStageObjective(integratedStageConfig);while(objective.MoveNext())yield return objective.Current;
  report.moneyAfter=master.money;report.experienceAfter=TeamManager.instance.GetTeamExperience(TeamIndex.Player);report.itemsAfter=IntegratedInventoryCount();
  Check(Run.instance==run&&worldPlayer==body&&body.master==master&&master.GetBody()==body&&body.netId.Value==report.bodyId&&master.netId.Value==report.masterId&&body.hasEffectiveAuthority&&report.itemsAfter==report.itemsBefore&&report.experienceAfter==report.experienceBefore&&report.moneyAfter==report.moneyBefore&&run.stageClearCount==report.completed.Count,"Original run/master/authority/inventory/XP/count continuity failed");
  report.current=next.name;report.transitions++;report.stageClearCount=run.stageClearCount;report.enteredAt=stageEnteredAt;report.transporting=false;pendingStage=null;transportingStage=false;bridge.enabled=true;r.phase="integrated-world-playing";Save();
 }
 void ReturnIntegratedStageEffects(){
  Check(ownsIntegratedPools,"Stage effect pools have no integrated ownership baseline");
  var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);
  foreach(var pool in pools.Values.ToArray())foreach(var effect in pool.InUse.ToArray())pool.ReturnObject(effect);
  Check(pools.Values.All(x=>x.InUseCount()==0),"Owned stage effect loans survived original return callbacks");
 }
 void CleanupStageTransport(){if(worldTransport)worldTransport.requested=null;if(NetworkManager.singleton==worldTransport)NetworkManager.singleton=null;if(worldTransportHost)Destroy(worldTransportHost);pendingStage=null;transportingStage=false;if(r.stageProgress!=null)r.stageProgress.cleaned=true;}
}
