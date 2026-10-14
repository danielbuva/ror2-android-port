using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Navigation;
using RoR2.ContentManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Additive converted-stage transport, with a declared continuous-body entry adapter.
// No synthetic stage count, reward, kill, authority, ownership or platform identity.
public sealed partial class MovementBatchProbe {
 [Serializable] public class IntegratedStageSpec {public bool moonMission;public string[] activeRoots;public int missionComponents;public string name,bundle,scene,groundGraph,airGraph;public int previewCallbacks,mapZoneCount,mapZoneNetworkObjects;public string[] mapZoneActiveNames;public string[] previewNames,emptyMeshPaths,emptyColliderPaths;}
 [Serializable] public class StageProgressReport {
  public string current,requested,error,scope,actualScene,actualSceneDef;public bool transporting,cleaned,activeSceneVerified;public int transitions,stageClearCount,completedBarrels,completedChests,effectLoansReturned,playerSummonsRemoved,retiredActorObservers,retiredModelObservers,retiredCommerceObservers,originalStageBegins;
  public float enteredAt,experienceSettlementSeconds;public uint bodyId,masterId,moneyBefore,moneyAfter;public ulong experienceBefore,experienceAfter,experienceAtExit,pendingExperienceAtExit;public int pendingExperienceAwardsAtExit;
  public int itemsBefore,itemsAfter;public List<string> completed=new List<string>();
  public List<ObjectiveReport> completedObjectives=new List<ObjectiveReport>();
  public List<StageEntryObservation> entryObservations=new List<StageEntryObservation>();
 }
 [Serializable] public class StageEntryObservation {public float at;public Vector3 position,velocity,queuedPositionTarget,bodyPosition,footPosition,corePosition;public bool sourceBounds,stable,groundCollider,groundEnabled,motorEnabled,solverEnabled,queuedPosition;public string tag,colliderPath,colliderScene;public int colliderLayer;public string[] mapZones;}
 void ObserveStageEntry(CharacterMotor motor,string tag="settling"){
  var solver=motor.Motor;var collider=solver.GroundingStatus.GroundCollider;var point=solver.TransientPosition;
  r.stageProgress.entryObservations.Add(new StageEntryObservation{tag=tag,at=Time.realtimeSinceStartup,sourceBounds=Util.IsPositionWithinMapBounds(point),position=point,velocity=motor.velocity,queuedPosition=(bool)solver.GetType().GetField("_movePositionDirty",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(solver),queuedPositionTarget=(Vector3)solver.GetType().GetField("_movePositionTarget",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(solver),bodyPosition=worldPlayer.transform.position,footPosition=worldPlayer.footPosition,corePosition=worldPlayer.corePosition,stable=solver.GroundingStatus.IsStableOnGround,groundCollider=collider,groundEnabled=collider&&collider.enabled,motorEnabled=motor.enabled,solverEnabled=solver.enabled,colliderPath=collider?StageObjectPath(collider.transform):"none",colliderScene=collider?collider.gameObject.scene.name:"none",colliderLayer=collider?collider.gameObject.layer:-1,mapZones=stageGeometryScene.GetRootGameObjects().SelectMany(x=>x.GetComponentsInChildren<MapZone>(true)).Where(x=>x.gameObject.activeInHierarchy).Select(x=>x.name+"|"+x.triggerType+"|"+x.zoneType+"|layer="+x.gameObject.layer+"|inside="+x.IsPointInsideMapZone(point)).ToArray()});Save();
 }
 AndroidStageTransport worldTransport;GameObject worldTransportHost;Result integratedStageConfig;
 string pendingStage;bool transportingStage;int stagePickupBaseline;float stageEnteredAt;
 HashSet<GameObject> stageStaticRoots=new HashSet<GameObject>();
 CursedBookSpellDef[] priorStageSpells;string[] priorStageSpellNames;ResourceAvailability priorStageSpellAvailability;bool ownsStageSpells;
 CraftableDef[] priorCraftableContent;object priorCraftableDefs,priorCraftableRecipes,priorIngredientTypes;ResourceAvailability priorCraftableAvailability,priorIngredientAvailability;bool ownsCraftableCatalog;
 void PrepareCraftableCatalog(){
  if(r.liveCatalogs==null||!stageSourceObjects)return;
  Check(!ownsCraftableCatalog&&PickupCatalog.pickupCount>0&&IngredientTypeCatalog.ingredientTypeCount==0&&CraftableCatalog.recipeCount==0&&CraftableCatalog.pickupToIngredientSearchTable.Count==0&&CraftableCatalog.resultToRecipeSearchTable.Count==0,"Original crafting dependencies have unexpected owners");
  var definitions=WholeCatalogComposed.DefinitionFamily(Array.Empty<CraftableDef>());
  Check(definitions.Length>0&&definitions.All(def=>def&&def.recipes!=null)&&definitions.Select(def=>def.name).Distinct().Count()==definitions.Length,"Original craftable definition closure is incomplete");
  priorCraftableContent=ContentManager._craftableDefs;priorCraftableDefs=RewardField(typeof(CraftableCatalog),"craftableDefs").GetValue(null);priorCraftableRecipes=RewardField(typeof(CraftableCatalog),"allRecipes").GetValue(null);priorIngredientTypes=RewardField(typeof(IngredientTypeCatalog),"ingredientTypeDefs").GetValue(null);priorCraftableAvailability=CraftableCatalog.availability;priorIngredientAvailability=IngredientTypeCatalog.availability;
  ownsCraftableCatalog=true;StaticCall(typeof(IngredientTypeCatalog),"Init");
  Check(IngredientTypeCatalog.ingredientTypeCount==5,"Original ingredient type initialization differs");
  ContentManager._craftableDefs=definitions;StaticCall(typeof(CraftableCatalog),"Init");
  var recipes=(IList)RewardField(typeof(CraftableCatalog),"allRecipes").GetValue(null);
  Check(CraftableCatalog.recipeCount==definitions.Length&&recipes.Count==definitions.Sum(def=>def.recipes.Length),"Original craftable recipe registration differs");
 }
 void CleanupCraftableCatalog(){
  if(!ownsCraftableCatalog)return;
  CraftableCatalog.pickupToIngredientSearchTable.Clear();CraftableCatalog.resultToRecipeSearchTable.Clear();
  RewardField(typeof(CraftableCatalog),"craftableDefs").SetValue(null,priorCraftableDefs);RewardField(typeof(CraftableCatalog),"allRecipes").SetValue(null,priorCraftableRecipes);ContentManager._craftableDefs=priorCraftableContent;CraftableCatalog.availability=priorCraftableAvailability;
  RewardField(typeof(IngredientTypeCatalog),"ingredientTypeDefs").SetValue(null,priorIngredientTypes);IngredientTypeCatalog.availability=priorIngredientAvailability;ownsCraftableCatalog=false;
 }
 void PrepareStageSpellCatalog(){
  if(r.liveCatalogs==null||!stageSourceObjects)return;
  Check(!ownsStageSpells&&CursedBookSpellCatalog.spellCount==0,"Unowned original Cursed Book spell catalog");
  var definitions=WholeCatalogComposed.DefinitionFamily(Array.Empty<CursedBookSpellDef>());
  Check(definitions.Length>0&&definitions.All(spell=>spell&&spell.itemDef&&spell.consumedItemDef)&&definitions.Select(spell=>spell.name).Distinct().Count()==definitions.Length,"Original Cursed Book spell closure is incomplete");
  priorStageSpells=ContentManager._cursedBookSpellDefs;priorStageSpellNames=CursedBookSpellCatalog.spellNames;priorStageSpellAvailability=CursedBookSpellCatalog.availability;
  ContentManager._cursedBookSpellDefs=Array.Empty<CursedBookSpellDef>();ownsStageSpells=true;
  StaticCall(typeof(CursedBookSpellCatalog),"SetCursedBookSpellDefs",new object[]{definitions});CursedBookSpellCatalog.availability.MakeAvailable();
  Check(CursedBookSpellCatalog.spellCount==definitions.Length&&CursedBookSpellCatalog.allCursedBookSpellDefs.All(spell=>spell.itemDef.itemIndex!=ItemIndex.None&&spell.consumedItemDef.itemIndex!=ItemIndex.None),"Original Cursed Book spell registration differs");
 }
 void CleanupStageSpellCatalog(){
  if(!ownsStageSpells)return;
  StaticCall(typeof(CursedBookSpellCatalog),"SetCursedBookSpellDefs",new object[]{Array.Empty<CursedBookSpellDef>()});
  ContentManager._cursedBookSpellDefs=priorStageSpells;CursedBookSpellCatalog.spellNames=priorStageSpellNames;CursedBookSpellCatalog.availability=priorStageSpellAvailability;ownsStageSpells=false;
 }
 void PrepareStageTransport(Result cfg){
  Check(!NetworkManager.singleton&&cfg.integratedStages!=null&&cfg.integratedStages.Length>0,"Unowned scene transport or missing converted stages");
  integratedStageConfig=cfg;r.stageProgress=new StageProgressReport{current=stageGeometryScene.name,bodyId=worldPlayer.netId.Value,masterId=worldPlayer.master.netId.Value,scope="Original Stage.Update, SceneExit and Run.AdvanceStage accounting; additive recovered scene/graph transport. Temporary continuous live-body/master/inventory adapter instead of stock network-user respawn. Stock startup, profiles, unsupported destinations and victory remain unavailable."};
  PrepareStageSpellCatalog();
  PrepareCraftableCatalog();
  worldTransportHost=new GameObject("Owned Android additive scene transport");worldTransport=worldTransportHost.AddComponent<AndroidStageTransport>();worldTransport.enabled=false;
  Check(NetworkManager.singleton==worldTransport,"Original NetworkManager singleton registration missing");
  var online=worldTransport.CanPlayOnline();Check(online.MoveNext()&&online.Current==RoR2.Networking.NetworkManagerSystem.CanPlayOnlineState.No,"Android transport must report online capability unavailable");
  worldTransport.requested=name=>{Check(string.IsNullOrEmpty(pendingStage)&&!transportingStage,"Overlapping original stage requests");pendingStage=name;r.stageProgress.requested=name;r.stageProgress.stageClearCount=Run.instance.stageClearCount;Save();};
 }
 bool ownsOriginalStage;
 IEnumerator BeginOriginalStage(){
  if(r.liveCatalogs==null||!stageSourceObjects)yield break;
  Check(objectiveStage&&!objectiveStageHost.activeInHierarchy&&Stage.instance==objectiveStage&&NetworkServer.active&&Run.instance,"Temporary stage context missing before original handoff");
  var spells=ContentManager.cursedBookSpellDefs;
  Check(spells!=null,"Original Cursed Book spell array absent before Stage.Start");
  foreach(var spell in spells)Check(spell&&spell.itemDef&&spell.consumedItemDef,"Original Cursed Book spell item references missing before Stage.Start: "+(spell?spell.name:"null spell")+" / item="+(spell&&(bool)spell.itemDef)+" / consumed="+(spell&&(bool)spell.consumedItemDef));
  var source=WholeCatalogComposed.LoadOwnedContent<GameObject>("Assets/WholeGame/RoR2/Base/Core/Network/Stage.prefab");
  var sourceIdentity=source.GetComponent<NetworkIdentity>();
  Check(source.name=="Stage"&&sourceIdentity&&source.GetComponent<Stage>()&&source.GetComponents<Component>().Length==3,"Original Stage prefab contract changed");
  var prior=objectiveStageHost;Call(objectiveStage,"OnDisable");Check(!Stage.instance,"Temporary Stage singleton survived original handoff");Destroy(prior);
  int begins=0;Action<Stage> onBegin=stage=>{if(stage==objectiveStage)begins++;};Stage.onServerStageBegin+=onBegin;
  try{
   Run.instance.OnServerSceneChanged(stageGeometryScene.name);
   objectiveStage=Stage.instance;objectiveStageHost=objectiveStage?objectiveStage.gameObject:null;
   var identity=objectiveStageHost?objectiveStageHost.GetComponent<NetworkIdentity>():null;
   Check(objectiveStageHost&&objectiveStageHost.activeInHierarchy&&identity&&identity.netId.Value!=0&&identity.assetId.Equals(sourceIdentity.assetId),"Original Run did not spawn the source Stage prefab");
   ownsOriginalStage=true;
   yield return null;
   Check(begins==1&&objectiveStage&&objectiveStage.sceneDef==SceneCatalog.GetSceneDefForCurrentScene(),"Original Stage.Start or server-begin callback did not complete");
   r.stageProgress.originalStageBegins++;Save();
  }finally{Stage.onServerStageBegin-=onBegin;}
 }
 void ReleaseObjectiveStage(){
  if(!objectiveStage)return;
  if(ownsOriginalStage){Check(NetworkServer.active,"Original Stage requires a live server for teardown");NetworkServer.Destroy(objectiveStageHost);ownsOriginalStage=false;}
  else{Call(objectiveStage,"OnDisable");Destroy(objectiveStageHost);}
  objectiveStage=null;objectiveStageHost=null;
 }
 void TickOriginalStage(){
  if(ownsOriginalStage)return; // Active source prefab receives Unity's own Update.
  if(r==null||!r.teleporterLoop||!objectiveStage||transportingStage||r.stageProgress==null||!string.IsNullOrEmpty(r.stageProgress.error))return;
  try{Call(objectiveStage,"Update");}catch(Exception e){r.stageProgress.error=e.ToString();if(Run.instance)r.stageProgress.stageClearCount=Run.instance.stageClearCount;Save();}
 }
 int IntegratedInventoryCount(){return ItemCatalog.allItemDefs.Sum(x=>worldPlayer.inventory.GetItemCountPermanent(x.itemIndex));}
 ulong PendingStagePlayerExperience(out int count){
  Check(rewardExperience&&ExperienceManager.instance==rewardExperience,"Original XP manager ownership changed before transport");
  var field=typeof(ExperienceManager).GetField("pendingAwards",BindingFlags.NonPublic|BindingFlags.Instance);Check(field!=null,"Original timed XP queue field unavailable");var pending=(IList)field.GetValue(rewardExperience);Check(pending!=null,"Original timed XP queue unavailable");ulong amount=0;count=0;
  foreach(var award in pending){var type=award.GetType();var recipient=type.GetField("recipient",BindingFlags.Public|BindingFlags.Instance);var value=type.GetField("awardAmount",BindingFlags.Public|BindingFlags.Instance);Check(recipient!=null&&value!=null,"Original timed XP award contract changed");if((TeamIndex)recipient.GetValue(award)!=TeamIndex.Player)continue;amount=checked(amount+(ulong)value.GetValue(award));count++;}
  return amount;
 }
 IEnumerator TransportIntegratedStage(NovaInputBridge bridge,float simulationBegan){
  if(string.IsNullOrEmpty(pendingStage))yield break;
  var next=integratedStageConfig.integratedStages.SingleOrDefault(x=>x.name==pendingStage);
  Check(next!=null,"Original next destination has no accepted converted content: "+pendingStage);
  var report=r.stageProgress;var run=Run.instance;var body=worldPlayer;var master=body.master;
  Check(r.objective.bossDefeated&&r.objective.charged&&r.objective.exitFinished&&objectiveStage.completed,"Original stage boss/charge/exit/completion missing before scene transport");
  report.completedBarrels+=r.world.openedBarrels;report.completedChests+=r.world.openedChests;report.completed.Add(stageGeometryScene.name+"|boss-defeated|natural-charge|"+(r.objective.rewardCollected?"post-boss-pickup-collected":"reward-uncollected")+"|original-exit");report.completedObjectives.Add(r.objective);report.moneyBefore=master.money;report.experienceBefore=TeamManager.instance.GetTeamExperience(TeamIndex.Player);report.itemsBefore=IntegratedInventoryCount();
  transportingStage=true;report.transporting=true;r.phase="integrated-stage-transition";Save();bridge.enabled=false;body.inputBank.moveVector=Vector3.zero;
  var beetleGland=body.GetComponent<RoR2.Items.BeetleGlandBodyBehavior>();bool resumeBeetleGland=beetleGland&&beetleGland.enabled;if(resumeBeetleGland)beetleGland.enabled=false;
  if(sourceSlowDirector)sourceSlowDirector.enabled=false;if(rewardDirector)rewardDirector.enabled=false;
  PauseStageMapZones();var motor=body.characterMotor;var solver=motor.Motor;solver.enabled=false;motor.velocity=Vector3.zero;
  CleanupStageBossInstances();
  // The native item can summon a player-owned ally outside the stage director.
  // Retire its body/master before replacing the source navigation graph; its
  // original item behavior may naturally resummon after the new stage loads.
  report.playerSummonsRemoved+=DestroyWholePlayerSummons();
  // Old actors must release their original navigation agents before replacing source graphs.
  CleanupDirectorActors();
  foreach(var projectile in FindObjectsOfType<RoR2.Projectile.ProjectileController>())NetworkServer.Destroy(projectile.gameObject);
  foreach(var instance in objectiveSupportInstances)if(instance)NetworkServer.Destroy(instance);objectiveSupportInstances.Clear();
  foreach(var pickup in EjectionPickups().ToArray())NetworkServer.Destroy(pickup.gameObject);foreach(var droplet in EjectionDroplets().ToArray())NetworkServer.Destroy(droplet.gameObject);
  CleanupWholeStageInteractables();CleanupWorldCommerce();foreach(var obj in worldObjects)if(obj)NetworkServer.Destroy(obj);worldObjects.Clear();worldBarrels.Clear();worldChests.Clear();
  CleanupWholeStagePool();
  if(objectiveHost)NetworkServer.Destroy(objectiveHost);if(objectiveBossDeck)Destroy(objectiveBossDeck);ReleaseObjectiveStage();if(sourceSceneInfoRoot)DeactivateSourceSceneInfo();if(enemySceneHost)Destroy(enemySceneHost);
  yield return null;yield return null;
  // Keep historical values in the plain report, but stop the persistent probe
  // from retaining actor/component wrappers from every completed stage.
  Check(directorActors.All(actor=>!actor.body&&!actor.master&&!actor.model),"Old stage actor observer retained a live source object");
  foreach(var actor in directorActors)actor.report.cleaned=true;
  report.retiredActorObservers+=directorActors.Count;directorActors.Clear();
  report.retiredModelObservers+=worldModels.RemoveAll(model=>!model);
  report.retiredCommerceObservers+=commerceOwned.RemoveAll(obj=>!obj);
  Check(!SceneInfo.instance&&!ClassicStageInfo.instance&&!Stage.instance&&!TeleporterInteraction.instance&&NavigationAgentCount()==0,"Old original scene context survived transition: scene="+(bool)SceneInfo.instance+", stageInfo="+(bool)ClassicStageInfo.instance+", stage="+(bool)Stage.instance+", teleporter="+(bool)TeleporterInteraction.instance+", agents="+NavigationAgentCount());
  // Earned XP can still be in the original timed queue after the exit. Let its
  // normal FixedUpdate settle it before taking the strict transport baseline.
  r.phase="integrated-stage-xp-settlement";report.experienceAtExit=TeamManager.instance.GetTeamExperience(TeamIndex.Player);int pendingCount;report.pendingExperienceAtExit=PendingStagePlayerExperience(out pendingCount);report.pendingExperienceAwardsAtExit=pendingCount;
  float settlementBegan=Time.realtimeSinceStartup,settlementDeadline=settlementBegan+ExperienceManager.maxOrbTravelTime+1;
  while(pendingCount>0&&Time.realtimeSinceStartup<settlementDeadline){yield return null;PendingStagePlayerExperience(out pendingCount);}
  report.experienceSettlementSeconds=Time.realtimeSinceStartup-settlementBegan;Check(pendingCount==0,"Original queued XP did not settle before transport");
  report.experienceBefore=TeamManager.instance.GetTeamExperience(TeamIndex.Player);Check(report.experienceBefore==checked(report.experienceAtExit+report.pendingExperienceAtExit),"Original queued XP settlement accounting failed");Save();
  var old=stageGeometryScene;
  ReturnIntegratedStageEffects(); // Original sceneUnloaded kills pools; release their live loans first.
  ReleaseObjectiveOrbCache(); // Original sceneUnloaded clears its map without releasing leases.
  foreach(var root in old.GetRootGameObjects())if(!stageStaticRoots.Contains(root))SceneManager.MoveGameObjectToScene(root,priorClockScene);
  Check(SceneManager.SetActiveScene(priorClockScene),"Persistent adapter scene missing");
  yield return SceneManager.UnloadSceneAsync(old);foreach(var mat in stageGeometryMaterials)if(mat)Destroy(mat);stageGeometryMaterials.Clear();
  if(stageGeometryBundle){stageGeometryBundle.Unload(true);stageGeometryBundle=null;}
  var geometry=LoadStageGeometry(next.bundle,next.previewCallbacks,next);while(geometry.MoveNext())yield return geometry.Current;
  // Moon activates its original scene objects while loading, after selecting its
  // scene. Unity returns false when reselecting the scene that is already active.
  if(SceneManager.GetActiveScene()!=stageGeometryScene)Check(SceneManager.SetActiveScene(stageGeometryScene),"Actual next active scene selection failed");
  var actualSceneDef=SceneCatalog.GetSceneDefForCurrentScene();report.actualScene=SceneManager.GetActiveScene().name;report.actualSceneDef=actualSceneDef?actualSceneDef.cachedName:"unavailable";report.activeSceneVerified=SceneManager.GetActiveScene()==stageGeometryScene;Save();
  Check(report.activeSceneVerified&&actualSceneDef&&actualSceneDef.cachedName==next.name,"Actual next scene catalog/name mismatch");
  SceneInfo info;
  if(next.moonMission)info=SceneInfo.instance;
  else if(stageSourceObjects)info=ActivateSourceSceneInfo();
  else{enemySceneHost=new GameObject("Owned original next-stage SceneInfo");enemySceneHost.SetActive(false);SceneManager.MoveGameObjectToScene(enemySceneHost,stageGeometryScene);
  info=enemySceneHost.AddComponent<SceneInfo>();typeof(SceneInfo).GetField("groundNodesAsset",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(info,artifactBundle.LoadAsset<NodeGraph>(next.groundGraph));typeof(SceneInfo).GetField("airNodesAsset",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(info,artifactBundle.LoadAsset<NodeGraph>(next.airGraph));enemySceneHost.SetActive(true);}yield return null;
  Check(SceneInfo.instance==info&&info.groundNodes.GetNodeCount()>0&&info.airNodes.GetNodeCount()>0,"Recovered next-stage navigation missing");
  if(stageSourceObjects){r.stage.sourceSceneInfoActive=true;r.stage.sourceStagePopulationActive=ClassicStageInfo.instance==sourceSceneInfoRoot.GetComponent<ClassicStageInfo>()&&ClassicStageInfo.instance.monsterSelection!=null;Check(r.stage.sourceStagePopulationActive,"Original source next-stage population did not initialize");}
  // Explicit temporary entry placement; movement afterward is original motor/state/solver.
  report.entryObservations.Clear();ObserveStageEntry(motor,"before-original-teleport");
  TeleportHelper.TeleportGameObject(body.gameObject,r.stage.spawnPosition);solver.CollidableLayers=LayerIndex.world.mask;solver.StableGroundLayers=LayerIndex.world.mask;solver.SetGroundSolvingActivation(true);solver.ForceUnground();solver.enabled=true;Physics.SyncTransforms();
  ObserveStageEntry(motor,"after-original-teleport");EnableStageMapZones();
  yield return new WaitForFixedUpdate();yield return null;
  float deadline=Time.realtimeSinceStartup+5,observedAt=Time.realtimeSinceStartup;while((!solver.GroundingStatus.IsStableOnGround||!solver.GroundingStatus.GroundCollider||solver.GroundingStatus.GroundCollider.gameObject.scene!=stageGeometryScene)&&Time.realtimeSinceStartup<deadline){if(Time.realtimeSinceStartup-observedAt>=.25f){ObserveStageEntry(motor);observedAt=Time.realtimeSinceStartup;}yield return null;}
  ObserveStageEntry(motor,"settled-or-failed");
  Check(solver.GroundingStatus.IsStableOnGround&&solver.GroundingStatus.GroundCollider&&solver.GroundingStatus.GroundCollider.gameObject.scene==stageGeometryScene,"Next-stage entry does not land on recovered geometry");
  Check(Util.IsPositionWithinMapBounds(solver.TransientPosition),"Original source bounds reject grounded next-stage entry");
  worldPathFollower.Reset();worldLocalNavigator.SetBody(null);worldNavigationBody=null;worldTerrainRecent.Clear();worldTerrainSelectedAt=worldTerrainRecoveryUntil=-100;
  if(automaticDirectorHost)Destroy(automaticDirectorHost);yield return null;
  sourceSlowDirector=null;SelectStageCombatDeck(integratedStageConfig,next.name);automaticDirectorHost=stageSourceObjects?SourceStageDirectorRoot(false):Instantiate(artifactBundle.LoadAsset<GameObject>(integratedStageConfig.enemyDirectorAsset));rewardDirector=automaticDirectorHost.GetComponent<CombatDirector>();rewardDirector.monsterCards=automaticDeck;
  if(stageSourceObjects){sourceSlowDirector.monsterCards=automaticDeck;ObserveSourceSlowDirector(worldPlayer);}else automaticDirectorHost.AddComponent<DirectorCore>();
  var spawningDirector=rewardDirector;spawningDirector.onSpawnedServer.AddListener(obj=>{RecordRewardSpawn(obj);if(currentStageCombatDeck!=null)RecordStageCombatSpawn(obj,worldPlayer,spawningDirector);else RecordDirectorActor(obj,worldPlayer);});automaticDirectorHost.SetActive(true);
  Check(DirectorCore.instance==automaticDirectorHost.GetComponent<DirectorCore>()&&rewardDirector.enabled&&CombatDirector.instancesList.Contains(rewardDirector)&&(!stageSourceObjects||CombatDirector.instancesList.Contains(sourceSlowDirector)),"Next-stage original director missing");
  worldObjective=0;stagePickupBaseline=r.world.pickupMessages;worldLastPress=-1;
  var origin=solver.TransientPosition;var chestSource=artifactBundle.LoadAsset<GameObject>(integratedStageConfig.chestAsset);
  if(r.liveCatalogs==null||next.moonMission){
  foreach(var offset in new[]{new Vector3(2,0,0),new Vector3(-2,0,0),new Vector3(0,0,3),new Vector3(4,0,3),new Vector3(-4,0,3),new Vector3(0,0,-3)}){var obj=CreateWorldInteractable(artifactBundle.LoadAsset<GameObject>(integratedStageConfig.barrelAsset),origin+offset,false);if(obj)worldBarrels.Add(obj.GetComponent<BarrelInteraction>());}
  foreach(var offset in new[]{new Vector3(5,0,0),new Vector3(-5,0,0),new Vector3(0,0,6),new Vector3(6,0,6)}){var obj=CreateWorldInteractable(chestSource,origin+offset,true);if(obj)worldChests.Add(obj.GetComponent<ChestBehavior>());}
  AddEquipmentBarrel(integratedStageConfig,origin);if(!next.moonMission)AddWorldChestBreadth(integratedStageConfig,origin);Check(worldBarrels.Count>=3&&worldChests.Count>=2,"Recovered next-stage layout lacks walkable interactables");r.world.barrels=worldBarrels.Count;r.world.chests=worldChests.Count;
  }
  if(next.moonMission){rewardDirector.enabled=false;var mission=PrepareMoonWorld();while(mission.MoveNext())yield return mission.Current;objectiveStageHost=new GameObject("Owned Moon stage coordinator");objectiveStageHost.SetActive(false);objectiveStageHost.AddComponent<NetworkIdentity>();objectiveStage=objectiveStageHost.AddComponent<Stage>();typeof(Stage).GetProperty("sceneDef").SetValue(objectiveStage,SceneCatalog.GetSceneDefForCurrentScene());Call(objectiveStage,"OnEnable");}
  else{var objective=SpawnStageObjective(integratedStageConfig);while(objective.MoveNext())yield return objective.Current;PrepareWorldCommerce(integratedStageConfig,origin);var population=PopulateWholeStage();while(population.MoveNext())yield return population.Current;var stage=BeginOriginalStage();while(stage.MoveNext())yield return stage.Current;}
  report.moneyAfter=master.money;report.experienceAfter=TeamManager.instance.GetTeamExperience(TeamIndex.Player);report.itemsAfter=IntegratedInventoryCount();
  Check(Run.instance==run&&worldPlayer==body&&body.master==master&&master.GetBody()==body&&body.netId.Value==report.bodyId&&master.netId.Value==report.masterId&&body.hasEffectiveAuthority&&report.itemsAfter==report.itemsBefore&&report.experienceAfter==report.experienceBefore&&report.moneyAfter==report.moneyBefore&&run.stageClearCount==report.completed.Count,"Original run/master/authority/inventory/XP/count continuity failed");
  stageEnteredAt=Time.realtimeSinceStartup-simulationBegan;report.current=next.name;report.transitions++;report.stageClearCount=run.stageClearCount;report.enteredAt=stageEnteredAt;report.transporting=false;pendingStage=null;transportingStage=false;if(resumeBeetleGland&&beetleGland)beetleGland.enabled=true;bridge.enabled=true;r.phase="integrated-world-playing";Save();
 }
 void ReturnIntegratedStageEffects(){
  Check(ownsIntegratedPools,"Stage effect pools have no integrated ownership baseline");
  var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);
  int loans=pools.Values.Sum(pool=>pool.InUseCount());
  foreach(var pool in pools.Values.ToArray())foreach(var effect in pool.InUse.ToArray())pool.ReturnObject(effect);
  if(r.stageProgress!=null)r.stageProgress.effectLoansReturned+=loans;
  Check(pools.Values.All(x=>x.InUseCount()==0),"Owned stage effect loans survived original return callbacks");
 }
 void CleanupStageTransport(){PauseStageMapZones();StopStageMapZoneObservations();if(sourceSceneInfoRoot)DeactivateSourceSceneInfo();if(worldTransport)worldTransport.requested=null;if(NetworkManager.singleton==worldTransport)NetworkManager.singleton=null;if(worldTransportHost)Destroy(worldTransportHost);CleanupCraftableCatalog();CleanupStageSpellCatalog();pendingStage=null;transportingStage=false;if(r.stageProgress!=null)r.stageProgress.cleaned=true;}
}
