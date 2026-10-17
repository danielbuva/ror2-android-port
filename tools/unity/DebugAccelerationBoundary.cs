// Subsystem: diagnostics (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareDebugAcceleration (DebugAccelerationSession.Prepare); teardown CleanupDebugAcceleration (Dispose).
using System;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEngine;

// Temporary, default-off development controls. Never change mission progress or
// remove enemies: original attacks, holdout occupancy and ending code still run.
public sealed partial class MovementBatchProbe {
 [Serializable] public class DebugAccelerationOptions {
  public bool invincibility,highDamage,fastCharge,movementBoost,jumpBoost;
  public string purpose;
 }
 [Serializable] public class DebugToggleEvent {
  public float seconds;public string toggle,source;public bool enabled;
 }
 [Serializable] public class DeveloperItemGrant {public string item;public int before,after,removed;}
 [Serializable] public class DebugAccelerationReport {
  public int version=1;public bool everAssisted,normalGameAcceptanceEligible=true,restored,ownerDestroyed;
  public DebugAccelerationOptions active=new DebugAccelerationOptions();
  public string purpose,error;
  public float damageMultiplier=1000,chargeRateMultiplier=8,movementMultiplier=2,jumpMultiplier=6;
  public float originalBaseDamage,originalLevelDamage,originalBaseMoveSpeed,originalLevelMoveSpeed;
  public float appliedBaseDamage,appliedLevelDamage,appliedBaseMoveSpeed,appliedLevelMoveSpeed;
  public float observedDamage,observedMoveSpeed;public bool godModeObserved;
  public float originalBaseJumpPower,originalLevelJumpPower,appliedBaseJumpPower,appliedLevelJumpPower,observedJumpPower;public int observedMaxJumpCount;
  public float lastOriginalChargeRate,lastAssistedChargeRate;public int positiveChargeCallbacks,unchangedNonpositiveChargeCallbacks,chargeZones;
  public List<DebugToggleEvent> events=new List<DebugToggleEvent>();
  public List<DeveloperItemGrant> itemGrants=new List<DeveloperItemGrant>();
  public List<DeveloperEquipmentSelection> equipmentSelections=new List<DeveloperEquipmentSelection>();
 }
 // Shared with IntegratedWorld's graphics button.
 bool debugPanel;
 DebugAccelerationSession debugAccelerationSession;
 DebugAccelerationSession DebugAccelerationOwner {get{if(debugAccelerationSession==null)debugAccelerationSession=new DebugAccelerationSession(this);return debugAccelerationSession;}}
 void PrepareDebugAcceleration(CharacterBody body){DebugAccelerationOwner.Prepare(body);}
 void ApplyDeveloperItemGrants(){DebugAccelerationOwner.ApplyDeveloperItemGrants();}
 void CleanupDeveloperItemGrants(){DebugAccelerationOwner.CleanupDeveloperItemGrants();}
 void DebugToggle(string name,bool enabled,string source){DebugAccelerationOwner.DebugToggle(name,enabled,source);}
 void ApplyDebugAcceleration(DebugAccelerationOptions next,string source){DebugAccelerationOwner.ApplyDebugAcceleration(next,source);}
 void TickDebugAcceleration(){DebugAccelerationOwner.Tick();}
 void AccelerateDebugCharge(ref float rate){DebugAccelerationOwner.AccelerateDebugCharge(ref rate);}
 void RemoveDebugChargeCallbacks(){DebugAccelerationOwner.RemoveDebugChargeCallbacks();}
 void SetDebugToggle(int index,bool enabled,string source){DebugAccelerationOwner.SetDebugToggle(index,enabled,source);}
 void DrawDebugAcceleration(){DebugAccelerationOwner.Draw();}
 string DebugAccelerationLabel(){return DebugAccelerationOwner.DebugAccelerationLabel();}
 void CleanupDebugAcceleration(){DebugAccelerationOwner.Dispose();}

