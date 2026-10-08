using System;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using UnityEngine;

// Source attachment rules and original CharacterModel factories; owned Android lifecycle/materials.
public sealed partial class MovementBatchProbe {
 [Serializable] public class ItemDisplayObservation {public string item,parent;public int instances;public Vector3 localPosition,localScale;}
 [Serializable] public class WorldItemDisplayReport {public bool ready,cleaned;public int groups,rules,itemInstances,equipmentInstances,updates;public string error,scope="Original eligible Commando display rules, attachment transforms and native item/equipment factories. Owned inventory callback and Android material copies; no exact PC pose/material parity or stock camera/highlight acceptance.";public List<ItemDisplayObservation> objects=new List<ItemDisplayObservation>();}
 CharacterBody worldDisplayBody;CharacterModel worldDisplayModel;ItemDisplayRuleSet worldDisplayRules,worldDisplayPriorRules;Action worldDisplayInventoryChanged;
 readonly HashSet<GameObject> worldDisplayInstances=new HashSet<GameObject>();
 void PrepareWorldItemDisplays(CharacterBody body,Result cfg){
  if(!cfg.worldItemDisplays)return;
  Check(!worldDisplayModel&&!worldDisplayRules&&worldDisplayInventoryChanged==null,"Existing owned item display context");
  worldDisplayBody=body;worldDisplayModel=body.modelLocator.modelTransform.GetComponent<CharacterModel>();
  Check(worldDisplayModel&&worldDisplayModel.body==body&&!worldDisplayModel.enabled&&worldDisplayModel.itemDisplayRuleSet,"Original disabled model/display rule context absent");
  worldDisplayPriorRules=worldDisplayModel.itemDisplayRuleSet;worldDisplayRules=Instantiate(worldDisplayPriorRules);
  var eligible=worldLootDefinitions.Cast<UnityEngine.Object>().Concat(EligibleWorldEquipment().Cast<UnityEngine.Object>()).ToArray();
  worldDisplayRules.keyAssetRuleGroups=worldDisplayRules.keyAssetRuleGroups.Where(group=>eligible.Contains(group.keyAsset)).ToArray();
  Check(worldDisplayRules.keyAssetRuleGroups.Length==eligible.Length&&worldDisplayRules.keyAssetRuleGroups.Select(group=>group.keyAsset).Distinct().Count()==eligible.Length,"Original eligible display identity/coverage differs from measured source contract");
  foreach(var group in worldDisplayRules.keyAssetRuleGroups){
   Check(group.keyAsset&&(!(group.keyAssetAddress?.RuntimeKeyIsValid()??false)),"Unresolved display key address");
   foreach(var rule in group.displayRuleGroup.rules??new ItemDisplayRule[0])if(rule.ruleType==ItemDisplayRuleType.ParentedPrefab)
    Check(rule.followerPrefab&&!(rule.followerPrefabAddress?.RuntimeKeyIsValid()??false)&&worldDisplayModel.GetComponent<ChildLocator>().FindChild(rule.childName),"Original display prefab/parent contract absent");
  }
  var generation=worldDisplayRules.GenerateRuntimeValuesAsync();Check(!generation.MoveNext(),"Direct source display rules yielded an unresolved request");worldDisplayModel.itemDisplayRuleSet=worldDisplayRules;
  r.itemDisplays=new WorldItemDisplayReport{groups=worldDisplayRules.keyAssetRuleGroups.Length,rules=worldDisplayRules.keyAssetRuleGroups.Sum(group=>(group.displayRuleGroup.rules??new ItemDisplayRule[0]).Length)};
  var native=(Action)Delegate.CreateDelegate(typeof(Action),worldDisplayModel,typeof(CharacterModel).GetMethod("OnInventoryChanged",BindingFlags.NonPublic|BindingFlags.Instance));
  worldDisplayInventoryChanged=()=>{try{native();PresentWorldItemDisplays();r.itemDisplays.updates++;}catch(Exception error){r.itemDisplays.error=error.ToString();Save();}};
  body.onInventoryChanged+=worldDisplayInventoryChanged;worldDisplayInventoryChanged();Check(string.IsNullOrEmpty(r.itemDisplays.error),"Original item display initialization failed: "+r.itemDisplays.error);r.itemDisplays.ready=true;
 }
 void PresentWorldItemDisplays(){
  var rows=new List<ItemDisplayObservation>();int items=0,equipment=0;
  foreach(var group in worldDisplayRules.keyAssetRuleGroups){
   var item=group.keyAsset as ItemDef;var equip=group.keyAsset as EquipmentDef;
   var instances=item?worldDisplayModel.GetItemDisplayObjects(item.itemIndex):worldDisplayModel.GetEquipmentDisplayObjects(equip.equipmentIndex);
   if(item)items+=instances.Count;else equipment+=instances.Count;
   foreach(var obj in instances){
    Check(obj&&obj.GetComponent<ItemDisplay>(),"Original display factory produced missing ItemDisplay");
    if(worldDisplayInstances.Add(obj)){PresentCommerceModel(obj.transform);var display=obj.GetComponent<ItemDisplay>();for(int i=0;i<display.rendererInfos.Length;i++){var renderer=display.rendererInfos[i].renderer;if(renderer)display.rendererInfos[i].defaultMaterial=renderer.sharedMaterial;}}
    rows.Add(new ItemDisplayObservation{item=group.keyAsset.name,instances=instances.Count,parent=obj.transform.parent.name,localPosition=obj.transform.localPosition,localScale=obj.transform.localScale});
   }
  }
  r.itemDisplays.itemInstances=items;r.itemDisplays.equipmentInstances=equipment;r.itemDisplays.objects=rows;
 }
 void ObserveWorldItemDisplays(){if(r.itemDisplays==null)return;Check(string.IsNullOrEmpty(r.itemDisplays.error),"Original item display callback failed: "+r.itemDisplays.error);}
 void CleanupWorldItemDisplays(){
  if(worldDisplayBody&&worldDisplayInventoryChanged!=null)worldDisplayBody.onInventoryChanged-=worldDisplayInventoryChanged;worldDisplayInventoryChanged=null;
  if(worldDisplayModel){worldDisplayModel.DisableAllItemDisplays();Call(worldDisplayModel,"SetEquipmentDisplay",EquipmentIndex.None);worldDisplayModel.itemDisplayRuleSet=worldDisplayPriorRules;}
  if(worldDisplayRules)Destroy(worldDisplayRules);worldDisplayRules=null;worldDisplayPriorRules=null;worldDisplayModel=null;worldDisplayBody=null;
  if(r.itemDisplays!=null)r.itemDisplays.cleaned=true;worldDisplayInstances.Clear();
 }
}
