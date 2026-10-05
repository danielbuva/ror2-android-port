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
 [Serializable] public class WorldReport {
  public NovaThirdPersonView.Report camera;
  public bool lunarDefinition,lunarCurrencyAvailable;
  public bool ready,authority,lootReady,interactionReady,cleaned,diagnosticInput;
  public int tableLoadedCount,barrels,chests,openedBarrels,openedChests,pickups,droplets,pickupMessages,coinMessages,xpMessages,frames,kills,liveEnemies;
  public int lootDomain,syringe,lightning,glasses,slug,drink,steak,secondary,roll,barrage;public uint money;public ulong experience;
  public float simulationSeconds,seconds,health,maxHealth,level,attackSpeed,crit,regen,moveSpeed,difficulty,distance;
  public string scope,objective,target,lastPickup,feedbackCapability;public Vector3 start,position;
  public float interactionDistance;public WorldPickupObservation[] pickupObservations;
  public List<WorldPickupMessageObservation> pickupMessageObservations=new List<WorldPickupMessageObservation>();public int unresolvedPickupMessages,otherPickupMessages,zeroCountPickupMessages;
  public string navigationTarget;public bool navigationReachable,navigationJump;public int navigationWaypoints;public Vector3 navigationDestination,navigationWaypoint;
  public int navigationRecoveries;public float navigationStalledSeconds;
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
 int worldObjective;float worldLastPress=-1;
 RoR2.PathFollower worldPathFollower=new RoR2.PathFollower();Vector3 worldPathTarget;float worldPathRequested=-100;
 Vector3 worldNavigationProgressPosition;float worldNavigationProgressAt,worldNavigationRecoveryUntil=-1;
 NovaThirdPersonView worldView;bool restartRequested;public int sessionIndex=1;
 bool ownsWorldMisc;MiscPickupDef[] previousWorldMiscContent;object previousWorldMiscCatalog;
 ResourceAvailability previousWorldMiscAvailability;LunarCoinDef worldLunarCoin;
Action<TeamIndex> unavailableTeamLevelSound;Action<Run> unavailableAmbientSound;Action<CharacterBody> unavailableLevelEffect;
Action<ItemIndex> unavailableItemHighlight;bool ownsWorldPresentation;


 ItemDef[] WorldTierOneLoot(Result cfg){
  var loot=new List<ItemDef>{RoR2Content.Items.Syringe,RoR2Content.Items.CritGlasses,RoR2Content.Items.HealWhileSafe};
  // Receipted additions only. Older accepted configurations retain their original pool.
  if(cfg.teleporterLoop&&cfg.objectiveItemNames!=null){
   if(cfg.objectiveItemNames.Contains("SprintBonus"))loot.Add(RoR2Content.Items.SprintBonus);
   if(cfg.objectiveItemNames.Contains("FlatHealth"))loot.Add(RoR2Content.Items.FlatHealth);
  }
  return loot.ToArray();
 }
 IEnumerator PrepareIntegratedWorld(CharacterBody player,Result cfg){
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
  var lunarPickup=worldLunarCoin.CreatePickupDef();PickupCatalog.SetEntries(ItemCatalog.allItemDefs.Select(x=>x.CreatePickupDef()).Concat(new[]{lunarPickup}).ToArray());
  r.world.lunarDefinition=MiscPickupCatalog.GetMiscDef(worldLunarCoin.miscPickupIndex)==worldLunarCoin&&PickupCatalog.FindPickupIndex(worldLunarCoin.miscPickupIndex)==lunarPickup.pickupIndex&&lunarPickup.attemptGrant.Method.DeclaringType==typeof(LunarCoinDef);
  Check(r.world.lunarDefinition&&!Util.LookUpBodyNetworkUser(player),"Original lunar definition or unavailable currency contract changed");r.world.lunarCurrencyAvailable=false;
  Check(Run.instance.availableTier1DropList.Count==0&&Run.instance.availableTier2DropList.Count==0,"Unowned integrated loot lists");
  ownsWorldLists=true;
  foreach(var item in WorldTierOneLoot(cfg)){
   Check(item&&!item.requiredExpansion&&!item.unlockableDef&&item.tier==ItemTier.Tier1&&!Run.instance.IsItemExpansionLocked(item.itemIndex),"Integrated base item unavailable");Run.instance.availableTier1DropList.Add(PickupCatalog.FindPickupIndex(item.itemIndex));
  }
  Run.instance.availableTier2DropList.Add(PickupCatalog.FindPickupIndex(RoR2Content.Items.ChainLightning.itemIndex));
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
  r.world.lootDomain=worldChestTable.GetPickupCount();Check(r.world.lootDomain==WorldTierOneLoot(cfg).Length+1,"Integrated source chest loot domain missing");
  PrepareWorldMessages();
  worldCoinLease=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/Effects/CoinEmitter");ownsWorldCoinLease=true;yield return worldCoinLease;
  Check(worldCoinLease.Result==rewardPrefabs[0],"Integrated coin source witness differs");worldCoinBaseline=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(worldCoinLease);
  worldPause=new GameObject("Offline gameplay pause context");worldPause.SetActive(false);worldPause.AddComponent<NetworkIdentity>();worldPause.AddComponent<PauseStopController>();worldPause.SetActive(true);
  yield return null;Check(PauseStopController.instance&&!PauseStopController.instance.isPaused,"Integrated unpaused context missing");
  worldDriver=player.GetComponent<InteractionDriver>();Check(worldDriver&&(!worldDriver||!worldDriver.enabled)&&!worldDriver.interactableOverride,"Unowned integrated interaction driver");
  if(!player.equipmentSlot.characterBody)Call(player.equipmentSlot,"Start");Call(player.equipmentSlot,"UpdateInventory");
  Check(player.equipmentSlot.equipmentIndex==EquipmentIndex.None&&!player.equipmentSlot.enabled,"Integrated equipment must remain unavailable/ungranted");
  if(DriverField(worldDriver,"networkIdentity")==null)Call(worldDriver,"Awake");
  worldStaging=new GameObject("Inactive offline content staging");worldStaging.SetActive(false);
  var chestSource=artifactBundle.LoadAsset<GameObject>(cfg.chestAsset);OwnChestAnimationSources(chestSource.GetComponent<ModelLocator>().modelTransform);
  // Measured near-spawn layout; placement is an Android adapter, not original SceneDirector placement.
  var origin=player.characterMotor.Motor.TransientPosition;
  var barrelOffsets=new[]{new Vector3(2,0,0),new Vector3(-2,0,0),new Vector3(0,0,3),new Vector3(4,0,3),new Vector3(-4,0,3),new Vector3(0,0,-3)};
  foreach(var offset in barrelOffsets){var obj=CreateWorldInteractable(artifactBundle.LoadAsset<GameObject>(cfg.barrelAsset),origin+offset,false);if(obj)worldBarrels.Add(obj.GetComponent<BarrelInteraction>());}
  foreach(var offset in new[]{new Vector3(5,0,0),new Vector3(-5,0,0),new Vector3(0,0,6),new Vector3(6,0,6)}){var obj=CreateWorldInteractable(chestSource,origin+offset,true);if(obj)worldChests.Add(obj.GetComponent<ChestBehavior>());}
  Check(worldBarrels.Count>=3&&worldChests.Count>=2,"Integrated layout has insufficient walkable source interactables");
  r.world.barrels=worldBarrels.Count;r.world.chests=worldChests.Count;r.world.lootReady=true;
  worldInteraction=(actor,component,obj)=>{if(actor!=worldDriver.interactor)return;if(worldObjects.Contains(obj))r.world.target=obj.name;};GlobalEventManager.OnInteractionsGlobal+=worldInteraction;
  worldDriver.enabled=true;yield return null;Call(activeBodyClient,"Update");
  r.world.interactionReady=worldDriver.enabled&&ReferenceEquals(DriverField(worldDriver,"inputBank"),player.inputBank);
  r.world.start=origin;r.world.ready=r.world.authority&&r.world.lootReady&&r.world.interactionReady&&rewardDirector.enabled;
  if(cfg.teleporterLoop){var objective=PrepareTeleporterWorld(cfg);while(objective.MoveNext())yield return objective.Current;}
  Check(r.world.ready,"Integrated session setup incomplete");r.phase="integrated-world-playing";Save();
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
  Check(!activeBodyClient.handlers.ContainsKey(52)&&!activeBodyClient.handlers.ContainsKey(55)&&!activeBodyClient.handlers.ContainsKey(57),"Unowned integrated presentation handlers");
  worldVfxOption=(RoR2.ConVar.IntConVar)RewardField(typeof(VFXBudget),"mediumPriorityCostThreshold").GetValue(null);priorWorldVfx=worldVfxOption.GetString();worldVfxOption.AttemptSetString(worldVfxOption.defaultValue);
  priorWorldXp=SettingsConVars.cvExpAndMoneyEffects.GetString();SettingsConVars.cvExpAndMoneyEffects.AttemptSetString("0");
  var effects=(NetworkMessageDelegate)Delegate.CreateDelegate(typeof(NetworkMessageDelegate),typeof(EffectManager).GetMethod("HandleEffectClient",BindingFlags.Static|BindingFlags.NonPublic));
  var xp=(NetworkMessageDelegate)Delegate.CreateDelegate(typeof(NetworkMessageDelegate),typeof(ExperienceManager).GetMethod("HandleCreateExpEffect",BindingFlags.Static|BindingFlags.NonPublic));
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
   if(observation.playerMaster&&definition!=null&&quantity>0){r.world.pickupMessages++;r.world.lastPickup=observation.item+" x"+quantity;}Save();
  });
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
  world.syringe=player.inventory.GetItemCountPermanent(RoR2Content.Items.Syringe);world.lightning=player.inventory.GetItemCountPermanent(RoR2Content.Items.ChainLightning);world.glasses=player.inventory.GetItemCountPermanent(RoR2Content.Items.CritGlasses);world.slug=player.inventory.GetItemCountPermanent(RoR2Content.Items.HealWhileSafe);world.crit=player.crit;world.regen=player.regen;world.moveSpeed=player.moveSpeed;
  if(world.lootDomain>4){world.drink=player.inventory.GetItemCountPermanent(RoR2Content.Items.SprintBonus);world.steak=player.inventory.GetItemCountPermanent(RoR2Content.Items.FlatHealth);}
  world.openedBarrels=worldBarrels.Count(x=>x&&x.Networkopened);world.openedChests=worldChests.Count(x=>x&&x.NetworkisChestOpened);world.liveEnemies=directorActors.Count(x=>x.body&&x.body.healthComponent.alive);
  var pickups=EjectionPickups().ToArray();world.pickups=pickups.Length;world.droplets=EjectionDroplets().Count();
  var interactor=player.GetComponent<Interactor>();world.interactionDistance=interactor.maxInteractionDistance;
  world.pickupObservations=pickups.Select(x=>{var collider=x.GetComponentsInChildren<Collider>(true).FirstOrDefault(c=>c.enabled&&(LayerIndex.CommonMasks.interactable.value&(1<<c.gameObject.layer))!=0);var aim=collider?collider.bounds.center:x.transform.position;var def=PickupCatalog.GetPickupDef(x.pickup.pickupIndex);return new WorldPickupObservation{item=def==null?"invalid":def.internalName,interactability=x.GetInteractability(interactor).ToString(),position=x.transform.position,aimTarget=aim,aimDistance=Vector3.Distance(player.inputBank.aimOrigin,aim),selected=worldDriver.currentInteractable==x.gameObject,collider=collider,interactableLayer=collider};}).ToArray();
  foreach(var pickup in pickups){if(!pickup.pickupDisplay)continue;var model=(GameObject)typeof(PickupDisplay).GetField("modelObject",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(pickup.pickupDisplay);if(model)PresentWorldModel(model.transform,false);}
  world.secondary=r.combat.secondaryEntries;world.roll=r.combat.utilityEntries;world.barrage=r.combat.specialEntries;
  world.target=worldDriver.currentInteractable?worldDriver.currentInteractable.name:"";
 }
 void IntegratedWorldStimulus(CharacterBody player,NovaInputBridge bridge,float elapsed){
  // Explicit automation for integrated validation only; direct app launches use physical controls.
  r.world.diagnosticInput=true;bridge.diagnosticSprint=false;GameObject target=null;bridge.diagnosticInteract=false;bridge.diagnosticPrimary=false;bridge.diagnosticSecondary=false;bridge.diagnosticUtility=false;bridge.diagnosticSpecial=false;bridge.DiagnosticJump(false);
  if(r.moon!=null&&r.moon.loaded&&MoonWorldStimulus(player,bridge,elapsed))return;
  if(worldObjective==0){var barrel=worldBarrels.FirstOrDefault(x=>x&&!x.Networkopened);if(barrel)target=barrel.gameObject;else worldObjective=1;}
  if(worldObjective==3&&elapsed-stageEnteredAt<105&&worldChests.Any(x=>x&&!x.NetworkisChestOpened&&player.master.money>=x.GetComponent<PurchaseInteraction>().cost))worldObjective=1;
  if(worldObjective==1){var chest=worldChests.FirstOrDefault(x=>x&&!x.NetworkisChestOpened);if(r.world.openedChests>r.world.pickupMessages-stagePickupBaseline)worldObjective=2;else if(chest&&player.master.money>=chest.GetComponent<PurchaseInteraction>().cost)target=chest.gameObject;else worldObjective=3;}
  if(worldObjective==2){var pickup=GrantableWorldPickups(player).OrderBy(x=>Vector3.Distance(x.transform.position,player.corePosition)).FirstOrDefault();if(pickup)target=pickup.gameObject;else if(r.world.pickupMessages-stagePickupBaseline==r.world.openedChests)worldObjective=3;}
  r.world.objective=worldObjective==0?"Collect original barrel rewards":worldObjective==1?"Purchase original chest":worldObjective==2?"Collect naturally ejected item":"Survive original director combat";
  if(r.teleporterLoop&&elapsed-stageEnteredAt>65){if(ObjectiveWorldStimulus(player,bridge,elapsed))return;}
  bridge.movement=Vector2.zero;
  if(target){
   NavigateWorldInput(player,bridge,target.transform.position,target.GetComponent<GenericPickupController>() ? .6f : 1.6f,target.name,elapsed);
   var collider=target.GetComponentsInChildren<Collider>(true).FirstOrDefault(x=>x.enabled&&!x.isTrigger);var aim=(collider?collider.bounds.center:target.transform.position)-player.inputBank.aimOrigin;bridge.aim=new Vector2(aim.x,aim.z).normalized;
   // The original input producer consumes a 3D ray; use the measured target elevation as well.
   bridge.diagnosticAim=aim.normalized;
   if(worldDriver.currentInteractable==target&&elapsed-worldLastPress>.5f){bridge.diagnosticInteract=true;worldLastPress=elapsed;}
  }else{
   bridge.diagnosticAim=Vector3.zero;var enemy=directorActors.Where(x=>x.body&&x.body.healthComponent.alive).OrderBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();
   if(enemy!=null){var aim=enemy.body.corePosition-player.inputBank.aimOrigin;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticAim=aim.normalized;bridge.diagnosticPrimary=true;bridge.diagnosticSecondary=elapsed%12<.2f;bridge.diagnosticSpecial=elapsed%20<.2f;bridge.diagnosticUtility=elapsed%16<.2f;}
   bridge.DiagnosticJump(elapsed%18<.2f);
  }
 }
 void NavigateWorldInput(CharacterBody player,NovaInputBridge bridge,Vector3 destination,float stopDistance,string target,float elapsed){
  var position=player.characterMotor.Motor.TransientPosition;var delta=destination-position;var planar=new Vector2(delta.x,delta.z);
  var graph=SceneInfo.instance?SceneInfo.instance.groundNodes:null;var waypoint=destination;
  r.world.navigationTarget=target;r.world.navigationDestination=destination;r.world.navigationJump=false;
  if(worldPathFollower.nodeGraph!=graph||Vector3.Distance(destination,worldPathTarget)>2||Vector3.Distance(position,worldNavigationProgressPosition)>1){worldNavigationProgressPosition=position;worldNavigationProgressAt=elapsed;}
  // Replay follows the recovered graph through the normal input boundary. Original
  // motor limits, graph gates, physics, interaction range and item positions remain authoritative.
  RaycastHit obstacle;bool needsRoute=Mathf.Abs(delta.y)>2||planar.magnitude>15||Physics.Linecast(position+Vector3.up,destination+Vector3.up,out obstacle,LayerIndex.world.mask,QueryTriggerInteraction.Ignore);
  if(graph&&needsRoute){
   if(worldPathFollower.nodeGraph!=graph||Vector3.Distance(destination,worldPathTarget)>2||elapsed-worldPathRequested>8){
    using(var path=new RoR2.Path(graph)){
     var task=graph.ComputePath(new RoR2.Navigation.NodeGraph.PathRequest{path=path,startPos=position,endPos=destination,hullClassification=player.hullClassification,maxSlope=player.characterMotor.Motor.MaxStableSlopeAngle,maxJumpHeight=player.maxJumpHeight,maxSpeed=player.moveSpeed});
     Check(task.status==RoR2.Navigation.PathTask.TaskStatus.Complete,"Original stage path did not complete");
     r.world.navigationReachable=task.wasReachable;r.world.navigationWaypoints=path.waypointsCount;worldPathFollower.SetPath(path);
    }
    worldPathTarget=destination;worldPathRequested=elapsed;
   }
   worldPathFollower.UpdatePosition(position);var next=worldPathFollower.GetNextPosition();if(next.HasValue)waypoint=next.Value;
   r.world.navigationJump=worldPathFollower.nextWaypointNeedsJump;
   bridge.DiagnosticJump(r.world.navigationJump&&player.characterMotor.isGrounded&&elapsed%1.5f<.25f);
  }else{worldPathFollower.Reset();r.world.navigationReachable=true;r.world.navigationWaypoints=0;}
  r.world.navigationWaypoint=waypoint;var direction=waypoint-position;var movement=new Vector2(direction.x,direction.z);
  bridge.movement=movement.magnitude>stopDistance?movement.normalized:Vector2.zero;
  r.world.navigationStalledSeconds=elapsed-worldNavigationProgressAt;
  if(movement.magnitude>Mathf.Max(3,stopDistance)&&r.world.navigationStalledSeconds>3&&elapsed>worldNavigationRecoveryUntil){worldNavigationRecoveryUntil=elapsed+3;r.world.navigationRecoveries++;worldPathRequested=-100;}
  if(elapsed<worldNavigationRecoveryUntil){
   float recovery=3-(worldNavigationRecoveryUntil-elapsed);var forward=movement.normalized;
   // A graph link is guidance, not proof that the current capsule clears a root/ledge.
   // Replay tries normal jump/sidestep/back-off input; the original state decides whether
   // jumping is possible. Never translate the actor or change collision/graph data.
   bridge.DiagnosticJump(recovery<.25f);
   bridge.movement=recovery<.4f?forward:recovery<1.5f?new Vector2(forward.y,-forward.x):recovery<2.5f?-forward:new Vector2(-forward.y,forward.x);
  }
 }
 IEnumerator VerifyIntegratedWorldCleanup(){
  if(r.world==null)yield break;yield return null;yield return null;
  if(r.objective!=null){r.objective.cleaned=!objectiveHost&&!objectiveStageHost&&!objectiveBossDeck&&objectiveResources.All(x=>!x)&&objectiveCards.All(x=>!x)&&objectiveTemplates.All(x=>!x)&&!ownsObjectiveIndicator&&objectiveLocator==null&&!objectiveSubscribed&&!TeleporterInteraction.instance&&!Stage.instance;Check(r.objective.cleaned,"Owned teleporter/actor/context/provider cleanup incomplete");}
  r.world.cleaned=worldObjects.All(x=>!x)&&worldModels.All(x=>!x)&&worldMaterials.All(x=>!x)&&!worldStaging&&!worldPause&&(!worldDriver||!worldDriver.enabled)&&!PauseStopController.instance&&!EjectionPickups().Any()&&!EjectionDroplets().Any()&&!ownsWorldDroplet&&!ownsWorldCoinLease&&worldDropletLocator==null&&!ownsPickupCatalog&&!ownsMoneyCatalog&&!ownsWorldLists&&!ownsWorldPresentation&&!ownsWorldMisc;
  Check(r.world.cleaned,"Integrated content/input/loot/source/catalog cleanup incomplete");Save();
 }
 void DrawIntegratedWorld(){
  var world=r.world;if(world==null||!world.ready)return;
  var style=new GUIStyle(GUI.skin.label){fontSize=22};var shadow=new GUIStyle(style);shadow.normal.textColor=Color.black;
  string text="Offline gameplay lab — "+(r.stageProgress!=null?r.stageProgress.current:"Titanic Plains")+"\nHP "+Mathf.Max(0,world.health).ToString("F0")+" / "+world.maxHealth.ToString("F0")+"    Lv "+world.level.ToString("F0")+"    $"+world.money+"    "+world.seconds.ToString("F0")+"s\nKills "+world.kills+"    Enemies "+world.liveEnemies+"    Chests "+world.openedChests+" / "+world.chests+"\nSyringe "+world.syringe+" · Glasses "+world.glasses+" · Slug "+world.slug+" · Ukulele "+world.lightning+"\n"+world.lastPickup+"    Crit "+world.crit.ToString("F0")+"% · Regen "+world.regen.ToString("F1")+"\nA jump · B interact · X primary · Y secondary · LB roll · RB barrage\n"+(string.IsNullOrEmpty(world.target)?"Explore, fight and earn money":"B: "+world.target)+"\nAudio, stock startup and profiles unavailable";
  if(world.lootDomain>4)text+="\nEnergy Drink "+world.drink+" · Steak "+world.steak+" · Move speed "+world.moveSpeed.ToString("F1");
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
 void CleanupIntegratedWorld(){CleanupIntegratedResults();CleanupTeleporterWorld();
  worldPathFollower.Reset();
  if(r.world==null)return;
  if(ownsWorldPresentation){GlobalEventManager.onTeamLevelUp+=unavailableTeamLevelSound;Run.onRunAmbientLevelUp+=unavailableAmbientSound;GlobalEventManager.onCharacterLevelUp+=unavailableLevelEffect;if(worldPlayer&&worldPlayer.inventory)worldPlayer.inventory.onItemAddedClient+=unavailableItemHighlight;ownsWorldPresentation=false;}
  if(worldInteraction!=null)GlobalEventManager.OnInteractionsGlobal-=worldInteraction;if(worldDriver)worldDriver.enabled=false;
  if(worldPlayer)worldPlayer.inputBank.interact.PushState(false);
  foreach(var pickup in EjectionPickups().ToArray())NetworkServer.Destroy(pickup.gameObject);foreach(var droplet in EjectionDroplets().ToArray())NetworkServer.Destroy(droplet.gameObject);
  foreach(var obj in worldObjects)if(obj)NetworkServer.Destroy(obj);if(worldStaging)Destroy(worldStaging);if(worldPause)NetworkServer.Destroy(worldPause);
  CleanupChestEjection();
  if(rewardPrefabs!=null){var prefab=rewardPrefabs[0];var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);EffectPool pool;if(pools.TryGetValue(prefab,out pool)){foreach(var effect in pool.InUse.ToArray())pool.ReturnObject(effect);EffectManager.ClearPool(prefab);pool.Kill();}((IDictionary)RewardField(typeof(EffectManager),"_ShouldUsePooledEffectMap").GetValue(null)).Remove(prefab);}
  if(ownsWorldCoinLease&&worldCoinLease.IsValid()){int extra=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(worldCoinLease)-worldCoinBaseline;Check(extra>=0&&extra<=worldBarrelConsumers,"Unattributed integrated barrel coin leases");for(int i=0;i<extra;i++)Addressables.Release(worldCoinLease.Result);Addressables.Release(worldCoinLease);ownsWorldCoinLease=false;}
  if(activeBodyClient!=null)foreach(short id in new short[]{52,55,57})activeBodyClient.UnregisterHandler(id);
  if(worldVfxOption!=null)worldVfxOption.AttemptSetString(priorWorldVfx);if(priorWorldXp!=null)SettingsConVars.cvExpAndMoneyEffects.AttemptSetString(priorWorldXp);
  if(ownsWorldLists&&Run.instance){Run.instance.availableTier1DropList.Clear();Run.instance.availableTier2DropList.Clear();if(worldChestTable)worldChestTable.RegenerateDropTable(Run.instance);Check(Run.instance.availableTier1DropList.Count==0&&Run.instance.availableTier2DropList.Count==0&&(!worldChestTable||worldChestTable.GetPickupCount()==0),"Integrated loot list/table restore failed");ownsWorldLists=false;}
  if(ownsWorldMisc){RoR2Content.MiscPickups.LunarCoin=null;worldLunarCoin.miscPickupIndex=MiscPickupIndex.None;RoR2.ContentManagement.ContentManager._miscPickupDefs=previousWorldMiscContent;RewardField(typeof(MiscPickupCatalog),"_miscPickupDefs").SetValue(null,previousWorldMiscCatalog);MiscPickupCatalog.availability=previousWorldMiscAvailability;ownsWorldMisc=false;Check(MiscPickupCatalog.pickupCount==0&&!RoR2Content.MiscPickups.LunarCoin,"Owned lunar definition/catalog restore failed");}
  if(worldDropletField!=null)worldDropletField.SetValue(null,priorWorldDroplet);if(ownsWorldDroplet&&worldDropletSource){Addressables.Release(worldDropletSource);ownsWorldDroplet=false;}if(worldDropletLocator!=null){Addressables.RemoveResourceLocator(worldDropletLocator);worldDropletLocator=null;}
  foreach(var material in worldMaterials)if(material)Destroy(material);
  Save();
 }
}
