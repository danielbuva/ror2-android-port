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
 Action stageHeatFixed;object stageHeatEntries;PropertyInfo stageHeatCount,stageHeatItem;
 AsyncOperationHandle<SpawnCard> stageMiniCardLease;SpawnCard stageMiniCard;GameObject priorStageMiniPrefab;
 readonly HashSet<CharacterBody> stageHeatOwners=new HashSet<CharacterBody>();
 readonly HashSet<GameObject> stageBossInstances=new HashSet<GameObject>();
 readonly HashSet<CharacterMaster> stageMiniInstances=new HashSet<CharacterMaster>();
 BuffDef[] StageBossBuffs(Result cfg){
  if(string.IsNullOrEmpty(cfg.stageOverheatBuffAsset))return new BuffDef[0];
  var buff=artifactBundle.LoadAsset<BuffDef>(cfg.stageOverheatBuffAsset);Check(buff&&buff.name=="bdOverheat","Original overheat buff missing");BindEnemyDefinition(typeof(RoR2Content.Buffs),"Overheat",buff);var armor=artifactBundle.LoadAsset<BuffDef>(cfg.stageBossArmorBuffAsset);Check(armor&&armor.name=="bdArmorBoost","Original Clay recovery armor buff missing");BindEnemyDefinition(typeof(RoR2Content.Buffs),"ArmorBoost",armor);return new[]{buff,armor};
 }
 System.Collections.IEnumerator PrepareStageBossContent(Result cfg){
  if(string.IsNullOrEmpty(cfg.stageMiniCardAsset))yield break;
  if(r.stageBossContent==null)r.stageBossContent=new StageBossContentReport();
  string key;Check(LegacyResourcesAPI.GetGuid(cfg.stageMiniCardPath,out key)&&key==cfg.stageMiniCardKey,"Original Solus summon card identity changed");
  objectiveLocator.Add(key,new ResourceLocationBase(key,cfg.stageMiniCardAsset,typeof(BundledAssetProvider).FullName,typeof(SpawnCard),objectiveBundleLocation));
  stageMiniCardLease=LegacyResourcesAPI.LoadAsync<SpawnCard>(cfg.stageMiniCardPath);yield return stageMiniCardLease;
  stageMiniCard=stageMiniCardLease.Result;Check(stageMiniCard&&stageMiniCard.name=="cscRoboBallMini"&&stageMiniCard is CharacterSpawnCard,"Original Solus summon card missing");
  priorStageMiniPrefab=stageMiniCard.prefab;stageMiniCard.prefab=objectiveCards.Single(x=>x.name==stageMiniCard.name).prefab;
  Check(stageMiniCard.prefab.GetComponent<CharacterMaster>()&&stageMiniCard.prefab.GetComponent<CharacterMaster>().bodyPrefab.name=="RoboBallMiniBody","Original Solus child template absent");
  var tetherIndex=Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/NetworkedObjects/TarTether");Check(tetherIndex>=0&&objectiveSupportSources[tetherIndex].GetComponent<TarTetherController>(),"Original Tar tether provider absent");worldNativeLootLeaseBaselines.Add(tetherIndex,(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(objectiveSupportLeases[tetherIndex]));
  var tether=objectiveSupportSources[tetherIndex];foreach(var renderer in tether.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}PresentCommerceModel(tether.transform);
  var visual=artifactBundle.LoadAsset<GameObject>(cfg.stageOverheatVisualAsset);Check(visual&&visual.GetComponent<TemporaryVisualEffect>()&&visual.GetComponentsInChildren<Component>(true).All(x=>x),"Original overheat visual missing");
  var field=typeof(CharacterBody).GetNestedType("AssetReferences",BindingFlags.NonPublic).GetField("overheatEffectPrefab",BindingFlags.Public|BindingFlags.Static);Check(field!=null&&field.GetValue(null)==null,"Unowned overheat visual binding");worldLootEffectSlots.Add(field,null);field.SetValue(null,visual);
  foreach(var renderer in visual.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}PresentCommerceModel(visual.transform);
  var sun=artifactBundle.LoadAsset<GameObject>(cfg.stageGrandparentSunAsset);Check(sun&&sun.GetComponent<GrandParentSunController>()&&sun.GetComponent<GenericOwnership>()&&sun.GetComponent<TeamFilter>()&&sun.GetComponent<NetworkIdentity>()&&sun.GetComponent<EntityStateMachine>()&&sun.GetComponentsInChildren<Component>(true).All(x=>x),"Original Grandparent sun contract absent");
  Check(EntityStates.GrandParent.ChannelSun.sunPrefab==sun,"Original configured sun has a different bundle owner");
  var heatField=typeof(OverheatSystem).GetField("bodyOverheatInfos",BindingFlags.NonPublic|BindingFlags.Static);stageHeatEntries=heatField.GetValue(null);stageHeatCount=stageHeatEntries.GetType().GetProperty("Count");stageHeatItem=stageHeatEntries.GetType().GetProperties().Single(x=>x.Name=="Item"&&x.GetIndexParameters().Length==1&&x.GetIndexParameters()[0].ParameterType==typeof(int));Check(stageHeatCount!=null&&stageHeatItem!=null&&StageHeatCount()==0,"Unowned native overheat context");
  var method=typeof(OverheatSystem).GetMethod("FixedUpdateServer",BindingFlags.NonPublic|BindingFlags.Static);var dispatch=typeof(RoR2Application).GetField("onFixedUpdate",BindingFlags.NonPublic|BindingFlags.Public|BindingFlags.Static).GetValue(null) as Delegate;Check(dispatch==null||dispatch.GetInvocationList().All(x=>x.Method!=method),"Native overheat already scheduled");stageHeatFixed=(Action)Delegate.CreateDelegate(typeof(Action),method);
  Check(!Resources.FindObjectsOfTypeAll<GrandParentSunController>().Any(x=>x.gameObject.scene.IsValid())&&!Resources.FindObjectsOfTypeAll<TarTetherController>().Any(x=>x.gameObject.scene.IsValid()),"Unowned boss support instances");r.stageBossContent.ready=true;Save();
 }
 bool UnavailableBossRewardTable(PickupDropTable source){
  var table=source as ExplicitPickupDropTable;if(!table)return false;
  var missing=table.pickupEntries.Select(x=>x.pickupDef as ItemDef).Where(x=>x&&ItemCatalog.FindItemIndex(x.name)==ItemIndex.None).Select(x=>x.name).Distinct().ToArray();if(missing.Length==0)return false;
  if(r.stageBossContent==null)r.stageBossContent=new StageBossContentReport();foreach(var name in missing)if(!r.stageBossContent.unavailableBossRewardItems.Contains(name))r.stageBossContent.unavailableBossRewardItems.Add(name);
  // Native BossGroup retains its ordinary supported reward path when this optional
  // explicit table is absent. Never create unusable items or change source tables.
  return true;
 }
 int StageHeatCount(){return (int)stageHeatCount.GetValue(stageHeatEntries);}
 object StageHeatPair(int index){return stageHeatItem.GetValue(stageHeatEntries,new object[]{index});}
 CharacterBody StageHeatBody(object pair){return (CharacterBody)pair.GetType().GetProperty("Key").GetValue(pair);}
 int StageHeatStacks(object pair){var value=pair.GetType().GetProperty("Value").GetValue(pair);return (int)value.GetType().GetProperty("channeledOverheatStacks").GetValue(value);}
 void TickStageBossHeat(){
  if(stageHeatFixed==null)return;
  for(int i=0;i<StageHeatCount();i++){var pair=StageHeatPair(i);var body=StageHeatBody(pair);Check(stageHeatOwners.Contains(body)||body&&(body==worldPlayer||ownedRewardSummons.Contains(body.master)),"Foreign native overheat target");stageHeatOwners.Add(body);r.stageBossContent.heatStacksPeak=Math.Max(r.stageBossContent.heatStacksPeak,StageHeatStacks(pair));}
  r.stageBossContent.heatTargetsPeak=Math.Max(r.stageBossContent.heatTargetsPeak,StageHeatCount());stageHeatFixed();r.stageBossContent.ticks++;
 }
 void ObserveStageBossContent(bool force=false){
  if(r.stageBossContent==null||(!force&&Time.frameCount%30!=0))return;
  foreach(var obj in Resources.FindObjectsOfTypeAll<GrandParentSunController>().Where(x=>x.gameObject.scene.IsValid()).Select(x=>x.gameObject).Concat(Resources.FindObjectsOfTypeAll<TarTetherController>().Where(x=>x.gameObject.scene.IsValid()).Select(x=>x.gameObject)).Distinct()){
   if(!stageBossInstances.Add(obj))continue;var id=obj.GetComponent<NetworkIdentity>();Check(id&&id.netId.Value!=0&&NetworkServer.FindLocalObject(id.netId)==obj,"Boss support has no owned server identity");if(obj.GetComponent<GrandParentSunController>())r.stageBossContent.suns++;else r.stageBossContent.tethers++;
  }
  foreach(var master in ownedRewardSummons.Where(x=>x&&x.bodyPrefab&&x.bodyPrefab.name=="RoboBallMiniBody"))if(stageMiniInstances.Add(master))r.stageBossContent.minions++;
 }
 void CleanupStageBossInstances(){
  if(r.stageBossContent==null)return;ObserveStageBossContent(true);foreach(var obj in stageBossInstances)if(obj)NetworkServer.Destroy(obj);stageBossInstances.Clear();
  if(stageHeatFixed==null){r.stageBossContent.heatEmpty=true;return;}TickStageBossHeat();
  for(int i=0;i<StageHeatCount();i++){var pair=StageHeatPair(i);var body=StageHeatBody(pair);Check(stageHeatOwners.Contains(body),"Foreign heat state during owned teardown");OverheatSystem.AccelerateHeatDissipationServer(body,Math.Max(1,StageHeatStacks(pair))*OverheatSystem.decayInterval);}
  stageHeatFixed();r.stageBossContent.heatEmpty=StageHeatCount()==0;Check(r.stageBossContent.heatEmpty,"Original heat state survived owned teardown");stageHeatOwners.Clear();
 }
 void CleanupStageBossContent(){
  if(r.stageBossContent==null)return;CleanupStageBossInstances();stageHeatFixed=null;stageHeatEntries=null;stageMiniInstances.Clear();r.stageBossContent.cardRestored=stageMiniCard==null;
  if(stageMiniCard){Check(stageMiniCard.prefab==objectiveCards.Single(x=>x.name==stageMiniCard.name).prefab,"Foreign Solus card replacement");stageMiniCard.prefab=priorStageMiniPrefab;r.stageBossContent.cardRestored=stageMiniCard.prefab==priorStageMiniPrefab;int references=(int)typeof(AsyncOperationHandle<SpawnCard>).GetProperty("ReferenceCount",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(stageMiniCardLease);Check(references>=1,"Original Solus card lease missing");for(int i=1;i<references;i++)Addressables.Release(stageMiniCard);Addressables.Release(stageMiniCardLease);stageMiniCardLease=default(AsyncOperationHandle<SpawnCard>);stageMiniCard=null;priorStageMiniPrefab=null;}
  r.stageBossContent.cleaned=r.stageBossContent.heatEmpty&&r.stageBossContent.cardRestored&&stageBossInstances.Count==0;Check(r.stageBossContent.cleaned,"Owned boss support cleanup incomplete");Save();
 }
}
