// Subsystem: stage transport (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PreloadObjectiveBundle, PrepareObjectiveSupport, PrepareTeleporterWorld, SpawnStageObjective (TeleporterWorldSession); teardown CleanupTeleporterWorld (Dispose), CleanupObjectiveSupport, ReleaseObjectiveBundlePreload, CleanupObjectiveConfigs, CleanupOriginalGameModes at their existing call sites.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using RoR2;
using RoR2.ContentManagement;
using RoR2.CharacterAI;
using RoR2.Orbs;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Composed original objective. This shell owns content/context, observation and Android view.
// Original interaction/FSM/director/boss squad/holdout/rewards/exit perform gameplay.
public sealed partial class MovementBatchProbe {
 [Serializable] public class ObjectiveVisualBinding {public string path,mesh,material;}
 [Serializable] public class ObjectiveVisualActivation {public string path;public bool active;}
 [Serializable] public class ObjectiveActorSpec {public string name,body,master,card,avatar,controller,material,mesh;public bool recoveredMaterials;public ObjectiveVisualBinding[] bindings;public ObjectiveVisualActivation[] activations;}
 [Serializable] public class SurfacePropertyObservation {public string name,type,texture;public Vector4 value;public int textureId,width,height;public Vector2 scale,offset;}
 [Serializable] public class SurfaceMaterialObservation {public int instanceId,shaderId,passCount;public string[] keywords;public bool instancing,doubleSidedGi;public SurfacePropertyObservation[] properties;}
 [Serializable] public class ObjectiveRendererObservation {public string path,kind;public int unityFrame;public string[] materials,shaders;public int[] queues;public bool enabled,active,visible,worldOwned;public int particles;public float projectedBoundsFraction;public Vector3 center,size;public string particleRenderMode,particleAlignment;public string[] vertexStreams;public SurfaceMaterialObservation[] materialState;}
 [Serializable] public class ObjectiveReport {
  public bool ready,rules,idle,available,selected,authority,charging,charged,bossDefeated,finished,exitBegan,exitFinished,cleaned,rewardCollected,rewardLeftBehind;
  public int rewardPickupBaseline,rewardPickupMessages;
  public string[] rewardTables;
  public int silentSourceComponents,frames,bossSpawns,bossDeaths,bossMembers,normalSpawns,ruleCount,unusedParticleMaterialSlots,previewMaterialSlots;
  public float charge,radius,bossHealth,bossMaxHealth,sourceDuration,sourceRadius,credits,spent;
  public string state,fsmState,nextScene,exitState,scope,bossSelectionScope,difficulty;public string[] eligibleBossCards;public Vector3 position;
  public List<string> transitions=new List<string>();
  public ObjectiveRendererObservation[] rendererViews,ownedSurfaceViews,presentedSurfaceViews;public int lateNativeMaterials,ownedSurfaceCount;
 }
 // Shared objective content, stage references and ownership observations.
 readonly List<GameObject> objectiveTemplates=new List<GameObject>();
 readonly List<CharacterSpawnCard> objectiveCards=new List<CharacterSpawnCard>();
 readonly List<UnityEngine.Object> objectiveResources=new List<UnityEngine.Object>();
 TeleporterInteraction worldTeleporter;
 GameObject objectiveHost;
 ResourceLocationMap objectiveLocator;
 bool ownsObjectiveIndicator;
 DirectorCardCategorySelection objectiveBossDeck;
 bool objectiveSubscribed;
 ResourceLocationBase objectiveBundleLocation;
 AsyncOperationHandle<IAssetBundleResource> objectiveBundlePreload;
 AsyncOperationHandle<GameObject>[] objectiveSupportLeases;
 GameObject[] objectiveSupportSources;
 readonly List<GameObject> objectiveSupportInstances=new List<GameObject>();
 GameObject objectiveStageHost;
 Stage objectiveStage;
 TeleporterWorldSession teleporterWorldSession;
 TeleporterWorldSession GetTeleporterWorldSession(){if(teleporterWorldSession==null)teleporterWorldSession=new TeleporterWorldSession(this);return teleporterWorldSession;}
 IEnumerator PreloadObjectiveBundle(){return GetTeleporterWorldSession().PreloadObjectiveBundle();}
 void ReleaseObjectiveBundlePreload(){GetTeleporterWorldSession().ReleaseObjectiveBundlePreload();}
 EffectDef[] ObjectiveEffects(SessionConfig cfg){return GetTeleporterWorldSession().ObjectiveEffects(cfg);}
 void PresentRegisteredNativeEffects(){GetTeleporterWorldSession().PresentRegisteredNativeEffects();}
 void CleanupObjectiveEffects(){GetTeleporterWorldSession().CleanupObjectiveEffects();}
 void QueueObjectiveDirectorActor(GameObject obj){GetTeleporterWorldSession().QueueObjectiveDirectorActor(obj);}
 void FlushObjectiveActors(){GetTeleporterWorldSession().FlushObjectiveActors();}
 void PrepareObjectivePresentationSources(){GetTeleporterWorldSession().PrepareObjectivePresentationSources();}
 BuffDef[] ObjectiveBuffs(SessionConfig cfg){return GetTeleporterWorldSession().ObjectiveBuffs(cfg);}
 IEnumerator PrepareObjectiveSupport(SessionConfig cfg){return GetTeleporterWorldSession().PrepareObjectiveSupport(cfg);}
 void ObserveObjectiveSupport(bool force=false){GetTeleporterWorldSession().ObserveObjectiveSupport(force);}
 void CleanupObjectiveSupport(){GetTeleporterWorldSession().CleanupObjectiveSupport();}
 void ReleaseObjectiveOrbCache(){GetTeleporterWorldSession().ReleaseObjectiveOrbCache();}
 PickupDropTable ObjectiveDropTable(PickupDropTable source){return GetTeleporterWorldSession().ObjectiveDropTable(source);}
 ArtifactDef[] ObjectiveArtifacts(SessionConfig cfg){return GetTeleporterWorldSession().ObjectiveArtifacts(cfg);}
 Type[] ObjectiveTypes(SessionConfig cfg){return GetTeleporterWorldSession().ObjectiveTypes(cfg);}
 EntityStateConfiguration[] PrepareObjectiveConfigs(SessionConfig cfg){return GetTeleporterWorldSession().PrepareObjectiveConfigs(cfg);}
 void PrepareObjectiveActorTemplates(SessionConfig cfg){GetTeleporterWorldSession().PrepareObjectiveActorTemplates(cfg);}
 bool IsObjectiveActor(CharacterBody body){return GetTeleporterWorldSession().IsObjectiveActor(body);}
 void PrepareObjectiveRuleCatalog(){GetTeleporterWorldSession().PrepareObjectiveRuleCatalog();}
 void PrepareOriginalGameModes(){GetTeleporterWorldSession().PrepareOriginalGameModes();}
 void CleanupOriginalGameModes(){GetTeleporterWorldSession().CleanupOriginalGameModes();}
 void PrepareObjectiveRules(){GetTeleporterWorldSession().PrepareObjectiveRules();}
 IEnumerator PrepareTeleporterWorld(SessionConfig cfg){return GetTeleporterWorldSession().PrepareTeleporterWorld(cfg);}
 IEnumerator SpawnStageObjective(SessionConfig cfg){return GetTeleporterWorldSession().SpawnStageObjective(cfg);}
 void ObserveTeleporterWorld(){GetTeleporterWorldSession().ObserveTeleporterWorld();}
 ObjectiveRendererObservation ObserveOwnedSurface(Renderer renderer){return GetTeleporterWorldSession().ObserveOwnedSurface(renderer);}
 SurfaceMaterialObservation ObserveSurfaceMaterial(Material material){return GetTeleporterWorldSession().ObserveSurfaceMaterial(material);}
 IEnumerable<GenericPickupController> GrantableWorldPickups(CharacterBody player,bool includeEquipment=false){return GetTeleporterWorldSession().GrantableWorldPickups(player,includeEquipment);}
 bool ObjectiveWorldStimulus(CharacterBody player,NovaInputBridge bridge,float elapsed){return GetTeleporterWorldSession().ObjectiveWorldStimulus(player,bridge,elapsed);}
 bool DefendWorldApproach(CharacterBody player,NovaInputBridge bridge,GameObject target,float elapsed){return GetTeleporterWorldSession().DefendWorldApproach(player,bridge,target,elapsed);}
 void ObjectiveCombatInput(CharacterBody player,NovaInputBridge bridge,float elapsed,Vector2 planar,bool constrainToHoldout=true){GetTeleporterWorldSession().ObjectiveCombatInput(player,bridge,elapsed,planar,constrainToHoldout);}
 Vector3 WorldCombatAimPoint(CharacterBody target,Vector3 origin,out bool visible){return GetTeleporterWorldSession().WorldCombatAimPoint(target,origin,out visible);}
 void SelectCombatMotion(CharacterBody player,NovaInputBridge bridge,Vector2 desired,DirectorActor[] threats,bool escape){GetTeleporterWorldSession().SelectCombatMotion(player,bridge,desired,threats,escape);}
 void CleanupTeleporterWorld(){GetTeleporterWorldSession().Dispose();}
 void CleanupObjectiveConfigs(){GetTeleporterWorldSession().CleanupObjectiveConfigs();}

