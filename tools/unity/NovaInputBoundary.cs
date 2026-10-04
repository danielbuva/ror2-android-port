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
 [Serializable] public class NovaReport {public bool novaOnly,originalInputConsumer,stopped,aimConsumed;public int samples,fixedTicks,jumpPresses,localJumpCallbacks,jumpTransitions,landings;public float seconds,pathLength,planarPathLength,maxRise;public uint spawnedBodyId,masterId;public NovaInputBridge.Mapping mapping;public List<NovaSample> observations=new List<NovaSample>();}
 bool IsNovaInput(){return r.id=="body-state-spawn-state-auto-nova-controls";}
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
  NovaInputBridge.RequireNova();r.nova=new NovaReport{novaOnly=true,spawnedBodyId=body.netId.Value,masterId=body.master.netId.Value};
  var mappingPath=System.IO.Path.Combine(Application.persistentDataPath,"nova-input-mapping.json");
  Check(File.Exists(mappingPath),"Measured Nova mapping required before physical Commando test");var mapping=JsonUtility.FromJson<NovaInputBridge.Mapping>(File.ReadAllText(mappingPath));mapping.Validate(r.attempt);Check(!mapping.enableSkills,"Ability execution is a separate probe");r.nova.mapping=mapping;
  var motor=body.characterMotor;var solver=motor.Motor;var state=machine.state;var bank=body.inputBank;
  Check(state is GenericCharacterMain&&body.master.GetBody()==body&&body.isServer&&motor.hasEffectiveAuthority,"Original spawned Commando input/authority contract");
  Check(RoR2Content.Items.JumpBoost&&DLC3Content.Items.JumpDamageStrike&&DLC1Content.Items.GummyCloneIdentifier&&string.IsNullOrEmpty(body.GetComponent<SfxLocator>().jumpSound),"Combined original empty inventory/jump contract");
  var gravity=Physics.gravity;var layers=solver.CollidableLayers;var stable=solver.StableGroundLayers;NovaInputBridge bridge=null;NovaDiagnosticDisplay display=null;
  CharacterBody.JumpDelegate jumped=()=>{r.nova.localJumpCallbacks++;};CharacterMotor.HitGroundDelegate landed=(ref CharacterMotor.HitGroundInfo hit)=>{r.nova.landings++;};body.onJump+=jumped;motor.onHitGroundAuthority+=landed;
  try{
   obstacle=GameObject.CreatePrimitive(PrimitiveType.Cube);obstacle.name="Owned Nova floor";obstacle.layer=30;obstacle.transform.position=new Vector3(0,9,0);obstacle.transform.localScale=new Vector3(200,1,200);
   solver.StableGroundLayers=1<<30;solver.CollidableLayers=1<<30;solver.SetGroundSolvingActivation(true);Physics.SyncTransforms();Physics.gravity=new Vector3(0,cfg.sourceGravity,0);
   var deadline=Time.realtimeSinceStartup+3;while(!solver.GroundingStatus.IsStableOnGround&&Time.realtimeSinceStartup<deadline){yield return new WaitForEndOfFrame();ObserveAutomaticModelFollow(body);}
   Check(solver.GroundingStatus.IsStableOnGround&&r.nova.landings==1&&body.healthComponent.health==110,"Original spawned body landing before physical input");
   // Diagnostic aim stance only; original state/direction still choose and turn toward bank aim.
   body.SetAimTimer(130);
   display=new NovaDiagnosticDisplay(body.modelLocator.modelTransform,artifactBundle,cfg.displayAssets,obstacle);
   bridge=body.gameObject.AddComponent<NovaInputBridge>();bridge.bank=bank;bridge.mapping=mapping;r.nova.originalInputConsumer=true;
   r.phase="nova-commando-ready";Save();float began=Time.realtimeSinceStartup,next=0,restingY=solver.TransientPosition.y;var previous=solver.TransientPosition;int priorJumpCount=motor.jumpCount;
   float initialAge=SpawnedStateAge(state,"age"),initialFixed=SpawnedStateAge(state,"fixedAge");var aimField=typeof(GenericCharacterMain).GetField("aimDirection",BindingFlags.NonPublic|BindingFlags.Instance);
   while(Time.realtimeSinceStartup-began<90){
    yield return new WaitForEndOfFrame();ObserveAutomaticModelFollow(body);TemporaryOverlayManager.OverlayUpdate();
    Check(string.IsNullOrEmpty(bridge.error),"Nova bridge input failure: "+bridge.error);Check(machine.state==state&&body.gameObject.activeInHierarchy&&body.master.GetBody()==body&&motor.hasEffectiveAuthority,"Original physical simulation state/link/authority changed");
    float elapsed=Time.realtimeSinceStartup-began;var position=solver.TransientPosition;r.nova.pathLength+=Vector3.Distance(position,previous);var delta=position-previous;delta.y=0;r.nova.planarPathLength+=delta.magnitude;previous=position;if(motor.jumpCount>priorJumpCount)r.nova.jumpTransitions+=motor.jumpCount-priorJumpCount;priorJumpCount=motor.jumpCount;r.nova.maxRise=Mathf.Max(r.nova.maxRise,position.y-restingY);
    var stateAim=(Vector3)aimField.GetValue(state);
    if(bridge.aim.sqrMagnitude>.1f&&Vector3.Distance(stateAim,bank.aimDirection)<.001f)r.nova.aimConsumed=true;
    if(r.nova.planarPathLength>3&&elapsed>15&&bank.moveVector==Vector3.zero&&motor.velocity.sqrMagnitude<.0001f&&solver.GroundingStatus.IsStableOnGround)r.nova.stopped=true;
    display.Observe(position,bank.aimDirection);
    if(elapsed>=next){r.nova.observations.Add(new NovaSample{seconds=elapsed,raw=NovaInputBridge.ReadRaw(),input=bank.moveVector,aim=bank.aimDirection,stateAim=stateAim,velocity=motor.velocity,position=position,grounded=solver.GroundingStatus.IsStableOnGround,jump=bank.jump.down,jumpCount=motor.jumpCount});r.nova.samples++;next=elapsed+.1f;}
    r.nova.seconds=elapsed;r.nova.fixedTicks=bridge.fixedTicks;r.nova.jumpPresses=bridge.jumpPresses;r.automaticFrames++;if(Time.frameCount%30==0)Save();
   }
   r.automaticSeconds=Time.realtimeSinceStartup-began;r.spawnedStateAge=SpawnedStateAge(state,"age")-initialAge;r.spawnedFixedAge=SpawnedStateAge(state,"fixedAge")-initialFixed;
   bridge.enabled=false;yield return new WaitForSeconds(.5f);
   Check(r.automaticSeconds>=90&&r.nova.fixedTicks>1000&&r.nova.samples>300,"Physical Commando sustained callbacks");Check(r.nova.planarPathLength>5&&r.nova.stopped,"Physical movement and original stopping not observed");Check(r.nova.aimConsumed&&bridge.aimTicks>10,"Physical right-stick aim not consumed by original state");Check(r.nova.jumpTransitions>0&&r.nova.jumpPresses>=r.nova.jumpTransitions&&r.nova.maxRise>.5f&&r.nova.landings>=2&&solver.GroundingStatus.IsStableOnGround&&motor.jumpCount==0,"Physical jump/original landing incomplete");Save();
  }finally{if(bridge){bridge.enabled=false;Destroy(bridge);}if(display!=null)display.Dispose();body.onJump-=jumped;motor.onHitGroundAuthority-=landed;Physics.gravity=gravity;solver.CollidableLayers=layers;solver.StableGroundLayers=stable;solver.SetGroundSolvingActivation(false);}
 }
}
