using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Bind shipped DOT content; original catalog, stacks, ticks and damage stay native.
public sealed partial class MovementBatchProbe {
 [Serializable] public class DotObservation {public string type;public int inflictions,damageEvents;public float damage;}
 [Serializable] public class WorldDotReport {
  public bool ready,cleaned;public int definitions,daggerSpawns,peakControllers;
  public string scope="Original bleed/burn/dagger dependencies. Other DOT buffs are comparison identities only, without expansion or unlock grants. Registration is not proc acceptance; audio unavailable.";
  public List<DotObservation> observations=new List<DotObservation>();
 }
 object previousWorldDotDefs;bool ownsWorldDots;BurnEffectController.EffectParams previousWorldBurn;
 DotController.OnDotInflictedServerGlobalDelegate worldDotInflicted;Action<DamageReport> worldDotDamage;
 readonly List<GameObject> worldDotPoolSources=new List<GameObject>();
 BuffDef[] WorldDotBuffs(Result cfg){
  if(cfg.worldDotBuffAssets==null||cfg.worldDotBuffAssets.Length==0)return new BuffDef[0];
  var names=new[]{"Bleeding","OnFire","Poisoned","Blight","SuperBleed","StrongerBurn","Fracture","lunarruin","Frost","Electrocuted"};
  var owners=new[]{typeof(RoR2Content.Buffs),typeof(RoR2Content.Buffs),typeof(RoR2Content.Buffs),typeof(RoR2Content.Buffs),typeof(RoR2Content.Buffs),typeof(DLC1Content.Buffs),typeof(DLC1Content.Buffs),typeof(DLC2Content.Buffs),typeof(DLC2Content.Buffs),typeof(DLC3Content.Buffs)};
  Check(cfg.worldDotBuffAssets.Length==names.Length,"Original DOT comparison closure differs");
  return cfg.worldDotBuffAssets.Select((path,i)=>{var def=artifactBundle.LoadAsset<BuffDef>(path);Check(def&&def.name=="bd"+names[i],"Original DOT buff missing: "+names[i]);BindEnemyDefinition(owners[i],names[i],def);return def;}).ToArray();
 }
 DotObservation WorldDotRow(DotController.DotIndex index){
  var name=index.ToString();var row=r.dots.observations.FirstOrDefault(x=>x.type==name);
  if(row==null){row=new DotObservation{type=name};r.dots.observations.Add(row);}return row;
 }
 GameObject[] PrepareWorldDotSupport(Result cfg){
  if(cfg.worldDotBuffAssets==null||cfg.worldDotBuffAssets.Length==0)return new GameObject[0];
  var field=typeof(DotController).GetField("dotDefs",BindingFlags.Static|BindingFlags.NonPublic);previousWorldDotDefs=field.GetValue(null);
  Check(previousWorldDotDefs==null&&DotController.readOnlyInstancesList.Count==0&&BurnEffectController.normalEffect==null,"Unowned original DOT context");
  ownsWorldDots=true;StaticCall(typeof(DotController),"InitDotCatalog");
  var defs=(Array)field.GetValue(null);Check(defs!=null&&defs.Length==(int)DotController.DotIndex.Count,"Original DOT catalog initialization differs");
  foreach(DotController.DotIndex index in Enum.GetValues(typeof(DotController.DotIndex))){if(index<DotController.DotIndex.Bleed||index>=DotController.DotIndex.Count)continue;var def=DotController.GetDotDef(index);Check(def!=null&&def.interval>0&&(!def.associatedBuff||BuffCatalog.GetBuffDef(def.associatedBuff.buffIndex)==def.associatedBuff),"Original DOT definition/buff not indexed: "+index);}
  var effects=new List<GameObject>();var paths=new[]{"Prefabs/NetworkedObjects/DotController","Prefabs/BleedEffect","Prefabs/FireEffect","Prefabs/Effects/ImpactEffects/IgniteExplosionVFX","Prefabs/Projectiles/DaggerProjectile"};
  foreach(var path in paths){
   int i=Array.IndexOf(cfg.objectiveSupportPaths,path);Check(i>=0,"Original DOT provider absent: "+path);var source=objectiveSupportSources[i];
   Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original DOT source references absent: "+path);
   var roots=new List<GameObject>{source};
   if(source.name=="DotController"){Check(source.GetComponent<DotController>()&&source.GetComponent<NetworkIdentity>(),"Original DOT network prefab absent");var slot=typeof(DotController).GetField("DotControllerPrefab");Check(slot.GetValue(null)==null,"Unowned DOT prefab");worldLootEffectSlots.Add(slot,null);slot.SetValue(null,source);}
   else if(source.name=="DaggerProjectile"){
    var slot=typeof(GlobalEventManager.CommonAssets).GetField("daggerPrefab");Check(slot.GetValue(null)==null,"Unowned original dagger binding");worldLootEffectSlots.Add(slot,null);slot.SetValue(null,source);
    var controller=source.GetComponent<RoR2.Projectile.ProjectileController>();Check(controller&&controller.ghostPrefab&&source.GetComponent<NetworkIdentity>(),"Original dagger projectile/ghost absent");roots.Add(controller.ghostPrefab);
    foreach(var component in source.GetComponents<Component>())foreach(var value in component.GetType().GetFields(BindingFlags.Instance|BindingFlags.Public)){if(value.FieldType!=typeof(GameObject))continue;var effect=value.GetValue(component) as GameObject;if(effect&&effect.GetComponent<EffectComponent>()){roots.Add(effect);effects.Add(effect);}}
   }else if(source.name=="IgniteExplosionVFX"){
    var slot=typeof(GlobalEventManager.CommonAssets).GetField("igniteOnKillExplosionEffectPrefab");Check(slot.GetValue(null)==null,"Unowned original ignite binding");worldLootEffectSlots.Add(slot,null);slot.SetValue(null,source);Check(source.GetComponent<EffectComponent>(),"Original ignite effect absent");effects.Add(source);
   }else {worldDotPoolSources.Add(source);Check((source.name=="BleedEffect"||source.GetComponent<BurnEffectControllerHelper>()),"Original DOT pooled effect contract absent");worldNativeLootLeaseBaselines.Add(i,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[i]));}
   foreach(var renderer in roots.Distinct().SelectMany(x=>x.GetComponentsInChildren<Renderer>(true)).Distinct()){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
   foreach(var root in roots.Distinct())PresentCommerceModel(root.transform);
  }
  var overlay=artifactBundle.LoadAsset<Material>(cfg.worldDotBurnMaterialAsset);Check(overlay&&overlay.name=="matOnFire","Original burn overlay absent");var copy=new Material(overlay);AndroidMaterialPresentation.Apply(overlay,copy);worldMaterials.Add(copy);
  previousWorldBurn=BurnEffectController.normalEffect;BurnEffectController.normalEffect=new BurnEffectController.EffectParams{overlayMaterial=copy,fireEffectPrefab=objectiveSupportSources[Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/FireEffect")]};
  r.dots=new WorldDotReport{ready=true,definitions=defs.Length};
  worldDotInflicted=(DotController controller,ref InflictDotInfo info)=>{Check(controller&&controller.victimObject==info.victimObject&&controller.netId.Value!=0,"Native DOT victim/network binding differs");WorldDotRow(info.dotIndex).inflictions++;r.dots.peakControllers=Mathf.Max(r.dots.peakControllers,DotController.readOnlyInstancesList.Count);};
  worldDotDamage=report=>{if(report.damageInfo.dotIndex==DotController.DotIndex.None)return;var row=WorldDotRow(report.damageInfo.dotIndex);row.damageEvents++;row.damage+=report.damageDealt;};
  DotController.onDotInflictedServerGlobal+=worldDotInflicted;GlobalEventManager.onServerDamageDealt+=worldDotDamage;
  return effects.Distinct().ToArray();
 }
 void CleanupWorldDots(){
  if(!ownsWorldDots)return;
  if(worldDotInflicted!=null)DotController.onDotInflictedServerGlobal-=worldDotInflicted;if(worldDotDamage!=null)GlobalEventManager.onServerDamageDealt-=worldDotDamage;worldDotInflicted=null;worldDotDamage=null;
  // Empty native stacks while their victim/buff/server context is still valid.
  foreach(var controller in DotController.readOnlyInstancesList.ToArray())if(controller){controller.enabled=false;var stacks=(IList)typeof(DotController).GetField("dotStackList",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(controller);if(NetworkServer.active&&stacks!=null)while(stacks.Count>0)Call(controller,"RemoveDotStackAtServer",stacks.Count-1);Call(controller,"HandleDestroy");}
  typeof(DotController).GetField("dotDefs",BindingFlags.Static|BindingFlags.NonPublic).SetValue(null,previousWorldDotDefs);BurnEffectController.normalEffect=previousWorldBurn;ownsWorldDots=false;
 }
 void FinishWorldDotCleanup(){
  if(r.dots==null)return;
  Check(!ownsWorldDots&&DotController.readOnlyInstancesList.Count==0,"Native DOT instances survived owned teardown");
  var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);var cache=(IDictionary)RewardField(typeof(EffectManager),"_ShouldUsePooledEffectMap").GetValue(null);
  foreach(var source in worldDotPoolSources){EffectPool pool;if(pools.TryGetValue(source,out pool)){foreach(var effect in pool.InUse.ToArray())pool.ReturnObject(effect);EffectManager.ClearPool(source);pool.Kill();}cache.Remove(source);}worldDotPoolSources.Clear();r.dots.cleaned=true;
 }
}