 // Create on first use and retain for partial setup, repeated cleanup and later
 // observations. Dispose preserves teleporter teardown; preload/config releases stay separate.
 sealed class TeleporterWorldSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  readonly List<EntityStateConfiguration> objectiveConfigs=new List<EntityStateConfiguration>();
  readonly Dictionary<FieldInfo,object> objectiveStaticFields=new Dictionary<FieldInfo,object>();
  TMPro.TMP_Settings objectiveTMPSettings;
  AsyncOperationHandle<TMPro.TMP_Settings> objectiveTMPLease;
  bool ownsObjectiveTMP;
  object priorObjectiveTMP;
  FieldInfo objectiveTMPField;
  GameObject objectiveIndicatorSource;
  AsyncOperationHandle<GameObject> objectiveIndicatorLease;
  int objectiveIndicatorReferences,objectiveIndicatorConsumers;
  Action<MasterSummon.MasterSummonReport> objectiveSummon;
  Action<BossGroup> objectiveDefeated;
  Action<SceneExitController> objectiveBeginExit,objectiveFinishExit;
  string objectiveState;
  float objectiveRewardApproachAt=-1;
  GameObject[] objectiveEffectSources;
  string[] deferredObjectiveEffectPaths;
  bool ownsObjectiveBundlePreload;
  readonly List<CharacterMaster> pendingObjectiveActors=new List<CharacterMaster>();
  readonly Dictionary<CharacterMaster,int> objectiveAmbientExpected=new Dictionary<CharacterMaster,int>();
  readonly HashSet<CharacterMaster> objectiveDirectorActors=new HashSet<CharacterMaster>();
  GameObject objectiveOrbHost,objectiveProjectileTemplates;
  bool ownsObjectiveOrbEffects;
  static bool objectiveHoldoutInitialized;
  readonly Dictionary<PickupDropTable,PickupDropTable> objectiveDropTables=new Dictionary<PickupDropTable,PickupDropTable>();
  Collider objectiveBeacon;
  GameObject[] priorGameModeContent;
  ResourceAvailability priorGameModeAvailability;
  bool ownsGameModeCatalog;
  static string objectiveRuleSignature;
  public TeleporterWorldSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public IEnumerator PreloadObjectiveBundle(){
   coordinator.Check(!ownsObjectiveBundlePreload,"Unowned objective bundle preload");
   var providers=Addressables.ResourceManager.ResourceProviders;if(!providers.Any(x=>x is AssetBundleProvider))providers.Add(new AssetBundleProvider());
   coordinator.objectiveBundleLocation=new ResourceLocationBase("objective-support-lab",System.IO.Path.Combine(Application.persistentDataPath,"payload","objective-support-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));coordinator.objectiveBundleLocation.Data=new AssetBundleRequestOptions{BundleName="objective-support-lab"};
   coordinator.objectiveBundlePreload=Addressables.ResourceManager.ProvideResource<IAssetBundleResource>(coordinator.objectiveBundleLocation);ownsObjectiveBundlePreload=true;yield return coordinator.objectiveBundlePreload;
   coordinator.Check(coordinator.objectiveBundlePreload.Status==AsyncOperationStatus.Succeeded&&coordinator.objectiveBundlePreload.Result!=null&&coordinator.objectiveBundlePreload.Result.GetAssetBundle(),"Original shared-support bundle container failed before prefab deserialization");
   // Attribute the current Android-only binding failure before bulk shared-asset deserialization.
   var cfg=JsonUtility.FromJson<SessionConfig>(Resources.Load<TextAsset>("MovementBatchProbe").text);
   var ward=coordinator.objectiveBundlePreload.Result.GetAssetBundle().LoadAsset<GameObject>(cfg.objectiveSupportAssets[1]);
   var missing=ward?ward.GetComponentsInChildren<Transform>(true).Where(child=>child.GetComponents<Component>().Any(component=>!component)).Select(child=>child.name).ToArray():new[]{"prefab absent"};
   coordinator.Check(ward&&missing.Length==0,"Preloaded original ward script binding failed: "+string.Join(",",missing));
  }
  public void ReleaseObjectiveBundlePreload(){if(ownsObjectiveBundlePreload){if(coordinator.objectiveBundlePreload.IsValid())Addressables.Release(coordinator.objectiveBundlePreload);ownsObjectiveBundlePreload=false;coordinator.objectiveBundleLocation=null;}}
  public EffectDef[] ObjectiveEffects(SessionConfig cfg){
   var shared=new HashSet<string>(cfg.objectiveSupportAssets??new string[0],StringComparer.OrdinalIgnoreCase);
   var effects=new HashSet<string>(cfg.objectiveEffectAssets,StringComparer.OrdinalIgnoreCase);
   deferredObjectiveEffectPaths=(cfg.objectiveSupportAssets??new string[0]).Where(effects.Contains).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
   var characterPaths=cfg.objectiveEffectAssets.Where(x=>!shared.Contains(x)).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
   objectiveEffectSources=characterPaths.Select(x=>coordinator.artifactBundle.LoadAsset<GameObject>(x)).ToArray();
   coordinator.r.rewards.characterEffects=characterPaths;coordinator.r.rewards.deferredEffects=deferredObjectiveEffectPaths;coordinator.r.rewards.supportBundlePreloaded=ownsObjectiveBundlePreload;coordinator.Save();
   for(int i=0;i<objectiveEffectSources.Length;i++)coordinator.Check(objectiveEffectSources[i]&&objectiveEffectSources[i].GetComponent<EffectComponent>(),"Original character-bundle effect missing: "+characterPaths[i]);
   foreach(var source in objectiveEffectSources)source.GetComponent<EffectComponent>().soundName=null;return objectiveEffectSources.Select(x=>new EffectDef(x)).ToArray();
  }
  public void PresentRegisteredNativeEffects(){
   // Only registered, owned effect sources are adapted before their native pool
   // instantiates them. Retain the original arrays for existing scoped teardown.
   var entries=(EffectDef[])MovementBatchProbe.RewardField(typeof(EffectCatalog),"entries").GetValue(null);
   foreach(var renderer in entries.Where(x=>x!=null&&x.prefabEffectComponent&&x.prefab).SelectMany(x=>x.prefab.GetComponentsInChildren<Renderer>(true)).Distinct()){
    if(coordinator.worldLootSourceMaterials.ContainsKey(renderer))continue;
    var originals=renderer.sharedMaterials;var copies=(Material[])originals.Clone();bool changed=false;
    for(int i=0;i<originals.Length;i++){
     var original=originals[i];if(!original)continue;var copy=new Material(original);
     if(!AndroidNativeDeferredPresentation.Apply(original,copy)){Destroy(copy);continue;}
     copies[i]=copy;coordinator.worldMaterials.Add(copy);coordinator.r.world.nativeEffectSourceMaterials++;changed=true;
    }
    if(changed){coordinator.worldLootSourceMaterials.Add(renderer,originals);renderer.sharedMaterials=copies;coordinator.r.world.nativeEffectSourceRenderers++;}
   }
  }
  public void CleanupObjectiveEffects(){
   if(objectiveEffectSources==null)return;var pools=(Dictionary<GameObject,EffectPool>)MovementBatchProbe.RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);var cache=(IDictionary)MovementBatchProbe.RewardField(typeof(EffectManager),"_ShouldUsePooledEffectMap").GetValue(null);
   foreach(var source in objectiveEffectSources.Where(x=>x)){EffectPool pool;if(pools.TryGetValue(source,out pool)){foreach(var effect in pool.InUse.ToArray())pool.ReturnObject(effect);EffectManager.ClearPool(source);pool.Kill();}cache.Remove(source);}
  }
  public void QueueObjectiveDirectorActor(GameObject obj){var master=obj.GetComponent<CharacterMaster>();if(master)objectiveDirectorActors.Add(master);}
  public void FlushObjectiveActors(){
   foreach(var master in pendingObjectiveActors.ToArray()){
    pendingObjectiveActors.Remove(master);if(!master)continue;
    coordinator.RecordDirectorActor(master.gameObject,coordinator.enemyPlayer,coordinator.IsWorldItemGhost(master)?"item-ghost":coordinator.stageCombatActors.Contains(master)?"stage-director":objectiveDirectorActors.Contains(master)?"teleporter-director":master.bodyPrefab.name.StartsWith("Lunar",StringComparison.Ordinal)||master.bodyPrefab.name.StartsWith("Brother",StringComparison.Ordinal)?"moon-encounter":"queen-summon",objectiveAmbientExpected[master]);objectiveAmbientExpected.Remove(master);
    if(coordinator.IsWorldItemGhost(master))continue;if(objectiveDirectorActors.Contains(master))coordinator.r.objective.bossSpawns++;else coordinator.r.objective.normalSpawns++;
   }
  }
  public void PrepareObjectivePresentationSources(){
   // These are owned converted Android prefab assets in memory, never the original input.
   // Remove native-audio components before cloning or EffectManagerHelper caches Ak callbacks.
   foreach(var source in coordinator.artifactBundle.LoadAllAssets<GameObject>())foreach(var component in source.GetComponentsInChildren<MonoBehaviour>(true))
    if(component&&component.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(component,true);coordinator.r.objective.silentSourceComponents++;}
  }
  public BuffDef[] ObjectiveBuffs(SessionConfig cfg){
   if(!cfg.teleporterLoop)return new BuffDef[0];var def=coordinator.artifactBundle.LoadAsset<BuffDef>(cfg.objectiveWardBuffAsset);coordinator.Check(def&&def.name=="bdBeetleJuice","Original Queen ward buff missing");coordinator.BindEnemyDefinition(typeof(RoR2Content.Buffs),"BeetleJuice",def);return new[]{def};
  }
  public IEnumerator PrepareObjectiveSupport(SessionConfig cfg){
   coordinator.Check(!OrbManager.instance,"Unowned original orb manager");
   coordinator.Check(ownsObjectiveBundlePreload&&coordinator.objectiveBundleLocation!=null,"Shared-support bundle must be loaded before character assets");var bundle=coordinator.objectiveBundleLocation;
   coordinator.objectiveSupportLeases=new AsyncOperationHandle<GameObject>[cfg.objectiveSupportAssets.Length];coordinator.objectiveSupportSources=new GameObject[cfg.objectiveSupportAssets.Length];
   for(int i=0;i<cfg.objectiveSupportAssets.Length;i++){
    string key;coordinator.Check(LegacyResourcesAPI.GetGuid(cfg.objectiveSupportPaths[i],out key)&&key==cfg.objectiveSupportKeys[i],"Original Queen/exit legacy identity changed");
    coordinator.objectiveLocator.Add(key,new ResourceLocationBase(key,cfg.objectiveSupportAssets[i],typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));
    coordinator.objectiveSupportLeases[i]=LegacyResourcesAPI.LoadAsync<GameObject>(cfg.objectiveSupportPaths[i]);yield return coordinator.objectiveSupportLeases[i];coordinator.objectiveSupportSources[i]=coordinator.objectiveSupportLeases[i].Result;
    coordinator.Check(coordinator.objectiveSupportSources[i]&&coordinator.objectiveSupportSources[i].GetComponentsInChildren<Component>(true).All(x=>x),"Original objective support serialization missing: "+cfg.objectiveSupportPaths[i]+" / "+coordinator.objectiveSupportLeases[i].Status);
   }
   coordinator.PrepareMoonSupport(cfg);coordinator.PrepareStagePopulationSupport(cfg);var bossSupport=coordinator.PrepareStageBossContent(cfg);while(bossSupport.MoveNext())yield return bossSupport.Current;
   var wholeItemSupport=coordinator.PrepareWholeItemBehaviorSupport(cfg);while(wholeItemSupport.MoveNext())yield return wholeItemSupport.Current;
   coordinator.PrepareSourceTemporaryVisuals();
   var coreLootEffects=coordinator.PrepareWorldLootSupport(cfg).Concat(coordinator.PrepareWorldEquipmentSupport(cfg)).Concat(coordinator.PrepareWorldProcSupport(cfg)).Concat(coordinator.PrepareWorldDotSupport(cfg)).Concat(coordinator.PrepareWorldItemBehaviorSupport(cfg)).Concat(coordinator.WholeItemBehaviorEffects()).ToArray();
   var commerceEffect=coordinator.PrepareCommerceSupport(cfg);
   var ward=coordinator.objectiveSupportSources[1];var wardModel=ward.GetComponent<ModelLocator>().modelTransform;var wardSkin=wardModel.GetComponent<ModelSkinController>();var wardAnimator=wardModel.GetComponent<Animator>();
   coordinator.Check(wardSkin&&wardAnimator&&cfg.objectiveWardVisualAssets.Length==5,"Original ward visual contract missing");
   wardSkin._animatorController=coordinator.artifactBundle.LoadAsset<RuntimeAnimatorController>(cfg.objectiveWardVisualAssets[0]);wardSkin._avatar=coordinator.artifactBundle.LoadAsset<Avatar>(cfg.objectiveWardVisualAssets[1]);
   typeof(ModelSkinController).GetField("_animatorControllerAddress",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(wardSkin,new AssetReferenceT<RuntimeAnimatorController>(""));
   typeof(ModelSkinController).GetField("_avatarAddress",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(wardSkin,new AssetReferenceT<Avatar>(""));
   wardAnimator.runtimeAnimatorController=wardSkin._animatorController;wardAnimator.avatar=wardSkin._avatar;coordinator.Check(wardAnimator.avatar&&wardAnimator.runtimeAnimatorController,"Original ward animation source missing");
   var wardMesh=coordinator.artifactBundle.LoadAsset<Mesh>(cfg.objectiveWardVisualAssets[2]);var wardRenderer=wardModel.GetComponentInChildren<SkinnedMeshRenderer>(true);coordinator.Check(wardMesh&&wardRenderer&&wardMesh.bindposes.Length==wardRenderer.bones.Length,"Original ward mesh binding absent");wardRenderer.sharedMesh=wardMesh;
   foreach(var renderer in wardModel.GetComponentsInChildren<Renderer>(true)){var material=Instantiate(coordinator.artifactBundle.LoadAsset<Material>(cfg.objectiveWardVisualAssets[renderer is SkinnedMeshRenderer?3:4]));material.shader=Resources.Load<Shader>("CommandoMaterialPreview");material.shaderKeywords=new string[0];coordinator.objectiveResources.Add(material);renderer.sharedMaterial=material;renderer.gameObject.layer=30;}
   foreach(var behaviour in ward.GetComponentsInChildren<MonoBehaviour>(true)){
    if(behaviour is RoR2.Networking.CharacterNetworkTransform||behaviour is InteractionDriver||behaviour is EquipmentSlot)behaviour.enabled=false;
    if(behaviour.transform!=ward.transform)behaviour.enabled=behaviour is HurtBox||behaviour is HurtBoxGroup||behaviour is HitBox||behaviour is HitBoxGroup||behaviour is RootMotionAccumulator||behaviour is AnimationEvents;
   }
   foreach(var locator in ward.GetComponentsInChildren<SfxLocator>(true))foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Public|BindingFlags.Instance))if(field.FieldType==typeof(string))field.SetValue(locator,null);
   var supportEffects=new[]{coordinator.objectiveSupportSources[0],coordinator.objectiveSupportSources[3]}.Concat(coordinator.moonTransferEffect?new[]{coordinator.moonTransferEffect}:new GameObject[0]).Concat(coreLootEffects).Concat(commerceEffect?new[]{commerceEffect}:new GameObject[0]).ToArray();foreach(var source in supportEffects)source.GetComponent<EffectComponent>().soundName=null;objectiveEffectSources=objectiveEffectSources.Concat(supportEffects).Distinct().ToArray();
   coordinator.RegisterComposedEffects(supportEffects.Select(x=>new EffectDef(x)));
   PresentRegisteredNativeEffects();
   foreach(var path in deferredObjectiveEffectPaths){int index=Array.IndexOf(cfg.objectiveSupportAssets,path);coordinator.Check(index>=0&&supportEffects.Contains(coordinator.objectiveSupportSources[index])&&EffectCatalog.FindEffectIndexFromPrefab(coordinator.objectiveSupportSources[index])!=EffectIndex.Invalid,"Deferred original support effect was not registered: "+path);}
   coordinator.r.rewards.registeredDeferredEffects=deferredObjectiveEffectPaths;coordinator.Save();
   coordinator.Check(!OrbEffectSingleton.instance&&OrbEffectSingleton.numPnts==0,"Unowned original orb visual context");
   objectiveOrbHost=new GameObject("Owned original Queen orb manager");objectiveOrbHost.AddComponent<OrbManager>();objectiveOrbHost.AddComponent<OrbEffectSingleton>();ownsObjectiveOrbEffects=true;coordinator.Check(OrbManager.instance&&OrbEffectSingleton.instance,"Original Queen orb context missing");
  }
  public void ObserveObjectiveSupport(bool force=false){
   if(!force&&Time.frameCount%30!=0)return;
   if(coordinator.objectiveSupportSources==null)return;
   // Both support sources are native networked objects. Normal observation can
   // use the server's spawned identities; teardown still sweeps inactive scenes.
   var instances=force?Resources.FindObjectsOfTypeAll<GameObject>():NetworkServer.objects.Values.Where(x=>x).Select(x=>x.gameObject).ToArray();
   foreach(var source in coordinator.objectiveSupportSources.Skip(1).Take(2).Where(source=>source))foreach(var instance in instances.Where(x=>x&&x.scene.IsValid()&&x.name==source.name+"(Clone)"))if(!coordinator.objectiveSupportInstances.Contains(instance))coordinator.objectiveSupportInstances.Add(instance);
  }
  public void CleanupObjectiveSupport(){
   coordinator.CleanupWorldLootSupport();
   coordinator.CleanupMoonSupport();
   if(objectiveOrbHost)Destroy(objectiveOrbHost);if(ownsObjectiveOrbEffects){OrbEffectSingleton.instance=null;OrbEffectSingleton.orbEffectArray=null;OrbEffectSingleton.numPnts=0;ownsObjectiveOrbEffects=false;}foreach(var instance in coordinator.objectiveSupportInstances)if(instance)NetworkServer.Destroy(instance);
   ReleaseObjectiveOrbCache();
   if(coordinator.objectiveSupportLeases!=null)foreach(var lease in coordinator.objectiveSupportLeases)if(lease.IsValid())Addressables.Release(lease);
  }
  public void ReleaseObjectiveOrbCache(){
   var cache=(IDictionary)typeof(OrbStorageUtility).GetField("_orbDictionary",BindingFlags.Static|BindingFlags.NonPublic).GetValue(null);
   foreach(var source in new[]{"Prefabs/Effects/OrbEffects/BeetleWardOrbEffect","Prefabs/NetworkedObjects/BeetleWard","Prefabs/Effects/OrbEffects/LightningOrbEffect"})if(cache.Contains(source)){var prefab=cache[source] as GameObject;cache.Remove(source);if(prefab)Addressables.Release(prefab);}
  }
  public PickupDropTable ObjectiveDropTable(PickupDropTable source){
   if(!source||coordinator.UnavailableBossRewardTable(source))return null;PickupDropTable copy;if(objectiveDropTables.TryGetValue(source,out copy))return copy;
   copy=Instantiate(source);copy.name=source.name;objectiveDropTables.Add(source,copy);coordinator.objectiveResources.Add(copy);return copy;
  }
  public ArtifactDef[] ObjectiveArtifacts(SessionConfig cfg){
   if(!cfg.teleporterLoop)return new ArtifactDef[0];
   var holders=typeof(ArtifactDef).Assembly.GetTypes().Where(x=>x.Name=="Artifacts"&&x.DeclaringType!=null&&x.DeclaringType.Name.EndsWith("Content",StringComparison.Ordinal)).ToArray();
   var defs=cfg.objectiveArtifactAssets.Select(x=>coordinator.artifactBundle.LoadAsset<ArtifactDef>(x)).ToArray();coordinator.Check(defs.All(x=>x),"Original objective artifact definitions absent");
   foreach(var def in defs){var fields=holders.Select(x=>x.GetField(def.cachedName)).Where(x=>x!=null&&x.FieldType==typeof(ArtifactDef)).ToArray();coordinator.Check(fields.Length==1,"Original artifact content identity ambiguous: "+def.cachedName);var prior=fields[0].GetValue(null);if(prior==null)coordinator.BindEnemyDefinition(fields[0].DeclaringType,fields[0].Name,def);else coordinator.Check(ReferenceEquals(prior,def),"Original artifact definition drift: "+def.cachedName);}
   return defs;
  }
  public Type[] ObjectiveTypes(SessionConfig cfg){
   if(!cfg.teleporterLoop)return new Type[0];
   var assembly=typeof(TeleporterInteraction).Assembly;
   return assembly.GetTypes().Where(t=>!t.IsAbstract&&typeof(EntityState).IsAssignableFrom(t)&&
    (t.DeclaringType==typeof(TeleporterInteraction)||t.Namespace=="EntityStates.BeetleQueenMonster"||t.Namespace=="EntityStates.BeetleGuardMonster"||
     (cfg.stageCombatDecks!=null&&cfg.stageCombatDecks.Length>0&&new[]{"EntityStates.GolemMonster","EntityStates.LemurianMonster","EntityStates.Wisp1Monster"}.Any(ns=>(t.Namespace??"").StartsWith(ns,StringComparison.Ordinal)))||coordinator.StagePopulationState(t,cfg)||t.Namespace=="EntityStates.LunarTeleporter"||
     (cfg.worldAdditionalLootItems!=null&&((cfg.worldAdditionalLootItems.Contains("TPHealingNova")&&t.Namespace=="EntityStates.TeleporterHealNovaController")||(cfg.worldAdditionalLootItems.Contains("Plant")&&t.DeclaringType==typeof(DeskPlantController))))||
     (cfg.worldAdditionalLootItems!=null&&((cfg.worldAdditionalLootItems.Contains("FallBoots")&&t.Namespace=="EntityStates.Headstompers")||(cfg.worldAdditionalLootItems.Contains("LaserTurbine")&&t.Namespace=="EntityStates.LaserTurbine")))||
     (cfg.moonMission&&(t==typeof(FlyState)||(t.Namespace??"").StartsWith("EntityStates.BrotherMonster",StringComparison.Ordinal)||(t.Namespace??"").StartsWith("EntityStates.LunarGolem",StringComparison.Ordinal)||(t.Namespace??"").StartsWith("EntityStates.LunarWisp",StringComparison.Ordinal)||(t.Namespace??"").StartsWith("EntityStates.LunarExploder",StringComparison.Ordinal)||t.Namespace=="EntityStates.Missions.Moon"||t.Namespace=="EntityStates.Missions.BrotherEncounter"||t.Namespace=="EntityStates.MoonElevator"||t.DeclaringType==typeof(EscapeSequenceController))))).ToArray();
  }
  public EntityStateConfiguration[] PrepareObjectiveConfigs(SessionConfig cfg){
   PrepareObjectivePresentationSources();
   foreach(var type in ObjectiveTypes(cfg))foreach(var field in type.GetFields(BindingFlags.Static|BindingFlags.Public|BindingFlags.DeclaredOnly))if(!field.IsLiteral&&!field.IsInitOnly)objectiveStaticFields[field]=field.GetValue(null);
   foreach(var path in cfg.objectiveConfigAssets){
    var source=coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(path);coordinator.Check(source,"Original objective state config absent: "+path);
    var copy=Instantiate(source);copy.serializedFieldsCollection.serializedFields=source.serializedFieldsCollection.serializedFields.ToArray();
    for(int i=0;i<copy.serializedFieldsCollection.serializedFields.Length;i++){
     var field=copy.serializedFieldsCollection.serializedFields[i];
     var member=((Type)copy.targetType).GetField(field.fieldName);
     if(member!=null&&member.FieldType==typeof(string)&&field.fieldName.IndexOf("sound",StringComparison.OrdinalIgnoreCase)>=0)copy.serializedFieldsCollection.serializedFields[i].fieldValue.stringValue="";
     // Retain genuine effect references: some original animation/state calls are unconditional.
     var projectile=field.fieldValue.objectValue as GameObject;
     if(projectile&&projectile.GetComponent<RoR2.Projectile.ProjectileController>()){
      if(!objectiveProjectileTemplates){objectiveProjectileTemplates=new GameObject("Owned silent objective projectile templates");objectiveProjectileTemplates.SetActive(false);coordinator.objectiveResources.Add(objectiveProjectileTemplates);}
      var owned=Instantiate(projectile,objectiveProjectileTemplates.transform);owned.name=projectile.name;owned.SetActive(true);if(!owned.GetComponent<SilentProjectileBoundary>())owned.AddComponent<SilentProjectileBoundary>();
      foreach(var component in owned.GetComponentsInChildren<MonoBehaviour>(true))foreach(var value in component.GetType().GetFields(BindingFlags.Instance|BindingFlags.Public)){
       if(value.FieldType==typeof(string)&&value.Name.IndexOf("sound",StringComparison.OrdinalIgnoreCase)>=0)value.SetValue(component,null);
       if(value.FieldType==typeof(NetworkSoundEventDef)||value.Name=="flightSoundLoop")value.SetValue(component,null);
      }
      copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue=owned;
     }
    }
    objectiveConfigs.Add(copy);
   }
   return objectiveConfigs.ToArray();
  }
  public void PrepareObjectiveActorTemplates(SessionConfig cfg){
   foreach(var spec in cfg.objectiveActors){
    coordinator.r.phase="objective-template-"+spec.name;coordinator.Save();
    var source=coordinator.artifactBundle.LoadAsset<GameObject>(spec.body);coordinator.Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original objective actor serialization missing: "+spec.name);
    var bodyObject=Instantiate(source,coordinator.enemyTemplates.transform);bodyObject.name=source.name;bodyObject.SetActive(true);coordinator.objectiveTemplates.Add(bodyObject);
    var body=bodyObject.GetComponent<CharacterBody>();var locator=bodyObject.GetComponent<ModelLocator>();coordinator.Check(body&&locator&&locator.modelTransform,"Original objective body/model components absent: "+spec.name);var model=locator.modelTransform;var animator=model.GetComponent<Animator>();coordinator.Check(animator,"Original objective Animator absent: "+spec.name);
    animator.avatar=coordinator.artifactBundle.LoadAsset<Avatar>(spec.avatar);animator.runtimeAnimatorController=coordinator.artifactBundle.LoadAsset<RuntimeAnimatorController>(spec.controller);animator.applyRootMotion=false;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
    coordinator.Check(animator.avatar&&animator.runtimeAnimatorController,"Original objective animation absent: "+spec.name);
    foreach(var behaviour in bodyObject.GetComponentsInChildren<MonoBehaviour>(true)){
     if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(behaviour);continue;}
     var rewards=behaviour as DeathRewards;if(rewards){rewards.logUnlockableDef=null;rewards.bossDropTable=ObjectiveDropTable(rewards.bossDropTable);}
     if(behaviour is RoR2.Networking.CharacterNetworkTransform||behaviour is InteractionDriver||behaviour is EquipmentSlot)behaviour.enabled=false;
     if(behaviour.transform!=bodyObject.transform)behaviour.enabled=behaviour is HurtBox||behaviour is HurtBoxGroup||behaviour is HitBox||behaviour is HitBoxGroup||behaviour is RootMotionAccumulator||behaviour is AnimationEvents;
    }
    var sfx=body.GetComponent<SfxLocator>();coordinator.Check(sfx,"Original objective SfxLocator absent: "+spec.name);foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Public|BindingFlags.Instance))if(field.FieldType==typeof(string))field.SetValue(sfx,null);
    if(spec.bindings!=null&&spec.bindings.Length>0)coordinator.BindMoonActorVisuals(bodyObject,model,spec);
    else{
     var material=Instantiate(coordinator.artifactBundle.LoadAsset<Material>(spec.material));material.shader=Resources.Load<Shader>("CommandoMaterialPreview");material.shaderKeywords=new string[0];material.SetFloat("_EmissionEnabled",0);AndroidMaterialPresentation.Apply(coordinator.artifactBundle.LoadAsset<Material>(spec.material),material);coordinator.objectiveResources.Add(material);
     var skins=model.GetComponentsInChildren<SkinnedMeshRenderer>(true);coordinator.Check(skins.Length==1,"Original objective default renderer contract changed: "+spec.name);var mesh=coordinator.artifactBundle.LoadAsset<Mesh>(spec.mesh);coordinator.Check(mesh&&mesh.vertexCount>0&&mesh.bindposes.Length==skins[0].bones.Length,"Original objective mesh/bind poses absent: "+spec.name);skins[0].sharedMesh=mesh;
     foreach(var renderer in model.GetComponentsInChildren<Renderer>(true)){renderer.gameObject.layer=30;renderer.sharedMaterial=material;var skin=renderer as SkinnedMeshRenderer;if(skin)skin.updateWhenOffscreen=true;}
     var characterModel=model.GetComponent<CharacterModel>();characterModel.visibility=VisibilityLevel.Invisible;
     for(int i=0;i<characterModel.baseRendererInfos.Length;i++)characterModel.baseRendererInfos[i].defaultMaterial=material;
    }
    foreach(var provider in bodyObject.GetComponentsInChildren<SurfaceDefProvider>(true)){var surface=Instantiate(provider.surfaceDef);surface.impactEffectPrefab=null;surface.impactSoundString=null;provider.surfaceDef=surface;coordinator.objectiveResources.Add(surface);}
    coordinator.BindCatalogBodyTemplate(bodyObject);
    var masterSource=coordinator.artifactBundle.LoadAsset<GameObject>(spec.master);var masterObject=Instantiate(masterSource,coordinator.enemyTemplates.transform);masterObject.name=masterSource.name;masterObject.GetComponent<Inventory>().enabled=false;masterObject.GetComponent<CharacterMaster>().bodyPrefab=bodyObject;masterObject.SetActive(true);coordinator.objectiveTemplates.Add(masterObject);
    var cardSource=spec.card==cfg.stageMiniCardAsset?coordinator.objectiveBundlePreload.Result.GetAssetBundle().LoadAsset<CharacterSpawnCard>(spec.card):coordinator.artifactBundle.LoadAsset<CharacterSpawnCard>(spec.card);coordinator.Check(cardSource&&cardSource.prefab&&cardSource.directorCreditCost>=0,"Original objective spawn card absent from its declared bundle owner: "+spec.name);var card=Instantiate(cardSource);card.name=card.name.Replace("(Clone)","");card.prefab=masterObject;coordinator.objectiveCards.Add(card);
   }
   // The original Queen summons a Guard using its configured source card. Redirect only the
   // generated card's prefab boundary to the owned compatible template; retain source settings.
   EntityStates.BeetleQueenMonster.SummonEggs.spawnCard=coordinator.objectiveCards.Single(x=>x.name=="cscBeetleGuard");
   objectiveSummon=report=>{
    if(!report.summonMasterInstance||!(coordinator.objectiveTemplates.Contains(report.masterSummon.masterPrefab)||coordinator.rewardCard&&report.masterSummon.masterPrefab==coordinator.rewardCard.prefab&&coordinator.IsWorldItemGhost(report.summonMasterInstance)))return;
    // Complete-catalog templates include player-owned repairable drones. Their
    // original summons belong to the player-minion observer, not the hostile
    // director actor/reward observer below.
    if(report.summonMasterInstance.teamIndex==TeamIndex.Player&&!coordinator.IsWorldItemGhost(report.summonMasterInstance))return;
    var master=report.summonMasterInstance;coordinator.BindMoonBodySupport(master.GetBody());coordinator.ownedRewardSummons.Add(master);pendingObjectiveActors.Add(master);
    var summoner=report.masterSummon.summonerBodyObject?report.masterSummon.summonerBodyObject.GetComponent<CharacterBody>():null;
    objectiveAmbientExpected[master]=1+(summoner&&summoner.inventory?summoner.inventory.GetItemCountEffective(RoR2Content.Items.UseAmbientLevel):0);
    // MasterSummon publishes before CombatDirector assigns cost, rewards and squad.
    // Observation must never interrupt the original spawn transaction.
   };
   MasterSummon.onServerMasterSummonGlobal+=objectiveSummon;
  }
  public bool IsObjectiveActor(CharacterBody body){return body&&coordinator.objectiveTemplates.Any(x=>x==body.master.bodyPrefab);}
  public void PrepareObjectiveRuleCatalog(){
   // RuleCatalog/RuleBook cache definitions for the process. Restart may reuse this exact
   // catalog signature, but cannot rebuild it while cached RuleBook rule references survive.
   var signature=string.Join("|",ItemCatalog.allItemDefs.Select(x=>x.name))+"/"+string.Join("|",Enumerable.Range(0,EquipmentCatalog.equipmentCount).Select(x=>EquipmentCatalog.GetEquipmentDef((EquipmentIndex)x).name))+"/"+string.Join("|",DroneCatalog.allDroneDefs.Select(x=>x.name))+"/"+string.Join("|",KeyItemCatalog.allKeyItemDefs.Select(x=>x.name));
   if(objectiveRuleSignature==null){
    coordinator.Check(RuleCatalog.ruleCount==0,"Unowned original rules");
    // FromKarma captures native unlock references. Gather only that metadata;
    // KarmaManager.Init would also start unrelated prefab/Run lifecycle work.
    var priorKarmaUnlocks=KarmaManager.startingKarmaUnlockables;
    try{
     if(coordinator.androidProgression!=null){coordinator.Check(priorKarmaUnlocks!=null&&priorKarmaUnlocks.Count==0,"Unowned Karma unlock metadata");KarmaManager.startingKarmaUnlockables=new List<UnlockableDef>();MovementBatchProbe.StaticCall(typeof(KarmaManager),"GatherStartingKarmaUnlockables");coordinator.Check(KarmaManager.startingKarmaUnlockables.All(def=>!def||UnlockableCatalog.GetUnlockableDef(def.cachedName)==def),"Original Karma rule unlock metadata identity differs");}
     MovementBatchProbe.StaticCall(typeof(RuleCatalog),"Init");MovementBatchProbe.StaticCall(typeof(RuleBook),"Init");objectiveRuleSignature=signature;
    }finally{KarmaManager.startingKarmaUnlockables=priorKarmaUnlocks;}
   }
   coordinator.Check(objectiveRuleSignature==signature&&RuleCatalog.FindRuleDef("Misc.StageOrder")!=null,"Restart rule catalog input changed");
   PrepareOriginalGameModes();
  }
  public void PrepareOriginalGameModes(){
   if(coordinator.r.liveCatalogs==null||!coordinator.stageSourceObjects||ownsGameModeCatalog)return;
   coordinator.Check(GameModeCatalog.gameModeCount==0,"Unowned original game-mode catalog");
   var modes=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.gameMode,Array.Empty<GameObject>());
   coordinator.Check(modes.Length>0&&modes.All(mode=>mode&&mode.GetComponent<Run>())&&modes.Select(mode=>mode.name).Distinct().Count()==modes.Length,"Original game-mode prefab family changed");
   priorGameModeContent=ContentManager._gameModePrefabs;priorGameModeAvailability=GameModeCatalog.availability;
   coordinator.Check(priorGameModeContent==null||priorGameModeContent.Length==0,"Unowned game-mode content array");
   ContentManager._gameModePrefabs=modes;ownsGameModeCatalog=true;
   MovementBatchProbe.StaticCall(typeof(GameModeCatalog),"LoadGameModes");
   var classic=GameModeCatalog.FindGameModePrefabComponent("ClassicRun");
   coordinator.Check(GameModeCatalog.gameModeCount==modes.Length&&classic&&classic.gameObject==modes.Single(mode=>mode.name=="ClassicRun")&&classic!=Run.instance,"Original ClassicRun catalog identity differs");
  }
  public void CleanupOriginalGameModes(){
   if(!ownsGameModeCatalog)return;
   MovementBatchProbe.StaticCall(typeof(GameModeCatalog),"SetGameModes",new object[]{Array.Empty<Run>()});
   ContentManager._gameModePrefabs=priorGameModeContent;GameModeCatalog.availability=priorGameModeAvailability;ownsGameModeCatalog=false;
   coordinator.Check(GameModeCatalog.gameModeCount==0&&!GameModeCatalog.FindGameModePrefabComponent("ClassicRun"),"Original game-mode catalog outlived its owned bundle");
  }
  public void PrepareObjectiveRules(){
   PrepareObjectiveRuleCatalog();
   var run=Run.instance;var networkBook=run.GetComponent<NetworkRuleBook>();coordinator.Check(networkBook,"Original Run rule component absent");
   if(networkBook.ruleBook==null)MovementBatchProbe.Call(networkBook,"Awake");
   typeof(Run).GetField("networkRuleBookComponent",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(run,networkBook);
   var selected=coordinator.SelectedOfflineDifficulty();var rule=RuleCatalog.FindChoiceDef("Difficulty."+selected);coordinator.Check(rule!=null,"Selected original difficulty rule missing: "+selected);run.ruleBook.ApplyChoice(rule);coordinator.Check(run.ruleBook.FindDifficulty()==selected&&run.selectedDifficulty==selected,"Original chosen difficulty mismatch");coordinator.r.objective.difficulty=selected.ToString();
   coordinator.Check(run.ruleBook.stageOrder==StageOrder.Normal&&!run.ruleBook.keepMoneyBetweenStages,"Original default stage-order/money rules changed");
   coordinator.RefreshRewardEquipmentMask(true);
   coordinator.RefreshWholeRunAvailability();
   if(coordinator.worldChestTable){
    // The owned table was first generated before native rules and earned profile
    // unlocks populated Run availability. Rebuild it from the source lists now.
    var expected=coordinator.worldLootDefinitions.Select(item=>PickupCatalog.FindPickupIndex(item.itemIndex)).OrderBy(index=>index.value).ToArray();
    var available=run.availableTier1DropList.Concat(run.availableTier2DropList).Concat(run.availableTier3DropList).OrderBy(index=>index.value).ToArray();
    coordinator.Check(expected.SequenceEqual(available),"Original unlocked tier lists differ from the Android profile's eligible loot");
    coordinator.worldChestTable.RegenerateDropTable(run);
    coordinator.r.world.lootTier1=run.availableTier1DropList.Count;coordinator.r.world.lootTier2=run.availableTier2DropList.Count;coordinator.r.world.lootTier3=run.availableTier3DropList.Count;
    coordinator.r.world.lootDomain=coordinator.worldChestTable.GetPickupCount();
    coordinator.Check(coordinator.r.world.lootDomain==expected.Length,"Original chest table missed an earned eligible item");
   }
   if(coordinator.r.moonCatalog!=null){var lunar=RoR2Content.Equipment.AffixLunar;coordinator.Check(lunar&&EquipmentCatalog.GetEquipmentDef(lunar.equipmentIndex)==lunar&&!lunar.requiredExpansion&&!run.IsEquipmentExpansionLocked(lunar.equipmentIndex),"Original base Lunar equipment availability failed");}
   coordinator.Check(run.runRNG!=null&&run.loopRngGenerator!=null&&run.nextStageRng!=null&&run.bossRewardRng!=null,"Original Run random streams absent");coordinator.r.objective.rules=true;coordinator.r.objective.ruleCount=RuleCatalog.ruleCount;
  }
  public IEnumerator PrepareTeleporterWorld(SessionConfig cfg){
   coordinator.r.phase="integrated-teleporter-context";coordinator.Save();PrepareObjectiveRules();
   // Rules refresh the loaded profile's earned Run unlock sets before native
   // DirectorCard.IsAvailable filters this first stage's population. Do not reroll.
   if(coordinator.r.liveCatalogs!=null&&coordinator.currentStageCombatDeck==null)coordinator.SelectStageCombatDeck(cfg,coordinator.stageGeometryScene.name);
   var bundle=new ResourceLocationBase("teleporter-indicator-lab",System.IO.Path.Combine(Application.persistentDataPath,"payload","teleporter-indicator-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));bundle.Data=new AssetBundleRequestOptions{BundleName="teleporter-indicator-lab"};
   coordinator.objectiveLocator=new ResourceLocationMap("composed-teleporter");coordinator.objectiveLocator.Add(cfg.teleporterIndicatorKey,new ResourceLocationBase(cfg.teleporterIndicatorKey,cfg.teleporterIndicatorAsset,typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));Addressables.AddResourceLocator(coordinator.objectiveLocator);
   var uiBundle=new ResourceLocationBase("objective-ui-lab",System.IO.Path.Combine(Application.persistentDataPath,"payload","objective-ui-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));uiBundle.Data=new AssetBundleRequestOptions{BundleName="objective-ui-lab"};
   coordinator.objectiveLocator.Add(cfg.objectiveTMPSettingsKey,new ResourceLocationBase(cfg.objectiveTMPSettingsKey,cfg.objectiveTMPSettingsAsset,typeof(BundledAssetProvider).FullName,typeof(TMPro.TMP_Settings),uiBundle));
   objectiveTMPField=typeof(TMPro.TMP_Settings).GetField("s_Instance",BindingFlags.Static|BindingFlags.NonPublic);priorObjectiveTMP=objectiveTMPField.GetValue(null);coordinator.Check(priorObjectiveTMP==null||(coordinator.ownsRecoveredText&&priorObjectiveTMP==coordinator.recoveredTextSettings),"Unowned original text settings");
   objectiveTMPLease=LegacyResourcesAPI.LoadAsync<TMPro.TMP_Settings>("TMP Settings");ownsObjectiveTMP=true;yield return objectiveTMPLease;objectiveTMPSettings=objectiveTMPLease.Result;coordinator.Check(objectiveTMPSettings,"Original text settings source missing");
   objectiveTMPField.SetValue(null,objectiveTMPSettings);coordinator.Check(TMPro.TMP_Settings.defaultStyleSheet&&TMPro.TMP_Settings.defaultFontAsset,"Original text settings style/font closure missing");
   var support=PrepareObjectiveSupport(cfg);while(support.MoveNext())yield return support.Current;
   // Recover the source indicator through the original provider before TeleporterInteraction.Awake.
   objectiveIndicatorLease=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/PositionIndicators/TeleporterChargingPositionIndicator");coordinator.ownsObjectiveIndicator=true;yield return objectiveIndicatorLease;objectiveIndicatorSource=objectiveIndicatorLease.Result;coordinator.Check(objectiveIndicatorSource,"Original charging indicator source absent");foreach(var text in objectiveIndicatorSource.GetComponentsInChildren<TMPro.TMP_Text>(true))text.enabled=false;objectiveIndicatorReferences=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveIndicatorLease);
   if(!objectiveHoldoutInitialized){MovementBatchProbe.StaticCall(typeof(HoldoutZoneController),"Init");objectiveHoldoutInitialized=true;}
   coordinator.PrepareStageTransport(cfg);coordinator.EnableStageMapZones();var spawn=SpawnStageObjective(cfg);while(spawn.MoveNext())yield return spawn.Current;
  }
  public IEnumerator SpawnStageObjective(SessionConfig cfg){
   coordinator.r.objective=new ObjectiveReport{rules=true,ruleCount=RuleCatalog.ruleCount,difficulty=coordinator.SelectedOfflineDifficulty().ToString(),scope="Original teleporter combat/holdout/rewards/exit; Android layout/context/presentation. Optional reward collection is recorded separately. No skipped combat, forced charge, currency or platform success."};objectiveState=null;objectiveRewardApproachAt=-1;
   coordinator.Check(!Stage.instance,"Unowned stage lifecycle");coordinator.objectiveStageHost=new GameObject("Owned Android stage coordinator");coordinator.objectiveStageHost.SetActive(false);coordinator.objectiveStageHost.AddComponent<NetworkIdentity>();coordinator.objectiveStage=coordinator.objectiveStageHost.AddComponent<Stage>();
   typeof(Stage).GetProperty("sceneDef").SetValue(coordinator.objectiveStage,SceneCatalog.GetSceneDefForCurrentScene());MovementBatchProbe.Call(coordinator.objectiveStage,"OnEnable");coordinator.Check(Stage.instance==coordinator.objectiveStage,"Original stage singleton absent");
   var origin=coordinator.worldPlayer.characterMotor.Motor.TransientPosition;RaycastHit hit;coordinator.Check(Physics.Raycast(origin+Vector3.forward*10+Vector3.up*20,Vector3.down,out hit,50,LayerIndex.world.mask,QueryTriggerInteraction.Ignore),"Objective placement has no source floor");
   var primordial=SceneCatalog.GetSceneDefForCurrentScene().cachedName=="skymeadow";var objectiveSource=coordinator.artifactBundle.LoadAsset<GameObject>(primordial?cfg.lunarTeleporterAsset:cfg.teleporterAsset);coordinator.Check(objectiveSource,"Original stage teleporter source missing");coordinator.objectiveHost=Instantiate(objectiveSource,coordinator.worldStaging.transform);coordinator.objectiveHost.name=objectiveSource.name;
   coordinator.Check(coordinator.objectiveHost.GetComponentsInChildren<Component>(true).All(x=>x),"Original teleporter serialized component missing");
   foreach(var behaviour in coordinator.objectiveHost.GetComponentsInChildren<MonoBehaviour>(true)){
    if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(behaviour);continue;}
    // Whole source objective callbacks run. Optional native presentation is explicitly unavailable.
    if(behaviour is SfxLocator||behaviour.GetType().Name=="PostProcessDuration"||behaviour.GetType().Name=="WwiseSound")behaviour.enabled=false;
   }
   coordinator.worldTeleporter=coordinator.objectiveHost.GetComponent<TeleporterInteraction>();coordinator.Check(coordinator.worldTeleporter&&!coordinator.worldTeleporter.skipCombat&&coordinator.worldTeleporter.bossDirector&&coordinator.worldTeleporter.bonusDirector,"Original objective combat contract absent");
   var rewardGroup=coordinator.objectiveHost.GetComponent<BossGroup>();coordinator.Check(rewardGroup,"Original objective BossGroup component absent");
   rewardGroup.dropTable=ObjectiveDropTable(rewardGroup.dropTable);
   foreach(var table in objectiveDropTables.Values)MovementBatchProbe.Call(table,"Regenerate",Run.instance);
   coordinator.r.objective.rewardTables=objectiveDropTables.Values.Select(x=>x.name+"|"+x.GetPickupCount()).ToArray();
   coordinator.Save();coordinator.Check(rewardGroup.dropTable&&rewardGroup.dropTable.GetPickupCount()>0&&objectiveDropTables.Values.All(x=>x.GetPickupCount()>0),"Original objective reward tables have no available pickups: "+string.Join(",",coordinator.r.objective.rewardTables));
   coordinator.PrepareStageBossDeck(cfg);
   coordinator.worldTeleporter.bossDirector.onSpawnedServer.AddListener(QueueObjectiveDirectorActor);
   coordinator.worldTeleporter.bossDirector.monsterCards=coordinator.objectiveBossDeck;coordinator.worldTeleporter.bonusDirector.monsterCards=coordinator.automaticDeck;
   var bonusDirector=coordinator.worldTeleporter.bonusDirector;bonusDirector.onSpawnedServer.AddListener(obj=>{coordinator.RecordRewardSpawn(obj);if(coordinator.currentStageCombatDeck!=null)coordinator.RecordStageCombatSpawn(obj,coordinator.worldPlayer,bonusDirector);else coordinator.RecordDirectorActor(obj,coordinator.worldPlayer);});
   var model=coordinator.objectiveHost.GetComponent<ModelLocator>().modelTransform;coordinator.worldModels.Add(model);coordinator.PresentWorldModel(model,false,true);
   objectiveBeacon=coordinator.objectiveHost.GetComponentsInChildren<Collider>(true).Single(x=>x.GetComponent<EntityLocator>()&&x.GetComponent<EntityLocator>().entity==coordinator.objectiveHost);coordinator.Check(objectiveBeacon.gameObject.layer==LayerIndex.defaultLayer.intVal,"Original teleporter interaction layer changed");
   if(!coordinator.objectiveSubscribed)objectiveDefeated=group=>{if(coordinator.worldTeleporter&&group==coordinator.worldTeleporter.bossGroup){coordinator.r.objective.bossDefeated=true;coordinator.r.objective.rewardPickupBaseline=coordinator.r.world.pickupMessages;coordinator.Save();}};
   if(!coordinator.objectiveSubscribed)objectiveBeginExit=exit=>{
    if(coordinator.worldTeleporter&&exit==coordinator.worldTeleporter.sceneExitController){coordinator.r.objective.exitBegan=true;coordinator.Save();}
    else if(coordinator.IsGoldshoresEntryPortal(exit)){coordinator.r.objective.exitBegan=true;if(coordinator.r.goldshores==null)coordinator.r.goldshores=new GoldshoresMissionReport();coordinator.r.goldshores.shrinePurchased=true;coordinator.Save();}
    else if(coordinator.IsGoldshoresReturnPortal(exit)){coordinator.r.goldshores.exitBegan=true;coordinator.Save();}
   };
   if(!coordinator.objectiveSubscribed)objectiveFinishExit=exit=>{
    if(coordinator.worldTeleporter&&exit==coordinator.worldTeleporter.sceneExitController){coordinator.r.objective.exitFinished=true;coordinator.Save();}
    else if(coordinator.IsGoldshoresEntryPortal(exit)){coordinator.r.objective.exitFinished=true;coordinator.r.goldshores.entryPortalUsed=true;coordinator.r.stageProgress.goldPortalEntry=true;coordinator.Save();}
    else if(coordinator.IsGoldshoresReturnPortal(exit)){coordinator.r.goldshores.exitFinished=true;coordinator.r.goldshores.returnScene=exit.destinationScene?exit.destinationScene.cachedName:"unavailable";coordinator.Save();}
   };
   if(!coordinator.objectiveSubscribed){BossGroup.onBossGroupDefeatedServer+=objectiveDefeated;SceneExitController.onBeginExit+=objectiveBeginExit;SceneExitController.onFinishExit+=objectiveFinishExit;coordinator.objectiveSubscribed=true;}
   coordinator.objectiveHost.transform.position=hit.point;coordinator.objectiveHost.transform.SetParent(null,true);coordinator.objectiveHost.SetActive(true);NetworkServer.Spawn(coordinator.objectiveHost);yield return null;
   coordinator.Check(TeleporterInteraction.instance==coordinator.worldTeleporter&&coordinator.worldTeleporter.holdoutZoneController&&coordinator.worldTeleporter.bossGroup&&Run.instance.nextStageScene,"Original objective Awake/Start context incomplete");
   objectiveIndicatorConsumers++; // Original Awake takes one synchronous source lease per teleporter.
   coordinator.Check(coordinator.worldTeleporter.isIdle&&coordinator.worldTeleporter.GetInteractability(coordinator.worldPlayer.GetComponent<Interactor>())==Interactability.Available,"Original teleporter idle/interaction state missing");
   coordinator.r.objective.sourceDuration=coordinator.worldTeleporter.holdoutZoneController.baseChargeDuration;coordinator.r.objective.sourceRadius=coordinator.worldTeleporter.holdoutZoneController.baseRadius;coordinator.r.objective.position=coordinator.objectiveHost.transform.position;coordinator.r.objective.ready=true;ObserveTeleporterWorld();coordinator.Save();
  }
  public void ObserveTeleporterWorld(){
   // Native startup can instantiate additional prong renderers after initial
   // presentation. Route only their measured recovered family through the same
   // owned clone path; retain source layers, controllers and unknown materials.
   if(coordinator.objectiveHost&&AndroidNativeDeferredPresentation.report.available&&Time.frameCount%30==0){
    foreach(var renderer in coordinator.objectiveHost.GetComponentsInChildren<Renderer>(true)){
     if(coordinator.worldPresented.Contains(renderer.GetInstanceID()))continue;
     var materials=renderer.sharedMaterials;bool changed=false;
     for(int i=0;i<materials.Length;i++)if(materials[i]&&(materials[i].shader.name=="Hopoo Games/Deferred/Standard"||materials[i].shader.name=="CalmWater/Calm Water [DX11]"||materials[i].shader.name=="CalmWater/Calm Water [DX11] [Double Sided]")){
      var source=materials[i];var copy=new Material(source);AndroidMaterialPresentation.Apply(source,copy);materials[i]=copy;coordinator.worldMaterials.Add(copy);coordinator.r.objective.lateNativeMaterials++;changed=true;
     }
     if(changed){renderer.sharedMaterials=materials;coordinator.worldPresented.Add(renderer.GetInstanceID());}
    }
   }
   // The full material/property census serves explicit visual attribution only;
   // normal gameplay runs retain lightweight objective evidence and adaptation.
   // Include particles and owned world views when attributing an opaque surface.
   // Bounds estimate screen coverage; it is not an occlusion/pixel measurement.
   if(coordinator.objectiveHost&&coordinator.r.objective!=null&&(coordinator.r.detailedVisualDiagnostics||coordinator.r.visualCaptureActive)&&Time.frameCount%30==0){
    coordinator.r.objective.rendererViews=coordinator.objectiveHost.GetComponentsInChildren<Renderer>(true).Select(ObserveOwnedSurface).ToArray();
    var ownedMaterials=new HashSet<Material>(coordinator.worldMaterials.Where(x=>x));
    var visible=Resources.FindObjectsOfTypeAll<Renderer>().Where(x=>x&&x.gameObject.scene.IsValid()&&x.gameObject.activeInHierarchy&&x.enabled&&x.isVisible).ToArray();
    var owned=visible.Where(x=>coordinator.worldPresented.Contains(x.GetInstanceID())||x.sharedMaterials.Any(m=>m&&ownedMaterials.Contains(m))).Select(ObserveOwnedSurface).OrderByDescending(x=>x.projectedBoundsFraction).ToArray();
    // Keep the first short-lived native Queen effect observation across stage
    // reports; it may disappear before the host's next sampling interval.
    if(coordinator.r.world.nativeEffectViews==null){
     var effects=visible.Where(x=>x.GetComponentInParent<EffectComponent>()&&MovementBatchProbe.StageObjectPath(x.transform).StartsWith("BeetleQueenBurrow",StringComparison.Ordinal)&&x.sharedMaterials.Any(m=>m&&m.shader&&m.shader.name.StartsWith("Porting Lab/AndroidNativeFamily1Variant",StringComparison.Ordinal))).Select(ObserveOwnedSurface).ToArray();
     if(effects.Length>0)coordinator.r.world.nativeEffectViews=effects;
    }
    coordinator.r.objective.ownedSurfaceCount=owned.Length;coordinator.r.objective.ownedSurfaceViews=owned.Take(64).ToArray();
    // Effects spawned by native providers need not belong to the world model
    // list. Observe presentation shaders separately; do not claim ownership.
    coordinator.r.objective.presentedSurfaceViews=visible.Where(x=>x.sharedMaterials.Any(m=>m&&m.shader&&(m.shader.name.StartsWith("Porting Lab/",StringComparison.Ordinal)||m.shader.name.StartsWith("Hopoo Games/",StringComparison.Ordinal)))).Select(ObserveOwnedSurface).OrderByDescending(x=>x.projectedBoundsFraction).Take(128).ToArray();
   }
   FlushObjectiveActors();ObserveObjectiveSupport();if(!coordinator.worldTeleporter)return;var report=coordinator.r.objective;report.frames++;report.state=coordinator.worldTeleporter.activationState.ToString();if(report.state!=objectiveState){objectiveState=report.state;report.transitions.Add(report.state);coordinator.Save();}
   report.fsmState=coordinator.worldTeleporter.mainStateMachine.state==null?"uninitialized":coordinator.worldTeleporter.mainStateMachine.state.GetType().FullName;report.idle=coordinator.worldTeleporter.isIdle;report.available=coordinator.worldTeleporter.GetInteractability(coordinator.worldPlayer.GetComponent<Interactor>())==Interactability.Available;report.selected=coordinator.worldDriver.currentInteractable==coordinator.objectiveHost;report.authority=Util.HasEffectiveAuthority(coordinator.worldTeleporter.GetComponent<NetworkIdentity>());
   report.charge=coordinator.worldTeleporter.chargeFraction;report.radius=coordinator.worldTeleporter.holdoutZoneController.currentRadius;report.charging|=coordinator.worldTeleporter.isCharging;report.charged|=coordinator.worldTeleporter.isCharged;report.finished|=coordinator.worldTeleporter.isInFinalSequence;
   report.bossMembers=coordinator.worldTeleporter.bossGroup.combatSquad.memberCount;report.bossHealth=coordinator.worldTeleporter.bossGroup.totalObservedHealth;report.bossMaxHealth=coordinator.worldTeleporter.bossGroup.totalMaxObservedMaxHealth;report.credits=coordinator.worldTeleporter.bossDirector.monsterCredit;report.spent=coordinator.worldTeleporter.bossDirector.totalCreditsSpent;report.exitState=typeof(SceneExitController).GetField("exitState",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(coordinator.worldTeleporter.sceneExitController).ToString();var destination=coordinator.worldTeleporter.sceneExitController.useRunNextStageScene?Run.instance.nextStageScene:coordinator.worldTeleporter.sceneExitController.destinationScene;report.nextScene=destination?destination.cachedName:"unavailable";
   report.bossDeaths=coordinator.directorActors.Count(x=>x.report.dead&&x.report.origin=="teleporter-director");
   if(report.bossDefeated){report.rewardPickupMessages=coordinator.r.world.pickupMessages-report.rewardPickupBaseline;report.rewardCollected=report.rewardPickupMessages>0;}
  }
  public ObjectiveRendererObservation ObserveOwnedSurface(Renderer renderer){
   var materials=renderer.sharedMaterials;var bounds=renderer.bounds;var lo=new Vector2(float.MaxValue,float.MaxValue);var hi=new Vector2(float.MinValue,float.MinValue);bool inFront=false;
   if(coordinator.worldView!=null)for(int i=0;i<8;i++){var point=bounds.center+Vector3.Scale(bounds.extents,new Vector3((i&1)==0?-1:1,(i&2)==0?-1:1,(i&4)==0?-1:1));var screen=coordinator.worldView.ProjectWorldPoint(point);if(screen.z<=0)continue;inFront=true;lo=Vector2.Min(lo,new Vector2(screen.x,screen.y));hi=Vector2.Max(hi,new Vector2(screen.x,screen.y));}
   float area=inFront?Mathf.Max(0,Mathf.Min(Screen.width,hi.x)-Mathf.Max(0,lo.x))*Mathf.Max(0,Mathf.Min(Screen.height,hi.y)-Mathf.Max(0,lo.y))/(Screen.width*(float)Screen.height):0;var particle=renderer.GetComponent<ParticleSystem>();
   var particleRenderer=renderer as ParticleSystemRenderer;var streams=new List<ParticleSystemVertexStream>();if(particleRenderer)particleRenderer.GetActiveVertexStreams(streams);
   bool detailed=particleRenderer||renderer.name=="Water"||renderer.name.IndexOf("AreaIndicator",StringComparison.Ordinal)>=0;
   return new ObjectiveRendererObservation{unityFrame=Time.frameCount,particleRenderMode=particleRenderer?particleRenderer.renderMode.ToString():null,particleAlignment=particleRenderer?particleRenderer.alignment.ToString():null,vertexStreams=particleRenderer?streams.Select(x=>x.ToString()).ToArray():null,materialState=detailed?materials.Select(ObserveSurfaceMaterial).ToArray():null,path=MovementBatchProbe.StageObjectPath(renderer.transform),kind=renderer.GetType().Name,materials=materials.Select(m=>m?m.name:"missing").ToArray(),shaders=materials.Select(m=>m&&m.shader?m.shader.name:"missing").ToArray(),queues=materials.Select(m=>m?m.renderQueue:-1).ToArray(),enabled=renderer.enabled,active=renderer.gameObject.activeInHierarchy,visible=renderer.isVisible,worldOwned=coordinator.worldPresented.Contains(renderer.GetInstanceID())||materials.Any(m=>m&&coordinator.worldMaterials.Contains(m)),center=bounds.center,size=bounds.size,particles=particle?particle.particleCount:0,projectedBoundsFraction=area};
  }
  public SurfaceMaterialObservation ObserveSurfaceMaterial(Material material){
   if(!material||!material.shader)return null;var shader=material.shader;var properties=new List<SurfacePropertyObservation>();
   for(int i=0;i<shader.GetPropertyCount();i++){
    var name=shader.GetPropertyName(i);var type=shader.GetPropertyType(i);var property=new SurfacePropertyObservation{name=name,type=type.ToString()};
    switch(type){
     case UnityEngine.Rendering.ShaderPropertyType.Float:case UnityEngine.Rendering.ShaderPropertyType.Range:property.value.x=material.GetFloat(name);break;
     case UnityEngine.Rendering.ShaderPropertyType.Color:property.value=material.GetColor(name);break;
     case UnityEngine.Rendering.ShaderPropertyType.Vector:property.value=material.GetVector(name);break;
     case UnityEngine.Rendering.ShaderPropertyType.Texture:var texture=material.GetTexture(name);property.texture=texture?texture.name:null;property.textureId=texture?texture.GetInstanceID():0;property.width=texture?texture.width:0;property.height=texture?texture.height:0;property.scale=material.GetTextureScale(name);property.offset=material.GetTextureOffset(name);break;
    }
    properties.Add(property);
   }
   return new SurfaceMaterialObservation{instanceId=material.GetInstanceID(),shaderId=shader.GetInstanceID(),passCount=material.passCount,keywords=material.shaderKeywords,instancing=material.enableInstancing,doubleSidedGi=material.doubleSidedGI,properties=properties.ToArray()};
  }
  public IEnumerable<GenericPickupController> GrantableWorldPickups(CharacterBody player,bool includeEquipment=false){
   return coordinator.EjectionPickups().Where(x=>{var def=PickupCatalog.GetPickupDef(x.pickup.pickupIndex);return def!=null&&(def.itemIndex!=ItemIndex.None||includeEquipment&&player.inventory.currentEquipmentIndex==EquipmentIndex.None&&coordinator.EligibleWorldEquipment().Contains(EquipmentCatalog.GetEquipmentDef(def.equipmentIndex)))&&def.coinValue==0&&x.GetInteractability(player.GetComponent<Interactor>())==Interactability.Available;});
  }
  public bool ObjectiveWorldStimulus(CharacterBody player,NovaInputBridge bridge,float elapsed){
   if(!coordinator.worldTeleporter||!coordinator.r.objective.ready)return false;
   var delta=coordinator.objectiveHost.transform.position-player.characterMotor.Motor.TransientPosition;
   var planar=new Vector2(delta.x,delta.z);bridge.movement=planar.magnitude>1?planar.normalized:Vector2.zero;
   // The original charged teleporter owns exit availability. Surviving adds do
   // not create an extra completion gate in the diagnostic input driver.
   if(coordinator.worldTeleporter.isCharged&&!coordinator.r.objective.rewardCollected){if(objectiveRewardApproachAt<0)objectiveRewardApproachAt=elapsed;else if(elapsed-objectiveRewardApproachAt>=30)coordinator.r.objective.rewardLeftBehind=true;}
   if(coordinator.worldTeleporter.isCharged&&!coordinator.r.objective.rewardCollected&&!coordinator.r.objective.rewardLeftBehind){
    var pickup=GrantableWorldPickups(player).OrderBy(x=>Vector3.Distance(x.transform.position,player.corePosition)).FirstOrDefault();
    if(!pickup){bridge.movement=Vector2.zero;coordinator.r.world.objective="Wait for original boss reward";return true;}
    if(DefendWorldApproach(player,bridge,pickup.gameObject,elapsed))return true;
    coordinator.NavigateWorldInput(player,bridge,pickup.transform.position,.6f,pickup.name,elapsed);
    var collider=pickup.GetComponentsInChildren<Collider>(true).FirstOrDefault(x=>x.enabled&&(LayerIndex.CommonMasks.interactable.value&(1<<x.gameObject.layer))!=0);
    var pickupAim=(collider?collider.bounds.center:pickup.transform.position)-player.inputBank.aimOrigin;bridge.aim=new Vector2(pickupAim.x,pickupAim.z).normalized;bridge.diagnosticAim=pickupAim.normalized;
    if(coordinator.worldDriver.currentInteractable==pickup.gameObject&&elapsed-coordinator.worldLastPress>.5f){bridge.diagnosticInteract=true;coordinator.worldLastPress=elapsed;}
    coordinator.r.world.objective="Collect original boss reward";return true;
   }
   if(coordinator.worldTeleporter.isIdle||coordinator.worldTeleporter.isCharged){
    coordinator.NavigateWorldInput(player,bridge,coordinator.objectiveHost.transform.position,1,coordinator.objectiveHost.name,elapsed);
    // Travelling to an objective must not disable normal self-defence. Interaction
    // wins when the original selector is ready; otherwise clear nearby attackers.
    if(DefendWorldApproach(player,bridge,coordinator.objectiveHost,elapsed))return true;
    var aim=objectiveBeacon.bounds.center-player.inputBank.aimOrigin;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticAim=aim.normalized;
    if(coordinator.worldDriver.currentInteractable==coordinator.objectiveHost&&elapsed-coordinator.worldLastPress>.5f){bridge.diagnosticInteract=true;coordinator.worldLastPress=elapsed;}
   }else{
    ObjectiveCombatInput(player,bridge,elapsed,planar);
   }
   coordinator.r.world.objective=coordinator.worldTeleporter.isIdle?"Activate teleporter":coordinator.worldTeleporter.isCharging?"Defeat boss and charge teleporter":coordinator.worldTeleporter.isCharged?"Collect reward and exit":"Prepare next stage";
   return true;
  }
  public bool DefendWorldApproach(CharacterBody player,NovaInputBridge bridge,GameObject target,float elapsed){
   // Preserve original selection/interaction priority. Travel resumes after the
   // nearby source threat is defeated through ordinary skill and movement input.
   if(coordinator.worldDriver.currentInteractable==target)return false;
   var threat=coordinator.directorActors.Where(x=>x.body&&x.body.healthComponent.alive&&coordinator.InsideSourceStageBounds(coordinator.DirectorPhysicsPosition(x.body))).OrderBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();
   if(threat==null||Vector3.Distance(threat.body.corePosition,player.corePosition)>=20)return false;
   // The diagnostic route must not starve a real idle teleporter indefinitely
   // while the original director continuously replaces nearby attackers.
   // After the shopping window, keep travelling and firing through the same
   // input boundary; the teleporter still needs its real selector and events.
   if(coordinator.worldTeleporter&&(coordinator.worldTeleporter.isCharged||coordinator.worldTeleporter.isIdle&&elapsed-coordinator.stageEnteredAt>120)){
    // Defend en route without replacing source objective movement. In-range
    // interaction takes aim priority, including the original reward selector.
    if(Vector3.Distance(player.corePosition,target.transform.position)<=player.GetComponent<Interactor>().maxInteractionDistance)return false;
    bool visible;var aimPoint=WorldCombatAimPoint(threat.body,player.inputBank.aimOrigin,out visible);if(!visible)return false;
    coordinator.NavigateWorldInput(player,bridge,target.transform.position,target.GetComponent<GenericPickupController>() ? .6f : 1f,target.name,elapsed);
    var aim=aimPoint-player.inputBank.aimOrigin;bridge.diagnosticAim=aim.normalized;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticPrimary=true;bridge.diagnosticSecondary=elapsed%4<.2f;bridge.diagnosticSpecial=elapsed%10<.2f;
    coordinator.r.world.travelDefenseFrames++;coordinator.r.world.travelDefenseTarget=target.name;coordinator.r.world.objective="Defend while moving to "+target.name;return true;
   }
   ObjectiveCombatInput(player,bridge,elapsed,Vector2.zero,false);coordinator.r.world.travelDefenseFrames++;coordinator.r.world.travelDefenseTarget=target.name;coordinator.r.world.objective="Defend while approaching "+target.name;return true;
  }
  public void ObjectiveCombatInput(CharacterBody player,NovaInputBridge bridge,float elapsed,Vector2 planar,bool constrainToHoldout=true){
    // Once original charging finishes, a source path may leave the holdout to
    // reach a surviving boss. Boss defeat and exit still require original events.
    if(coordinator.worldTeleporter&&coordinator.worldTeleporter.chargeFraction>=1)constrainToHoldout=false;coordinator.r.world.combatHoldoutConstrained=constrainToHoldout;
    var living=coordinator.directorActors.Where(x=>x.body&&x.body.healthComponent.alive&&x.master.teamIndex!=player.teamComponent.teamIndex).ToArray();
    var actors=living.Where(x=>coordinator.InsideSourceStageBounds(coordinator.DirectorPhysicsPosition(x.body))).ToArray();coordinator.r.world.combatCandidates=living.Length;coordinator.r.world.combatBoundsRejected=living.Length-actors.Length;
    // The unattended route can aim through terrain or continually select distant
    // adds while the boss survives. Observe actual firing lines before choosing input.
    var origin=player.inputBank.aimOrigin;
    var targets=actors.Select(x=>{bool visible;var point=WorldCombatAimPoint(x.body,origin,out visible);return new {actor=x,point=point,visible=visible,distance=Vector3.Distance(point,origin),boss=coordinator.worldTeleporter&&coordinator.worldTeleporter.bossGroup.combatSquad.readOnlyMembersList.Contains(x.master)};}).ToArray();
    coordinator.r.world.combatVisibleCandidates=targets.Count(x=>x.visible);coordinator.r.world.combatOccludedCandidates=targets.Length-coordinator.r.world.combatVisibleCandidates;
    var guardIndex=BodyCatalog.FindBodyIndex("BeetleGuardBody");
    var target=targets.OrderBy(x=>!x.visible?(x.boss?5:6):x.actor.body.bodyIndex==guardIndex&&x.distance<25?0:x.distance<16?1:x.boss?2:x.distance<40?3:4).ThenBy(x=>x.distance).FirstOrDefault();
    // A fully overlapping enemy can make the unattended muzzle aim collapse
    // while this assisted route is earning legitimate repair currency.
    if(coordinator.r.commerceSweep&&coordinator.CommerceSweepPendingRepairs()&&target!=null&&target.distance<2){var clear=targets.Where(x=>x.visible&&x.distance>=5).OrderBy(x=>x.distance).FirstOrDefault();if(clear!=null)target=clear;}
    if(target!=null){
     // A distant occluded add must not interrupt a source-reachable boss approach.
     // Near contact remains a threat even without a clear firing line.
     var nearest=targets.Where(x=>x.visible||x.distance<8).OrderBy(x=>x.distance).FirstOrDefault();
     var fromThreat=player.characterMotor.Motor.TransientPosition-coordinator.DirectorPhysicsPosition(nearest!=null?nearest.actor.body:target.actor.body);float distance=fromThreat.magnitude;fromThreat.y=0;
     // The source Loader primary is a BasicMeleeAttack. A ranged retreat ring
     // kept it outside its own hitbox for the entire unattended route.
     var primary=player.skillLocator.primary.skillDef;
     bool meleePrimary=primary&&primary.activationState.stateType!=null&&typeof(EntityStates.BasicMeleeAttack).IsAssignableFrom(primary.activationState.stateType);
     float safeDistance=meleePrimary?1.6f:20f,engagementRange=meleePrimary?2.2f:32f;
     coordinator.r.world.combatMeleePrimary=meleePrimary;coordinator.r.world.combatEngagementRange=engagementRange;
     bool escape=nearest!=null&&distance<safeDistance;
     Vector2 desired=escape?new Vector2(fromThreat.x,fromThreat.z).normalized:distance>safeDistance+12?-new Vector2(fromThreat.x,fromThreat.z).normalized:new Vector2(fromThreat.z,-fromThreat.x).normalized;
     bool returnToHoldout=constrainToHoldout&&coordinator.worldTeleporter&&planar.magnitude>Mathf.Max(12f,coordinator.worldTeleporter.holdoutZoneController.currentRadius*.75f);
     bool approach=!escape&&(!target.visible||target.distance>engagementRange)&&(!constrainToHoldout||planar.magnitude<=50);
     if(returnToHoldout){
      // The unattended input driver follows the original scene graph back into
      // the real holdout; native charge, enemies and attacks remain unchanged.
      coordinator.NavigateWorldInput(player,bridge,coordinator.objectiveHost.transform.position,Mathf.Max(2f,coordinator.worldTeleporter.holdoutZoneController.currentRadius*.35f),"Return to original holdout",elapsed);
      coordinator.r.world.combatHoldoutReturnFrames++;coordinator.r.world.combatHoldoutReturnDistance=planar.magnitude;
     }else if(approach){
      coordinator.NavigateWorldInput(player,bridge,coordinator.DirectorPhysicsPosition(target.actor.body),1,"Combat: "+target.actor.body.name,elapsed);coordinator.r.world.combatApproachFrames++;
     }else SelectCombatMotion(player,bridge,desired,actors,escape);
     coordinator.r.world.combatTarget=target.actor.body.name;coordinator.r.world.combatLineOfSight=target.visible;coordinator.r.world.combatTargetBoss=target.boss;coordinator.r.world.combatTargetDistance=target.distance;coordinator.r.world.combatThreatDistance=distance;coordinator.r.world.combatAimOrigin=origin;coordinator.r.world.combatAimTarget=target.point;
     bool evade=!meleePrimary&&nearest!=null&&distance<16;if(!returnToHoldout)bridge.diagnosticSprint=evade;if(!approach&&!returnToHoldout)bridge.DiagnosticJump(elapsed%1.8f<.25f);
     bridge.diagnosticUtility=evade&&player.skillLocator.utility.CanExecute();
     var aim=target.point-origin;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticAim=aim.normalized;bridge.diagnosticPrimary=target.visible;bridge.diagnosticSecondary=target.visible&&elapsed%4<.2f;bridge.diagnosticSpecial=target.visible&&elapsed%10<.2f;
     if(coordinator.r.commerceSweep&&coordinator.CommerceSweepPendingRepairs()){bridge.diagnosticUtility=bridge.diagnosticSecondary=bridge.diagnosticSpecial=false;}
     coordinator.r.world.combatPrimaryRequested=bridge.diagnosticPrimary;
    }
  }
  public Vector3 WorldCombatAimPoint(CharacterBody target,Vector3 origin,out bool visible){
   var point=target.mainHurtBox?target.mainHurtBox.transform.position:target.corePosition;
   visible=!Physics.Linecast(origin,point,LayerIndex.world.mask,QueryTriggerInteraction.Ignore);
   float best=visible?(point-origin).sqrMagnitude:float.PositiveInfinity;
   var group=target.hurtBoxGroup;if(!group)return point;
   foreach(var box in group.hurtBoxes){
    if(!box||!box.isBullseye||!box.gameObject.activeInHierarchy)continue;
    var candidate=box.transform.position;var distance=(candidate-origin).sqrMagnitude;
    if(distance>=best||Physics.Linecast(origin,candidate,LayerIndex.world.mask,QueryTriggerInteraction.Ignore))continue;
    point=candidate;best=distance;visible=true;
   }
   return point;
  }
  public void SelectCombatMotion(CharacterBody player,NovaInputBridge bridge,Vector2 desired,DirectorActor[] threats,bool escape){
   // Input-only terrain selection. Compare ground to ground, including while
   // jumping; capsule-position comparison can reject otherwise walkable ground.
   var solver=player.characterMotor.Motor;var origin=solver.TransientPosition;RaycastHit floor;
   coordinator.r.world.combatMotionSamples++;bridge.movement=Vector2.zero;coordinator.r.world.combatMotion=Vector2.zero;
   if(!Physics.Raycast(origin+Vector3.up*.25f,Vector3.down,out floor,24,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||floor.collider.gameObject.scene!=coordinator.stageGeometryScene){coordinator.r.world.combatMotionBlocked++;return;}
   var baseline=solver.GroundingStatus.IsStableOnGround?solver.GroundingStatus.GroundPoint:floor.point;coordinator.r.world.combatGround=baseline;
   if(desired.sqrMagnitude<.01f)desired=Vector2.right;desired.Normalize();var perpendicular=new Vector2(desired.y,-desired.x);
   var choices=new[]{desired,(desired+perpendicular).normalized,perpendicular,(-desired+perpendicular).normalized,-desired,(-desired-perpendicular).normalized,-perpendicular,(desired-perpendicular).normalized};
   float best=float.NegativeInfinity;
   foreach(var choice in choices)foreach(float length in new[]{2f,4f}){
    RaycastHit ground;var ahead=baseline+new Vector3(choice.x,0,choice.y)*length;
    if(!Physics.Raycast(ahead+Vector3.up*4,Vector3.down,out ground,9,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||ground.collider.gameObject.scene!=coordinator.stageGeometryScene||ground.normal.y<=.75f||Mathf.Abs(ground.point.y-baseline.y)>=2||!coordinator.InsideSourceStageBounds(ground.point))continue;
    if(Physics.Linecast(baseline+Vector3.up,ground.point+Vector3.up,LayerIndex.world.mask,QueryTriggerInteraction.Ignore))continue;
    float score=Vector2.Dot(choice,desired)*4;
    if(escape)score+=threats.Min(x=>Vector3.Distance(ground.point,coordinator.DirectorPhysicsPosition(x.body)));
    if(score<=best)continue;best=score;bridge.movement=choice;coordinator.r.world.combatDestination=ground.point;
   }
   coordinator.r.world.combatMotion=bridge.movement;if(bridge.movement==Vector2.zero)coordinator.r.world.combatMotionBlocked++;
  }
  public void Dispose(){coordinator.CleanupStageBossContent();coordinator.CleanupMoonMission();coordinator.CleanupStageTransport();
   if(objectiveSummon!=null)MasterSummon.onServerMasterSummonGlobal-=objectiveSummon;pendingObjectiveActors.Clear();objectiveAmbientExpected.Clear();objectiveDirectorActors.Clear();
   if(coordinator.objectiveSubscribed){BossGroup.onBossGroupDefeatedServer-=objectiveDefeated;SceneExitController.onBeginExit-=objectiveBeginExit;SceneExitController.onFinishExit-=objectiveFinishExit;coordinator.objectiveSubscribed=false;}
   ObserveObjectiveSupport(true);CleanupObjectiveEffects();CleanupObjectiveSupport();if(coordinator.objectiveHost)NetworkServer.Destroy(coordinator.objectiveHost);if(coordinator.objectiveBossDeck)Destroy(coordinator.objectiveBossDeck);
   coordinator.ReleaseObjectiveStage();
   foreach(var resource in coordinator.objectiveResources)if(resource)Destroy(resource);objectiveDropTables.Clear();foreach(var card in coordinator.objectiveCards)if(card)Destroy(card);
   if(coordinator.ownsObjectiveIndicator&&objectiveIndicatorLease.IsValid()){int extra=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveIndicatorLease)-objectiveIndicatorReferences;coordinator.Check(extra>=0&&extra<=objectiveIndicatorConsumers,"Unattributed teleporter indicator leases");for(int i=0;i<extra;i++)Addressables.Release(objectiveIndicatorSource);Addressables.Release(objectiveIndicatorLease);coordinator.ownsObjectiveIndicator=false;objectiveIndicatorSource=null;}
   if(ownsObjectiveTMP){objectiveTMPField.SetValue(null,priorObjectiveTMP);if(objectiveTMPLease.IsValid())Addressables.Release(objectiveTMPLease);ownsObjectiveTMP=false;objectiveTMPSettings=null;}
   if(coordinator.objectiveLocator!=null){Addressables.RemoveResourceLocator(coordinator.objectiveLocator);coordinator.objectiveLocator=null;}
  }
  public void CleanupObjectiveConfigs(){foreach(var pair in objectiveStaticFields)pair.Key.SetValue(null,pair.Value);objectiveStaticFields.Clear();foreach(var config in objectiveConfigs)if(config)Destroy(config);objectiveConfigs.Clear();}
 }
}
