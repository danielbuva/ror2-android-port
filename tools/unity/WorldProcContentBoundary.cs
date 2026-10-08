using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

// Required source content for native item procs; no proc/damage/ward algorithms here.
public sealed partial class MovementBatchProbe {
 [Serializable] public class ProcContentReport {public bool ready,cleaned;public int buffs,supportSources;public string scope="Original item/proc content and owned dependency bindings; registration is not individual proc acceptance.";}
 [Serializable] public class HealingWardObservation {public string shrine;public uint netId;public int purchases;public float radius,interval,healFraction,healPoints;public bool playerTeam,parentMatched,teardownRequested;}
 readonly Dictionary<GameObject,HealingWardObservation> commerceHealingWards=new Dictionary<GameObject,HealingWardObservation>();
 BuffDef[] WorldProcBuffs(Result cfg){
  if(cfg.worldProcBuffAssets==null||cfg.worldProcBuffAssets.Length==0)return new BuffDef[0];
  var names=new[]{"DeathMark","PulverizeBuildup","Pulverized"};Check(cfg.worldProcBuffAssets.Length==names.Length,"Original proc buff closure differs");
  return cfg.worldProcBuffAssets.Select((path,i)=>{var def=artifactBundle.LoadAsset<BuffDef>(path);Check(def&&def.name=="bd"+names[i],"Original proc buff missing: "+names[i]);BindEnemyDefinition(typeof(RoR2Content.Buffs),names[i],def);return def;}).ToArray();
 }
 GameObject[] PrepareWorldProcSupport(Result cfg){
  if(cfg.worldProcSupportPaths==null||cfg.worldProcSupportPaths.Length==0)return new GameObject[0];
  Check(cfg.worldProcSupportPaths.Length==4,"Original proc support closure differs");var effects=new List<GameObject>();
  foreach(var path in cfg.worldProcSupportPaths){
   int index=Array.IndexOf(cfg.objectiveSupportPaths,path);Check(index>=0,"Original proc provider absent: "+path);var source=objectiveSupportSources[index];Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original proc references absent: "+path);
   bool missile=path=="Prefabs/Projectiles/MissileProjectile",pulverized=path=="Prefabs/Effects/ImpactEffects/PulverizedEffect",deathmark=path=="Prefabs/TemporaryVisualEffects/DeathMarkEffect";
   Check(missile||pulverized||deathmark||path=="Prefabs/Effects/OmniEffect/OmniExplosionVFXQuick","Unknown original proc source");
   if(missile||pulverized||deathmark){
    var type=(missile?typeof(GlobalEventManager):pulverized?typeof(HealthComponent):typeof(CharacterBody)).GetNestedType(missile?"CommonAssets":"AssetReferences",missile?BindingFlags.Public:BindingFlags.NonPublic);
    var field=type.GetField(missile?"missilePrefab":pulverized?"pulverizedEffectPrefab":"deathmarkEffectPrefab",BindingFlags.Public|BindingFlags.Static);Check(field!=null&&field.FieldType==typeof(GameObject)&&field.GetValue(null)==null,"Unowned original proc field");worldLootEffectSlots.Add(field,null);field.SetValue(null,source);
   }else worldNativeLootLeaseBaselines.Add(index,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[index]));
   if(missile)worldNativeLootLeaseBaselines.Add(index,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[index]));
   var roots=new List<GameObject>{source};
   if(missile){var controller=source.GetComponent<ProjectileController>();var explosion=source.GetComponent<ProjectileSingleTargetImpact>();Check(controller&&controller.ghostPrefab&&source.GetComponent<MissileController>()&&explosion&&explosion.impactEffect&&source.GetComponent<NetworkIdentity>(),"Original missile projectile contract absent");roots.Add(controller.ghostPrefab);roots.Add(explosion.impactEffect);effects.Add(explosion.impactEffect);}
   else if(deathmark)Check(source.GetComponent<TemporaryVisualEffect>(),"Original Death Mark presentation contract absent");
   else{Check(source.GetComponent<EffectComponent>(),"Original proc effect identity absent");effects.Add(source);}
   foreach(var renderer in roots.Distinct().SelectMany(x=>x.GetComponentsInChildren<Renderer>(true)).Distinct()){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
   foreach(var root in roots.Distinct())PresentCommerceModel(root.transform);
  }
  r.procContent=new ProcContentReport{ready=true,buffs=cfg.worldProcBuffAssets.Length,supportSources=cfg.worldProcSupportPaths.Length};return effects.Distinct().ToArray();
 }
 void ObserveHealingCommerceWards(){
  foreach(var purchase in commercePurchases.Where(x=>x)){
   var shrine=purchase.GetComponent<ShrineHealingBehavior>();if(!shrine)continue;var obj=(GameObject)typeof(ShrineHealingBehavior).GetField("wardInstance",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(shrine);if(!obj)continue;
   var ward=obj.GetComponent<HealingWard>();Check(ward&&obj.GetComponent<TeamFilter>()&&ward.netId.Value!=0,"Native healing shrine ward/network identity absent");
   HealingWardObservation row;if(!commerceHealingWards.TryGetValue(obj,out row)){row=new HealingWardObservation{shrine=shrine.name,netId=ward.netId.Value};commerceHealingWards.Add(obj,row);worldObjects.Add(obj);r.commerce.healingWards.Add(row);PresentCommerceModel(obj.transform);}
   row.purchases=shrine.purchaseCount;row.radius=ward.radius;row.interval=ward.interval;row.healFraction=ward.healFraction;row.healPoints=ward.healPoints;row.playerTeam=obj.GetComponent<TeamFilter>().teamIndex==TeamIndex.Player;row.parentMatched=obj.transform.parent==shrine.GetComponent<ModelLocator>().modelTransform;
   Check(row.playerTeam&&Mathf.Abs(row.radius-(shrine.baseRadius+shrine.radiusBonusPerPurchase*(shrine.purchaseCount-1)))<.001f,"Native healing shrine radius/team differs");
  }
 }
 void CleanupHealingCommerceWards(){foreach(var pair in commerceHealingWards){if(pair.Key)NetworkServer.Destroy(pair.Key);pair.Value.teardownRequested=true;}commerceHealingWards.Clear();}
 void CleanupWorldProcContent(){
  CleanupWorldItemBehaviors();CleanupWorldDots();
  if(r.procContent!=null)r.procContent.cleaned=true;
 }
}
