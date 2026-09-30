using System;
using System.Collections;
using EntityStates;
using KinematicCharacterController;
using RoR2;
using UnityEngine;

// Reuse the measured floor/event contract; all state/motor/solver ticks remain original Unity callbacks.
public sealed partial class MovementBatchProbe {
 IEnumerator AutomaticGroundBoundary(CharacterBody body,EntityStateMachine machine,Result cfg){
  bool floor=r.id!="body-state-spawn-state-auto-gravity",wall=r.id=="body-state-spawn-state-auto-ground-wall";
  bool scripted=r.id=="body-state-spawn-state-auto-ground-stop"||wall;
  var motor=body.characterMotor;var solver=motor.Motor;var input=body.inputBank;var state=machine.state;
  Check(cfg.sourceGravity<0&&motor.useGravity&&state is GenericCharacterMain,"Original automatic gravity prerequisites");
  var gravity=Physics.gravity;var layers=solver.CollidableLayers;var stable=solver.StableGroundLayers;
  float initialAge=SpawnedStateAge(state,"age"),initialFixed=SpawnedStateAge(state,"fixedAge");var origin=solver.TransientPosition;
  GameObject ownedWall=null;
  CharacterMotor.HitGroundDelegate landed=(ref CharacterMotor.HitGroundInfo hit)=>{r.landingEvents++;r.landingVelocity=hit.velocity.y;};
  motor.onHitGroundAuthority+=landed;
  try{
   if(floor){
    Check(GlobalEventManager.instance&&RunArtifactManager.instance&&RoR2Content.Artifacts.WeakAssKnees&&!RunArtifactManager.instance.IsArtifactEnabled(RoR2Content.Artifacts.WeakAssKnees),"Original inactive fall-artifact/server event context");
    obstacle=new GameObject("Owned automatic landing floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(40,1,40);
    if(wall){ownedWall=new GameObject("Owned automatic wall");ownedWall.layer=30;ownedWall.transform.position=new Vector3(2,12,0);ownedWall.AddComponent<BoxCollider>().size=new Vector3(1,5,6);}
    solver.StableGroundLayers=1<<30;solver.CollidableLayers=1<<30;solver.SetGroundSolvingActivation(true);Physics.SyncTransforms();
   }
   Physics.gravity=new Vector3(0,cfg.sourceGravity,0);r.gravity=Physics.gravity.y;r.phase=floor?"automatic-source-gravity-landing":"automatic-source-gravity-pulse";Save();
   if(floor){
    var deadline=Time.realtimeSinceStartup+3;
    while(!solver.GroundingStatus.IsStableOnGround&&Time.realtimeSinceStartup<deadline){TemporaryOverlayManager.OverlayUpdate();yield return null;}
    r.grounded=solver.GroundingStatus.IsStableOnGround;r.landingHeight=solver.TransientPosition.y;
    Check(r.grounded&&r.landingEvents==1&&r.landingVelocity<0&&Mathf.Abs(motor.velocity.y)<.001f&&r.landingHeight>9.5f&&r.landingHeight<10.5f&&motor.jumpCount==0,"Original automatic landing/event/grounding");
    Check(body.healthComponent.health==110,"Short original landing changed health");
   }else{
    while(SpawnedStateAge(state,"fixedAge")-initialFixed<.5f){TemporaryOverlayManager.OverlayUpdate();yield return null;}
    r.gravitySeconds=SpawnedStateAge(state,"fixedAge")-initialFixed;r.fallVelocity=motor.velocity.y;r.y=solver.TransientPosition.y-origin.y;Save();
    Check(Mathf.Abs(r.fallVelocity-cfg.sourceGravity*r.gravitySeconds)<Mathf.Abs(cfg.sourceGravity)*.08f&&Mathf.Abs(r.y-.5f*cfg.sourceGravity*r.gravitySeconds*r.gravitySeconds)<.4f&&r.y<0,"Original automatic source gravity velocity/displacement");
    Check(r.landingEvents==0&&!solver.GroundingStatus.IsStableOnGround,"Free-fall pulse unexpectedly landed");
    // End this diagnostic pulse without translating the actor; the later hold uses zero gravity.
    Physics.gravity=Vector3.zero;motor.velocity=Vector3.zero;
   }
   float began=Time.realtimeSinceStartup;var resting=solver.TransientPosition;origin=resting;
   bool moved=false,stopped=false;if(scripted){input.moveVector=Vector3.right;input.aimDirection=Vector3.right;}
   r.phase=scripted?"automatic-grounded-scripted-motion":"automatic-gravity-neutral-hold";Save();
   while(Time.realtimeSinceStartup-began<60){
    TemporaryOverlayManager.OverlayUpdate();float elapsed=Time.realtimeSinceStartup-began;
    Check(machine.state==state&&body.gameObject.activeInHierarchy,"Automatic grounded state/root changed");
    if(floor)Check(solver.GroundingStatus.IsStableOnGround&&Mathf.Abs(solver.TransientPosition.y-r.landingHeight)<.02f&&Mathf.Abs(motor.velocity.y)<.001f,"Automatic stable floor hold");
    if(scripted&&!moved&&elapsed>=1){
     r.x=solver.TransientPosition.x-origin.x;
     Check(wall?r.x>.8f&&r.x<1.05f:r.x>5&&r.x<9,"Original automatic grounded movement/contact");input.moveVector=Vector3.zero;moved=true;Save();
    }
    if(scripted&&moved&&!stopped&&elapsed>=2){
     r.z=solver.TransientPosition.x-origin.x;resting=solver.TransientPosition;
     Check(motor.velocity.sqrMagnitude<.000001f&&motor.moveDirection==Vector3.zero&&(wall?r.z>.8f&&r.z<1.05f:r.z>=r.x&&r.z<r.x+2),"Original automatic grounded braking/contact");stopped=true;Save();
    }
    if(!scripted||stopped)Check(Vector3.Distance(solver.TransientPosition,resting)<.02f,"Automatic gravity/ground neutral drift");
    r.automaticFrames++;yield return null;
   }
   r.automaticSeconds=Time.realtimeSinceStartup-began;r.spawnedStateAge=SpawnedStateAge(state,"age")-initialAge;r.spawnedFixedAge=SpawnedStateAge(state,"fixedAge")-initialFixed;
   Check(r.automaticSeconds>=60&&r.automaticFrames>300&&r.spawnedStateAge>55&&r.spawnedFixedAge>55&&(!scripted||(moved&&stopped)),"Automatic gravity/ground sustained ages/input sequence");
   Check(!floor||r.landingEvents==1,"Unexpected repeated original landing event");Save();
  }finally{
   body.gameObject.SetActive(false);input.moveVector=Vector3.zero;motor.onHitGroundAuthority-=landed;
   Physics.gravity=gravity;solver.CollidableLayers=layers;solver.StableGroundLayers=stable;solver.SetGroundSolvingActivation(false);
   if(ownedWall)Destroy(ownedWall);
  }
 }
}
