using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Persistent local gameplay composition. Original simulation, purchases, loot and rewards
// remain in the preserved assemblies. The shell supplies content/context and unavailable audio UI.
public sealed partial class MovementBatchProbe {
 [Serializable] public class WorldPickupObservation {public string item,interactability;public Vector3 position,aimTarget;public float aimDistance;public bool selected,collider,interactableLayer;}
 [Serializable] public class WorldPickupMessageObservation {public float at;public bool resolvedMaster,playerMaster,knownPickup;public uint masterId,quantity;public int pickupIndex;public string item;}
 [Serializable] public class WorldItemObservation {public string item,tier;public int count;}
 [Serializable] public class WorldMessageFailure {public float at;public int id;public string side,handler,error;}
 [Serializable] public class NavigationPathPoint {public Vector3 position;public float minimumJumpHeight;}
 [Serializable] public class WorldReport {
  public int nativeEffectSourceRenderers,nativeEffectSourceMaterials;public ObjectiveRendererObservation[] nativeEffectViews;

  public NovaThirdPersonView.Report camera;public WorldEquipmentReport equipment;
  public bool lunarDefinition,lunarCurrencyAvailable;
  public bool ready,authority,lootReady,interactionReady,cleaned,diagnosticInput;
  public int tableLoadedCount,barrels,chests,openedBarrels,openedChests,pickups,droplets,pickupMessages,coinMessages,xpMessages,frames,kills,liveEnemies;
  public int lootDomain,syringe,lightning,glasses,slug,drink,steak,secondary,roll,barrage;public uint money;public ulong experience;
  public int lootTier1,lootTier2,lootTier3;public float shield,maxShield,armor;public WorldItemObservation[] itemStacks;
  public int featherJumps,featherEffectLoads;public bool featherEffectCleaned,featherInputAttempted;public string featherInputOutcome;
  public int nativeLootProviderLoads,healthPacks,moneyPacks,stunImpactLoads,slowedEnemiesPeak;public bool nativeLootProvidersCleaned;
  public int stickyBombLoads,stickyBombSpawns,wispDelaySpawns;
  public float simulationSeconds,seconds,health,maxHealth,level,attackSpeed,crit,regen,moveSpeed,difficulty,distance;
  public string scope,objective,target,lastPickup,feedbackCapability;public Vector3 start,position;
  public float interactionDistance;public WorldPickupObservation[] pickupObservations;
  public List<WorldPickupMessageObservation> pickupMessageObservations=new List<WorldPickupMessageObservation>();public int unresolvedPickupMessages,otherPickupMessages,zeroCountPickupMessages;
  public List<WorldMessageFailure> messageFailures=new List<WorldMessageFailure>();public int messageFailureCount;
  public string navigationTarget;public bool navigationReachable,navigationJump;public int navigationWaypoints;public Vector3 navigationDestination,navigationWaypoint;
  public int navigationRecoveries,navigationRecoveryJumpFrames;public float navigationStalledSeconds,navigationProgressDistance,navigationObjectiveStalledSeconds,navigationObjectiveProgressDistance;public bool navigationRecoveryJump;
  public Vector3 navigationReference,navigationLocalMovement;public bool navigationLocalObstructed,navigationAllowWalkOffCliff;public float navigationLocalJumpSpeed;public NavigationPathPoint[] navigationPath;
  public bool navigationTerrainFallback,navigationTerrainNoCandidate,navigationSprint;public int navigationTerrainFrames,navigationTerrainBlocked;public Vector3 navigationTerrainTarget;
 public int navigationTerrainLowerChoices,navigationTerrainRayOverflow;
  public bool navigationPartial;public int navigationPartialCandidates,navigationPartialNode=-1;public float navigationPartialSeconds;public Vector3 navigationPartialDestination;
  public string navigationHull,navigationJumpHeight;public int navigationGraphNodes,navigationStartNode=-1,navigationNearestNode=-1,navigationApproachBoundsRejected,navigationApproachTooShort,navigationApproachUnreachable;public float navigationMaxSpeed,navigationMaxSlope,navigationGravityY;public Vector3 navigationStartPosition;
  public bool motorGrounded,motorStable,jumpDown,jumpPressed,jumpClaimed;public int motorJumpCount,motorMaxJumpCount;public Vector3 motorVelocity,motorGroundPoint;public string motorGroundCollider,movementState;
  public bool manualTakeover;
  public int combatMotionSamples,combatMotionBlocked,combatCandidates,combatBoundsRejected,travelDefenseFrames;public string combatTarget,travelDefenseTarget;public Vector3 combatGround,combatDestination;public Vector2 combatMotion;
  public int combatVisibleCandidates,combatOccludedCandidates,combatApproachFrames;public bool combatLineOfSight,combatTargetBoss,combatHoldoutConstrained;public float combatTargetDistance,combatThreatDistance;public Vector3 combatAimOrigin,combatAimTarget;
  public Vector3 combatTargetPhysicsPosition,combatTargetCorePosition;
 }
 readonly List<GameObject> worldObjects=new List<GameObject>();
 readonly List<Transform> worldModels=new List<Transform>();
 readonly List<Material> worldMaterials=new List<Material>();
 readonly HashSet<int> worldPresented=new HashSet<int>();
 readonly List<BarrelInteraction> worldBarrels=new List<BarrelInteraction>();
 readonly List<ChestBehavior> worldChests=new List<ChestBehavior>();
 GameObject worldStaging,worldPause;InteractionDriver worldDriver;CharacterBody worldPlayer;
 ResourceLocationMap worldDropletLocator;GameObject worldDropletSource;FieldInfo worldDropletField;
 object priorWorldDroplet;bool ownsWorldDroplet,ownsWorldLists;BasicPickupDropTable worldChestTable;
 RoR2.ConVar.IntConVar worldVfxOption;string priorWorldVfx,priorWorldXp;
 AsyncOperationHandle<GameObject> worldCoinLease;bool ownsWorldCoinLease;int worldCoinBaseline,worldBarrelConsumers;bool ownsIntegratedPools;
 Action<Interactor,IInteractable,GameObject> worldInteraction;
 bool ownsWorldTeleportHandler;
 readonly Dictionary<short,NetworkMessageDelegate> worldClientHandlers=new Dictionary<short,NetworkMessageDelegate>(),worldServerHandlers=new Dictionary<short,NetworkMessageDelegate>(),worldClientObservers=new Dictionary<short,NetworkMessageDelegate>(),worldServerObservers=new Dictionary<short,NetworkMessageDelegate>();
 int worldObjective;float worldLastPress=-1;
 RoR2.PathFollower worldPathFollower=new RoR2.PathFollower();Vector3 worldPathTarget;float worldPathRequested=-100;
 LocalNavigator worldLocalNavigator=new LocalNavigator();CharacterBody worldNavigationBody;float worldNavigationUpdatedAt;
 Vector3 worldNavigationProgressWaypoint,worldNavigationProgressDestination;float worldNavigationProgressDistance,worldNavigationProgressAt,worldNavigationRecoveryUntil=-1;bool worldNavigationHasProgress;
 Vector3 worldNavigationObjective;float worldNavigationObjectiveDistance,worldNavigationObjectiveProgressAt;bool worldNavigationHasObjectiveProgress;
 Vector3 worldTerrainTarget,worldTerrainGoal;float worldTerrainSelectedAt=-100,worldTerrainRecoveryUntil=-100;readonly List<Vector3> worldTerrainRecent=new List<Vector3>();
 readonly RaycastHit[] worldTerrainHits=new RaycastHit[64];
 NovaThirdPersonView worldView;bool restartRequested,worldManualTakeover;public int sessionIndex=1;
 bool ownsWorldMisc;MiscPickupDef[] previousWorldMiscContent;object previousWorldMiscCatalog;
 ResourceAvailability previousWorldMiscAvailability;LunarCoinDef worldLunarCoin;
Action<TeamIndex> unavailableTeamLevelSound;Action<Run> unavailableAmbientSound;Action<CharacterBody> unavailableLevelEffect;
Action<ItemIndex> unavailableItemHighlight;bool ownsWorldPresentation;
 ItemDef[] worldLootDefinitions;
 ItemMask worldAvailableItems,previousWorldAvailableItems;EquipmentMask worldAvailableEquipment,previousWorldAvailableEquipment;
 readonly Dictionary<FieldInfo,GameObject> worldLootEffectSlots=new Dictionary<FieldInfo,GameObject>();
 readonly List<GameObject> worldLootTemporaryEffects=new List<GameObject>();
 readonly Dictionary<Renderer,Material[]> worldLootSourceMaterials=new Dictionary<Renderer,Material[]>();
 readonly Dictionary<GameObject,int> worldLootSourceLayers=new Dictionary<GameObject,int>();
 int worldFeatherEffectIndex=-1,worldFeatherReferenceBaseline;CharacterBody.JumpDelegate worldFeatherJumped;
 readonly Dictionary<int,int> worldNativeLootLeaseBaselines=new Dictionary<int,int>();
 readonly HashSet<GameObject> worldNativeLootObjects=new HashSet<GameObject>();


