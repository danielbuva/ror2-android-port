using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using RoR2;
using RoR2.CharacterAI;
using RoR2.Navigation;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Original actor/AI/input/state/physics. Only owned audio/visual binding and diagnostic placement.
public sealed partial class MovementBatchProbe {
 [Serializable] public class EnemyReport {
  public bool graphReady,spawned,linked,authority,targetFound,dead,cleaned,naturalBodyDestroyed,naturalMasterDestroyed,preservedCorpseObserved;
  public int groundNodes,airNodes,aiFrames,headbutts,enemyDamageEvents,playerDamageEvents,groundedFrames,groundedBeforeDamage,collisionMask,stableMask,deathGlobalEvents,playerKillsBefore,playerKillsAfter;
  public float pathLength,planarPathLength,planarBeforeDamage,maxFall,maxFallBeforeDamage,maxIncomingForce,health,playerHealth,damageToEnemy,damageToPlayer;public string aiState,bodyState;public Vector3 position,spawnPosition,velocity;public string[] excludedCallbacks;
 }
 GameObject enemyTemplates,enemyMasterHost,enemySceneHost;CharacterMaster enemyMaster;CharacterBody enemyBody,enemyPlayer;
 BaseAI enemyAI;Material enemyMaterial;SurfaceDef enemySurface;EntityState priorEnemyState;Vector3 priorEnemyPosition;GameObject enemyDetachedModel;
 readonly List<EntityStateConfiguration> enemyConfigs=new List<EntityStateConfiguration>();
 readonly Dictionary<FieldInfo,object> enemyStaticFields=new Dictionary<FieldInfo,object>();
 EliteDef[] priorEnemyElites;EliteIndex[] priorEnemyEliteList;bool ownsEnemyElites;
 void BindEnemyDefinition(Type holder,string name,UnityEngine.Object value){var field=holder.GetField(name);Check(field!=null&&field.GetValue(null)==null&&value,"Existing or missing enemy death definition "+name);enemyStaticFields[field]=null;field.SetValue(null,value);}
 ArtifactDef[] EnemyArtifacts(Result cfg,ArtifactDef fall){if(!cfg.enemySpine)return new[]{fall};var wisp=artifactBundle.LoadAsset<ArtifactDef>(cfg.enemyWispArtifactAsset);Check(wisp&&wisp.cachedName=="WispOnDeath","Original death artifact missing");BindEnemyDefinition(typeof(RoR2Content.Artifacts),"WispOnDeath",wisp);if(!cfg.automaticDirector)return new[]{fall,wisp};var honor=artifactBundle.LoadAsset<ArtifactDef>(cfg.enemyHonorArtifactAsset);Check(honor&&honor.cachedName=="EliteOnly","Original Honor artifact missing");BindEnemyDefinition(typeof(RoR2Content.Artifacts),"EliteOnly",honor);return new[]{fall,wisp,honor};}
 void PrepareEnemyElites(Result cfg){
  var field=typeof(EliteCatalog).GetField("eliteDefs",BindingFlags.NonPublic|BindingFlags.Static);priorEnemyElites=(EliteDef[])field.GetValue(null);priorEnemyEliteList=EliteCatalog.eliteList.ToArray();Check((priorEnemyElites==null||priorEnemyElites.Length==0)&&priorEnemyEliteList.Length==0,"Existing elite catalog");
  var names=new[]{"Poison","Haunted","Lunar","Void"};var defs=cfg.enemyEliteAssets.Select(x=>artifactBundle.LoadAsset<EliteDef>(x)).ToArray();Check(defs.Length==4,"Measured death elite definitions missing");for(int i=0;i<4;i++){Check(defs[i]&&defs[i].name=="ed"+names[i],"Original elite identity");BindEnemyDefinition(i==3?typeof(DLC1Content.Elites):typeof(RoR2Content.Elites),names[i],defs[i]);}
  ownsEnemyElites=true;StaticCall(typeof(EliteCatalog),"SetEliteDefs",new object[]{defs});foreach(var def in defs)Check(def.eliteIndex!=EliteIndex.None&&EliteCatalog.GetEliteDef(def.eliteIndex)==def,"Original elite catalog identity");
 }
 BuffDef[] EnemyDeathBuffs(Result cfg){if(!cfg.enemySpine)return new BuffDef[0];var def=artifactBundle.LoadAsset<BuffDef>(cfg.enemyDeathBuffAsset);Check(def&&def.name=="bdExtraLifeBuff","Original death buff missing");BindEnemyDefinition(typeof(DLC2Content.Buffs),"ExtraLifeBuff",def);return new[]{def};}
 EquipmentDef[] EnemyDeathEquipment(Result cfg){if(!cfg.enemySpine)return new EquipmentDef[0];var names=new[]{"HealAndRevive","HealAndReviveConsumed"};var defs=cfg.enemyDeathEquipment.Select(x=>artifactBundle.LoadAsset<EquipmentDef>(x)).ToArray();for(int i=0;i<2;i++){Check(defs[i]&&defs[i].name==names[i],"Original death equipment missing");BindEnemyDefinition(typeof(DLC2Content.Equipment),names[i],defs[i]);}if(cfg.originalMoneyCost){var card=artifactBundle.LoadAsset<EquipmentDef>(cfg.multiShopCardAsset);Check(card&&card.name=="MultiShopCard","Original money-cost comparison equipment missing");BindEnemyDefinition(typeof(DLC1Content.Equipment),"MultiShopCard",card);return defs.Concat(new[]{card}).ToArray();}return defs;}
 Type[] EnemyTypes(){return new[]{typeof(EntityStates.BeetleMonster.SpawnState),typeof(EntityStates.BeetleMonster.HeadbuttState),typeof(EntityStates.AI.Walker.Wander),typeof(EntityStates.AI.Walker.Combat),typeof(EntityStates.AI.Walker.LookBusy),typeof(EntityStates.AI.Walker.Guard),typeof(GenericCharacterDeath),typeof(HurtState),typeof(HurtStateFlyer),typeof(StunState),typeof(SleepState),typeof(EntityStates.Emote.SurpriseState),typeof(EntityStates.EmotePoint)};}
 EntityStateConfiguration[] PrepareEnemyConfigs(Result cfg){
  r.enemy=new EnemyReport();foreach(var type in EnemyTypes())foreach(var field in type.GetFields(BindingFlags.Public|BindingFlags.Static|BindingFlags.DeclaredOnly))if(!field.IsInitOnly&&!field.IsLiteral)enemyStaticFields[field]=field.GetValue(null);
  foreach(var path in new[]{cfg.enemySpawnConfigAsset,cfg.enemyAttackConfigAsset,cfg.enemySleepConfigAsset}){
   var original=artifactBundle.LoadAsset<EntityStateConfiguration>(path);Check(original,"Original enemy state configuration missing");var copy=Instantiate(original);copy.serializedFieldsCollection.serializedFields=original.serializedFieldsCollection.serializedFields.ToArray();
   for(int i=0;i<copy.serializedFieldsCollection.serializedFields.Length;i++){
    var field=copy.serializedFieldsCollection.serializedFields[i];if(field.fieldName.IndexOf("sound",StringComparison.OrdinalIgnoreCase)>=0)copy.serializedFieldsCollection.serializedFields[i].fieldValue.stringValue="";
    if(field.fieldName.IndexOf("effect",StringComparison.OrdinalIgnoreCase)>=0)copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue=null;
   }
   enemyConfigs.Add(copy);
  }
  return enemyConfigs.ToArray();
 }
 void EnemyExclusions(){EntityStates.BeetleMonster.HeadbuttState.attackSoundString="";EntityStates.BeetleMonster.HeadbuttState.hitEffectPrefab=null;StunState.stunVfxPrefab=null;}
 IEnumerator PrepareEnemy(CharacterBody player,Result cfg){
  enemyPlayer=player;PrepareEnemyElites(cfg);if(cfg.enemyRewards){var rewards=PrepareEnemyRewards(player,cfg);while(rewards.MoveNext())yield return rewards.Current;}Check(RunArtifactManager.instance&&RoR2Content.Artifacts.WispOnDeath,"Original enemy death artifact context missing");Check(!RunArtifactManager.instance.IsArtifactEnabled(RoR2Content.Artifacts.WispOnDeath),"Enemy fixture requires original disabled death artifact");r.phase="enemy-navigation-context";Save();Check(!SceneInfo.instance,"Existing original SceneInfo context");
  enemySceneHost=new GameObject("Owned original SceneInfo");enemySceneHost.SetActive(false);SceneManager.MoveGameObjectToScene(enemySceneHost,stageGeometryScene);
  var sceneInfo=enemySceneHost.AddComponent<SceneInfo>();typeof(SceneInfo).GetField("groundNodesAsset",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(sceneInfo,artifactBundle.LoadAsset<NodeGraph>(cfg.enemyGroundGraphAsset));typeof(SceneInfo).GetField("airNodesAsset",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(sceneInfo,artifactBundle.LoadAsset<NodeGraph>(cfg.enemyAirGraphAsset));
  enemySceneHost.SetActive(true);yield return null;r.enemy.groundNodes=sceneInfo.groundNodes.GetNodeCount();r.enemy.airNodes=sceneInfo.airNodes.GetNodeCount();r.enemy.graphReady=SceneInfo.instance==sceneInfo&&r.enemy.groundNodes>0&&r.enemy.airNodes>0;Check(r.enemy.graphReady,"Original navigation context missing");
  enemyTemplates=new GameObject("Owned inactive enemy templates");enemyTemplates.SetActive(false);
  var originalBody=artifactBundle.LoadAsset<GameObject>(cfg.enemyBodyAsset);var bodyTemplate=Instantiate(originalBody,enemyTemplates.transform);bodyTemplate.name=originalBody.name;bodyTemplate.SetActive(true);
  r.phase="enemy-template-binding";Save();var templateBody=bodyTemplate.GetComponent<CharacterBody>();var locator=bodyTemplate.GetComponent<ModelLocator>();Check(templateBody&&locator&&locator.modelTransform,"Original enemy template components missing");var model=locator.modelTransform;var animator=model.GetComponent<Animator>();Check(animator,"Original enemy animator missing");animator.avatar=artifactBundle.LoadAsset<Avatar>(cfg.enemyAvatarAsset);animator.runtimeAnimatorController=artifactBundle.LoadAsset<RuntimeAnimatorController>(cfg.enemyControllerAsset);animator.applyRootMotion=false;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
  Check(animator.avatar&&animator.runtimeAnimatorController,"Original enemy avatar/controller missing");
  foreach(var component in bodyTemplate.GetComponentsInChildren<MonoBehaviour>(true)){
   if(component.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(component);continue;}
   if(component is DeathRewards){if(cfg.enemyRewards)((DeathRewards)component).logUnlockableDef=null;else{DestroyImmediate(component);continue;}} // Reward/XP/drop producers are the next integration, not this empty-inventory actor fixture.
   // Same limited empty-inventory/local-server scope as the accepted player. These measured
   // callbacks require unprovided platform-clock, pause or equipment catalog contracts.
   if(component is RoR2.Networking.CharacterNetworkTransform||component is InteractionDriver||component is EquipmentSlot)component.enabled=false;
   // Root gameplay callbacks remain original; inactive visual observers must not initiate new loaders.
   if(component.transform!=bodyTemplate.transform)component.enabled=component is HurtBox||component is HurtBoxGroup||component is HitBox||component is HitBoxGroup||component is RootMotionAccumulator;
  }
  var sfx=templateBody.GetComponent<SfxLocator>();foreach(var field in typeof(SfxLocator).GetFields(BindingFlags.Public|BindingFlags.Instance))if(field.FieldType==typeof(string))field.SetValue(sfx,null);
  var sourceMaterial=artifactBundle.LoadAsset<Material>(cfg.enemyMaterialAsset);enemyMaterial=new Material(sourceMaterial);enemyMaterial.shader=Resources.Load<Shader>("CommandoMaterialPreview");enemyMaterial.shaderKeywords=new string[0];enemyMaterial.SetTexture("_MainTex",sourceMaterial.GetTexture("_MainTex"));enemyMaterial.SetColor("_Color",sourceMaterial.GetColor("_Color")*2);enemyMaterial.SetFloat("_EmissionEnabled",0); // Opaque diagnostic preview; source alpha is not a cutout contract.
  foreach(var renderer in model.GetComponentsInChildren<Renderer>(true)){renderer.gameObject.layer=30;renderer.sharedMaterial=enemyMaterial;var skin=renderer as SkinnedMeshRenderer;if(skin){Check(skin.sharedMesh&&skin.sharedMesh.vertexCount>0&&(skin.bones.Length>0||(!animator.hasTransformHierarchy&&animator.avatar.isValid&&skin.sharedMesh.bindposes.Length>0)),"Original enemy skin/optimized-avatar contract missing");skin.updateWhenOffscreen=true;}}
  var characterModel=model.GetComponent<CharacterModel>();characterModel.visibility=VisibilityLevel.Invisible; // Its camera/overlay Start is excluded; original OnDeath may hide owned preview renderers without uninitialized/native RTPC work.
  for(int i=0;i<characterModel.baseRendererInfos.Length;i++)characterModel.baseRendererInfos[i].defaultMaterial=enemyMaterial;
  var surfaces=bodyTemplate.GetComponentsInChildren<SurfaceDefProvider>(true);Check(surfaces.Length>0&&surfaces.All(x=>x.surfaceDef==surfaces[0].surfaceDef),"Original enemy impact surface identity missing");enemySurface=Instantiate(surfaces[0].surfaceDef);enemySurface.impactEffectPrefab=null;if(cfg.integratedWorld)enemySurface.impactSoundString=null;foreach(var surface in surfaces)surface.surfaceDef=enemySurface;
  GlobalEventManager.onServerDamageDealt+=EnemyDamage;GlobalEventManager.onCharacterDeathGlobal+=EnemyDeath;r.enemy.playerKillsBefore=player.killCountServer;
  r.enemy.excludedCallbacks=new[]{"CharacterNetworkTransform platform snapshot clock","InteractionDriver pause/interaction context","EquipmentSlot targeting catalogs",cfg.enemyRewards?"Inventory automatic equipment refresh (only original UseAmbientLevel)":"Inventory automatic equipment refresh (empty inventory only)",cfg.enemyRewards?"Optional logbook/profile drop":"DeathRewards gold/XP/drop producers"};
  var position=player.transform.position+Vector3.forward*9;RaycastHit ground;Check(Physics.Raycast(position+Vector3.up*20,Vector3.down,out ground,50,LayerIndex.world.mask,QueryTriggerInteraction.Ignore),"Original terrain enemy spawn floor missing");position=ground.point+Vector3.up*2;
  r.phase="original-enemy-master-spawn";Save();
  if(cfg.enemyRewards){var spawning=SpawnRewardEnemy(bodyTemplate,position,player,cfg);while(spawning.MoveNext())yield return spawning.Current;}
  else{
   enemyMasterHost=Instantiate(artifactBundle.LoadAsset<GameObject>(cfg.enemyMasterAsset));enemyMasterHost.GetComponent<Inventory>().enabled=false;enemyMasterHost.SetActive(true);enemyMaster=enemyMasterHost.GetComponent<CharacterMaster>();Check(enemyMaster.inventory.itemAcquisitionOrder.Count==0&&enemyMaster.inventory.currentEquipmentIndex==EquipmentIndex.None,"Enemy callback exclusion requires original empty inventory");enemyMaster.teamIndex=TeamIndex.Monster;NetworkServer.Spawn(enemyMasterHost);enemyMaster.bodyPrefab=bodyTemplate;
   enemyBody=enemyMaster.SpawnBody(position,Quaternion.LookRotation(player.transform.position-position));
  }
  Check(enemyBody,"Original enemy spawn failed");enemyAI=enemyMasterHost.GetComponent<BaseAI>();priorEnemyPosition=enemyBody.transform.position;
  r.enemy.spawned=true;r.enemy.linked=enemyMaster.GetBody()==enemyBody&&enemyBody.master==enemyMaster;Check(r.enemy.linked,"Original enemy master/body linkage failure");
  r.phase="enemy-await-original-start";Save();yield return null;r.enemy.authority=enemyBody.isServer&&enemyBody.hasEffectiveAuthority;Check(r.enemy.authority,"Original enemy authority after Start missing");Check(enemyAI.body==enemyBody,"Original AI OnBodyStart did not adopt body");if(cfg.enemyRewards){r.rewards.spawnLevelAfterStart=enemyBody.level;Check(enemyBody.level==1,"Original directed enemy stats after Start failed");}
  // The lab collision matrix is not the original project's matrix. Use the accepted
  // recovered-world-only collision scope, including both actors' own hurtbox exclusions.
  var solver=enemyBody.characterMotor.Motor;solver.CollidableLayers=LayerIndex.world.mask;solver.StableGroundLayers=LayerIndex.world.mask;solver.SetGroundSolvingActivation(true);r.enemy.collisionMask=solver.CollidableLayers;r.enemy.stableMask=solver.StableGroundLayers;r.enemy.spawnPosition=enemyBody.transform.position;enemyDetachedModel=enemyBody.modelLocator.modelTransform.gameObject;r.phase="enemy-active";Save();
 }
 void EnemyDamage(DamageReport report){ObserveDirectorDamage(report);if(report.victimBody==enemyBody){r.enemy.enemyDamageEvents++;r.enemy.damageToEnemy+=report.damageDealt;r.enemy.maxIncomingForce=Mathf.Max(r.enemy.maxIncomingForce,report.damageInfo.force.magnitude);}if(report.victimBody==enemyPlayer){r.enemy.playerDamageEvents++;r.enemy.damageToPlayer+=report.damageDealt;}}
 void EnemyDeath(DamageReport report){ObserveDirectorDeath(report);if(report.victimBody==enemyBody)r.enemy.deathGlobalEvents++;}
 void ObserveEnemy(){
  ObserveEnemyRewards();ObserveOriginalNavigation();ObserveDirectorActors();
  if(enemyAI){r.enemy.aiFrames++;r.enemy.targetFound|=enemyAI.currentEnemy.characterBody==enemyPlayer;if(enemyAI.stateMachine.state!=null)r.enemy.aiState=enemyAI.stateMachine.state.GetType().FullName;}
  if(enemyBody){var state=EntityStateMachine.FindByCustomName(enemyBody.gameObject,"Body").state;if(state!=priorEnemyState&&state is EntityStates.BeetleMonster.HeadbuttState)r.enemy.headbutts++;priorEnemyState=state;r.enemy.bodyState=state==null?"null":state.GetType().FullName;r.enemy.position=enemyBody.transform.position;var delta=r.enemy.position-priorEnemyPosition;r.enemy.pathLength+=delta.magnitude;delta.y=0;r.enemy.planarPathLength+=delta.magnitude;r.enemy.maxFall=Mathf.Max(r.enemy.maxFall,r.enemy.spawnPosition.y-r.enemy.position.y);r.enemy.velocity=enemyBody.characterMotor.velocity;if(enemyBody.characterMotor.isGrounded)r.enemy.groundedFrames++;if(r.enemy.enemyDamageEvents==0){r.enemy.planarBeforeDamage+=delta.magnitude;r.enemy.maxFallBeforeDamage=r.enemy.maxFall;if(enemyBody.characterMotor.isGrounded)r.enemy.groundedBeforeDamage++;}priorEnemyPosition=r.enemy.position;r.enemy.health=enemyBody.healthComponent.health;r.enemy.dead|=!enemyBody.healthComponent.alive;}
  if(enemyPlayer){r.enemy.playerHealth=enemyPlayer.healthComponent.health;r.enemy.playerKillsAfter=enemyPlayer.killCountServer;}if(r.enemy.dead){r.enemy.naturalBodyDestroyed=!enemyBody;r.enemy.naturalMasterDestroyed=!enemyMasterHost;r.enemy.preservedCorpseObserved|=!enemyBody&&enemyDetachedModel&&enemyDetachedModel.GetComponent<Corpse>();}
 }
 void CleanupEnemy(){
  GlobalEventManager.onServerDamageDealt-=EnemyDamage;GlobalEventManager.onCharacterDeathGlobal-=EnemyDeath;if(enemyMasterHost)NetworkServer.Destroy(enemyMasterHost);if(enemyBody)NetworkServer.Destroy(enemyBody.gameObject);if(enemyDetachedModel)Destroy(enemyDetachedModel); // Original ModelLocator relinquishes a corpse on death; the bounded fixture still owns that detached object.
  CleanupDirectorActors();CleanupRewardHosts();if(enemySceneHost)Destroy(enemySceneHost);if(enemyTemplates)Destroy(enemyTemplates);if(enemyMaterial)Destroy(enemyMaterial);if(enemySurface)Destroy(enemySurface);
 }
 IEnumerator VerifyEnemyCleanup(){if(r.enemy==null)yield break;for(int i=0;i<3;i++)yield return null;var remaining=new[]{enemyMasterHost?"master":null,enemyBody?"body":null,enemyDetachedModel?"model/corpse":null,enemySceneHost?"scene context":null,enemyTemplates?"templates":null,enemyMaterial?"material":null,enemySurface?"surface":null,SceneInfo.instance?"SceneInfo singleton":null}.Where(x=>x!=null).ToArray();r.enemy.cleaned=remaining.Length==0;Check(r.enemy.cleaned,"Owned enemy destruction before provider release: "+string.Join(",",remaining));VerifyDirectorActorCleanup();Save();}
 void CleanupEnemyConfigs(){if(ownsEnemyElites){typeof(EliteCatalog).GetField("eliteDefs",BindingFlags.NonPublic|BindingFlags.Static).SetValue(null,priorEnemyElites);EliteCatalog.eliteList.Clear();EliteCatalog.eliteList.AddRange(priorEnemyEliteList);ownsEnemyElites=false;}foreach(var entry in enemyStaticFields)entry.Key.SetValue(null,entry.Value);enemyStaticFields.Clear();foreach(var cfg in enemyConfigs)if(cfg)Destroy(cfg);enemyConfigs.Clear();}
}
