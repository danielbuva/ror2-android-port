using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;

// Supplies eligible shipped equipment content and input/lifecycle scheduling.
// Original grants, activation dispatch, buffs, healing and cooldowns execute unchanged.
public sealed partial class MovementBatchProbe {
 [Serializable] public class EquipmentActionObservation {public string equipment;public float seconds,health,armor,crit;public int stock;}
 [Serializable] public class WorldEquipmentReport {
  public bool ready,cleaned;public string equipment,error,scope="Original equipment pickup/activation/cooldown; owned input/scheduling, source presentation approximation, no stock profile unlocks.";
  public int definitions,eligible,stock,maxStock,ticks,activations,ammoPacks;public float cooldown;
  public List<EquipmentActionObservation> actions=new List<EquipmentActionObservation>();
  public ObjectiveRendererObservation[] temporaryEffectViews;
 }
 Action worldEquipmentFixed,worldEquipmentInventoryFixed;Action<EquipmentSlot,EquipmentIndex> worldEquipmentActivated;
 readonly List<ChestBehavior> worldEquipmentChests=new List<ChestBehavior>();
 EquipmentDef[] worldEquipmentDefinitions;EquipmentSlot worldEquipmentSlot;float equipmentLastInput=-100;bool worldEquipmentTouch;NovaInputBridge worldEquipmentBridge;
 EquipmentDef[] WorldEquipmentDefs(Result cfg){
  if(cfg.worldEquipmentAssets==null||cfg.worldEquipmentAssets.Length==0)return new EquipmentDef[0];
  var names=new[]{"Fruit","CritOnUse","GainArmor","LifestealOnHit","GoldGat","PassiveHealing","CommandMissile","Saw","Blackhole","TeamWarCry"};
  Check(cfg.worldEquipmentAssets.Length==names.Length,"Equipment source context differs");
  worldEquipmentDefinitions=cfg.worldEquipmentAssets.Select(x=>artifactBundle.LoadAsset<EquipmentDef>(x)).ToArray();
  for(int i=0;i<names.Length;i++){var def=worldEquipmentDefinitions[i];Check(def&&def.name==names[i],"Original equipment definition missing: "+names[i]);BindEnemyDefinition(typeof(RoR2Content.Equipment),names[i],def);if(i<4||i>=6)Check(!def.unlockableDef&&!def.requiredExpansion&&def.canDrop&&!def.isLunar&&!def.isBoss,"Equipment requires unavailable ownership/profile: "+names[i]);}
  return worldEquipmentDefinitions;
 }
 BuffDef[] WorldEquipmentBuffs(Result cfg){
  if(cfg.worldEquipmentBuffAssets==null||cfg.worldEquipmentBuffAssets.Length==0)return new BuffDef[0];
  var names=new[]{"FullCrit","ElephantArmorBoost","LifeSteal","TeamWarCry"};Check(cfg.worldEquipmentBuffAssets.Length==names.Length,"Equipment buff context differs");
  var defs=cfg.worldEquipmentBuffAssets.Select(x=>artifactBundle.LoadAsset<BuffDef>(x)).ToArray();
  for(int i=0;i<names.Length;i++){Check(defs[i]&&defs[i].name=="bd"+names[i],"Original equipment buff missing");BindEnemyDefinition(typeof(RoR2Content.Buffs),names[i],defs[i]);}return defs;
 }
 IEnumerable<EquipmentDef> EligibleWorldEquipment(){return (worldEquipmentDefinitions??new EquipmentDef[0]).Where(x=>x.name!="GoldGat"&&x.name!="PassiveHealing");}
 GameObject[] PrepareWorldEquipmentSupport(Result cfg){
  if(cfg.worldEquipmentSupportPaths==null||cfg.worldEquipmentSupportPaths.Length==0)return new GameObject[0];
  Check(cfg.worldEquipmentSupportPaths.Length==10,"Equipment/proc provider closure differs");var effects=new List<GameObject>();
  foreach(var path in cfg.worldEquipmentSupportPaths){
   int i=Array.IndexOf(cfg.objectiveSupportPaths,path);Check(i>=0,"Equipment/proc provider missing: "+path);var source=objectiveSupportSources[i];Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Equipment/proc source reference missing: "+path);
   worldNativeLootLeaseBaselines.Add(i,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[i]));
   if(source.GetComponent<EffectComponent>()){source.GetComponent<EffectComponent>().soundName=null;effects.Add(source);}
   else if(source.GetComponent<RoR2.Projectile.ProjectileController>()!=null){
    var controller=source.GetComponent<RoR2.Projectile.ProjectileController>();Check((controller.ghostPrefab||(source.name=="GravSphere"&&source.GetComponentsInChildren<Renderer>(true).Length>0))&&source.GetComponent<UnityEngine.Networking.NetworkIdentity>(),"Original equipment projectile/network contract absent");
    var roots=new List<GameObject>{source};if(controller.ghostPrefab)roots.Add(controller.ghostPrefab);foreach(var component in source.GetComponents<Component>())foreach(var field in component.GetType().GetFields(BindingFlags.Public|BindingFlags.Instance)){if(field.FieldType!=typeof(GameObject))continue;var effect=field.GetValue(component) as GameObject;if(effect&&effect.GetComponent<EffectComponent>()){roots.Add(effect);effects.Add(effect);}}
    foreach(var root in roots.Distinct()){foreach(var renderer in root.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}PresentCommerceModel(root.transform);}
   }
   else if(source.name=="AmmoPack"){var pickup=source.GetComponentInChildren<AmmoPickup>(true);Check(pickup&&pickup.baseObject==source&&pickup.teamFilter&&source.GetComponent<UnityEngine.Networking.NetworkIdentity>()&&pickup.pickupEffect,"Original ammo pickup linkage missing");effects.Add(pickup.pickupEffect);}
   else {
    Check(source.GetComponent<TemporaryVisualEffect>(),"Unknown equipment support source: "+path);var field=typeof(CharacterBody).GetNestedType("AssetReferences",BindingFlags.NonPublic).GetField(source.name=="ElephantDefense"?"elephantDefenseEffectPrefab":source.name=="TeamWarCryAura"?"teamWarCryEffectPrefab":"lifestealOnHitEffectPrefab",BindingFlags.Public|BindingFlags.Static);Check(field!=null&&field.GetValue(null)==null,"Unowned equipment visual context");worldLootEffectSlots.Add(field,null);field.SetValue(null,source);
    // These prefabs bypass EffectCatalog; bind the same source-driven programs
    // before original CharacterBody creates their native temporary instances.
    foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
    PresentCommerceModel(source.transform);
   }
  }
  foreach(var source in effects.Distinct()){Check(source.GetComponent<EffectComponent>(),"Equipment/proc effect identity absent");source.GetComponent<EffectComponent>().soundName=null;}
  return effects.Distinct().ToArray();
 }
 void PrepareWorldEquipment(CharacterBody player,Result cfg){
  if(worldEquipmentDefinitions==null)return;
  r.world.equipment=new WorldEquipmentReport{definitions=worldEquipmentDefinitions.Length,eligible=EligibleWorldEquipment().Count()};worldEquipmentSlot=player.equipmentSlot;
  Check(worldEquipmentSlot&&!worldEquipmentSlot.enabled&&worldEquipmentSlot.equipmentIndex==EquipmentIndex.None,"Unowned equipment scheduler");
  Call(worldEquipmentSlot,"UpdateAuthority");Check((bool)typeof(EquipmentSlot).GetField("hasEffectiveAuthority",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(worldEquipmentSlot),"Original equipment authority missing");
  worldEquipmentFixed=(Action)Delegate.CreateDelegate(typeof(Action),worldEquipmentSlot,typeof(EquipmentSlot).GetMethod("FixedUpdate",BindingFlags.Instance|BindingFlags.NonPublic));
  if(!player.inventory.isActiveAndEnabled)worldEquipmentInventoryFixed=(Action)Delegate.CreateDelegate(typeof(Action),player.inventory,typeof(Inventory).GetMethod("FixedUpdate",BindingFlags.Instance|BindingFlags.NonPublic));
  worldEquipmentActivated=(slot,index)=>{if(slot!=worldEquipmentSlot)return;var def=EquipmentCatalog.GetEquipmentDef(index);Check(EligibleWorldEquipment().Contains(def),"Unsupported equipment activated");r.world.equipment.activations++;r.world.equipment.actions.Add(new EquipmentActionObservation{equipment=def.name,seconds=Run.instance.GetRunStopwatch(),stock=slot.stock,health=player.healthComponent.health,armor=player.armor,crit=player.crit});};EquipmentSlot.onServerEquipmentActivated+=worldEquipmentActivated;r.world.equipment.ready=true;
 }
 void TickWorldEquipment(){
  if(worldEquipmentFixed==null||!worldPlayer||!worldPlayer.healthComponent.alive)return;
  try{if(worldEquipmentInventoryFixed!=null)worldEquipmentInventoryFixed();worldEquipmentFixed();r.world.equipment.ticks++;}
  catch(Exception e){r.world.equipment.error=e.ToString();worldEquipmentFixed=null;Save();}
 }
 void ObserveWorldEquipment(){
  var report=r.world.equipment;if(report==null)return;Check(string.IsNullOrEmpty(report.error),"Original equipment lifecycle failed: "+report.error);
  var def=EquipmentCatalog.GetEquipmentDef(worldEquipmentSlot.equipmentIndex);report.equipment=def?def.name:"";report.stock=worldEquipmentSlot.stock;report.maxStock=worldEquipmentSlot.maxStock;report.cooldown=worldEquipmentSlot.cooldownTimer;
  foreach(var fieldName in new[]{"elephantDefenseEffectInstance","lifestealOnHitEffectInstance","teamWarCryEffectInstance"}){var effect=(TemporaryVisualEffect)typeof(CharacterBody).GetField(fieldName,BindingFlags.Instance|BindingFlags.NonPublic).GetValue(worldPlayer);if(effect&&!worldLootTemporaryEffects.Contains(effect.gameObject)){worldLootTemporaryEffects.Add(effect.gameObject);report.temporaryEffectViews=effect.GetComponentsInChildren<Renderer>(true).Select(ObserveOwnedSurface).ToArray();}}
  foreach(var pickup in Resources.FindObjectsOfTypeAll<AmmoPickup>().Where(x=>x.gameObject.scene.IsValid()))if(worldNativeLootObjects.Add(pickup.baseObject)){worldObjects.Add(pickup.baseObject);report.ammoPacks++;}
 }
 void WorldEquipmentStimulus(NovaInputBridge bridge,float elapsed){
  bridge.diagnosticEquipment=false;if(r.world.equipment==null)return;
  if(worldEquipmentSlot.stock>0&&worldEquipmentSlot.equipmentIndex!=EquipmentIndex.None&&elapsed-equipmentLastInput>45){bridge.diagnosticEquipment=true;equipmentLastInput=elapsed;}
 }
 void CleanupWorldEquipment(){
  worldEquipmentFixed=null;worldEquipmentInventoryFixed=null;worldEquipmentTouch=false;worldEquipmentChests.Clear();equipmentLastInput=-100;
  if(worldEquipmentActivated!=null)EquipmentSlot.onServerEquipmentActivated-=worldEquipmentActivated;worldEquipmentActivated=null;worldEquipmentDefinitions=null;worldEquipmentSlot=null;worldEquipmentBridge=null;if(r.world!=null&&r.world.equipment!=null)r.world.equipment.cleaned=true;
 }
 void AddEquipmentBarrel(Result cfg,Vector3 origin){
  if(string.IsNullOrEmpty(cfg.worldEquipmentChestAsset))return;var source=artifactBundle.LoadAsset<GameObject>(cfg.worldEquipmentChestAsset);Check(source&&source.name=="EquipmentBarrel","Original equipment barrel absent");var chest=source.GetComponent<ChestBehavior>();Check(chest&&chest.dropTable&&Run.instance.availableEquipmentDropList.Count==EligibleWorldEquipment().Count(),"Original equipment loot domain absent");var table=chest.dropTable as BasicPickupDropTable;Check(table,"Equipment source drop table type differs");table.RegenerateDropTable(Run.instance);Check(chest.dropTable.GetPickupCount()==EligibleWorldEquipment().Count(),"Source equipment table mismatch");OwnChestAnimationSources(source.GetComponent<ModelLocator>().modelTransform,"EquipmentBarrelArmature|Open");foreach(var offset in new[]{new Vector3(-8,0,4),new Vector3(8,0,4)}){var obj=CreateWorldInteractable(source,origin+offset,true);if(obj){var owned=obj.GetComponent<ChestBehavior>();worldChests.Add(owned);worldEquipmentChests.Add(owned);}}
 }
 ChestBehavior NextAutomaticWorldChest(CharacterBody player){
  // Diagnostic route chooses a normal purchase; it never grants equipment or bypasses cost.
  if(player.inventory.currentEquipmentIndex==EquipmentIndex.None){var equipment=worldEquipmentChests.FirstOrDefault(x=>x&&!x.NetworkisChestOpened);if(equipment)return equipment;}
  return worldChests.FirstOrDefault(x=>x&&!x.NetworkisChestOpened&&!worldEquipmentChests.Contains(x));
 }
 void DrawWorldEquipment(){
  if(r.world.equipment==null)return;
  if(GUI.Button(new Rect(Screen.width-205,Screen.height-180,185,45),"Use equipment")){if(worldEquipmentBridge)worldEquipmentBridge.touchEquipment=true;}
 }
}
