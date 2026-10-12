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
  var source=(JObject)contexts["stages"][stage];Check(source!=null,"Original stage context absent: "+stage);
  var info=SceneInfo.instance;Check(info&&!info.GetComponent<ClassicStageInfo>(),"Stage context has a foreign population owner");
  // Add to the existing scene owner: RequireComponent must not create another SceneInfo.
  wholeStageInfo=info.gameObject.AddComponent<ClassicStageInfo>();wholeStageInfo.enabled=false;
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
  foreach(var card in deck.categories.SelectMany(category=>category.cards)){
   var original=card.GetSpawnCard() as CharacterSpawnCard;Check(original,"Stage population contains a non-character card: "+stage);
   card.spawnCard=WholeSpawnCard(original);card.spawnCardReference=new AssetReferenceT<SpawnCard>("");
  }
  return deck;
 }
 void CleanupWholeStagePool(){
  if(wholeStageInfo){Call(wholeStageInfo,"OnDestroy");Destroy(wholeStageInfo);wholeStageInfo=null;}
  foreach(var lease in wholeStageLeases)if(lease.IsValid())Addressables.Release(lease);wholeStageLeases.Clear();
 }
 void CleanupWholePopulation(){
  CleanupWholeStagePool();foreach(var card in wholeSpawnCards.Values)if(card)Destroy(card);wholeSpawnCards.Clear();wholeMasterTemplates.Clear();
 }
}
