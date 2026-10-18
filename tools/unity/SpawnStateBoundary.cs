// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareSpawnStateCatalog (SpawnStateSession); teardown CleanupSpawnConfig (Dispose: objective, enemy, spine, spawn config, then RestoreWholeStateOwnership).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using KinematicCharacterController;
using RoR2;
using UnityEngine;

public sealed partial class MovementBatchProbe {
 [Serializable] public class LiveCatalogReport {
  public int emptyPreloadKeys,projectiles,bodies,masters,adaptedMasters,skills,skillFamilies,emptySkillVariants,stateTypes,stateConfigurations,adaptedStateConfigurations,staticStateFields,preloadGUIDs;
  public string[] missingSourcePreloadKeys;
  public bool projectileCleanup,stateCleanup,bodySkillCleanup;public string scope="Native provider category membership and original catalog setters in the composed session; selected actor templates/configuration adaptations retained. Registration is not all-content gameplay acceptance.";
 }
 SpawnStateSession spawnStateSession;
 SpawnStateSession GetSpawnStateSession(){if(spawnStateSession==null)spawnStateSession=new SpawnStateSession(this);return spawnStateSession;}
 void CaptureWholeStateOwnership(EntityStateConfiguration[] configs){GetSpawnStateSession().CaptureWholeStateOwnership(configs);}
 int RemoveEmptyStatePreloadKeys(){return GetSpawnStateSession().RemoveEmptyStatePreloadKeys();}
 void RestoreWholeStateOwnership(){GetSpawnStateSession().RestoreWholeStateOwnership();}
 IEnumerator PrepareSpawnStateCatalog(SessionConfig cfg){return GetSpawnStateSession().PrepareSpawnStateCatalog(cfg);}
 void CleanupSpawnConfig(){GetSpawnStateSession().Dispose();}
 void ProbeSpawnStates(CharacterBody body,SessionConfig cfg){GetSpawnStateSession().ProbeSpawnStates(body,cfg);}
 static float SpawnedStateAge(EntityState state,string property){return SpawnStateSession.SpawnedStateAge(state,property);}
 void ProbeSpawnedMain(CharacterBody body,EntityStateMachine machine,SessionConfig cfg){GetSpawnStateSession().ProbeSpawnedMain(body,machine,cfg);}

