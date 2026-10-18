// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWorldLegendaryItemSource, ObserveWorldLegendaryItems (WorldLegendaryItemsSession); teardown CleanupWorldLegendaryItems (Dispose).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Items;
using UnityEngine;
using UnityEngine.Networking;

// Original controllers and state/configuration data provide gameplay. This owns
// the Android provider/material boundary and records actual native instances.
public sealed partial class MovementBatchProbe {
 [Serializable] public class LegendaryItemObservation {public string source;public uint netId;public string[] states;public int samples,maxIcicles;public float maxCharge,maxVisualSpin;public bool forceHostAuthority,localPlayerAuthority,hasAuthority;}
 WorldLegendaryItemsSession worldLegendaryItemsSession;
 WorldLegendaryItemsSession GetWorldLegendaryItemsSession(){if(worldLegendaryItemsSession==null)worldLegendaryItemsSession=new WorldLegendaryItemsSession(this);return worldLegendaryItemsSession;}
 bool IsWorldLegendaryItemSource(string path){return GetWorldLegendaryItemsSession().IsWorldLegendaryItemSource(path);}
 bool PrepareWorldLegendaryItemSource(string path,GameObject source,int index){return GetWorldLegendaryItemsSession().PrepareWorldLegendaryItemSource(path,source,index);}
 void ObserveWorldLegendaryItems(bool force=false){GetWorldLegendaryItemsSession().ObserveWorldLegendaryItems(force);}
 void CleanupWorldLegendaryItems(){GetWorldLegendaryItemsSession().Dispose();}

