using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using EntityStates;
using KinematicCharacterController;
using RoR2;
using UnityEngine;

public sealed partial class MovementBatchProbe {
 [Serializable] public class NovaSample {public float seconds;public NovaInputBridge.Raw raw;public Vector3 input,aim,stateAim,velocity,position;public bool grounded,jump;public int jumpCount;}
 [Serializable] public class NovaReport {public bool novaOnly,originalInputConsumer,stopped,aimConsumed,rendersOriginalModel,diagnosticInput;public int samples,fixedTicks,jumpPresses,localJumpCallbacks,jumpTransitions,landings;public float seconds,pathLength,planarPathLength,maxRise,diagnosticReturnFireAt;public uint spawnedBodyId,masterId;public NovaInputBridge.Mapping mapping;public List<NovaSample> observations=new List<NovaSample>();}
 void OnGUI(){if(DrawOfflineStart())return;if(r!=null&&r.results!=null&&r.results.reportGenerated){DrawIntegratedResults();return;}if(r!=null&&r.integratedWorld&&r.world!=null&&r.world.ready){DrawIntegratedWorld();return;}if(r!=null)DrawItemPickupObservation();if(r!=null&&r.phase=="commando-defeated"){GUI.Label(new Rect(20,70,800,40),"Commando defeated. Close the test, then open Porting Lab again to retry.");if(GUI.Button(new Rect(20,115,200,40),"Close test"))Application.Quit();return;}if(r!=null&&IsPlayableSpine()&&r.primary!=null)GUI.Label(new Rect(20,70,850,100),"Commando | A: jump | X: primary | Y: secondary | LB: roll | RB: barrage | audio unavailable\nOriginal primary entries: "+r.primary.shots+" | stock: "+r.primary.stockAfter+(r.combat==null?"":"\nTarget HP: "+r.combat.healthAfter.ToString("F1")+" | damage: "+r.combat.damageDealt.ToString("F1")+" | secondary/roll/barrage: "+r.combat.secondaryEntries+"/"+r.combat.utilityEntries+"/"+r.combat.specialEntries)+(r.enemy==null?"":"\nBeetle HP: "+r.enemy.health.ToString("F1")+" | player HP: "+r.enemy.playerHealth.ToString("F1")+" | AI: "+r.enemy.aiState+" | attacks: "+r.enemy.headbutts));}
 bool IsNovaInput(){return IsPlayableSpine()||r.id=="body-state-spawn-state-auto-nova-controls";}
 IEnumerator NovaRawBoundary(){
  NovaInputBridge.RequireNova();r.nova=new NovaReport{novaOnly=true};r.phase="nova-raw-ready";Save();float began=Time.realtimeSinceStartup,next=0;
  while(Time.realtimeSinceStartup-began<120){
   float elapsed=Time.realtimeSinceStartup-began;
   if(elapsed>=next){r.nova.observations.Add(new NovaSample{seconds=elapsed,raw=NovaInputBridge.ReadRaw()});r.nova.samples++;r.nova.seconds=elapsed;next=elapsed+.05f;}
   if(Time.frameCount%30==0)Save();yield return null;
  }
  Check(r.nova.samples>300,"Nova Unity raw capture incomplete");Save();
 }
 IEnumerator NovaInputBoundary(CharacterBody body,EntityStateMachine machine,Result cfg){
  bool spine=IsPlayableSpine(),bringup=r.id.EndsWith("-bringup");r.integratedWorld=cfg.integratedWorld;r.teleporterLoop=cfg.teleporterLoop;NovaInputBridge.RequireNova();r.nova=new NovaReport{rendersOriginalModel=spine,diagnosticInput=bringup,novaOnly=true,spawnedBodyId=body.netId.Value,masterId=body.master.netId.Value};
  var mappingPath=System.IO.Path.Combine(Application.persistentDataPath,"nova-input-mapping.json");
  Check(File.Exists(mappingPath),"Measured Nova mapping required before physical Commando test");var mapping=JsonUtility.FromJson<NovaInputBridge.Mapping>(File.ReadAllText(mappingPath));mapping.Validate(r.attempt);Check(!mapping.enableSkills,"Ability execution is a separate probe");r.nova.mapping=mapping;
  var motor=body.characterMotor;var solver=motor.Motor;var state=machine.state;var bank=body.inputBank;
  Check(state is GenericCharacterMain&&body.master.GetBody()==body&&body.isServer&&motor.hasEffectiveAuthority,"Original spawned Commando input/authority contract");
  Check(RoR2Content.Items.JumpBoost&&DLC3Content.Items.JumpDamageStrike&&DLC1Content.Items.GummyCloneIdentifier&&string.IsNullOrEmpty(body.GetComponent<SfxLocator>().jumpSound),"Combined original empty inventory/jump contract");
  var priorTriggerQueries=Physics.queriesHitTriggers;var gravity=Physics.gravity;var layers=solver.CollidableLayers;var stable=solver.StableGroundLayers;NovaInputBridge bridge=null;NovaDiagnosticDisplay display=null;int sleepTimeout=Screen.sleepTimeout;Screen.sleepTimeout=SleepTimeout.NeverSleep;
  CharacterBody.JumpDelegate jumped=()=>{r.nova.localJumpCallbacks++;};CharacterMotor.HitGroundDelegate landed=(ref CharacterMotor.HitGroundInfo hit)=>{r.nova.landings++;};body.onJump+=jumped;motor.onHitGroundAuthority+=landed;
  try{
   if(cfg.automaticDirector){Check(!cfg.sourceQueriesHitTriggers,"Source placement trigger-query flag changed");Physics.queriesHitTriggers=cfg.sourceQueriesHitTriggers;}
   if(!cfg.stageGeometry){obstacle=GameObject.CreatePrimitive(PrimitiveType.Cube);obstacle.name="Owned Nova floor";obstacle.layer=30;obstacle.transform.position=new Vector3(0,9,0);obstacle.transform.localScale=new Vector3(200,1,200);}
   solver.StableGroundLayers=cfg.stageGeometry?LayerIndex.world.mask:1<<30;solver.CollidableLayers=solver.StableGroundLayers;solver.SetGroundSolvingActivation(true);Physics.SyncTransforms();Physics.gravity=new Vector3(0,cfg.sourceGravity,0);
   var deadline=Time.realtimeSinceStartup+3;while(!solver.GroundingStatus.IsStableOnGround&&Time.realtimeSinceStartup<deadline){yield return new WaitForEndOfFrame();ObserveAutomaticModelFollow(body);}
   Check(solver.GroundingStatus.IsStableOnGround&&r.nova.landings==1&&body.healthComponent.health==110,"Original spawned body landing before physical input");
   // Diagnostic aim stance only; original state/direction still choose and turn toward bank aim.
   body.SetAimTimer(130);
   display=new NovaDiagnosticDisplay(body.modelLocator.modelTransform,artifactBundle,cfg.displayAssets,obstacle,spine);
   if(cfg.stageGeometry)display.camera.cullingMask|=LayerIndex.world.mask;
   if(cfg.combatSpine)PrepareCombatScene(body,cfg);
   if(cfg.originalRunClock){var sceneContext=PrepareRunSceneContext(cfg);while(sceneContext.MoveNext())yield return sceneContext.Current;}
   if(!string.IsNullOrEmpty(cfg.playerDeathEffectAsset)){var defeatSetup=PreparePlayerDefeat(body,cfg);while(defeatSetup.MoveNext())yield return defeatSetup.Current;}
   if(cfg.enemySpine){foreach(var hurt in body.hurtBoxGroup.hurtBoxes){hurt.enabled=true;hurt.GetComponent<Collider>().enabled=true;}var enemyRoutine=PrepareEnemy(body,cfg);while(enemyRoutine.MoveNext())yield return enemyRoutine.Current;}
   if(cfg.integratedWorld){var world=PrepareIntegratedWorld(body,cfg);while(world.MoveNext())yield return world.Current;}
   PrepareIntegratedResults(body,cfg);
   if(cfg.teleporterLoop)display.camera.cullingMask|=LayerIndex.defaultLayer.mask;
   if(cfg.integratedWorld){display.ConfigureThirdPerson(body);worldView=display.thirdPerson;r.world.camera=worldView.report;}
   bridge=body.gameObject.AddComponent<NovaInputBridge>();bridge.bank=bank;bridge.mapping=mapping;bridge.enablePrimary=spine;bridge.enableAllSkills=cfg.combatSpine;bridge.diagnosticInput=bringup;bridge.thirdPerson=display.thirdPerson;r.nova.originalInputConsumer=true;
   r.phase=cfg.integratedWorld?"integrated-world-playing":bringup?"nova-spine-bringup":"nova-commando-ready";Save();float began=Time.realtimeSinceStartup,next=0,restingY=solver.TransientPosition.y,combatBegan=-1;var previous=solver.TransientPosition;int priorJumpCount=motor.jumpCount;
   float initialAge=SpawnedStateAge(state,"age"),initialFixed=SpawnedStateAge(state,"fixedAge");var aimField=typeof(GenericCharacterMain).GetField("aimDirection",BindingFlags.NonPublic|BindingFlags.Instance);
   while(r.freePlay||Time.realtimeSinceStartup-began<(cfg.integratedWorld?(cfg.teleporterLoop?(cfg.integratedRuntimeSeconds>0?cfg.integratedRuntimeSeconds:360):120):bringup?(cfg.automaticDirector?60:cfg.enemySpine?30:20):90)){
    yield return new WaitForEndOfFrame();
    if(CompletedResultsReturn())yield break;
    if((r.freePlay||cfg.integratedWorld)&&body&&!body.healthComponent.alive){var defeat=ObservePlayerDefeat(body,machine,bridge);while(defeat.MoveNext())yield return defeat.Current;if(restartRequested)yield break;Check(false,"Integrated diagnostic run ended by original player death before objective completion");}
    if(cfg.teleporterLoop){Check(r.stageProgress!=null&&string.IsNullOrEmpty(r.stageProgress.error),"Original stage callback failed: "+(r.stageProgress==null?"missing":r.stageProgress.error));if(!string.IsNullOrEmpty(pendingStage)){var transition=TransportIntegratedStage(bridge,began);while(transition.MoveNext())yield return transition.Current;previous=solver.TransientPosition;}}
    ObserveAutomaticModelFollow(body);TemporaryOverlayManager.OverlayUpdate();
    Check(string.IsNullOrEmpty(bridge.error),"Nova bridge input failure: "+bridge.error);Check((cfg.combatSpine||machine.state==state)&&body.gameObject.activeInHierarchy&&body.master.GetBody()==body&&motor.hasEffectiveAuthority,"Original physical simulation state/link/authority changed");
    float elapsed=Time.realtimeSinceStartup-began;var position=solver.TransientPosition;r.nova.pathLength+=Vector3.Distance(position,previous);var delta=position-previous;delta.y=0;r.nova.planarPathLength+=delta.magnitude;previous=position;if(motor.jumpCount>priorJumpCount)r.nova.jumpTransitions+=motor.jumpCount-priorJumpCount;priorJumpCount=motor.jumpCount;r.nova.maxRise=Mathf.Max(r.nova.maxRise,position.y-restingY);
    var stateAim=machine.state is GenericCharacterMain?(Vector3)aimField.GetValue(machine.state):Vector3.zero;
    if(bridge.aim.sqrMagnitude>.1f&&Vector3.Distance(stateAim,bank.aimDirection)<.001f)r.nova.aimConsumed=true;
    if(r.nova.planarPathLength>3&&elapsed>15&&bank.moveVector==Vector3.zero&&motor.velocity.sqrMagnitude<.0001f&&solver.GroundingStatus.IsStableOnGround)r.nova.stopped=true;
    if(spine)ObserveSpinePrimary(body);
    if(cfg.combatSpine)ObserveCombat(body,machine);if(cfg.enemySpine)ObserveEnemy();ObserveOriginalRunClock();
    if(cfg.integratedWorld){ObserveIntegratedWorld(body,elapsed);ObserveIntegratedResults();if(bringup&&!(r.results!=null&&r.results.persisted))IntegratedWorldStimulus(body,bridge,elapsed);}
    if(bringup&&!cfg.integratedWorld){
     bridge.movement=elapsed<3?Vector2.right:elapsed<6?Vector2.left:Vector2.zero;bridge.aim=elapsed<6?Vector2.right:cfg.combatSpine?CombatAim(body):Vector2.up;bridge.DiagnosticJump(elapsed>7&&elapsed<7.2f);
     // Observe real melee before diagnostic return fire; wall-clock timing can knock the enemy away before contact.
     if(cfg.enemySpine&&combatBegan<0&&elapsed>=9&&r.enemy.playerDamageEvents>0&&(!DirectorBatch()||r.director.actors.Count>=2)){combatBegan=elapsed;r.nova.diagnosticReturnFireAt=elapsed;}
     float fireAge=cfg.enemySpine?(combatBegan<0?-1:elapsed-combatBegan+9):elapsed;
     if(cfg.automaticDirector&&enemyBody&&fireAge>9&&fireAge<12){var enemyAimDelta=enemyBody.corePosition-body.inputBank.aimOrigin;bridge.aim=new Vector2(enemyAimDelta.x,enemyAimDelta.z).normalized;}bridge.diagnosticPrimary=fireAge>9&&fireAge<12;bridge.diagnosticSecondary=cfg.combatSpine&&fireAge>12.3f&&fireAge<12.5f;bridge.diagnosticUtility=cfg.combatSpine&&fireAge>14&&fireAge<14.2f;bridge.diagnosticSpecial=cfg.combatSpine&&fireAge>16&&fireAge<16.2f;
     if(DirectorBatch()&&fireAge>18.5f){var target=DirectorReturnFireTarget();bridge.diagnosticPrimary=target;if(target){var batchAim=target.corePosition-body.inputBank.aimOrigin;bridge.aim=new Vector2(batchAim.x,batchAim.z).normalized;}}
    }
    if(bringup&&worldView!=null&&bridge.diagnosticInput)worldView.DiagnosticDirection(bank.aimDirection);display.Observe(position,bank.aimDirection);
    if(elapsed>=next){if((r.freePlay||cfg.integratedWorld)&&r.nova.observations.Count>=900)r.nova.observations.RemoveAt(0);r.nova.observations.Add(new NovaSample{seconds=elapsed,raw=NovaInputBridge.ReadRaw(),input=bank.moveVector,aim=bank.aimDirection,stateAim=stateAim,velocity=motor.velocity,position=position,grounded=solver.GroundingStatus.IsStableOnGround,jump=bank.jump.down,jumpCount=motor.jumpCount});r.nova.samples++;next=elapsed+.1f;}
    if(cfg.teleporterLoop&&r.stageProgress.transitions>=Mathf.Max(1,cfg.integratedTransitionTarget)&&elapsed-r.stageProgress.enteredAt>30&&(!cfg.moonMission||(r.moon!=null&&r.moon.gameOver&&(!cfg.integratedResults||(r.results!=null&&r.results.persisted))))){r.nova.seconds=elapsed;break;}
    r.nova.seconds=elapsed;r.nova.fixedTicks=bridge.fixedTicks;r.nova.jumpPresses=bridge.jumpPresses;r.automaticFrames++;if(Time.frameCount%30==0)Save();
   }
   r.automaticSeconds=Time.realtimeSinceStartup-began;r.spawnedStateAge=SpawnedStateAge(state,"age")-initialAge;r.spawnedFixedAge=SpawnedStateAge(state,"fixedAge")-initialFixed;
   bridge.enabled=false;yield return new WaitForSeconds(.5f);
   if(cfg.integratedWorld){
    r.world.simulationSeconds=r.automaticSeconds;
    Check(r.world.ready&&r.world.simulationSeconds>=120&&r.world.frames>1000,"Integrated world simulation incomplete");
    if(!cfg.moonMission)Check(r.world.openedBarrels+(r.stageProgress==null?0:r.stageProgress.completedBarrels)>=3&&r.world.lootDomain==4&&r.world.openedChests+(r.stageProgress==null?0:r.stageProgress.completedChests)>=2&&r.world.pickupMessages>=2&&r.world.syringe+r.world.lightning+r.world.glasses+r.world.slug>=2&&r.world.kills>0&&r.world.coinMessages>0&&r.world.xpMessages>0,"Integrated world gameplay loop incomplete");
    Check(r.world.authority&&body.healthComponent.alive&&(cfg.teleporterLoop||rewardDirector.enabled)&&r.director.actors.Count>3,"Integrated continuous combat/authority/survival incomplete");if(cfg.teleporterLoop)Check(r.stageProgress.transitions>=Mathf.Max(1,cfg.integratedTransitionTarget)&&r.stageProgress.stageClearCount>=Mathf.Max(1,cfg.integratedTransitionTarget),"Integrated original teleporter/boss/charge loop incomplete");if(cfg.moonMission)Check(r.moon!=null&&r.moon.gameOver&&moonEscape.mainStateMachine.state is EscapeSequenceController.EscapeSequenceSuccessState,"Original Moon mission/escape/ending remains incomplete");if(cfg.integratedResults)Check(r.results!=null&&r.results.reportGenerated&&r.results.clientEnding&&r.results.reportReloaded&&r.results.persisted,"Original ending report/persistence incomplete");Save();yield break;
   }
   Check(r.automaticSeconds>=(bringup?20:90)&&r.nova.fixedTicks>(bringup?300:1000)&&r.nova.samples>(bringup?100:300),"Physical Commando sustained callbacks");Check(r.nova.planarPathLength>5&&r.nova.stopped,"Physical movement and original stopping not observed");Check(r.nova.aimConsumed&&(bringup||bridge.aimTicks>10),"Physical right-stick aim not consumed by original state");if(spine)Check(r.primary.shots>0&&(cfg.combatSpine?body.skillLocator.primary.CanExecute():body.skillLocator.primary.stock==1),"Original primary firing/readiness not observed");Check(r.nova.jumpTransitions>0&&r.nova.jumpPresses>=r.nova.jumpTransitions&&r.nova.maxRise>.5f&&r.nova.landings>=2&&solver.GroundingStatus.IsStableOnGround&&motor.jumpCount==0,"Physical jump/original landing incomplete");Save();
   if(cfg.combatSpine)Check(r.combat.secondaryEntries>0&&r.combat.utilityEntries>0&&r.combat.specialEntries>0&&r.combat.projectiles>0&&r.combat.damageEvents>0&&r.combat.healthAfter<r.combat.healthBefore,"Integrated original skills/projectile/target damage incomplete");
  if(cfg.enemySpine)Check(r.enemy.graphReady&&r.enemy.linked&&r.enemy.authority&&r.enemy.targetFound&&r.enemy.planarBeforeDamage>4&&r.enemy.groundedBeforeDamage>100&&r.enemy.maxFallBeforeDamage<10,"Original grounded enemy chase before incoming damage not observed");
  if(cfg.enemySpine&&bringup)Check(r.enemy.headbutts>0&&r.enemy.playerDamageEvents>0&&r.enemy.enemyDamageEvents>0&&r.enemy.dead,"Original enemy melee, return damage and death not observed");
  if(cfg.enemySpine&&bringup)Check(r.enemy.deathGlobalEvents==1&&r.enemy.playerKillsAfter==r.enemy.playerKillsBefore+(DirectorBatch()?3:1)&&r.enemy.naturalBodyDestroyed&&r.enemy.naturalMasterDestroyed,"Original enemy death event/kill count/natural teardown incomplete");
  if(cfg.automaticDirector&&bringup)Check(r.director.navigationTicks>500&&r.director.navigationNext&&r.director.navigationReachable&&r.director.navigationPathUpdate>0&&(DirectorBatch()?r.director.navigationAgentPeak>=2:r.director.navigationAgentPeak==1),"Original broad route output/scheduling not observed");
  if(cfg.enemyRewards&&bringup){if(DirectorBatch())VerifyDirectorBatch();else VerifyEnemyRewardDelivery();}
  if(cfg.originalRunClock&&bringup)VerifyOriginalRunClock();
  if(cfg.barrelInteraction&&bringup){var interaction=ProbeOriginalBarrel(body,cfg);while(interaction.MoveNext())yield return interaction.Current;}
  if(cfg.originalDefaultPickup&&bringup){var generic=PrepareOriginalDefaultPickup(cfg);while(generic.MoveNext())yield return generic.Current;}
  if(cfg.originalItemPickup&&bringup){var pickup=ProbeOriginalItemPickup(body,cfg);while(pickup.MoveNext())yield return pickup.Current;}
  if(cfg.originalMoneyCost&&bringup){var cost=ProbeOriginalMoneyCost(body,cfg);while(cost.MoveNext())yield return cost.Current;}
  if(cfg.originalActiveClient&&bringup){var client=ProbeActiveBodyClient(body,cfg);while(client.MoveNext())yield return client.Current;}
  }finally{if(cfg.integratedWorld)CleanupIntegratedWorld();CleanupActiveBodyClient();CleanupOriginalMoneyCost();CleanupOriginalItemPickup();if(cfg.originalDefaultPickup&&(bringup||cfg.integratedWorld))CleanupOriginalDefaultPickup();CleanupOriginalBarrel();CleanupRunClock();if(cfg.enemySpine)CleanupEnemy();if(bridge){bridge.enabled=false;Destroy(bridge);}if(cfg.combatSpine)CleanupCombatScene();if(display!=null)display.Dispose();if(!ReferenceEquals(body,null))body.onJump-=jumped;if(!ReferenceEquals(motor,null))motor.onHitGroundAuthority-=landed;Physics.gravity=gravity;Physics.queriesHitTriggers=priorTriggerQueries;if(solver){solver.CollidableLayers=layers;solver.StableGroundLayers=stable;solver.SetGroundSolvingActivation(false);}worldView=null;Screen.sleepTimeout=sleepTimeout;}
 }
}
