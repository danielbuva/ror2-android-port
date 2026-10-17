// Subsystem: session (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareResultsKeyItems, PrepareIntegratedResults (IntegratedResultsSession.Prepare); teardown CleanupIntegratedResults (Dispose).
using System;
using System.Collections.Generic;
using System.IO;
using Path=System.IO.Path;
using Zio;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.ContentManagement;
using RoR2.Stats;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.Networking;

// Original statistics/report generation; owned Android presentation and local run ledger.
public sealed partial class MovementBatchProbe {
 [Serializable] public class IntegratedResultsReport {
  public bool ready,statsRegistered,serverEnding,clientEnding,reportGenerated,reportReloaded,persisted,cleaned;
  public string scope,error,ending,reportFile,ledgerRecovery,ledgerRecoveryError,ledgerRejectedPrimary,initializationStep;public int players,items,stageClearCount,statFields,priorRuns,itemGroupTypes,itemGroupProviders,itemGroups,itemRelationshipTypes,itemRelationshipProviders,itemRelationshipPairs;
  public float seconds,startupCollectionSeconds;public double damageDealt,damageTaken;public ulong kills,stagesCompletedStat;public int stageVisitsStat;public long startupManagedBefore,startupManagedAfter;
 }
 [Serializable] sealed class AndroidRunLedger {public int version=1;public List<AndroidRunEntry> runs=new List<AndroidRunEntry>();}
 [Serializable] sealed class AndroidRunEntry {public string file,ending;public bool win,debugAssisted;public string debugEvidence;public float seconds;public int stages;}
 // Shared with AndroidProfileSession and earned run availability.
 AndroidProfileSaveSystem resultsSaveSystem;AndroidRunLedger resultsLedger;
 PlayerStatsComponent resultsStats;RunReport resultsRunReport;
 IntegratedResultsSession integratedResultsSession;
 IntegratedResultsSession GetIntegratedResultsSession(){if(integratedResultsSession==null)integratedResultsSession=new IntegratedResultsSession(this);return integratedResultsSession;}
 void PrepareResultsKeyItems(){GetIntegratedResultsSession().PrepareResultsKeyItems();}
 void PrepareIntegratedResults(CharacterBody player,SessionConfig cfg){GetIntegratedResultsSession().Prepare(player,cfg);}
 void TickIntegratedResults(){GetIntegratedResultsSession().TickIntegratedResults();}
 void ObserveIntegratedResults(){GetIntegratedResultsSession().ObserveIntegratedResults();}
 void DrawIntegratedResults(){GetIntegratedResultsSession().DrawIntegratedResults();}
 void CleanupIntegratedResults(){GetIntegratedResultsSession().Dispose();}

