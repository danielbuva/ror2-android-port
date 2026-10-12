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
using UnityEngine.Networking;

// Original statistics/report generation; owned Android presentation and local run ledger.
public sealed partial class MovementBatchProbe {
 [Serializable] public class IntegratedResultsReport {
  public bool ready,statsRegistered,serverEnding,clientEnding,reportGenerated,reportReloaded,persisted,cleaned;
  public string scope,error,ending,reportFile,ledgerRecovery,ledgerRecoveryError,ledgerRejectedPrimary,initializationStep;public int players,items,stageClearCount,statFields,priorRuns,itemGroupTypes,itemGroupProviders,itemGroups;
  public float seconds;public double damageDealt,damageTaken;public ulong kills;
 }
 [Serializable] sealed class AndroidRunLedger {public int version=1;public List<AndroidRunEntry> runs=new List<AndroidRunEntry>();}
 [Serializable] sealed class AndroidRunEntry {public string file,ending;public bool win,debugAssisted;public string debugEvidence;public float seconds;public int stages;}
 sealed class UnavailableProfileSaveSystem:SaveSystem {
  static Exception Unavailable(){return new NotSupportedException("Stock profile operations unavailable in the composed Android run; original RunReport and owned local results are separate.");}
  protected override void ProcessFileOutputQueue(){throw Unavailable();}
  protected override void StartSave(UserProfile profile,bool blocking){throw Unavailable();}
  protected override LoadUserProfileOperationResult LoadUserProfileFromDisk(IFileSystem files,UPath path){throw Unavailable();}
  public override void InitializeSaveSystem(){throw Unavailable();}
  public override void LoadInitialData(){throw Unavailable();}
  public override void LoadUserProfiles(){throw Unavailable();}
  public override UserProfile LoadPrimaryProfile(){return null;}
  public override string GetPlatformUsernameOrDefault(string defaultName){return defaultName;}
  public override UserProfile CreateProfile(IFileSystem files,string name,ulong platformUserID=0){throw Unavailable();}
  public override void SaveHistory(byte[] data,string name){throw Unavailable();}
  public override Dictionary<string,byte[]> LoadHistory(){throw Unavailable();}
 }
 SaveSystem previousResultsSaveSystem;UnavailableProfileSaveSystem resultsSaveSystem;bool ownsResultsSaveSystem;
 static string resultsStatsSignature;static bool resultsSerializersReady;
 readonly Dictionary<FieldInfo,object> resultsEventContext=new Dictionary<FieldInfo,object>();
 PlayerStatsComponent resultsStats;Action resultsStatsFixed,resultsStatsProcess;GameObject resultsTemplate;GameObject previousGameOverPrefab;
 GameEndingDef[] previousEndingContent,previousEndingCatalog;string previousReportFolder;
 RunReport resultsRunReport;GameOverController resultsController;Action<Run,GameEndingDef> resultsServerEvent;Action<Run,RunReport> resultsClientEvent;
 string resultsDirectory;AndroidRunLedger resultsLedger;bool ownsResultsContext,ownsResultsStats;
 KeyItemDef[] priorResultsKeyItems;string[] priorResultsKeyItemNames;bool ownsResultsKeyItems;
 void PrepareResultsKeyItems(){
  if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return;
  priorResultsKeyItems=ContentManager._keyItemDefs;priorResultsKeyItemNames=KeyItemCatalog.keyItemNames;
  var map=(System.Collections.IDictionary)RewardField(typeof(KeyItemCatalog),"keyItemNameToIndex").GetValue(null);
  Check(!ownsResultsKeyItems&&(priorResultsKeyItems==null||priorResultsKeyItems.Length==0)&&priorResultsKeyItemNames.Length==0&&map.Count==0,"Unowned key-item statistics catalog");
  var definitions=WholeCatalogComposed.KeyItemDefinitions();Check(definitions.Length>0&&definitions.All(def=>def)&&definitions.Select(def=>def.name).Distinct().Count()==definitions.Length,"Original key-item statistics definitions unavailable");
  ownsResultsKeyItems=true;ContentManager._keyItemDefs=Array.Empty<KeyItemDef>();StaticCall(typeof(KeyItemCatalog),"SetKeyItemDefs",new object[]{definitions});
  Check(KeyItemCatalog.keyItemCount==definitions.Length&&definitions.All(def=>KeyItemCatalog.GetKeyItemDef(def.keyItemIndex)==def),"Original key-item statistics identity differs");
 }
 void CleanupResultsKeyItems(){if(!ownsResultsKeyItems)return;StaticCall(typeof(KeyItemCatalog),"SetKeyItemDefs",new object[]{Array.Empty<KeyItemDef>()});ContentManager._keyItemDefs=priorResultsKeyItems;KeyItemCatalog.keyItemNames=priorResultsKeyItemNames;ownsResultsKeyItems=false;}
 bool ownsResultsItemGroups;
 void PrepareResultsItemGroups(){
  if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return;
  var map=(System.Collections.IDictionary)RewardField(typeof(ItemCatalog),"itemGroups").GetValue(null);Check(!ownsResultsItemGroups&&map.Count==0,"Unowned item-group catalog");
  var types=WholeCatalogComposed.ItemGroupTypes();var providers=WholeCatalogComposed.ItemGroupProviders();
  var fields=typeof(DLC4Content.ItemGroupTypes).GetFields(BindingFlags.Public|BindingFlags.Static);
  Check(types.Length>0&&providers.Length>0&&types.Length==fields.Length&&types.All(type=>type)&&types.Select(type=>type.name).Distinct().Count()==types.Length&&providers.All(provider=>provider&&types.Contains(provider.groupType)&&provider.groups!=null&&provider.groups.All(group=>group.items!=null)),"Original item-group metadata missing or ambiguous");
  foreach(var field in fields)BindEnemyDefinition(typeof(DLC4Content.ItemGroupTypes),field.Name,types.Single(type=>type.name==field.Name));
  // Preserve shipped group slots, including source-null item references; never invent membership.
  ownsResultsItemGroups=true;StaticCall(typeof(ItemCatalog),"SetItemGroups",new object[]{providers});
  Check(types.All(type=>ItemCatalog.GetItemGroupsForGroupType(type).Length==providers.Where(provider=>provider.groupType==type).Sum(provider=>provider.groups.Count(group=>group.items.Length>0))),"Original item-group registration differs");
  r.results.itemGroupTypes=types.Length;r.results.itemGroupProviders=providers.Length;r.results.itemGroups=providers.Sum(provider=>provider.groups.Length);
 }
 void CleanupResultsItemGroups(){if(!ownsResultsItemGroups)return;StaticCall(typeof(ItemCatalog),"SetItemGroups",new object[]{Array.Empty<ItemGroupProvider>()});ownsResultsItemGroups=false;}
 void RememberResultsEvent(Type type,string name){var field=type.GetField(name,BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);Check(field!=null,"Original results event missing: "+type.Name+"/"+name);resultsEventContext[field]=field.GetValue(null);}
 void ResultsStep(string value){r.results.initializationStep=value;Save();}
 void PrepareIntegratedResults(CharacterBody player,Result cfg){
  if(!cfg.integratedResults)return;
  r.results=new IntegratedResultsReport{scope="Original statistics, genuine Run.BeginGameOver/GameOverController/RunReport and client ending. Owned Android result presentation and run ledger; stock cutscene, Steam profiles, authentication, achievements and lunar awards unavailable."};r.phase="integrated-results-context";Save();
  Check(NetworkServer.active&&activeBodyClient.isConnected&&!GameOverController.instance&&PlayerStatsComponent.instancesList.Count==0,"Unowned results context");
  previousResultsSaveSystem=PlatformSystems.saveSystem;Check(previousResultsSaveSystem==null,"Existing platform save-system context");resultsSaveSystem=new UnavailableProfileSaveSystem();PlatformSystems.saveSystem=resultsSaveSystem;ownsResultsSaveSystem=true;
  // Current StatDef adds PerKeyItemStatDef. Register original metadata before its fixed buffers;
  // this grants no key item and does not start its pickup/platform simulation.
  ResultsStep("key-item-statistics");PrepareResultsKeyItems();
  var signature=string.Join("|",Enumerable.Range(0,BodyCatalog.bodyCount).Select(x=>BodyCatalog.GetBodyName((BodyIndex)x)))+"/"+string.Join("|",ItemCatalog.allItemDefs.Select(x=>x.name))+"/"+string.Join("|",clockSceneDefs.Select(x=>x.cachedName))+"/"+string.Join("|",KeyItemCatalog.keyItemNames);
  if(resultsStatsSignature==null){StaticCall(typeof(StatDef),"Init");StaticCall(typeof(StatSheet),"Init");resultsStatsSignature=signature;}else {Check(resultsStatsSignature==signature,"Restart original statistics catalog changed");resultsSaveSystem.isXmlReady=true;}
  ResultsStep("player-statistics");resultsStats=player.master.GetComponent<PlayerStatsComponent>();Check(resultsStats&&resultsStats.currentStats==null&&!resultsStats.gameObject.activeInHierarchy,"Original inactive player statistics scope changed");Call(resultsStats,"Awake");ownsResultsStats=true;
  Check(resultsStats.characterMaster==player.master&&resultsStats.playerCharacterMasterController==directorPlayer&&resultsStats.currentStats!=null&&PlayerStatsComponent.instancesList.Contains(resultsStats)&&!directorPlayer.networkUser,"Original player statistics identity missing");
  foreach(var name in new[]{"onServerDamageDealt","onCharacterDeathServer","onServerCharacterExecuted","onCharacterPickupItem"})RememberResultsEvent(typeof(GlobalEventManager),name);
  RememberResultsEvent(typeof(HealthComponent),"onCharacterHealServer");foreach(var name in new[]{"onPlayerFirstCreatedServer","onServerGameOver"})RememberResultsEvent(typeof(Run),name);
  foreach(var name in new[]{"onServerStageComplete","onServerStageBegin"})RememberResultsEvent(typeof(Stage),name);
  RememberResultsEvent(typeof(Inventory),"onServerItemGiven");RememberResultsEvent(typeof(RoR2Application),"onFixedUpdate");RememberResultsEvent(typeof(EquipmentSlot),"onServerEquipmentActivated");RememberResultsEvent(typeof(InfiniteTowerRun),"onWaveInitialized");RememberResultsEvent(typeof(MasterSummon),"onServerMasterSummonGlobal");
  RememberResultsEvent(typeof(KeyItemSlot),"onServerKeyItemActivated");
  ResultsStep("statistics-callbacks");ownsResultsContext=true;var statManager=typeof(PlayerStatsComponent).Assembly.GetType("RoR2.Stats.StatManager",true);StaticCall(statManager,"Init");resultsStatsProcess=(Action)Delegate.CreateDelegate(typeof(Action),statManager.GetMethod("ForceUpdate",BindingFlags.Public|BindingFlags.Static));resultsStatsFixed=(Action)Delegate.CreateDelegate(typeof(Action),resultsStats,typeof(PlayerStatsComponent).GetMethod("FixedUpdate",BindingFlags.Instance|BindingFlags.NonPublic));
  ResultsStep("ending-catalog");previousEndingContent=ContentManager._gameEndingDefs;previousEndingCatalog=(GameEndingDef[])RewardField(typeof(GameEndingCatalog),"gameEndingDefs").GetValue(null);
  Check(GameEndingCatalog.endingCount==0,"Unowned original ending catalog");var endings=cfg.resultsEndingAssets.Select(x=>artifactBundle.LoadAsset<GameEndingDef>(x)).ToArray();Check(endings.Length>=2&&endings.All(x=>x)&&endings.Any(x=>x.cachedName=="MainEnding"&&x.isWin),"Original game ending definitions missing");ContentManager._gameEndingDefs=endings;StaticCall(typeof(GameEndingCatalog),"Init");
  // The composed catalog previously used SetItemDefs, which does not register the
  // original ItemIndex[] XML rules. Run the source initializer with the exact owned
  // definitions; keep content roots, relationships and prior availability scoped.
  ResultsStep("item-xml");if(HGXml.SerializationRules<ItemIndex[]>.defaultRules==null){
   var itemDefs=ItemCatalog.allItemDefs.ToArray();var previousItems=ContentManager._itemDefs;var providersField=typeof(ContentManager).GetField("_itemRelationshipProviders",BindingFlags.NonPublic|BindingFlags.Static);var previousProviders=providersField.GetValue(null);var previousAvailability=ItemCatalog.availability;
   var previousGroups=ContentManager._itemGroupProviders;
   var groups=(System.Collections.IDictionary)RewardField(typeof(ItemCatalog),"itemGroups").GetValue(null);
   var relationships=(System.Collections.IDictionary)typeof(ItemCatalog).GetField("itemRelationships",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);Check(relationships.Count==0&&groups.Count==0&&providersField!=null,"Unowned item relationships/groups during original XML initialization");
   try{ContentManager._itemDefs=itemDefs;providersField.SetValue(null,Array.Empty<ItemRelationshipProvider>());ContentManager._itemGroupProviders=Array.Empty<ItemGroupProvider>();StaticCall(typeof(ItemCatalog),"Init");Check(ItemCatalog.allItemDefs.SequenceEqual(itemDefs)&&relationships.Count==0&&groups.Count==0&&HGXml.SerializationRules<ItemIndex[]>.defaultRules!=null,"Original item XML/catalog initialization differs");}
   finally{ContentManager._itemDefs=previousItems;providersField.SetValue(null,previousProviders);ContentManager._itemGroupProviders=previousGroups;ItemCatalog.availability=previousAvailability;}
  }
  ResultsStep("item-groups");PrepareResultsItemGroups();
  ResultsStep("report-xml");var folder=RewardField(typeof(RunReport),"runReportsFolder");Check(folder!=null,"Original report-folder field absent");previousReportFolder=(string)folder.GetValue(null);if(!resultsSerializersReady){StaticCall(typeof(RunReport),"Init");resultsSerializersReady=true;}
  resultsDirectory=Path.Combine(Application.persistentDataPath,"offline-run-results-v1");Directory.CreateDirectory(resultsDirectory);folder.SetValue(null,resultsDirectory+Path.DirectorySeparatorChar);LoadAndroidRunLedger();r.results.priorRuns=resultsLedger.runs.Count;
  // Disabled stock cutscene/vote/UI scheduling is an explicit Android presentation adapter.
  // The unchanged original ending method still creates its controller and genuine report.
  ResultsStep("ending-template");resultsTemplate=new GameObject("Owned Android original result template");resultsTemplate.SetActive(false);resultsTemplate.AddComponent<NetworkIdentity>();var fsm=resultsTemplate.AddComponent<EntityStateMachine>();fsm.customName="Main";fsm.enabled=false;
  var vote=resultsTemplate.AddComponent<VoteController>();vote.enabled=false;var controller=resultsTemplate.AddComponent<GameOverController>();controller.enabled=false;resultsTemplate.SetActive(true);
  Check(!GameOverController.instance&&controller.runReport!=null,"Android result template activated stock flow");previousGameOverPrefab=Run.instance.gameOverPrefab;Run.instance.gameOverPrefab=resultsTemplate;
  resultsServerEvent=(run,ending)=>{if(run!=Run.instance)return;var created=FindObjectsOfType<GameOverController>().Where(x=>x.gameObject!=resultsTemplate&&x.runReport!=null&&x.runReport.gameEnding==ending).ToArray();Check(created.Length==1,"Original generated ending controller/report missing");resultsController=created[0];resultsRunReport=resultsController.runReport;resultsController.enabled=true;r.results.serverEnding=true;r.results.reportGenerated=true;r.results.ending=ending.cachedName;Save();};
  resultsClientEvent=(run,report)=>{if(run!=Run.instance)return;Check(resultsRunReport!=null&&report.gameEnding==resultsRunReport.gameEnding&&report.playerInfoCount==resultsRunReport.playerInfoCount,"Original client ending/report differs");r.results.clientEnding=true;Save();};Run.onServerGameOver+=resultsServerEvent;Run.onClientGameOverGlobal+=resultsClientEvent;
  ResultsStep("run-identity");if(Run.instance.GetUniqueId()==Guid.Empty){Run.instance.Network_uniqueId=(RoR2.Networking.NetworkGuid)Guid.NewGuid();Run.instance.NetworkstartTimeUtc=(RoR2.Networking.NetworkDateTime)DateTime.UtcNow;}
  Run.instance.isRunning=true;r.results.statsRegistered=true;r.results.statFields=resultsStats.currentStats.fields.Length;r.results.ready=true;Save();
 }
 void TickIntegratedResults(){
  if(r==null||r.results==null||!r.results.ready||resultsStatsFixed==null||!string.IsNullOrEmpty(r.results.error))return;
  try{resultsStatsFixed();resultsStatsProcess();}catch(Exception e){r.results.error=e.ToString();resultsStatsFixed=null;Save();}
 }
 void ObserveIntegratedResults(){
  if(r.results==null||!r.results.ready)return;var report=r.results;
  Check(string.IsNullOrEmpty(report.error),"Original integrated statistics failed: "+report.error);
  report.damageDealt=resultsStats.currentStats.GetStatValueULong(StatDef.totalDamageDealt);report.damageTaken=resultsStats.currentStats.GetStatValueULong(StatDef.totalDamageTaken);report.kills=resultsStats.currentStats.GetStatValueULong(StatDef.totalKills);
  if(!report.serverEnding||!report.clientEnding||report.persisted)return;
  Check(Run.instance.isGameOverServer&&!Run.instance.isRunning&&resultsController&&resultsController.netId.Value!=0&&resultsRunReport!=null&&resultsRunReport.playerInfoCount==1&&resultsRunReport.GetPlayerInfo(0).master==resultsStats.characterMaster,"Original final report/ending accounting incomplete");
  report.players=resultsRunReport.playerInfoCount;report.items=resultsRunReport.GetPlayerInfo(0).itemAcquisitionOrder.Length;report.seconds=resultsRunReport.runStopwatchValue;report.stageClearCount=Run.instance.stageClearCount;
  var file="run-"+resultsRunReport.runGuid.ToString("N");RunReport.ToXml(new System.Xml.Linq.XElement("RunReport"),resultsRunReport);Check(RunReport.Save(resultsRunReport,file),"Original Android result save failed");var loaded=RunReport.Load(file);
  Check(loaded!=null&&loaded.gameEnding==resultsRunReport.gameEnding&&loaded.seed==resultsRunReport.seed&&loaded.playerInfoCount==report.players&&loaded.GetPlayerInfo(0).bodyIndex==resultsRunReport.GetPlayerInfo(0).bodyIndex&&loaded.GetPlayerInfo(0).itemStacks.SequenceEqual(resultsRunReport.GetPlayerInfo(0).itemStacks)&&loaded.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalKills)==resultsRunReport.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalKills)&&loaded.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageDealt)==resultsRunReport.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageDealt)&&loaded.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageTaken)==resultsRunReport.GetPlayerInfo(0).statSheet.GetStatValueULong(StatDef.totalDamageTaken)&&Mathf.Abs(loaded.runStopwatchValue-report.seconds)<.01f,"Original result XML round trip differs");
  report.reportFile=file+".xml";report.reportReloaded=true;
  bool assisted=r.debugAcceleration!=null&&r.debugAcceleration.everAssisted;string debugEvidence=assisted?file+".debug.json":null;
  if(assisted)File.WriteAllText(Path.Combine(resultsDirectory,debugEvidence),JsonUtility.ToJson(r.debugAcceleration,true));
  if(!resultsLedger.runs.Any(x=>x.file==report.reportFile)){resultsLedger.runs.Add(new AndroidRunEntry{file=report.reportFile,ending=report.ending,win=resultsRunReport.gameEnding.isWin,seconds=report.seconds,stages=report.stageClearCount,debugAssisted=assisted,debugEvidence=debugEvidence});SaveAndroidRunLedger();}
  report.persisted=true;Save();
 }
 void LoadAndroidRunLedger(){
  var path=Path.Combine(resultsDirectory,"profile.json");var backup=path+".backup";resultsLedger=new AndroidRunLedger();
  bool hasPrimary=File.Exists(path);
  if(hasPrimary){try{resultsLedger=ReadAndroidRunLedger(path);return;}catch(Exception error){r.results.ledgerRecoveryError=error.GetType().Name;}}
  else if(!File.Exists(backup))return;
  // Validate before moving any generation. Retain the rejected primary and the
  // valid backup; a later save must never replace that backup with corrupt data.
  var recovered=ReadAndroidRunLedger(backup);var pending=path+".pending";
  File.WriteAllText(pending,JsonUtility.ToJson(recovered,true));ReadAndroidRunLedger(pending);
  if(hasPrimary){var rejected=path+".rejected-"+Guid.NewGuid().ToString("N");File.Move(path,rejected);r.results.ledgerRejectedPrimary=Path.GetFileName(rejected);}
  File.Move(pending,path);resultsLedger=ReadAndroidRunLedger(path);r.results.ledgerRecovery="validated-backup";
 }
 static void ValidateAndroidRunLedger(bool valid,string message){if(!valid)throw new InvalidDataException(message);}
 AndroidRunLedger ReadAndroidRunLedger(string path){var value=JsonUtility.FromJson<AndroidRunLedger>(File.ReadAllText(path));ValidateAndroidRunLedger(value!=null&&value.version==1&&value.runs!=null,"Android run ledger schema invalid");foreach(var entry in value.runs)ValidateAndroidRunLedger(entry!=null&&entry.file==Path.GetFileName(entry.file)&&entry.file.StartsWith("run-")&&entry.file.EndsWith(".xml")&&File.Exists(Path.Combine(resultsDirectory,entry.file)),"Android run ledger references a missing result");foreach(var entry in value.runs)if(entry.debugAssisted){ValidateAndroidRunLedger(entry.debugEvidence==Path.ChangeExtension(entry.file,".debug.json")&&File.Exists(Path.Combine(resultsDirectory,entry.debugEvidence)),"Assisted result lacks its owned debug evidence");var debug=JsonUtility.FromJson<DebugAccelerationReport>(File.ReadAllText(Path.Combine(resultsDirectory,entry.debugEvidence)));ValidateAndroidRunLedger(debug!=null&&debug.version==1&&debug.everAssisted&&!debug.normalGameAcceptanceEligible,"Assisted ledger evidence claims normal acceptance");}return value;}
 void SaveAndroidRunLedger(){var path=Path.Combine(resultsDirectory,"profile.json");var pending=path+".pending";File.WriteAllText(pending,JsonUtility.ToJson(resultsLedger,true));ReadAndroidRunLedger(pending);if(File.Exists(path))File.Replace(pending,path,path+".backup");else File.Move(pending,path);var saved=ReadAndroidRunLedger(path);Check(saved.runs.Count==resultsLedger.runs.Count,"Android run ledger write did not persist");}
 void DrawIntegratedResults(){
  var report=r.results;var style=new GUIStyle(GUI.skin.label){fontSize=28,wordWrap=true};
  GUI.Box(new Rect(12,45,880,330),"Offline run result");
  var title=resultsRunReport!=null&&resultsRunReport.gameEnding&&resultsRunReport.gameEnding.isWin?"Victory":"Run ended";
  if(r.debugAcceleration!=null&&r.debugAcceleration.everAssisted)title="DEBUG ASSISTED — "+title+" (no normal-game acceptance)";
  if(r.freePlay&&report.persisted){if(r.phase=="commando-defeated"&&GUI.Button(new Rect(32,390,350,60),"Restart run (A)"))RequestWorldRestart();if(GUI.Button(new Rect(410,390,400,60),r.phase=="commando-defeated"?"Return to menu":"Return to menu (A)"))RequestResultsMenu();}
  GUI.Label(new Rect(32,78,820,260),title+" — "+report.ending+"\nOriginal stages cleared: "+report.stageClearCount+"   Time: "+report.seconds.ToString("F0")+"s\nKills: "+report.kills+"   Damage dealt: "+report.damageDealt.ToString("F0")+"\n"+(report.persisted?"Original report saved on this Android device":"Saving original report…")+"\nStock cutscene and Steam profile integration unavailable",style);
 }
 void CleanupIntegratedResults(){
  resultsStatsFixed=null;
  if(ownsResultsSaveSystem){Check(ReferenceEquals(PlatformSystems.saveSystem,resultsSaveSystem),"Results save-system boundary ownership changed");PlatformSystems.saveSystem=previousResultsSaveSystem;ownsResultsSaveSystem=false;}
  if(!ownsResultsContext){if(ownsResultsStats&&resultsStats){Call(resultsStats,"OnDestroy");ownsResultsStats=false;}foreach(var entry in resultsEventContext)entry.Key.SetValue(null,entry.Value);resultsEventContext.Clear();CleanupResultsItemGroups();CleanupResultsKeyItems();if(r.results!=null)r.results.cleaned=true;return;}
  Run.onServerGameOver-=resultsServerEvent;Run.onClientGameOverGlobal-=resultsClientEvent;
  if(Run.instance)Run.instance.gameOverPrefab=previousGameOverPrefab;
  if(resultsController)NetworkServer.Destroy(resultsController.gameObject);if(resultsTemplate)Destroy(resultsTemplate);
  if(ownsResultsStats&&resultsStats){Call(resultsStats,"OnDestroy");ownsResultsStats=false;}
  foreach(var entry in resultsEventContext)entry.Key.SetValue(null,entry.Value);resultsEventContext.Clear();
  ContentManager._gameEndingDefs=previousEndingContent;StaticCall(typeof(GameEndingCatalog),"SetGameEndingDefs",new object[]{previousEndingCatalog});typeof(RunReport).GetField("runReportsFolder",BindingFlags.Static|BindingFlags.NonPublic).SetValue(null,previousReportFolder);
  CleanupResultsItemGroups();CleanupResultsKeyItems();ownsResultsContext=false;if(r.results!=null)r.results.cleaned=true;
 }
}
