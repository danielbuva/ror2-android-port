using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using EntityStates;
using KinematicCharacterController;
using RoR2;
using UnityEngine;

// Original Unity callbacks; the harness only observes and supplies diagnostic input.
public sealed partial class MovementBatchProbe {
 IEnumerator AutomaticSpawnBoundary(CharacterBody body,Result cfg){
  PrepareSpawnStateCatalog(cfg);
  var machine=EntityStateMachine.FindByCustomName(body.gameObject,"Body");
  var motor=body.characterMotor;var solver=body.GetComponent<KinematicCharacterMotor>();var input=body.inputBank;var spawnedMaster=body.master;
  bool automaticBody=IsAutomaticBody(),automaticDirection=IsAutomaticDirection(),automaticModel=IsAutomaticModel();
  var direction=body.GetComponent<CharacterDirection>();
  if(automaticDirection)Check(direction&&!direction.modelAnimator,"Direction Start already ran; refuse automatic scheduling claim");
  bool movingMotor=r.id!="body-state-spawn-state-auto-state",scripted=r.id=="body-state-spawn-state-auto-motion";
  Check(machine&&machine.state is Uninitialized&&machine.initialStateType.stateType==typeof(SpawnTeleporterState)&&machine.mainStateType.stateType==typeof(GenericCharacterMain),"Original automatic state starting identity");
  Check(motor&&solver&&motor.Motor==solver&&input&&!body.gameObject.activeInHierarchy,"Automatic fixture motor/input isolation");
  var model=body.modelLocator.modelTransform.GetComponent<CharacterModel>();int invisible=model.invisibilityCount;
  var savedGravity=Physics.gravity;var savedLayers=solver.CollidableLayers;
  bool savedSolving=(bool)typeof(KinematicCharacterMotor).GetField("_solveGrounding",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(solver);
  Action<CharacterBody> observed=b=>{if(b==body)r.motorStartEvents++;};motor.onMotorStart+=observed;
  Action<CharacterBody> masterStarted=b=>{if(b==body)r.masterStartEvents++;},bodyStarted=b=>{if(b==body)r.bodyStartEvents++;},stats=b=>{if(b==body)r.automaticBodyStatsEvents++;};
  if(automaticBody){body.master.onBodyStart+=masterStarted;CharacterBody.onBodyStartGlobal+=bodyStarted;body.onRecalculateStats+=stats;}
  try{
   // Body-enabled probes use only Unity Start/Update/FixedUpdate; other root callbacks remain inactive.
   foreach(var component in body.GetComponents<MonoBehaviour>())component.enabled=false;
   if(automaticModel)PrepareAutomaticModel(body);
   machine.enabled=true;if(movingMotor)motor.enabled=true;if(automaticBody)body.enabled=true;if(automaticDirection)direction.enabled=true;if(automaticModel)body.modelLocator.enabled=true;if(IsAutomaticSkill())EnableAutomaticSkills(body);
   if(IsPlayableSpine()){foreach(var skill in cfg.combatSpine?new[]{body.skillLocator.primary,body.skillLocator.secondary,body.skillLocator.utility,body.skillLocator.special}:new[]{body.skillLocator.primary}){skill.enabled=true;skill.stateMachine.enabled=true;}}
   r.automaticCallbacks=body.GetComponents<MonoBehaviour>().Where(x=>x.enabled).Select(x=>x.GetType().FullName).ToArray();
   if(!cfg.combatSpine)Check(r.automaticCallbacks.Length==(movingMotor?2:1)+(automaticBody?1:0)+(automaticDirection?1:0)+(automaticModel?1:0)+AutomaticSkillCount()+(IsPlayableSpine()?2:0),"Unexpected enabled root callback");
   Physics.gravity=Vector3.zero;solver.SetGroundSolvingActivation(false);input.moveVector=Vector3.zero;
   r.phase="automatic-spawn-state-start";Save();body.gameObject.SetActive(true);yield return null;
   Check(machine.state is SpawnTeleporterState&&body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility)==1&&model.invisibilityCount==invisible+1,"Automatic original spawn Start/buff/model effects");r.spawnStateEntries++;
   if(automaticBody){
    r.spawnedHealth=body.healthComponent.health;r.spawnedSkinIndex=body.skinIndex;r.automaticBodyRegistered=CharacterBody.readOnlyInstancesList.Contains(body);Save();
    Check(r.masterStartEvents==1&&r.bodyStartEvents==1&&r.automaticBodyStatsEvents>=1&&r.automaticBodyRegistered&&r.spawnedHealth==110,"Original automatic body Start/events/stats/registration");
   }
   if(movingMotor){
    r.rawAuthority=body.hasAuthority;r.effectiveAuthority=RoR2.Util.HasEffectiveAuthority(body.gameObject);
    Check(r.motorStartEvents==1&&motor.hasEffectiveAuthority&&r.effectiveAuthority&&!r.rawAuthority&&motor.useGravity,"Automatic original motor Start/authority");
    Check(solver.enabled&&KinematicCharacterSystem.CharacterMotors_Important.Contains(solver)&&KinematicCharacterSystem.Settings.AutoSimulation,"Original automatic solver registration/settings");r.automaticSolverRegistered=true;
    solver.CollidableLayers=0; // Start rebuilds layers; isolate collisions only after the original callback.
   }else Check(!solver.enabled&&!KinematicCharacterSystem.CharacterMotors_Important.Contains(solver),"State-only probe unexpectedly schedules solver");
   var deadline=Time.realtimeSinceStartup+cfg.sourceSpawnDelay+3;
   while(machine.state is SpawnTeleporterState&&Time.realtimeSinceStartup<deadline){
    ObserveTeleportOverlays(body);TemporaryOverlayManager.OverlayUpdate();yield return null;
   }
   // The final spawn tick and transition can occur before the coroutine resumes.
   ObserveTeleportOverlays(body);
   r.spawnState=machine.state.GetType().FullName;r.hiddenBuffCount=body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility);r.spawnedStateAge=SpawnedStateAge(machine.state,"age");r.spawnedFixedAge=SpawnedStateAge(machine.state,"fixedAge");Save();
   Check(machine.state is GenericCharacterMain&&model.invisibilityCount==invisible,"Automatic original timed transition/model exit");
   float buffDuration=0;Check(r.hiddenBuffCount==1&&body.GetTimedBuffTotalDurationForIndex(RoR2Content.Buffs.HiddenInvincibility.buffIndex,out buffDuration)&&buffDuration>2.5f&&buffDuration<=3f&&(automaticBody||buffDuration==3f),"Original spawn exit timed hidden buff duration");r.spawnExitBuffSeconds=buffDuration;
   Check(r.teleportOverlays==1,"Original automatic spawn overlay not observed");r.spawnState=machine.state.GetType().FullName;
   r.spawnedMoveSpeed=body.moveSpeed;r.spawnedAcceleration=body.acceleration;
   Check((cfg.enemySpine?body.healthComponent.health>0&&body.maxHealth==110:body.healthComponent.health==110)&&body.moveSpeed==7&&body.acceleration==80&&body.jumpPower==15,"Original automatic spawned computed stats");
   if(IsAutomaticHealth()){
    if(IsPlayableSpine())body.healthComponent.enabled=true;else{var healthRoutine=AutomaticHealthBoundary(body,machine);while(healthRoutine.MoveNext())yield return healthRoutine.Current;}
   }
   if(IsAutomaticSkill())StartAutomaticSkillTiming(body);
   if(IsNovaInput()){
    var novaRoutine=NovaInputBoundary(body,machine,cfg);while(novaRoutine.MoveNext())yield return novaRoutine.Current;if(restartRequested){Check(CompletedResultsReturn()||(r.playerDefeat!=null&&r.playerDefeat.bodyDestroyed&&r.playerDefeat.deathEntered&&!body),"Restart before original death or persisted ending completed");yield break;}
   }else if(automaticDirection){
    var directionRoutine=AutomaticDirectionBoundary(body,machine);while(directionRoutine.MoveNext())yield return directionRoutine.Current;
   }else if(r.id=="body-state-spawn-state-auto-gravity"||IsRecoveredLanding()){
    var groundRoutine=AutomaticGroundBoundary(body,machine,cfg);while(groundRoutine.MoveNext())yield return groundRoutine.Current;
   }else{
   var state=machine.state;float age=SpawnedStateAge(state,"age"),fixedAge=SpawnedStateAge(state,"fixedAge");var origin=solver.TransientPosition;
   float began=Time.realtimeSinceStartup;bool moved=false,stopped=false;Vector3 stopPosition=origin;
   if(scripted){input.moveVector=Vector3.right;input.aimDirection=Vector3.right;}
   r.phase=scripted?"automatic-spawned-scripted-motion":"automatic-spawned-neutral-hold";Save();
   while(Time.realtimeSinceStartup-began<60){
    ObserveTeleportOverlays(body);TemporaryOverlayManager.OverlayUpdate();if(r.id=="body-state-spawn-state-auto-barrier")ObserveBarrierEffect(body);
    float elapsed=Time.realtimeSinceStartup-began;
    Check(machine.state==state&&body.gameObject.activeInHierarchy,"Automatic original main state/root changed");
    if(scripted&&!moved&&elapsed>=1){
     r.x=solver.TransientPosition.x-origin.x;r.y=solver.TransientPosition.y-origin.y;
     Check(r.x>4&&r.x<9&&Mathf.Abs(r.y)<.001f&&Mathf.Abs(motor.velocity.x-body.moveSpeed)<.001f,"Automatic original state/motor/solver movement");
     input.moveVector=Vector3.zero;moved=true;
    }
    if(scripted&&moved&&!stopped&&elapsed>=2){
     r.z=solver.TransientPosition.x-origin.x;stopPosition=solver.TransientPosition;
     Check(r.z>=r.x&&r.z<r.x+2&&motor.velocity.sqrMagnitude<.000001f&&motor.moveDirection==Vector3.zero,"Automatic original state braking");stopped=true;
    }
    if(stopped)Check(Vector3.Distance(solver.TransientPosition,stopPosition)<.001f,"Automatic neutral hold drift");
    if(!scripted)Check(Vector3.Distance(solver.TransientPosition,origin)<.001f,"Automatic neutral position drift");
    r.automaticFrames++;yield return null;
   }
   r.automaticSeconds=Time.realtimeSinceStartup-began;r.spawnedStateAge=SpawnedStateAge(state,"age")-age;r.spawnedFixedAge=SpawnedStateAge(state,"fixedAge")-fixedAge;
   Check(r.automaticSeconds>=60&&r.automaticFrames>300&&r.spawnedStateAge>55&&r.spawnedFixedAge>55,"Automatic original sustained frame/fixed ages");
   Check(!scripted||(moved&&stopped),"Automatic motion sequence incomplete");Save();
   }
   if(r.id=="body-state-spawn-state-auto-barrier"){ObserveBarrierEffect(body);Check(r.barrierMaterialCopies>0&&r.barrierEffectEntries==1&&r.barrierEffectExited&&r.barrierEffectDestroyed&&!BodyBarrier(body),"Original automatic barrier effect entry/exit/destruction");}
   if(IsAutomaticHealth()){
    var health=body.healthComponent;
    if(cfg.integratedWorld)Check(health.enabled&&health.health>0&&health.health<=health.fullHealth&&health.barrier>=0&&health.barrier<=health.fullBarrier,"Original integrated health/barrier outside native limits");
    else Check(health.enabled&&(cfg.enemySpine?health.health>0&&health.health<=body.maxHealth:health.health==110)&&health.barrier==0,"Original automatic health sustained full health/barrier expiry");
   }
   if(automaticBody){
    r.hiddenBuffCount=body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility);r.spawnBuffExpired=r.hiddenBuffCount==0&&!body.GetTimedBuffTotalDurationForIndex(RoR2Content.Buffs.HiddenInvincibility.buffIndex,out buffDuration);
    r.stationarySeconds=(float)typeof(CharacterBody).GetField("notMovingStopwatch",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(body);Save();
    Check(r.spawnBuffExpired&&(IsNovaInput()||r.stationarySeconds>55)&&r.automaticBodyStatsEvents>=2,"Original automatic body buff expiry/update timer/stat recalculation");
    Check((cfg.integratedWorld?body.healthComponent.health>0&&body.maxHealth>=110&&body.attackSpeed>=1:(cfg.enemySpine?body.healthComponent.health>0&&body.maxHealth==110:body.healthComponent.health==110))&&body.moveSpeed==7&&body.acceleration==80&&body.jumpPower==15&&r.bodyStartEvents==1&&r.masterStartEvents==1,"Original continuing body stats/Start uniqueness");
   }
  }finally{
   if(body)body.gameObject.SetActive(false);if(!ReferenceEquals(motor,null))motor.onMotorStart-=observed;if(input)input.moveVector=Vector3.zero;
   if(automaticBody){if(spawnedMaster)spawnedMaster.onBodyStart-=masterStarted;CharacterBody.onBodyStartGlobal-=bodyStarted;if(!ReferenceEquals(body,null))body.onRecalculateStats-=stats;}
   // Explicit original exit keeps measured buff/material dependencies alive during teardown.
   if(body&&IsPlayableSpine())foreach(var weapon in new[]{body.skillLocator.primary.stateMachine,body.skillLocator.secondary.stateMachine,body.skillLocator.utility.stateMachine,body.skillLocator.special.stateMachine}.Distinct().Where(x=>x!=machine))if(weapon)Call(weapon,"OnDestroy");if(machine)Call(machine,"OnDestroy");Physics.gravity=savedGravity;if(solver){solver.CollidableLayers=savedLayers;solver.SetGroundSolvingActivation(savedSolving);}if((restartRequested||(r.playerDefeat!=null&&r.playerDefeat.bodyDestroyed))&&ownedDetachedModel)Destroy(ownedDetachedModel);
  }
  Check(!automaticBody||!CharacterBody.readOnlyInstancesList.Contains(body),"Original automatic body deregistration");
  Check(machine.state==null&&!KinematicCharacterSystem.CharacterMotors_Important.Contains(solver),"Automatic state exit/solver unregistration");
 }
}
