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
 [Serializable] public class NovaReport {public bool novaOnly,originalInputConsumer,stopped,aimConsumed,rendersOriginalModel,diagnosticInput;public int samples,fixedTicks,jumpPresses,localJumpCallbacks,jumpTransitions,landings;public float seconds,pathLength,planarPathLength,maxRise;public uint spawnedBodyId,masterId;public NovaInputBridge.Mapping mapping;public List<NovaSample> observations=new List<NovaSample>();}
 void OnGUI(){if(r!=null&&IsPlayableSpine()&&r.primary!=null)GUI.Label(new Rect(20,70,850,100),"Commando | A: jump | X: primary | Y: secondary | LB: roll | RB: barrage | audio unavailable\nOriginal primary entries: "+r.primary.shots+" | stock: "+r.primary.stockAfter+(r.combat==null?"":"\nTarget HP: "+r.combat.healthAfter.ToString("F1")+" | damage: "+r.combat.damageDealt.ToString("F1")+" | secondary/roll/barrage: "+r.combat.secondaryEntries+"/"+r.combat.utilityEntries+"/"+r.combat.specialEntries));}
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
  bool spine=IsPlayableSpine(),bringup=r.id.EndsWith("-bringup");NovaInputBridge.RequireNova();r.nova=new NovaReport{rendersOriginalModel=spine,diagnosticInput=bringup,novaOnly=true,spawnedBodyId=body.netId.Value,masterId=body.master.netId.Value};
  var mappingPath=System.IO.Path.Combine(Application.persistentDataPath,"nova-input-mapping.json");
  Check(File.Exists(mappingPath),"Measured Nova mapping required before physical Commando test");var mapping=JsonUtility.FromJson<NovaInputBridge.Mapping>(File.ReadAllText(mappingPath));mapping.Validate(r.attempt);Check(!mapping.enableSkills,"Ability execution is a separate probe");r.nova.mapping=mapping;
  var motor=body.characterMotor;var solver=motor.Motor;var state=machine.state;var bank=body.inputBank;
  Check(state is GenericCharacterMain&&body.master.GetBody()==body&&body.isServer&&motor.hasEffectiveAuthority,"Original spawned Commando input/authority contract");
  Check(RoR2Content.Items.JumpBoost&&DLC3Content.Items.JumpDamageStrike&&DLC1Content.Items.GummyCloneIdentifier&&string.IsNullOrEmpty(body.GetComponent<SfxLocator>().jumpSound),"Combined original empty inventory/jump contract");
  var gravity=Physics.gravity;var layers=solver.CollidableLayers;var stable=solver.StableGroundLayers;NovaInputBridge bridge=null;NovaDiagnosticDisplay display=null;
  CharacterBody.JumpDelegate jumped=()=>{r.nova.localJumpCallbacks++;};CharacterMotor.HitGroundDelegate landed=(ref CharacterMotor.HitGroundInfo hit)=>{r.nova.landings++;};body.onJump+=jumped;motor.onHitGroundAuthority+=landed;
  try{
   if(!cfg.stageGeometry){obstacle=GameObject.CreatePrimitive(PrimitiveType.Cube);obstacle.name="Owned Nova floor";obstacle.layer=30;obstacle.transform.position=new Vector3(0,9,0);obstacle.transform.localScale=new Vector3(200,1,200);}
   solver.StableGroundLayers=cfg.stageGeometry?LayerIndex.world.mask:1<<30;solver.CollidableLayers=solver.StableGroundLayers;solver.SetGroundSolvingActivation(true);Physics.SyncTransforms();Physics.gravity=new Vector3(0,cfg.sourceGravity,0);
   var deadline=Time.realtimeSinceStartup+3;while(!solver.GroundingStatus.IsStableOnGround&&Time.realtimeSinceStartup<deadline){yield return new WaitForEndOfFrame();ObserveAutomaticModelFollow(body);}
   Check(solver.GroundingStatus.IsStableOnGround&&r.nova.landings==1&&body.healthComponent.health==110,"Original spawned body landing before physical input");
   // Diagnostic aim stance only; original state/direction still choose and turn toward bank aim.
   body.SetAimTimer(130);
   display=new NovaDiagnosticDisplay(body.modelLocator.modelTransform,artifactBundle,cfg.displayAssets,obstacle,spine);
   if(cfg.stageGeometry)display.camera.cullingMask|=LayerIndex.world.mask;
   if(cfg.combatSpine)PrepareCombatScene(body,cfg);
   bridge=body.gameObject.AddComponent<NovaInputBridge>();bridge.bank=bank;bridge.mapping=mapping;bridge.enablePrimary=spine;bridge.enableAllSkills=cfg.combatSpine;bridge.diagnosticInput=bringup;r.nova.originalInputConsumer=true;
   r.phase=bringup?"nova-spine-bringup":"nova-commando-ready";Save();float began=Time.realtimeSinceStartup,next=0,restingY=solver.TransientPosition.y;var previous=solver.TransientPosition;int priorJumpCount=motor.jumpCount;
   float initialAge=SpawnedStateAge(state,"age"),initialFixed=SpawnedStateAge(state,"fixedAge");var aimField=typeof(GenericCharacterMain).GetField("aimDirection",BindingFlags.NonPublic|BindingFlags.Instance);
   while(r.freePlay||Time.realtimeSinceStartup-began<(bringup?20:90)){
    yield return new WaitForEndOfFrame();ObserveAutomaticModelFollow(body);TemporaryOverlayManager.OverlayUpdate();
    Check(string.IsNullOrEmpty(bridge.error),"Nova bridge input failure: "+bridge.error);Check((cfg.combatSpine||machine.state==state)&&body.gameObject.activeInHierarchy&&body.master.GetBody()==body&&motor.hasEffectiveAuthority,"Original physical simulation state/link/authority changed");
    float elapsed=Time.realtimeSinceStartup-began;var position=solver.TransientPosition;r.nova.pathLength+=Vector3.Distance(position,previous);var delta=position-previous;delta.y=0;r.nova.planarPathLength+=delta.magnitude;previous=position;if(motor.jumpCount>priorJumpCount)r.nova.jumpTransitions+=motor.jumpCount-priorJumpCount;priorJumpCount=motor.jumpCount;r.nova.maxRise=Mathf.Max(r.nova.maxRise,position.y-restingY);
    var stateAim=machine.state is GenericCharacterMain?(Vector3)aimField.GetValue(machine.state):Vector3.zero;
    if(bridge.aim.sqrMagnitude>.1f&&Vector3.Distance(stateAim,bank.aimDirection)<.001f)r.nova.aimConsumed=true;
    if(r.nova.planarPathLength>3&&elapsed>15&&bank.moveVector==Vector3.zero&&motor.velocity.sqrMagnitude<.0001f&&solver.GroundingStatus.IsStableOnGround)r.nova.stopped=true;
    if(spine)ObserveSpinePrimary(body);
    if(cfg.combatSpine)ObserveCombat(body,machine);
    if(bringup){bridge.movement=elapsed<3?Vector2.right:elapsed<6?Vector2.left:Vector2.zero;bridge.aim=elapsed<6?Vector2.right:cfg.combatSpine?CombatAim(body):Vector2.up;bridge.DiagnosticJump(elapsed>7&&elapsed<7.2f);bridge.diagnosticPrimary=elapsed>9&&elapsed<12;bridge.diagnosticSecondary=cfg.combatSpine&&elapsed>12.3f&&elapsed<12.5f;bridge.diagnosticUtility=cfg.combatSpine&&elapsed>14&&elapsed<14.2f;bridge.diagnosticSpecial=cfg.combatSpine&&elapsed>16&&elapsed<16.2f;}
    display.Observe(position,bank.aimDirection);
    if(elapsed>=next){if(r.freePlay&&r.nova.observations.Count>=900)r.nova.observations.RemoveAt(0);r.nova.observations.Add(new NovaSample{seconds=elapsed,raw=NovaInputBridge.ReadRaw(),input=bank.moveVector,aim=bank.aimDirection,stateAim=stateAim,velocity=motor.velocity,position=position,grounded=solver.GroundingStatus.IsStableOnGround,jump=bank.jump.down,jumpCount=motor.jumpCount});r.nova.samples++;next=elapsed+.1f;}
    r.nova.seconds=elapsed;r.nova.fixedTicks=bridge.fixedTicks;r.nova.jumpPresses=bridge.jumpPresses;r.automaticFrames++;if(Time.frameCount%30==0)Save();
   }
   r.automaticSeconds=Time.realtimeSinceStartup-began;r.spawnedStateAge=SpawnedStateAge(state,"age")-initialAge;r.spawnedFixedAge=SpawnedStateAge(state,"fixedAge")-initialFixed;
   bridge.enabled=false;yield return new WaitForSeconds(.5f);
   Check(r.automaticSeconds>=(bringup?20:90)&&r.nova.fixedTicks>(bringup?300:1000)&&r.nova.samples>(bringup?100:300),"Physical Commando sustained callbacks");Check(r.nova.planarPathLength>5&&r.nova.stopped,"Physical movement and original stopping not observed");Check(r.nova.aimConsumed&&(bringup||bridge.aimTicks>10),"Physical right-stick aim not consumed by original state");if(spine)Check(r.primary.shots>0&&(cfg.combatSpine?body.skillLocator.primary.CanExecute():body.skillLocator.primary.stock==1),"Original primary firing/readiness not observed");Check(r.nova.jumpTransitions>0&&r.nova.jumpPresses>=r.nova.jumpTransitions&&r.nova.maxRise>.5f&&r.nova.landings>=2&&solver.GroundingStatus.IsStableOnGround&&motor.jumpCount==0,"Physical jump/original landing incomplete");Save();
   if(cfg.combatSpine)Check(r.combat.secondaryEntries>0&&r.combat.utilityEntries>0&&r.combat.specialEntries>0&&r.combat.projectiles>0&&r.combat.damageEvents>0&&r.combat.healthAfter<r.combat.healthBefore,"Integrated original skills/projectile/target damage incomplete");
  }finally{if(bridge){bridge.enabled=false;Destroy(bridge);}if(cfg.combatSpine)CleanupCombatScene();if(display!=null)display.Dispose();body.onJump-=jumped;motor.onHitGroundAuthority-=landed;Physics.gravity=gravity;solver.CollidableLayers=layers;solver.StableGroundLayers=stable;solver.SetGroundSolvingActivation(false);}
 }
}
