using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using RoR2;
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
 [Serializable] public class ObjectiveActorSpec {public string name,body,master,card,avatar,controller,material,mesh;public ObjectiveVisualBinding[] bindings;}
 [Serializable] public class ObjectiveReport {
  public bool ready,rules,idle,available,selected,authority,charging,charged,bossDefeated,finished,exitBegan,exitFinished,cleaned,rewardCollected,rewardLeftBehind;
  public int rewardPickupBaseline,rewardPickupMessages;
  public string[] rewardTables;
  public int silentSourceComponents,frames,bossSpawns,bossDeaths,bossMembers,normalSpawns,ruleCount,unusedParticleMaterialSlots,previewMaterialSlots;
  public float charge,radius,bossHealth,bossMaxHealth,sourceDuration,sourceRadius,credits,spent;
  public string state,fsmState,nextScene,exitState,scope;public Vector3 position;
  public List<string> transitions=new List<string>();
 }
 readonly List<GameObject> objectiveTemplates=new List<GameObject>();
 readonly List<CharacterSpawnCard> objectiveCards=new List<CharacterSpawnCard>();
 readonly List<UnityEngine.Object> objectiveResources=new List<UnityEngine.Object>();
 readonly List<EntityStateConfiguration> objectiveConfigs=new List<EntityStateConfiguration>();
 readonly Dictionary<FieldInfo,object> objectiveStaticFields=new Dictionary<FieldInfo,object>();
 TeleporterInteraction worldTeleporter;GameObject objectiveHost;ResourceLocationMap objectiveLocator;
 TMPro.TMP_Settings objectiveTMPSettings;AsyncOperationHandle<TMPro.TMP_Settings> objectiveTMPLease;bool ownsObjectiveTMP;object priorObjectiveTMP;FieldInfo objectiveTMPField;
 GameObject objectiveIndicatorSource;AsyncOperationHandle<GameObject> objectiveIndicatorLease;int objectiveIndicatorReferences,objectiveIndicatorConsumers;bool ownsObjectiveIndicator;DirectorCardCategorySelection objectiveBossDeck;
 Action<MasterSummon.MasterSummonReport> objectiveSummon;Action<BossGroup> objectiveDefeated;
 Action<SceneExitController> objectiveBeginExit,objectiveFinishExit;
 string objectiveState;bool objectiveSubscribed;float objectiveRewardApproachAt=-1;
 GameObject[] objectiveEffectSources;
 EffectDef[] ObjectiveEffects(Result cfg){
  objectiveEffectSources=cfg.objectiveEffectAssets.Select(x=>artifactBundle.LoadAsset<GameObject>(x)).Distinct().ToArray();
  Check(objectiveEffectSources.All(x=>x&&x.GetComponent<EffectComponent>()),"Original composed effect catalog roots missing");
  foreach(var source in objectiveEffectSources)source.GetComponent<EffectComponent>().soundName=null;return objectiveEffectSources.Select(x=>new EffectDef(x)).ToArray();
 }
 void CleanupObjectiveEffects(){
  if(objectiveEffectSources==null)return;var pools=(Dictionary<GameObject,EffectPool>)RewardField(typeof(EffectManager),"_EffectPrefabMap").GetValue(null);var cache=(IDictionary)RewardField(typeof(EffectManager),"_ShouldUsePooledEffectMap").GetValue(null);
  foreach(var source in objectiveEffectSources){EffectPool pool;if(pools.TryGetValue(source,out pool)){foreach(var effect in pool.InUse.ToArray())pool.ReturnObject(effect);EffectManager.ClearPool(source);pool.Kill();}cache.Remove(source);}
 }
 readonly List<CharacterMaster> pendingObjectiveActors=new List<CharacterMaster>();
 readonly Dictionary<CharacterMaster,int> objectiveAmbientExpected=new Dictionary<CharacterMaster,int>();
 readonly HashSet<CharacterMaster> objectiveDirectorActors=new HashSet<CharacterMaster>();
 void QueueObjectiveDirectorActor(GameObject obj){var master=obj.GetComponent<CharacterMaster>();if(master)objectiveDirectorActors.Add(master);}
 void FlushObjectiveActors(){
  foreach(var master in pendingObjectiveActors.ToArray()){
   pendingObjectiveActors.Remove(master);if(!master)continue;
   RecordDirectorActor(master.gameObject,enemyPlayer,objectiveDirectorActors.Contains(master)?"teleporter-director":master.bodyPrefab.name.StartsWith("Lunar",StringComparison.Ordinal)||master.bodyPrefab.name.StartsWith("Brother",StringComparison.Ordinal)?"moon-encounter":"queen-summon",objectiveAmbientExpected[master]);objectiveAmbientExpected.Remove(master);
   if(master.bodyPrefab.name=="BeetleQueen2Body")r.objective.bossSpawns++;else r.objective.normalSpawns++;
  }
 }
 void PrepareObjectivePresentationSources(){
  // These are owned converted Android prefab assets in memory, never the original input.
  // Remove native-audio components before cloning or EffectManagerHelper caches Ak callbacks.
  foreach(var source in artifactBundle.LoadAllAssets<GameObject>())foreach(var component in source.GetComponentsInChildren<MonoBehaviour>(true))
   if(component&&component.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(component,true);r.objective.silentSourceComponents++;}
 }

 GameObject objectiveOrbHost,objectiveProjectileTemplates;AsyncOperationHandle<GameObject>[] objectiveSupportLeases;GameObject[] objectiveSupportSources;bool ownsObjectiveOrbEffects;
 readonly List<GameObject> objectiveSupportInstances=new List<GameObject>();
 BuffDef[] ObjectiveBuffs(Result cfg){
  if(!cfg.teleporterLoop)return new BuffDef[0];var def=artifactBundle.LoadAsset<BuffDef>(cfg.objectiveWardBuffAsset);Check(def&&def.name=="bdBeetleJuice","Original Queen ward buff missing");BindEnemyDefinition(typeof(RoR2Content.Buffs),"BeetleJuice",def);return new[]{def};
 }
 IEnumerator PrepareObjectiveSupport(Result cfg){
  Check(!OrbManager.instance,"Unowned original orb manager");
  var bundle=new ResourceLocationBase("objective-support-lab",System.IO.Path.Combine(Application.persistentDataPath,"payload","objective-support-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));bundle.Data=new AssetBundleRequestOptions{BundleName="objective-support-lab"};
  objectiveSupportLeases=new AsyncOperationHandle<GameObject>[cfg.objectiveSupportAssets.Length];objectiveSupportSources=new GameObject[cfg.objectiveSupportAssets.Length];
  for(int i=0;i<cfg.objectiveSupportAssets.Length;i++){
   string key;Check(LegacyResourcesAPI.GetGuid(cfg.objectiveSupportPaths[i],out key)&&key==cfg.objectiveSupportKeys[i],"Original Queen/exit legacy identity changed");
   objectiveLocator.Add(key,new ResourceLocationBase(key,cfg.objectiveSupportAssets[i],typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));
   objectiveSupportLeases[i]=LegacyResourcesAPI.LoadAsync<GameObject>(cfg.objectiveSupportPaths[i]);yield return objectiveSupportLeases[i];objectiveSupportSources[i]=objectiveSupportLeases[i].Result;
   Check(objectiveSupportSources[i]&&objectiveSupportSources[i].GetComponentsInChildren<Component>(true).All(x=>x),"Original objective support serialization missing");
  }
  PrepareMoonSupport(cfg);
  var ward=objectiveSupportSources[1];var wardModel=ward.GetComponent<ModelLocator>().modelTransform;var wardSkin=wardModel.GetComponent<ModelSkinController>();var wardAnimator=wardModel.GetComponent<Animator>();
  Check(wardSkin&&wardAnimator&&cfg.objectiveWardVisualAssets.Length==5,"Original ward visual contract missing");
  wardSkin._animatorController=artifactBundle.LoadAsset<RuntimeAnimatorController>(cfg.objectiveWardVisualAssets[0]);wardSkin._avatar=artifactBundle.LoadAsset<Avatar>(cfg.objectiveWardVisualAssets[1]);
  typeof(ModelSkinController).GetField("_animatorControllerAddress",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(wardSkin,new AssetReferenceT<RuntimeAnimatorController>(""));
  typeof(ModelSkinController).GetField("_avatarAddress",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(wardSkin,new AssetReferenceT<Avatar>(""));
  wardAnimator.runtimeAnimatorController=wardSkin._animatorController;wardAnimator.avatar=wardSkin._avatar;Check(wardAnimator.avatar&&wardAnimator.runtimeAnimatorController,"Original ward animation source missing");
  var wardMesh=artifactBundle.LoadAsset<Mesh>(cfg.objectiveWardVisualAssets[2]);var wardRenderer=wardModel.GetComponentInChildren<SkinnedMeshRenderer>(true);Check(wardMesh&&wardRenderer&&wardMesh.bindposes.Length==wardRenderer.bones.Length,"Original ward mesh binding absent");wardRenderer.sharedMesh=wardMesh;
  foreach(var renderer in wardModel.GetComponentsInChildren<Renderer>(true)){var material=Instantiate(artifactBundle.LoadAsset<Material>(cfg.objectiveWardVisualAssets[renderer is SkinnedMeshRenderer?3:4]));material.shader=Resources.Load<Shader>("CommandoMaterialPreview");material.shaderKeywords=new string[0];objectiveResources.Add(material);renderer.sharedMaterial=material;renderer.gameObject.layer=30;}
  foreach(var behaviour in ward.GetComponentsInChildren<MonoBehaviour>(true)){
   if(behaviour is RoR2.Networking.CharacterNetworkTransform||behaviour is InteractionDriver||behaviour is EquipmentSlot)behaviour.enabled=false;
   if(behaviour.transform!=ward.transform)behaviour.enabled=behaviour is HurtBox||behaviour is HurtBoxGroup||behaviour is HitBox||behaviour is HitBoxGroup||behaviour is RootMotionAccumulator||behaviour is AnimationEvents;
  }
  foreach(var locator in ward.GetComponentsInChildren<SfxLocator>(true))foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Public|BindingFlags.Instance))if(field.FieldType==typeof(string))field.SetValue(locator,null);
  var supportEffects=new[]{objectiveSupportSources[0],objectiveSupportSources[3]};foreach(var source in supportEffects)source.GetComponent<EffectComponent>().soundName=null;objectiveEffectSources=objectiveEffectSources.Concat(supportEffects).Distinct().ToArray();
  var entries=(EffectDef[])RewardField(typeof(EffectCatalog),"entries").GetValue(null);EffectCatalog.SetEntries(entries.Concat(supportEffects.Select(x=>new EffectDef(x))).GroupBy(x=>x.prefab).Select(x=>x.First()).ToArray());
  Check(!OrbEffectSingleton.instance&&OrbEffectSingleton.numPnts==0,"Unowned original orb visual context");
  objectiveOrbHost=new GameObject("Owned original Queen orb manager");objectiveOrbHost.AddComponent<OrbManager>();objectiveOrbHost.AddComponent<OrbEffectSingleton>();ownsObjectiveOrbEffects=true;Check(OrbManager.instance&&OrbEffectSingleton.instance,"Original Queen orb context missing");
 }
 void ObserveObjectiveSupport(bool force=false){
  if(!force&&Time.frameCount%30!=0)return;
  if(objectiveSupportSources==null)return;
  foreach(var source in objectiveSupportSources.Skip(1).Take(2))foreach(var instance in Resources.FindObjectsOfTypeAll<GameObject>().Where(x=>x.scene.IsValid()&&x.name==source.name+"(Clone)"))if(!objectiveSupportInstances.Contains(instance))objectiveSupportInstances.Add(instance);
 }
 void CleanupObjectiveSupport(){
  CleanupMoonSupport();
  if(objectiveOrbHost)Destroy(objectiveOrbHost);if(ownsObjectiveOrbEffects){OrbEffectSingleton.instance=null;OrbEffectSingleton.orbEffectArray=null;OrbEffectSingleton.numPnts=0;ownsObjectiveOrbEffects=false;}foreach(var instance in objectiveSupportInstances)if(instance)NetworkServer.Destroy(instance);
  ReleaseObjectiveOrbCache();
  if(objectiveSupportLeases!=null)foreach(var lease in objectiveSupportLeases)if(lease.IsValid())Addressables.Release(lease);
 }
 void ReleaseObjectiveOrbCache(){
  var cache=(IDictionary)typeof(OrbStorageUtility).GetField("_orbDictionary",BindingFlags.Static|BindingFlags.NonPublic).GetValue(null);
  foreach(var source in new[]{"Prefabs/Effects/OrbEffects/BeetleWardOrbEffect","Prefabs/NetworkedObjects/BeetleWard","Prefabs/Effects/OrbEffects/LightningOrbEffect"})if(cache.Contains(source)){var prefab=cache[source] as GameObject;cache.Remove(source);if(prefab)Addressables.Release(prefab);}
 }
 GameObject objectiveStageHost;Stage objectiveStage;static bool objectiveHoldoutInitialized;
 readonly Dictionary<PickupDropTable,PickupDropTable> objectiveDropTables=new Dictionary<PickupDropTable,PickupDropTable>();
 PickupDropTable ObjectiveDropTable(PickupDropTable source){
  if(!source)return null;PickupDropTable copy;if(objectiveDropTables.TryGetValue(source,out copy))return copy;
  copy=Instantiate(source);copy.name=source.name;objectiveDropTables.Add(source,copy);objectiveResources.Add(copy);return copy;
 }
 Collider objectiveBeacon;

 ArtifactDef[] ObjectiveArtifacts(Result cfg){
  if(!cfg.teleporterLoop)return new ArtifactDef[0];
  var holders=typeof(ArtifactDef).Assembly.GetTypes().Where(x=>x.Name=="Artifacts"&&x.DeclaringType!=null&&x.DeclaringType.Name.EndsWith("Content",StringComparison.Ordinal)).ToArray();
  var defs=cfg.objectiveArtifactAssets.Select(x=>artifactBundle.LoadAsset<ArtifactDef>(x)).ToArray();Check(defs.All(x=>x),"Original objective artifact definitions absent");
  foreach(var def in defs){var fields=holders.Select(x=>x.GetField(def.cachedName)).Where(x=>x!=null&&x.FieldType==typeof(ArtifactDef)).ToArray();Check(fields.Length==1,"Original artifact content identity ambiguous: "+def.cachedName);var prior=fields[0].GetValue(null);if(prior==null)BindEnemyDefinition(fields[0].DeclaringType,fields[0].Name,def);else Check(ReferenceEquals(prior,def),"Original artifact definition drift: "+def.cachedName);}
  return defs;
 }

 Type[] ObjectiveTypes(Result cfg){
  if(!cfg.teleporterLoop)return new Type[0];
  var assembly=typeof(TeleporterInteraction).Assembly;
  return assembly.GetTypes().Where(t=>!t.IsAbstract&&typeof(EntityState).IsAssignableFrom(t)&&
   (t.DeclaringType==typeof(TeleporterInteraction)||t.Namespace=="EntityStates.BeetleQueenMonster"||t.Namespace=="EntityStates.BeetleGuardMonster"||t.Namespace=="EntityStates.LunarTeleporter"||
    (cfg.moonMission&&((t.Namespace??"").StartsWith("EntityStates.BrotherMonster",StringComparison.Ordinal)||(t.Namespace??"").StartsWith("EntityStates.LunarGolem",StringComparison.Ordinal)||(t.Namespace??"").StartsWith("EntityStates.LunarWisp",StringComparison.Ordinal)||(t.Namespace??"").StartsWith("EntityStates.LunarExploder",StringComparison.Ordinal)||t.Namespace=="EntityStates.Missions.Moon"||t.Namespace=="EntityStates.Missions.BrotherEncounter"||t.Namespace=="EntityStates.MoonElevator"||t.DeclaringType==typeof(EscapeSequenceController))))).ToArray();
 }
 EntityStateConfiguration[] PrepareObjectiveConfigs(Result cfg){
  PrepareObjectivePresentationSources();
  foreach(var type in ObjectiveTypes(cfg))foreach(var field in type.GetFields(BindingFlags.Static|BindingFlags.Public|BindingFlags.DeclaredOnly))if(!field.IsLiteral&&!field.IsInitOnly)objectiveStaticFields[field]=field.GetValue(null);
  foreach(var path in cfg.objectiveConfigAssets){
   var source=artifactBundle.LoadAsset<EntityStateConfiguration>(path);Check(source,"Original objective state config absent: "+path);
   var copy=Instantiate(source);copy.serializedFieldsCollection.serializedFields=source.serializedFieldsCollection.serializedFields.ToArray();
   for(int i=0;i<copy.serializedFieldsCollection.serializedFields.Length;i++){
    var field=copy.serializedFieldsCollection.serializedFields[i];
    if(field.fieldName.IndexOf("sound",StringComparison.OrdinalIgnoreCase)>=0)copy.serializedFieldsCollection.serializedFields[i].fieldValue.stringValue="";
    // Retain genuine effect references: some original animation/state calls are unconditional.
    var projectile=field.fieldValue.objectValue as GameObject;
    if(projectile&&projectile.GetComponent<RoR2.Projectile.ProjectileController>()){
     if(!objectiveProjectileTemplates){objectiveProjectileTemplates=new GameObject("Owned silent objective projectile templates");objectiveProjectileTemplates.SetActive(false);objectiveResources.Add(objectiveProjectileTemplates);}
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
 void PrepareObjectiveActorTemplates(Result cfg){
  foreach(var spec in cfg.objectiveActors){
   r.phase="objective-template-"+spec.name;Save();
   var source=artifactBundle.LoadAsset<GameObject>(spec.body);Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original objective actor serialization missing: "+spec.name);
   var bodyObject=Instantiate(source,enemyTemplates.transform);bodyObject.name=source.name;bodyObject.SetActive(true);objectiveTemplates.Add(bodyObject);
   var body=bodyObject.GetComponent<CharacterBody>();var locator=bodyObject.GetComponent<ModelLocator>();Check(body&&locator&&locator.modelTransform,"Original objective body/model components absent: "+spec.name);var model=locator.modelTransform;var animator=model.GetComponent<Animator>();Check(animator,"Original objective Animator absent: "+spec.name);
   animator.avatar=artifactBundle.LoadAsset<Avatar>(spec.avatar);animator.runtimeAnimatorController=artifactBundle.LoadAsset<RuntimeAnimatorController>(spec.controller);animator.applyRootMotion=false;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
   Check(animator.avatar&&animator.runtimeAnimatorController,"Original objective animation absent: "+spec.name);
   foreach(var behaviour in bodyObject.GetComponentsInChildren<MonoBehaviour>(true)){
    if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(behaviour);continue;}
    var rewards=behaviour as DeathRewards;if(rewards){rewards.logUnlockableDef=null;rewards.bossDropTable=ObjectiveDropTable(rewards.bossDropTable);}
    if(behaviour is RoR2.Networking.CharacterNetworkTransform||behaviour is InteractionDriver||behaviour is EquipmentSlot)behaviour.enabled=false;
    if(behaviour.transform!=bodyObject.transform)behaviour.enabled=behaviour is HurtBox||behaviour is HurtBoxGroup||behaviour is HitBox||behaviour is HitBoxGroup||behaviour is RootMotionAccumulator||behaviour is AnimationEvents;
   }
   var sfx=body.GetComponent<SfxLocator>();Check(sfx,"Original objective SfxLocator absent: "+spec.name);foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Public|BindingFlags.Instance))if(field.FieldType==typeof(string))field.SetValue(sfx,null);
   if(spec.bindings!=null&&spec.bindings.Length>0)BindMoonActorVisuals(bodyObject,model,spec);
   else{
    var material=Instantiate(artifactBundle.LoadAsset<Material>(spec.material));material.shader=Resources.Load<Shader>("CommandoMaterialPreview");material.shaderKeywords=new string[0];material.SetFloat("_EmissionEnabled",0);objectiveResources.Add(material);
    var skins=model.GetComponentsInChildren<SkinnedMeshRenderer>(true);Check(skins.Length==1,"Original objective default renderer contract changed: "+spec.name);var mesh=artifactBundle.LoadAsset<Mesh>(spec.mesh);Check(mesh&&mesh.vertexCount>0&&mesh.bindposes.Length==skins[0].bones.Length,"Original objective mesh/bind poses absent: "+spec.name);skins[0].sharedMesh=mesh;
    foreach(var renderer in model.GetComponentsInChildren<Renderer>(true)){renderer.gameObject.layer=30;renderer.sharedMaterial=material;var skin=renderer as SkinnedMeshRenderer;if(skin)skin.updateWhenOffscreen=true;}
    var characterModel=model.GetComponent<CharacterModel>();characterModel.visibility=VisibilityLevel.Invisible;
    for(int i=0;i<characterModel.baseRendererInfos.Length;i++)characterModel.baseRendererInfos[i].defaultMaterial=material;
   }
   foreach(var provider in bodyObject.GetComponentsInChildren<SurfaceDefProvider>(true)){var surface=Instantiate(provider.surfaceDef);surface.impactEffectPrefab=null;surface.impactSoundString=null;provider.surfaceDef=surface;objectiveResources.Add(surface);}
   var masterObject=Instantiate(artifactBundle.LoadAsset<GameObject>(spec.master),enemyTemplates.transform);masterObject.name=spec.name+"Master";masterObject.GetComponent<Inventory>().enabled=false;masterObject.GetComponent<CharacterMaster>().bodyPrefab=bodyObject;masterObject.SetActive(true);objectiveTemplates.Add(masterObject);
   var card=Instantiate(artifactBundle.LoadAsset<CharacterSpawnCard>(spec.card));Check(card&&card.prefab&&card.directorCreditCost>=0,"Original objective spawn card absent");card.name=card.name.Replace("(Clone)","");card.prefab=masterObject;objectiveCards.Add(card);
  }
  // The original Queen summons a Guard using its configured source card. Redirect only the
  // generated card's prefab boundary to the owned compatible template; retain source settings.
  EntityStates.BeetleQueenMonster.SummonEggs.spawnCard=objectiveCards.Single(x=>x.name=="cscBeetleGuard");
  objectiveSummon=report=>{
   if(!report.summonMasterInstance||!objectiveTemplates.Contains(report.masterSummon.masterPrefab))return;
   var master=report.summonMasterInstance;BindMoonBodySupport(master.GetBody());ownedRewardSummons.Add(master);pendingObjectiveActors.Add(master);
   var summoner=report.masterSummon.summonerBodyObject?report.masterSummon.summonerBodyObject.GetComponent<CharacterBody>():null;
   objectiveAmbientExpected[master]=1+(summoner&&summoner.inventory?summoner.inventory.GetItemCountEffective(RoR2Content.Items.UseAmbientLevel):0);
   // MasterSummon publishes before CombatDirector assigns cost, rewards and squad.
   // Observation must never interrupt the original spawn transaction.
  };
  MasterSummon.onServerMasterSummonGlobal+=objectiveSummon;
 }
 bool IsObjectiveActor(CharacterBody body){return body&&objectiveTemplates.Any(x=>x==body.master.bodyPrefab);}

 void PrepareObjectiveRules(){
  // RuleCatalog/RuleBook cache definitions for the process. Restart may reuse this exact
  // catalog signature, but cannot rebuild it while cached RuleBook rule references survive.
  var signature=string.Join("|",ItemCatalog.allItemDefs.Select(x=>x.name))+"/"+string.Join("|",Enumerable.Range(0,EquipmentCatalog.equipmentCount).Select(x=>EquipmentCatalog.GetEquipmentDef((EquipmentIndex)x).name));
  if(objectiveRuleSignature==null){Check(RuleCatalog.ruleCount==0,"Unowned original rules");StaticCall(typeof(RuleCatalog),"Init");StaticCall(typeof(RuleBook),"Init");objectiveRuleSignature=signature;}
  Check(objectiveRuleSignature==signature&&RuleCatalog.FindRuleDef("Misc.StageOrder")!=null,"Restart rule catalog input changed");
  var run=Run.instance;var networkBook=run.GetComponent<NetworkRuleBook>();Check(networkBook,"Original Run rule component absent");
  if(networkBook.ruleBook==null)Call(networkBook,"Awake");
  typeof(Run).GetField("networkRuleBookComponent",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(run,networkBook);
  var easy=RuleCatalog.FindChoiceDef("Difficulty.Easy");Check(easy!=null,"Original Drizzle rule missing");run.ruleBook.ApplyChoice(easy);Check(run.ruleBook.FindDifficulty()==DifficultyIndex.Easy&&run.selectedDifficulty==DifficultyIndex.Easy,"Original chosen Drizzle difficulty mismatch");
  Check(run.ruleBook.stageOrder==StageOrder.Normal&&!run.ruleBook.keepMoneyBetweenStages,"Original default stage-order/money rules changed");
  RefreshRewardEquipmentMask(true);
  if(r.moonCatalog!=null){var lunar=RoR2Content.Equipment.AffixLunar;Check(lunar&&EquipmentCatalog.GetEquipmentDef(lunar.equipmentIndex)==lunar&&!lunar.requiredExpansion&&!run.IsEquipmentExpansionLocked(lunar.equipmentIndex),"Original base Lunar equipment availability failed");}
  Check(run.runRNG!=null&&run.loopRngGenerator!=null&&run.nextStageRng!=null&&run.bossRewardRng!=null,"Original Run random streams absent");r.objective.rules=true;r.objective.ruleCount=RuleCatalog.ruleCount;
 }
 static string objectiveRuleSignature;
 IEnumerator PrepareTeleporterWorld(Result cfg){
  r.phase="integrated-teleporter-context";Save();PrepareObjectiveRules();
  var bundle=new ResourceLocationBase("teleporter-indicator-lab",System.IO.Path.Combine(Application.persistentDataPath,"payload","teleporter-indicator-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));bundle.Data=new AssetBundleRequestOptions{BundleName="teleporter-indicator-lab"};
  objectiveLocator=new ResourceLocationMap("composed-teleporter");objectiveLocator.Add(cfg.teleporterIndicatorKey,new ResourceLocationBase(cfg.teleporterIndicatorKey,cfg.teleporterIndicatorAsset,typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));Addressables.AddResourceLocator(objectiveLocator);
  var uiBundle=new ResourceLocationBase("objective-ui-lab",System.IO.Path.Combine(Application.persistentDataPath,"payload","objective-ui-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));uiBundle.Data=new AssetBundleRequestOptions{BundleName="objective-ui-lab"};
  objectiveLocator.Add(cfg.objectiveTMPSettingsKey,new ResourceLocationBase(cfg.objectiveTMPSettingsKey,cfg.objectiveTMPSettingsAsset,typeof(BundledAssetProvider).FullName,typeof(TMPro.TMP_Settings),uiBundle));
  objectiveTMPField=typeof(TMPro.TMP_Settings).GetField("s_Instance",BindingFlags.Static|BindingFlags.NonPublic);priorObjectiveTMP=objectiveTMPField.GetValue(null);Check(priorObjectiveTMP==null,"Unowned original text settings");
  objectiveTMPLease=LegacyResourcesAPI.LoadAsync<TMPro.TMP_Settings>("TMP Settings");ownsObjectiveTMP=true;yield return objectiveTMPLease;objectiveTMPSettings=objectiveTMPLease.Result;Check(objectiveTMPSettings,"Original text settings source missing");
  objectiveTMPField.SetValue(null,objectiveTMPSettings);Check(TMPro.TMP_Settings.defaultStyleSheet&&TMPro.TMP_Settings.defaultFontAsset,"Original text settings style/font closure missing");
  var support=PrepareObjectiveSupport(cfg);while(support.MoveNext())yield return support.Current;
  // Recover the source indicator through the original provider before TeleporterInteraction.Awake.
  objectiveIndicatorLease=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/PositionIndicators/TeleporterChargingPositionIndicator");ownsObjectiveIndicator=true;yield return objectiveIndicatorLease;objectiveIndicatorSource=objectiveIndicatorLease.Result;Check(objectiveIndicatorSource,"Original charging indicator source absent");foreach(var text in objectiveIndicatorSource.GetComponentsInChildren<TMPro.TMP_Text>(true))text.enabled=false;objectiveIndicatorReferences=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveIndicatorLease);
  if(!objectiveHoldoutInitialized){StaticCall(typeof(HoldoutZoneController),"Init");objectiveHoldoutInitialized=true;}
  PrepareStageTransport(cfg);EnableStageMapZones();var spawn=SpawnStageObjective(cfg);while(spawn.MoveNext())yield return spawn.Current;
 }
 IEnumerator SpawnStageObjective(Result cfg){
  r.objective=new ObjectiveReport{rules=true,ruleCount=RuleCatalog.ruleCount,scope="Original teleporter combat/holdout/rewards/exit; Android layout/context/presentation. Optional reward collection is recorded separately. No skipped combat, forced charge, currency or platform success."};objectiveState=null;objectiveRewardApproachAt=-1;
  Check(!Stage.instance,"Unowned stage lifecycle");objectiveStageHost=new GameObject("Owned Android stage coordinator");objectiveStageHost.SetActive(false);objectiveStageHost.AddComponent<NetworkIdentity>();objectiveStage=objectiveStageHost.AddComponent<Stage>();
  typeof(Stage).GetProperty("sceneDef").SetValue(objectiveStage,SceneCatalog.GetSceneDefForCurrentScene());Call(objectiveStage,"OnEnable");Check(Stage.instance==objectiveStage,"Original stage singleton absent");
  var origin=worldPlayer.characterMotor.Motor.TransientPosition;RaycastHit hit;Check(Physics.Raycast(origin+Vector3.forward*10+Vector3.up*20,Vector3.down,out hit,50,LayerIndex.world.mask,QueryTriggerInteraction.Ignore),"Objective placement has no source floor");
  var primordial=SceneCatalog.GetSceneDefForCurrentScene().cachedName=="skymeadow";var objectiveSource=artifactBundle.LoadAsset<GameObject>(primordial?cfg.lunarTeleporterAsset:cfg.teleporterAsset);Check(objectiveSource,"Original stage teleporter source missing");objectiveHost=Instantiate(objectiveSource,worldStaging.transform);objectiveHost.name=objectiveSource.name;
  Check(objectiveHost.GetComponentsInChildren<Component>(true).All(x=>x),"Original teleporter serialized component missing");
  foreach(var behaviour in objectiveHost.GetComponentsInChildren<MonoBehaviour>(true)){
   if(behaviour.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(behaviour);continue;}
   // Whole source objective callbacks run. Optional native presentation is explicitly unavailable.
   if(behaviour is SfxLocator||behaviour.GetType().Name=="PostProcessDuration"||behaviour.GetType().Name=="WwiseSound")behaviour.enabled=false;
  }
  worldTeleporter=objectiveHost.GetComponent<TeleporterInteraction>();Check(worldTeleporter&&!worldTeleporter.skipCombat&&worldTeleporter.bossDirector&&worldTeleporter.bonusDirector,"Original objective combat contract absent");
  var rewardGroup=objectiveHost.GetComponent<BossGroup>();Check(rewardGroup,"Original objective BossGroup component absent");
  rewardGroup.dropTable=ObjectiveDropTable(rewardGroup.dropTable);
  foreach(var table in objectiveDropTables.Values)Call(table,"Regenerate",Run.instance);
  Check(rewardGroup.dropTable&&rewardGroup.dropTable.GetPickupCount()>0&&objectiveDropTables.Values.All(x=>x.GetPickupCount()>0),"Original objective reward tables have no available pickups");
  r.objective.rewardTables=objectiveDropTables.Values.Select(x=>x.name+"|"+x.GetPickupCount()).ToArray();
  objectiveBossDeck=Instantiate(automaticDeck);var queen=objectiveCards.Single(x=>x.name=="cscBeetleQueen");var category=objectiveBossDeck.categories[0];var bossCard=category.cards[0];bossCard.spawnCard=queen;bossCard.selectionWeight=1;category.name="Champions";category.selectionWeight=2;category.cards=new[]{bossCard};objectiveBossDeck.categories=new[]{category};
  worldTeleporter.bossDirector.onSpawnedServer.AddListener(QueueObjectiveDirectorActor);
  worldTeleporter.bossDirector.monsterCards=objectiveBossDeck;worldTeleporter.bonusDirector.monsterCards=automaticDeck;
  worldTeleporter.bonusDirector.onSpawnedServer.AddListener(obj=>{RecordRewardSpawn(obj);RecordDirectorActor(obj,worldPlayer);});
  var model=objectiveHost.GetComponent<ModelLocator>().modelTransform;worldModels.Add(model);PresentWorldModel(model,false,true);
  objectiveBeacon=objectiveHost.GetComponentsInChildren<Collider>(true).Single(x=>x.GetComponent<EntityLocator>()&&x.GetComponent<EntityLocator>().entity==objectiveHost);Check(objectiveBeacon.gameObject.layer==LayerIndex.defaultLayer.intVal,"Original teleporter interaction layer changed");
  if(!objectiveSubscribed)objectiveDefeated=group=>{if(worldTeleporter&&group==worldTeleporter.bossGroup){r.objective.bossDefeated=true;r.objective.rewardPickupBaseline=r.world.pickupMessages;Save();}};
  if(!objectiveSubscribed)objectiveBeginExit=exit=>{if(worldTeleporter&&exit==worldTeleporter.sceneExitController){r.objective.exitBegan=true;Save();}};
  if(!objectiveSubscribed)objectiveFinishExit=exit=>{if(worldTeleporter&&exit==worldTeleporter.sceneExitController){r.objective.exitFinished=true;Save();}};
  if(!objectiveSubscribed){BossGroup.onBossGroupDefeatedServer+=objectiveDefeated;SceneExitController.onBeginExit+=objectiveBeginExit;SceneExitController.onFinishExit+=objectiveFinishExit;objectiveSubscribed=true;}
  objectiveHost.transform.position=hit.point;objectiveHost.transform.SetParent(null,true);objectiveHost.SetActive(true);NetworkServer.Spawn(objectiveHost);yield return null;
  Check(TeleporterInteraction.instance==worldTeleporter&&worldTeleporter.holdoutZoneController&&worldTeleporter.bossGroup&&Run.instance.nextStageScene,"Original objective Awake/Start context incomplete");
  objectiveIndicatorConsumers++; // Original Awake takes one synchronous source lease per teleporter.
  Check(worldTeleporter.isIdle&&worldTeleporter.GetInteractability(worldPlayer.GetComponent<Interactor>())==Interactability.Available,"Original teleporter idle/interaction state missing");
  r.objective.sourceDuration=worldTeleporter.holdoutZoneController.baseChargeDuration;r.objective.sourceRadius=worldTeleporter.holdoutZoneController.baseRadius;r.objective.position=objectiveHost.transform.position;r.objective.ready=true;ObserveTeleporterWorld();Save();
 }
 void ObserveTeleporterWorld(){
  FlushObjectiveActors();ObserveObjectiveSupport();if(!worldTeleporter)return;var report=r.objective;report.frames++;report.state=worldTeleporter.activationState.ToString();if(report.state!=objectiveState){objectiveState=report.state;report.transitions.Add(report.state);Save();}
  report.fsmState=worldTeleporter.mainStateMachine.state==null?"uninitialized":worldTeleporter.mainStateMachine.state.GetType().FullName;report.idle=worldTeleporter.isIdle;report.available=worldTeleporter.GetInteractability(worldPlayer.GetComponent<Interactor>())==Interactability.Available;report.selected=worldDriver.currentInteractable==objectiveHost;report.authority=Util.HasEffectiveAuthority(worldTeleporter.GetComponent<NetworkIdentity>());
  report.charge=worldTeleporter.chargeFraction;report.radius=worldTeleporter.holdoutZoneController.currentRadius;report.charging|=worldTeleporter.isCharging;report.charged|=worldTeleporter.isCharged;report.finished|=worldTeleporter.isInFinalSequence;
  report.bossMembers=worldTeleporter.bossGroup.combatSquad.memberCount;report.bossHealth=worldTeleporter.bossGroup.totalObservedHealth;report.bossMaxHealth=worldTeleporter.bossGroup.totalMaxObservedMaxHealth;report.credits=worldTeleporter.bossDirector.monsterCredit;report.spent=worldTeleporter.bossDirector.totalCreditsSpent;report.exitState=typeof(SceneExitController).GetField("exitState",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(worldTeleporter.sceneExitController).ToString();var destination=worldTeleporter.sceneExitController.useRunNextStageScene?Run.instance.nextStageScene:worldTeleporter.sceneExitController.destinationScene;report.nextScene=destination?destination.cachedName:"unavailable";
  report.bossDeaths=directorActors.Count(x=>x.report.dead&&x.report.origin=="teleporter-director");
  if(report.bossDefeated){report.rewardPickupMessages=r.world.pickupMessages-report.rewardPickupBaseline;report.rewardCollected=report.rewardPickupMessages>0;}
 }
 IEnumerable<GenericPickupController> GrantableWorldPickups(CharacterBody player){
  return EjectionPickups().Where(x=>{var def=PickupCatalog.GetPickupDef(x.pickup.pickupIndex);return def!=null&&def.itemIndex!=ItemIndex.None&&def.coinValue==0&&x.GetInteractability(player.GetComponent<Interactor>())==Interactability.Available;});
 }
 bool ObjectiveWorldStimulus(CharacterBody player,NovaInputBridge bridge,float elapsed){
  if(!worldTeleporter||!r.objective.ready)return false;
  var delta=objectiveHost.transform.position-player.characterMotor.Motor.TransientPosition;
  var planar=new Vector2(delta.x,delta.z);bridge.movement=planar.magnitude>1?planar.normalized:Vector2.zero;
  // Charging completion does not remove surviving enemies. Loot/exit replay must
  // retain ordinary combat input when an add can still reach the player.
  if(!worldTeleporter.isIdle&&!worldTeleporter.isCharging){
   var threat=directorActors.Where(x=>x.body&&x.body.healthComponent.alive).OrderBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();
   if(threat!=null&&Vector3.Distance(threat.body.corePosition,player.corePosition)<35){ObjectiveCombatInput(player,bridge,elapsed,planar);r.world.objective="Clear surviving threats before reward and exit";return true;}
  }
  if(worldTeleporter.isCharged&&!r.objective.rewardCollected){if(objectiveRewardApproachAt<0)objectiveRewardApproachAt=elapsed;else if(elapsed-objectiveRewardApproachAt>=30)r.objective.rewardLeftBehind=true;}
  if(worldTeleporter.isCharged&&!r.objective.rewardCollected&&!r.objective.rewardLeftBehind){
   var pickup=GrantableWorldPickups(player).OrderBy(x=>Vector3.Distance(x.transform.position,player.corePosition)).FirstOrDefault();
   if(!pickup){bridge.movement=Vector2.zero;r.world.objective="Wait for original boss reward";return true;}
   NavigateWorldInput(player,bridge,pickup.transform.position,.6f,pickup.name,elapsed);
   var collider=pickup.GetComponentsInChildren<Collider>(true).FirstOrDefault(x=>x.enabled&&(LayerIndex.CommonMasks.interactable.value&(1<<x.gameObject.layer))!=0);
   var pickupAim=(collider?collider.bounds.center:pickup.transform.position)-player.inputBank.aimOrigin;bridge.aim=new Vector2(pickupAim.x,pickupAim.z).normalized;bridge.diagnosticAim=pickupAim.normalized;
   if(worldDriver.currentInteractable==pickup.gameObject&&elapsed-worldLastPress>.5f){bridge.diagnosticInteract=true;worldLastPress=elapsed;}
   r.world.objective="Collect original boss reward";return true;
  }
  if(worldTeleporter.isIdle||worldTeleporter.isCharged){
   NavigateWorldInput(player,bridge,objectiveHost.transform.position,1,objectiveHost.name,elapsed);
   // Travelling to an objective must not disable normal self-defence. Interaction
   // wins when the original selector is ready; otherwise clear nearby attackers.
   var nearby=directorActors.Where(x=>x.body&&x.body.healthComponent.alive).OrderBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();
   if(worldDriver.currentInteractable!=objectiveHost&&nearby!=null&&Vector3.Distance(nearby.body.corePosition,player.corePosition)<20){ObjectiveCombatInput(player,bridge,elapsed,planar,false);r.world.objective="Clear nearby threats while approaching teleporter";return true;}
   var aim=objectiveBeacon.bounds.center-player.inputBank.aimOrigin;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticAim=aim.normalized;
   if(worldDriver.currentInteractable==objectiveHost&&elapsed-worldLastPress>.5f){bridge.diagnosticInteract=true;worldLastPress=elapsed;}
  }else{
   ObjectiveCombatInput(player,bridge,elapsed,planar);
  }
  r.world.objective=worldTeleporter.isIdle?"Activate teleporter":worldTeleporter.isCharging?"Defeat boss and charge teleporter":worldTeleporter.isCharged?"Collect reward and exit":"Prepare next stage";
  return true;
 }
 void ObjectiveCombatInput(CharacterBody player,NovaInputBridge bridge,float elapsed,Vector2 planar,bool constrainToHoldout=true){
   var actors=directorActors.Where(x=>x.body&&x.body.healthComponent.alive&&InsideSourceStageBounds(DirectorPhysicsPosition(x.body))).ToArray();
   var nearest=actors.OrderBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();
   // The whole-run capture records lethal nearby guard slams while the input
   // driver aims at other adds. Choose that immediate threat before distant adds.
   var guardIndex=BodyCatalog.FindBodyIndex("BeetleGuardBody");
   var enemy=actors.OrderBy(x=>x.body.bodyIndex==guardIndex&&Vector3.Distance(x.body.corePosition,player.corePosition)<25?0:worldTeleporter.bossGroup.combatSquad.readOnlyMembersList.Contains(x.master)?2:1).ThenBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();
   if(enemy!=null){
    var fromThreat=player.characterMotor.Motor.TransientPosition-nearest.body.characterMotor.Motor.TransientPosition;fromThreat.y=0;float distance=fromThreat.magnitude;
    float safeDistance=20;
    Vector2 desired=distance<safeDistance?new Vector2(fromThreat.x,fromThreat.z).normalized:distance>safeDistance+12?-new Vector2(fromThreat.x,fromThreat.z).normalized:new Vector2(fromThreat.z,-fromThreat.x).normalized;
    if(constrainToHoldout&&planar.magnitude>50)desired=planar.normalized;
    SelectCombatMotion(player,bridge,desired,actors,distance<safeDistance);
    r.world.combatTarget=enemy.body.name;
    bool evade=distance<16;bridge.diagnosticSprint=evade;bridge.DiagnosticJump(elapsed%1.8f<.25f);
    bridge.diagnosticUtility=evade&&player.skillLocator.utility.CanExecute();
    var aim=enemy.body.corePosition-player.inputBank.aimOrigin;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticAim=aim.normalized;bridge.diagnosticPrimary=true;bridge.diagnosticSecondary=elapsed%4<.2f;bridge.diagnosticSpecial=elapsed%10<.2f;
   }
 }
 void SelectCombatMotion(CharacterBody player,NovaInputBridge bridge,Vector2 desired,DirectorActor[] threats,bool escape){
  // Input-only terrain selection. Compare ground to ground, including while
  // jumping; the old capsule-position comparison rejected all four directions.
  var solver=player.characterMotor.Motor;var origin=solver.TransientPosition;RaycastHit floor;
  r.world.combatMotionSamples++;bridge.movement=Vector2.zero;r.world.combatMotion=Vector2.zero;
  if(!Physics.Raycast(origin+Vector3.up*.25f,Vector3.down,out floor,24,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||floor.collider.gameObject.scene!=stageGeometryScene){r.world.combatMotionBlocked++;return;}
  var baseline=solver.GroundingStatus.IsStableOnGround?solver.GroundingStatus.GroundPoint:floor.point;r.world.combatGround=baseline;
  if(desired.sqrMagnitude<.01f)desired=Vector2.right;desired.Normalize();var perpendicular=new Vector2(desired.y,-desired.x);
  var choices=new[]{desired,(desired+perpendicular).normalized,perpendicular,(-desired+perpendicular).normalized,-desired,(-desired-perpendicular).normalized,-perpendicular,(desired-perpendicular).normalized};
  float best=float.NegativeInfinity;
  foreach(var choice in choices)foreach(float length in new[]{2f,4f}){
   RaycastHit ground;var ahead=baseline+new Vector3(choice.x,0,choice.y)*length;
   if(!Physics.Raycast(ahead+Vector3.up*4,Vector3.down,out ground,9,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||ground.collider.gameObject.scene!=stageGeometryScene||ground.normal.y<=.75f||Mathf.Abs(ground.point.y-baseline.y)>=2||!InsideSourceStageBounds(ground.point))continue;
   if(Physics.Linecast(baseline+Vector3.up,ground.point+Vector3.up,LayerIndex.world.mask,QueryTriggerInteraction.Ignore))continue;
   float score=Vector2.Dot(choice,desired)*4;
   if(escape)score+=threats.Min(x=>Vector3.Distance(ground.point,DirectorPhysicsPosition(x.body)));
   if(score<=best)continue;best=score;bridge.movement=choice;r.world.combatDestination=ground.point;
  }
  r.world.combatMotion=bridge.movement;if(bridge.movement==Vector2.zero)r.world.combatMotionBlocked++;
 }
 void CleanupTeleporterWorld(){CleanupMoonMission();CleanupStageTransport();
  if(objectiveSummon!=null)MasterSummon.onServerMasterSummonGlobal-=objectiveSummon;pendingObjectiveActors.Clear();objectiveAmbientExpected.Clear();objectiveDirectorActors.Clear();
  if(objectiveSubscribed){BossGroup.onBossGroupDefeatedServer-=objectiveDefeated;SceneExitController.onBeginExit-=objectiveBeginExit;SceneExitController.onFinishExit-=objectiveFinishExit;objectiveSubscribed=false;}
  ObserveObjectiveSupport(true);CleanupObjectiveEffects();CleanupObjectiveSupport();if(objectiveHost)NetworkServer.Destroy(objectiveHost);if(objectiveBossDeck)Destroy(objectiveBossDeck);
  if(objectiveStage){Call(objectiveStage,"OnDisable");Destroy(objectiveStageHost);}
  foreach(var resource in objectiveResources)if(resource)Destroy(resource);objectiveDropTables.Clear();foreach(var card in objectiveCards)if(card)Destroy(card);
  if(ownsObjectiveIndicator&&objectiveIndicatorLease.IsValid()){int extra=(int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveIndicatorLease)-objectiveIndicatorReferences;Check(extra>=0&&extra<=objectiveIndicatorConsumers,"Unattributed teleporter indicator leases");for(int i=0;i<extra;i++)Addressables.Release(objectiveIndicatorSource);Addressables.Release(objectiveIndicatorLease);ownsObjectiveIndicator=false;objectiveIndicatorSource=null;}
  if(ownsObjectiveTMP){objectiveTMPField.SetValue(null,priorObjectiveTMP);if(objectiveTMPLease.IsValid())Addressables.Release(objectiveTMPLease);ownsObjectiveTMP=false;objectiveTMPSettings=null;}
  if(objectiveLocator!=null){Addressables.RemoveResourceLocator(objectiveLocator);objectiveLocator=null;}
 }
 void CleanupObjectiveConfigs(){foreach(var pair in objectiveStaticFields)pair.Key.SetValue(null,pair.Value);objectiveStaticFields.Clear();foreach(var config in objectiveConfigs)if(config)Destroy(config);objectiveConfigs.Clear();}
}
