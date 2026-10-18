// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWholeDroneCatalog, PrepareWholeRunAvailability, PrepareWholeMasterTemplates, SelectWholeStagePool (WholePopulationSession); teardown CleanupWholePopulation (Dispose), CleanupWholeRunAvailability, CleanupWholeStagePool, CleanupWholePickups.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.AsyncOperations;

// Original pools choose content. Android owns template activation and unavailable audio.
public sealed partial class PortSession {
 // Shared with the other runtime boundaries.
 readonly Dictionary<string,GameObject> wholeMasterTemplates=new Dictionary<string,GameObject>(StringComparer.Ordinal);
 readonly Dictionary<CharacterSpawnCard,CharacterSpawnCard> wholeSpawnCards=new Dictionary<CharacterSpawnCard,CharacterSpawnCard>();
 readonly HashSet<CharacterMaster> wholePlayerSummons=new HashSet<CharacterMaster>();
 ClassicStageInfo wholeStageInfo;
 WholePopulationSession wholePopulationSession;
 WholePopulationSession GetWholePopulationSession(){if(wholePopulationSession==null)wholePopulationSession=new WholePopulationSession(this);return wholePopulationSession;}
 System.Collections.IEnumerator PrepareWholePickups(){return GetWholePopulationSession().PrepareWholePickups();}
 void CleanupWholePickups(){GetWholePopulationSession().CleanupWholePickups();}
 void PrepareWholeDroneCatalog(){GetWholePopulationSession().PrepareWholeDroneCatalog();}
 void PrepareWholeRunAvailability(){GetWholePopulationSession().PrepareWholeRunAvailability();}
 void RefreshWholeRunAvailability(){GetWholePopulationSession().RefreshWholeRunAvailability();}
 void CleanupWholeRunAvailability(){GetWholePopulationSession().CleanupWholeRunAvailability();}
 GameObject[] PrepareWholeMasterTemplates(GameObject[] originals,GameObject[] adapted){return GetWholePopulationSession().PrepareWholeMasterTemplates(originals,adapted);}
 void ObserveWholePlayerSummon(MasterSummon.MasterSummonReport report){GetWholePopulationSession().ObserveWholePlayerSummon(report);}
 int DestroyWholePlayerSummons(){return GetWholePopulationSession().DestroyWholePlayerSummons();}
 IEnumerator PrepareWholeModelDisplayRules(){return GetWholePopulationSession().PrepareWholeModelDisplayRules();}
 CharacterSpawnCard WholeSpawnCard(CharacterSpawnCard source){return GetWholePopulationSession().WholeSpawnCard(source);}
 DirectorCardCategorySelection SelectWholeStagePool(string stage){return GetWholePopulationSession().SelectWholeStagePool(stage);}
 void CleanupWholeStagePool(){GetWholePopulationSession().CleanupWholeStagePool();}
 void CleanupWholePopulation(){GetWholePopulationSession().Dispose();}

