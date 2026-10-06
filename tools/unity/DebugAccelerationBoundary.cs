using System;
using System.Collections.Generic;
using RoR2;
using UnityEngine;

// Temporary, default-off development controls. Never change mission progress or
// remove enemies: original attacks, holdout occupancy and ending code still run.
public sealed partial class MovementBatchProbe {
 [Serializable] public class DebugAccelerationOptions {
  public bool invincibility,highDamage,fastCharge,movementBoost;
  public string purpose;
 }
 [Serializable] public class DebugToggleEvent {
  public float seconds;public string toggle,source;public bool enabled;
 }
 [Serializable] public class DebugAccelerationReport {
  public int version=1;public bool everAssisted,normalGameAcceptanceEligible=true,restored,ownerDestroyed;
  public DebugAccelerationOptions active=new DebugAccelerationOptions();
  public string purpose,error;
  public float damageMultiplier=1000,chargeRateMultiplier=8,movementMultiplier=2;
  public float originalBaseDamage,originalLevelDamage,originalBaseMoveSpeed,originalLevelMoveSpeed;
  public float appliedBaseDamage,appliedLevelDamage,appliedBaseMoveSpeed,appliedLevelMoveSpeed;
  public float observedDamage,observedMoveSpeed;public bool godModeObserved;
  public float lastOriginalChargeRate,lastAssistedChargeRate;public int positiveChargeCallbacks,unchangedNonpositiveChargeCallbacks,chargeZones;
  public List<DebugToggleEvent> events=new List<DebugToggleEvent>();
 }
 CharacterBody debugBody;bool debugPriorGodMode,debugPanel,ownsDebugAcceleration;float debugNextZoneScan;
 readonly HashSet<HoldoutZoneController> debugChargeZones=new HashSet<HoldoutZoneController>();
 void PrepareDebugAcceleration(CharacterBody body){
  // Unity can create an empty inline report while reading the launch selection.
  // Serialized presence is not ownership of live body fields or callbacks.
  Check(!debugBody&&!ownsDebugAcceleration,"Debug acceleration owner already exists");
  debugBody=body;debugPriorGodMode=body.healthComponent.godMode;
  r.debugAcceleration=new DebugAccelerationReport{purpose=r.debugOptions==null||string.IsNullOrWhiteSpace(r.debugOptions.purpose)?"Interactive developer controls":r.debugOptions.purpose,originalBaseDamage=body.baseDamage,originalLevelDamage=body.levelDamage,originalBaseMoveSpeed=body.baseMoveSpeed,originalLevelMoveSpeed=body.levelMoveSpeed};
  ownsDebugAcceleration=true;
  ApplyDebugAcceleration(r.debugOptions??new DebugAccelerationOptions(),"launch selection");
 }
 void DebugToggle(string name,bool enabled,string source){
  var report=r.debugAcceleration;report.events.Add(new DebugToggleEvent{seconds=r.nova==null?0:r.nova.seconds,toggle=name,enabled=enabled,source=source});
  if(enabled){report.everAssisted=true;report.normalGameAcceptanceEligible=false;}
 }
 void ApplyDebugAcceleration(DebugAccelerationOptions next,string source){
  var report=r.debugAcceleration;var active=report.active;
  if(active.invincibility!=next.invincibility){debugBody.healthComponent.godMode=next.invincibility||debugPriorGodMode;DebugToggle("invincibility",next.invincibility,source);}
  bool stats=active.highDamage!=next.highDamage||active.movementBoost!=next.movementBoost;
  if(active.highDamage!=next.highDamage){
   debugBody.baseDamage=report.originalBaseDamage*(next.highDamage?report.damageMultiplier:1);debugBody.levelDamage=report.originalLevelDamage*(next.highDamage?report.damageMultiplier:1);DebugToggle("highDamage",next.highDamage,source);
  }
  if(active.movementBoost!=next.movementBoost){
   debugBody.baseMoveSpeed=report.originalBaseMoveSpeed*(next.movementBoost?report.movementMultiplier:1);debugBody.levelMoveSpeed=report.originalLevelMoveSpeed*(next.movementBoost?report.movementMultiplier:1);DebugToggle("movementBoost",next.movementBoost,source);
  }
  if(active.fastCharge!=next.fastCharge){DebugToggle("fastCharge",next.fastCharge,source);if(!next.fastCharge)RemoveDebugChargeCallbacks();debugNextZoneScan=0;}
  report.active=new DebugAccelerationOptions{invincibility=next.invincibility,highDamage=next.highDamage,fastCharge=next.fastCharge,movementBoost=next.movementBoost,purpose=report.purpose};
  if(stats)debugBody.RecalculateStats();
  report.appliedBaseDamage=debugBody.baseDamage;report.appliedLevelDamage=debugBody.levelDamage;report.appliedBaseMoveSpeed=debugBody.baseMoveSpeed;report.appliedLevelMoveSpeed=debugBody.levelMoveSpeed;
  report.observedDamage=debugBody.damage;report.observedMoveSpeed=debugBody.moveSpeed;report.godModeObserved=debugBody.healthComponent.godMode;
  Save();
 }
 void TickDebugAcceleration(){
  if(!debugBody||r==null||r.debugAcceleration==null||r.debugAcceleration.restored)return;
  try{
   r.debugAcceleration.observedDamage=debugBody.damage;r.debugAcceleration.observedMoveSpeed=debugBody.moveSpeed;r.debugAcceleration.godModeObserved=debugBody.healthComponent.godMode;
   if(r.results!=null&&r.results.reportGenerated)return;
   var a=r.debugAcceleration.active;
   if(UnityEngine.Input.GetKeyDown(KeyCode.F1))SetDebugToggle(0,!a.invincibility,"F1");
   if(UnityEngine.Input.GetKeyDown(KeyCode.F2))SetDebugToggle(1,!a.highDamage,"F2");
   if(UnityEngine.Input.GetKeyDown(KeyCode.F3))SetDebugToggle(2,!a.fastCharge,"F3");
   if(UnityEngine.Input.GetKeyDown(KeyCode.F4))SetDebugToggle(3,!a.movementBoost,"F4");
   if(r.debugAcceleration.active.fastCharge&&Time.realtimeSinceStartup>=debugNextZoneScan){
    debugNextZoneScan=Time.realtimeSinceStartup+.5f;
    debugChargeZones.RemoveWhere(x=>!x);
    foreach(var zone in FindObjectsOfType<HoldoutZoneController>())if(debugChargeZones.Add(zone))zone.calcChargeRate+=AccelerateDebugCharge;
    r.debugAcceleration.chargeZones=debugChargeZones.Count;
   }
  }catch(Exception e){r.debugAcceleration.error=e.ToString();Save();}
 }
 void AccelerateDebugCharge(ref float rate){
  // Zero occupancy and negative discharge are unchanged. The original controller
  // integrates/clamps charge and invokes its own completion events.
  if(!r.debugAcceleration.active.fastCharge)return;
  if(rate<=0){r.debugAcceleration.unchangedNonpositiveChargeCallbacks++;return;}
  r.debugAcceleration.lastOriginalChargeRate=rate;rate*=r.debugAcceleration.chargeRateMultiplier;
  r.debugAcceleration.lastAssistedChargeRate=rate;r.debugAcceleration.positiveChargeCallbacks++;
 }
 void RemoveDebugChargeCallbacks(){foreach(var zone in debugChargeZones)if(zone)zone.calcChargeRate-=AccelerateDebugCharge;debugChargeZones.Clear();if(r!=null&&r.debugAcceleration!=null)r.debugAcceleration.chargeZones=0;}
 void SetDebugToggle(int index,bool enabled,string source){
  var a=r.debugAcceleration.active;var next=new DebugAccelerationOptions{invincibility=a.invincibility,highDamage=a.highDamage,fastCharge=a.fastCharge,movementBoost=a.movementBoost};
  if(index==0)next.invincibility=enabled;if(index==1)next.highDamage=enabled;if(index==2)next.fastCharge=enabled;if(index==3)next.movementBoost=enabled;
  ApplyDebugAcceleration(next,source);
 }
 void DrawDebugAcceleration(){
  if(r.debugAcceleration==null||r.debugAcceleration.restored||!debugBody||!debugBody.healthComponent.alive)return;
  var report=r.debugAcceleration;float x=Screen.width-270;
  var style=new GUIStyle(GUI.skin.label){fontSize=18,wordWrap=true};style.normal.textColor=report.everAssisted?Color.yellow:Color.white;
  GUI.Label(new Rect(x,140,260,100),report.everAssisted?"DEBUG ASSISTED RUN\nNo normal-game acceptance":"Debug acceleration: OFF",style);
  if(GUI.Button(new Rect(x,82,250,46),debugPanel?"Hide developer controls":"Developer controls"))debugPanel=!debugPanel;
  if(!debugPanel){if(report.everAssisted)GUI.Label(new Rect(x,240,260,110),DebugAccelerationLabel(),style);return;}
  var a=report.active;
  if(GUI.Button(new Rect(x,245,250,44),"F1 Invincibility: "+a.invincibility))SetDebugToggle(0,!a.invincibility,"developer panel");
  if(GUI.Button(new Rect(x,295,250,44),"F2 Damage x1000: "+a.highDamage))SetDebugToggle(1,!a.highDamage,"developer panel");
  if(GUI.Button(new Rect(x,345,250,44),"F3 Charge x8: "+a.fastCharge))SetDebugToggle(2,!a.fastCharge,"developer panel");
  if(GUI.Button(new Rect(x,395,250,44),"F4 Movement x2: "+a.movementBoost))SetDebugToggle(3,!a.movementBoost,"developer panel");
  if(GUI.Button(new Rect(x,445,250,44),"Disable all (run stays assisted)"))ApplyDebugAcceleration(new DebugAccelerationOptions(),"developer panel clear");
 }
 string DebugAccelerationLabel(){var a=r.debugAcceleration.active;return "Invincible "+a.invincibility+" · damage "+(a.highDamage?"x1000":"normal")+"\nCharge "+(a.fastCharge?"x8":"normal")+" · movement "+(a.movementBoost?"x2":"normal");}
 void CleanupDebugAcceleration(){
  if(!ownsDebugAcceleration||r==null||r.debugAcceleration==null||r.debugAcceleration.restored)return;
  RemoveDebugChargeCallbacks();
  if(debugBody){ApplyDebugAcceleration(new DebugAccelerationOptions(),"owned cleanup");Check(debugBody.healthComponent.godMode==debugPriorGodMode&&debugBody.baseDamage==r.debugAcceleration.originalBaseDamage&&debugBody.levelDamage==r.debugAcceleration.originalLevelDamage&&debugBody.baseMoveSpeed==r.debugAcceleration.originalBaseMoveSpeed&&debugBody.levelMoveSpeed==r.debugAcceleration.originalLevelMoveSpeed,"Debug acceleration restore failed");}
  else{var a=r.debugAcceleration.active;if(a.invincibility)DebugToggle("invincibility",false,"owner destroyed");if(a.highDamage)DebugToggle("highDamage",false,"owner destroyed");if(a.fastCharge)DebugToggle("fastCharge",false,"owner destroyed");if(a.movementBoost)DebugToggle("movementBoost",false,"owner destroyed");r.debugAcceleration.active=new DebugAccelerationOptions{purpose=r.debugAcceleration.purpose};r.debugAcceleration.ownerDestroyed=true;}
  debugBody=null;ownsDebugAcceleration=false;r.debugAcceleration.restored=true;Save();
 }
}
