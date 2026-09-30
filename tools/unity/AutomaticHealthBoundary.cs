using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;

// Observe original fixed callbacks after accepted body Start; no replacement health simulation.
public sealed partial class MovementBatchProbe {
 IEnumerator AutomaticHealthBoundary(CharacterBody body,EntityStateMachine machine){
  var health=body.healthComponent;bool barrier=r.id=="body-state-spawn-state-auto-barrier";
  Check(health&&health.body==body&&!health.enabled&&health.health==110&&health.barrier==0&&body.regen>0,"Original automatic health starting contract");
  health.enabled=true;r.automaticHealthEnabled=true;r.healthRegen=body.regen;
  var active=body.GetComponents<MonoBehaviour>().Where(x=>x.enabled).ToArray();
  r.automaticCallbacks=active.Select(x=>x.GetType().FullName).ToArray();
  Check(active.Length==5&&active.Contains(body)&&active.Contains(body.characterMotor)&&active.Contains(body.characterMotor.Motor)&&active.Contains(machine)&&active.Contains(health),"Unexpected health callback activation");
  var accumulator=typeof(HealthComponent).GetField("regenAccumulator",BindingFlags.Instance|BindingFlags.NonPublic);
  r.regenBefore=(float)accumulator.GetValue(health);
  if(barrier){health.AddBarrier(20);r.barrierBefore=health.barrier;Check(r.barrierBefore==20&&health.fullBarrier==110,"Original public AddBarrier result");}
  float initialFixed=SpawnedStateAge(machine.state,"fixedAge"),duration=barrier?1f:.5f;
  r.phase=barrier?"automatic-original-barrier-decay":"automatic-original-health-regeneration";Save();
  while(SpawnedStateAge(machine.state,"fixedAge")-initialFixed<duration){TemporaryOverlayManager.OverlayUpdate();if(barrier)ObserveBarrierEffect(body);yield return null;}
  r.healthTickSeconds=SpawnedStateAge(machine.state,"fixedAge")-initialFixed;r.regenAfter=(float)accumulator.GetValue(health);r.barrierAfter=health.barrier;Save();
  // Original accumulator subtracts whole positive healing units; compare its remainder independently.
  float expected=r.regenBefore+r.healthRegen*r.healthTickSeconds;if(expected>1)expected-=Mathf.Floor(expected);
  Check(Mathf.Abs(r.regenAfter-expected)<.08f&&health.health==110,"Original automatic regeneration accumulator/full health");
  if(barrier){
   // Solve dB/dt = -(fullBarrier/60 + B/12); allow the shipped discrete Euler step.
   r.barrierExpected=(r.barrierBefore+health.fullBarrier/5f)*Mathf.Exp(-r.healthTickSeconds/12f)-health.fullBarrier/5f;Save();
   Check(r.barrierAfter>0&&r.barrierAfter<r.barrierBefore&&Mathf.Abs(r.barrierAfter-r.barrierExpected)<.15f,"Original automatic barrier decay differs from measured formula");
  }else Check(r.barrierAfter==0,"Neutral health tick created barrier");
 }
}
