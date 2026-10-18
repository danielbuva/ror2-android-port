// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareEnemyRewards, InitializeRewardRunStreams (EnemyRewardSession); teardown CleanupRewardHosts (Dispose), then CleanupEnemyRewards (awaited in Start after Run teardown).
using System;
using System.Collections;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;

// Owned configuration/observation around original director, summon and reward callbacks.
public sealed partial class MovementBatchProbe {
 [Serializable] public class RewardReport {
  public string[] characterEffects,deferredEffects,registeredDeferredEffects,retainedOperations;
  public bool supportBundlePreloaded,effectSoundMetadataRestored;public int unavailableEffectSounds;
  public bool assetsReady,directedSpawn,spawnContract,queuedExperience,delivered,cleaned,equipmentMaskReady;public int equipmentDefinitions,expansionLockedEquipment;public int playerTeamBefore,playerTeamAfter;public bool inactiveFixtureRemoved;public int summonEvents,spawnEvents,creditCost,spawnValue,pendingPeak,ambientItems,boostHpItems,boostDamageItems;public uint goldExpected,experienceExpected,moneyBefore,moneyAfter,teamLevel;public ulong experienceBefore,experienceAfter;public float spawnLevelBeforeStart,spawnLevelAfterStart;public int acquisitionCount,equipmentIndex;public float bodyCost,compensatedDifficulty,deathAt,experienceAt,goldEvents;public string scope;public string seed,seedSource;
 }
 // Shared with the director, enemy/world lifecycle and reward observers.
 ResourceLocationMap rewardLocator;GameObject[] rewardPrefabs;GameObject rewardDirectorHost;
 ExperienceManager rewardExperience;CombatDirector rewardDirector;CharacterSpawnCard rewardCard;CharacterMaster rewardPlayerMaster;
 readonly List<CharacterMaster> ownedRewardSummons=new List<CharacterMaster>();
 EnemyRewardSession enemyRewardSession;
 EnemyRewardSession GetEnemyRewardSession(){if(enemyRewardSession==null)enemyRewardSession=new EnemyRewardSession(this);return enemyRewardSession;}
 static FieldInfo RewardField(Type type,string name){return EnemyRewardSession.RewardField(type,name);}
 IEnumerator PrepareEnemyRewards(CharacterBody player,SessionConfig cfg){return GetEnemyRewardSession().PrepareEnemyRewards(player,cfg);}
 void InitializeRewardRunStreams(SessionConfig cfg){GetEnemyRewardSession().InitializeRewardRunStreams(cfg);}
 void RefreshRewardEquipmentMask(bool rulesReady){GetEnemyRewardSession().RefreshRewardEquipmentMask(rulesReady);}
 void RewardGold(float amount){GetEnemyRewardSession().RewardGold(amount);}
 void RewardSummon(MasterSummon.MasterSummonReport report){GetEnemyRewardSession().RewardSummon(report);}
 IEnumerator SpawnRewardEnemy(GameObject bodyTemplate,Vector3 position,CharacterBody player,SessionConfig cfg){return GetEnemyRewardSession().SpawnRewardEnemy(bodyTemplate,position,player,cfg);}
 void RecordRewardSpawn(GameObject obj){GetEnemyRewardSession().RecordRewardSpawn(obj);}
 void CaptureRewardSummons(GameObject bodyTemplate,GameObject template){GetEnemyRewardSession().CaptureRewardSummons(bodyTemplate,template);}
 void ObserveEnemyRewards(){GetEnemyRewardSession().ObserveEnemyRewards();}
 void VerifyEnemyRewardDelivery(){GetEnemyRewardSession().VerifyEnemyRewardDelivery();}
 void CleanupRewardHosts(){GetEnemyRewardSession().Dispose();}
 IEnumerator CleanupEnemyRewards(){return GetEnemyRewardSession().CleanupEnemyRewards();}

