// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareStageBossContent (StageBossContentSession); teardown CleanupStageBossInstances, then CleanupStageBossContent (Dispose).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Supplies source dependencies and schedules the native overheat callback.
// Boss AI, summoning, tether healing, sun damage and heat decay remain original.
public sealed partial class MovementBatchProbe {
 [Serializable] public class StageBossContentReport {
  public bool ready,cleaned,cardRestored,heatEmpty;public int ticks,heatTargetsPeak,heatStacksPeak,suns,tethers,minions;
  public List<string> unavailableBossRewardItems=new List<string>();
  public string scope="Original boss dependencies; unsupported boss rewards use the inherited fallback; owned provider/scheduling/cleanup. Registration does not establish individual boss combat, source placement or PC appearance.";
 }
 StageBossContentSession stageBossContentSession;
 StageBossContentSession GetStageBossContentSession(){if(stageBossContentSession==null)stageBossContentSession=new StageBossContentSession(this);return stageBossContentSession;}
 BuffDef[] StageBossBuffs(SessionConfig cfg){return GetStageBossContentSession().StageBossBuffs(cfg);}
 System.Collections.IEnumerator PrepareStageBossContent(SessionConfig cfg){return GetStageBossContentSession().PrepareStageBossContent(cfg);}
 bool UnavailableBossRewardTable(PickupDropTable source){return GetStageBossContentSession().UnavailableBossRewardTable(source);}
 ItemDef[] ComposedBaseBossRewards(SessionConfig cfg){return GetStageBossContentSession().ComposedBaseBossRewards(cfg);}
 int StageHeatCount(){return GetStageBossContentSession().StageHeatCount();}
 object StageHeatPair(int index){return GetStageBossContentSession().StageHeatPair(index);}
 CharacterBody StageHeatBody(object pair){return GetStageBossContentSession().StageHeatBody(pair);}
 int StageHeatStacks(object pair){return GetStageBossContentSession().StageHeatStacks(pair);}
 void TickStageBossHeat(){GetStageBossContentSession().TickStageBossHeat();}
 void ObserveStageBossContent(bool force=false){GetStageBossContentSession().ObserveStageBossContent(force);}
 void CleanupStageBossInstances(){GetStageBossContentSession().CleanupStageBossInstances();}
 void CleanupStageBossContent(){GetStageBossContentSession().Dispose();}

