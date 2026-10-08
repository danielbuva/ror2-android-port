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
 [Serializable] public class LegendaryItemObservation {public string source;public uint netId;public string[] states;public int samples,maxIcicles;public float maxCharge,maxVisualSpin;}
 readonly Dictionary<GameObject,LegendaryItemObservation> worldLegendaryItemInstances=new Dictionary<GameObject,LegendaryItemObservation>();
 readonly Dictionary<Behaviour,bool> worldLegendaryRemoteTransforms=new Dictionary<Behaviour,bool>();
 static readonly string[] worldLegendaryControllers={"HeadstompersController","IcicleAura","LaserTurbineController"};
 bool IsWorldLegendaryItemSource(string path){return path=="Prefabs/Effects/ImpactEffects/BootShockwave"||worldLegendaryControllers.Any(name=>path=="Prefabs/NetworkedObjects/"+name);}
 bool PrepareWorldLegendaryItemSource(string path,GameObject source,int index){
  bool effect=path=="Prefabs/Effects/ImpactEffects/BootShockwave";Check(effect?(bool)source.GetComponent<EffectComponent>():(bool)source.GetComponent<NetworkIdentity>(),"Original legendary provider identity missing: "+path);
  if(source.name=="IcicleAura"){
   Check(source.GetComponent<IcicleAuraController>(),"Original Icicle controller missing");var field=typeof(IcicleBodyBehavior).GetField("icicleAuraPrefab",BindingFlags.NonPublic|BindingFlags.Static);Check(field!=null&&field.GetValue(null)==null,"Unowned Icicle provider");worldLootEffectSlots.Add(field,null);field.SetValue(null,source);
  }else if(!effect)Check(source.GetComponent<NetworkedBodyAttachment>()&&source.GetComponent<EntityStateMachine>(),"Original legendary attachment/state contract missing: "+source.name);
  if(source.name=="LaserTurbineController"){
   // Its original attachment already follows the owner in this local server/client.
   // Remote snapshot timing requires the unavailable platform network manager.
   var remote=source.GetComponent<RoR2.Networking.CharacterNetworkTransform>();Check(remote&&remote.enabled,"Original LaserTurbine remote transform contract differs");worldLegendaryRemoteTransforms.Add(remote,remote.enabled);remote.enabled=false;
  }
  worldNativeLootLeaseBaselines.Add(index,(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[index]));
  foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}PresentCommerceModel(source.transform);return effect;
 }
 void ObserveWorldLegendaryItems(bool force=false){
  if(r.itemBehaviors==null||(!force&&Time.frameCount%30!=0))return;
  foreach(var obj in Resources.FindObjectsOfTypeAll<GameObject>().Where(x=>x&&x.scene.IsValid()&&worldLegendaryControllers.Any(name=>x.name==name+"(Clone)"))){
   LegendaryItemObservation observation;if(!worldLegendaryItemInstances.TryGetValue(obj,out observation)){var identity=obj.GetComponent<NetworkIdentity>();Check(identity&&identity.netId.Value!=0&&NetworkServer.FindLocalObject(identity.netId)==obj,"Original legendary local network ownership differs");worldObjects.Add(obj);observation=new LegendaryItemObservation{source=obj.name,netId=identity.netId.Value,states=new string[0]};worldLegendaryItemInstances.Add(obj,observation);r.itemBehaviors.legendaryInstances.Add(observation);}
   observation.samples++;observation.states=observation.states.Concat(obj.GetComponents<EntityStateMachine>().Where(x=>x.state!=null).Select(x=>x.state.GetType().FullName)).Distinct().ToArray();Check(observation.states.Length<=11,"Unexpected legendary state domain");
   var icicle=obj.GetComponent<IcicleAuraController>();if(icicle)observation.maxIcicles=Mathf.Max(observation.maxIcicles,icicle.NetworkfinalIcicleCount);
   var turbine=obj.GetComponent<LaserTurbineController>();if(turbine){observation.maxCharge=Mathf.Max(observation.maxCharge,turbine.charge);observation.maxVisualSpin=Mathf.Max(observation.maxVisualSpin,turbine.visualSpin);}
  }
 }
 void CleanupWorldLegendaryItems(){ObserveWorldLegendaryItems(true);foreach(var obj in worldLegendaryItemInstances.Keys)if(obj)NetworkServer.Destroy(obj);worldLegendaryItemInstances.Clear();foreach(var pair in worldLegendaryRemoteTransforms)if(pair.Key)pair.Key.enabled=pair.Value;worldLegendaryRemoteTransforms.Clear();}
}
