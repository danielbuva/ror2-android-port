using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Items;
using UnityEngine;
using UnityEngine.Networking;

// Scoped startup adapter; component assignment, stack refresh and simulation are native.
public sealed partial class MovementBatchProbe {
 [Serializable] public class ItemBehaviorReport {
  public bool ready,cleaned;public int bodies,assignments,refreshes,mushroomWards,cloakObservations;public string[] definitions;
  public List<LegendaryItemObservation> legendaryInstances=new List<LegendaryItemObservation>();
  public string scope="Adapted inventory lifecycle using original item associations; original ward/healing/recharge/controller logic. Registration alone is not proc acceptance.";
 }
 readonly Dictionary<CharacterBody,BaseItemBodyBehavior[]> worldItemBehaviors=new Dictionary<CharacterBody,BaseItemBodyBehavior[]>();
 readonly HashSet<GameObject> worldMushroomWards=new HashSet<GameObject>();
 Type[] worldItemBehaviorTypes={typeof(MushroomBodyBehavior),typeof(PhasingBodyBehavior)};
 ItemDef[] worldItemBehaviorDefinitions;
 bool ownsWorldItemBehaviors,ownsWorldMushroomBinding;object previousWorldMushroom;
 static FieldInfo MushroomPrefabField(){return typeof(MushroomBodyBehavior).GetField("mushroomWardPrefab",BindingFlags.NonPublic|BindingFlags.Static);}
 BuffDef[] WorldItemBehaviorBuffs(Result cfg){
  if(cfg.worldItemBehaviorBuffAssets==null)return new BuffDef[0];
  var names=new[]{"Cloak","CloakSpeed"};if(cfg.worldAdditionalLootItems!=null&&cfg.worldAdditionalLootItems.Contains("LaserTurbine"))names=names.Concat(new[]{"LaserTurbineKillCharge"}).ToArray();Check(cfg.worldItemBehaviorBuffAssets.Length==names.Length,"Original item-behavior buff closure differs");
  return cfg.worldItemBehaviorBuffAssets.Select((path,i)=>{var def=artifactBundle.LoadAsset<BuffDef>(path);Check(def&&def.name=="bd"+names[i],"Original stealth buff missing");BindEnemyDefinition(typeof(RoR2Content.Buffs),names[i],def);return def;}).ToArray();
 }
 GameObject[] PrepareWorldItemBehaviorSupport(Result cfg){
  if(cfg.worldItemBehaviorBuffAssets==null)return new GameObject[0];var effects=new List<GameObject>();
  foreach(var path in new[]{"Prefabs/NetworkedObjects/MushroomWard","Prefabs/Effects/ProcStealthkit"}){
   int i=Array.IndexOf(cfg.objectiveSupportPaths,path);Check(i>=0,"Original item-behavior provider absent: "+path);var source=objectiveSupportSources[i];Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original item-behavior references absent");
   if(source.name=="MushroomWard"){
    Check(source.GetComponent<HealingWard>()&&source.GetComponent<TeamFilter>()&&source.GetComponent<NetworkIdentity>(),"Original Mushroom ward contract absent");previousWorldMushroom=MushroomPrefabField().GetValue(null);Check(previousWorldMushroom==null,"Unowned original Mushroom binding");ownsWorldMushroomBinding=true;MushroomPrefabField().SetValue(null,source);
   }else{Check(source.name=="ProcStealthkit"&&source.GetComponent<EffectComponent>(),"Original stealth effect absent");effects.Add(source);worldNativeLootLeaseBaselines.Add(i,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[i]));}
   foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
   PresentCommerceModel(source.transform);
  }
  return effects.ToArray();
 }
 void PrepareWorldItemBehaviors(Result cfg){
  if(cfg.worldItemBehaviorBuffAssets==null)return;
  Check(NetworkServer.active,"Original item-behavior adapter requires active original server");
  var nativeBodies=(System.Collections.IDictionary)typeof(BaseItemBodyBehavior).GetField("bodyToItemBehaviors",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
  var context=typeof(BaseItemBodyBehavior).GetField("server",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
  Check(nativeBodies.Count==0&&context.GetType().GetField("itemTypePairs").GetValue(context)==null,"Native item-behavior lifecycle already initialized; refuse duplicate adapter");
  Check(MushroomPrefabField().GetValue(null)!=null&&RoR2Content.Items.Mushroom&&RoR2Content.Items.Phasing,"Original item behavior inputs absent");
  var types=new List<Type>{typeof(MushroomBodyBehavior),typeof(PhasingBodyBehavior)};var defs=new List<ItemDef>{RoR2Content.Items.Mushroom,RoR2Content.Items.Phasing};
  var names=new[]{"FallBoots","Icicle","LaserTurbine"};var nativeTypes=new[]{typeof(HeadstomperBodyBehavior),typeof(IcicleBodyBehavior),typeof(LaserTurbineBodyBehavior)};
  for(int i=0;i<names.Length;i++)if(cfg.worldAdditionalLootItems!=null&&cfg.worldAdditionalLootItems.Contains(names[i])){var def=ItemCatalog.GetItemDef(ItemCatalog.FindItemIndex(names[i]));Check(def&&!def.unlockableDef&&!def.requiredExpansion,"Original legendary item unavailable: "+names[i]);types.Add(nativeTypes[i]);defs.Add(def);}
  if(cfg.stagePopulationFamilies!=null&&cfg.stagePopulationFamilies.Contains("Vagrant")){var def=RoR2Content.Items.NovaOnLowHealth;Check(def&&!def.unlockableDef&&!def.requiredExpansion&&def.tier==ItemTier.Boss,"Original Vagrant boss item unavailable");types.Add(typeof(NovaOnLowHealthBodyBehavior));defs.Add(def);}
  if(cfg.integratedWorld&&Resources.Load<TextAsset>("WholeCatalogBootstrap")){
   types.Clear();defs.Clear();
   foreach(var method in typeof(CharacterBody).Assembly.GetTypes().SelectMany(type=>type.GetMethods(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static|BindingFlags.DeclaredOnly))){
    var association=(BaseItemBodyBehavior.ItemDefAssociationAttribute)Attribute.GetCustomAttribute(method,typeof(BaseItemBodyBehavior.ItemDefAssociationAttribute));
    if(association==null||!(NetworkServer.active&&association.useOnServer||NetworkClient.active&&association.useOnClient))continue;
    var type=association.behaviorTypeOverride??method.DeclaringType;
    Check(typeof(BaseItemBodyBehavior).IsAssignableFrom(type)&&!type.IsAbstract&&method.GetParameters().Length==0&&!method.IsGenericMethod&&method.ReturnType==typeof(ItemDef),"Original item-behavior association signature differs: "+method.Name);
    var def=(ItemDef)method.Invoke(null,null);Check(def&&def.itemIndex!=ItemIndex.None&&ItemCatalog.GetItemDef(def.itemIndex)==def,"Original item-behavior association is unregistered: "+type.FullName);
    types.Add(type);defs.Add(def);
   }
   Check(types.Count>0&&types.Distinct().Count()==types.Count,"Original item-behavior association family ambiguous");
  }
  worldItemBehaviorTypes=types.ToArray();worldItemBehaviorDefinitions=defs.ToArray();r.itemBehaviors=new ItemBehaviorReport{ready=true,definitions=defs.Select(x=>x.name).ToArray()};ownsWorldItemBehaviors=true;
  CharacterBody.onBodyInventoryChangedGlobal+=RefreshWorldItemBehaviors;CharacterBody.onBodyDestroyGlobal+=RemoveWorldItemBehaviors;
  foreach(var body in CharacterBody.readOnlyInstancesList.ToArray())if(body&&body.gameObject.activeInHierarchy)RefreshWorldItemBehaviors(body);
 }
 void RefreshWorldItemBehaviors(CharacterBody body){
  if(!ownsWorldItemBehaviors||!body||!body.gameObject.activeInHierarchy)return;
  BaseItemBodyBehavior[] entries;if(!worldItemBehaviors.TryGetValue(body,out entries)){entries=new BaseItemBodyBehavior[worldItemBehaviorTypes.Length];worldItemBehaviors.Add(body,entries);r.itemBehaviors.bodies++;}
  var defs=worldItemBehaviorDefinitions;var setter=typeof(BaseItemBodyBehavior).GetMethod("SetItemStack",BindingFlags.NonPublic|BindingFlags.Static);
  for(int i=0;i<entries.Length;i++){var before=entries[i];var args=new object[]{body,entries[i],worldItemBehaviorTypes[i],body.inventory?body.inventory.GetItemCountEffective(defs[i]):0};setter.Invoke(null,args);entries[i]=(BaseItemBodyBehavior)args[1];if(!before&&entries[i])r.itemBehaviors.assignments++;Check(!entries[i]||entries[i].body==body,"Original item-behavior body assignment differs");}r.itemBehaviors.refreshes++;
 }
 void RemoveWorldItemBehaviors(CharacterBody body){BaseItemBodyBehavior[] entries;if(!worldItemBehaviors.TryGetValue(body,out entries))return;foreach(var entry in entries)if(entry)Destroy(entry);worldItemBehaviors.Remove(body);}
 void ObserveWorldItemBehaviors(){
  if(!ownsWorldItemBehaviors)return;
  foreach(var pair in worldItemBehaviors.ToArray()){
   if(!pair.Key){worldItemBehaviors.Remove(pair.Key);continue;}
   if(pair.Key.HasBuff(RoR2Content.Buffs.Cloak))r.itemBehaviors.cloakObservations++;
   int mushroom=Array.IndexOf(worldItemBehaviorTypes,typeof(MushroomBodyBehavior));var behavior=mushroom<0?null:pair.Value[mushroom];if(!behavior)continue;var obj=(GameObject)typeof(MushroomBodyBehavior).GetField("mushroomWardGameObject",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(behavior);
   if(obj&&worldMushroomWards.Add(obj)){var ward=obj.GetComponent<HealingWard>();Check(ward&&ward.netId.Value!=0&&obj.GetComponent<TeamFilter>().teamIndex==pair.Key.teamComponent.teamIndex,"Native Mushroom ward authority/team differs");r.itemBehaviors.mushroomWards++;worldObjects.Add(obj);}
  }
 }
 void CleanupWorldItemBehaviors(){
  if(ownsWorldItemBehaviors){CharacterBody.onBodyInventoryChangedGlobal-=RefreshWorldItemBehaviors;CharacterBody.onBodyDestroyGlobal-=RemoveWorldItemBehaviors;ownsWorldItemBehaviors=false;
   foreach(var body in worldItemBehaviors.Keys.ToArray())RemoveWorldItemBehaviors(body);foreach(var ward in worldMushroomWards)if(ward)NetworkServer.Destroy(ward);worldMushroomWards.Clear();r.itemBehaviors.cleaned=true;
  }
  if(ownsWorldMushroomBinding){MushroomPrefabField().SetValue(null,previousWorldMushroom);ownsWorldMushroomBinding=false;}
 }
}
