// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWorldProcSupport, ObserveHealingCommerceWards (WorldProcContentSession); teardown CleanupHealingCommerceWards, CleanupWorldProcContent (Dispose).
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
 [Serializable] public class ProcContentReport {public bool ready,cleaned;public int buffs,supportSources,warbannerWards,warbannerBuffEffects,deskPlants,deskplantWards,healNovaGenerators,healNovaPulses;public string scope="Original item/proc content and owned dependency bindings; registration is not individual proc acceptance.";}
 [Serializable] public class HealingWardObservation {public string shrine;public uint netId;public int purchases;public float radius,interval,healFraction,healPoints;public bool playerTeam,parentMatched,teardownRequested;}
 WorldProcContentSession worldProcContentSession;
 WorldProcContentSession GetWorldProcContentSession(){if(worldProcContentSession==null)worldProcContentSession=new WorldProcContentSession(this);return worldProcContentSession;}
 BuffDef[] WorldProcBuffs(SessionConfig cfg){return GetWorldProcContentSession().WorldProcBuffs(cfg);}
 GameObject[] PrepareWorldProcSupport(SessionConfig cfg){return GetWorldProcContentSession().PrepareWorldProcSupport(cfg);}
 static bool WorldProcSupportContract(SessionConfig cfg){return WorldProcContentSession.WorldProcSupportContract(cfg);}
 void ObserveHealingCommerceWards(){GetWorldProcContentSession().ObserveHealingCommerceWards();}
 void CleanupHealingCommerceWards(){GetWorldProcContentSession().CleanupHealingCommerceWards();}
 void CleanupWorldProcContent(){GetWorldProcContentSession().Dispose();}

 // Retain the owner for partial setup, repeated cleanup and later observations.
 // Commerce ward teardown stays separate from Dispose's proc cleanup dispatch.
 sealed class WorldProcContentSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  readonly Dictionary<GameObject,HealingWardObservation> commerceHealingWards=new Dictionary<GameObject,HealingWardObservation>();
  public WorldProcContentSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public BuffDef[] WorldProcBuffs(SessionConfig cfg){
   if(cfg.worldProcBuffAssets==null||cfg.worldProcBuffAssets.Length==0)return new BuffDef[0];
   var names=new[]{"DeathMark","PulverizeBuildup","Pulverized"};if(cfg.worldAdditionalLootItems!=null&&cfg.worldAdditionalLootItems.Contains("WardOnLevel"))names=names.Concat(new[]{"Warbanner"}).ToArray();coordinator.Check(cfg.worldProcBuffAssets.Length==names.Length,"Original proc buff closure differs");
   return cfg.worldProcBuffAssets.Select((path,i)=>{var def=coordinator.artifactBundle.LoadAsset<BuffDef>(path);coordinator.Check(def&&def.name=="bd"+names[i],"Original proc buff missing: "+names[i]);coordinator.BindEnemyDefinition(typeof(RoR2Content.Buffs),names[i],def);return def;}).ToArray();
  }
  public GameObject[] PrepareWorldProcSupport(SessionConfig cfg){
   if(cfg.worldProcSupportPaths==null||cfg.worldProcSupportPaths.Length==0)return new GameObject[0];
   coordinator.Check(WorldProcSupportContract(cfg),"Original proc support closure differs");var effects=new List<GameObject>();
   foreach(var path in cfg.worldProcSupportPaths){
    int index=Array.IndexOf(cfg.objectiveSupportPaths,path);coordinator.Check(index>=0,"Original proc provider absent: "+path);var source=coordinator.objectiveSupportSources[index];coordinator.Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original proc references absent: "+path);
    if(coordinator.IsWorldHealingItemSource(path)){coordinator.PrepareWorldHealingItemSource(path,source);continue;}
    if(coordinator.IsWorldLegendaryItemSource(path)){var effect=coordinator.PrepareWorldLegendaryItemSource(path,source,index);if(effect)effects.Add(source);continue;}
    bool missile=path=="Prefabs/Projectiles/MissileProjectile",pulverized=path=="Prefabs/Effects/ImpactEffects/PulverizedEffect",deathmark=path=="Prefabs/TemporaryVisualEffects/DeathMarkEffect";
    coordinator.Check(missile||pulverized||deathmark||path=="Prefabs/Effects/OmniEffect/OmniExplosionVFXQuick","Unknown original proc source");
    if(missile||pulverized||deathmark){
     var type=(missile?typeof(GlobalEventManager):pulverized?typeof(HealthComponent):typeof(CharacterBody)).GetNestedType(missile?"CommonAssets":"AssetReferences",missile?BindingFlags.Public:BindingFlags.NonPublic);
     var field=type.GetField(missile?"missilePrefab":pulverized?"pulverizedEffectPrefab":"deathmarkEffectPrefab",BindingFlags.Public|BindingFlags.Static);coordinator.Check(field!=null&&field.FieldType==typeof(GameObject)&&field.GetValue(null)==null,"Unowned original proc field");coordinator.worldLootEffectSlots.Add(field,null);field.SetValue(null,source);
    }else coordinator.worldNativeLootLeaseBaselines.Add(index,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(coordinator.objectiveSupportLeases[index]));
    if(missile)coordinator.worldNativeLootLeaseBaselines.Add(index,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(coordinator.objectiveSupportLeases[index]));
    var roots=new List<GameObject>{source};
    if(missile){var ghost=coordinator.OriginalProjectileGhost(source.GetComponent<ProjectileController>());var explosion=source.GetComponent<ProjectileSingleTargetImpact>();coordinator.Check(ghost&&source.GetComponent<MissileController>()&&explosion&&explosion.impactEffect&&source.GetComponent<NetworkIdentity>(),"Original missile projectile contract absent");roots.Add(ghost);roots.Add(explosion.impactEffect);effects.Add(explosion.impactEffect);}
    else if(deathmark)coordinator.Check(source.GetComponent<TemporaryVisualEffect>(),"Original Death Mark presentation contract absent");
    else{coordinator.Check(source.GetComponent<EffectComponent>(),"Original proc effect identity absent");effects.Add(source);}
    foreach(var renderer in roots.Distinct().SelectMany(x=>x.GetComponentsInChildren<Renderer>(true)).Distinct()){if(coordinator.worldLootSourceMaterials.ContainsKey(renderer))continue;coordinator.worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);coordinator.worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
    foreach(var root in roots.Distinct())coordinator.PresentCommerceModel(root.transform);
   }
   coordinator.r.procContent=new ProcContentReport{ready=true,buffs=cfg.worldProcBuffAssets.Length,supportSources=cfg.worldProcSupportPaths.Length};return effects.Distinct().ToArray();
  }
  public static bool WorldProcSupportContract(SessionConfig cfg){
   var paths=cfg.worldProcSupportPaths;if(paths==null)return false;
   if(paths.Length==4||paths.Length==9||paths.Length==13)return true;
   bool population=(paths.Length==14||paths.Length==15)&&paths.Distinct().Count()==paths.Length&&
    paths.Contains("Prefabs/NetworkedObjects/BodyAttachments/VagrantNovaItemBodyAttachment")&&
    cfg.objectiveItemNames!=null&&cfg.objectiveItemNames.Contains("NovaOnLowHealth")&&
    cfg.stagePopulationFamilies!=null&&cfg.stagePopulationFamilies.Contains("Vagrant");
   return population&&(paths.Length==14||paths.Contains("Prefabs/TemporaryVisualEffects/WarbannerBuffEffect")&&
    cfg.worldAdditionalLootItems!=null&&cfg.worldAdditionalLootItems.Contains("WardOnLevel"));
  }
  public void ObserveHealingCommerceWards(){
   foreach(var purchase in coordinator.commercePurchases.Where(x=>x)){
    if(coordinator.commercePurchaseCounts[purchase]==0)continue;
    var shrine=purchase.GetComponent<ShrineHealingBehavior>();if(!shrine)continue;var obj=(GameObject)typeof(ShrineHealingBehavior).GetField("wardInstance",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(shrine);if(!obj)continue;
    var ward=obj.GetComponent<HealingWard>();coordinator.Check(ward&&obj.GetComponent<TeamFilter>()&&ward.netId.Value!=0,"Native healing shrine ward/network identity absent");
    HealingWardObservation row;if(!commerceHealingWards.TryGetValue(obj,out row)){row=new HealingWardObservation{shrine=shrine.name,netId=ward.netId.Value};commerceHealingWards.Add(obj,row);coordinator.worldObjects.Add(obj);coordinator.r.commerce.healingWards.Add(row);coordinator.PresentCommerceModel(obj.transform);}
    row.purchases=shrine.purchaseCount;row.radius=ward.radius;row.interval=ward.interval;row.healFraction=ward.healFraction;row.healPoints=ward.healPoints;row.playerTeam=obj.GetComponent<TeamFilter>().teamIndex==TeamIndex.Player;row.parentMatched=obj.transform.parent==shrine.GetComponent<ModelLocator>().modelTransform;
    coordinator.Check(row.playerTeam&&Mathf.Abs(row.radius-(shrine.baseRadius+shrine.radiusBonusPerPurchase*(shrine.purchaseCount-1)))<.001f,"Native healing shrine radius/team differs");
   }
  }
  public void CleanupHealingCommerceWards(){foreach(var pair in commerceHealingWards){if(pair.Key)NetworkServer.Destroy(pair.Key);pair.Value.teardownRequested=true;}commerceHealingWards.Clear();}
  public void Dispose(){
   coordinator.CleanupWorldHealingItems();coordinator.CleanupWorldLegendaryItems();coordinator.CleanupWorldItemBehaviors();coordinator.CleanupWorldDots();
   if(coordinator.r.procContent!=null)coordinator.r.procContent.cleaned=true;
  }
 }
}