 // Nested to retain access to shared state without widening its visibility.
 // Create on first use, including diagnostic input before Prepare, and retain
 // after Dispose so repeated cleanup and later calls keep the original state.
 sealed class DebugAccelerationSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  CharacterBody debugBody;bool debugPriorGodMode,ownsDebugAcceleration;float debugNextZoneScan;
  readonly HashSet<HoldoutZoneController> debugChargeZones=new HashSet<HoldoutZoneController>();
  Inventory debugGrantInventory;
  public DebugAccelerationSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public void Prepare(CharacterBody body){
   // Unity can create an empty inline report while reading the launch selection.
   // Serialized presence is not ownership of live body fields or callbacks.
   coordinator.Check(!debugBody&&!ownsDebugAcceleration,"Debug acceleration owner already exists");
   debugBody=body;debugPriorGodMode=body.healthComponent.godMode;
   coordinator.r.debugAcceleration=new DebugAccelerationReport{purpose=coordinator.r.debugOptions==null||string.IsNullOrWhiteSpace(coordinator.r.debugOptions.purpose)?"Interactive developer controls":coordinator.r.debugOptions.purpose,originalBaseDamage=body.baseDamage,originalLevelDamage=body.levelDamage,originalBaseMoveSpeed=body.baseMoveSpeed,originalLevelMoveSpeed=body.levelMoveSpeed};
   ownsDebugAcceleration=true;
   coordinator.r.debugAcceleration.originalBaseJumpPower=body.baseJumpPower;coordinator.r.debugAcceleration.originalLevelJumpPower=body.levelJumpPower;
   ApplyDebugAcceleration(coordinator.r.debugOptions??new DebugAccelerationOptions(),"launch selection");
   if(coordinator.r.goldshoresRoute&&coordinator.r.goldshores!=null&&coordinator.r.goldshores.diagnosticShrineSpawned)DebugToggle("diagnosticGoldShrinePlacement",true,"selected assisted integration route");
   if(coordinator.r.developerSurvivorOverride)DebugToggle("developerSurvivorOverride",true,"launch selection");
   ApplyDeveloperItemGrants();
  }
  public void ApplyDeveloperItemGrants(){
   var names=coordinator.r.developerItemGrants;if(names==null||names.Length==0)return;
   coordinator.Check(names.Length<=3&&names.Distinct().Count()==names.Length&&coordinator.r.debugOptions!=null&&!string.IsNullOrWhiteSpace(coordinator.r.debugOptions.purpose)&&coordinator.r.debugOptions.purpose.Length<=160,"Developer grants require a bounded explicit experiment purpose");
   coordinator.Check(UnityEngine.Networking.NetworkServer.active&&debugBody.inventory&&coordinator.worldLootDefinitions!=null,"Developer grant inventory ownership absent");
   // Validate the complete request before changing the original inventory.
   var definitions=names.Select(name=>coordinator.worldLootDefinitions.SingleOrDefault(x=>x.name==name)).ToArray();
   coordinator.Check(definitions.All(x=>x&&!x.unlockableDef&&!x.requiredExpansion&&!x.hidden&&x.DoesNotContainTag(ItemTag.WorldUnique)&&x.DoesNotContainTag(ItemTag.IgnoreForDropList)&&!Run.instance.IsItemExpansionLocked(x.itemIndex)),"Developer grant is outside the eligible composed item domain");
   debugGrantInventory=debugBody.inventory;coordinator.r.debugAcceleration.everAssisted=true;coordinator.r.debugAcceleration.normalGameAcceptanceEligible=false;
   foreach(var def in definitions){var entry=new DeveloperItemGrant{item=def.name,before=debugGrantInventory.GetItemCountPermanent(def)};coordinator.r.debugAcceleration.itemGrants.Add(entry);debugGrantInventory.GiveItemPermanent(def,1);entry.after=debugGrantInventory.GetItemCountPermanent(def);coordinator.Check(entry.after==entry.before+1,"Original developer item grant failed: "+def.name);coordinator.Save();}
  }
  public void CleanupDeveloperItemGrants(){
   if(debugGrantInventory){coordinator.Check(UnityEngine.Networking.NetworkServer.active,"Developer inventory teardown requires owned server");foreach(var entry in coordinator.r.debugAcceleration.itemGrants){var def=ItemCatalog.GetItemDef(ItemCatalog.FindItemIndex(entry.item));int before=debugGrantInventory.GetItemCountPermanent(def);int count=Mathf.Min(1,before);if(count>0)debugGrantInventory.RemoveItemPermanent(def,count);entry.removed=count;coordinator.Check(debugGrantInventory.GetItemCountPermanent(def)==before-count,"Original developer grant restore failed");}}
   debugGrantInventory=null;
  }
  public void DebugToggle(string name,bool enabled,string source){
   var report=coordinator.r.debugAcceleration;report.events.Add(new DebugToggleEvent{seconds=coordinator.r.nova==null?0:coordinator.r.nova.seconds,toggle=name,enabled=enabled,source=source});
   if(enabled){report.everAssisted=true;report.normalGameAcceptanceEligible=false;}
  }
  public void ApplyDebugAcceleration(DebugAccelerationOptions next,string source){
   var report=coordinator.r.debugAcceleration;var active=report.active;
   if(active.invincibility!=next.invincibility){debugBody.healthComponent.godMode=next.invincibility||debugPriorGodMode;DebugToggle("invincibility",next.invincibility,source);}
   bool stats=active.highDamage!=next.highDamage||active.movementBoost!=next.movementBoost||active.jumpBoost!=next.jumpBoost;
   if(active.highDamage!=next.highDamage){
    debugBody.baseDamage=report.originalBaseDamage*(next.highDamage?report.damageMultiplier:1);debugBody.levelDamage=report.originalLevelDamage*(next.highDamage?report.damageMultiplier:1);DebugToggle("highDamage",next.highDamage,source);
   }
   if(active.movementBoost!=next.movementBoost){
    debugBody.baseMoveSpeed=report.originalBaseMoveSpeed*(next.movementBoost?report.movementMultiplier:1);debugBody.levelMoveSpeed=report.originalLevelMoveSpeed*(next.movementBoost?report.movementMultiplier:1);DebugToggle("movementBoost",next.movementBoost,source);
   }
   if(active.jumpBoost!=next.jumpBoost){
    // Keep the original single-jump consumer, collision, gravity and landing code.
    // This toggle grants no items and changes no jump-count or position fields.
    debugBody.baseJumpPower=report.originalBaseJumpPower*(next.jumpBoost?report.jumpMultiplier:1);debugBody.levelJumpPower=report.originalLevelJumpPower*(next.jumpBoost?report.jumpMultiplier:1);DebugToggle("jumpBoost",next.jumpBoost,source);
   }
   if(active.fastCharge!=next.fastCharge){DebugToggle("fastCharge",next.fastCharge,source);if(!next.fastCharge)RemoveDebugChargeCallbacks();debugNextZoneScan=0;}
   report.active=new DebugAccelerationOptions{invincibility=next.invincibility,highDamage=next.highDamage,fastCharge=next.fastCharge,movementBoost=next.movementBoost,jumpBoost=next.jumpBoost,purpose=report.purpose};
   if(stats)debugBody.RecalculateStats();
   report.appliedBaseDamage=debugBody.baseDamage;report.appliedLevelDamage=debugBody.levelDamage;report.appliedBaseMoveSpeed=debugBody.baseMoveSpeed;report.appliedLevelMoveSpeed=debugBody.levelMoveSpeed;
   report.observedDamage=debugBody.damage;report.observedMoveSpeed=debugBody.moveSpeed;report.godModeObserved=debugBody.healthComponent.godMode;
   report.appliedBaseJumpPower=debugBody.baseJumpPower;report.appliedLevelJumpPower=debugBody.levelJumpPower;report.observedJumpPower=debugBody.jumpPower;report.observedMaxJumpCount=debugBody.maxJumpCount;
   coordinator.Save();
  }
  public void Tick(){
   if(!debugBody||coordinator.r==null||coordinator.r.debugAcceleration==null||coordinator.r.debugAcceleration.restored)return;
   try{
    coordinator.r.debugAcceleration.observedDamage=debugBody.damage;coordinator.r.debugAcceleration.observedMoveSpeed=debugBody.moveSpeed;coordinator.r.debugAcceleration.godModeObserved=debugBody.healthComponent.godMode;
    coordinator.r.debugAcceleration.observedJumpPower=debugBody.jumpPower;coordinator.r.debugAcceleration.observedMaxJumpCount=debugBody.maxJumpCount;
    if(coordinator.r.results!=null&&coordinator.r.results.reportGenerated)return;
    var a=coordinator.r.debugAcceleration.active;
    if(UnityEngine.Input.GetKeyDown(KeyCode.F1))SetDebugToggle(0,!a.invincibility,"F1");
    if(UnityEngine.Input.GetKeyDown(KeyCode.F2))SetDebugToggle(1,!a.highDamage,"F2");
    if(UnityEngine.Input.GetKeyDown(KeyCode.F3))SetDebugToggle(2,!a.fastCharge,"F3");
    if(UnityEngine.Input.GetKeyDown(KeyCode.F4))SetDebugToggle(3,!a.movementBoost,"F4");
    if(UnityEngine.Input.GetKeyDown(KeyCode.F5))SetDebugToggle(4,!a.jumpBoost,"F5");
    if(coordinator.r.debugAcceleration.active.fastCharge&&Time.realtimeSinceStartup>=debugNextZoneScan){
     debugNextZoneScan=Time.realtimeSinceStartup+.5f;
     debugChargeZones.RemoveWhere(x=>!x);
     foreach(var zone in FindObjectsOfType<HoldoutZoneController>())if(debugChargeZones.Add(zone))zone.calcChargeRate+=AccelerateDebugCharge;
     coordinator.r.debugAcceleration.chargeZones=debugChargeZones.Count;
    }
   }catch(Exception e){coordinator.r.debugAcceleration.error=e.ToString();coordinator.Save();}
  }
  public void AccelerateDebugCharge(ref float rate){
   // Zero occupancy and negative discharge are unchanged. The original controller
   // integrates/clamps charge and invokes its own completion events.
   if(!coordinator.r.debugAcceleration.active.fastCharge)return;
   if(rate<=0){coordinator.r.debugAcceleration.unchangedNonpositiveChargeCallbacks++;return;}
   coordinator.r.debugAcceleration.lastOriginalChargeRate=rate;rate*=coordinator.r.debugAcceleration.chargeRateMultiplier;
   coordinator.r.debugAcceleration.lastAssistedChargeRate=rate;coordinator.r.debugAcceleration.positiveChargeCallbacks++;
  }
  public void RemoveDebugChargeCallbacks(){foreach(var zone in debugChargeZones)if(zone)zone.calcChargeRate-=AccelerateDebugCharge;debugChargeZones.Clear();if(coordinator.r!=null&&coordinator.r.debugAcceleration!=null)coordinator.r.debugAcceleration.chargeZones=0;}
  public void SetDebugToggle(int index,bool enabled,string source){
   var a=coordinator.r.debugAcceleration.active;var next=new DebugAccelerationOptions{invincibility=a.invincibility,highDamage=a.highDamage,fastCharge=a.fastCharge,movementBoost=a.movementBoost,jumpBoost=a.jumpBoost};
   if(index==0)next.invincibility=enabled;if(index==1)next.highDamage=enabled;if(index==2)next.fastCharge=enabled;if(index==3)next.movementBoost=enabled;
   if(index==4)next.jumpBoost=enabled;
   ApplyDebugAcceleration(next,source);
  }
  public void Draw(){
   if(coordinator.r.debugAcceleration==null||coordinator.r.debugAcceleration.restored||!debugBody||!debugBody.healthComponent.alive)return;
   var report=coordinator.r.debugAcceleration;float x=coordinator.recoveredHud?20:Screen.width-270;
   var style=new GUIStyle(GUI.skin.label){fontSize=18,wordWrap=true};style.normal.textColor=report.everAssisted?Color.yellow:Color.white;
   if(!coordinator.recoveredHud||coordinator.debugPanel)GUI.Label(new Rect(x,140,260,100),report.everAssisted?"DEBUG ASSISTED RUN\nNo normal-game acceptance":"Debug acceleration: OFF",style);
   if(GUI.Button(new Rect(x,coordinator.recoveredHud?Screen.height-250:82,250,46),coordinator.debugPanel?"Hide developer controls":"Developer controls"))coordinator.debugPanel=!coordinator.debugPanel;
   if(!coordinator.debugPanel){if(report.everAssisted){if(coordinator.recoveredHud){style.fontSize=14;GUI.Label(new Rect(20,Screen.height-320,500,54),"DEBUG ASSISTED · "+DebugAccelerationLabel(),style);}else GUI.Label(new Rect(x,240,260,110),DebugAccelerationLabel(),style);}return;}
   var a=report.active;
   if(GUI.Button(new Rect(x,245,250,44),"F1 Invincibility: "+a.invincibility))SetDebugToggle(0,!a.invincibility,"developer panel");
   if(GUI.Button(new Rect(x,295,250,44),"F2 Damage x1000: "+a.highDamage))SetDebugToggle(1,!a.highDamage,"developer panel");
   if(GUI.Button(new Rect(x,345,250,44),"F3 Charge x8: "+a.fastCharge))SetDebugToggle(2,!a.fastCharge,"developer panel");
   if(GUI.Button(new Rect(x,395,250,44),"F4 Movement x2: "+a.movementBoost))SetDebugToggle(3,!a.movementBoost,"developer panel");
   if(GUI.Button(new Rect(x,445,250,44),"F5 Jump power x6: "+a.jumpBoost))SetDebugToggle(4,!a.jumpBoost,"developer panel");
   if(GUI.Button(new Rect(x,495,250,44),"Disable toggles (grants remain)"))ApplyDebugAcceleration(new DebugAccelerationOptions(),"developer panel clear");
  }
  public string DebugAccelerationLabel(){var a=coordinator.r.debugAcceleration.active;return "Invincible "+a.invincibility+" · damage "+(a.highDamage?"x1000":"normal")+"\nCharge "+(a.fastCharge?"x8":"normal")+" · movement "+(a.movementBoost?"x2":"normal")+"\nJump "+(a.jumpBoost?"x6":"normal")+(coordinator.r.debugAcceleration.events.Any(x=>x.toggle=="diagnosticInput"&&x.enabled)?" · diagnostic input":"")+(coordinator.r.debugAcceleration.itemGrants.Count>0?" · granted: "+string.Join(", ",coordinator.r.debugAcceleration.itemGrants.Select(x=>x.item).ToArray()):"");}
  public void Dispose(){
   if(!ownsDebugAcceleration||coordinator.r==null||coordinator.r.debugAcceleration==null||coordinator.r.debugAcceleration.restored)return;
   RemoveDebugChargeCallbacks();
   CleanupDeveloperItemGrants();
   if(debugBody){ApplyDebugAcceleration(new DebugAccelerationOptions(),"owned cleanup");coordinator.Check(debugBody.healthComponent.godMode==debugPriorGodMode&&debugBody.baseDamage==coordinator.r.debugAcceleration.originalBaseDamage&&debugBody.levelDamage==coordinator.r.debugAcceleration.originalLevelDamage&&debugBody.baseMoveSpeed==coordinator.r.debugAcceleration.originalBaseMoveSpeed&&debugBody.levelMoveSpeed==coordinator.r.debugAcceleration.originalLevelMoveSpeed&&debugBody.baseJumpPower==coordinator.r.debugAcceleration.originalBaseJumpPower&&debugBody.levelJumpPower==coordinator.r.debugAcceleration.originalLevelJumpPower,"Debug acceleration restore failed");}
   else{var a=coordinator.r.debugAcceleration.active;if(a.invincibility)DebugToggle("invincibility",false,"owner destroyed");if(a.highDamage)DebugToggle("highDamage",false,"owner destroyed");if(a.fastCharge)DebugToggle("fastCharge",false,"owner destroyed");if(a.movementBoost)DebugToggle("movementBoost",false,"owner destroyed");if(a.jumpBoost)DebugToggle("jumpBoost",false,"owner destroyed");coordinator.r.debugAcceleration.active=new DebugAccelerationOptions{purpose=coordinator.r.debugAcceleration.purpose};coordinator.r.debugAcceleration.ownerDestroyed=true;}
   debugBody=null;ownsDebugAcceleration=false;coordinator.r.debugAcceleration.restored=true;coordinator.Save();
  }
 }
}
