// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareFlightEquipmentSource, ObserveFlightEquipment (WorldFlightEquipmentSession); teardown CleanupFlightEquipment (Dispose), then VerifyFlightEquipmentCleanup.
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
  public float seconds,maxSpeed,maxRise,maxVehicleSpeed;public bool passengerObserved,naturallyDestroyed;
  public int passengerRenderers,hiddenPassengerSamples,passengerInvisibilityPeak;
  public Vector3 origin;
 }
 [Serializable] public class DeveloperEquipmentSelection {public string equipment,previous;public float seconds;public bool activated;}
 // Shared discovery window is extended by WorldEquipmentSession.
 float worldFlightDiscoveryUntil;
 WorldFlightEquipmentSession worldFlightEquipmentSession;
 WorldFlightEquipmentSession GetWorldFlightEquipmentSession(){if(worldFlightEquipmentSession==null)worldFlightEquipmentSession=new WorldFlightEquipmentSession(this);return worldFlightEquipmentSession;}
 void PrepareFlightEquipmentSource(GameObject source,List<GameObject> effects){GetWorldFlightEquipmentSession().PrepareFlightEquipmentSource(source,effects);}
 void ObserveFlightEquipment(bool includeInactive=false){GetWorldFlightEquipmentSession().ObserveFlightEquipment(includeInactive);}
 void RemoveFlightDeathOwner(JetpackController controller,CharacterMaster master){GetWorldFlightEquipmentSession().RemoveFlightDeathOwner(controller,master);}
 void CleanupFlightEquipment(){GetWorldFlightEquipmentSession().Dispose();}
 void VerifyFlightEquipmentCleanup(){GetWorldFlightEquipmentSession().VerifyFlightEquipmentCleanup();}
 bool DeveloperEquipmentStimulus(NovaInputBridge bridge,float elapsed){return GetWorldFlightEquipmentSession().DeveloperEquipmentStimulus(bridge,elapsed);}
 static void SetDeveloperEquipmentState(Inventory inventory,EquipmentState state){WorldFlightEquipmentSession.SetDeveloperEquipmentState(inventory,state);}
 bool DeveloperEquipmentStimulusOwned(NovaInputBridge bridge,float elapsed){return GetWorldFlightEquipmentSession().DeveloperEquipmentStimulusOwned(bridge,elapsed);}

 // Create on first use and retain for partial setup, repeated cleanup and later
 // observations. Dispose preserves flight teardown; verification stays separate.
 sealed class WorldFlightEquipmentSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  readonly Dictionary<GameObject,FlightEquipmentObservation> worldFlightObjects=new Dictionary<GameObject,FlightEquipmentObservation>();
  readonly Dictionary<JetpackController,CharacterMaster> worldFlightDeathOwners=new Dictionary<JetpackController,CharacterMaster>();
  float worldFlightDiscoveryNext;
  readonly Dictionary<Renderer,bool> worldFlightVisibility=new Dictionary<Renderer,bool>();
  EquipmentState developerEquipmentPrior;
  Inventory developerEquipmentInventory;
  int developerEquipmentCursor;
  float developerEquipmentChangedAt,developerEquipmentNextAt=4;
  bool developerEquipmentValidated;
  public WorldFlightEquipmentSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public void PrepareFlightEquipmentSource(GameObject source,List<GameObject> effects){
   coordinator.Check(source.GetComponent<NetworkIdentity>(),"Original flight equipment network identity absent");
   if(source.name=="JetpackController")coordinator.Check(source.GetComponent<JetpackController>()&&source.GetComponent<NetworkedBodyAttachment>(),"Original flight attachment/controller absent");
   else {
    var vehicle=source.GetComponent<FireballVehicle>();var seat=source.GetComponent<VehicleSeat>();
    coordinator.Check(vehicle&&seat&&seat.seatPosition&&source.GetComponent<Rigidbody>()&&source.GetComponent<HitBoxGroup>(),"Original vehicle physics/seat/overlap contract absent");
    coordinator.Check(!seat.disablePassengerMotor&&!seat.disableCharacterNetworkTransform&&!seat.inheritRotation&&seat.hidePassenger&&seat.passengerState.stateType==typeof(EntityStates.GenericCharacterVehicleSeated),"Unmeasured source passenger policy");
    coordinator.Check(vehicle.explosionEffectPrefab&&vehicle.overlapHitEffectPrefab,"Original vehicle effects absent");effects.Add(vehicle.explosionEffectPrefab);effects.Add(vehicle.overlapHitEffectPrefab);
   }
   foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){if(coordinator.worldLootSourceMaterials.ContainsKey(renderer))continue;coordinator.worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);coordinator.worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
   coordinator.PresentCommerceModel(source.transform);
  }
  public void ObserveFlightEquipment(bool includeInactive=false){
   // Live updates need scene instances, not every inactive asset in the complete
   // registered catalog. The final cleanup still audits inactive scene objects.
   bool discover=includeInactive||Time.realtimeSinceStartup<coordinator.worldFlightDiscoveryUntil&&Time.realtimeSinceStartup>=worldFlightDiscoveryNext;
   if(discover&&!includeInactive)worldFlightDiscoveryNext=Time.realtimeSinceStartup+.1f;
   var candidates=includeInactive?Resources.FindObjectsOfTypeAll<GameObject>():discover?NetworkServer.objects.Values.Where(x=>x).Select(x=>x.gameObject).ToArray():worldFlightObjects.Keys.ToArray();
   foreach(var obj in candidates.Where(x=>x&&x.scene.IsValid()&&(x.name=="JetpackController(Clone)"||x.name=="FireballVehicle(Clone)"))){
    var attachment=obj.GetComponent<NetworkedBodyAttachment>();var seat=obj.GetComponent<VehicleSeat>();
    coordinator.Check(attachment?attachment.attachedBody==coordinator.worldPlayer:seat&&seat.currentPassengerBody==coordinator.worldPlayer,"Flight equipment owned passenger/body differs");
    FlightEquipmentObservation entry;if(!worldFlightObjects.TryGetValue(obj,out entry)){
     var id=obj.GetComponent<NetworkIdentity>();coordinator.Check(id&&id.netId.Value!=0&&NetworkServer.FindLocalObject(id.netId)==obj,"Original flight equipment local network ownership absent");
     entry=new FlightEquipmentObservation{source=obj.name,netId=id.netId.Value,origin=coordinator.worldPlayer.transform.position};worldFlightObjects.Add(obj,entry);coordinator.r.world.equipment.flightObjects.Add(entry);coordinator.worldObjects.Add(obj);
     var jetpack=obj.GetComponent<JetpackController>();if(jetpack){coordinator.Check(coordinator.worldDisplayModel&&coordinator.worldDisplayModel.GetEquipmentDisplayObjects(RoR2Content.Equipment.Jetpack.equipmentIndex).Count==1,"Native flight requires original wing display");worldFlightDeathOwners.Add(jetpack,coordinator.worldPlayer.master);}
    }
    entry.samples++;entry.seconds=Run.instance.GetRunStopwatch();entry.maxRise=Mathf.Max(entry.maxRise,coordinator.worldPlayer.transform.position.y-entry.origin.y);entry.maxSpeed=Mathf.Max(entry.maxSpeed,coordinator.worldPlayer.characterMotor.velocity.magnitude);entry.passengerObserved|=seat&&seat.currentPassengerBody==coordinator.worldPlayer;
    entry.flightProviderPeak=Mathf.Max(entry.flightProviderPeak,coordinator.worldPlayer.characterMotor.flightParameters.channeledFlightGranterCount);entry.antiGravityPeak=Mathf.Max(entry.antiGravityPeak,coordinator.worldPlayer.characterMotor.gravityParameters.channeledAntiGravityGranterCount);
    var rigidbody=obj.GetComponent<Rigidbody>();if(rigidbody)entry.maxVehicleSpeed=Mathf.Max(entry.maxVehicleSpeed,rigidbody.velocity.magnitude);
    if(seat&&coordinator.worldDisplayModel){entry.passengerInvisibilityPeak=Mathf.Max(entry.passengerInvisibilityPeak,coordinator.worldDisplayModel.invisibilityCount);entry.passengerRenderers=coordinator.worldDisplayModel.GetComponentsInChildren<Renderer>(true).Count(x=>x.enabled);}
   }
   foreach(var pair in worldFlightObjects)if(!pair.Key)pair.Value.naturallyDestroyed=true;
   // Native OnDestroy removes the body callback, but retains its death listener.
   // Remove only the exact observed owned instance from its measured master.
   foreach(var pair in worldFlightDeathOwners.Where(x=>!x.Key).ToArray())RemoveFlightDeathOwner(pair.Key,pair.Value);
   if(coordinator.worldDisplayModel){
    // The disabled native model's renderer-info array is not the Android view's
    // full renderer set. Honor the original seated policy on the owned hierarchy.
    bool hidden=coordinator.worldDisplayModel.invisibilityCount>0||coordinator.worldPlayer&&coordinator.worldPlayer.currentVehicle&&coordinator.worldPlayer.currentVehicle.hidePassenger;
    var renderers=coordinator.worldDisplayModel.GetComponentsInChildren<Renderer>(true);
    foreach(var renderer in renderers){if(!worldFlightVisibility.ContainsKey(renderer))worldFlightVisibility.Add(renderer,renderer.forceRenderingOff);renderer.forceRenderingOff=worldFlightVisibility[renderer]||hidden;}
    if(coordinator.worldPlayer&&coordinator.worldPlayer.currentVehicle&&hidden&&renderers.Length>0&&renderers.All(x=>x.forceRenderingOff)){
     FlightEquipmentObservation entry;if(worldFlightObjects.TryGetValue(coordinator.worldPlayer.currentVehicle.gameObject,out entry))entry.hiddenPassengerSamples++;
    }
   }
  }
  public void RemoveFlightDeathOwner(JetpackController controller,CharacterMaster master){if(master){master.onBodyDeath.RemoveListener(controller.ReleaseBody);coordinator.r.world.equipment.ownedFlightDeathCallbacksRemoved++;}worldFlightDeathOwners.Remove(controller);}
  public void Dispose(){
   if(coordinator.r.world==null||coordinator.r.world.equipment==null)return;ObserveFlightEquipment(true);
   foreach(var pair in worldFlightDeathOwners.ToArray())RemoveFlightDeathOwner(pair.Key,pair.Value);
   foreach(var obj in worldFlightObjects.Keys)if(obj)NetworkServer.Destroy(obj);
   foreach(var pair in worldFlightVisibility)if(pair.Key)pair.Key.forceRenderingOff=pair.Value;worldFlightVisibility.Clear();
   if(developerEquipmentInventory){SetDeveloperEquipmentState(developerEquipmentInventory,developerEquipmentPrior);developerEquipmentInventory=null;}
   developerEquipmentCursor=0;developerEquipmentChangedAt=0;developerEquipmentNextAt=4;developerEquipmentValidated=false;
   coordinator.worldFlightDiscoveryUntil=worldFlightDiscoveryNext=0;
  }
  public void VerifyFlightEquipmentCleanup(){
   if(coordinator.r.world==null||coordinator.r.world.equipment==null)return;
   coordinator.Check(worldFlightObjects.Keys.All(x=>!x)&&worldFlightDeathOwners.Count==0&&!developerEquipmentInventory,"Owned flight objects/listeners/developer selection survived teardown");
   coordinator.r.world.equipment.flightCleaned=true;worldFlightObjects.Clear();
  }
  public bool DeveloperEquipmentStimulus(NovaInputBridge bridge,float elapsed){
   try{return DeveloperEquipmentStimulusOwned(bridge,elapsed);}
   catch(Exception error){if(string.IsNullOrEmpty(coordinator.r.firstFailure)){coordinator.r.firstFailure="Developer equipment selection: "+error;coordinator.r.firstFailurePhase=coordinator.r.phase;coordinator.Save();}throw;}
  }
  public static void SetDeveloperEquipmentState(Inventory inventory,EquipmentState state){
   // The original selector handles an empty slot and retains the active set.
   // Do not index activeEquipmentSet before the native setter creates it.
   inventory.SetEquipment(state,inventory.activeEquipmentSlot,inventory.FindBestEquipmentSetIndex(true));
  }
  public bool DeveloperEquipmentStimulusOwned(NovaInputBridge bridge,float elapsed){
   var names=coordinator.r.developerEquipmentSequence;if(names==null||names.Length==0)return false;
   if(!developerEquipmentValidated){
    var eligible=coordinator.EligibleWorldEquipment().Where(def=>Run.instance.IsEquipmentAvailable(def.equipmentIndex)).Select(def=>def.name).ToArray();
    coordinator.Check(names.Length<=12&&names.Distinct().Count()==names.Length&&names.All(eligible.Contains)&&coordinator.r.debugOptions!=null&&!string.IsNullOrWhiteSpace(coordinator.r.debugOptions.purpose)&&coordinator.r.debugOptions.purpose.Length<=160,"Developer equipment selection requires available original definitions and a bounded explicit purpose");
    developerEquipmentValidated=true;
   }
   if(developerEquipmentCursor<names.Length&&elapsed>=developerEquipmentNextAt&&coordinator.worldPlayer.characterMotor.isGrounded&&!coordinator.worldPlayer.currentVehicle&&!JetpackController.FindJetpackController(coordinator.worldPlayer.gameObject)){
    coordinator.Check(NetworkServer.active&&coordinator.r.itemDisplays.ready,"Developer equipment source/display ownership absent");
    if(!developerEquipmentInventory){developerEquipmentInventory=coordinator.worldPlayer.inventory;developerEquipmentPrior=developerEquipmentInventory.GetActiveEquipment();}
    var def=coordinator.EligibleWorldEquipment().Single(x=>x.name==names[developerEquipmentCursor]);var previous=EquipmentCatalog.GetEquipmentDef(developerEquipmentInventory.currentEquipmentIndex);
    coordinator.r.debugAcceleration.everAssisted=true;coordinator.r.debugAcceleration.normalGameAcceptanceEligible=false;SetDeveloperEquipmentState(developerEquipmentInventory,new EquipmentState(def.equipmentIndex,Run.FixedTimeStamp.negativeInfinity,1));coordinator.r.debugAcceleration.equipmentSelections.Add(new DeveloperEquipmentSelection{equipment=def.name,previous=previous?previous.name:"",seconds=elapsed});
    developerEquipmentCursor++;developerEquipmentChangedAt=elapsed;
    developerEquipmentNextAt=elapsed+(def.name=="Jetpack"||def.name=="FireBallDash"?30:12);
   }
   if(developerEquipmentCursor>0){var selection=coordinator.r.debugAcceleration.equipmentSelections.Last();selection.activated|=coordinator.r.world.equipment.actions.Any(x=>x.equipment==selection.equipment&&x.seconds>=developerEquipmentChangedAt);if(!selection.activated&&coordinator.worldEquipmentSlot.equipmentIndex==developerEquipmentInventory.currentEquipmentIndex&&coordinator.worldEquipmentSlot.stock>0&&elapsed-developerEquipmentChangedAt<5)bridge.diagnosticEquipment=true;}
   return true;
  }
 }
}