 // Create on first use and retain for partial setup, repeated cleanup and later
 // observations. Dispose only tears down hosts and restores Run state; provider
 // release stays in Start's later awaited coroutine after Run destruction.
 sealed class EnemyRewardSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  const string RewardBundle="enemy-reward-lab";
  readonly string[] rewardPaths={"Prefabs/Effects/CoinEmitter","Prefabs/NetworkedObjects/LogPickup","Prefabs/ExpOrb"};
  GameObject rewardExperienceHost,rewardPlacementHost;
  EffectDef[] priorRewardEffects;bool ownsRewardEffects,observesRewardSummon;object priorCoinPrefab,priorLogPrefab,priorOrbPrefab;
  Xoroshiro128Plus priorStageRng,priorStageGenerator,priorRunRng,priorLoopRng,priorNextStageRng;ulong priorRunSeed;string[] priorRunLoopResetFlags;bool ownsRewardRunRng;ItemMask ownedRewardMask;Run rewardRun;TeamComponent rewardFixtureTeam;TeamIndex priorRewardFixtureTeam;
  EquipmentMask ownedRewardEquipmentMask;
  public EnemyRewardSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public static FieldInfo RewardField(Type type,string name){return type.GetField(name,BindingFlags.NonPublic|BindingFlags.Static);}
  public IEnumerator PrepareEnemyRewards(CharacterBody player,SessionConfig cfg){
   coordinator.r.rewards=new RewardReport{scope="Original directed spawn and server gold/timed XP; no sustained waves, connected-client effects, level-up, logbook/profile or full Run lifecycle",deathAt=-1,experienceAt=-1};coordinator.r.phase="enemy-reward-provider";coordinator.Save();
   coordinator.Check(!ExperienceManager.instance&&!DirectorCore.instance&&CombatDirector.instancesList.Count==0,"Existing reward/director context");coordinator.Check(NetworkServer.active&&!NetworkClient.active,"Measured server-only reward scope changed");
   priorCoinPrefab=RewardField(typeof(DeathRewards),"coinEffectPrefab").GetValue(null);priorLogPrefab=RewardField(typeof(DeathRewards),"logbookPrefab").GetValue(null);priorOrbPrefab=RewardField(typeof(ExperienceManager),"experienceOrbPrefab").GetValue(null);coordinator.Check(priorCoinPrefab==null&&priorLogPrefab==null&&priorOrbPrefab==null,"Existing reward prefab references");
   var bundle=new ResourceLocationBase(RewardBundle,System.IO.Path.Combine(Application.persistentDataPath,"payload",RewardBundle),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));bundle.Data=new AssetBundleRequestOptions{BundleName=RewardBundle};coordinator.rewardLocator=new ResourceLocationMap("enemy-reward-probe");
   coordinator.Check(cfg.enemyRewardKeys.Length==3&&cfg.enemyRewardAssets.Length==3,"Measured reward asset count");
   for(int i=0;i<3;i++){string key;coordinator.Check(LegacyResourcesAPI.GetGuid(rewardPaths[i],out key)&&key==cfg.enemyRewardKeys[i],"Original reward legacy identity "+rewardPaths[i]);coordinator.rewardLocator.Add(key,new ResourceLocationBase(key,cfg.enemyRewardAssets[i],typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));}
   Addressables.AddResourceLocator(coordinator.rewardLocator);MovementBatchProbe.StaticCall(typeof(DeathRewards),"LoadAssets");
   rewardExperienceHost=new GameObject("Owned original ExperienceManager");rewardExperienceHost.SetActive(false);coordinator.rewardExperience=rewardExperienceHost.AddComponent<ExperienceManager>();rewardExperienceHost.SetActive(true);
   float deadline=Time.realtimeSinceStartup+8;while(LegacyResourcesAPI.ActiveCount!=0&&Time.realtimeSinceStartup<deadline)yield return null;yield return null;
   coordinator.rewardPrefabs=new[]{(GameObject)RewardField(typeof(DeathRewards),"coinEffectPrefab").GetValue(null),(GameObject)RewardField(typeof(DeathRewards),"logbookPrefab").GetValue(null),(GameObject)RewardField(typeof(ExperienceManager),"experienceOrbPrefab").GetValue(null)};
   var names=new[]{"CoinEmitter","LogPickup","ExpOrb"};coordinator.Check(LegacyResourcesAPI.ActiveCount==0&&ExperienceManager.instance==coordinator.rewardExperience,"Original reward callbacks incomplete");for(int i=0;i<3;i++)coordinator.Check(coordinator.rewardPrefabs[i]&&coordinator.rewardPrefabs[i].name==names[i]&&coordinator.rewardPrefabs[i].GetComponentsInChildren<Component>(true).All(x=>x),"Genuine reward prefab contract "+names[i]);
   var entries=typeof(EffectCatalog).GetField("entries",BindingFlags.NonPublic|BindingFlags.Static);priorRewardEffects=(EffectDef[])entries.GetValue(null);coordinator.Check(priorRewardEffects.Length==0,"Existing effect catalog");ownsRewardEffects=true;coordinator.InitializeComposedEffects(new[]{new EffectDef(coordinator.rewardPrefabs[0])}.Concat(cfg.teleporterLoop?coordinator.ObjectiveEffects(cfg):new EffectDef[0]).GroupBy(x=>x.prefab).Select(x=>x.First()).ToArray());coordinator.Check(EffectCatalog.FindEffectIndexFromPrefab(coordinator.rewardPrefabs[0])!=EffectIndex.Invalid,"Original coin effect catalog identity");
   rewardRun=Run.instance;if(cfg.teleporterLoop){rewardRun.selectedDifficulty=coordinator.SelectedOfflineDifficulty();player.RecalculateStats();}
   coordinator.Check(rewardRun&&rewardRun.expansionLockedItems==null&&rewardRun.expansionLockedEquipment==null,"Existing expansion item/equipment mask");ownedRewardMask=ItemMask.Rent();rewardRun.expansionLockedItems=ownedRewardMask;
   ownedRewardEquipmentMask=EquipmentMask.Rent();rewardRun.expansionLockedEquipment=ownedRewardEquipmentMask;RefreshRewardEquipmentMask(false);
   var internalItems=new[]{RoR2Content.Items.UseAmbientLevel,RoR2Content.Items.BoostHp,RoR2Content.Items.BoostDamage};if(cfg.originalItemPickup)internalItems=internalItems.Concat(new[]{RoR2Content.Items.Syringe}).ToArray();if(cfg.originalChestDropTable){var baseLoot=RoR2Content.Items.ChainLightning;coordinator.Check(baseLoot&&!baseLoot.requiredExpansion&&!baseLoot.unlockableDef&&baseLoot.tier==ItemTier.Tier2,"Measured base loot definition contract changed");internalItems=internalItems.Concat(new[]{baseLoot}).ToArray();}coordinator.Check(internalItems.All(x=>x&&!x.requiredExpansion),"Required allowed items must be original base definitions");
   if(cfg.integratedWorld){var loot=coordinator.WorldLoot(cfg);foreach(var item in loot)coordinator.Check(item&&!item.requiredExpansion&&coordinator.HasOwnedProfileUnlock(item.unlockableDef),"Integrated unlocked base loot unavailable: "+(item?item.name:"missing definition"));internalItems=internalItems.Concat(loot).Distinct().ToArray();}
   if(cfg.teleporterLoop)internalItems=internalItems.Concat(coordinator.ComposedBaseBossRewards(cfg)).Distinct().ToArray();
   bool completeDefinitions=cfg.integratedWorld&&Resources.Load<TextAsset>("WholeCatalogBootstrap");
   foreach(var item in ItemCatalog.allItemDefs)if(completeDefinitions?(bool)item.requiredExpansion:!internalItems.Contains(item))ownedRewardMask.Add(item.itemIndex);
   coordinator.Check(internalItems.All(x=>!rewardRun.IsItemExpansionLocked(x.itemIndex))&&ItemCatalog.allItemDefs.All(item=>rewardRun.IsItemExpansionLocked(item.itemIndex)==(completeDefinitions?(bool)item.requiredExpansion:!internalItems.Contains(item))),"Owned item expansion mask changed");
   coordinator.rewardPlayerMaster=player.master;coordinator.Check(player.isPlayerControlled&&coordinator.rewardPlayerMaster&&TeamManager.instance,"Original reward recipient missing");
   rewardFixtureTeam=coordinator.host.GetComponent<TeamComponent>();priorRewardFixtureTeam=rewardFixtureTeam.teamIndex;coordinator.r.rewards.playerTeamBefore=TeamComponent.GetTeamMembers(TeamIndex.Player).Count;
   coordinator.Check(coordinator.host!=player.gameObject&&!coordinator.host.activeInHierarchy&&rewardFixtureTeam.body.master==coordinator.rewardPlayerMaster&&priorRewardFixtureTeam==TeamIndex.Player&&coordinator.r.rewards.playerTeamBefore==2,"Measured inactive fixture/team identity changed");rewardFixtureTeam.teamIndex=TeamIndex.None;coordinator.r.rewards.playerTeamAfter=TeamComponent.GetTeamMembers(TeamIndex.Player).Count;coordinator.Check(coordinator.r.rewards.playerTeamAfter==1&&TeamComponent.GetTeamMembers(TeamIndex.Player)[0]==player.teamComponent,"Original reward recipient must be the sole live player body");coordinator.r.rewards.inactiveFixtureRemoved=true;coordinator.r.rewards.moneyBefore=coordinator.rewardPlayerMaster.money;coordinator.r.rewards.experienceBefore=TeamManager.instance.GetTeamExperience(TeamIndex.Player);coordinator.rewardPlayerMaster.OnGoldCollected+=RewardGold;
   // The original source ClassicStageInfo.Awake consumes the stage RNG when its
   // scene root activates, before the directed enemy spawn below.
   InitializeRewardRunStreams(cfg);
   if(cfg.automaticDirector){var assets=coordinator.PrepareDirectorAssets(cfg,bundle);while(assets.MoveNext())yield return assets.Current;}coordinator.r.rewards.assetsReady=true;coordinator.Save();
  }
  public void InitializeRewardRunStreams(SessionConfig cfg){
   priorStageGenerator=rewardRun.stageRngGenerator;priorStageRng=rewardRun.stageRng;priorRunRng=rewardRun.runRNG;priorLoopRng=rewardRun.loopRngGenerator;priorNextStageRng=rewardRun.nextStageRng;priorRunSeed=rewardRun.seed;
   coordinator.Check(priorStageGenerator==null&&priorStageRng==null&&priorRunRng==null&&priorLoopRng==null&&priorNextStageRng==null,"Existing Run RNG context");ownsRewardRunRng=true;
   priorRunLoopResetFlags=rewardRun.EventFlagsToResetOnLoop;coordinator.Check(!cfg.teleporterLoop||cfg.runEventFlagsToResetOnLoop!=null,"Original loop-reset settings absent");
   if(priorRunLoopResetFlags==null)rewardRun.EventFlagsToResetOnLoop=cfg.runEventFlagsToResetOnLoop==null?Array.Empty<string>():cfg.runEventFlagsToResetOnLoop.ToArray();
   else coordinator.Check(cfg.integratedWorld&&cfg.runEventFlagsToResetOnLoop!=null&&priorRunLoopResetFlags.SequenceEqual(cfg.runEventFlagsToResetOnLoop),"Original ClassicRun loop-reset settings differ from accepted input");
   rewardRun.seed=coordinator.SelectOwnedRunSeed(cfg);coordinator.r.rewards.seed=rewardRun.seed.ToString(System.Globalization.CultureInfo.InvariantCulture);rewardRun.runRNG=new Xoroshiro128Plus(rewardRun.seed);rewardRun.nextStageRng=new Xoroshiro128Plus(rewardRun.runRNG.nextUlong);
   if(coordinator.firstStagePolicyConsumed)coordinator.Check(rewardRun.nextStageRng.nextNormalizedFloat==coordinator.firstStageSelectionValue,"Original starting-scene RNG draw differs from the owned Run stream");
   rewardRun.stageRngGenerator=new Xoroshiro128Plus(rewardRun.runRNG.nextUlong);MovementBatchProbe.Call(rewardRun,"GenerateStageRNG");MovementBatchProbe.Call(rewardRun,"GenerateLoopRNG");
  }
  public void RefreshRewardEquipmentMask(bool rulesReady){
   coordinator.Check(rewardRun&&ownedRewardEquipmentMask!=null&&rewardRun.expansionLockedEquipment==ownedRewardEquipmentMask,"Original equipment expansion mask is unowned");ownedRewardEquipmentMask.Clear();int locked=0;
   foreach(var index in EquipmentCatalog.allEquipment){var definition=EquipmentCatalog.GetEquipmentDef(index);coordinator.Check(definition&&definition.equipmentIndex==index,"Original equipment catalog identity missing");if(definition.requiredExpansion&&(!rulesReady||!rewardRun.IsExpansionEnabled(definition.requiredExpansion))){ownedRewardEquipmentMask.Add(index);locked++;}}
   coordinator.r.rewards.equipmentDefinitions=EquipmentCatalog.equipmentCount;coordinator.r.rewards.expansionLockedEquipment=locked;coordinator.r.rewards.equipmentMaskReady=true;
  }
  public void RewardGold(float amount){coordinator.r.rewards.goldEvents+=amount;}
  public void RewardSummon(MasterSummon.MasterSummonReport report){if(report.summonMasterInstance&&report.masterSummon.masterPrefab==coordinator.rewardCard.prefab){if(coordinator.IsWorldItemGhost(report.summonMasterInstance))return;coordinator.r.rewards.summonEvents++;coordinator.Check(report.masterSummon.useAmbientLevel==true&&report.summonMasterInstance.teamIndex==TeamIndex.Monster,"Original summon contract changed");}}
  public IEnumerator SpawnRewardEnemy(GameObject bodyTemplate,Vector3 position,CharacterBody player,SessionConfig cfg){
   var source=coordinator.artifactBundle.LoadAsset<CharacterSpawnCard>(cfg.enemySpawnCardAsset);coordinator.Check(source&&source.name=="cscBeetle"&&source.directorCreditCost==8&&source.prefab.GetComponent<CharacterMaster>()&&source.sendOverNetwork&&!source.occupyPosition&&source.equipmentToGrant.Length==0&&source.itemsToGrant.Length==0&&(source.loadout==null||source.loadout.isEmpty),"Original cscBeetle contract changed");
   coordinator.rewardCard=MovementBatchProbe.Instantiate(source);coordinator.rewardCard.name=source.name;var template=MovementBatchProbe.Instantiate(coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyMasterAsset),coordinator.enemyTemplates.transform);template.name=source.prefab.name;template.GetComponent<Inventory>().enabled=false;template.GetComponent<CharacterMaster>().bodyPrefab=bodyTemplate;template.SetActive(true);coordinator.rewardCard.prefab=template;
   coordinator.Check(ownsRewardRunRng&&rewardRun.stageRng!=null&&rewardRun.runRNG!=null,"Original Run RNG streams must precede source scene activation");
   coordinator.rewardDirectorHost=new GameObject("Owned directed original spawn context");coordinator.rewardDirectorHost.SetActive(false);coordinator.rewardDirectorHost.AddComponent<DirectorCore>();if(!cfg.automaticDirector){coordinator.rewardDirector=coordinator.rewardDirectorHost.AddComponent<CombatDirector>();coordinator.rewardDirector.enabled=false;coordinator.rewardDirector.moneyWaveIntervals=new RangeFloat[0];coordinator.rewardDirector.ignoreTeamSizeLimit=true;}coordinator.rewardDirectorHost.SetActive(true);coordinator.Check(DirectorCore.instance==coordinator.rewardDirectorHost.GetComponent<DirectorCore>(),"Original DirectorCore singleton missing");
   MasterSummon.onServerMasterSummonGlobal+=RewardSummon;observesRewardSummon=true;
   if(cfg.automaticDirector){var automatic=coordinator.SpawnAutomaticEnemy(template,player,cfg);while(automatic.MoveNext())yield return automatic.Current;}
   else{rewardPlacementHost=new GameObject("Owned initial spawn target");rewardPlacementHost.transform.SetPositionAndRotation(position,Quaternion.LookRotation(player.transform.position-position));coordinator.rewardDirector.onSpawnedServer=new CombatDirector.OnSpawnedServer();coordinator.rewardDirector.onSpawnedServer.AddListener(RecordRewardSpawn);
    try{coordinator.Check(coordinator.rewardDirector.Spawn(coordinator.rewardCard,null,rewardPlacementHost.transform,DirectorCore.MonsterSpawnDistance.Standard,false,1,DirectorPlacementRule.PlacementMode.Direct),"Original directed spawn failed");}
    finally{CaptureRewardSummons(bodyTemplate,template);}
   }
   coordinator.Check(coordinator.enemyMaster&&coordinator.enemyBody&&coordinator.r.rewards.spawnEvents==1&&coordinator.r.rewards.summonEvents==1,"Original director/summon/body result missing");
   var rewards=coordinator.enemyBody.GetComponent<DeathRewards>();coordinator.Check(rewards&&!rewards.logUnlockableDef,"Original rewards or optional logbook scope missing");coordinator.r.rewards.creditCost=coordinator.rewardCard.directorCreditCost;coordinator.r.rewards.bodyCost=coordinator.enemyBody.cost;coordinator.r.rewards.compensatedDifficulty=Run.instance.compensatedDifficultyCoefficient;coordinator.r.rewards.spawnValue=rewards.spawnValue;coordinator.r.rewards.goldExpected=rewards.goldReward;coordinator.r.rewards.experienceExpected=rewards.expReward;
   coordinator.r.rewards.ambientItems=coordinator.enemyMaster.inventory.GetItemCountPermanent(RoR2Content.Items.UseAmbientLevel);coordinator.r.rewards.boostHpItems=coordinator.enemyMaster.inventory.GetItemCountPermanent(RoR2Content.Items.BoostHp);coordinator.r.rewards.boostDamageItems=coordinator.enemyMaster.inventory.GetItemCountPermanent(RoR2Content.Items.BoostDamage);
   coordinator.r.rewards.acquisitionCount=coordinator.enemyMaster.inventory.itemAcquisitionOrder.Count;coordinator.r.rewards.equipmentIndex=(int)coordinator.enemyMaster.inventory.currentEquipmentIndex;
   coordinator.Check(coordinator.r.rewards.bodyCost==8&&coordinator.r.rewards.compensatedDifficulty==1&&coordinator.r.rewards.spawnValue==1,"Original spawn cost/difficulty assertions failed");coordinator.Check(coordinator.r.rewards.goldExpected==3&&coordinator.r.rewards.experienceExpected==1,"Original director reward values failed");coordinator.Check(coordinator.r.rewards.ambientItems==1&&coordinator.r.rewards.boostHpItems==0&&coordinator.r.rewards.boostDamageItems==0&&coordinator.r.rewards.acquisitionCount==1&&coordinator.enemyMaster.inventory.currentEquipmentIndex==EquipmentIndex.None,"Original spawn internal inventory assertions failed");coordinator.r.rewards.directedSpawn=true;coordinator.r.rewards.spawnContract=true;
   // Whole-catalog availability depends on the loaded earned profile and native rules.
   // Keep its startup wave until PrepareTeleporterWorld selects the stage pool once.
   if(cfg.integratedWorld&&coordinator.r.liveCatalogs==null)coordinator.SelectStageCombatDeck(cfg,coordinator.stageGeometryScene.name);coordinator.Save();
  }
  public void RecordRewardSpawn(GameObject obj){coordinator.r.rewards.spawnEvents++;var master=obj.GetComponent<CharacterMaster>();if(!coordinator.ownedRewardSummons.Contains(master))coordinator.ownedRewardSummons.Add(master);if(coordinator.r.rewards.spawnEvents!=1)return;coordinator.enemyMasterHost=obj;coordinator.enemyMaster=master;coordinator.enemyBody=coordinator.enemyMaster.GetBody();coordinator.r.rewards.spawnLevelBeforeStart=coordinator.enemyBody.level;}
  public void CaptureRewardSummons(GameObject bodyTemplate,GameObject template){coordinator.ownedRewardSummons.AddRange(Resources.FindObjectsOfTypeAll<CharacterMaster>().Where(x=>x.gameObject.scene.IsValid()&&x.gameObject!=template&&x.bodyPrefab==bodyTemplate&&!coordinator.ownedRewardSummons.Contains(x)));}
  public void ObserveEnemyRewards(){
   if(coordinator.r.rewards==null||!coordinator.rewardExperience||!TeamManager.instance)return;var pending=(IList)typeof(ExperienceManager).GetField("pendingAwards",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(coordinator.rewardExperience);coordinator.r.rewards.pendingPeak=Math.Max(coordinator.r.rewards.pendingPeak,pending.Count);coordinator.r.rewards.queuedExperience|=pending.Count>0;
   if(coordinator.r.enemy.dead&&coordinator.r.rewards.deathAt<0)coordinator.r.rewards.deathAt=Time.realtimeSinceStartup;coordinator.r.rewards.moneyAfter=coordinator.rewardPlayerMaster?coordinator.rewardPlayerMaster.money:0;coordinator.r.rewards.experienceAfter=TeamManager.instance.GetTeamExperience(TeamIndex.Player);coordinator.r.rewards.teamLevel=TeamManager.instance.GetTeamLevel(TeamIndex.Player);
   if(coordinator.r.rewards.experienceAfter>coordinator.r.rewards.experienceBefore&&coordinator.r.rewards.experienceAt<0)coordinator.r.rewards.experienceAt=Time.realtimeSinceStartup;coordinator.r.rewards.delivered=coordinator.r.rewards.moneyAfter-coordinator.r.rewards.moneyBefore==coordinator.r.rewards.goldExpected&&coordinator.r.rewards.experienceAfter-coordinator.r.rewards.experienceBefore==coordinator.r.rewards.experienceExpected;
  }
  public void VerifyEnemyRewardDelivery(){ObserveEnemyRewards();coordinator.Check(coordinator.r.rewards.assetsReady&&coordinator.r.rewards.directedSpawn&&coordinator.r.rewards.spawnContract&&coordinator.r.rewards.delivered&&coordinator.r.rewards.queuedExperience&&coordinator.r.rewards.pendingPeak==1&&coordinator.r.rewards.goldEvents==coordinator.r.rewards.goldExpected&&coordinator.r.rewards.teamLevel==1&&coordinator.r.rewards.experienceAt-coordinator.r.rewards.deathAt>1.5f&&coordinator.r.rewards.experienceAt-coordinator.r.rewards.deathAt<2.2f,"Original gold/timed experience delivery incomplete");}
  public void Dispose(){if(coordinator.r.rewards==null)return;coordinator.CleanupAutomaticDirector();if(observesRewardSummon){MasterSummon.onServerMasterSummonGlobal-=RewardSummon;observesRewardSummon=false;}if(coordinator.rewardPlayerMaster)coordinator.rewardPlayerMaster.OnGoldCollected-=RewardGold;if(rewardFixtureTeam)rewardFixtureTeam.teamIndex=priorRewardFixtureTeam;foreach(var summon in coordinator.ownedRewardSummons)if(summon&&summon.gameObject!=coordinator.enemyMasterHost)NetworkServer.Destroy(summon.gameObject);if(rewardExperienceHost)MovementBatchProbe.Destroy(rewardExperienceHost);if(coordinator.rewardDirectorHost)MovementBatchProbe.Destroy(coordinator.rewardDirectorHost);if(rewardPlacementHost)MovementBatchProbe.Destroy(rewardPlacementHost);if(coordinator.rewardCard)MovementBatchProbe.Destroy(coordinator.rewardCard);if(rewardRun){rewardRun.stageRng=priorStageRng;rewardRun.stageRngGenerator=priorStageGenerator;if(ownsRewardRunRng){rewardRun.runRNG=priorRunRng;rewardRun.loopRngGenerator=priorLoopRng;rewardRun.nextStageRng=priorNextStageRng;rewardRun.seed=priorRunSeed;rewardRun.EventFlagsToResetOnLoop=priorRunLoopResetFlags;ownsRewardRunRng=false;}if(ownedRewardMask!=null&&rewardRun.expansionLockedItems==ownedRewardMask)rewardRun.expansionLockedItems=null;if(ownedRewardEquipmentMask!=null&&rewardRun.expansionLockedEquipment==ownedRewardEquipmentMask)rewardRun.expansionLockedEquipment=null;}if(ownedRewardMask!=null){ItemMask.Return(ownedRewardMask);ownedRewardMask=null;}if(ownedRewardEquipmentMask!=null){EquipmentMask.Return(ownedRewardEquipmentMask);ownedRewardEquipmentMask=null;}}
  public IEnumerator CleanupEnemyRewards(){
   if(coordinator.rewardLocator==null)yield break;yield return null;coordinator.Check(coordinator.ownedRewardSummons.All(x=>!x)&&!rewardExperienceHost&&!coordinator.rewardDirectorHost&&!rewardPlacementHost&&!coordinator.rewardCard&&!ExperienceManager.instance&&!DirectorCore.instance&&CombatDirector.instancesList.Count==0,"Owned reward/director teardown incomplete");
   coordinator.ReleaseCompletedRunAsyncAssets();
   if(ownsRewardEffects){coordinator.RestoreComposedEffects(priorRewardEffects);ownsRewardEffects=false;}coordinator.ReleaseDirectorAssets();
   RewardField(typeof(DeathRewards),"coinEffectPrefab").SetValue(null,priorCoinPrefab);RewardField(typeof(DeathRewards),"logbookPrefab").SetValue(null,priorLogPrefab);RewardField(typeof(ExperienceManager),"experienceOrbPrefab").SetValue(null,priorOrbPrefab);
   var poolCache=(IDictionary)RewardField(typeof(EffectManager),"_ShouldUsePooledEffectMap").GetValue(null);if(coordinator.rewardPrefabs!=null)foreach(var prefab in coordinator.rewardPrefabs)if(prefab){poolCache.Remove(prefab);Addressables.Release(prefab);}yield return null;
   if(AssetBundle.GetAllLoadedAssetBundles().Any(x=>x.name==RewardBundle)){
    // Observe the current native cache graph before rejecting retention; never decrement unknown leases.
    var cache=(IDictionary)typeof(UnityEngine.ResourceManagement.ResourceManager).GetField("m_AssetOperationCache",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(Addressables.ResourceManager);
    var contract=typeof(UnityEngine.ResourceManagement.ResourceManager).Assembly.GetType("UnityEngine.ResourceManagement.AsyncOperations.IAsyncOperation");var rows=new List<string>();
    foreach(DictionaryEntry pair in cache){
     var operation=pair.Value;var name=(string)contract.GetProperty("DebugName").GetValue(operation);var references=contract.GetProperty("ReferenceCount").GetValue(operation);
     if(name.Contains(RewardBundle)||(coordinator.rewardPrefabs??new GameObject[0]).Any(prefab=>prefab&&name.Contains(prefab.name)))rows.Add(name+" / references="+references);
     var dependencies=new List<AsyncOperationHandle>();contract.GetMethod("GetDependencies").Invoke(operation,new object[]{dependencies});
     foreach(var dependency in dependencies.Where(handle=>handle.IsValid())){
      var dependencyName=dependency.DebugName;
      if(dependencyName.Contains(RewardBundle))rows.Add("owner="+name+" / references="+references+" -> "+dependencyName);
     }
    }
    coordinator.r.rewards.retainedOperations=rows.ToArray();coordinator.Save();
   }
   coordinator.Check(!AssetBundle.GetAllLoadedAssetBundles().Any(x=>x.name==RewardBundle),"Reward provider bundle retained");Addressables.RemoveResourceLocator(coordinator.rewardLocator);coordinator.rewardLocator=null;coordinator.r.rewards.cleaned=true;coordinator.Save();
  }
 }
}
