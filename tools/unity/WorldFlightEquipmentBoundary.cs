using System;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Original equipment factories, flight providers and vehicle simulation remain unchanged.
// Own only Android presentation, observed objects and the explicit developer selection.
public sealed partial class MovementBatchProbe {
 [Serializable] public class FlightEquipmentObservation {
  public string source;public uint netId;public int samples,flightProviderPeak,antiGravityPeak;
  public float seconds,maxSpeed,maxRise;public bool passengerObserved,naturallyDestroyed;
  public Vector3 origin;
 }
 [Serializable] public class DeveloperEquipmentSelection {public string equipment,previous;public float seconds;public bool activated;}
 readonly Dictionary<GameObject,FlightEquipmentObservation> worldFlightObjects=new Dictionary<GameObject,FlightEquipmentObservation>();
 readonly Dictionary<JetpackController,CharacterMaster> worldFlightDeathOwners=new Dictionary<JetpackController,CharacterMaster>();
 readonly Dictionary<Renderer,bool> worldFlightVisibility=new Dictionary<Renderer,bool>();
 EquipmentState developerEquipmentPrior;Inventory developerEquipmentInventory;int developerEquipmentCursor;float developerEquipmentChangedAt;

 void PrepareFlightEquipmentSource(GameObject source,List<GameObject> effects){
  Check(source.GetComponent<NetworkIdentity>(),"Original flight equipment network identity absent");
  if(source.name=="JetpackController")Check(source.GetComponent<JetpackController>()&&source.GetComponent<NetworkedBodyAttachment>(),"Original flight attachment/controller absent");
  else {
   var vehicle=source.GetComponent<FireballVehicle>();var seat=source.GetComponent<VehicleSeat>();
   Check(vehicle&&seat&&seat.seatPosition&&source.GetComponent<Rigidbody>()&&source.GetComponent<HitBoxGroup>(),"Original vehicle physics/seat/overlap contract absent");
   Check(!seat.disablePassengerMotor&&!seat.disableCharacterNetworkTransform&&!seat.inheritRotation&&seat.hidePassenger&&seat.passengerState.stateType==typeof(EntityStates.GenericCharacterVehicleSeated),"Unmeasured source passenger policy");
   Check(vehicle.explosionEffectPrefab&&vehicle.overlapHitEffectPrefab,"Original vehicle effects absent");effects.Add(vehicle.explosionEffectPrefab);effects.Add(vehicle.overlapHitEffectPrefab);
  }
  foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
  PresentCommerceModel(source.transform);
 }
 void ObserveFlightEquipment(){
  foreach(var obj in Resources.FindObjectsOfTypeAll<GameObject>().Where(x=>x&&x.scene.IsValid()&&(x.name=="JetpackController(Clone)"||x.name=="FireballVehicle(Clone)"))){
   var attachment=obj.GetComponent<NetworkedBodyAttachment>();var seat=obj.GetComponent<VehicleSeat>();
   Check(attachment?attachment.attachedBody==worldPlayer:seat&&seat.currentPassengerBody==worldPlayer,"Flight equipment owned passenger/body differs");
   FlightEquipmentObservation entry;if(!worldFlightObjects.TryGetValue(obj,out entry)){
    var id=obj.GetComponent<NetworkIdentity>();Check(id&&id.netId.Value!=0&&NetworkServer.FindLocalObject(id.netId)==obj,"Original flight equipment local network ownership absent");
    entry=new FlightEquipmentObservation{source=obj.name,netId=id.netId.Value,origin=worldPlayer.transform.position};worldFlightObjects.Add(obj,entry);r.world.equipment.flightObjects.Add(entry);worldObjects.Add(obj);
    var jetpack=obj.GetComponent<JetpackController>();if(jetpack){Check(worldDisplayModel&&worldDisplayModel.GetEquipmentDisplayObjects(RoR2Content.Equipment.Jetpack.equipmentIndex).Count==1,"Native flight requires original wing display");worldFlightDeathOwners.Add(jetpack,worldPlayer.master);}
   }
   entry.samples++;entry.seconds=Run.instance.GetRunStopwatch();entry.maxRise=Mathf.Max(entry.maxRise,worldPlayer.transform.position.y-entry.origin.y);entry.maxSpeed=Mathf.Max(entry.maxSpeed,worldPlayer.characterMotor.velocity.magnitude);entry.passengerObserved|=seat&&seat.currentPassengerBody==worldPlayer;
   entry.flightProviderPeak=Mathf.Max(entry.flightProviderPeak,worldPlayer.characterMotor.flightParameters.channeledFlightGranterCount);entry.antiGravityPeak=Mathf.Max(entry.antiGravityPeak,worldPlayer.characterMotor.gravityParameters.channeledAntiGravityGranterCount);
  }
  foreach(var pair in worldFlightObjects)if(!pair.Key)pair.Value.naturallyDestroyed=true;
  // Native OnDestroy removes the body callback, but retains its death listener.
  // Remove only the exact observed owned instance from its measured master.
  foreach(var pair in worldFlightDeathOwners.Where(x=>!x.Key).ToArray())RemoveFlightDeathOwner(pair.Key,pair.Value);
  if(worldDisplayModel)foreach(var info in worldDisplayModel.baseRendererInfos)if(info.renderer){if(!worldFlightVisibility.ContainsKey(info.renderer))worldFlightVisibility.Add(info.renderer,info.renderer.forceRenderingOff);info.renderer.forceRenderingOff=worldFlightVisibility[info.renderer]||worldDisplayModel.invisibilityCount>0;}
 }
 void RemoveFlightDeathOwner(JetpackController controller,CharacterMaster master){if(master){master.onBodyDeath.RemoveListener(controller.ReleaseBody);r.world.equipment.ownedFlightDeathCallbacksRemoved++;}worldFlightDeathOwners.Remove(controller);}
 void CleanupFlightEquipment(){
  if(r.world==null||r.world.equipment==null)return;ObserveFlightEquipment();
  foreach(var pair in worldFlightDeathOwners.ToArray())RemoveFlightDeathOwner(pair.Key,pair.Value);
  foreach(var obj in worldFlightObjects.Keys)if(obj)NetworkServer.Destroy(obj);
  foreach(var pair in worldFlightVisibility)if(pair.Key)pair.Key.forceRenderingOff=pair.Value;worldFlightVisibility.Clear();
  if(developerEquipmentInventory){SetDeveloperEquipmentState(developerEquipmentInventory,developerEquipmentPrior);developerEquipmentInventory=null;}
  developerEquipmentCursor=0;developerEquipmentChangedAt=0;
 }
 void VerifyFlightEquipmentCleanup(){
  if(r.world==null||r.world.equipment==null)return;
  Check(worldFlightObjects.Keys.All(x=>!x)&&worldFlightDeathOwners.Count==0&&!developerEquipmentInventory,"Owned flight objects/listeners/developer selection survived teardown");
  r.world.equipment.flightCleaned=true;worldFlightObjects.Clear();
 }
 bool DeveloperEquipmentStimulus(NovaInputBridge bridge,float elapsed){
  try{return DeveloperEquipmentStimulusOwned(bridge,elapsed);}
  catch(Exception error){if(string.IsNullOrEmpty(r.firstFailure)){r.firstFailure="Developer equipment selection: "+error;r.firstFailurePhase=r.phase;Save();}throw;}
 }
 static void SetDeveloperEquipmentState(Inventory inventory,EquipmentState state){
  // The original selector handles an empty slot and retains the active set.
  // Do not index activeEquipmentSet before the native setter creates it.
  inventory.SetEquipment(state,inventory.activeEquipmentSlot,inventory.FindBestEquipmentSetIndex(true));
 }
 bool DeveloperEquipmentStimulusOwned(NovaInputBridge bridge,float elapsed){
  var names=r.developerEquipmentSequence;if(names==null||names.Length==0)return false;
  Check(names.Length<=2&&names.Distinct().Count()==names.Length&&names.All(x=>x=="Jetpack"||x=="FireBallDash")&&r.debugOptions!=null&&!string.IsNullOrWhiteSpace(r.debugOptions.purpose)&&r.debugOptions.purpose.Length<=160,"Developer flight selection requires bounded explicit purpose");
  if(developerEquipmentCursor<names.Length&&elapsed>=4+developerEquipmentCursor*30&&worldPlayer.characterMotor.isGrounded&&!worldPlayer.currentVehicle&&!JetpackController.FindJetpackController(worldPlayer.gameObject)){
   Check(NetworkServer.active&&r.itemDisplays.ready,"Developer equipment source/display ownership absent");
   if(!developerEquipmentInventory){developerEquipmentInventory=worldPlayer.inventory;developerEquipmentPrior=developerEquipmentInventory.GetActiveEquipment();}
   var def=EligibleWorldEquipment().Single(x=>x.name==names[developerEquipmentCursor]);var previous=EquipmentCatalog.GetEquipmentDef(developerEquipmentInventory.currentEquipmentIndex);
   SetDeveloperEquipmentState(developerEquipmentInventory,new EquipmentState(def.equipmentIndex,Run.FixedTimeStamp.negativeInfinity,1));r.debugAcceleration.equipmentSelections.Add(new DeveloperEquipmentSelection{equipment=def.name,previous=previous?previous.name:"",seconds=elapsed});r.debugAcceleration.everAssisted=true;r.debugAcceleration.normalGameAcceptanceEligible=false;
   developerEquipmentCursor++;developerEquipmentChangedAt=elapsed;
  }
  if(developerEquipmentCursor>0){var selection=r.debugAcceleration.equipmentSelections.Last();selection.activated|=r.world.equipment.actions.Any(x=>x.equipment==selection.equipment&&x.seconds>=developerEquipmentChangedAt);if(!selection.activated&&worldEquipmentSlot.equipmentIndex==developerEquipmentInventory.currentEquipmentIndex&&worldEquipmentSlot.stock>0&&elapsed-developerEquipmentChangedAt<5)bridge.diagnosticEquipment=true;}
  return true;
 }
}
