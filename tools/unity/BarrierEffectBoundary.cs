using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// One measured original prefab location; original initialization owns its completion callback.
public sealed partial class MovementBatchProbe {
 const string BarrierBundle="barrier-effect-lab",BarrierPath="Prefabs/TemporaryVisualEffects/BarrierEffect";
 ResourceLocationMap barrierLocator;
 AsyncOperationHandle<GameObject> barrierHandle;
 GameObject barrierPrefab;
 readonly Dictionary<FieldInfo,GameObject> priorEffectSlots=new Dictionary<FieldInfo,GameObject>();
 readonly List<Material> ownedBarrierMaterials=new List<Material>();
 readonly List<TemporaryVisualEffect> ownedBarrierEffects=new List<TemporaryVisualEffect>();
 FieldInfo BarrierSlot(){return typeof(CharacterBody).GetNestedType("AssetReferences",BindingFlags.NonPublic).GetField("barrierTempEffectPrefab",BindingFlags.Public|BindingFlags.Static);}
 TemporaryVisualEffect BodyBarrier(CharacterBody body){return (TemporaryVisualEffect)typeof(CharacterBody).GetField("barrierTempEffectInstance",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(body);}
 IEnumerator PrepareBarrierEffect(Result cfg){
  Check(!AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==BarrierBundle),"Barrier bundle already owned");
  string key;Check(LegacyResourcesAPI.GetGuid(BarrierPath,out key)&&key==cfg.barrierEffectKey,"Actual legacy barrier GUID");
  var providers=Addressables.ResourceManager.ResourceProviders;
  if(!providers.Any(p=>p is AssetBundleProvider))providers.Add(new AssetBundleProvider());
  if(!providers.Any(p=>p is BundledAssetProvider))providers.Add(new BundledAssetProvider());
  var bundle=new ResourceLocationBase(BarrierBundle,System.IO.Path.Combine(Application.persistentDataPath,"payload",BarrierBundle),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));
  bundle.Data=new AssetBundleRequestOptions{BundleName=BarrierBundle};
  var location=new ResourceLocationBase(key,cfg.barrierEffectAsset,typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle);
  barrierLocator=new ResourceLocationMap("barrier-effect-probe");barrierLocator.Add(key,location);Addressables.AddResourceLocator(barrierLocator);
  r.phase="original-barrier-cold-sync";Save();barrierPrefab=LegacyResourcesAPI.Load<GameObject>(BarrierPath);if(barrierPrefab)r.barrierSyncLoads++;
  Check(barrierPrefab&&barrierPrefab.name=="BarrierEffect"&&barrierPrefab.GetComponentsInChildren<Component>(true).All(x=>x),"Original barrier prefab/component identity");
  var effect=barrierPrefab.GetComponent<TemporaryVisualEffect>();
  Check(effect&&effect.visualTransform&&effect.enterComponents.Length>0&&effect.exitComponents.Length>0&&effect.enterComponents.All(x=>x)&&effect.exitComponents.All(x=>x),"Original barrier serialized effect references");
  Check(AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==BarrierBundle&&b.GetAllAssetNames().Contains(cfg.barrierEffectAsset)),"Barrier provider bundle identity");r.barrierPrefabLoaded=true;
  barrierHandle=LegacyResourcesAPI.LoadAsync<GameObject>(BarrierPath);
  float deadline=Time.realtimeSinceStartup+5;while(!barrierHandle.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;yield return null;
  Check(barrierHandle.IsDone&&barrierHandle.Status==AsyncOperationStatus.Succeeded&&barrierHandle.Result==barrierPrefab&&LegacyResourcesAPI.ActiveCount==0,"Original async barrier identity/callback balance");
  if(r.id=="body-state-spawn-state-barrier-asset")yield break;
  foreach(var slot in BarrierSlot().DeclaringType.GetFields(BindingFlags.Public|BindingFlags.Static).Where(x=>x.FieldType==typeof(GameObject))){var value=(GameObject)slot.GetValue(null);Check(!value,"Existing effect slot; refuse initialization ownership");priorEffectSlots.Add(slot,value);}
  if(r.id!="body-state-spawn-state-barrier-init"){
   r.phase="original-barrier-completion-callback";Save();
   var type=typeof(CharacterBody).Assembly.GetType(cfg.barrierCompletionType,true);
   Check(type.DeclaringType==BarrierSlot().DeclaringType,"Callback ownership differs from measured resolver");
   var method=type.GetMethod(cfg.barrierCompletionMethod,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance);
   Check(method!=null&&method.GetParameters().Length==1&&method.GetParameters()[0].ParameterType==typeof(AsyncOperationHandle<GameObject>),"Original callback signature differs");
   var owner=type.GetField("<>9",BindingFlags.Public|BindingFlags.Static).GetValue(null);Check(owner!=null,"Original compiler callback owner missing");
   method.Invoke(owner,new object[]{barrierHandle});r.barrierCompletionCalls++;
   Check((GameObject)BarrierSlot().GetValue(null)==barrierPrefab&&priorEffectSlots.Keys.Count(x=>(GameObject)x.GetValue(null))==1,"Original successful callback slot identity");
   r.barrierCompletionSucceeded=true;Save();yield break;
  }
  r.phase="original-character-body-init";Save();CharacterBody.Init();r.barrierInitCalls++;
  deadline=Time.realtimeSinceStartup+10;while(LegacyResourcesAPI.ActiveCount!=0&&Time.realtimeSinceStartup<deadline)yield return null;yield return null;
  Check(LegacyResourcesAPI.ActiveCount==0&&(GameObject)BarrierSlot().GetValue(null)==barrierPrefab,"Original Init barrier completion");
  Check(priorEffectSlots.Keys.Count(x=>(GameObject)x.GetValue(null))==1,"Unexpected successful effect requests");r.barrierInitCompleted=true;Save();
 }
 void ObserveBarrierEffect(CharacterBody body){
  var effect=BodyBarrier(body);
  if(effect&&!ownedBarrierEffects.Contains(effect)){ownedBarrierEffects.Add(effect);r.barrierEffectEntries++;Check(effect.parentTransform==body.coreTransform&&effect.healthComponent==body.healthComponent&&effect.visualState==TemporaryVisualEffect.VisualState.Enter,"Original effect linkage/entry");}
  var sourceMaterials=barrierPrefab.GetComponentsInChildren<Renderer>(true).SelectMany(x=>x.sharedMaterials).ToArray();
  foreach(var owned in ownedBarrierEffects)if(owned){
   foreach(var material in owned.GetComponentsInChildren<Renderer>(true).SelectMany(x=>x.sharedMaterials))if(material&&!sourceMaterials.Contains(material)&&!ownedBarrierMaterials.Contains(material))ownedBarrierMaterials.Add(material);
   r.barrierMaterialCopies=ownedBarrierMaterials.Count;
   if(owned.visualState==TemporaryVisualEffect.VisualState.Exit)r.barrierEffectExited=true;}else r.barrierEffectDestroyed=true;
 }
 IEnumerator ProbeBarrierEffectLifecycle(CharacterBody body){
  Check(!body.gameObject.activeInHierarchy&&body.healthComponent.alive&&body.healthComponent.barrier==0&&(r.barrierInitCompleted||r.barrierCompletionSucceeded),"Inactive barrier lifecycle baseline");
  body.healthComponent.AddBarrier(20);body.UpdateAllTemporaryVisualEffects();ObserveBarrierEffect(body);
  yield return new WaitForSeconds(.5f);ObserveBarrierEffect(body);var effect=BodyBarrier(body);
  Check(effect&&effect.enterComponents.All(x=>x.enabled)&&effect.exitComponents.All(x=>!x.enabled),"Original automatic effect Enter components");
  Check(Vector3.Distance(effect.transform.position,body.coreTransform.position)<.001f&&Vector3.Distance(effect.visualTransform.localScale,Vector3.one*effect.radius)<.001f,"Original automatic effect follow/scale");
  body.healthComponent.AddBarrier(-20);body.UpdateAllTemporaryVisualEffects();ObserveBarrierEffect(body);
  Check(BodyBarrier(body)==effect&&effect.visualState==TemporaryVisualEffect.VisualState.Exit,"Original effect exit retains reference until destruction");
  float deadline=Time.realtimeSinceStartup+3;while(effect&&Time.realtimeSinceStartup<deadline){ObserveBarrierEffect(body);yield return null;}ObserveBarrierEffect(body);
  Check(r.barrierMaterialCopies>0,"Original shader-alpha callback material instances not observed");
  Check(!effect&&!BodyBarrier(body)&&r.barrierEffectEntries==1&&r.barrierEffectExited&&r.barrierEffectDestroyed,"Original automatic effect timed destruction");
 }
 IEnumerator CleanupBarrierEffect(){
  if(barrierLocator==null)yield break;
  foreach(var effect in ownedBarrierEffects)if(effect)Destroy(effect.gameObject);yield return null;
  Check(ownedBarrierEffects.All(x=>!x),"Owned barrier effects survived cleanup");
  r.barrierMaterialCopiesAliveAfterEffect=ownedBarrierMaterials.Count(x=>x);
  foreach(var material in ownedBarrierMaterials)if(material)Destroy(material);yield return null;
  Check(ownedBarrierMaterials.All(x=>!x),"Owned shader-alpha material copies survived cleanup");r.barrierMaterialCopiesReleased=true;
  float deadline=Time.realtimeSinceStartup+3;while(LegacyResourcesAPI.ActiveCount!=0&&Time.realtimeSinceStartup<deadline)yield return null;
  Check(LegacyResourcesAPI.ActiveCount==0,"Refuse barrier release with pending callbacks");
  foreach(var slot in priorEffectSlots)slot.Key.SetValue(null,slot.Value);
  for(int i=0;i<r.barrierSyncLoads+(r.barrierInitCompleted?1:0);i++)Addressables.Release(barrierPrefab);
  if(barrierHandle.IsValid())Addressables.Release(barrierHandle);yield return null;
  Check(!barrierHandle.IsValid()&&!AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==BarrierBundle),"Barrier references retained bundle");
  Addressables.RemoveResourceLocator(barrierLocator);barrierLocator=null;r.barrierBundleReleased=true;
 }
}