 // Create on first use and retain for partial setup, repeated cleanup and later
 // observations. Dispose preserves instance teardown before source restoration.
 sealed class WorldLegendaryItemsSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  readonly Dictionary<GameObject,LegendaryItemObservation> worldLegendaryItemInstances=new Dictionary<GameObject,LegendaryItemObservation>();
  readonly Dictionary<Behaviour,bool> worldLegendaryRemoteTransforms=new Dictionary<Behaviour,bool>();
  readonly Dictionary<NetworkedBodyAttachment,bool> worldLegendaryHostAuthority=new Dictionary<NetworkedBodyAttachment,bool>();
  static readonly string[] worldLegendaryControllers={"HeadstompersController","IcicleAura","LaserTurbineController","VagrantNovaItemBodyAttachment"};
  public WorldLegendaryItemsSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public bool IsWorldLegendaryItemSource(string path){return path=="Prefabs/Effects/ImpactEffects/BootShockwave"||path=="Prefabs/NetworkedObjects/BodyAttachments/VagrantNovaItemBodyAttachment"||worldLegendaryControllers.Any(name=>path=="Prefabs/NetworkedObjects/"+name);}
  public bool PrepareWorldLegendaryItemSource(string path,GameObject source,int index){
   bool effect=path=="Prefabs/Effects/ImpactEffects/BootShockwave";coordinator.Check(effect?(bool)source.GetComponent<EffectComponent>():(bool)source.GetComponent<NetworkIdentity>(),"Original legendary provider identity missing: "+path);
   if(source.name=="IcicleAura"){
    coordinator.Check(source.GetComponent<IcicleAuraController>(),"Original Icicle controller missing");var field=typeof(IcicleBodyBehavior).GetField("icicleAuraPrefab",BindingFlags.NonPublic|BindingFlags.Static);coordinator.Check(field!=null&&field.GetValue(null)==null,"Unowned Icicle provider");coordinator.worldLootEffectSlots.Add(field,null);field.SetValue(null,source);
   }else if(!effect)coordinator.Check(source.GetComponent<NetworkedBodyAttachment>()&&source.GetComponent<EntityStateMachine>(),"Original legendary attachment/state contract missing: "+source.name);
   var attachment=source.GetComponent<NetworkedBodyAttachment>();
   if(attachment&&!source.GetComponent<NetworkIdentity>().localPlayerAuthority&&!attachment.forceHostAuthority){
    // The composed local client owns its player body. Server-only source
    // attachments cannot inherit that ownership through SpawnWithClientAuthority.
    // Use the native host-authority option; retain their original identity flag.
    worldLegendaryHostAuthority.Add(attachment,attachment.forceHostAuthority);attachment.forceHostAuthority=true;
   }
   if(source.name=="LaserTurbineController"||source.name=="VagrantNovaItemBodyAttachment"&&source.GetComponent<RoR2.Networking.CharacterNetworkTransform>()){
    // Its original attachment already follows the owner in this local server/client.
    // Remote snapshot timing requires the unavailable platform network manager.
    var remote=source.GetComponent<RoR2.Networking.CharacterNetworkTransform>();coordinator.Check(remote&&remote.enabled,"Original attachment remote transform contract differs: "+source.name);worldLegendaryRemoteTransforms.Add(remote,remote.enabled);remote.enabled=false;
   }
   coordinator.worldNativeLootLeaseBaselines.Add(index,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(coordinator.objectiveSupportLeases[index]));
   foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){if(coordinator.worldLootSourceMaterials.ContainsKey(renderer))continue;coordinator.worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);coordinator.worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}coordinator.PresentCommerceModel(source.transform);return effect;
  }
  public void ObserveWorldLegendaryItems(bool force=false){
   if(coordinator.r.itemBehaviors==null||(!force&&Time.frameCount%30!=0))return;
   var instances=force?Resources.FindObjectsOfTypeAll<GameObject>():NetworkServer.objects.Values.Where(x=>x).Select(x=>x.gameObject).ToArray();
   foreach(var obj in instances.Where(x=>x&&x.scene.IsValid()&&worldLegendaryControllers.Any(name=>x.name==name+"(Clone)"))){
    LegendaryItemObservation observation;if(!worldLegendaryItemInstances.TryGetValue(obj,out observation)){var identity=obj.GetComponent<NetworkIdentity>();coordinator.Check(identity&&identity.netId.Value!=0&&NetworkServer.FindLocalObject(identity.netId)==obj,"Original legendary local network ownership differs");coordinator.worldObjects.Add(obj);observation=new LegendaryItemObservation{source=obj.name,netId=identity.netId.Value,states=new string[0]};worldLegendaryItemInstances.Add(obj,observation);coordinator.r.itemBehaviors.legendaryInstances.Add(observation);}
    observation.samples++;var network=obj.GetComponent<NetworkIdentity>();var attachment=obj.GetComponent<NetworkedBodyAttachment>();observation.localPlayerAuthority=network.localPlayerAuthority;observation.hasAuthority=network.hasAuthority;observation.forceHostAuthority=attachment&&attachment.forceHostAuthority;observation.states=observation.states.Concat(obj.GetComponents<EntityStateMachine>().Where(x=>x.state!=null).Select(x=>x.state.GetType().FullName)).Distinct().ToArray();coordinator.Check(observation.states.Length<=11,"Unexpected legendary state domain");
    var icicle=obj.GetComponent<IcicleAuraController>();if(icicle)observation.maxIcicles=Mathf.Max(observation.maxIcicles,icicle.NetworkfinalIcicleCount);
    var turbine=obj.GetComponent<LaserTurbineController>();if(turbine){observation.maxCharge=Mathf.Max(observation.maxCharge,turbine.charge);observation.maxVisualSpin=Mathf.Max(observation.maxVisualSpin,turbine.visualSpin);}
   }
  }
  public void Dispose(){ObserveWorldLegendaryItems(true);foreach(var obj in worldLegendaryItemInstances.Keys)if(obj)NetworkServer.Destroy(obj);worldLegendaryItemInstances.Clear();foreach(var pair in worldLegendaryRemoteTransforms)if(pair.Key)pair.Key.enabled=pair.Value;worldLegendaryRemoteTransforms.Clear();foreach(var pair in worldLegendaryHostAuthority)if(pair.Key)pair.Key.forceHostAuthority=pair.Value;worldLegendaryHostAuthority.Clear();}
 }
}
