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

// Native SceneDirector owns selection, credits, caps, placement and initial map spawns.
// Android owns inactive templates, explicit no-audio presentation and paired resources.
public sealed partial class MovementBatchProbe {
 readonly Dictionary<GameObject,GameObject> wholeInteractableTemplates=new Dictionary<GameObject,GameObject>();
 readonly Dictionary<SpawnCard,SpawnCard> wholeInteractableCards=new Dictionary<SpawnCard,SpawnCard>();
 readonly List<GameObject> wholePlayerSpawnPoints=new List<GameObject>();
 SceneDirector wholeSceneDirector;JObject wholeStageContext;GameObject priorSpawnPointPrefab;
 AsyncOperationHandle<GameObject> wholeSpawnPointLease;bool ownsSpawnPointPrefab;

 GameObject WholeInteractableTemplate(GameObject source){
  GameObject owned;if(wholeInteractableTemplates.TryGetValue(source,out owned))return owned;
  Check(source&&worldStaging&&!worldStaging.activeInHierarchy,"Original interactable staging unavailable");
  owned=Instantiate(source,worldStaging.transform);owned.name=source.name;owned.SetActive(true);wholeInteractableTemplates.Add(source,owned);
  Check(owned.GetComponentsInChildren<Component>(true).All(value=>value),"Original interactable has a missing component: "+source.name);
  foreach(var behaviour in owned.GetComponentsInChildren<MonoBehaviour>(true)){
   if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(behaviour);continue;}
   foreach(var field in behaviour.GetType().GetFields(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)){
    if(field.IsInitOnly||(!field.IsPublic&&!Attribute.IsDefined(field,typeof(SerializeField))))continue;
    var table=field.GetValue(behaviour) as PickupDropTable;
    if(table){var copy=ObjectiveDropTable(table);Check(copy,"Original interactable drop table unavailable: "+table.name);field.SetValue(behaviour,copy);}
    if(field.FieldType==typeof(GameObject)){
     var target=field.GetValue(behaviour) as GameObject;GameObject master;
     if(target&&target.GetComponent<CharacterMaster>()&&wholeMasterTemplates.TryGetValue(target.name,out master))field.SetValue(behaviour,master);
    }
   }
  }
  foreach(var sfx in owned.GetComponentsInChildren<SfxLocator>(true))foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Instance|BindingFlags.Public))if(field.FieldType==typeof(string))field.SetValue(sfx,null);
  var shop=owned.GetComponent<MultiShopController>();if(shop&&shop.terminalPrefab)shop.terminalPrefab=WholeInteractableTemplate(shop.terminalPrefab);
  PrepareCommerceSymbols(owned);PresentCommerceModel(owned.transform);return owned;
 }
 SpawnCard WholeInteractableCard(SpawnCard source){
  SpawnCard owned;if(wholeInteractableCards.TryGetValue(source,out owned))return owned;
  Check(source is InteractableSpawnCard&&source.prefab,"Original stage has an invalid interactable spawn card");
  owned=Instantiate(source);owned.name=source.name;owned.prefab=WholeInteractableTemplate(source.prefab);wholeInteractableCards.Add(source,owned);return owned;
 }
 void AdaptWholeInteractableSelection(SceneDirector director,DirectorCardCategorySelection selection){
  if(director!=wholeSceneDirector)return;
  // Native CopyFrom clones arrays but shares DirectorCard instances with source pools.
  // Unity's serialized clone separates those instances before Android substitutions.
  var owned=Instantiate(selection);
  try{foreach(var card in owned.categories.SelectMany(category=>category.cards)){
   card.spawnCard=WholeInteractableCard(card.GetSpawnCard());card.spawnCardReference=new AssetReferenceT<SpawnCard>("");
  }selection.categories=owned.categories;}finally{DestroyImmediate(owned);}
 }
 void ObserveWholeInteractable(SceneDirector director,GameObject obj,DirectorCard card){
  if(director!=wholeSceneDirector)return;
  Check(obj&&card.GetSpawnCard()&&wholeInteractableCards.Values.Contains(card.GetSpawnCard()),"Native interactable has no owned source card");
  worldObjects.Add(obj);commerceOwned.Add(obj);var barrel=obj.GetComponent<BarrelInteraction>();if(barrel){worldBarrels.Add(barrel);worldBarrelConsumers++;}
  var chest=obj.GetComponent<ChestBehavior>();if(chest)worldChests.Add(chest);
  var shop=obj.GetComponent<MultiShopController>();if(shop){commerceShops.Add(shop);r.commerce.shops++;foreach(var terminal in shop.terminalGameObjectsList){worldObjects.Add(terminal);commerceOwned.Add(terminal);WatchCommercePurchase(terminal.GetComponent<PurchaseInteraction>());}}
  var purchase=obj.GetComponent<PurchaseInteraction>();if(purchase)WatchCommercePurchase(purchase);
  if(obj.GetComponent<ShrineChanceBehavior>())r.commerce.chanceShrines++;
  if(obj.GetComponent<ShrineBloodBehavior>())r.commerce.bloodShrines++;
  if(obj.GetComponent<ShrineHealingBehavior>())r.commerce.healingShrines++;
  if(obj.GetComponent<ShrineBossBehavior>())r.commerce.bossShrines++;
  if(obj.GetComponent<ShrineRestackBehavior>())r.commerce.restackShrines++;
  currentStageCombatDeck.placedInteractables.Add(card.GetSpawnCard().name);
 }
 IEnumerator PopulateWholeStage(){
  if(r.liveCatalogs==null)yield break;
  Check(wholeStageInfo&&ClassicStageInfo.instance==wholeStageInfo&&wholeStageContext!=null&&objectiveStage&&worldTeleporter&&DirectorCore.instance,"Native stage population context incomplete");
  if(!ownsSpawnPointPrefab){
   var field=typeof(SpawnPoint).GetField("prefab",BindingFlags.Static|BindingFlags.NonPublic);priorSpawnPointPrefab=(GameObject)field.GetValue(null);Check(!priorSpawnPointPrefab,"Foreign player-spawn prefab owner");
   wholeSpawnPointLease=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/SpawnPoint");ownsSpawnPointPrefab=true;yield return wholeSpawnPointLease;
   Check(wholeSpawnPointLease.Status==AsyncOperationStatus.Succeeded&&wholeSpawnPointLease.Result,"Original player-spawn prefab unavailable");field.SetValue(null,wholeSpawnPointLease.Result);
  }
  wholeSceneDirector=automaticDirectorHost.AddComponent<SceneDirector>();wholeSceneDirector.enabled=false;
  foreach(var property in ((JObject)wholeStageContext["director_fields"]).Properties()){
   var field=typeof(SceneDirector).GetField(property.Name,BindingFlags.Public|BindingFlags.Instance);Check(field!=null,"Original scene director field unavailable: "+property.Name);field.SetValue(wholeSceneDirector,property.Value.ToObject(field.FieldType));
  }
  // Keep the accepted teleporter lifecycle; native population reuses that instance.
  wholeSceneDirector.teleporterInstance=worldTeleporter.gameObject;
  wholeStageInfo.bonusInteractibleCreditObjects=((JArray)wholeStageContext["bonus_credits"]).Select(row=>{
   var matches=stageGeometryScene.GetRootGameObjects().SelectMany(root=>root.GetComponentsInChildren<Transform>(true)).Where(value=>StageObjectPath(value)==(string)row["path"]).ToArray();
   Check(matches.Length==1,"Original stage bonus-credit object is ambiguous: "+row["path"]);
   return new ClassicStageInfo.BonusInteractibleCreditObject{objectThatGrantsPointsIfEnabled=matches[0].gameObject,points=(int)row["points"]};
  }).ToArray();
  int credits=wholeStageInfo.sceneDirectorInteractibleCredits;
  foreach(var bonus in wholeStageInfo.bonusInteractibleCreditObjects)if(bonus.objectThatGrantsPointsIfEnabled.activeSelf)credits+=bonus.points;
  currentStageCombatDeck.initialInteractableCredits=credits;
  currentStageCombatDeck.droneDefinitions=DroneCatalog.droneCount;currentStageCombatDeck.availableDrones=DroneCatalog.allDroneDefs.Count(def=>Run.instance.IsDroneAvailable(def.droneIndex));
  currentStageCombatDeck.pickupDefinitions=PickupCatalog.pickupCount;currentStageCombatDeck.lunarLoot=Run.instance.availableLunarCombinedDropList.Count;
  var priorPoints=new HashSet<SpawnPoint>(SpawnPoint.readOnlyInstancesList);
  SceneDirector.onGenerateInteractableCardSelection+=AdaptWholeInteractableSelection;SceneDirector.onSpawnInteractableServer+=ObserveWholeInteractable;
  try{Call(wholeSceneDirector,"Start");currentStageCombatDeck.nativeScenePopulation=true;currentStageCombatDeck.remainingInteractableCredits=wholeSceneDirector.interactableCredit;}
  finally{SceneDirector.onGenerateInteractableCardSelection-=AdaptWholeInteractableSelection;SceneDirector.onSpawnInteractableServer-=ObserveWholeInteractable;foreach(var point in SpawnPoint.readOnlyInstancesList)if(!priorPoints.Contains(point))wholePlayerSpawnPoints.Add(point.gameObject);}
  currentStageCombatDeck.playerSpawnPoints=wholePlayerSpawnPoints.Count;
  r.world.barrels=worldBarrels.Count;r.world.chests=worldChests.Count;Save();yield return null;
 }
 void CleanupWholeStageInteractables(){
  if(wholeSceneDirector)Destroy(wholeSceneDirector);wholeSceneDirector=null;
  foreach(var point in wholePlayerSpawnPoints)if(point)Destroy(point);wholePlayerSpawnPoints.Clear();
  foreach(var card in wholeInteractableCards.Values)if(card)Destroy(card);wholeInteractableCards.Clear();
  foreach(var template in wholeInteractableTemplates.Values)if(template)Destroy(template);wholeInteractableTemplates.Clear();
 }
 void CleanupWholeInteractables(){
  CleanupWholeStageInteractables();if(ownsSpawnPointPrefab){typeof(SpawnPoint).GetField("prefab",BindingFlags.Static|BindingFlags.NonPublic).SetValue(null,priorSpawnPointPrefab);if(wholeSpawnPointLease.IsValid())Addressables.Release(wholeSpawnPointLease);ownsSpawnPointPrefab=false;}
 }
}