 // Nested to keep shared profile state and the report private to the coordinator.
 // Key-item setup may precede Prepare; retain the owner after Dispose for partial
 // setup, repeated cleanup and later sessions. Static serializer guards stay static.
 sealed class IntegratedResultsSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  SaveSystem previousResultsSaveSystem;bool ownsResultsSaveSystem;
  static string resultsStatsSignature;static bool resultsSerializersReady;
  readonly Dictionary<FieldInfo,object> resultsEventContext=new Dictionary<FieldInfo,object>();
  Action resultsStatsFixed,resultsStatsProcess;GameObject resultsTemplate;GameObject previousGameOverPrefab;
  Action<Stage> resultsOfflineStageBegin,resultsOfflineStageComplete;readonly HashSet<int> resultsVisitedStages=new HashSet<int>(),resultsCompletedStages=new HashSet<int>();
  GameEndingDef[] previousEndingContent,previousEndingCatalog;string previousReportFolder;
  GameOverController resultsController;Action<Run,GameEndingDef> resultsServerEvent;Action<Run,RunReport> resultsClientEvent;
  string resultsDirectory;bool ownsResultsContext,ownsResultsStats;
  KeyItemDef[] priorResultsKeyItems;string[] priorResultsKeyItemNames;bool ownsResultsKeyItems;
  bool ownsResultsItemGroups;
  bool ownsResultsItemRelationships;ItemRelationshipType[] priorResultsRelationshipTypes;ItemRelationshipProvider[] priorResultsRelationshipProviders;
  public IntegratedResultsSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public void PrepareResultsKeyItems(){
   if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return;
   if(ownsResultsKeyItems){coordinator.Check(KeyItemCatalog.keyItemCount==WholeCatalogComposed.KeyItemDefinitions().Length,"Owned key-item catalog changed");return;}
   priorResultsKeyItems=ContentManager._keyItemDefs;priorResultsKeyItemNames=KeyItemCatalog.keyItemNames;
   var map=(System.Collections.IDictionary)RewardField(typeof(KeyItemCatalog),"keyItemNameToIndex").GetValue(null);
   coordinator.Check(!ownsResultsKeyItems&&(priorResultsKeyItems==null||priorResultsKeyItems.Length==0)&&priorResultsKeyItemNames.Length==0&&map.Count==0,"Unowned key-item statistics catalog");
   var definitions=WholeCatalogComposed.KeyItemDefinitions();coordinator.Check(definitions.Length>0&&definitions.All(def=>def)&&definitions.Select(def=>def.name).Distinct().Count()==definitions.Length,"Original key-item statistics definitions unavailable");
   ownsResultsKeyItems=true;ContentManager._keyItemDefs=Array.Empty<KeyItemDef>();StaticCall(typeof(KeyItemCatalog),"SetKeyItemDefs",new object[]{definitions});
   coordinator.Check(KeyItemCatalog.keyItemCount==definitions.Length&&definitions.All(def=>KeyItemCatalog.GetKeyItemDef(def.keyItemIndex)==def),"Original key-item statistics identity differs");
  }
  void CleanupResultsKeyItems(){if(!ownsResultsKeyItems)return;StaticCall(typeof(KeyItemCatalog),"SetKeyItemDefs",new object[]{Array.Empty<KeyItemDef>()});ContentManager._keyItemDefs=priorResultsKeyItems;KeyItemCatalog.keyItemNames=priorResultsKeyItemNames;ownsResultsKeyItems=false;}
  void PrepareResultsItemGroups(){
   if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return;
   var map=(System.Collections.IDictionary)RewardField(typeof(ItemCatalog),"itemGroups").GetValue(null);coordinator.Check(!ownsResultsItemGroups&&map.Count==0,"Unowned item-group catalog");
   var types=WholeCatalogComposed.ItemGroupTypes();var providers=WholeCatalogComposed.ItemGroupProviders();
   var fields=typeof(DLC4Content.ItemGroupTypes).GetFields(BindingFlags.Public|BindingFlags.Static);
   coordinator.Check(types.Length>0&&providers.Length>0&&types.Length==fields.Length&&types.All(type=>type)&&types.Select(type=>type.name).Distinct().Count()==types.Length&&providers.All(provider=>provider&&types.Contains(provider.groupType)&&provider.groups!=null&&provider.groups.All(group=>group.items!=null)),"Original item-group metadata missing or ambiguous");
   foreach(var field in fields)coordinator.BindEnemyDefinition(typeof(DLC4Content.ItemGroupTypes),field.Name,types.Single(type=>type.name==field.Name));
   // Preserve shipped group slots, including source-null item references; never invent membership.
   ownsResultsItemGroups=true;StaticCall(typeof(ItemCatalog),"SetItemGroups",new object[]{providers});
   coordinator.Check(types.All(type=>ItemCatalog.GetItemGroupsForGroupType(type).Length==providers.Where(provider=>provider.groupType==type).Sum(provider=>provider.groups.Count(group=>group.items.Length>0))),"Original item-group registration differs");
   coordinator.r.results.itemGroupTypes=types.Length;coordinator.r.results.itemGroupProviders=providers.Length;coordinator.r.results.itemGroups=providers.Sum(provider=>provider.groups.Length);
  }
  void CleanupResultsItemGroups(){if(!ownsResultsItemGroups)return;StaticCall(typeof(ItemCatalog),"SetItemGroups",new object[]{Array.Empty<ItemGroupProvider>()});ownsResultsItemGroups=false;}
  void PrepareResultsItemRelationships(){
   if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return;
   var map=(System.Collections.IDictionary)RewardField(typeof(ItemCatalog),"itemRelationships").GetValue(null);
   var typeField=typeof(ContentManager).GetField("_itemRelationshipTypes",BindingFlags.NonPublic|BindingFlags.Static);
   var providerField=typeof(ContentManager).GetField("_itemRelationshipProviders",BindingFlags.NonPublic|BindingFlags.Static);
   coordinator.Check(typeField!=null&&providerField!=null&&!ownsResultsItemRelationships&&map.Count==0,"Unowned item-relationship catalog");
   priorResultsRelationshipTypes=(ItemRelationshipType[])typeField.GetValue(null);priorResultsRelationshipProviders=(ItemRelationshipProvider[])providerField.GetValue(null);
   coordinator.Check((priorResultsRelationshipTypes==null||priorResultsRelationshipTypes.Length==0)&&(priorResultsRelationshipProviders==null||priorResultsRelationshipProviders.Length==0),"Existing item-relationship content owner");
   var types=WholeCatalogComposed.CategoryFamily(AddressablesLabels.itemRelationshipType,Array.Empty<ItemRelationshipType>());
   var providers=WholeCatalogComposed.CategoryFamily(AddressablesLabels.itemRelationshipProvider,Array.Empty<ItemRelationshipProvider>());
   coordinator.Check(types.Length==1&&providers.Length==1&&types[0]&&providers[0]&&providers[0].relationshipType==types[0]&&providers[0].relationships!=null&&providers[0].relationships.Length>0&&providers[0].relationships.All(pair=>pair.itemDef1&&pair.itemDef2&&ItemCatalog.GetItemDef(pair.itemDef1.itemIndex)==pair.itemDef1&&ItemCatalog.GetItemDef(pair.itemDef2.itemIndex)==pair.itemDef2),"Original item relationship source or item identity differs");
   WholeCatalogComposed.PopulateDefinitionFields("ItemRelationshipTypes",types);
   ownsResultsItemRelationships=true;typeField.SetValue(null,types);providerField.SetValue(null,providers);
   StaticCall(typeof(ItemCatalog),"SetItemRelationships",new object[]{providers});
   var pairs=ItemCatalog.GetItemPairsForRelationship(types[0]);
   coordinator.Check(map.Count==types.Length&&pairs.Length==providers[0].relationships.Distinct().Count(),"Original item relationship registration differs");
   coordinator.r.results.itemRelationshipTypes=types.Length;coordinator.r.results.itemRelationshipProviders=providers.Length;coordinator.r.results.itemRelationshipPairs=pairs.Length;
  }
  void CleanupResultsItemRelationships(){
   if(!ownsResultsItemRelationships)return;
   StaticCall(typeof(ItemCatalog),"SetItemRelationships",new object[]{Array.Empty<ItemRelationshipProvider>()});
   typeof(ContentManager).GetField("_itemRelationshipTypes",BindingFlags.NonPublic|BindingFlags.Static).SetValue(null,priorResultsRelationshipTypes);
   typeof(ContentManager).GetField("_itemRelationshipProviders",BindingFlags.NonPublic|BindingFlags.Static).SetValue(null,priorResultsRelationshipProviders);
   priorResultsRelationshipTypes=null;priorResultsRelationshipProviders=null;ownsResultsItemRelationships=false;
  }
  void RememberResultsEvent(Type type,string name){var field=type.GetField(name,BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);coordinator.Check(field!=null,"Original results event missing: "+type.Name+"/"+name);resultsEventContext[field]=field.GetValue(null);}
  void ReleaseResultsEvents(){
   // StatManager.Init adds static handlers. Replaying the whole pre-init delegate
   // snapshot can resurrect a CharacterMaster already destroyed during the run.
   var stats=typeof(PlayerStatsComponent).Assembly.GetType("RoR2.Stats.StatManager",true);
   foreach(var entry in resultsEventContext){
    var current=entry.Key.GetValue(null) as Delegate;var prior=entry.Value as Delegate;
    if(current==null)continue;
    var priorHandlers=prior==null?Array.Empty<Delegate>():prior.GetInvocationList();
    foreach(var handler in current.GetInvocationList())if(handler.Method.DeclaringType==stats&&!priorHandlers.Contains(handler))current=Delegate.Remove(current,handler);
    entry.Key.SetValue(null,current);
   }
   resultsEventContext.Clear();
  }
  void ResultsStep(string value){coordinator.r.results.initializationStep=value;coordinator.Save();}
  void RecordOfflineStageBegin(Stage stage){
   if(!stage||!coordinator.resultsStats||coordinator.directorPlayer.isConnected)return;
   coordinator.Check(!coordinator.directorPlayer.networkUser&&coordinator.resultsStats.playerCharacterMasterController==coordinator.directorPlayer&&coordinator.resultsStats.currentStats!=null,"Offline stage statistics lost the owned local player");
   if(!resultsVisitedStages.Add(stage.GetInstanceID()))return;
   var definition=PerStageStatDef.totalTimesVisited.FindStatDef(stage.sceneDef?stage.sceneDef.baseSceneName:string.Empty);
   if(definition!=null)coordinator.resultsStats.currentStats.PushStatValue(definition,1uL);
   coordinator.r.results.stageVisitsStat=resultsVisitedStages.Count;
  }
  void RecordOfflineStageComplete(Stage stage){
   if(!stage||!coordinator.resultsStats||coordinator.directorPlayer.isConnected)return;
   coordinator.Check(!coordinator.directorPlayer.networkUser&&coordinator.resultsStats.playerCharacterMasterController==coordinator.directorPlayer&&coordinator.resultsStats.currentStats!=null&&SceneInfo.instance,"Offline stage completion lacks its original local context");
   if(!resultsCompletedStages.Add(stage.GetInstanceID()))return;
   var sheet=coordinator.resultsStats.currentStats;
   if(SceneInfo.instance.countsAsStage){sheet.PushStatValue(StatDef.totalStagesCompleted,1uL);sheet.PushStatValue(StatDef.highestStagesCompleted,sheet.GetStatValueULong(StatDef.totalStagesCompleted));}
   var definition=PerStageStatDef.totalTimesCleared.FindStatDef(stage.sceneDef?stage.sceneDef.baseSceneName:string.Empty);
   if(definition!=null)sheet.PushStatValue(definition,1uL);
   coordinator.r.results.stagesCompletedStat=sheet.GetStatValueULong(StatDef.totalStagesCompleted);
  }
  public void Prepare(CharacterBody player,SessionConfig cfg){
   if(!cfg.integratedResults)return;
   coordinator.r.results=new IntegratedResultsReport{scope="Original statistics, genuine Run.BeginGameOver/GameOverController/RunReport and client ending. Owned Android result presentation and run ledger; stock cutscene, Steam profiles, authentication, achievements and lunar awards unavailable."};coordinator.r.phase="integrated-results-context";coordinator.Save();
   coordinator.Check(NetworkServer.active&&coordinator.activeBodyClient.isConnected&&!GameOverController.instance&&PlayerStatsComponent.instancesList.Count==0,"Unowned results context");
   previousResultsSaveSystem=PlatformSystems.saveSystem;coordinator.Check(previousResultsSaveSystem==null,"Existing platform save-system context");coordinator.resultsSaveSystem=new AndroidProfileSaveSystem();PlatformSystems.saveSystem=coordinator.resultsSaveSystem;ownsResultsSaveSystem=true;
   // Current StatDef adds PerKeyItemStatDef. Register original metadata before its fixed buffers;
   // this grants no key item and does not start its pickup/platform simulation.
   ResultsStep("key-item-statistics");
   // Full-catalog loading leaves a large transient managed graph. On this device
   // an unlucky collection schedule let the process exceed its memory limit here.
   // Reclaim only at this loading boundary, before native statistics allocate.
   coordinator.r.results.startupManagedBefore=Profiler.GetMonoUsedSizeLong();
   if(coordinator.r.results.startupManagedBefore>1073741824L&&UnityEngine.Scripting.GarbageCollector.GCMode!=UnityEngine.Scripting.GarbageCollector.Mode.Disabled){
    var began=Time.realtimeSinceStartup;GC.Collect();coordinator.r.results.startupCollectionSeconds=Time.realtimeSinceStartup-began;
   }
   coordinator.r.results.startupManagedAfter=Profiler.GetMonoUsedSizeLong();coordinator.Save();
   PrepareResultsKeyItems();
   var signature=string.Join("|",Enumerable.Range(0,BodyCatalog.bodyCount).Select(x=>BodyCatalog.GetBodyName((BodyIndex)x)))+"/"+string.Join("|",ItemCatalog.allItemDefs.Select(x=>x.name))+"/"+string.Join("|",coordinator.clockSceneDefs.Select(x=>x.cachedName))+"/"+string.Join("|",KeyItemCatalog.keyItemNames);
   if(resultsStatsSignature==null){StaticCall(typeof(StatDef),"Init");StaticCall(typeof(StatSheet),"Init");resultsStatsSignature=signature;}else {coordinator.Check(resultsStatsSignature==signature,"Restart original statistics catalog changed");coordinator.resultsSaveSystem.isXmlReady=true;}
   ResultsStep("player-statistics");coordinator.resultsStats=player.master.GetComponent<PlayerStatsComponent>();coordinator.Check(coordinator.resultsStats&&coordinator.resultsStats.currentStats==null&&!coordinator.resultsStats.gameObject.activeInHierarchy,"Original inactive player statistics scope changed");Call(coordinator.resultsStats,"Awake");ownsResultsStats=true;
   coordinator.Check(coordinator.resultsStats.characterMaster==player.master&&coordinator.resultsStats.playerCharacterMasterController==coordinator.directorPlayer&&coordinator.resultsStats.currentStats!=null&&PlayerStatsComponent.instancesList.Contains(coordinator.resultsStats)&&!coordinator.directorPlayer.networkUser,"Original player statistics identity missing");
   foreach(var name in new[]{"onServerDamageDealt","onCharacterDeathServer","onServerCharacterExecuted","onCharacterPickupItem"})RememberResultsEvent(typeof(GlobalEventManager),name);
   RememberResultsEvent(typeof(HealthComponent),"onCharacterHealServer");foreach(var name in new[]{"onPlayerFirstCreatedServer","onServerGameOver"})RememberResultsEvent(typeof(Run),name);
   foreach(var name in new[]{"onServerStageComplete","onServerStageBegin"})RememberResultsEvent(typeof(Stage),name);
   RememberResultsEvent(typeof(Inventory),"onServerItemGiven");RememberResultsEvent(typeof(RoR2Application),"onFixedUpdate");RememberResultsEvent(typeof(EquipmentSlot),"onServerEquipmentActivated");RememberResultsEvent(typeof(InfiniteTowerRun),"onWaveInitialized");RememberResultsEvent(typeof(MasterSummon),"onServerMasterSummonGlobal");
   RememberResultsEvent(typeof(KeyItemSlot),"onServerKeyItemActivated");
   ResultsStep("statistics-callbacks");ownsResultsContext=true;var statManager=typeof(PlayerStatsComponent).Assembly.GetType("RoR2.Stats.StatManager",true);StaticCall(statManager,"Init");resultsStatsProcess=(Action)Delegate.CreateDelegate(typeof(Action),statManager.GetMethod("ForceUpdate",BindingFlags.Public|BindingFlags.Static));resultsStatsFixed=(Action)Delegate.CreateDelegate(typeof(Action),coordinator.resultsStats,typeof(PlayerStatsComponent).GetMethod("FixedUpdate",BindingFlags.Instance|BindingFlags.NonPublic));
   // Stock StatManager gates stage counters on NetworkUser connectivity. This
   // owned offline player has real server stage events but no platform user.
   resultsOfflineStageBegin=RecordOfflineStageBegin;resultsOfflineStageComplete=RecordOfflineStageComplete;
   Stage.onServerStageBegin+=resultsOfflineStageBegin;Stage.onServerStageComplete+=resultsOfflineStageComplete;
   if(Stage.instance)RecordOfflineStageBegin(Stage.instance);
   ResultsStep("ending-catalog");previousEndingContent=ContentManager._gameEndingDefs;previousEndingCatalog=(GameEndingDef[])RewardField(typeof(GameEndingCatalog),"gameEndingDefs").GetValue(null);
   coordinator.Check(GameEndingCatalog.endingCount==0,"Unowned original ending catalog");var endings=cfg.resultsEndingAssets.Select(x=>coordinator.artifactBundle.LoadAsset<GameEndingDef>(x)).ToArray();coordinator.Check(endings.Length>=2&&endings.All(x=>x)&&endings.Any(x=>x.cachedName=="MainEnding"&&x.isWin),"Original game ending definitions missing");ContentManager._gameEndingDefs=endings;StaticCall(typeof(GameEndingCatalog),"Init");
   // The composed catalog previously used SetItemDefs, which does not register the
   // original ItemIndex[] XML rules. Run the source initializer with the exact owned
   // definitions; keep content roots, relationships and prior availability scoped.
   ResultsStep("item-xml");if(HGXml.SerializationRules<ItemIndex[]>.defaultRules==null){
    var itemDefs=ItemCatalog.allItemDefs.ToArray();var previousItems=ContentManager._itemDefs;var providersField=typeof(ContentManager).GetField("_itemRelationshipProviders",BindingFlags.NonPublic|BindingFlags.Static);var previousProviders=providersField.GetValue(null);var previousAvailability=ItemCatalog.availability;
    var previousGroups=ContentManager._itemGroupProviders;
    var groups=(System.Collections.IDictionary)RewardField(typeof(ItemCatalog),"itemGroups").GetValue(null);
    var relationships=(System.Collections.IDictionary)typeof(ItemCatalog).GetField("itemRelationships",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);coordinator.Check(relationships.Count==0&&groups.Count==0&&providersField!=null,"Unowned item relationships/groups during original XML initialization");
    try{ContentManager._itemDefs=itemDefs;providersField.SetValue(null,Array.Empty<ItemRelationshipProvider>());ContentManager._itemGroupProviders=Array.Empty<ItemGroupProvider>();StaticCall(typeof(ItemCatalog),"Init");coordinator.Check(ItemCatalog.allItemDefs.SequenceEqual(itemDefs)&&relationships.Count==0&&groups.Count==0&&HGXml.SerializationRules<ItemIndex[]>.defaultRules!=null,"Original item XML/catalog initialization differs");}
    finally{ContentManager._itemDefs=previousItems;providersField.SetValue(null,previousProviders);ContentManager._itemGroupProviders=previousGroups;ItemCatalog.availability=previousAvailability;}
   }
   ResultsStep("item-groups");PrepareResultsItemGroups();ResultsStep("item-relationships");PrepareResultsItemRelationships();
   ResultsStep("report-xml");var folder=RewardField(typeof(RunReport),"runReportsFolder");coordinator.Check(folder!=null,"Original report-folder field absent");previousReportFolder=(string)folder.GetValue(null);if(!resultsSerializersReady){StaticCall(typeof(RunReport),"Init");resultsSerializersReady=true;}
   resultsDirectory=Path.Combine(Application.persistentDataPath,"offline-run-results-v1");Directory.CreateDirectory(resultsDirectory);folder.SetValue(null,resultsDirectory+Path.DirectorySeparatorChar);LoadAndroidRunLedger();coordinator.r.results.priorRuns=coordinator.resultsLedger.runs.Count;
   ResultsStep("android-profile");coordinator.PrepareAndroidProfile(player);
   // GameOverController.Awake creates RunReport, whose RuleBook requires the
   // native default-value metadata. This applies no Run rules or availability.
   ResultsStep("rule-metadata");coordinator.PrepareObjectiveRuleCatalog();
   // Disabled stock cutscene/vote/UI scheduling is an explicit Android presentation adapter.
   // The unchanged original ending method still creates its controller and genuine report.
   ResultsStep("ending-template");resultsTemplate=new GameObject("Owned Android original result template");resultsTemplate.SetActive(false);resultsTemplate.AddComponent<NetworkIdentity>();var fsm=resultsTemplate.AddComponent<EntityStateMachine>();fsm.customName="Main";fsm.enabled=false;
   var vote=resultsTemplate.AddComponent<VoteController>();vote.enabled=false;var controller=resultsTemplate.AddComponent<GameOverController>();controller.enabled=false;resultsTemplate.SetActive(true);
   coordinator.Check(controller.runReport!=null,"Original result template Awake did not create its RunReport");coordinator.Check(!GameOverController.instance,"Disabled Android result template activated stock flow");previousGameOverPrefab=Run.instance.gameOverPrefab;Run.instance.gameOverPrefab=resultsTemplate;
   resultsServerEvent=(run,ending)=>{if(run!=Run.instance)return;var created=FindObjectsOfType<GameOverController>().Where(x=>x.gameObject!=resultsTemplate&&x.runReport!=null&&x.runReport.gameEnding==ending).ToArray();coordinator.Check(created.Length==1,"Original generated ending controller/report missing");resultsController=created[0];coordinator.resultsRunReport=resultsController.runReport;resultsController.enabled=true;coordinator.r.results.serverEnding=true;coordinator.r.results.reportGenerated=true;coordinator.r.results.ending=ending.cachedName;coordinator.Save();};
   resultsClientEvent=(run,report)=>{if(run!=Run.instance)return;coordinator.Check(coordinator.resultsRunReport!=null&&report.gameEnding==coordinator.resultsRunReport.gameEnding&&report.playerInfoCount==coordinator.resultsRunReport.playerInfoCount,"Original client ending/report differs");coordinator.r.results.clientEnding=true;coordinator.Save();};Run.onServerGameOver+=resultsServerEvent;Run.onClientGameOverGlobal+=resultsClientEvent;
   ResultsStep("run-identity");if(Run.instance.GetUniqueId()==Guid.Empty){Run.instance.Network_uniqueId=(RoR2.Networking.NetworkGuid)Guid.NewGuid();Run.instance.NetworkstartTimeUtc=(RoR2.Networking.NetworkDateTime)DateTime.UtcNow;}
   Run.instance.isRunning=true;coordinator.r.results.statsRegistered=true;coordinator.r.results.statFields=coordinator.resultsStats.currentStats.fields.Length;coordinator.r.results.ready=true;coordinator.Save();
  }
  public void TickIntegratedResults(){
   if(coordinator.r==null||coordinator.r.results==null||!coordinator.r.results.ready||resultsStatsFixed==null||!string.IsNullOrEmpty(coordinator.r.results.error))return;
   try{resultsStatsFixed();resultsStatsProcess();if(coordinator.resultsSaveSystem.local!=null&&coordinator.resultsSaveSystem.local.profile.saveRequestPending)coordinator.resultsSaveSystem.local.Save();}catch(Exception e){coordinator.r.results.error=e.ToString();resultsStatsFixed=null;coordinator.Save();}
  }
  public void ObserveIntegratedResults(){
   if(coordinator.r.results==null||!coordinator.r.results.ready)return;var report=coordinator.r.results;
   coordinator.Check(string.IsNullOrEmpty(report.error),"Original integrated statistics failed: "+report.error);
   report.damageDealt=coordinator.resultsStats.currentStats.GetStatValueULong(StatDef.totalDamageDealt);report.damageTaken=coordinator.resultsStats.currentStats.GetStatValueULong(StatDef.totalDamageTaken);report.kills=coordinator.resultsStats.currentStats.GetStatValueULong(StatDef.totalKills);report.stagesCompletedStat=coordinator.resultsStats.currentStats.GetStatValueULong(StatDef.totalStagesCompleted);
   if(!report.serverEnding||!report.clientEnding||report.persisted)return;
   coordinator.Check(Run.instance.isGameOverServer&&!Run.instance.isRunning&&resultsController&&resultsController.netId.Value!=0&&coordinator.resultsRunReport!=null&&coordinator.resultsRunReport.playerInfoCount==1&&coordinator.resultsRunReport.GetPlayerInfo(0).master==coordinator.resultsStats.characterMaster,"Original final report/ending accounting incomplete");
   report.players=coordinator.resultsRunReport.playerInfoCount;report.items=coordinator.resultsRunReport.GetPlayerInfo(0).itemAcquisitionOrder.Length;report.seconds=coordinator.resultsRunReport.runStopwatchValue;report.stageClearCount=Run.instance.stageClearCount;
   var file="run-"+coordinator.resultsRunReport.runGuid.ToString("N");RunReport.ToXml(new System.Xml.Linq.XElement("RunReport"),coordinator.resultsRunReport);coordinator.Check(RunReport.Save(coordinator.resultsRunReport,file),"Original Android result save failed");var loaded=RunReport.Load(file);
   coordinator.Check(loaded!=null&&loaded.gameEnding==coordinator.resultsRunReport.gameEnding&&loaded.seed==coordinator.resultsRunReport.seed&&loaded.playerInfoCount==report.players&&loaded.GetPlayerInfo(0).bodyIndex==coordinator.resultsRunReport.GetPlayerInfo(0).bodyIndex&&loaded.GetPlayerInfo(0).itemStacks.SequenceEqual(coordinator.resultsRunReport.GetPlayerInfo(0).itemStacks)&&loaded.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalKills)==coordinator.resultsRunReport.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalKills)&&loaded.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageDealt)==coordinator.resultsRunReport.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageDealt)&&loaded.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageTaken)==coordinator.resultsRunReport.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageTaken)&&Mathf.Abs(loaded.runStopwatchValue-report.seconds)<.01f,"Original result XML round trip differs");
   report.reportFile=file+".xml";report.reportReloaded=true;
   bool assisted=coordinator.r.debugAcceleration!=null&&coordinator.r.debugAcceleration.everAssisted;string debugEvidence=assisted?file+".debug.json":null;
   if(assisted)File.WriteAllText(Path.Combine(resultsDirectory,debugEvidence),JsonUtility.ToJson(coordinator.r.debugAcceleration,true));
   if(!coordinator.resultsLedger.runs.Any(x=>x.file==report.reportFile)){coordinator.resultsLedger.runs.Add(new AndroidRunEntry{file=report.reportFile,ending=report.ending,win=coordinator.resultsRunReport.gameEnding.isWin,seconds=report.seconds,stages=report.stageClearCount,debugAssisted=assisted,debugEvidence=debugEvidence});SaveAndroidRunLedger();}
   coordinator.PersistAndroidProfileResult(assisted);report.persisted=true;coordinator.Save();
  }
  void LoadAndroidRunLedger(){
   var path=Path.Combine(resultsDirectory,"profile.json");var backup=path+".backup";coordinator.resultsLedger=new AndroidRunLedger();
   bool hasPrimary=File.Exists(path);
   if(hasPrimary){try{coordinator.resultsLedger=ReadAndroidRunLedger(path);return;}catch(Exception error){coordinator.r.results.ledgerRecoveryError=error.GetType().Name;}}
   else if(!File.Exists(backup))return;
   // Validate before moving any generation. Retain the rejected primary and the
   // valid backup; a later save must never replace that backup with corrupt data.
   var recovered=ReadAndroidRunLedger(backup);var pending=path+".pending";
   File.WriteAllText(pending,JsonUtility.ToJson(recovered,true));ReadAndroidRunLedger(pending);
   if(hasPrimary){var rejected=path+".rejected-"+Guid.NewGuid().ToString("N");File.Move(path,rejected);coordinator.r.results.ledgerRejectedPrimary=Path.GetFileName(rejected);}
   File.Move(pending,path);coordinator.resultsLedger=ReadAndroidRunLedger(path);coordinator.r.results.ledgerRecovery="validated-backup";
  }
  static void ValidateAndroidRunLedger(bool valid,string message){if(!valid)throw new InvalidDataException(message);}
  AndroidRunLedger ReadAndroidRunLedger(string path){var value=JsonUtility.FromJson<AndroidRunLedger>(File.ReadAllText(path));ValidateAndroidRunLedger(value!=null&&value.version==1&&value.runs!=null,"Android run ledger schema invalid");foreach(var entry in value.runs)ValidateAndroidRunLedger(entry!=null&&entry.file==Path.GetFileName(entry.file)&&entry.file.StartsWith("run-")&&entry.file.EndsWith(".xml")&&File.Exists(Path.Combine(resultsDirectory,entry.file)),"Android run ledger references a missing result");foreach(var entry in value.runs)if(entry.debugAssisted){ValidateAndroidRunLedger(entry.debugEvidence==Path.ChangeExtension(entry.file,".debug.json")&&File.Exists(Path.Combine(resultsDirectory,entry.debugEvidence)),"Assisted result lacks its owned debug evidence");var debug=JsonUtility.FromJson<DebugAccelerationReport>(File.ReadAllText(Path.Combine(resultsDirectory,entry.debugEvidence)));ValidateAndroidRunLedger(debug!=null&&debug.version==1&&debug.everAssisted&&!debug.normalGameAcceptanceEligible,"Assisted ledger evidence claims normal acceptance");}return value;}
  void SaveAndroidRunLedger(){var path=Path.Combine(resultsDirectory,"profile.json");var pending=path+".pending";File.WriteAllText(pending,JsonUtility.ToJson(coordinator.resultsLedger,true));ReadAndroidRunLedger(pending);if(File.Exists(path))File.Replace(pending,path,path+".backup");else File.Move(pending,path);var saved=ReadAndroidRunLedger(path);coordinator.Check(saved.runs.Count==coordinator.resultsLedger.runs.Count,"Android run ledger write did not persist");}
  public void DrawIntegratedResults(){
   var report=coordinator.r.results;var style=new GUIStyle(GUI.skin.label){fontSize=25,wordWrap=false};
   GUI.Box(new Rect(12,45,880,330),"Offline run result");
   var title=coordinator.resultsRunReport!=null&&coordinator.resultsRunReport.gameEnding&&coordinator.resultsRunReport.gameEnding.isWin?"Victory":"Run ended";
   bool assisted=coordinator.r.debugAcceleration!=null&&coordinator.r.debugAcceleration.everAssisted;
   if(coordinator.r.freePlay&&report.persisted){if(coordinator.r.phase=="commando-defeated"&&GUI.Button(new Rect(32,390,350,60),"Restart run (A)"))coordinator.RequestWorldRestart();if(GUI.Button(new Rect(410,390,400,60),coordinator.r.phase=="commando-defeated"?"Return to menu":"Return to menu (A)"))coordinator.RequestResultsMenu();}
   var lines=new List<string>{title};
   if(assisted)lines.Add("DEBUG ASSISTED — not eligible for normal-game acceptance");
   lines.Add("Original stages cleared: "+report.stageClearCount+"   Time: "+report.seconds.ToString("F0")+"s");
   lines.Add("Kills: "+report.kills+"   Damage dealt: "+report.damageDealt.ToString("F0"));
   lines.Add(report.persisted?"Original report saved on this Android device":"Saving original report…");
   lines.Add(coordinator.r.profile!=null&&coordinator.r.profile.ready?(coordinator.r.profile.assistedExcluded?"Assisted result excluded from Android profile":"Android profile saved · "+coordinator.r.profile.appliedRuns+" genuine results"):"Android profile unavailable");
   lines.Add("Stock cutscene and Steam/cloud profiles unavailable");
   for(int i=0;i<lines.Count;i++)GUI.Label(new Rect(32,78+i*40,840,38),lines[i],style);
  }
  public void Dispose(){
   resultsStatsFixed=null;
   if(resultsOfflineStageBegin!=null){Stage.onServerStageBegin-=resultsOfflineStageBegin;resultsOfflineStageBegin=null;}
   if(resultsOfflineStageComplete!=null){Stage.onServerStageComplete-=resultsOfflineStageComplete;resultsOfflineStageComplete=null;}
   resultsVisitedStages.Clear();resultsCompletedStages.Clear();
   coordinator.CleanupAndroidProfile();
   if(ownsResultsSaveSystem){coordinator.Check(ReferenceEquals(PlatformSystems.saveSystem,coordinator.resultsSaveSystem),"Results save-system boundary ownership changed");PlatformSystems.saveSystem=previousResultsSaveSystem;ownsResultsSaveSystem=false;}
   if(!ownsResultsContext){if(ownsResultsStats&&coordinator.resultsStats){Call(coordinator.resultsStats,"OnDestroy");ownsResultsStats=false;}ReleaseResultsEvents();CleanupResultsItemRelationships();CleanupResultsItemGroups();CleanupResultsKeyItems();if(coordinator.r.results!=null)coordinator.r.results.cleaned=true;return;}
   Run.onServerGameOver-=resultsServerEvent;Run.onClientGameOverGlobal-=resultsClientEvent;
   if(Run.instance)Run.instance.gameOverPrefab=previousGameOverPrefab;
   if(resultsController)NetworkServer.Destroy(resultsController.gameObject);if(resultsTemplate)Destroy(resultsTemplate);
   if(ownsResultsStats&&coordinator.resultsStats){Call(coordinator.resultsStats,"OnDestroy");ownsResultsStats=false;}
   ReleaseResultsEvents();
   ContentManager._gameEndingDefs=previousEndingContent;StaticCall(typeof(GameEndingCatalog),"SetGameEndingDefs",new object[]{previousEndingCatalog});typeof(RunReport).GetField("runReportsFolder",BindingFlags.Static|BindingFlags.NonPublic).SetValue(null,previousReportFolder);
   CleanupResultsItemRelationships();CleanupResultsItemGroups();CleanupResultsKeyItems();ownsResultsContext=false;if(coordinator.r.results!=null)coordinator.r.results.cleaned=true;
  }
 }
}
