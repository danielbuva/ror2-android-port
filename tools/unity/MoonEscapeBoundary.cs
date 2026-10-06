using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;

// Schedule the original fixed-time queue while the composed app keeps startup inactive.
public sealed partial class MovementBatchProbe {
 bool ownsMoonTimers;TimerQueue moonTimerQueue;FieldInfo moonTimerCount,moonTimerArray;
 void PrepareMoonTimers(){
  Check(!ownsMoonTimers&&FindObjectsOfType<RoR2Application>().Length==0,"Original application already schedules its timers");
  moonTimerQueue=RoR2Application.fixedTimeTimers;Check(moonTimerQueue!=null,"Original fixed-time queue missing");
  moonTimerCount=typeof(TimerQueue).GetField("count",BindingFlags.Instance|BindingFlags.NonPublic);
  moonTimerArray=typeof(TimerQueue).GetField("timers",BindingFlags.Instance|BindingFlags.NonPublic);
  Check(moonTimerCount!=null&&moonTimerArray!=null&&(int)moonTimerCount.GetValue(moonTimerQueue)==0,"Existing fixed-time callbacks; refuse another scheduler");
  ownsMoonTimers=true;r.moon.originalTimersScheduled=true;
 }
 void TickMoonTimers(){
  if(!ownsMoonTimers||r.moon==null||r.moon.cleaned)return;
  moonTimerQueue.Update(Time.fixedDeltaTime);r.moon.fixedTimerTicks++;
  r.moon.pendingFixedTimers=(int)moonTimerCount.GetValue(moonTimerQueue);
 }
 void StopMoonTimers(){
  ownsMoonTimers=false;
  // PhaseObjects.OnDisable may queue the source completion event during cleanup.
  // Disable only this scene's delayed receivers before deactivating source roots.
  if(moonRoots!=null)foreach(var delayed in moonRoots.SelectMany(x=>x.GetComponentsInChildren<RoR2.EntityLogic.DelayedEvent>(true)))delayed.enabled=false;
 }
 void CleanupMoonTimers(){
  if(moonTimerQueue==null)return;var timers=(Array)moonTimerArray.GetValue(moonTimerQueue);var remove=new List<TimerQueue.TimerHandle>();
  int count=(int)moonTimerCount.GetValue(moonTimerQueue);
  for(int i=0;i<count;i++){
   var timer=timers.GetValue(i);var action=(Action)timer.GetType().GetField("action").GetValue(timer);
   var target=action==null?null:action.Target as RoR2.EntityLogic.DelayedEvent;
   if(target&&target.gameObject.scene==stageGeometryScene)remove.Add((TimerQueue.TimerHandle)timer.GetType().GetField("handle").GetValue(timer));
  }
  foreach(var handle in remove)moonTimerQueue.RemoveTimer(handle);
  r.moon.cancelledOwnedTimers=remove.Count;r.moon.pendingFixedTimers=(int)moonTimerCount.GetValue(moonTimerQueue);r.moon.timersStopped=true;
  moonTimerQueue=null;moonTimerCount=null;moonTimerArray=null;
 }
 void ObserveMoonEscape(){
  if(!moonEscape||moonRoots==null)return;
  var zone=moonRoots.Single(x=>x.name=="Moon2DropshipZone");
  var states=zone.transform.Find("States");Check(states,"Original dropship state hierarchy missing");
  r.moon.dropshipStates=Enumerable.Range(0,states.childCount).Select(i=>states.GetChild(i)).Where(x=>x.gameObject.activeSelf).Select(x=>x.name).ToArray();
  var holdout=zone.GetComponentInChildren<HoldoutZoneController>(true);Check(holdout,"Original dropship holdout missing");
  r.moon.dropshipCharge=holdout.charge;r.moon.dropshipHoldoutActive=holdout.isActiveAndEnabled;r.moon.dropshipPosition=holdout.transform.position;
  var escapeState=moonEscape.mainStateMachine.state as EscapeSequenceController.EscapeSequenceMainState;
  r.moon.escapeSecondsRemaining=escapeState==null?0:((Run.FixedTimeStamp)typeof(EscapeSequenceController.EscapeSequenceMainState).GetField("endTime",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(escapeState)).timeUntilClamped;
  var stealer=FindObjectsOfType<ItemStealController>();r.moon.liveItemStealers=stealer.Length;
  r.moon.itemStealerObserved|=stealer.Any(x=>x.GetComponent<NetworkedBodyAttachment>()&&x.GetComponent<UnityEngine.Networking.NetworkIdentity>().netId.Value!=0);
 }
}
