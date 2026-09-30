using System;
using System.Collections;
using System.Collections.Generic;
using Path = System.IO.Path;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// A single measured legacy Material location. The prefab bundle keeps its existing owner.
public sealed partial class MovementBatchProbe {
 const string TeleportBundle="teleport-material-lab";
 ResourceLocationMap teleportLocator;
 AsyncOperationHandle<Material> teleportHandle;
 Material teleportMaterial;
 readonly List<TemporaryOverlayInstance> ownedTeleportOverlays=new List<TemporaryOverlayInstance>();
 readonly HashSet<TemporaryOverlayInstance> observedTeleportOverlays=new HashSet<TemporaryOverlayInstance>();
 int TeleportOverlayCount(){return (int)typeof(TemporaryOverlayManager).GetField("arraySize",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);}
 IEnumerator PrepareTeleportMaterial(Result cfg){
  Check(!AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==TeleportBundle),"Teleport bundle already has an owner");
  Check(TeleportOverlayCount()==0,"Existing overlays; refuse ownership");
  string key;Check(LegacyResourcesAPI.GetGuid("Materials/matTPInOut",out key)&&key==cfg.teleportMaterialKey,"Actual legacy material GUID");
  var providers=Addressables.ResourceManager.ResourceProviders;
  if(!providers.Any(p=>p is AssetBundleProvider))providers.Add(new AssetBundleProvider());
  if(!providers.Any(p=>p is BundledAssetProvider))providers.Add(new BundledAssetProvider());
  var bundle=new ResourceLocationBase(TeleportBundle,Path.Combine(Application.persistentDataPath,"payload",TeleportBundle),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));
  bundle.Data=new AssetBundleRequestOptions{BundleName=TeleportBundle};
  var location=new ResourceLocationBase(key,cfg.teleportMaterialAsset,typeof(BundledAssetProvider).FullName,typeof(Material),bundle);
  teleportLocator=new ResourceLocationMap("teleport-material-probe");teleportLocator.Add(key,location);Addressables.AddResourceLocator(teleportLocator);
  if(r.id!="body-state-spawn-state-material")yield break;
  r.phase="original-teleport-material-cold-sync";Save();teleportMaterial=LegacyResourcesAPI.Load<Material>("Materials/matTPInOut");
  if(teleportMaterial)r.teleportSyncLoads++;
  AcceptTeleportMaterial(teleportMaterial,cfg);
  r.phase="original-teleport-material-async";Save();teleportHandle=LegacyResourcesAPI.LoadAsync<Material>("Materials/matTPInOut");
  var deadline=Time.realtimeSinceStartup+5;while(!teleportHandle.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;yield return null;
  Check(teleportHandle.IsDone&&teleportHandle.Status==AsyncOperationStatus.Succeeded&&teleportHandle.Result==teleportMaterial,"Original async/sync material identity");
  Check(LegacyResourcesAPI.ActiveCount==0,"Legacy material callbacks not drained");
 }
 void AcceptTeleportMaterial(Material material,Result cfg){
  Check(material&&material.name=="matTPInOut"&&material.shader,"Actual typed teleport material missing");
  Check(AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==TeleportBundle&&b.GetAllAssetNames().Contains(cfg.teleportMaterialAsset)),"Provider did not load the separately owned material bundle");
  r.teleportMaterialLoaded=true;r.teleportMaterialName=material.name;r.teleportShader=material.shader.name;
 }
 void ObserveTeleportOverlays(CharacterBody body){
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  var model=body.modelLocator.modelTransform.GetComponent<CharacterModel>();
  foreach(var overlay in model.temporaryOverlays){
   if(!observedTeleportOverlays.Add(overlay))continue;
   ownedTeleportOverlays.Add(overlay);
   if(overlay.originalMaterial){teleportMaterial=overlay.originalMaterial;r.teleportSyncLoads++;}
   AcceptTeleportMaterial(overlay.originalMaterial,cfg);r.teleportOverlays++;
   Check(overlay.initialized&&overlay.assignedCharacterModel==model&&overlay.materialInstance&&overlay.materialInstance!=overlay.originalMaterial&&overlay.materialInstance.shader==overlay.originalMaterial.shader,"Original overlay material copy/assignment");
  }
 }
 void ProbeTeleportOverlay(CharacterBody body,Result cfg){
  var model=body.modelLocator.modelTransform.GetComponent<CharacterModel>();Check(model&&model.temporaryOverlays.Count==0,"Recovered model overlay baseline");
  r.phase="original-teleport-overlay-setup";Save();TeleportOutController.AddTPOutEffect(model,1f,0f,cfg.sourceSpawnDelay);ObserveTeleportOverlays(body);
  Check(r.teleportOverlays==1&&TeleportOverlayCount()==1,"Original overlay registration");var overlay=ownedTeleportOverlays.Single();
  Check(overlay.animateShaderAlpha&&overlay.destroyComponentOnEnd&&overlay.duration==cfg.sourceSpawnDelay&&overlay.alphaCurve.Evaluate(0)==1&&overlay.alphaCurve.Evaluate(1)==0,"Original overlay configuration");
  TemporaryOverlayManager.OverlayUpdate();Check(overlay.stopwatch>0&&Mathf.Abs(overlay.materialInstance.GetFloat("_ExternalAlpha")-overlay.alphaCurve.Evaluate(overlay.stopwatch/overlay.duration))<.0001f,"Original diagnostic overlay update");
  r.phase="original-teleport-overlay-remove";Save();TemporaryOverlayManager.RemoveOverlay(overlay.managerIndex);
  Check(TeleportOverlayCount()==0&&model.temporaryOverlays.Count==0&&overlay.managerIndex==-1&&overlay.assignedCharacterModel==null,"Original overlay removal");r.teleportOverlayRemoved=true;
 }
 IEnumerator CleanupTeleportMaterial(){
  if(teleportLocator==null)yield break;
  var copies=ownedTeleportOverlays.Select(x=>x.materialInstance).ToArray();
  foreach(var overlay in ownedTeleportOverlays)if(overlay.managerIndex>=0)TemporaryOverlayManager.RemoveOverlay(overlay.managerIndex);
  Check(TeleportOverlayCount()==0,"Owned overlay cleanup incomplete");yield return null;
  Check(copies.All(x=>!x),"Overlay material copies survived destruction");
  var deadline=Time.realtimeSinceStartup+3;while(LegacyResourcesAPI.ActiveCount!=0&&Time.realtimeSinceStartup<deadline)yield return null;
  Check(LegacyResourcesAPI.ActiveCount==0,"Refuse material release with pending callbacks");
  for(int i=0;i<r.teleportSyncLoads;i++)Addressables.Release(teleportMaterial);
  if(teleportHandle.IsValid())Addressables.Release(teleportHandle);
  yield return null;
  Check(!teleportHandle.IsValid()&&!AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==TeleportBundle),"Original material release retained its bundle");
  Addressables.RemoveResourceLocator(teleportLocator);teleportLocator=null;r.teleportBundleReleased=true;
 }
}