 // Retain the owner for partial setup, repeated cleanup and later observations.
 // Dispose preserves cross-owner cleanup before spawn and native preload restoration.
 sealed class SpawnStateSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  readonly Dictionary<FieldInfo,object> wholeStateFields=new Dictionary<FieldInfo,object>();
  readonly Dictionary<FieldInfo,object> wholePreloadFields=new Dictionary<FieldInfo,object>();
  public SpawnStateSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public void CaptureWholeStateOwnership(EntityStateConfiguration[] configs){
   coordinator.Check(wholeStateFields.Count==0&&wholePreloadFields.Count==0,"Whole state fields already owned");
   foreach(var config in configs){var type=(Type)config.targetType;if(type==null)continue;foreach(var value in config.serializedFieldsCollection.serializedFields){
    var field=type.GetField(value.fieldName,BindingFlags.Public|BindingFlags.Static);
    if(field!=null&&!wholeStateFields.ContainsKey(field))wholeStateFields.Add(field,field.GetValue(null));
   }}
   foreach(var name in new[]{"preloadGUIDLocators","preloadGUIDs"}){var field=typeof(EntityStatePreloadCatalog).GetField(name,BindingFlags.NonPublic|BindingFlags.Static);wholePreloadFields.Add(field,field.GetValue(null));}
  }
  [Serializable] sealed class PreloadSourceDescriptor {public string[] missingSourcePreloadKeys;}
  public int RemoveEmptyStatePreloadKeys(){
   var flags=BindingFlags.NonPublic|BindingFlags.Static;var type=typeof(EntityStatePreloadCatalog);
   var locatorField=type.GetField("preloadGUIDLocators",flags);var guidField=type.GetField("preloadGUIDs",flags);
   var locators=((EntityStatePreloadCatalog.PreloadLocator[])locatorField.GetValue(null)).ToArray();var original=(string[])guidField.GetValue(null);
   var descriptor=JsonUtility.FromJson<PreloadSourceDescriptor>(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);
   var sourceMissing=new HashSet<string>(descriptor.missingSourcePreloadKeys??Array.Empty<string>(),StringComparer.Ordinal);
   var valid=new List<string>();var observedMissing=new HashSet<string>(StringComparer.Ordinal);int skipped=0;
   // Empty slots and keys absent from the exact shipped PC catalog cannot
   // preload. Keep every other native key and its state/locator ordering intact.
   for(int i=0;i<locators.Length;i++){var locator=locators[i];int start=valid.Count;
    if(locator.index<0||locator.totalPreloadItems<0||locator.index+locator.totalPreloadItems>original.Length)throw new Exception("Native preload locator outside owned array");
    for(int j=locator.index;j<locator.index+locator.totalPreloadItems;j++){
     var key=original[j];if(string.IsNullOrEmpty(key)){skipped++;continue;}
     if(sourceMissing.Contains(key)){
      IList<UnityEngine.ResourceManagement.ResourceLocations.IResourceLocation> locations;
      if(WholeCatalogLoader.locator.Locate(key,typeof(GameObject),out locations))throw new Exception("Source-missing preload unexpectedly resolves: "+key);
      observedMissing.Add(key);continue;
     }
     valid.Add(key);
    }
    locators[i]=new EntityStatePreloadCatalog.PreloadLocator{index=start,totalPreloadItems=valid.Count-start};
   }
   coordinator.r.liveCatalogs.missingSourcePreloadKeys=observedMissing.OrderBy(key=>key,StringComparer.Ordinal).ToArray();
   locatorField.SetValue(null,locators);guidField.SetValue(null,valid.ToArray());return skipped;
  }
  public void RestoreWholeStateOwnership(){
   foreach(var pair in wholeStateFields)pair.Key.SetValue(null,pair.Value);wholeStateFields.Clear();
   foreach(var pair in wholePreloadFields)pair.Key.SetValue(null,pair.Value);wholePreloadFields.Clear();
   if(coordinator.r.liveCatalogs!=null)coordinator.r.liveCatalogs.stateCleanup=EntityStateCatalog.entityStateCount==0;
  }
  bool ownsSpawnConfig;float priorSpawnDelay;string priorSpawnSound;
  public IEnumerator PrepareSpawnStateCatalog(SessionConfig cfg){
   coordinator.Check(!coordinator.ownsStateCatalog,"Existing state catalog ownership");
   var types=new[]{typeof(Uninitialized),typeof(Idle),typeof(SpawnTeleporterState),typeof(GenericCharacterMain),typeof(GenericCharacterVehicleSeated)};
   var flags=BindingFlags.NonPublic|BindingFlags.Static;
   coordinator.Check(((Type[])typeof(EntityStateCatalog).GetField("stateIndexToType",flags).GetValue(null)).Length==0&&((System.Collections.IDictionary)typeof(EntityStateCatalog).GetField("stateTypeToIndex",flags).GetValue(null)).Count==0&&((System.Collections.IDictionary)typeof(EntityStateCatalog).GetField("instanceFieldInitializers",flags).GetValue(null)).Count==0,"Existing state catalog; refuse replacement");
   var originals=coordinator.r.liveCatalogs!=null?WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.entityStateConfiguration,new EntityStateConfiguration[0]):null;
   if(originals!=null)CaptureWholeStateOwnership(originals);
   var config=coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.spawnConfigAsset);
   coordinator.Check(config&&(Type)config.targetType==typeof(SpawnTeleporterState),"Actual spawn configuration identity");
   priorSpawnDelay=SpawnTeleporterState.initialDelay;priorSpawnSound=SpawnTeleporterState.soundString;ownsSpawnConfig=true;
   var configs=new[]{config};if(coordinator.IsPlayableSpine()){types=types.Concat(new[]{typeof(EntityStates.Commando.CommandoWeapon.FirePistol2),typeof(EntityStates.Commando.CommandoWeapon.ReloadPistols)}).ToArray();configs=coordinator.PrepareSpineConfigs(cfg,config);}
   if(cfg.combatSpine)types=types.Concat(new[]{typeof(EntityStates.Commando.CommandoWeapon.FireFMJ),typeof(EntityStates.Commando.DodgeState),typeof(EntityStates.Commando.CommandoWeapon.FireBarrage)}).ToArray();
   if(cfg.enemySpine){types=types.Concat(coordinator.EnemyTypes()).Distinct().ToArray();configs=configs.Concat(coordinator.PrepareEnemyConfigs(cfg)).ToArray();}
   if(cfg.teleporterLoop){coordinator.r.objective=new ObjectiveReport{scope="Original teleporter combat/holdout/rewards/exit; Android layout/context/presentation. No skipped combat, forced charge, currency or platform success."};types=types.Concat(coordinator.ObjectiveTypes(cfg)).Distinct().ToArray();configs=configs.Concat(coordinator.PrepareObjectiveConfigs(cfg)).ToArray();}
   if(!string.IsNullOrEmpty(cfg.playerDeathEffectAsset))types=types.Concat(new[]{typeof(EntityStates.Commando.DeathState)}).Distinct().ToArray();
   if(cfg.barrelInteraction)types=types.Concat(new[]{typeof(EntityStates.Barrel.Opening),typeof(EntityStates.Barrel.Opened)}).Distinct().ToArray();
   if(cfg.worldChestBreadth!=null)types=types.Concat(coordinator.WorldChestTypes(cfg)).Distinct().ToArray();
   if(cfg.teleporterLoop)foreach(var actor in cfg.objectiveActors)foreach(var hurt in coordinator.artifactBundle.LoadAsset<GameObject>(actor.body).GetComponentsInChildren<SetStateOnHurt>(true).Where(x=>x.canBeHitStunned))coordinator.Check(hurt.hurtState.stateType!=null&&types.Contains(hurt.hurtState.stateType),"Original actor hurt state absent from selected catalog: "+actor.name);
   var selectedTypes=types;
   if(originals!=null){types=originals.Select(value=>(Type)value.targetType).Where(value=>value!=null).Concat(types).Distinct().ToArray();coordinator.r.liveCatalogs.stateTypes=types.Length;coordinator.r.liveCatalogs.stateConfigurations=originals.Length;coordinator.r.liveCatalogs.adaptedStateConfigurations=configs.Length;coordinator.r.liveCatalogs.staticStateFields=wholeStateFields.Count;}
   coordinator.ownsStateCatalog=true;coordinator.r.phase="original-spawn-state-catalog";coordinator.Save();
   var initialize=MovementBatchProbe.BuildStateCatalogRoutine(types,originals??configs);while(initialize.MoveNext())yield return initialize.Current;
   // Retain the accepted bounded configuration adaptations without changing the
   // native full configuration/preload ordering or replacing original programs.
   if(originals!=null){coordinator.r.liveCatalogs.emptyPreloadKeys=RemoveEmptyStatePreloadKeys();foreach(var selected in configs)MovementBatchProbe.StaticCall(typeof(EntityStateCatalog),"ApplyEntityStateConfiguration",selected);coordinator.r.liveCatalogs.preloadGUIDs=((string[])typeof(EntityStatePreloadCatalog).GetField("preloadGUIDs",flags).GetValue(null)).Length;}
   if(coordinator.IsPlayableSpine())coordinator.ApplySpineExclusions();if(cfg.enemySpine)coordinator.EnemyExclusions();if(cfg.teleporterLoop){StunState.stunVfxPrefab=coordinator.artifactBundle.LoadAsset<GameObject>(cfg.objectiveStunAsset);coordinator.Check(StunState.stunVfxPrefab,"Original composed stun presentation missing");}
   foreach(var type in types){var index=EntityStateCatalog.GetStateIndex(type);coordinator.Check(index!=EntityStateIndex.Invalid&&EntityStateCatalog.GetStateType(index)==type,"Original complete state identity round trip");}
   foreach(var type in selectedTypes){var index=EntityStateCatalog.GetStateIndex(type);coordinator.Check(EntityStateCatalog.InstantiateState(index).GetType()==type,"Original live state constructor identity");}
   coordinator.Check(cfg.sourceSpawnDelay>0&&cfg.sourceSpawnDelay<10&&SpawnTeleporterState.initialDelay==cfg.sourceSpawnDelay,"Original configured spawn delay");
   coordinator.Check(SpawnTeleporterState.soundString==cfg.sourceSpawnSound,"Original configured spawn sound");
  }
  public void Dispose(){coordinator.CleanupObjectiveConfigs();coordinator.CleanupEnemyConfigs();coordinator.CleanupSpineConfig();if(ownsSpawnConfig){SpawnTeleporterState.initialDelay=priorSpawnDelay;SpawnTeleporterState.soundString=priorSpawnSound;ownsSpawnConfig=false;}RestoreWholeStateOwnership();}
  public void ProbeSpawnStates(CharacterBody body,SessionConfig cfg){
   if(!coordinator.ownsStateCatalog){var preparation=PrepareSpawnStateCatalog(cfg);while(preparation.MoveNext()){};}
   if(coordinator.r.id=="body-state-spawn-state-overlay"){coordinator.ProbeTeleportOverlay(body,cfg);return;}
   if(coordinator.r.id=="body-state-spawn-state-buff-removal"){
    coordinator.Check(RoR2Content.Buffs.MedkitHeal&&RoR2Content.Buffs.TonicBuff&&DLC2Content.Buffs.SoulCost,"Original removal definitions");
    coordinator.Check(body.GetBuffCount(RoR2Content.Buffs.MedkitHeal)==0&&body.GetBuffCount(RoR2Content.Buffs.TonicBuff)==0&&body.GetBuffCount(DLC2Content.Buffs.SoulCost)==0,"Unrelated removal buffs remain absent");
    var buff=RoR2Content.Buffs.HiddenInvincibility;coordinator.Check(buff&&body.GetBuffCount(buff)==0,"Original empty hidden buff");coordinator.r.phase="original-hidden-buff-cycle";coordinator.Save();
    body.AddBuff(buff);coordinator.Check(body.GetBuffCount(buff)==1,"Original hidden buff addition");body.RemoveBuff(buff);coordinator.Check(body.GetBuffCount(buff)==0,"Original hidden buff removal");
    body.AddTimedBuff(buff,3f);float duration;coordinator.Check(body.GetBuffCount(buff)==1&&body.GetTimedBuffTotalDurationForIndex(buff.buffIndex,out duration)&&duration==3f,"Original timed hidden buff restoration");
    body.ClearTimedBuffs(buff);coordinator.Check(body.GetBuffCount(buff)==0,"Original timed hidden buff cleanup");return;
   }
   var machine=EntityStateMachine.FindByCustomName(body.gameObject,"Body");
   var weapon=EntityStateMachine.FindByCustomName(body.gameObject,"Weapon");var slide=EntityStateMachine.FindByCustomName(body.gameObject,"Slide");
   coordinator.Check(machine&&weapon&&slide&&machine.initialStateType.stateType==typeof(SpawnTeleporterState)&&machine.mainStateType.stateType==typeof(GenericCharacterMain),"Original named body state path");
   var selected=coordinator.r.id=="body-state-spawn-state-idle"?new[]{weapon,slide}:new[]{machine};Exception failure=null;
   try{
    foreach(var stateMachine in selected){
     coordinator.Check(stateMachine.state is Uninitialized&&stateMachine.networker==body.GetComponent<NetworkStateMachine>(),"Automatic state Awake/network cache");
     if(coordinator.r.id=="body-state-spawn-state-idle"){
      coordinator.Check(stateMachine.initialStateType.stateType==typeof(Idle)&&stateMachine.mainStateType.stateType==typeof(Idle),"Original Idle machine types");
      coordinator.r.phase="original-idle-start:"+stateMachine.customName;coordinator.Save();MovementBatchProbe.Call(stateMachine,"Start");coordinator.Check(stateMachine.state is Idle,"Original Idle Start entry");coordinator.r.idleStarts++;
     }else{
      var model=body.modelLocator.modelTransform.GetComponent<CharacterModel>();coordinator.Check(model,"Original model component");var priorInvisible=model.invisibilityCount;
      coordinator.Check(RoR2Content.Buffs.HiddenInvincibility&&RoR2Content.Buffs.HiddenInvincibility.buffIndex!=BuffIndex.None&&body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility)==0,"Original hidden buff context");
      coordinator.r.phase="original-spawn-state-start";coordinator.Save();MovementBatchProbe.Call(stateMachine,"Start");coordinator.r.spawnState=stateMachine.state.GetType().FullName;coordinator.r.hiddenBuffCount=body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility);
      coordinator.Check(stateMachine.state is SpawnTeleporterState&&coordinator.r.hiddenBuffCount==1&&model.invisibilityCount==priorInvisible+1,"Original spawn OnEnter and buff/model effects");coordinator.r.spawnStateEntries++;
      if(coordinator.r.id=="body-state-spawn-state-transition"||coordinator.r.id.StartsWith("body-state-spawn-state-main-")){
       coordinator.r.phase="original-spawn-state-ticks";coordinator.Save();int limit=Mathf.CeilToInt(cfg.sourceSpawnDelay/Time.fixedDeltaTime)+5;
       for(int i=0;i<limit&&stateMachine.state is SpawnTeleporterState;i++)stateMachine.ManagedFixedUpdate(Time.fixedDeltaTime);
       coordinator.r.spawnState=stateMachine.state.GetType().FullName;coordinator.Check(stateMachine.state is GenericCharacterMain,"Original timed transition to main");
       if(coordinator.r.id.StartsWith("body-state-spawn-state-main-"))ProbeSpawnedMain(body,stateMachine,cfg);
      }
     }
    }
   }catch(Exception e){failure=e;}
   try{if(!string.IsNullOrEmpty(cfg.teleportMaterialAsset))coordinator.ObserveTeleportOverlays(body);}catch(Exception e){failure=failure==null?e:new AggregateException(failure,e);}
   // Original destruction exits selected states while their actual catalog/buff dependencies still exist.
   foreach(var stateMachine in selected){try{MovementBatchProbe.Call(stateMachine,"OnDestroy");}catch(Exception e){failure=failure==null?e:new AggregateException(failure,e);}}
   if(failure!=null)throw failure;
   coordinator.Check(selected.All(x=>x.state==null),"Original selected state teardown");
  }

  public static float SpawnedStateAge(EntityState state,string property){return (float)typeof(EntityState).GetProperty(property,BindingFlags.Instance|BindingFlags.NonPublic).GetValue(state);}
  public void ProbeSpawnedMain(CharacterBody body,EntityStateMachine machine,SessionConfig cfg){
   var motor=body.characterMotor;var solver=body.GetComponent<KinematicCharacterMotor>();var input=body.inputBank;
   coordinator.r.spawnedMoveSpeed=body.moveSpeed;coordinator.r.spawnedAcceleration=body.acceleration;
   coordinator.Check(body.healthComponent.health==110&&body.moveSpeed==7&&body.acceleration==80&&body.jumpPower==15,"Actual spawned body original computed stats");
   coordinator.Check(motor&&solver&&input&&motor.Motor==solver&&!body.gameObject.activeInHierarchy,"Actual spawned motor/input isolation");
   if(coordinator.r.id!="body-state-spawn-state-main-neutral"){
    coordinator.r.phase="original-spawned-motor-start";coordinator.Save();Action<CharacterBody> observed=b=>{if(b==body)coordinator.r.motorStartEvents++;};motor.onMotorStart+=observed;
    try{MovementBatchProbe.Call(motor,"Start");}finally{motor.onMotorStart-=observed;}
    coordinator.r.rawAuthority=body.hasAuthority;coordinator.r.effectiveAuthority=RoR2.Util.HasEffectiveAuthority(body.gameObject);
    coordinator.Check(coordinator.r.motorStartEvents==1&&motor.hasEffectiveAuthority&&coordinator.r.effectiveAuthority&&!coordinator.r.rawAuthority&&motor.useGravity,"Original spawned motor Start/event/server authority");
    coordinator.Check(solver.MaxStableSlopeAngle==70&&solver.MaxStableDenivelationAngle==55&&motor.capsuleHeight==body.GetComponent<CapsuleCollider>().height,"Original spawned motor parameters");
    if(coordinator.r.id=="body-state-spawn-state-main-motor")return;
   }
   var state=machine.state;float age=SpawnedStateAge(state,"age"),fixedAge=SpawnedStateAge(state,"fixedAge");var origin=solver.TransientPosition;
   if(coordinator.r.id=="body-state-spawn-state-main-neutral"){
    coordinator.r.phase="original-spawned-main-neutral-ticks";coordinator.Save();coordinator.Check(input.moveVector==Vector3.zero&&!input.jump.down,"Original neutral input baseline");
    for(int i=0;i<50;i++){machine.ManagedUpdate();machine.ManagedFixedUpdate(.02f);coordinator.r.spawnedMainTicks++;}
    coordinator.r.spawnedStateAge=SpawnedStateAge(state,"age")-age;coordinator.r.spawnedFixedAge=SpawnedStateAge(state,"fixedAge")-fixedAge;
    coordinator.Check(machine.state==state&&Mathf.Abs(coordinator.r.spawnedFixedAge-1)<.0001f&&coordinator.r.spawnedStateAge>0,"Original main neutral scheduling/ages");
    coordinator.Check(motor.moveDirection==Vector3.zero&&solver.TransientPosition==origin&&!body.gameObject.activeInHierarchy,"Neutral state changed inactive solver position");return;
   }
   var savedGravity=Physics.gravity;var savedLayers=solver.CollidableLayers;var savedSolving=(bool)typeof(KinematicCharacterMotor).GetField("_solveGrounding",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(solver);
   try{
    coordinator.r.phase="original-spawned-main-motion";coordinator.Save();Physics.gravity=Vector3.zero;solver.SetGroundSolvingActivation(false);solver.CollidableLayers=0;motor.velocity=Vector3.zero;
    input.moveVector=Vector3.right;input.aimDirection=Vector3.right;
    for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);MovementBatchProbe.Step(solver,1);coordinator.r.spawnedMainTicks++;}
    coordinator.r.x=solver.TransientPosition.x-origin.x;coordinator.r.y=solver.TransientPosition.y-origin.y;
    coordinator.Check(coordinator.r.x>5&&coordinator.r.x<7&&Mathf.Abs(coordinator.r.y)<.001f&&Mathf.Abs(motor.velocity.x-body.moveSpeed)<.001f,"Original spawned main/motor/solver displacement");
    input.moveVector=Vector3.zero;
    for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);MovementBatchProbe.Step(solver,1);coordinator.r.spawnedMainTicks++;}
    coordinator.r.z=solver.TransientPosition.x-origin.x;
    coordinator.Check(coordinator.r.z>=coordinator.r.x&&coordinator.r.z<coordinator.r.x+2&&motor.velocity.sqrMagnitude<.000001f&&motor.moveDirection==Vector3.zero,"Original spawned main braking");
    coordinator.Check(machine.state==state&&!body.gameObject.activeInHierarchy,"Spawned main state identity/isolation changed");
   }finally{input.moveVector=Vector3.zero;Physics.gravity=savedGravity;solver.CollidableLayers=savedLayers;solver.SetGroundSolvingActivation(savedSolving);}
  }
 }
}