 // Create on first use and retain for partial setup, repeated cleanup and later
 // observations. Dispose preserves instance cleanup before card/lease restoration.
 sealed class StageBossContentSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  Action stageHeatFixed;object stageHeatEntries;PropertyInfo stageHeatCount,stageHeatItem;
  AsyncOperationHandle<SpawnCard> stageMiniCardLease;SpawnCard stageMiniCard;GameObject priorStageMiniPrefab;
  readonly HashSet<CharacterBody> stageHeatOwners=new HashSet<CharacterBody>();
  readonly HashSet<GameObject> stageBossInstances=new HashSet<GameObject>();
  readonly HashSet<CharacterMaster> stageMiniInstances=new HashSet<CharacterMaster>();
  public StageBossContentSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public BuffDef[] StageBossBuffs(SessionConfig cfg){
   if(string.IsNullOrEmpty(cfg.stageOverheatBuffAsset))return new BuffDef[0];
   var buff=coordinator.artifactBundle.LoadAsset<BuffDef>(cfg.stageOverheatBuffAsset);coordinator.Check(buff&&buff.name=="bdOverheat","Original overheat buff missing");coordinator.BindEnemyDefinition(typeof(RoR2Content.Buffs),"Overheat",buff);var armor=coordinator.artifactBundle.LoadAsset<BuffDef>(cfg.stageBossArmorBuffAsset);coordinator.Check(armor&&armor.name=="bdArmorBoost","Original Clay recovery armor buff missing");coordinator.BindEnemyDefinition(typeof(RoR2Content.Buffs),"ArmorBoost",armor);return new[]{buff,armor};
  }
  public System.Collections.IEnumerator PrepareStageBossContent(SessionConfig cfg){
   if(string.IsNullOrEmpty(cfg.stageMiniCardAsset))yield break;
   if(coordinator.r.stageBossContent==null)coordinator.r.stageBossContent=new StageBossContentReport();
   string key;coordinator.Check(LegacyResourcesAPI.GetGuid(cfg.stageMiniCardPath,out key)&&key==cfg.stageMiniCardKey,"Original Solus summon card identity changed");
   coordinator.objectiveLocator.Add(key,new ResourceLocationBase(key,cfg.stageMiniCardAsset,typeof(BundledAssetProvider).FullName,typeof(SpawnCard),coordinator.objectiveBundleLocation));
   stageMiniCardLease=LegacyResourcesAPI.LoadAsync<SpawnCard>(cfg.stageMiniCardPath);yield return stageMiniCardLease;
   stageMiniCard=stageMiniCardLease.Result;coordinator.Check(stageMiniCard&&stageMiniCard.name=="cscRoboBallMini"&&stageMiniCard is CharacterSpawnCard,"Original Solus summon card missing");
   priorStageMiniPrefab=stageMiniCard.prefab;stageMiniCard.prefab=coordinator.objectiveCards.Single(x=>x.name==stageMiniCard.name).prefab;
   coordinator.Check(stageMiniCard.prefab.GetComponent<CharacterMaster>()&&stageMiniCard.prefab.GetComponent<CharacterMaster>().bodyPrefab.name=="RoboBallMiniBody","Original Solus child template absent");
   var tetherIndex=Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/NetworkedObjects/TarTether");coordinator.Check(tetherIndex>=0&&coordinator.objectiveSupportSources[tetherIndex].GetComponent<TarTetherController>(),"Original Tar tether provider absent");coordinator.worldNativeLootLeaseBaselines.Add(tetherIndex,(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(coordinator.objectiveSupportLeases[tetherIndex]));
   var tether=coordinator.objectiveSupportSources[tetherIndex];foreach(var renderer in tether.GetComponentsInChildren<Renderer>(true)){if(coordinator.worldLootSourceMaterials.ContainsKey(renderer))continue;coordinator.worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);coordinator.worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}coordinator.PresentCommerceModel(tether.transform);
   var visual=coordinator.artifactBundle.LoadAsset<GameObject>(cfg.stageOverheatVisualAsset);coordinator.Check(visual&&visual.GetComponent<TemporaryVisualEffect>()&&visual.GetComponentsInChildren<Component>(true).All(x=>x),"Original overheat visual missing");
   var field=typeof(CharacterBody).GetNestedType("AssetReferences",BindingFlags.NonPublic).GetField("overheatEffectPrefab",BindingFlags.Public|BindingFlags.Static);coordinator.Check(field!=null&&field.GetValue(null)==null,"Unowned overheat visual binding");coordinator.worldLootEffectSlots.Add(field,null);field.SetValue(null,visual);
   foreach(var renderer in visual.GetComponentsInChildren<Renderer>(true)){if(coordinator.worldLootSourceMaterials.ContainsKey(renderer))continue;coordinator.worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);coordinator.worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}coordinator.PresentCommerceModel(visual.transform);
   var sun=coordinator.artifactBundle.LoadAsset<GameObject>(cfg.stageGrandparentSunAsset);coordinator.Check(sun&&sun.GetComponent<GrandParentSunController>()&&sun.GetComponent<GenericOwnership>()&&sun.GetComponent<TeamFilter>()&&sun.GetComponent<NetworkIdentity>()&&sun.GetComponent<EntityStateMachine>()&&sun.GetComponentsInChildren<Component>(true).All(x=>x),"Original Grandparent sun contract absent");
   coordinator.Check(EntityStates.GrandParent.ChannelSun.sunPrefab==sun,"Original configured sun has a different bundle owner");
   var heatField=typeof(OverheatSystem).GetField("bodyOverheatInfos",BindingFlags.NonPublic|BindingFlags.Static);stageHeatEntries=heatField.GetValue(null);stageHeatCount=stageHeatEntries.GetType().GetProperty("Count");stageHeatItem=stageHeatEntries.GetType().GetProperties().Single(x=>x.Name=="Item"&&x.GetIndexParameters().Length==1&&x.GetIndexParameters()[0].ParameterType==typeof(int));coordinator.Check(stageHeatCount!=null&&stageHeatItem!=null&&StageHeatCount()==0,"Unowned native overheat context");
   var method=typeof(OverheatSystem).GetMethod("FixedUpdateServer",BindingFlags.NonPublic|BindingFlags.Static);var dispatch=typeof(RoR2Application).GetField("onFixedUpdate",BindingFlags.NonPublic|BindingFlags.Public|BindingFlags.Static).GetValue(null) as Delegate;coordinator.Check(dispatch==null||dispatch.GetInvocationList().All(x=>x.Method!=method),"Native overheat already scheduled");stageHeatFixed=(Action)Delegate.CreateDelegate(typeof(Action),method);
   coordinator.Check(!Resources.FindObjectsOfTypeAll<GrandParentSunController>().Any(x=>x.gameObject.scene.IsValid())&&!Resources.FindObjectsOfTypeAll<TarTetherController>().Any(x=>x.gameObject.scene.IsValid()),"Unowned boss support instances");coordinator.r.stageBossContent.ready=true;coordinator.Save();
  }
  public bool UnavailableBossRewardTable(PickupDropTable source){
   var table=source as ExplicitPickupDropTable;if(!table)return false;
   var missing=table.pickupEntries.Select(x=>x.pickupDef as ItemDef).Where(x=>x&&ItemCatalog.FindItemIndex(x.name)==ItemIndex.None).Select(x=>x.name).Distinct().ToArray();if(missing.Length==0)return false;
   if(coordinator.r.stageBossContent==null)coordinator.r.stageBossContent=new StageBossContentReport();foreach(var name in missing)if(!coordinator.r.stageBossContent.unavailableBossRewardItems.Contains(name))coordinator.r.stageBossContent.unavailableBossRewardItems.Add(name);
   // Native BossGroup retains its ordinary supported reward path when this optional
   // explicit table is absent. Never create unusable items or change source tables.
   return true;
  }
  public ItemDef[] ComposedBaseBossRewards(SessionConfig cfg){
   if(!cfg.teleporterLoop)return new ItemDef[0];
   var tables=cfg.objectiveActors.Select(actor=>coordinator.artifactBundle.LoadAsset<GameObject>(actor.body).GetComponent<DeathRewards>()).Where(rewards=>rewards).Select(rewards=>rewards.bossDropTable as ExplicitPickupDropTable).Where(table=>table);
   var items=tables.SelectMany(table=>table.pickupEntries).Select(entry=>entry.pickupDef as ItemDef).Where(item=>item&&ItemCatalog.GetItemDef(ItemCatalog.FindItemIndex(item.name))==item).Distinct().ToArray();
   foreach(var item in items)coordinator.Check(item.tier==ItemTier.Boss&&!item.requiredExpansion&&!item.unlockableDef&&!item.hidden,"Original composed boss reward requires unavailable policy: "+item.name);
   return items;
  }
  public int StageHeatCount(){return (int)stageHeatCount.GetValue(stageHeatEntries);}
  public object StageHeatPair(int index){return stageHeatItem.GetValue(stageHeatEntries,new object[]{index});}
  public CharacterBody StageHeatBody(object pair){return (CharacterBody)pair.GetType().GetProperty("Key").GetValue(pair);}
  public int StageHeatStacks(object pair){var value=pair.GetType().GetProperty("Value").GetValue(pair);return (int)value.GetType().GetProperty("channeledOverheatStacks").GetValue(value);}
  public void TickStageBossHeat(){
   if(stageHeatFixed==null)return;
   for(int i=0;i<StageHeatCount();i++){var pair=StageHeatPair(i);var body=StageHeatBody(pair);coordinator.Check(stageHeatOwners.Contains(body)||body&&(body==coordinator.worldPlayer||coordinator.ownedRewardSummons.Contains(body.master)),"Foreign native overheat target");stageHeatOwners.Add(body);coordinator.r.stageBossContent.heatStacksPeak=Math.Max(coordinator.r.stageBossContent.heatStacksPeak,StageHeatStacks(pair));}
   coordinator.r.stageBossContent.heatTargetsPeak=Math.Max(coordinator.r.stageBossContent.heatTargetsPeak,StageHeatCount());stageHeatFixed();coordinator.r.stageBossContent.ticks++;
  }
  public void ObserveStageBossContent(bool force=false){
   if(coordinator.r.stageBossContent==null||(!force&&Time.frameCount%30!=0))return;
   var instances=force?Resources.FindObjectsOfTypeAll<GameObject>():NetworkServer.objects.Values.Where(x=>x).Select(x=>x.gameObject).ToArray();
   foreach(var obj in instances.Where(x=>x&&x.scene.IsValid()&&(x.GetComponent<GrandParentSunController>()||x.GetComponent<TarTetherController>()))){
    if(!stageBossInstances.Add(obj))continue;var id=obj.GetComponent<NetworkIdentity>();coordinator.Check(id&&id.netId.Value!=0&&NetworkServer.FindLocalObject(id.netId)==obj,"Boss support has no owned server identity");if(obj.GetComponent<GrandParentSunController>())coordinator.r.stageBossContent.suns++;else coordinator.r.stageBossContent.tethers++;
   }
   foreach(var master in coordinator.ownedRewardSummons.Where(x=>x&&x.bodyPrefab&&x.bodyPrefab.name=="RoboBallMiniBody"))if(stageMiniInstances.Add(master))coordinator.r.stageBossContent.minions++;
  }
  public void CleanupStageBossInstances(){
   if(coordinator.r.stageBossContent==null)return;ObserveStageBossContent(true);foreach(var obj in stageBossInstances)if(obj)NetworkServer.Destroy(obj);stageBossInstances.Clear();
   if(stageHeatFixed==null){coordinator.r.stageBossContent.heatEmpty=true;return;}TickStageBossHeat();
   for(int i=0;i<StageHeatCount();i++){var pair=StageHeatPair(i);var body=StageHeatBody(pair);coordinator.Check(stageHeatOwners.Contains(body),"Foreign heat state during owned teardown");OverheatSystem.AccelerateHeatDissipationServer(body,Math.Max(1,StageHeatStacks(pair))*OverheatSystem.decayInterval);}
   stageHeatFixed();coordinator.r.stageBossContent.heatEmpty=StageHeatCount()==0;coordinator.Check(coordinator.r.stageBossContent.heatEmpty,"Original heat state survived owned teardown");stageHeatOwners.Clear();
  }
  public void Dispose(){
   if(coordinator.r.stageBossContent==null)return;CleanupStageBossInstances();stageHeatFixed=null;stageHeatEntries=null;stageMiniInstances.Clear();coordinator.r.stageBossContent.cardRestored=stageMiniCard==null;
   if(stageMiniCard){coordinator.Check(stageMiniCard.prefab==coordinator.objectiveCards.Single(x=>x.name==stageMiniCard.name).prefab,"Foreign Solus card replacement");stageMiniCard.prefab=priorStageMiniPrefab;coordinator.r.stageBossContent.cardRestored=stageMiniCard.prefab==priorStageMiniPrefab;int references=(int)typeof(AsyncOperationHandle<SpawnCard>).GetProperty("ReferenceCount",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(stageMiniCardLease);coordinator.Check(references>=1,"Original Solus card lease missing");for(int i=1;i<references;i++)Addressables.Release(stageMiniCard);Addressables.Release(stageMiniCardLease);stageMiniCardLease=default(AsyncOperationHandle<SpawnCard>);stageMiniCard=null;priorStageMiniPrefab=null;}
   coordinator.r.stageBossContent.cleaned=coordinator.r.stageBossContent.heatEmpty&&coordinator.r.stageBossContent.cardRestored&&stageBossInstances.Count==0;coordinator.Check(coordinator.r.stageBossContent.cleaned,"Owned boss support cleanup incomplete");coordinator.Save();
  }
 }
}