 ItemDef[] WorldTierOneLoot(Result cfg){
  return WorldLoot(cfg).Where(x=>x.tier==ItemTier.Tier1).ToArray();
 }
 ItemDef[] WorldLoot(Result cfg){
  var loot=new List<ItemDef>{RoR2Content.Items.Syringe,RoR2Content.Items.CritGlasses,RoR2Content.Items.HealWhileSafe};
  // Receipted additions only. Older accepted configurations retain their original pool.
  if(cfg.teleporterLoop&&cfg.objectiveItemNames!=null){
   if(cfg.objectiveItemNames.Contains("SprintBonus"))loot.Add(RoR2Content.Items.SprintBonus);
   if(cfg.objectiveItemNames.Contains("FlatHealth"))loot.Add(RoR2Content.Items.FlatHealth);
  }
  loot.Add(RoR2Content.Items.ChainLightning);
  if(cfg.worldAdditionalLootItems!=null)foreach(var name in cfg.worldAdditionalLootItems){var def=ItemCatalog.GetItemDef(ItemCatalog.FindItemIndex(name));Check(def&&def.name==name&&!def.requiredExpansion&&!def.unlockableDef&&!def.hidden,"Core loot identity/requirement unavailable: "+name);loot.Add(def);}
  Check(loot.All(x=>x)&&loot.Distinct().Count()==loot.Count,"Duplicate or absent composed loot definition");
  return loot.ToArray();
 }
 BuffDef[] WorldLootBuffs(Result cfg){
  if(cfg.worldAdditionalLootItems==null||!cfg.worldAdditionalLootItems.Contains("SlowOnHit"))return new BuffDef[0];
  var def=artifactBundle.LoadAsset<BuffDef>(cfg.worldLootSlowBuffAsset);Check(def&&def.name=="bdSlow60","Original loot slow buff missing");
  BindEnemyDefinition(typeof(RoR2Content.Buffs),"Slow60",def);return new[]{def};
 }
 GameObject[] PrepareWorldLootSupport(Result cfg){
  if(cfg.worldLootSupportPaths==null||cfg.worldLootSupportPaths.Length==0)return new GameObject[0];
  Check(cfg.worldLootSupportPaths.Length==2||cfg.worldLootSupportPaths.Length==3||cfg.worldLootSupportPaths.Length==6||cfg.worldLootSupportPaths.Length==7||cfg.worldLootSupportPaths.Length==9||cfg.worldLootSupportPaths.Length==10,"Core loot support contract length changed");
  r.phase="integrated-core-loot-support";Save();var effects=new List<GameObject>();
  foreach(var path in cfg.worldLootSupportPaths){
   int effectStart=effects.Count;var presentationRoots=new List<GameObject>();
   int index=Array.IndexOf(cfg.objectiveSupportPaths,path);Check(index>=0,"Core loot provider location absent: "+path);var source=objectiveSupportSources[index];
   bool shield=path=="Prefabs/Effects/ShieldBreakEffect",feather=path=="Prefabs/Effects/FeatherEffect",slow=path=="Prefabs/TemporaryVisualEffects/SlowDownTime",healthPack=path=="Prefabs/NetworkedObjects/HealPack",moneyPack=path=="Prefabs/NetworkedObjects/BonusMoneyPack";
   bool stun=path=="Prefabs/Effects/ImpactEffects/ImpactStunGrenade",diamond=path=="Prefabs/Effects/ImpactEffects/DiamondDamageBonusEffect";
   bool sticky=path=="Prefabs/Projectiles/StickyBomb",wisp=path=="Prefabs/NetworkedObjects/WilloWispDelay";
   Check(shield||feather||slow||healthPack||moneyPack||stun||sticky||wisp||diamond||path=="Prefabs/TemporaryVisualEffects/BucklerDefense","Unknown core loot support: "+path);
   Check(source&&source.name==(shield?"ShieldBreakEffect":feather?"FeatherEffect":slow?"SlowDownTime":healthPack?"HealPack":moneyPack?"BonusMoneyPack":stun?"ImpactStunGrenade":diamond?"DiamondDamageBonusEffect":sticky?"StickyBomb":wisp?"WilloWispDelay":"BucklerDefense"),"Core loot source prefab identity changed: "+path);
   if(slow||healthPack||moneyPack||stun||sticky)worldNativeLootLeaseBaselines.Add(index,(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[index]));
   if(feather){
    // Original ProcessJump loads this provider asset on each bonus jump.
    // Observe those real calls and release their owned leases on teardown.
    Check(worldPlayer&&r.world!=null&&worldFeatherEffectIndex<0,"Unowned Feather effect observation");worldFeatherEffectIndex=index;
    worldFeatherReferenceBaseline=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[index]);
    worldFeatherJumped=()=>{if(worldPlayer.characterMotor.jumpCount>worldPlayer.baseJumpCount)r.world.featherJumps++;};worldPlayer.onJump+=worldFeatherJumped;
   }else if(!healthPack&&!moneyPack&&!stun&&!sticky){
    var type=wisp?typeof(GlobalEventManager).GetNestedType("CommonAssets",BindingFlags.Public):(shield||diamond?typeof(HealthComponent):typeof(CharacterBody)).GetNestedType("AssetReferences",BindingFlags.NonPublic);
    var field=type.GetField(wisp?"explodeOnDeathPrefab":shield?"shieldBreakEffectPrefab":diamond?"diamondDamageBonusImpactEffectPrefab":slow?"slowDownTimeTempEffectPrefab":"bucklerShieldTempEffectPrefab",BindingFlags.Public|BindingFlags.Static);
    Check(field!=null&&field.FieldType==typeof(GameObject)&&!((GameObject)field.GetValue(null)),"Unowned core loot effect slot: "+path);
    worldLootEffectSlots.Add(field,(GameObject)field.GetValue(null));field.SetValue(null,source);
    Check((GameObject)field.GetValue(null)==source,"Core loot source binding failed: "+path);
   }
   if(shield||feather||stun||diamond){Check(source.GetComponent<EffectComponent>(),"Original core loot EffectComponent missing: "+path);effects.Add(source);}
   else if(healthPack){var pickup=source.GetComponentInChildren<HealthPickup>(true);Check(pickup&&pickup.baseObject==source&&pickup.teamFilter&&source.GetComponent<NetworkIdentity>()&&pickup.pickupEffect&&pickup.pickupEffect.GetComponent<EffectComponent>(),"Original heal pack linkage missing");effects.Add(pickup.pickupEffect);}
   else if(moneyPack){var pickup=source.GetComponentInChildren<MoneyPickup>(true);Check(pickup&&pickup.baseObject==source&&pickup.teamFilter&&source.GetComponent<NetworkIdentity>(),"Original money pack linkage missing");if(pickup.pickupEffectPrefab){Check(pickup.pickupEffectPrefab.GetComponent<EffectComponent>(),"Original money effect linkage missing");effects.Add(pickup.pickupEffectPrefab);}}
   else if(sticky){var controller=source.GetComponent<RoR2.Projectile.ProjectileController>();var explosion=source.GetComponent<RoR2.Projectile.ProjectileImpactExplosion>();Check(controller&&controller.ghostPrefab&&explosion&&explosion.impactEffect&&source.GetComponent<NetworkIdentity>(),"Original sticky projectile/ghost/blast contract missing");effects.Add(explosion.impactEffect);presentationRoots.Add(controller.ghostPrefab);}
   else if(wisp){var blast=source.GetComponent<DelayBlast>();Check(blast&&blast.explosionEffect&&source.GetComponent<TeamFilter>()&&source.GetComponent<NetworkIdentity>(),"Original on-kill delay/blast contract missing");if(blast.delayEffect)effects.Add(blast.delayEffect);effects.Add(blast.explosionEffect);}
   else Check(source.GetComponent<TemporaryVisualEffect>()&&source.GetComponent<TemporaryVisualEffect>().visualTransform,"Original temporary effect linkage missing: "+path);
   foreach(var renderer in presentationRoots.Concat(new[]{source}).Concat(effects.Skip(effectStart)).Distinct().SelectMany(x=>x.GetComponentsInChildren<Renderer>(true)).Distinct()){
    if(worldLootSourceMaterials.ContainsKey(renderer))continue;
    Check(!renderer.GetComponent<Collider>(),"Core loot renderer shares a collider; preserve its layer before adapting visibility");
    worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;
    renderer.sharedMaterials=renderer.sharedMaterials.Select(original=>{if(!original)return null;var copy=new Material(original);copy.shader=Resources.Load<Shader>("StageSurfacePreview");copy.shaderKeywords=new string[0];AndroidMaterialPresentation.Apply(original,copy);worldMaterials.Add(copy);return copy;}).ToArray();renderer.gameObject.layer=30;
   }
  }
  return effects.Distinct().ToArray();
 }
 void ObserveWorldLootSupport(CharacterBody body,bool force=false){
  r.world.nativeLootProviderLoads=worldNativeLootLeaseBaselines.Sum(pair=>(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[pair.Key])-pair.Value);
  foreach(var pair in worldNativeLootLeaseBaselines)if(objectiveSupportSources[pair.Key].name=="ImpactStunGrenade")r.world.stunImpactLoads=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[pair.Key])-pair.Value;
  foreach(var pair in worldNativeLootLeaseBaselines)if(objectiveSupportSources[pair.Key].name=="StickyBomb")r.world.stickyBombLoads=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[pair.Key])-pair.Value;
  if(force||Time.frameCount%10==0){
   foreach(var blast in Resources.FindObjectsOfTypeAll<DelayBlast>().Where(x=>x.gameObject.scene.IsValid()&&x.name=="WilloWispDelay(Clone)"))if(worldNativeLootObjects.Add(blast.gameObject)){worldObjects.Add(blast.gameObject);r.world.wispDelaySpawns++;}
   foreach(var bomb in Resources.FindObjectsOfTypeAll<RoR2.Projectile.ProjectileController>().Where(x=>x.gameObject.scene.IsValid()&&(x.name=="StickyBomb(Clone)"||x.name=="MissileProjectile(Clone)"||x.name=="Sawmerang(Clone)"||x.name=="GravSphere(Clone)"||x.name=="DaggerProjectile(Clone)")))if(worldNativeLootObjects.Add(bomb.gameObject)){worldObjects.Add(bomb.gameObject);if(bomb.name=="StickyBomb(Clone)")r.world.stickyBombSpawns++;if(bomb.name=="DaggerProjectile(Clone)"&&r.dots!=null)r.dots.daggerSpawns++;}
  }
  if(RoR2Content.Buffs.Slow60)r.world.slowedEnemiesPeak=Mathf.Max(r.world.slowedEnemiesPeak,directorActors.Count(x=>x.body&&x.body.healthComponent.alive&&x.body.HasBuff(RoR2Content.Buffs.Slow60)));
  if(worldNativeLootLeaseBaselines.Count>0&&(force||Time.frameCount%30==0))foreach(var obj in Resources.FindObjectsOfTypeAll<GameObject>().Where(x=>x.scene.IsValid()&&(x.name=="HealPack(Clone)"||x.name=="BonusMoneyPack(Clone)")))if(worldNativeLootObjects.Add(obj)){worldObjects.Add(obj);if(obj.name=="HealPack(Clone)")r.world.healthPacks++;else r.world.moneyPacks++;}
  if(worldFeatherEffectIndex>=0){r.world.featherEffectLoads=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[worldFeatherEffectIndex])-worldFeatherReferenceBaseline;Check(r.world.featherEffectLoads==r.world.featherJumps,"Original Feather loads differ from observed bonus jumps");}
  if(worldLootEffectSlots.Count==0||!body)return;var field=typeof(CharacterBody).GetField("bucklerShieldTempEffectInstance",BindingFlags.Instance|BindingFlags.NonPublic);
  var effect=(TemporaryVisualEffect)field.GetValue(body);if(effect&&!worldLootTemporaryEffects.Contains(effect.gameObject))worldLootTemporaryEffects.Add(effect.gameObject);
 }
 void CleanupWorldLootSupport(){
  CleanupWorldProcContent();
  CleanupOfflineSettingsPause();
  CleanupWorldEquipment();
  if(r.world!=null)ObserveWorldLootSupport(worldPlayer,true);
  foreach(var pair in worldNativeLootLeaseBaselines){int extra=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[pair.Key])-pair.Value;Check(extra>=0,"Original native loot provider ownership changed");for(int i=0;i<extra;i++)Addressables.Release(objectiveSupportSources[pair.Key]);}worldNativeLootLeaseBaselines.Clear();worldNativeLootObjects.Clear();if(r.world!=null)r.world.nativeLootProvidersCleaned=true;
  if(worldFeatherJumped!=null){if(worldPlayer)worldPlayer.onJump-=worldFeatherJumped;worldFeatherJumped=null;}
  if(worldFeatherEffectIndex>=0){for(int i=0;i<r.world.featherEffectLoads;i++)Addressables.Release(objectiveSupportSources[worldFeatherEffectIndex]);worldFeatherEffectIndex=-1;r.world.featherEffectCleaned=true;}
  foreach(var effect in worldLootTemporaryEffects)if(effect)Destroy(effect);
  foreach(var pair in worldLootEffectSlots)pair.Key.SetValue(null,pair.Value);worldLootEffectSlots.Clear();
  foreach(var pair in worldLootSourceMaterials)if(pair.Key)pair.Key.sharedMaterials=pair.Value;worldLootSourceMaterials.Clear();
  foreach(var pair in worldLootSourceLayers)if(pair.Key)pair.Key.layer=pair.Value;worldLootSourceLayers.Clear();
 }
 IEnumerator PrepareIntegratedWorld(CharacterBody player,Result cfg){
  worldFeatherInputAt=-1;
  Check(((Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null)).Count==0,"Unowned effect pools before integrated world");ownsIntegratedPools=true;
  r.world=new WorldReport{scope="Persistent original Commando/default skills, recovered golemplains collision/navigation, continuous original one-card director, local HLAPI client/authority, original Money purchases/chest animation/droplet/default pickup/server grants/gold/XP/stats. Authored layout/HUD/input/materials and explicit audio-unavailable pickup presentation. Original Run clock only: stock startup/menu/profile/route/victory remain unavailable; composed original teleporter is observed separately; no NetworkUser, LocalUser or entitlement grant.",feedbackCapability="Authored pickup HUD; original native-audio notification handler unavailable."};
  worldPlayer=player;PrepareUnavailableWorldPresentation(player);r.phase="integrated-world-client";Save();
  var connect=ConnectActiveBodyClient(player);while(connect.MoveNext())yield return connect.Current;
  r.world.authority=player.networkIdentity.hasAuthority&&activeBodyClient.isConnected&&activeBodyOwner.isReady;
  Check(r.world.authority,"Integrated local authority missing");
  // Source catalogs persist for the session, rather than being rebuilt around each interaction.
  var flags=BindingFlags.Static|BindingFlags.NonPublic;
  Check(!ownsPickupCatalog&&PickupCatalog.pickupCount==0,"Unowned integrated pickup catalog");
  foreach(var name in new[]{"entries","itemIndexToPickupIndex","equipmentIndexToPickupIndex","artifactIndexToPickupIndex","miscPickupIndexToPickupIndex","droneIndexToPickupIndex","<pickupCount>k__BackingField"}){var field=typeof(PickupCatalog).GetField(name,flags);Check(field!=null,"Integrated pickup field absent: "+name);priorPickupFields[field]=field.GetValue(null);}
  pickupNameMap=(IDictionary)typeof(PickupCatalog).GetField("nameToPickupIndex",flags).GetValue(null);
  pickupTierMap=(IDictionary)typeof(PickupCatalog).GetField("itemTierToPickupIndex",flags).GetValue(null);
  Check(pickupNameMap.Count==0&&pickupTierMap.Count==0,"Unowned integrated pickup maps");
  priorPickupAvailability=PickupCatalog.availability;ownsPickupCatalog=true;
  Check(MiscPickupCatalog.pickupCount==0&&!RoR2Content.MiscPickups.LunarCoin,"Unowned integrated misc catalog");
  worldLunarCoin=artifactBundle.LoadAsset<LunarCoinDef>(cfg.worldLunarCoinAsset);
  Check(worldLunarCoin&&worldLunarCoin.name=="LunarCoin"&&worldLunarCoin.coinValue==1&&worldLunarCoin.displayPrefab&&worldLunarCoin.dropletDisplayPrefab,"Original lunar coin definition/display missing");
  previousWorldMiscContent=RoR2.ContentManagement.ContentManager._miscPickupDefs;previousWorldMiscCatalog=RewardField(typeof(MiscPickupCatalog),"_miscPickupDefs").GetValue(null);previousWorldMiscAvailability=MiscPickupCatalog.availability;ownsWorldMisc=true;
  RoR2.ContentManagement.ContentManager._miscPickupDefs=new MiscPickupDef[]{worldLunarCoin};RoR2Content.MiscPickups.LunarCoin=worldLunarCoin;StaticCall(typeof(MiscPickupCatalog),"Init");
  var lunarPickup=worldLunarCoin.CreatePickupDef();
  var moonEquipmentPickups=cfg.moonMission?new[]{RoR2Content.Equipment.AffixLunar.CreatePickupDef()}:new PickupDef[0];
  PickupCatalog.SetEntries(ItemCatalog.allItemDefs.Select(x=>x.CreatePickupDef()).Concat(moonEquipmentPickups).Concat(EligibleWorldEquipment().Select(x=>x.CreatePickupDef())).Concat(new[]{lunarPickup}).ToArray());
  if(cfg.moonMission)Check(PickupCatalog.GetPickupDef(PickupCatalog.FindPickupIndex(RoR2Content.Equipment.AffixLunar.equipmentIndex))==moonEquipmentPickups[0],"Original Lunar equipment pickup metadata missing");
  r.world.lunarDefinition=MiscPickupCatalog.GetMiscDef(worldLunarCoin.miscPickupIndex)==worldLunarCoin&&PickupCatalog.FindPickupIndex(worldLunarCoin.miscPickupIndex)==lunarPickup.pickupIndex&&lunarPickup.attemptGrant.Method.DeclaringType==typeof(LunarCoinDef);
  Check(r.world.lunarDefinition&&!Util.LookUpBodyNetworkUser(player),"Original lunar definition or unavailable currency contract changed");r.world.lunarCurrencyAvailable=false;
  Check(Run.instance.availableTier1DropList.Count==0&&Run.instance.availableTier2DropList.Count==0&&Run.instance.availableTier3DropList.Count==0,"Unowned integrated loot lists");
  ownsWorldLists=true;
  worldLootDefinitions=WorldLoot(cfg);
  r.world.itemStacks=worldLootDefinitions.Select(x=>new WorldItemObservation{item=x.name,tier=x.tier.ToString()}).ToArray();
  foreach(var item in worldLootDefinitions)Check(!Run.instance.IsItemExpansionLocked(item.itemIndex)&&!item.requiredExpansion&&!item.unlockableDef&&!item.hidden&&item.DoesNotContainTag(ItemTag.IgnoreForDropList)&&item.DoesNotContainTag(ItemTag.WorldUnique),"Integrated base item unavailable: "+item.name);
  if(cfg.worldAdditionalLootItems!=null&&cfg.worldAdditionalLootItems.Length>0){
   previousWorldAvailableItems=Run.instance.availableItems;previousWorldAvailableEquipment=Run.instance.availableEquipment;
   worldAvailableItems=ItemMask.Rent();worldAvailableEquipment=EquipmentMask.Rent();Run.instance.availableItems=worldAvailableItems;Run.instance.availableEquipment=worldAvailableEquipment;
   foreach(var item in worldLootDefinitions)worldAvailableItems.Add(item.itemIndex);foreach(var def in EligibleWorldEquipment())worldAvailableEquipment.Add(def.equipmentIndex);
   if(cfg.teleporterLoop)worldAvailableItems.Add(RoR2Content.Items.Knurl.itemIndex);
   Run.instance.BuildDropTable();
  }else{
   foreach(var item in worldLootDefinitions)if(item.tier==ItemTier.Tier1)Run.instance.availableTier1DropList.Add(PickupCatalog.FindPickupIndex(item.itemIndex));else if(item.tier==ItemTier.Tier2)Run.instance.availableTier2DropList.Add(PickupCatalog.FindPickupIndex(item.itemIndex));
  }
  r.world.lootTier1=Run.instance.availableTier1DropList.Count;r.world.lootTier2=Run.instance.availableTier2DropList.Count;r.world.lootTier3=Run.instance.availableTier3DropList.Count;
  Check(r.world.lootTier1+r.world.lootTier2+r.world.lootTier3==worldLootDefinitions.Length,"Original composed drop lists differ from eligible item domain");
  moneyCatalogField=typeof(CostTypeCatalog).GetField("costTypeDefs",flags);priorMoneyCatalog=moneyCatalogField.GetValue(null);
  Check(priorMoneyCatalog==null&&!ownsMoneyCatalog,"Unowned integrated cost catalog");ownsMoneyCatalog=true;StaticCall(typeof(CostTypeCatalog),"Init");
  var generic=PrepareOriginalDefaultPickup(cfg);while(generic.MoveNext())yield return generic.Current;
  r.phase="integrated-world-loot";Save();
  worldDropletField=RewardField(typeof(PickupDropletController),"pickupDropletPrefab");priorWorldDroplet=worldDropletField.GetValue(null);
  Check(priorWorldDroplet==null,"Unowned integrated droplet source");
  var bundle=new ResourceLocationBase("pickup-droplet-lab",System.IO.Path.Combine(Application.persistentDataPath,"payload","pickup-droplet-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));
  bundle.Data=new AssetBundleRequestOptions{BundleName="pickup-droplet-lab"};
  worldDropletLocator=new ResourceLocationMap("integrated-world-droplet");
  worldDropletLocator.Add(cfg.pickupDropletKey,new ResourceLocationBase(cfg.pickupDropletKey,cfg.pickupDropletAsset,typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));Addressables.AddResourceLocator(worldDropletLocator);
  StaticCall(typeof(PickupDropletController),"Init");float deadline=Time.realtimeSinceStartup+8;
  while(worldDropletField.GetValue(null)==null&&Time.realtimeSinceStartup<deadline)yield return null;
  worldDropletSource=(GameObject)worldDropletField.GetValue(null);ownsWorldDroplet=worldDropletSource;
  Check(worldDropletSource&&worldDropletSource.name=="PickupDroplet"&&LegacyResourcesAPI.ActiveCount==0,"Integrated original droplet Init failed");
  worldChestTable=artifactBundle.LoadAsset<BasicPickupDropTable>(cfg.chestDropTableAsset);
  Check(worldChestTable&&worldChestTable.name=="dtChest1"&&worldChestTable.canDropBeReplaced,"Integrated source drop table identity/policy differs");r.world.tableLoadedCount=worldChestTable.GetPickupCount();worldChestTable.RegenerateDropTable(Run.instance);
  r.world.lootDomain=worldChestTable.GetPickupCount();Check(r.world.lootDomain==worldLootDefinitions.Length,"Integrated source chest loot domain missing");
  PrepareWorldMessages();
  worldCoinLease=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/Effects/CoinEmitter");ownsWorldCoinLease=true;yield return worldCoinLease;
  Check(worldCoinLease.Result==rewardPrefabs[0],"Integrated coin source witness differs");worldCoinBaseline=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(worldCoinLease);
  worldPause=new GameObject("Offline gameplay pause context");worldPause.SetActive(false);worldPause.AddComponent<NetworkIdentity>();worldPause.AddComponent<PauseStopController>();worldPause.SetActive(true);
  yield return null;Check(PauseStopController.instance&&!PauseStopController.instance.isPaused,"Integrated unpaused context missing");
  worldDriver=player.GetComponent<InteractionDriver>();Check(worldDriver&&(!worldDriver||!worldDriver.enabled)&&!worldDriver.interactableOverride,"Unowned integrated interaction driver");
  if(!player.equipmentSlot.characterBody)Call(player.equipmentSlot,"Start");Call(player.equipmentSlot,"UpdateInventory");
  Check(player.equipmentSlot.equipmentIndex==EquipmentIndex.None&&!player.equipmentSlot.enabled,"Integrated equipment must start empty/ungranted");PrepareWorldEquipment(player,cfg);
  if(DriverField(worldDriver,"networkIdentity")==null)Call(worldDriver,"Awake");
  worldStaging=new GameObject("Inactive offline content staging");worldStaging.SetActive(false);
  var chestSource=artifactBundle.LoadAsset<GameObject>(cfg.chestAsset);OwnChestAnimationSources(chestSource.GetComponent<ModelLocator>().modelTransform);
  // Measured near-spawn layout; placement is an Android adapter, not original SceneDirector placement.
  var origin=player.characterMotor.Motor.TransientPosition;
  var barrelOffsets=new[]{new Vector3(2,0,0),new Vector3(-2,0,0),new Vector3(0,0,3),new Vector3(4,0,3),new Vector3(-4,0,3),new Vector3(0,0,-3)};
  foreach(var offset in barrelOffsets){var obj=CreateWorldInteractable(artifactBundle.LoadAsset<GameObject>(cfg.barrelAsset),origin+offset,false);if(obj)worldBarrels.Add(obj.GetComponent<BarrelInteraction>());}
  foreach(var offset in new[]{new Vector3(5,0,0),new Vector3(-5,0,0),new Vector3(0,0,6),new Vector3(6,0,6)}){var obj=CreateWorldInteractable(chestSource,origin+offset,true);if(obj)worldChests.Add(obj.GetComponent<ChestBehavior>());}
  AddEquipmentBarrel(cfg,origin);Check(worldBarrels.Count>=3&&worldChests.Count>=2,"Integrated layout has insufficient walkable source interactables");
  r.world.barrels=worldBarrels.Count;r.world.chests=worldChests.Count;r.world.lootReady=true;
  worldInteraction=(actor,component,obj)=>{if(actor!=worldDriver.interactor)return;if(worldObjects.Contains(obj))r.world.target=obj.name;};GlobalEventManager.OnInteractionsGlobal+=worldInteraction;
  worldDriver.enabled=true;yield return null;Call(activeBodyClient,"Update");
  r.world.interactionReady=worldDriver.enabled&&ReferenceEquals(DriverField(worldDriver,"inputBank"),player.inputBank);
  r.world.start=origin;r.world.ready=r.world.authority&&r.world.lootReady&&r.world.interactionReady&&rewardDirector.enabled;
  if(cfg.teleporterLoop){var objective=PrepareTeleporterWorld(cfg);while(objective.MoveNext())yield return objective.Current;}
  PrepareWorldCommerce(cfg,origin);
  PrepareRecoveredHud();Check(r.world.ready,"Integrated session setup incomplete");r.phase="integrated-world-playing";Save();
 }

 void PrepareUnavailableWorldPresentation(CharacterBody player){
  // Optional presentation requires stock application/native audio/item-display contexts.
  // Remove only these measured original listeners; all original XP/level/inventory events remain.
  var flags=BindingFlags.Static|BindingFlags.NonPublic;var type=typeof(LevelUpEffectManager);
  unavailableTeamLevelSound=(Action<TeamIndex>)Delegate.CreateDelegate(typeof(Action<TeamIndex>),type.GetMethod("OnTeamLevelUp",flags));
  unavailableAmbientSound=(Action<Run>)Delegate.CreateDelegate(typeof(Action<Run>),type.GetMethod("OnRunAmbientLevelUp",flags));
  unavailableLevelEffect=(Action<CharacterBody>)Delegate.CreateDelegate(typeof(Action<CharacterBody>),type.GetMethod("OnCharacterLevelUp",flags));
  unavailableItemHighlight=(Action<ItemIndex>)Delegate.CreateDelegate(typeof(Action<ItemIndex>),player.master,typeof(CharacterMaster).GetMethod("OnItemAddedClient",BindingFlags.Instance|BindingFlags.NonPublic));
  var teamListeners=(Delegate)RewardField(typeof(GlobalEventManager),"onTeamLevelUp").GetValue(null);var ambientListeners=(Delegate)RewardField(typeof(Run),"onRunAmbientLevelUp").GetValue(null);var effectListeners=(Delegate)RewardField(typeof(GlobalEventManager),"onCharacterLevelUp").GetValue(null);var highlightListeners=(Delegate)typeof(Inventory).GetField("onItemAddedClient",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic).GetValue(player.inventory);
  Check(teamListeners!=null&&ambientListeners!=null&&effectListeners!=null&&highlightListeners!=null&&teamListeners.GetInvocationList().Count(x=>x.Equals(unavailableTeamLevelSound))==1&&ambientListeners.GetInvocationList().Count(x=>x.Equals(unavailableAmbientSound))==1&&effectListeners.GetInvocationList().Count(x=>x.Equals(unavailableLevelEffect))==1&&highlightListeners.GetInvocationList().Count(x=>x.Equals(unavailableItemHighlight))==1,"Original optional presentation listener ownership changed");
  GlobalEventManager.onTeamLevelUp-=unavailableTeamLevelSound;Run.onRunAmbientLevelUp-=unavailableAmbientSound;GlobalEventManager.onCharacterLevelUp-=unavailableLevelEffect;
  player.inventory.onItemAddedClient-=unavailableItemHighlight;ownsWorldPresentation=true;
  r.world.feedbackCapability+=" Original level-up sound/effect and item-display highlight unavailable; original levels/stats/grants retained.";
 }
 void PrepareWorldMessages(){
  Check(!activeBodyClient.handlers.ContainsKey(52)&&!activeBodyClient.handlers.ContainsKey(55)&&!activeBodyClient.handlers.ContainsKey(57)&&!activeBodyClient.handlers.ContainsKey(68)&&!NetworkServer.handlers.ContainsKey(68),"Unowned integrated presentation/teleport handlers");
  worldVfxOption=(RoR2.ConVar.IntConVar)RewardField(typeof(VFXBudget),"mediumPriorityCostThreshold").GetValue(null);priorWorldVfx=worldVfxOption.GetString();worldVfxOption.AttemptSetString(worldVfxOption.defaultValue);
  priorWorldXp=SettingsConVars.cvExpAndMoneyEffects.GetString();SettingsConVars.cvExpAndMoneyEffects.AttemptSetString("0");
  var effects=(NetworkMessageDelegate)Delegate.CreateDelegate(typeof(NetworkMessageDelegate),typeof(EffectManager).GetMethod("HandleEffectClient",BindingFlags.Static|BindingFlags.NonPublic));
  var xp=(NetworkMessageDelegate)Delegate.CreateDelegate(typeof(NetworkMessageDelegate),typeof(ExperienceManager).GetMethod("HandleCreateExpEffect",BindingFlags.Static|BindingFlags.NonPublic));
  var teleport=(NetworkMessageDelegate)Delegate.CreateDelegate(typeof(NetworkMessageDelegate),typeof(TeleportHelper).GetMethod("HandleTeleport",BindingFlags.Static|BindingFlags.NonPublic));ownsWorldTeleportHandler=true;activeBodyClient.RegisterHandler(68,teleport);NetworkServer.RegisterHandler(68,teleport);
  activeBodyClient.RegisterHandler(52,msg=>{r.world.coinMessages++;effects(msg);});
  activeBodyClient.RegisterHandler(55,msg=>{r.world.xpMessages++;xp(msg);});
  // Decode with the original MessageBase. Do not call the original native-audio UI handler
  // or fabricate its completion/profile discovery. Server grant, quantity and identity stay original.
  var type=typeof(GenericPickupController).GetNestedType("PickupMessage",BindingFlags.NonPublic);
  Check(type!=null&&typeof(MessageBase).IsAssignableFrom(type),"Original pickup message contract missing");
  activeBodyClient.RegisterHandler(57,msg=>{
   var message=(MessageBase)Activator.CreateInstance(type,true);msg.ReadMessage(message);
   var master=(GameObject)type.GetField("masterGameObject").GetValue(message);var pickup=(UniquePickup)type.GetField("pickupState").GetValue(message);var quantity=(uint)type.GetField("pickupQuantity").GetValue(message);
   var characterMaster=master?master.GetComponent<CharacterMaster>():null;var definition=PickupCatalog.GetPickupDef(pickup.pickupIndex);var item=ItemCatalog.GetItemDef(definition!=null?definition.itemIndex:ItemIndex.None);
   var observation=new WorldPickupMessageObservation{at=r.world.seconds,resolvedMaster=characterMaster,playerMaster=characterMaster&&worldPlayer&&characterMaster==worldPlayer.master,knownPickup=definition!=null,masterId=characterMaster?characterMaster.netId.Value:0,quantity=quantity,pickupIndex=pickup.pickupIndex.value,item=item?item.name:definition!=null?definition.internalName:"unavailable"};
   if(r.world.pickupMessageObservations.Count==64)r.world.pickupMessageObservations.RemoveAt(0);r.world.pickupMessageObservations.Add(observation);
   // Original notification handling tolerates missing masters and zero effective stacks.
   // Record those packets without claiming a connected player grant.
   if(!characterMaster)r.world.unresolvedPickupMessages++;else if(!observation.playerMaster)r.world.otherPickupMessages++;else if(quantity==0)r.world.zeroCountPickupMessages++;
   if(observation.playerMaster&&definition!=null&&quantity>0){r.world.pickupMessages++;r.world.lastPickup=observation.item+" x"+quantity;if(recoveredHud)recoveredHud.QueuePickup(characterMaster,pickup);}Save();
  });
  ObserveWorldHandlers(false);ObserveWorldHandlers(true);
 }
 void ObserveWorldHandlers(bool server){
  var handlers=server?NetworkServer.handlers:activeBodyClient.handlers;var originals=server?worldServerHandlers:worldClientHandlers;var observers=server?worldServerObservers:worldClientObservers;
  Check(originals.Count==0&&observers.Count==0,"Unowned integrated handler observation");
  foreach(var pair in handlers.ToArray()){
   short id=pair.Key;var original=pair.Value;NetworkMessageDelegate observer=msg=>{
    try{original(msg);}catch(Exception error){
     var failure=new WorldMessageFailure{at=r.world.seconds,id=id,side=server?"server":"client",handler=original.Method.DeclaringType.FullName+"."+original.Method.Name,error=error.GetBaseException().ToString()};r.world.messageFailureCount++;if(r.world.messageFailures.Count<16)r.world.messageFailures.Add(failure);Save();Debug.LogError("Integrated message failure "+failure.side+"/"+id+": "+failure.error);throw;
    }
   };
   originals.Add(id,original);observers.Add(id,observer);if(server)NetworkServer.RegisterHandler(id,observer);else activeBodyClient.RegisterHandler(id,observer);
  }
 }
 void RestoreWorldHandlers(bool server){
  var originals=server?worldServerHandlers:worldClientHandlers;var observers=server?worldServerObservers:worldClientObservers;
  if((server&&NetworkServer.active)||(!server&&activeBodyClient!=null)){var handlers=server?NetworkServer.handlers:activeBodyClient.handlers;foreach(var pair in originals){NetworkMessageDelegate current;if(handlers.TryGetValue(pair.Key,out current)&&current==observers[pair.Key]){if(server)NetworkServer.RegisterHandler(pair.Key,pair.Value);else activeBodyClient.RegisterHandler(pair.Key,pair.Value);}}}
  originals.Clear();observers.Clear();
 }

 GameObject CreateWorldInteractable(GameObject source,Vector3 candidate,bool chest){
  RaycastHit hit;if(!Physics.Raycast(candidate+Vector3.up*20,Vector3.down,out hit,50,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||hit.normal.y<.9f||Mathf.Abs(hit.point.y-worldPlayer.characterMotor.Motor.TransientPosition.y)>2)return null;
  Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Integrated source interactable reference missing");
  var obj=Instantiate(source,worldStaging.transform);obj.name=source.name;worldObjects.Add(obj);
  var allowed=new[]{typeof(NetworkIdentity),typeof(NetworkStateMachine),typeof(EntityStateMachine),typeof(BarrelInteraction),typeof(ChestBehavior),typeof(PurchaseInteraction),typeof(DelusionChestController),typeof(ModelLocator),typeof(EntityLocator),typeof(ChildLocator),typeof(PingInfoProvider),typeof(AnimationEvents)};
  foreach(var behaviour in obj.GetComponentsInChildren<MonoBehaviour>(true))behaviour.enabled=allowed.Contains(behaviour.GetType());
  var sound=obj.GetComponent<SfxLocator>();if(sound)DestroyImmediate(sound);
  foreach(var animator in obj.GetComponentsInChildren<Animator>(true)){animator.enabled=chest;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;}
  var model=obj.GetComponent<ModelLocator>().modelTransform;worldModels.Add(model);PresentWorldModel(model,true);
  foreach(var collider in obj.GetComponentsInChildren<Collider>(true))collider.enabled=true;
  obj.transform.position=hit.point+Vector3.up*.4f;obj.transform.SetParent(null,true);obj.SetActive(true);NetworkServer.Spawn(obj);if(!chest)worldBarrelConsumers++;return obj;
 }
 void PresentWorldModel(Transform model,bool sourceView,bool optionalObjectiveSlots=false){
  var shader=Resources.Load<Shader>("StageSurfacePreview");Check(shader&&shader.isSupported,"Integrated preview material unavailable");
  foreach(var renderer in model.GetComponentsInChildren<Renderer>(true)){
   if(!worldPresented.Add(renderer.GetInstanceID()))continue;
   renderer.sharedMaterials=renderer.sharedMaterials.Select(original=>{
    if(!original&&optionalObjectiveSlots&&renderer is ParticleSystemRenderer){r.objective.unusedParticleMaterialSlots++;return null;}
    Check(original||optionalObjectiveSlots,"Integrated source material absent");
    var material=original?new Material(original):new Material(shader);material.shader=shader;
    if(original)AndroidMaterialPresentation.Apply(original,material);
    if(!original){r.objective.previewMaterialSlots++;material.SetColor("_Color",new Color(.3f,.65f,.9f,1));}
    worldMaterials.Add(material);return material;
   }).ToArray();
   if(sourceView&&renderer is SkinnedMeshRenderer){var skin=(SkinnedMeshRenderer)renderer;var view=new GameObject("Offline source renderer view");view.layer=30;view.transform.SetParent(renderer.transform,false);var copy=view.AddComponent<SkinnedMeshRenderer>();copy.sharedMesh=skin.sharedMesh;copy.sharedMaterials=skin.sharedMaterials;copy.bones=skin.bones;copy.rootBone=skin.rootBone;copy.localBounds=skin.localBounds;copy.updateWhenOffscreen=true;worldPresented.Add(copy.GetInstanceID());}
   else if(!sourceView&&!(optionalObjectiveSlots&&renderer.GetComponent<Collider>()))renderer.gameObject.layer=30;
  }
 }
 void ObserveIntegratedWorld(CharacterBody player,float elapsed){
  Call(activeBodyClient,"Update");Check(activeBodyClient.isConnected&&player.networkIdentity.hasAuthority&&player.networkIdentity.clientAuthorityOwner==activeBodyOwner&&LocalUserManager.readOnlyLocalUsersList.Count==0&&!player.master.playerCharacterMasterController.networkUser,"Integrated authority/unavailable-user scope changed");
  ObserveTeleporterWorld();ObserveMoonMission();var world=r.world;world.frames++;world.seconds=elapsed;world.position=player.characterMotor.Motor.TransientPosition;world.distance=Vector3.Distance(world.start,world.position);world.health=player.healthComponent.health;world.maxHealth=player.maxHealth;world.level=player.level;world.attackSpeed=player.attackSpeed;world.money=player.master.money;world.experience=TeamManager.instance.GetTeamExperience(TeamIndex.Player);world.kills=player.killCountServer;world.difficulty=Run.instance.difficultyCoefficient;
  var motor=player.characterMotor;var grounding=motor.Motor.GroundingStatus;world.motorGrounded=motor.isGrounded;world.motorStable=grounding.IsStableOnGround;world.motorGroundPoint=grounding.GroundPoint;world.motorGroundCollider=grounding.GroundCollider?StageObjectPath(grounding.GroundCollider.transform):"";world.motorVelocity=motor.velocity;world.motorJumpCount=motor.jumpCount;world.motorMaxJumpCount=player.maxJumpCount;
  world.jumpDown=player.inputBank.jump.down;world.jumpPressed=player.inputBank.jump.justPressed;world.jumpClaimed=player.inputBank.jump.hasPressBeenClaimed;var bodyMachine=player.GetComponents<EntityStateMachine>().FirstOrDefault(x=>x.customName=="Body");world.movementState=bodyMachine&&bodyMachine.state!=null?bodyMachine.state.GetType().FullName:"unavailable";
  world.syringe=player.inventory.GetItemCountPermanent(RoR2Content.Items.Syringe);world.lightning=player.inventory.GetItemCountPermanent(RoR2Content.Items.ChainLightning);world.glasses=player.inventory.GetItemCountPermanent(RoR2Content.Items.CritGlasses);world.slug=player.inventory.GetItemCountPermanent(RoR2Content.Items.HealWhileSafe);world.crit=player.crit;world.regen=player.regen;world.moveSpeed=player.moveSpeed;
  world.shield=player.healthComponent.shield;world.maxShield=player.maxShield;world.armor=player.armor;for(int i=0;i<worldLootDefinitions.Length;i++)world.itemStacks[i].count=player.inventory.GetItemCountPermanent(worldLootDefinitions[i]);ObserveWorldLootSupport(player);ObserveWorldEquipment();
  if(world.lootDomain>4){world.drink=player.inventory.GetItemCountPermanent(RoR2Content.Items.SprintBonus);world.steak=player.inventory.GetItemCountPermanent(RoR2Content.Items.FlatHealth);}
  world.openedBarrels=worldBarrels.Count(x=>x&&x.Networkopened);world.openedChests=worldChests.Count(x=>x&&x.NetworkisChestOpened);world.liveEnemies=directorActors.Count(x=>x.body&&x.body.healthComponent.alive);
  var pickups=EjectionPickups().ToArray();world.pickups=pickups.Length;world.droplets=EjectionDroplets().Count();
  var interactor=player.GetComponent<Interactor>();world.interactionDistance=interactor.maxInteractionDistance;
  world.pickupObservations=pickups.Select(x=>{var collider=x.GetComponentsInChildren<Collider>(true).FirstOrDefault(c=>c.enabled&&(LayerIndex.CommonMasks.interactable.value&(1<<c.gameObject.layer))!=0);var aim=collider?collider.bounds.center:x.transform.position;var def=PickupCatalog.GetPickupDef(x.pickup.pickupIndex);return new WorldPickupObservation{item=def==null?"invalid":def.internalName,interactability=x.GetInteractability(interactor).ToString(),position=x.transform.position,aimTarget=aim,aimDistance=Vector3.Distance(player.inputBank.aimOrigin,aim),selected=worldDriver.currentInteractable==x.gameObject,collider=collider,interactableLayer=collider};}).ToArray();
  foreach(var pickup in pickups){if(!pickup.pickupDisplay)continue;var model=(GameObject)typeof(PickupDisplay).GetField("modelObject",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(pickup.pickupDisplay);if(model)PresentWorldModel(model.transform,false);}
  world.secondary=r.combat.secondaryEntries;world.roll=r.combat.utilityEntries;world.barrage=r.combat.specialEntries;
  world.target=worldDriver.currentInteractable?worldDriver.currentInteractable.name:"";ObserveWorldCommerce();ObserveRecoveredHud();
 }
 void IntegratedWorldStimulus(CharacterBody player,NovaInputBridge bridge,float elapsed){
  // Explicit automation for integrated validation only; direct app launches use physical controls.
  bridge.touchEquipment|=worldEquipmentTouch;worldEquipmentTouch=false;bridge.diagnosticInput=!worldManualTakeover;r.world.manualTakeover=worldManualTakeover;
  if(worldManualTakeover){r.world.diagnosticInput=false;return;}
  r.world.diagnosticInput=true;WorldEquipmentStimulus(bridge,elapsed);bridge.diagnosticSprint=false;GameObject target=null;bridge.diagnosticInteract=false;bridge.diagnosticPrimary=false;bridge.diagnosticSecondary=false;bridge.diagnosticUtility=false;bridge.diagnosticSpecial=false;bridge.DiagnosticJump(false);
  if(r.moon!=null&&r.moon.loaded&&MoonWorldStimulus(player,bridge,elapsed))return;
  if(worldObjective==0){var barrel=worldBarrels.FirstOrDefault(x=>x&&!x.Networkopened);if(barrel)target=barrel.gameObject;else worldObjective=1;}
  if(worldObjective==3&&elapsed-stageEnteredAt<105&&NextAutomaticWorldChest(player)&&player.master.money>=NextAutomaticWorldChest(player).GetComponent<PurchaseInteraction>().cost)worldObjective=1;
  if(worldObjective==1){var chest=NextAutomaticWorldChest(player);if(r.world.openedChests>r.world.pickupMessages-stagePickupBaseline)worldObjective=2;else if(chest&&player.master.money>=chest.GetComponent<PurchaseInteraction>().cost)target=chest.gameObject;else worldObjective=3;}
  if(worldObjective>0&&GrantableWorldPickups(player,true).Any())worldObjective=2;
  if(worldObjective==2){var pickup=GrantableWorldPickups(player,true).OrderBy(x=>Vector3.Distance(x.transform.position,player.corePosition)).FirstOrDefault();if(pickup)target=pickup.gameObject;else if(r.world.pickupMessages-stagePickupBaseline>=r.world.openedChests)worldObjective=3;}
  if(worldObjective==3&&elapsed-stageEnteredAt<65){var commerce=AffordableWorldCommerce();if(commerce)target=commerce;}
  r.world.objective=worldObjective==0?"Collect original barrel rewards":worldObjective==1?"Purchase original chest":worldObjective==2?"Collect naturally ejected item":"Survive original director combat";
  if(r.teleporterLoop&&elapsed-stageEnteredAt>65){if(ObjectiveWorldStimulus(player,bridge,elapsed))return;}
  bridge.movement=Vector2.zero;
  if(target){
   if(r.teleporterLoop&&DefendWorldApproach(player,bridge,target,elapsed))return;
   NavigateWorldInput(player,bridge,target.transform.position,target.GetComponent<GenericPickupController>() ? .6f : 1.6f,target.name,elapsed);
   var collider=target.GetComponentsInChildren<Collider>(true).FirstOrDefault(x=>x.enabled&&!x.isTrigger);var aim=(collider?collider.bounds.center:target.transform.position)-player.inputBank.aimOrigin;bridge.aim=new Vector2(aim.x,aim.z).normalized;
   // The original input producer consumes a 3D ray; use the measured target elevation as well.
   bridge.diagnosticAim=aim.normalized;
   if(worldDriver.currentInteractable==target&&elapsed-worldLastPress>.5f){bridge.diagnosticInteract=true;worldLastPress=elapsed;}
  }else{
   if(r.teleporterLoop){ObjectiveCombatInput(player,bridge,elapsed,Vector2.zero,false);return;}
   bridge.diagnosticAim=Vector3.zero;var enemy=directorActors.Where(x=>x.body&&x.body.healthComponent.alive).OrderBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();
   if(enemy!=null){var aim=enemy.body.corePosition-player.inputBank.aimOrigin;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticAim=aim.normalized;bridge.diagnosticPrimary=true;bridge.diagnosticSecondary=elapsed%12<.2f;bridge.diagnosticSpecial=elapsed%20<.2f;bridge.diagnosticUtility=elapsed%16<.2f;}
   bridge.DiagnosticJump(elapsed%18<.2f);
  }
 }
 float worldFeatherInputAt=-1;
 void EarnedFeatherInput(CharacterBody player,NovaInputBridge bridge,float elapsed){
  // Whole-game diagnostic input only. Do not grant inventory, change jump limits,
  // move the body, or claim a controller/normal jump-height acceptance.
  if(r.world.featherJumps>0){if(r.world.featherInputAttempted)r.world.featherInputOutcome="Original bonus jump and effect observed";return;}
  if(!bridge.diagnosticInput||worldManualTakeover||r.moon!=null&&r.moon.loaded)return;
  var motor=player.characterMotor;
  if(worldFeatherInputAt<0){
   if(r.world.featherInputAttempted||!r.objective.charging||r.objective.charge>.5f||!motor.isGrounded||player.inventory.GetItemCount(RoR2Content.Items.Feather)<=0||player.maxJumpCount<=player.baseJumpCount)return;
   if(Vector3.Distance(motor.Motor.TransientPosition,r.objective.position)>r.objective.radius*.5f)return;
   worldFeatherInputAt=elapsed;r.world.featherInputAttempted=true;r.world.featherInputOutcome="Original grounded press, release, then airborne second press";
  }
  float age=elapsed-worldFeatherInputAt;
  if(age>1.5f){r.world.featherInputOutcome="No bonus jump observed during input sequence";worldFeatherInputAt=-1;return;}
  bridge.movement=Vector2.zero;bridge.diagnosticSprint=false;
  bool first=age<.1f,second=age>.35f&&age<.55f&&!motor.isGrounded&&motor.jumpCount==1;
  bridge.DiagnosticJump(first||second);
 }
 void NavigateWorldInput(CharacterBody player,NovaInputBridge bridge,Vector3 destination,float stopDistance,string target,float elapsed){
  // Match the exact shipped BaseAI navigation reference for this pinned input.
  var position=player.temporaryPathfindingFootpositionDoNotUseWillBePatchedOut;var delta=destination-position;var planar=new Vector2(delta.x,delta.z);r.world.navigationReference=position;
  var graph=SceneInfo.instance?SceneInfo.instance.groundNodes:null;var waypoint=destination;
  bool moon=r.moon!=null&&r.moon.loaded;
  // Players may sprint while travelling. Let original input/stat callbacks supply
  // the actual speed used by the next source path request, including earned items.
  if(moon||elapsed<worldTerrainRecoveryUntil)bridge.diagnosticSprint=planar.magnitude>8;
  r.world.navigationSprint=bridge.diagnosticSprint;r.world.navigationTerrainFallback=false;r.world.navigationTerrainNoCandidate=false;
  r.world.navigationTarget=target;r.world.navigationDestination=destination;r.world.navigationJump=false;
  // Replay follows the recovered graph through the normal input boundary. Original
  // motor limits, graph gates, physics, interaction range and item positions remain authoritative.
  RaycastHit obstacle;bool needsRoute=Mathf.Abs(delta.y)>2||planar.magnitude>15||Physics.Linecast(position+Vector3.up,destination+Vector3.up,out obstacle,LayerIndex.world.mask,QueryTriggerInteraction.Ignore);
  if(graph&&needsRoute){
   if(worldPathFollower.nodeGraph!=graph||Vector3.Distance(destination,worldPathTarget)>2||elapsed-worldPathRequested>8){
    r.world.navigationHull=player.hullClassification.ToString();r.world.navigationJumpHeight=player.maxJumpHeight.ToString("R",System.Globalization.CultureInfo.InvariantCulture);r.world.navigationMaxSpeed=player.moveSpeed;r.world.navigationMaxSlope=player.characterMotor.Motor.MaxStableSlopeAngle;r.world.navigationGravityY=Physics.gravity.y;r.world.navigationGraphNodes=graph.GetNodeCount();
    r.world.navigationNearestNode=graph.FindClosestNode(position,player.hullClassification).nodeIndex;var startNode=graph.FindClosestNodeWithRaycast(position,player.hullClassification,100,2);r.world.navigationStartNode=startNode.nodeIndex;Vector3 startPosition;r.world.navigationStartPosition=graph.GetNodePosition(startNode,out startPosition)?startPosition:Vector3.zero;
    r.world.navigationApproachBoundsRejected=r.world.navigationApproachTooShort=r.world.navigationApproachUnreachable=0;
    using(var path=new RoR2.Path(graph)){
     var task=graph.ComputePath(new RoR2.Navigation.NodeGraph.PathRequest{path=path,startPos=position,endPos=destination,hullClassification=player.hullClassification,maxSlope=player.characterMotor.Motor.MaxStableSlopeAngle,maxJumpHeight=player.maxJumpHeight,maxSpeed=player.moveSpeed});
     Check(task.status==RoR2.Navigation.PathTask.TaskStatus.Complete,"Original stage path did not complete");
     r.world.navigationReachable=task.wasReachable;r.world.navigationPartial=false;r.world.navigationPartialCandidates=0;r.world.navigationPartialNode=-1;r.world.navigationPartialSeconds=0;
     // Moon's monster graph need not connect to the player's battery destination.
     // Ask the original solver for a reachable approach before abandoning its route.
     if(moon&&!task.wasReachable)r.world.navigationPartial=FindSourceWorldApproach(player,graph,path,position,destination);
     r.world.navigationWaypoints=path.waypointsCount;worldPathFollower.SetPath(path);
     var observed=new List<NavigationPathPoint>();for(int i=0;i<path.waypointsCount;i++){Vector3 node;Check(graph.GetNodePosition(path[i].nodeIndex,out node),"Original path node position unavailable");observed.Add(new NavigationPathPoint{position=node,minimumJumpHeight=path[i].minJumpHeight});}r.world.navigationPath=observed.ToArray();
    }
    worldPathTarget=destination;worldPathRequested=elapsed;
   }
   worldPathFollower.UpdatePosition(position);var next=worldPathFollower.GetNextPosition();if(next.HasValue)waypoint=next.Value;
   r.world.navigationJump=worldPathFollower.nextWaypointNeedsJump;
  }else{worldPathFollower.Reset();r.world.navigationReachable=true;r.world.navigationPartial=false;r.world.navigationWaypoints=0;r.world.navigationPath=new NavigationPathPoint[0];}
  bool stalled=worldNavigationHasProgress&&elapsed-worldNavigationProgressAt>3&&Vector3.Distance(waypoint,worldNavigationProgressWaypoint)<.5f&&Vector3.Distance(destination,worldNavigationProgressDestination)<2;
  bool sourceApproach=r.world.navigationPartial&&!worldPathFollower.isFinished;
  if(needsRoute&&((graph&&!r.world.navigationReachable&&!sourceApproach)||stalled))worldTerrainRecoveryUntil=elapsed+4;
  if(needsRoute&&elapsed<worldTerrainRecoveryUntil){
   // The source graph can be disconnected or reach a waypoint the current
   // approach cannot traverse. Retain its result; steer normal input over ground.
   // Do not open gates, edit links, invent extra jumps or move the body directly.
   waypoint=TerrainTravelWaypoint(player,position,waypoint,elapsed);
   r.world.navigationTerrainFallback=true;r.world.navigationTerrainFrames++;r.world.navigationTerrainTarget=waypoint;
  }
  r.world.navigationWaypoint=waypoint;var direction=waypoint-position;var movement=new Vector2(direction.x,direction.z);
  if(worldNavigationBody!=player){worldLocalNavigator.SetBody(player);worldNavigationBody=player;worldNavigationUpdatedAt=elapsed;worldNavigationHasProgress=false;worldNavigationHasObjectiveProgress=false;}
  // Original graph traversal can include jumps. Terrain fallback has no such
  // link contract: retain the source cliff guard for its local steering too.
  worldLocalNavigator.targetPosition=waypoint+(player.transform.position-position);worldLocalNavigator.allowWalkOffCliff=!r.world.navigationTerrainFallback;worldLocalNavigator.Update(Mathf.Clamp(elapsed-worldNavigationUpdatedAt,.001f,.1f));worldNavigationUpdatedAt=elapsed;
  r.world.navigationAllowWalkOffCliff=worldLocalNavigator.allowWalkOffCliff;
  r.world.navigationLocalMovement=worldLocalNavigator.moveVector;r.world.navigationLocalObstructed=worldLocalNavigator.wasObstructedLastUpdate;r.world.navigationLocalJumpSpeed=worldLocalNavigator.jumpSpeed;
  bridge.movement=movement.magnitude>stopDistance?new Vector2(worldLocalNavigator.moveVector.x,worldLocalNavigator.moveVector.z):Vector2.zero;
  // Walking in a circle is not progress toward the source waypoint. The real
  // Wetland return capture does this at full speed, so source frustration stays
  // zero. Recovery requests a normal player jump; source physics owns the result.
  var remaining=Vector3.Distance(position,waypoint);
  if(!worldNavigationHasProgress||Vector3.Distance(waypoint,worldNavigationProgressWaypoint)>.5f||Vector3.Distance(destination,worldNavigationProgressDestination)>2||remaining<worldNavigationProgressDistance-.5f){worldNavigationHasProgress=true;worldNavigationProgressWaypoint=waypoint;worldNavigationProgressDestination=destination;worldNavigationProgressDistance=remaining;worldNavigationProgressAt=elapsed;}
  r.world.navigationStalledSeconds=elapsed-worldNavigationProgressAt;
  // Terrain replanning changes the local waypoint even while circling the same
  // obstacle. Track the actual objective separately so it cannot hide that stall.
  float objectiveDistance=Vector3.Distance(position,destination);
  if(!worldNavigationHasObjectiveProgress||Vector3.Distance(destination,worldNavigationObjective)>2||objectiveDistance<worldNavigationObjectiveDistance-.5f){worldNavigationHasObjectiveProgress=true;worldNavigationObjective=destination;worldNavigationObjectiveDistance=objectiveDistance;worldNavigationObjectiveProgressAt=elapsed;}
  r.world.navigationObjectiveStalledSeconds=elapsed-worldNavigationObjectiveProgressAt;r.world.navigationObjectiveProgressDistance=worldNavigationObjectiveDistance;
  r.world.navigationProgressDistance=worldNavigationProgressDistance;r.world.navigationRecoveryJump=remaining>Mathf.Max(1,stopDistance)&&(r.world.navigationStalledSeconds>3||(r.world.navigationTerrainFallback&&r.world.navigationObjectiveStalledSeconds>3));
  bool jump=(r.world.navigationJump||worldLocalNavigator.jumpSpeed>0||r.world.navigationRecoveryJump)&&player.characterMotor.isGrounded&&elapsed%1.5f<.25f;bridge.DiagnosticJump(jump);if(jump&&r.world.navigationRecoveryJump)r.world.navigationRecoveryJumpFrames++;
  if(r.world.navigationRecoveryJump&&elapsed>worldNavigationRecoveryUntil){worldNavigationRecoveryUntil=elapsed+3;r.world.navigationRecoveries++;worldPathRequested=-100;}
 }
 bool FindSourceWorldApproach(CharacterBody player,RoR2.Navigation.NodeGraph graph,RoR2.Path path,Vector3 position,Vector3 destination){
  var began=Time.realtimeSinceStartup;float currentDistance=Vector3.Distance(position,destination);
  var candidates=new List<KeyValuePair<float,RoR2.Navigation.NodeGraph.NodeIndex>>();
  foreach(var index in graph.GetActiveNodesForHullMask((HullMask)(1<<(int)player.hullClassification))){
   Vector3 node;Check(graph.GetNodePosition(index,out node),"Original approach node unavailable");float distance=Vector3.Distance(node,destination);
   if(distance>=currentDistance-8)continue;if(!InsideSourceStageBounds(node)){r.world.navigationApproachBoundsRejected++;continue;}candidates.Add(new KeyValuePair<float,RoR2.Navigation.NodeGraph.NodeIndex>(distance,index));
  }
  candidates.Sort((a,b)=>a.Key.CompareTo(b.Key));
  foreach(var candidate in candidates){
   r.world.navigationPartialCandidates++;
   var task=graph.ComputePath(new RoR2.Navigation.NodeGraph.PathRequest{path=path,startPos=position,endPos=candidate.Value,hullClassification=player.hullClassification,maxSlope=player.characterMotor.Motor.MaxStableSlopeAngle,maxJumpHeight=player.maxJumpHeight,maxSpeed=player.moveSpeed});
   Check(task.status==RoR2.Navigation.PathTask.TaskStatus.Complete,"Original approach path did not complete");
   if(!task.wasReachable){r.world.navigationApproachUnreachable++;continue;}if(path.waypointsCount<2){r.world.navigationApproachTooShort++;continue;}
   r.world.navigationPartialNode=candidate.Value.nodeIndex;Check(graph.GetNodePosition(candidate.Value,out r.world.navigationPartialDestination),"Original approach destination unavailable");
   r.world.navigationPartialSeconds=Time.realtimeSinceStartup-began;return true;
  }
  r.world.navigationPartialSeconds=Time.realtimeSinceStartup-began;path.Clear();return false;
 }
 Vector3 TerrainTravelWaypoint(CharacterBody player,Vector3 position,Vector3 destination,float elapsed){
  r.world.navigationTerrainNoCandidate=false;
  if(worldNavigationBody!=player||Vector3.Distance(destination,worldTerrainGoal)>2){worldTerrainRecent.Clear();worldTerrainSelectedAt=-100;worldTerrainGoal=destination;}
  if(elapsed-worldTerrainSelectedAt<1&&Vector3.Distance(position,worldTerrainTarget)>1)return worldTerrainTarget;
  worldTerrainSelectedAt=elapsed;var desired=destination-position;desired.y=0;desired.Normalize();
  float best=float.NegativeInfinity;Vector3 selected=position;
  // Reuse the full game's ground-to-ground avoidance contract. Short candidates
  // handle local obstacles; longer ones keep the driver on recovered bridges.
  for(int i=0;i<16;i++)foreach(float length in new[]{4f,8f,16f}){
   var direction=Quaternion.AngleAxis(i*22.5f,Vector3.up)*desired;Vector3 prior=position,groundPoint=position;bool valid=true;
   int steps=Mathf.CeilToInt(length/1.5f);
   for(int step=1;step<=steps;step++){
    var sample=position+direction*(length*step/steps);sample.y=prior.y;RaycastHit ground=default(RaycastHit);
    int hits=Physics.RaycastNonAlloc(sample+Vector3.up*4,Vector3.down,worldTerrainHits,9,LayerIndex.world.mask,QueryTriggerInteraction.Ignore);
    if(hits==worldTerrainHits.Length){r.world.navigationTerrainRayOverflow++;valid=false;break;}
    // Overlapping floors must not turn a ceiling into the walking surface.
    float nearest=float.PositiveInfinity,highest=float.NegativeInfinity;
    for(int hitIndex=0;hitIndex<hits;hitIndex++){
     var hit=worldTerrainHits[hitIndex];float change=Mathf.Abs(hit.point.y-prior.y);
     if(hit.collider.gameObject.scene!=stageGeometryScene||Vector3.Angle(hit.normal,Vector3.up)>player.characterMotor.Motor.MaxStableSlopeAngle||change>player.maxJumpHeight||!InsideSourceStageBounds(hit.point))continue;
     highest=Mathf.Max(highest,hit.point.y);if(change<nearest){nearest=change;ground=hit;}
    }
    if(!ground.collider){valid=false;break;}if(highest-ground.point.y>.1f)r.world.navigationTerrainLowerChoices++;
    // A clear center ray can still send the actual body into an adjacent wall.
    // Sweep its measured torso width; original KCC remains the movement solver.
    var segment=ground.point-prior;RaycastHit clearance;
    if(segment.sqrMagnitude>.0001f&&Physics.SphereCast(prior+Vector3.up,player.characterMotor.Motor.Capsule.radius*.9f,segment.normalized,out clearance,segment.magnitude,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)){valid=false;break;}
    prior=groundPoint=ground.point;
   }
   if(!valid)continue;
   float score=Vector3.Distance(position,destination)-Vector3.Distance(groundPoint,destination);
   // A blocked slope may require moving sideways or away. Recent ground samples
   // penalize repeating the same circle without changing any simulation values.
   foreach(var recent in worldTerrainRecent)score-=Mathf.Max(0,8-Vector3.Distance(recent,groundPoint));
   if(score<=best)continue;best=score;selected=groundPoint;
  }
  // Rejection must not bypass the ground/torso/bounds checks by steering toward
  // an unchecked distant goal. Neutral input lets original physics settle.
  if(selected==position){r.world.navigationTerrainBlocked++;r.world.navigationTerrainNoCandidate=true;worldTerrainTarget=position;return position;}
  worldTerrainTarget=selected;if(worldTerrainRecent.Count==0||Vector3.Distance(position,worldTerrainRecent[worldTerrainRecent.Count-1])>3){worldTerrainRecent.Add(position);if(worldTerrainRecent.Count>40)worldTerrainRecent.RemoveAt(0);}
  return selected;
 }
 IEnumerator VerifyIntegratedWorldCleanup(){
  if(r.world==null)yield break;yield return null;yield return null;FinishWorldDotCleanup();
  if(r.objective!=null){r.objective.cleaned=!objectiveHost&&!objectiveStageHost&&!objectiveBossDeck&&objectiveResources.All(x=>!x)&&objectiveCards.All(x=>!x)&&objectiveTemplates.All(x=>!x)&&!ownsObjectiveIndicator&&objectiveLocator==null&&!objectiveSubscribed&&!TeleporterInteraction.instance&&!Stage.instance;Check(r.objective.cleaned,"Owned teleporter/actor/context/provider cleanup incomplete");}
  r.world.cleaned=worldObjects.All(x=>!x)&&worldModels.All(x=>!x)&&worldMaterials.All(x=>!x)&&!worldStaging&&!worldPause&&(!worldDriver||!worldDriver.enabled)&&!PauseStopController.instance&&!EjectionPickups().Any()&&!EjectionDroplets().Any()&&!ownsWorldDroplet&&!ownsWorldCoinLease&&worldDropletLocator==null&&!ownsPickupCatalog&&!ownsMoneyCatalog&&!ownsWorldLists&&!ownsWorldPresentation&&!ownsWorldMisc&&worldLootEffectSlots.Count==0&&worldLootSourceMaterials.Count==0&&worldLootSourceLayers.Count==0&&worldLootTemporaryEffects.All(x=>!x)&&worldFeatherEffectIndex<0&&worldFeatherJumped==null&&worldAvailableItems==null&&worldAvailableEquipment==null;
  r.world.cleaned&=worldNativeLootLeaseBaselines.Count==0&&worldNativeLootObjects.Count==0&&!ownsWorldDots&&(r.dots==null||(r.dots.cleaned&&DotController.readOnlyInstancesList.Count==0));
  if(r.hud!=null){r.hud.cleaned=!recoveredHud&&!recoveredMenu;r.world.cleaned&=r.hud.cleaned;}
  if(r.commerce!=null){r.commerce.cleaned=commerceOwned.All(x=>!x)&&commerceListeners.Count==0&&commercePurchases.Count==0&&!ownsCommerceMessages&&commerceEffectIndex<0;r.world.cleaned&=r.commerce.cleaned;}
  Check(r.world.cleaned,"Integrated content/input/loot/source/catalog cleanup incomplete");Save();
 }
 void DrawIntegratedWorld(){
  DrawWorldEquipment();
  var world=r.world;if(world==null||!world.ready)return;
  DrawDebugAcceleration();
  DrawMoonPillarMarkers();
  if(r.enhancedPresentation&&(!recoveredHud||debugPanel)&&GUI.Button(new Rect(recoveredHud?20:Screen.width-270,555,250,42),AndroidMaterialPresentation.report.enabled?"Graphics: approximation":"Graphics: legacy preview"))AndroidMaterialPresentation.SetEnabled(!AndroidMaterialPresentation.report.enabled);
  if(r.id.EndsWith("-bringup")&&world.health>0&&GUI.Button(new Rect(recoveredHud?20:Screen.width-210,recoveredHud?Screen.height-195:20,190,48),worldManualTakeover?"Resume auto route":"Take control")){
   var bridge=worldPlayer?worldPlayer.GetComponent<NovaInputBridge>():null;
   if(bridge){bridge.Neutral();worldManualTakeover=!worldManualTakeover;bridge.touchEquipment|=worldEquipmentTouch;worldEquipmentTouch=false;bridge.diagnosticInput=!worldManualTakeover;world.manualTakeover=worldManualTakeover;world.diagnosticInput=!worldManualTakeover;Save();}
  }
  var style=new GUIStyle(GUI.skin.label){fontSize=22};var shadow=new GUIStyle(style);shadow.normal.textColor=Color.black;
  if(recoveredHud&&world.health>0){GUI.Label(new Rect(20,Screen.height-30,Screen.width-40,26),"Offline composition · source UI/shader approximation · audio unavailable");return;}
  string text="Offline gameplay lab — "+(r.stageProgress!=null?r.stageProgress.current:"Titanic Plains")+"\nHP "+Mathf.Max(0,world.health).ToString("F0")+" / "+world.maxHealth.ToString("F0")+"    Lv "+world.level.ToString("F0")+"    $"+world.money+"    "+world.seconds.ToString("F0")+"s\nKills "+world.kills+"    Enemies "+world.liveEnemies+"    Chests "+world.openedChests+" / "+world.chests+"\nSyringe "+world.syringe+" · Glasses "+world.glasses+" · Slug "+world.slug+" · Ukulele "+world.lightning+"\n"+world.lastPickup+"    Crit "+world.crit.ToString("F0")+"% · Regen "+world.regen.ToString("F1")+"\nA jump · B interact · X primary · Y secondary · LB roll · RB barrage\n"+(string.IsNullOrEmpty(world.target)?"Explore, fight and earn money":"B: "+world.target)+"\nAudio, stock startup and profiles unavailable";
  if(world.lootDomain>4)text+="\nEnergy Drink "+world.drink+" · Steak "+world.steak+" · Move speed "+world.moveSpeed.ToString("F1");
  if(world.lootTier3>0)text+="\nShield "+world.shield.ToString("F0")+" / "+world.maxShield.ToString("F0")+" · Jumps "+world.motorMaxJumpCount;
  if(r.moon!=null&&r.moon.loaded)text+="\nMoon batteries "+r.moon.charged+" / "+r.moon.required+" · Encounter enemies "+r.moon.livingEncounterMembers+"\n"+world.objective;
  else if(r.objective!=null&&r.objective.ready)text+="\nTeleporter "+r.objective.state+" — "+(r.objective.charge*100).ToString("F0")+"% | "+(r.objective.bossDefeated?"Boss defeated":"Boss HP "+r.objective.bossHealth.ToString("F0")+" / "+r.objective.bossMaxHealth.ToString("F0"));
  if(world.health<=0){text+="\nCommando defeated. Press A to restart a fresh run.";if(GUI.Button(new Rect(20,420,240,48),"Restart run (A)"))RequestWorldRestart();if(GUI.Button(new Rect(280,420,180,48),"Close session"))Application.Quit();}else if(worldView!=null)worldView.DrawReticle();
  GUI.Label(new Rect(21,61,1100,350),text,shadow);GUI.Label(new Rect(20,60,1100,350),text,style);
 }
 void RequestWorldRestart(){if(r!=null&&r.freePlay&&r.integratedWorld&&r.phase=="commando-defeated"&&r.playerDefeat.bodyDestroyed){restartRequested=true;r.phase="restarting-world";Save();}}
 void ObserveWorldRestartInput(){if(r==null||!r.freePlay||!r.integratedWorld||r.phase!="commando-defeated"||r.nova==null)return;if(UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0+r.nova.mapping.jump)))RequestWorldRestart();}
 void RestartWorldAfterCleanup(){
  if(!restartRequested)return;Check(r.success&&r.cleanup&&r.world.cleaned&&r.modelDestroyed&&!Run.instance&&!SceneInfo.instance&&!NetworkServer.active&&!NetworkClient.active,"Defeated world not clean enough to restart");
  System.IO.File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"movement-completed-session-"+sessionIndex+".json"),JsonUtility.ToJson(r,true));
  var next=new GameObject("Persistent offline gameplay session").AddComponent<MovementBatchProbe>();next.sessionIndex=sessionIndex+1;next.skipOfflineMenu=!returnToOfflineMenu;Destroy(gameObject);
 }
 void CleanupIntegratedWorld(){CleanupRecoveredHud();CleanupIntegratedResults();CleanupWorldCommerce(true);CleanupTeleporterWorld();
  worldPathFollower.Reset();worldLocalNavigator.SetBody(null);worldNavigationBody=null;worldTerrainRecent.Clear();worldTerrainSelectedAt=worldTerrainRecoveryUntil=-100;
  if(r.world==null)return;
  if(ownsWorldPresentation){GlobalEventManager.onTeamLevelUp+=unavailableTeamLevelSound;Run.onRunAmbientLevelUp+=unavailableAmbientSound;GlobalEventManager.onCharacterLevelUp+=unavailableLevelEffect;if(worldPlayer&&worldPlayer.inventory)worldPlayer.inventory.onItemAddedClient+=unavailableItemHighlight;ownsWorldPresentation=false;}
  if(worldInteraction!=null)GlobalEventManager.OnInteractionsGlobal-=worldInteraction;if(worldDriver)worldDriver.enabled=false;
  if(worldPlayer)worldPlayer.inputBank.interact.PushState(false);
  foreach(var pickup in EjectionPickups().ToArray())NetworkServer.Destroy(pickup.gameObject);foreach(var droplet in EjectionDroplets().ToArray())NetworkServer.Destroy(droplet.gameObject);
  foreach(var obj in worldObjects)if(obj)NetworkServer.Destroy(obj);if(worldStaging)Destroy(worldStaging);if(worldPause)NetworkServer.Destroy(worldPause);
  CleanupChestEjection();
  if(rewardPrefabs!=null){var prefab=rewardPrefabs[0];var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);EffectPool pool;if(pools.TryGetValue(prefab,out pool)){foreach(var effect in pool.InUse.ToArray())pool.ReturnObject(effect);EffectManager.ClearPool(prefab);pool.Kill();}((IDictionary)RewardField(typeof(EffectManager),"_ShouldUsePooledEffectMap").GetValue(null)).Remove(prefab);}
  if(ownsWorldCoinLease&&worldCoinLease.IsValid()){int extra=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(worldCoinLease)-worldCoinBaseline;Check(extra>=0&&extra<=worldBarrelConsumers,"Unattributed integrated barrel coin leases");for(int i=0;i<extra;i++)Addressables.Release(worldCoinLease.Result);Addressables.Release(worldCoinLease);ownsWorldCoinLease=false;}
  RestoreWorldHandlers(false);RestoreWorldHandlers(true);if(activeBodyClient!=null)foreach(short id in new short[]{52,55,57})activeBodyClient.UnregisterHandler(id);if(ownsWorldTeleportHandler){if(activeBodyClient!=null)activeBodyClient.UnregisterHandler(68);if(NetworkServer.active)NetworkServer.UnregisterHandler(68);ownsWorldTeleportHandler=false;}
  if(worldVfxOption!=null)worldVfxOption.AttemptSetString(priorWorldVfx);if(priorWorldXp!=null)SettingsConVars.cvExpAndMoneyEffects.AttemptSetString(priorWorldXp);
  if(ownsWorldLists&&Run.instance){
   if(worldAvailableItems!=null){worldAvailableItems.Clear();worldAvailableEquipment.Clear();Run.instance.BuildDropTable();Run.instance.availableItems=previousWorldAvailableItems;Run.instance.availableEquipment=previousWorldAvailableEquipment;ItemMask.Return(worldAvailableItems);EquipmentMask.Return(worldAvailableEquipment);worldAvailableItems=null;worldAvailableEquipment=null;}
   else{Run.instance.availableTier1DropList.Clear();Run.instance.availableTier2DropList.Clear();Run.instance.availableTier3DropList.Clear();}
   if(worldChestTable)worldChestTable.RegenerateDropTable(Run.instance);Check(Run.instance.availableTier1DropList.Count==0&&Run.instance.availableTier2DropList.Count==0&&Run.instance.availableTier3DropList.Count==0&&(!worldChestTable||worldChestTable.GetPickupCount()==0),"Integrated loot list/table restore failed");ownsWorldLists=false;
  }
  if(ownsWorldMisc){RoR2Content.MiscPickups.LunarCoin=null;worldLunarCoin.miscPickupIndex=MiscPickupIndex.None;RoR2.ContentManagement.ContentManager._miscPickupDefs=previousWorldMiscContent;RewardField(typeof(MiscPickupCatalog),"_miscPickupDefs").SetValue(null,previousWorldMiscCatalog);MiscPickupCatalog.availability=previousWorldMiscAvailability;ownsWorldMisc=false;Check(MiscPickupCatalog.pickupCount==0&&!RoR2Content.MiscPickups.LunarCoin,"Owned lunar definition/catalog restore failed");}
  if(worldDropletField!=null)worldDropletField.SetValue(null,priorWorldDroplet);if(ownsWorldDroplet&&worldDropletSource){Addressables.Release(worldDropletSource);ownsWorldDroplet=false;}if(worldDropletLocator!=null){Addressables.RemoveResourceLocator(worldDropletLocator);worldDropletLocator=null;}
  foreach(var material in worldMaterials)if(material)Destroy(material);
  Save();
 }
}
