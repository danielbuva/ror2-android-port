using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

// Original pools choose content. Android owns template activation and unavailable audio.
public sealed partial class MovementBatchProbe {
 readonly Dictionary<string,GameObject> wholeMasterTemplates=new Dictionary<string,GameObject>(StringComparer.Ordinal);
 readonly Dictionary<CharacterSpawnCard,CharacterSpawnCard> wholeSpawnCards=new Dictionary<CharacterSpawnCard,CharacterSpawnCard>();
 readonly List<AsyncOperationHandle> wholeStageLeases=new List<AsyncOperationHandle>();
 ClassicStageInfo wholeStageInfo;
 readonly Dictionary<FieldInfo,object> priorWholeDroneFields=new Dictionary<FieldInfo,object>();
 readonly Dictionary<DroneDef,object[]> priorWholeDroneDefinitions=new Dictionary<DroneDef,object[]>();
 Run wholeAvailabilityRun;DroneMask wholeAvailableDrones,wholeLockedDrones;KeyItemMask wholeAvailableKeyItems,wholeLockedKeyItems;
 AsyncOperationHandle<GameObject> wholeEquipmentOrbLease;GameObject priorWholeEquipmentOrb;int wholeEquipmentOrbReferences;bool ownsWholePickupOrb;
 System.Collections.IEnumerator PrepareWholePickups(){
  priorWholeEquipmentOrb=EquipmentDef.dropletDisplayPrefab;wholeEquipmentOrbLease=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/ItemPickups/EquipmentOrb");ownsWholePickupOrb=true;yield return wholeEquipmentOrbLease;
  Check(wholeEquipmentOrbLease.Status==AsyncOperationStatus.Succeeded&&wholeEquipmentOrbLease.Result,"Original equipment pickup presentation unavailable");
  wholeEquipmentOrbReferences=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(wholeEquipmentOrbLease);
  var native=PickupCatalog.Init();while(native.MoveNext())yield return native.Current;
  Check(EquipmentDef.dropletDisplayPrefab==wholeEquipmentOrbLease.Result,"Native pickup initializer changed equipment orb identity");
 }
 void CleanupWholePickups(){
  if(!ownsWholePickupOrb)return;EquipmentDef.SetDropletDisplayPrefab(priorWholeEquipmentOrb);
  if(wholeEquipmentOrbLease.IsValid()){
   int extra=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(wholeEquipmentOrbLease)-wholeEquipmentOrbReferences;
   Check(extra>=0&&extra<=1,"Unattributed native pickup initialization lease");if(extra==1)Addressables.Release(wholeEquipmentOrbLease.Result);Addressables.Release(wholeEquipmentOrbLease);
  }ownsWholePickupOrb=false;
 }
 void PrepareWholeDroneCatalog(){
  Check(DroneCatalog.droneCount==0&&priorWholeDroneFields.Count==0,"Foreign drone catalog owner");
  var fields=typeof(DroneCatalog).GetFields(BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);
  Check(((System.Collections.IDictionary)fields.Single(field=>field.Name=="nameToDroneIndex").GetValue(null)).Count==0,"Foreign drone index owner");
  foreach(var field in fields)if(!field.IsLiteral&&(field.FieldType.IsArray||field.FieldType==typeof(global::ResourceAvailability)))priorWholeDroneFields.Add(field,field.GetValue(null));
  var definitions=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.droneDef,new DroneDef[0]);
  foreach(var def in definitions)priorWholeDroneDefinitions.Add(def,new object[]{def.droneIndex,def.requiredExpansion});
  StaticCall(typeof(DroneCatalog),"SetDroneDefs",new object[]{definitions});DroneCatalog.availability.MakeAvailable();
  WholeCatalogComposed.PopulateDefinitionFields("DroneDefs",definitions);
  Check(definitions.All(def=>DroneCatalog.GetDroneDef(def.droneIndex)==def&&DroneCatalog.GetBodyIndexFromDroneIndex(def.droneIndex)!=BodyIndex.None),"Original drone catalog identity differs");
 }
 void PrepareWholeRunAvailability(){
  if(r.liveCatalogs==null)return;
  var run=Run.instance;Check(run&&run.availableDrones==null&&run.expansionLockedDrones==null&&run.availableKeyItems==null&&run.expansionLockedKeyItems==null,"Foreign drone/key-item availability owner");
  // Register key-item metadata before fixed-size masks and the native RuleCatalog.
  PrepareResultsKeyItems();wholeAvailabilityRun=run;
  wholeAvailableDrones=DroneMask.Rent();wholeLockedDrones=DroneMask.Rent();wholeAvailableKeyItems=KeyItemMask.Rent();wholeLockedKeyItems=KeyItemMask.Rent();
  run.availableDrones=wholeAvailableDrones;run.expansionLockedDrones=wholeLockedDrones;run.availableKeyItems=wholeAvailableKeyItems;run.expansionLockedKeyItems=wholeLockedKeyItems;
 }
 void RefreshWholeRunAvailability(){
  if(!wholeAvailabilityRun)return;
  var run=wholeAvailabilityRun;run.ruleBook.GenerateDroneMask(wholeAvailableDrones);run.ruleBook.GenerateKeyItemMask(wholeAvailableKeyItems);wholeLockedDrones.Clear();wholeLockedKeyItems.Clear();
  // Native rules retain every droppable family, including Lunar content. Currency
  // access is a separate purchase boundary; it must not create empty source tables.
  run.ruleBook.GenerateItemMask(worldAvailableItems);run.ruleBook.GenerateEquipmentMask(worldAvailableEquipment);
  foreach(var def in ItemCatalog.allItemDefs)if(def.hidden||(def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion))||(def.unlockableDef&&!run.IsUnlockableUnlocked(def.unlockableDef)))worldAvailableItems.Remove(def.itemIndex);
  foreach(var index in EquipmentCatalog.allEquipment){var def=EquipmentCatalog.GetEquipmentDef(index);if((def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion))||(def.unlockableDef&&!run.IsUnlockableUnlocked(def.unlockableDef)))worldAvailableEquipment.Remove(index);}
  foreach(var def in DroneCatalog.allDroneDefs)if(def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion)){wholeAvailableDrones.Remove(def.droneIndex);wholeLockedDrones.Add(def.droneIndex);}
  foreach(var def in KeyItemCatalog.allKeyItemDefs){if(def.requiredExpansion&&!run.IsExpansionEnabled(def.requiredExpansion)){wholeAvailableKeyItems.Remove(def.keyItemIndex);wholeLockedKeyItems.Add(def.keyItemIndex);}if(def.unlockableDef&&!run.IsUnlockableUnlocked(def.unlockableDef))wholeAvailableKeyItems.Remove(def.keyItemIndex);}
  run.BuildDropTable();
 }
 void CleanupWholeRunAvailability(){
  CleanupWholePickups();
  if(wholeAvailabilityRun){wholeAvailabilityRun.availableDrones=null;wholeAvailabilityRun.expansionLockedDrones=null;wholeAvailabilityRun.availableKeyItems=null;wholeAvailabilityRun.expansionLockedKeyItems=null;wholeAvailabilityRun=null;}
  if(wholeAvailableDrones!=null)DroneMask.Return(wholeAvailableDrones);if(wholeLockedDrones!=null)DroneMask.Return(wholeLockedDrones);if(wholeAvailableKeyItems!=null)KeyItemMask.Return(wholeAvailableKeyItems);if(wholeLockedKeyItems!=null)KeyItemMask.Return(wholeLockedKeyItems);
  wholeAvailableDrones=null;wholeLockedDrones=null;wholeAvailableKeyItems=null;wholeLockedKeyItems=null;
  if(priorWholeDroneFields.Count>0){StaticCall(typeof(DroneCatalog),"SetDroneDefs",new object[]{Array.Empty<DroneDef>()});foreach(var entry in priorWholeDroneDefinitions){entry.Key.droneIndex=(DroneIndex)entry.Value[0];entry.Key.requiredExpansion=(RoR2.ExpansionManagement.ExpansionDef)entry.Value[1];}foreach(var entry in priorWholeDroneFields)entry.Key.SetValue(null,entry.Value);priorWholeDroneDefinitions.Clear();priorWholeDroneFields.Clear();}
 }
 GameObject[] PrepareWholeMasterTemplates(GameObject[] originals,GameObject[] adapted){
  foreach(var value in adapted)wholeMasterTemplates.Add(value.name,value);
  foreach(var source in originals){
   if(wholeMasterTemplates.ContainsKey(source.name))continue;
   var originalMaster=source.GetComponent<CharacterMaster>();var originalBody=originalMaster.bodyPrefab;
   // Some shipped masters intentionally have no body. Preserve that source contract.
   if(!originalBody){wholeMasterTemplates.Add(source.name,source);continue;}
   var index=originalBody.GetComponent<CharacterBody>().bodyIndex;var bodyObject=BodyCatalog.GetBodyPrefab(index);
   if(!priorCatalogBodyTemplates.ContainsKey((int)index)){
    bodyObject=Instantiate(originalBody,enemyTemplates.transform);bodyObject.name=originalBody.name;bodyObject.SetActive(true);objectiveTemplates.Add(bodyObject);
    Check(bodyObject.GetComponentsInChildren<Component>(true).All(value=>value),"Whole actor has a missing serialized component: "+source.name);
    foreach(var behaviour in bodyObject.GetComponentsInChildren<MonoBehaviour>(true)){
     if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(behaviour);continue;}
     if(behaviour is RoR2.Networking.CharacterNetworkTransform||behaviour is InteractionDriver)behaviour.enabled=false;
    }
    foreach(var sfx in bodyObject.GetComponentsInChildren<SfxLocator>(true))foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Public|BindingFlags.Instance))if(field.FieldType==typeof(string))field.SetValue(sfx,null);
    BindCatalogBodyTemplate(bodyObject);
   }
   var masterObject=Instantiate(source,enemyTemplates.transform);masterObject.name=source.name;masterObject.GetComponent<CharacterMaster>().bodyPrefab=bodyObject;
   var inventory=masterObject.GetComponent<Inventory>();if(inventory)inventory.enabled=false;
   foreach(var behaviour in masterObject.GetComponentsInChildren<MonoBehaviour>(true))if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal))DestroyImmediate(behaviour);
   masterObject.SetActive(true);objectiveTemplates.Add(masterObject);wholeMasterTemplates.Add(source.name,masterObject);
  }
  return originals.Select(value=>wholeMasterTemplates[value.name]).ToArray();
 }
 CharacterSpawnCard WholeSpawnCard(CharacterSpawnCard source){
  CharacterSpawnCard copy;if(wholeSpawnCards.TryGetValue(source,out copy))return copy;
  GameObject master;Check(source.prefab&&wholeMasterTemplates.TryGetValue(source.prefab.name,out master),"Original spawn card master missing from complete catalog: "+source.name);
  copy=Instantiate(source);copy.name=source.name;copy.prefab=wholeMasterTemplates[source.prefab.name];wholeSpawnCards.Add(source,copy);return copy;
 }
 DirectorCardCategorySelection SelectWholeStagePool(string stage){
  CleanupWholeStagePool();var text=Resources.Load<TextAsset>("WholeStageContexts");Check(text,"Original stage context metadata absent");
  var contexts=JObject.Parse(text.text);var generation=JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);Check((string)contexts["input_id"]==(string)generation["input_id"],"Stage population input generation differs");
  var source=(JObject)contexts["stages"][stage];wholeStageContext=source;Check(source!=null,"Original stage context absent: "+stage);
  var info=SceneInfo.instance;Check(info&&!info.GetComponent<ClassicStageInfo>()&&!ClassicStageInfo.instance,"Stage context has a foreign population owner");
  // Add to the existing scene owner: RequireComponent must not create another SceneInfo.
  wholeStageInfo=info.gameObject.AddComponent<ClassicStageInfo>();wholeStageInfo.enabled=false;Call(wholeStageInfo,"OnEnable");
  foreach(var name in new[]{"monsterDccsPool","interactableDccsPool"}){
   var handle=Addressables.LoadAssetAsync<DccsPool>((string)source[name]);wholeStageLeases.Add(handle);var pool=handle.WaitForCompletion();Check(handle.Status==AsyncOperationStatus.Succeeded&&pool,"Original stage pool unavailable: "+stage+"/"+name);
   typeof(ClassicStageInfo).GetField(name,BindingFlags.Instance|BindingFlags.NonPublic).SetValue(wholeStageInfo,pool);
  }
  foreach(var property in ((JObject)source["fields"]).Properties()){
   var field=typeof(ClassicStageInfo).GetField(property.Name,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);Check(field!=null,"Original population field absent: "+property.Name);
   field.SetValue(wholeStageInfo,property.Value.ToObject(field.FieldType));
  }
  // Native Awake seeds this context; native RebuildCards owns mixing, family,
  // expansion, unlock and stage restrictions plus the master preload requests.
  Call(wholeStageInfo,"RebuildCards",new object[]{null,null});
  var selected=(DirectorCardCategorySelection)typeof(ClassicStageInfo).GetField("modifiableMonsterCategories",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(wholeStageInfo);Check(selected,"Original population selection returned no deck: "+stage);
  var deck=Instantiate(selected);
  var sourceCards=selected.categories.SelectMany(category=>category.cards).ToArray();
  var ownedCards=deck.categories.SelectMany(category=>category.cards).ToArray();
  var replacements=new Dictionary<DirectorCard,DirectorCard>();
  for(int i=0;i<sourceCards.Length;i++)replacements[sourceCards[i]]=ownedCards[i];
  foreach(var card in deck.categories.SelectMany(category=>category.cards)){
   var original=card.GetSpawnCard() as CharacterSpawnCard;Check(original,"Stage population contains a non-character card: "+stage);
   card.spawnCard=WholeSpawnCard(original);card.spawnCardReference=new AssetReferenceT<SpawnCard>("");
  }
  // Child directors without an explicit deck consume ClassicStageInfo's selection.
  // Preserve the native choices/weights; substitute only owned activation templates.
  var sharedSelection=new WeightedSelection<DirectorCard>();
  for(int i=0;i<wholeStageInfo.monsterSelection.Count;i++){
   var choice=wholeStageInfo.monsterSelection.GetChoice(i);sharedSelection.AddChoice(replacements[choice.value],choice.weight);
  }
  typeof(ClassicStageInfo).GetProperty("monsterSelection").GetSetMethod(true).Invoke(wholeStageInfo,new object[]{sharedSelection});
  return deck;
 }
 void CleanupWholeStagePool(){
  if(wholeStageInfo){Call(wholeStageInfo,"OnDisable");Call(wholeStageInfo,"OnDestroy");if(wholeStageInfo.interactableCategories)Destroy(wholeStageInfo.interactableCategories);Destroy(wholeStageInfo);wholeStageInfo=null;}
  foreach(var lease in wholeStageLeases)if(lease.IsValid())Addressables.Release(lease);wholeStageLeases.Clear();
 }
 void CleanupWholePopulation(){
  CleanupWholeInteractables();CleanupWholeStagePool();CleanupWholeRunAvailability();foreach(var card in wholeSpawnCards.Values)if(card)Destroy(card);wholeSpawnCards.Clear();wholeMasterTemplates.Clear();
 }
}
