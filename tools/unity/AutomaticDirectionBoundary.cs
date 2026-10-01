using System;
using System.Collections;
using EntityStates;
using RoR2;
using UnityEngine;

// Only diagnostic input and observations; original main-state and direction callbacks turn the model base.
public sealed partial class MovementBatchProbe {
 bool IsAutomaticDirection(){return r.id.StartsWith("body-state-spawn-state-auto-direction-");}
 IEnumerator AutomaticDirectionBoundary(CharacterBody body,EntityStateMachine machine){
  var direction=body.GetComponent<CharacterDirection>();var input=body.inputBank;var motor=body.characterMotor;var solver=motor.Motor;var state=machine.state;
  bool motion=r.id=="body-state-spawn-state-auto-direction-motion",reverse=r.id=="body-state-spawn-state-auto-direction-reverse",aim=r.id=="body-state-spawn-state-auto-direction-aim";
  Check(direction.enabled&&direction.hasEffectiveAuthority&&direction.targetTransform==body.modelLocator.modelBaseTransform&&direction.modelAnimator==body.modelLocator.modelTransform.GetComponent<Animator>(),"Original automatic direction Start/cache/authority");
  Check(!direction.driveFromRootRotation&&!direction.shouldDirectPitch&&direction.turnSpeed==720&&!direction.targetTransform.gameObject.activeInHierarchy&&!body.shouldAim,"Measured recovered direction contract changed");
  r.automaticDirectionStarted=true;r.directionTarget=direction.targetTransform.name;r.directionTurnSpeed=direction.turnSpeed;r.directionStartYaw=direction.yaw;
  Check(Mathf.Abs(Mathf.DeltaAngle(direction.yaw,0))<.001f,"Original spawned direction baseline");
  var origin=solver.TransientPosition;float age=SpawnedStateAge(state,"age"),fixedAge=SpawnedStateAge(state,"fixedAge"),began=Time.realtimeSinceStartup;
  bool first=false,second=false,stopped=false;float heldYaw=direction.yaw;Vector3 resting=origin;
  if(motion||reverse){input.moveVector=Vector3.right;input.aimDirection=Vector3.right;}
  if(aim){
   var animator=body.modelLocator.modelTransform.GetComponent<AimAnimator>();Check(animator&&animator.aimType==AimAnimator.AimType.Direct&&!animator.isActiveAndEnabled,"Recovered direct aim contract");
   input.aimDirection=Vector3.back;body.SetAimTimer(1.5f);Check(body.shouldAim,"Original public aim timer did not enable aim");
  }
  r.phase=aim?"automatic-original-direction-aim":motion||reverse?"automatic-original-direction-input":"automatic-original-direction-neutral";Save();
  while(Time.realtimeSinceStartup-began<60){
   ObserveTeleportOverlays(body);TemporaryOverlayManager.OverlayUpdate();float elapsed=Time.realtimeSinceStartup-began;
   Check(machine.state==state&&state is GenericCharacterMain&&direction.enabled&&direction.hasEffectiveAuthority,"Original automatic direction/state changed");
   Check(Quaternion.Angle(body.transform.rotation,Quaternion.identity)<.001f&&Mathf.Abs(direction.pitch)<.001f,"Direction changed solver root rotation or unsupported pitch");
   if((motion||reverse)&&!first&&elapsed>=1){
    r.directionEastYaw=direction.yaw;r.directionEastTargetYaw=direction.targetTransform.eulerAngles.y;r.x=solver.TransientPosition.x-origin.x;
    Check(Mathf.Abs(Mathf.DeltaAngle(direction.yaw,90))<.2f&&Mathf.Abs(Mathf.DeltaAngle(r.directionEastTargetYaw,90))<.3f&&r.x>4&&r.x<9&&Mathf.Abs(motor.velocity.x-7)<.001f,"Original automatic east facing/motion");
    input.moveVector=reverse?Vector3.left:Vector3.zero;if(reverse)input.aimDirection=Vector3.left;first=true;Save();
   }
   if(reverse&&first&&!second&&elapsed>=2){
    r.directionWestYaw=direction.yaw;r.y=solver.TransientPosition.x-origin.x;
    Check(Mathf.Abs(Mathf.DeltaAngle(direction.yaw,270))<.2f&&Mathf.Abs(Mathf.DeltaAngle(direction.targetTransform.eulerAngles.y,270))<.3f&&r.y<r.x&&r.y>-3&&Mathf.Abs(motor.velocity.x+7)<.001f,"Original automatic reverse facing/motion");
    input.moveVector=Vector3.zero;second=true;Save();
   }
   if((motion||reverse)&&first&&!stopped&&elapsed>=(reverse?3:2)){
    resting=solver.TransientPosition;r.z=resting.x-origin.x;heldYaw=direction.yaw;
    Check(motor.velocity.sqrMagnitude<.000001f&&motor.moveDirection==Vector3.zero&&(reverse?r.z<=r.y&&r.z>r.y-2:r.z>=r.x&&r.z<r.x+2),"Original automatic direction braking");stopped=true;Save();
   }
   if(aim&&!first&&elapsed>=.8f){
    r.directionAimYaw=direction.yaw;Check(body.shouldAim&&Mathf.Abs(Mathf.DeltaAngle(direction.yaw,180))<.2f&&Mathf.Abs(Mathf.DeltaAngle(direction.targetTransform.eulerAngles.y,180))<.3f,"Original timer-driven automatic aim facing");first=true;Save();
   }
   if(aim&&first&&!second&&elapsed>=2){
    r.directionAimExpired=!body.shouldAim;Check(r.directionAimExpired&&direction.moveVector==Vector3.zero,"Original aim timer natural expiry/main-state neutral input");
    input.aimDirection=Vector3.forward;heldYaw=direction.yaw;second=true;stopped=true;Save();
   }
   if(stopped)Check(Vector3.Distance(solver.TransientPosition,resting)<.001f&&Mathf.Abs(Mathf.DeltaAngle(direction.yaw,heldYaw))<.02f&&Mathf.Abs(Mathf.DeltaAngle(direction.targetTransform.eulerAngles.y,heldYaw))<.03f,"Original automatic neutral facing/position hold");
   if(!motion&&!reverse)Check(Vector3.Distance(solver.TransientPosition,origin)<.001f,"Direction-only input translated actor");
   if(!motion&&!reverse&&!aim)Check(Mathf.Abs(Mathf.DeltaAngle(direction.yaw,r.directionStartYaw))<.001f&&Mathf.Abs(Mathf.DeltaAngle(direction.targetTransform.eulerAngles.y,r.directionStartYaw))<.001f,"Original automatic neutral facing drift");
   r.automaticFrames++;yield return null;
  }
  r.directionFinalYaw=direction.yaw;r.automaticSeconds=Time.realtimeSinceStartup-began;r.spawnedStateAge=SpawnedStateAge(state,"age")-age;r.spawnedFixedAge=SpawnedStateAge(state,"fixedAge")-fixedAge;
  Check(r.automaticSeconds>=60&&r.automaticFrames>300&&r.spawnedStateAge>55&&r.spawnedFixedAge>55&&(!(motion||reverse||aim)||first&&stopped)&&(!reverse&&!aim||second),"Original automatic direction sequence/hold incomplete");Save();
 }
}