 // Create on first use and retain for partial setup, repeated cleanup and stage
 // turnover. Dispose keeps summon removal before interactables, stage pools,
 // availability masks and template/card registries; their forwarders stay separate.
 sealed class WholePopulationSession : IDisposable {
  readonly PortSession coordinator;
  readonly HashSet<ItemDisplayRuleSet> wholeModelDisplayRules=new HashSet<ItemDisplayRuleSet>();
  CharacterSpawnCard wholeBeetleAllyCard;GameObject priorBeetleAllyMaster;bool observesWholePlayerSummons;
  readonly List<AsyncOperationHandle> wholeStageLeases=new List<AsyncOperationHandle>();
  bool wholeStageInfoSerialized;
  readonly Dictionary<FieldInfo,object> priorWholeDroneFields=new Dictionary<FieldInfo,object>();
  readonly Dictionary<DroneDef,object[]> priorWholeDroneDefinitions=new Dictionary<DroneDef,object[]>();
  Run wholeAvailabilityRun;DroneMask wholeAvailableDrones,wholeLockedDrones;KeyItemMask wholeAvailableKeyItems,wholeLockedKeyItems;
  AsyncOperationHandle<GameObject> wholeEquipmentOrbLease;GameObject priorWholeEquipmentOrb;int wholeEquipmentOrbReferences;bool ownsWholePickupOrb;
  public WholePopulationSession(PortSession coordinator){this.coordinator=coordinator;}
  public System.Collections.IEnumerator PrepareWholePickups(){
   priorWholeEquipmentOrb=EquipmentDef.dropletDisplayPrefab;wholeEquipmentOrbLease=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/ItemPickups/EquipmentOrb");ownsWholePickupOrb=true;yield return wholeEquipmentOrbLease;
   coordinator.Check(wholeEquipmentOrbLease.Status==AsyncOperationStatus.Succeeded&&wholeEquipmentOrbLease.Result,"Original equipment pickup presentation unavailable");
   wholeEquipmentOrbReferences=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(wholeEquipmentOrbLease);
   var native=PickupCatalog.Init();while(native.MoveNext())yield return native.Current;
   coordinator.Check(EquipmentDef.dropletDisplayPrefab==wholeEquipmentOrbLease.Result,"Native pickup initializer changed equipment orb identity");
  }
  public void CleanupWholePickups(){
   if(!ownsWholePickupOrb)return;EquipmentDef.SetDropletDisplayPrefab(priorWholeEquipmentOrb);
   if(wholeEquipmentOrbLease.IsValid()){
    int extra=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(wholeEquipmentOrbLease)-wholeEquipmentOrbReferences;
    coordinator.Check(extra>=0&&extra<=1,"Unattributed native pickup initialization lease");if(extra==1)Addressables.Release(wholeEquipmentOrbLease.Result);Addressables.Release(wholeEquipmentOrbLease);
   }ownsWholePickupOrb=false;
  }
  public void PrepareWholeDroneCatalog(){
   coordinator.Check(DroneCatalog.droneCount==0&&priorWholeDroneFields.Count==0,"Foreign drone catalog owner");
   var fields=typeof(DroneCatalog).GetFields(BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);
   coordinator.Check(((System.Collections.IDictionary)fields.Single(field=>field.Name=="nameToDroneIndex").GetValue(null)).Count==0,"Foreign drone index owner");
   foreach(var field in fields)if(!field.IsLiteral&&(field.FieldType.IsArray||field.FieldType==typeof(global::ResourceAvailability)))priorWholeDroneFields.Add(field,field.GetValue(null));
   var definitions=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.droneDef,new DroneDef[0]);
   foreach(var def in definitions)priorWholeDroneDefinitions.Add(def,new object[]{def.droneIndex,def.requiredExpansion});
   PortSession.StaticCall(typeof(DroneCatalog),"SetDroneDefs",new object[]{definitions});DroneCatalog.availability.MakeAvailable();
   WholeCatalogComposed.PopulateDefinitionFields("DroneDefs",definitions);
   coordinator.Check(definitions.All(def=>DroneCatalog.GetDroneDef(def.droneIndex)==def&&DroneCatalog.GetBodyIndexFromDroneIndex(def.droneIndex)!=BodyIndex.None),"Original drone catalog identity differs");
  }
  public void PrepareWholeRunAvailability(){
   if(coordinator.r.liveCatalogs==null)return;
   var run=Run.instance;coordinator.Check(run&&run.availableDrones==null&&run.expansionLockedDrones==null&&run.availableKeyItems==null&&run.expansionLockedKeyItems==null,"Foreign drone/key-item availability owner");
   // Register key-item metadata before fixed-size masks and the native RuleCatalog.
   coordinator.PrepareResultsKeyItems();wholeAvailabilityRun=run;
   wholeAvailableDrones=DroneMask.Rent();wholeLockedDrones=DroneMask.Rent();wholeAvailableKeyItems=KeyItemMask.Rent();wholeLockedKeyItems=KeyItemMask.Rent();
   run.availableDrones=wholeAvailableDrones;run.expansionLockedDrones=wholeLockedDrones;run.availableKeyItems=wholeAvailableKeyItems;run.expansionLockedKeyItems=wholeLockedKeyItems;
  }
  public void RefreshWholeRunAvailability(){
   if(!wholeAvailabilityRun)return;
   if(coordinator.androidProgression!=null&&coordinator.r.profile!=null&&coordinator.r.profile.ready)coordinator.r.profile.availableEarnedUnlocks=coordinator.androidProgression.PopulateEarnedRunAvailability(wholeAvailabilityRun,coordinator.resultsSaveSystem.local.profile);
   var run=wholeAvailabilityRun;run.ruleBook.GenerateDroneMask(wholeAvailableDrones);run.ruleBook.GenerateKeyItemMask(wholeAvailableKeyItems);wholeLockedDrones.Clear();wholeLockedKeyItems.Clear();
   // Native rules retain every droppable family, including Lunar content. Currency
   // access is a separate purchase boundary; it must not create empty source tables.
   run.ruleBook.GenerateItemMask(coordinator.worldAvailableItems);run.ruleBook.GenerateEquipmentMask(coordinator.worldAvailableEquipment);
   foreach(var def in ItemCatalog.allItemDefs)if(def.hidden||(def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion))||(def.unlockableDef&&!run.IsUnlockableUnlocked(def.unlockableDef)))coordinator.worldAvailableItems.Remove(def.itemIndex);
   foreach(var index in EquipmentCatalog.allEquipment){var def=EquipmentCatalog.GetEquipmentDef(index);if((def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion))||(def.unlockableDef&&!run.IsUnlockableUnlocked(def.unlockableDef)))coordinator.worldAvailableEquipment.Remove(index);}
   foreach(var def in DroneCatalog.allDroneDefs)if(def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion)){wholeAvailableDrones.Remove(def.droneIndex);wholeLockedDrones.Add(def.droneIndex);}
   foreach(var def in KeyItemCatalog.allKeyItemDefs){if(def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion)){wholeAvailableKeyItems.Remove(def.keyItemIndex);wholeLockedKeyItems.Add(def.keyItemIndex);}if(def.unlockableDef&&!run.IsUnlockableUnlocked(def.unlockableDef))wholeAvailableKeyItems.Remove(def.keyItemIndex);}
   run.BuildDropTable();
   if(coordinator.r.profile!=null&&coordinator.r.profile.ready)coordinator.r.profile.earnedLoot=ItemCatalog.allItemDefs.Where(def=>def.unlockableDef&&coordinator.worldAvailableItems.Contains(def.itemIndex)).Select(def=>def.name).OrderBy(name=>name,StringComparer.Ordinal).ToArray();
  }
  public void CleanupWholeRunAvailability(){
   CleanupWholePickups();
   if(wholeAvailabilityRun){wholeAvailabilityRun.availableDrones=null;wholeAvailabilityRun.expansionLockedDrones=null;wholeAvailabilityRun.availableKeyItems=null;wholeAvailabilityRun.expansionLockedKeyItems=null;wholeAvailabilityRun=null;}
   if(wholeAvailableDrones!=null)DroneMask.Return(wholeAvailableDrones);if(wholeLockedDrones!=null)DroneMask.Return(wholeLockedDrones);if(wholeAvailableKeyItems!=null)KeyItemMask.Return(wholeAvailableKeyItems);if(wholeLockedKeyItems!=null)KeyItemMask.Return(wholeLockedKeyItems);
   wholeAvailableDrones=null;wholeLockedDrones=null;wholeAvailableKeyItems=null;wholeLockedKeyItems=null;
   if(priorWholeDroneFields.Count>0){PortSession.StaticCall(typeof(DroneCatalog),"SetDroneDefs",new object[]{Array.Empty<DroneDef>()});foreach(var entry in priorWholeDroneDefinitions){entry.Key.droneIndex=(DroneIndex)entry.Value[0];entry.Key.requiredExpansion=(RoR2.ExpansionManagement.ExpansionDef)entry.Value[1];}foreach(var entry in priorWholeDroneFields)entry.Key.SetValue(null,entry.Value);priorWholeDroneDefinitions.Clear();priorWholeDroneFields.Clear();}
  }
  public GameObject[] PrepareWholeMasterTemplates(GameObject[] originals,GameObject[] adapted){
   foreach(var value in adapted)coordinator.wholeMasterTemplates.Add(value.name,value);
   foreach(var source in originals){
    if(coordinator.wholeMasterTemplates.ContainsKey(source.name))continue;
    var originalMaster=source.GetComponent<CharacterMaster>();var originalBody=originalMaster.bodyPrefab;
    // Some shipped masters intentionally have no body. Preserve that source contract.
    if(!originalBody){coordinator.wholeMasterTemplates.Add(source.name,source);continue;}
    var index=originalBody.GetComponent<CharacterBody>().bodyIndex;var bodyObject=BodyCatalog.GetBodyPrefab(index);
    if(!coordinator.priorCatalogBodyTemplates.ContainsKey((int)index)){
     bodyObject=PortSession.Instantiate(originalBody,coordinator.enemyTemplates.transform);bodyObject.name=originalBody.name;bodyObject.SetActive(true);coordinator.objectiveTemplates.Add(bodyObject);
     coordinator.Check(bodyObject.GetComponentsInChildren<Component>(true).All(value=>value),"Whole actor has a missing serialized component: "+source.name);
     foreach(var behaviour in bodyObject.GetComponentsInChildren<MonoBehaviour>(true)){
      if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){PortSession.DestroyImmediate(behaviour);continue;}
      if(behaviour is RoR2.Networking.CharacterNetworkTransform||behaviour is InteractionDriver)behaviour.enabled=false;
     }
     foreach(var sfx in bodyObject.GetComponentsInChildren<SfxLocator>(true))foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Public|BindingFlags.Instance))if(field.FieldType==typeof(string))field.SetValue(sfx,null);
     coordinator.BindCatalogBodyTemplate(bodyObject);
    }
    var masterObject=PortSession.Instantiate(source,coordinator.enemyTemplates.transform);masterObject.name=source.name;masterObject.GetComponent<CharacterMaster>().bodyPrefab=bodyObject;
    var inventory=masterObject.GetComponent<Inventory>();if(inventory)inventory.enabled=false;
    foreach(var behaviour in masterObject.GetComponentsInChildren<MonoBehaviour>(true))if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal))PortSession.DestroyImmediate(behaviour);
    masterObject.SetActive(true);coordinator.objectiveTemplates.Add(masterObject);coordinator.wholeMasterTemplates.Add(source.name,masterObject);
   }
   // The original Beetle Gland behavior loads this card by legacy key each time
   // it summons. Bind only its prefab to the same owned master used by the native
   // catalog; restore the source card before releasing the content owner.
   const string allyPath="SpawnCards/CharacterSpawnCards/cscBeetleGuardAlly";
   string allyKey;coordinator.Check(LegacyResourcesAPI.GetGuid(allyPath,out allyKey)&&!string.IsNullOrEmpty(allyKey),"Original Beetle Gland spawn-card alias missing");
   wholeBeetleAllyCard=LegacyResourcesAPI.Load<SpawnCard>(allyPath) as CharacterSpawnCard;
   GameObject adaptedAlly=null;
   coordinator.Check(wholeBeetleAllyCard&&wholeBeetleAllyCard.name=="cscBeetleGuardAlly"&&wholeBeetleAllyCard.prefab&&coordinator.wholeMasterTemplates.TryGetValue(wholeBeetleAllyCard.prefab.name,out adaptedAlly)&&adaptedAlly&&adaptedAlly!=wholeBeetleAllyCard.prefab,"Original Beetle Gland master adaptation missing");
   priorBeetleAllyMaster=wholeBeetleAllyCard.prefab;wholeBeetleAllyCard.prefab=adaptedAlly;
   coordinator.Check(!observesWholePlayerSummons,"Player summon observer already registered");MasterSummon.onServerMasterSummonGlobal+=ObserveWholePlayerSummon;observesWholePlayerSummons=true;
   return originals.Select(value=>coordinator.wholeMasterTemplates[value.name]).ToArray();
  }
  public void ObserveWholePlayerSummon(MasterSummon.MasterSummonReport report){
   if(report.leaderMasterInstance==coordinator.rewardPlayerMaster&&report.summonMasterInstance&&report.summonMasterInstance.teamIndex==TeamIndex.Player)coordinator.wholePlayerSummons.Add(report.summonMasterInstance);
  }
  public int DestroyWholePlayerSummons(){
   int count=0;
   foreach(var summon in coordinator.wholePlayerSummons){if(!summon)continue;
    // Original OnDestroy also removes MinionLeash. Do that through the original
    // ownership API while Run still exists; Destroy is deferred until a frame
    // where the owned Run may already have been disabled.
    var ownership=summon.GetComponent<MinionOwnership>();if(ownership&&ownership.group!=null){coordinator.Check(Run.instance&&NetworkServer.active,"Owned minion needs a live Run for original inventory release");ownership.SetOwner(null);}
    var body=summon.GetBody();if(body&&body!=coordinator.worldPlayer)NetworkServer.Destroy(body.gameObject);NetworkServer.Destroy(summon.gameObject);count++;}
   coordinator.wholePlayerSummons.Clear();return count;
  }
  public IEnumerator PrepareWholeModelDisplayRules(){
   if(coordinator.r.liveCatalogs==null)yield break;
   // Stock ItemDisplayRuleSet.Init visits enabled instances. Converted inactive
   // body prefabs are cataloged without that startup path, so run the original
   // per-set initializer once after all item/equipment/key-item catalogs exist.
   var models=BodyCatalog.allBodyPrefabs.Where(body=>body).SelectMany(body=>body.GetComponentsInChildren<CharacterModel>(true))
    .Concat(coordinator.objectiveTemplates.Where(template=>template).SelectMany(template=>template.GetComponentsInChildren<CharacterModel>(true)));
   foreach(var rules in models.Select(model=>model.itemDisplayRuleSet).Where(rules=>rules).Distinct()){
    if(!wholeModelDisplayRules.Add(rules))continue;
    var original=rules.GenerateRuntimeValuesAsync();while(original.MoveNext())yield return original.Current;
   }
   coordinator.Check(wholeModelDisplayRules.Count>0,"Original catalog body display rules unavailable");
  }
  public CharacterSpawnCard WholeSpawnCard(CharacterSpawnCard source){
   CharacterSpawnCard copy;if(coordinator.wholeSpawnCards.TryGetValue(source,out copy))return copy;
   GameObject master;coordinator.Check(source.prefab&&coordinator.wholeMasterTemplates.TryGetValue(source.prefab.name,out master),"Original spawn card master missing from complete catalog: "+source.name);
   copy=PortSession.Instantiate(source);copy.name=source.name;copy.prefab=coordinator.wholeMasterTemplates[source.prefab.name];coordinator.wholeSpawnCards.Add(source,copy);return copy;
  }
  public DirectorCardCategorySelection SelectWholeStagePool(string stage){
   CleanupWholeStagePool();var text=Resources.Load<TextAsset>("WholeStageContexts");coordinator.Check(text,"Original stage context metadata absent");
   var contexts=JObject.Parse(text.text);var generation=JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);coordinator.Check((string)contexts["input_id"]==(string)generation["input_id"],"Stage population input generation differs");
   var source=(JObject)contexts["stages"][stage];coordinator.wholeStageContext=source;coordinator.Check(source!=null,"Original stage context absent: "+stage);
   var info=SceneInfo.instance;coordinator.Check(info,"Stage navigation/population owner missing");
   if(coordinator.stageSourceObjects){
    coordinator.wholeStageInfo=info.GetComponent<ClassicStageInfo>();
    wholeStageInfoSerialized=true;
    coordinator.Check(info.gameObject==coordinator.sourceSceneInfoRoot&&coordinator.wholeStageInfo&&ClassicStageInfo.instance==coordinator.wholeStageInfo&&coordinator.wholeStageInfo.monsterSelection!=null&&coordinator.wholeStageInfo.interactableCategories,"Original serialized stage population did not start");
    foreach(var name in new[]{"monsterDccsPool","interactableDccsPool"}){
     var field=typeof(ClassicStageInfo).GetField(name,BindingFlags.Instance|BindingFlags.NonPublic);coordinator.Check(field!=null&&field.GetValue(coordinator.wholeStageInfo) is DccsPool,"Original serialized stage pool missing: "+stage+"/"+name);
    }
   }else{
    wholeStageInfoSerialized=false;
    coordinator.Check(!info.GetComponent<ClassicStageInfo>()&&!ClassicStageInfo.instance,"Stage context has a foreign population owner");
    // Reduced-scene rollback still reconstructs the measured source fields.
    coordinator.wholeStageInfo=info.gameObject.AddComponent<ClassicStageInfo>();coordinator.wholeStageInfo.enabled=false;PortSession.Call(coordinator.wholeStageInfo,"OnEnable");
    foreach(var name in new[]{"monsterDccsPool","interactableDccsPool"}){
     var handle=Addressables.LoadAssetAsync<DccsPool>((string)source[name]);wholeStageLeases.Add(handle);var pool=handle.WaitForCompletion();coordinator.Check(handle.Status==AsyncOperationStatus.Succeeded&&pool,"Original stage pool unavailable: "+stage+"/"+name);
     typeof(ClassicStageInfo).GetField(name,BindingFlags.Instance|BindingFlags.NonPublic).SetValue(coordinator.wholeStageInfo,pool);
    }
    foreach(var property in ((JObject)source["fields"]).Properties()){
     var field=typeof(ClassicStageInfo).GetField(property.Name,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);coordinator.Check(field!=null,"Original population field absent: "+property.Name);
     field.SetValue(coordinator.wholeStageInfo,property.Value.ToObject(field.FieldType));
    }
    PortSession.Call(coordinator.wholeStageInfo,"RebuildCards",new object[]{null,null});
   }
   var selected=(DirectorCardCategorySelection)typeof(ClassicStageInfo).GetField("modifiableMonsterCategories",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(coordinator.wholeStageInfo);coordinator.Check(selected,"Original population selection returned no deck: "+stage);
   var deck=PortSession.Instantiate(selected);
   var sourceCards=selected.categories.SelectMany(category=>category.cards).ToArray();
   var ownedCards=deck.categories.SelectMany(category=>category.cards).ToArray();
   var replacements=new Dictionary<DirectorCard,DirectorCard>();
   for(int i=0;i<sourceCards.Length;i++)replacements[sourceCards[i]]=ownedCards[i];
   foreach(var card in deck.categories.SelectMany(category=>category.cards)){
    var original=card.GetSpawnCard() as CharacterSpawnCard;coordinator.Check(original,"Stage population contains a non-character card: "+stage);
    card.spawnCard=WholeSpawnCard(original);card.spawnCardReference=new AssetReferenceT<SpawnCard>("");
   }
   // Child directors without an explicit deck consume ClassicStageInfo's selection.
   // Preserve the native choices/weights; substitute only owned activation templates.
   var sharedSelection=new WeightedSelection<DirectorCard>();
   for(int i=0;i<coordinator.wholeStageInfo.monsterSelection.Count;i++){
    var choice=coordinator.wholeStageInfo.monsterSelection.GetChoice(i);sharedSelection.AddChoice(replacements[choice.value],choice.weight);
   }
   typeof(ClassicStageInfo).GetProperty("monsterSelection").GetSetMethod(true).Invoke(coordinator.wholeStageInfo,new object[]{sharedSelection});
   return deck;
  }
  public void CleanupWholeStagePool(){
   if(coordinator.wholeStageInfo){
    bool serialized=wholeStageInfoSerialized;
    if(coordinator.wholeStageInfo.interactableCategories){PortSession.Destroy(coordinator.wholeStageInfo.interactableCategories);coordinator.wholeStageInfo.interactableCategories=null;}
    if(serialized)coordinator.wholeStageInfo.enabled=false;
    else{PortSession.Call(coordinator.wholeStageInfo,"OnDisable");PortSession.Call(coordinator.wholeStageInfo,"OnDestroy");PortSession.Destroy(coordinator.wholeStageInfo);}
    coordinator.wholeStageInfo=null;
   }
   wholeStageInfoSerialized=false;
   foreach(var lease in wholeStageLeases)if(lease.IsValid())Addressables.Release(lease);wholeStageLeases.Clear();
  }
  public void Dispose(){
   if(observesWholePlayerSummons){MasterSummon.onServerMasterSummonGlobal-=ObserveWholePlayerSummon;observesWholePlayerSummons=false;}
   DestroyWholePlayerSummons();
   if(wholeBeetleAllyCard){coordinator.Check(wholeBeetleAllyCard.prefab==coordinator.wholeMasterTemplates[priorBeetleAllyMaster.name],"Owned Beetle Gland card changed");wholeBeetleAllyCard.prefab=priorBeetleAllyMaster;wholeBeetleAllyCard=null;priorBeetleAllyMaster=null;}
   coordinator.CleanupWholeInteractables();CleanupWholeStagePool();CleanupWholeRunAvailability();foreach(var card in coordinator.wholeSpawnCards.Values)if(card)PortSession.Destroy(card);coordinator.wholeSpawnCards.Clear();coordinator.wholeMasterTemplates.Clear();wholeModelDisplayRules.Clear();
  }
 }
}
