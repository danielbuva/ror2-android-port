using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Source providers and native callbacks only; no ward, pulse or plant algorithms.
public sealed partial class MovementBatchProbe {
 static readonly string[] worldHealingItemNames={"WarbannerWard","InterstellarDeskPlant","DeskplantWard","TeleporterHealNovaGenerator","TeleporterHealNovaPulse"};
 readonly HashSet<GameObject> worldHealingItemInstances=new HashSet<GameObject>();
 Action<CharacterBody> worldWarbannerLevel;
 bool IsWorldHealingItemSource(string path){return worldHealingItemNames.Any(name=>path=="Prefabs/NetworkedObjects/"+name);}
 void PrepareWorldHealingItemSource(string path,GameObject source){
  Check(path=="Prefabs/NetworkedObjects/"+source.name&&source.GetComponent<NetworkIdentity>()&&source.GetComponent<TeamFilter>(),"Original healing-item source/network/team identity differs");
  if(source.name=="WarbannerWard"){
   Check(source.GetComponent<BuffWard>()&&source.GetComponent<BuffWard>().buffDef==RoR2Content.Buffs.Warbanner,"Original Warbanner buff contract differs");
   var owner=typeof(RoR2.Items.WardOnLevelManager);var field=owner.GetField("wardPrefab",BindingFlags.NonPublic|BindingFlags.Static);Check(field!=null&&field.GetValue(null)==null&&worldWarbannerLevel==null,"Unowned native Warbanner callback/provider");
   worldLootEffectSlots.Add(field,null);field.SetValue(null,source);worldWarbannerLevel=(Action<CharacterBody>)Delegate.CreateDelegate(typeof(Action<CharacterBody>),owner.GetMethod("OnCharacterLevelUp",BindingFlags.NonPublic|BindingFlags.Static));GlobalEventManager.onCharacterLevelUp+=worldWarbannerLevel;
  }else if(source.name=="InterstellarDeskPlant"){
   var plant=source.GetComponent<DeskPlantController>();Check(plant&&plant.plantObject&&plant.seedObject&&source.GetComponent<EntityStateMachine>(),"Original Desk Plant state/presentation contract differs");
  }else if(source.name=="DeskplantWard")Check(source.GetComponent<HealingWard>(),"Original Desk Plant healing ward missing");
  else Check(source.GetComponent<EntityStateMachine>(),"Original teleporter healing state machine missing");
  foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){if(worldLootSourceMaterials.ContainsKey(renderer))continue;worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}
  PresentCommerceModel(source.transform);
 }
 void ObserveWorldHealingItems(bool force=false){
  if(r.procContent==null||(!force&&Time.frameCount%30!=0))return;
  foreach(var obj in Resources.FindObjectsOfTypeAll<GameObject>().Where(x=>x&&x.scene.IsValid()&&worldHealingItemNames.Any(name=>x.name==name+"(Clone)"))){
   if(!worldHealingItemInstances.Add(obj))continue;var identity=obj.GetComponent<NetworkIdentity>();Check(identity&&identity.netId.Value!=0&&NetworkServer.FindLocalObject(identity.netId)==obj,"Original healing-item local network ownership differs");worldObjects.Add(obj);
   switch(obj.name){case "WarbannerWard(Clone)":r.procContent.warbannerWards++;break;case "InterstellarDeskPlant(Clone)":r.procContent.deskPlants++;break;case "DeskplantWard(Clone)":r.procContent.deskplantWards++;break;case "TeleporterHealNovaGenerator(Clone)":r.procContent.healNovaGenerators++;break;case "TeleporterHealNovaPulse(Clone)":r.procContent.healNovaPulses++;break;}
  }
 }
 void CleanupWorldHealingItems(){
  ObserveWorldHealingItems(true);if(worldWarbannerLevel!=null){GlobalEventManager.onCharacterLevelUp-=worldWarbannerLevel;worldWarbannerLevel=null;}
  foreach(var obj in worldHealingItemInstances)if(obj)NetworkServer.Destroy(obj);worldHealingItemInstances.Clear();
 }
}
