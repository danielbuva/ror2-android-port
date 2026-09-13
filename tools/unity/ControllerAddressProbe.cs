using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using RoR2.ContentManagement;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// A single original deferred request. No original application or body is activated.
public class ControllerAddressProbe : MonoBehaviour {
 [Serializable] public class Config {public string attempt,key,asset,bundle;}
 [Serializable] public class Report {public string attempt,phase,error,key,asset,bundlePath,provider;public int pid,clips,callbacks;public bool success,initialized,shared,retained,released,reloaded,missingFailed,wrongTypeFailed,startupInactive;public string scheduler="Diagnostic calls to original manager Update; not game-loop acceptance";}
 Config cfg;Report report;MethodInfo tick;
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("ControllerAddressProbe"))new GameObject("Original controller request probe").AddComponent<ControllerAddressProbe>();}
 IEnumerator Start(){
  cfg=JsonUtility.FromJson<Config>(Resources.Load<TextAsset>("ControllerAddressProbe").text);report=new Report{attempt=cfg.attempt,key=cfg.key,asset=cfg.asset};
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))report.pid=process.CallStatic<int>("myPid");
#endif
  yield return new WaitForSeconds(6);
  report.bundlePath=Path.Combine(Application.persistentDataPath,"payload",cfg.bundle);
  if(!File.Exists(report.bundlePath))yield break; // first launch precedes owned payload synchronization
  var routine=Run();
  while(true){bool more;object current=null;try{more=routine.MoveNext();if(more)current=routine.Current;}catch(Exception e){report.error=e.ToString();report.success=false;Save();yield break;}if(!more)break;yield return current;}
 }
 void Phase(string value){report.phase=value;Save();}
 static void Require(bool value,string error){if(!value)throw new Exception(error);}
 void Save(){File.WriteAllText(Path.Combine(Application.persistentDataPath,"controller-address-probe.json"),JsonUtility.ToJson(report,true));}
 AssetOrDirectReference<RuntimeAnimatorController> Wrapper(){var w=new AssetOrDirectReference<RuntimeAnimatorController>{loadOnAssigned=false,unloadType=AsyncReferenceHandleUnloadType.AtWill};w.address=new AssetReferenceT<RuntimeAnimatorController>(cfg.key);w.onValidReferenceDiscovered+=x=>report.callbacks++;return w;}
 IEnumerator Run(){
  Phase("initialize");
  Require(!AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==cfg.bundle),"Bundle already owned by another loader");
  var directory=Path.Combine(Application.persistentDataPath,"controller-catalog");Directory.CreateDirectory(directory);
  var catalogPath=Path.Combine(directory,"catalog.json");var settingsPath=Path.Combine(directory,"settings.json");
  // Valid zero-entry serialized catalog; the typed local mapping is registered after real initialization.
  File.WriteAllText(catalogPath,"{\"m_LocatorId\":\"controller-init\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
  var data=new ResourceManagerRuntimeData{BuildTarget="Android",DisableCatalogUpdateOnStartup=true,LogResourceManagerExceptions=true};
  data.CatalogLocations.Add(new ResourceLocationData(new[]{ResourceManagerRuntimeData.kCatalogAddress},catalogPath,typeof(ContentCatalogProvider),typeof(ContentCatalogData)));
  File.WriteAllText(settingsPath,JsonUtility.ToJson(data));
  string defaultSettings=Addressables.RuntimePath+"/settings.json";
  Addressables.InternalIdTransformFunc=location=>location.InternalId==defaultSettings?settingsPath:location.InternalId;
  var init=Addressables.InitializeAsync();Addressables.ResourceManager.Acquire(init);while(!init.IsDone)yield return null;
  Require(init.Status==AsyncOperationStatus.Succeeded,"Addressables initialization failed: "+init.OperationException);report.initialized=true;Addressables.Release(init);
  Addressables.ResourceManager.ResourceProviders.Add(new AssetBundleProvider());Addressables.ResourceManager.ResourceProviders.Add(new BundledAssetProvider());
  var bundleLocation=new ResourceLocationBase("controller-android-bundle",report.bundlePath,typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));
  bundleLocation.Data=new AssetBundleRequestOptions{BundleName=cfg.bundle};
  var location=new ResourceLocationBase(cfg.key,cfg.asset,typeof(BundledAssetProvider).FullName,typeof(RuntimeAnimatorController),bundleLocation);
  var locator=new ResourceLocationMap("controller-local");locator.Add(cfg.key,location);Addressables.AddResourceLocator(locator);report.provider=location.ProviderId;
  Phase("original-load");var first=Wrapper();var second=Wrapper();first.LoadAsync();second.LoadAsync();var handle=first.loadHandle;
  while(!handle.IsDone)yield return null;yield return null;
  Require(handle.Status==AsyncOperationStatus.Succeeded&&first.Result,"Original controller request failed: "+handle.OperationException);
  report.clips=first.Result.animationClips.Length;Require(report.clips==35&&first.Result.animationClips.Any(c=>c.name=="CommandoArmature|RunForward"),"Wrong recovered controller");
  report.shared=handle.Equals(second.loadHandle)&&first.Result==second.Result;Require(report.shared,"Original manager did not share handle");
  first.Reset();report.retained=second.loadHandle.IsValid()&&second.Result;Require(report.retained,"First reset invalidated other owner");
  Phase("delayed-release");second.Reset();
  tick=typeof(AssetAsyncReferenceManager<RuntimeAnimatorController>).GetMethod("Update",BindingFlags.Static|BindingFlags.NonPublic);Require(tick!=null,"Missing original cleanup method");
  float deadline=Time.time+12;while(Time.time<deadline){tick.Invoke(null,null);yield return null;}
  report.released=!handle.IsValid()&&!AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==cfg.bundle);Require(report.released,"Original deferred release did not release handle/bundle");
  Phase("reload");var third=Wrapper();third.LoadAsync();while(!third.loadHandle.IsDone)yield return null;
  report.reloaded=third.loadHandle.Status==AsyncOperationStatus.Succeeded&&third.Result&&third.Result.animationClips.Length==35;Require(report.reloaded,"Reload failed");
  Phase("negative-controls");var missing=Addressables.LoadAssetAsync<RuntimeAnimatorController>("lab-missing-controller");while(!missing.IsDone)yield return null;
  report.missingFailed=missing.Status==AsyncOperationStatus.Failed&&!missing.Result;Addressables.Release(missing);
  var wrong=Addressables.LoadAssetAsync<Texture2D>(cfg.key);while(!wrong.IsDone)yield return null;
  report.wrongTypeFailed=wrong.Status==AsyncOperationStatus.Failed&&!wrong.Result;Addressables.Release(wrong);
  Require(report.missingFailed&&report.wrongTypeFailed,"Invalid request unexpectedly succeeded");
  third.Reset();deadline=Time.time+12;while(Time.time<deadline){tick.Invoke(null,null);yield return null;}
  Require(!AssetBundle.GetAllLoadedAssetBundles().Any(b=>b.name==cfg.bundle),"Reload bundle still retained");
  Addressables.RemoveResourceLocator(locator);
  report.startupInactive=RoR2.RoR2Application.instance==null&&RoR2.RoR2Application.fileSystem==null&&RoR2.RoR2Application.cloudStorage==null;
  Require(report.startupInactive,"Unexpected original startup/filesystem initialization");Require(report.callbacks>=3,"Completion callbacks missing");
  report.success=true;Phase("complete");Debug.Log("LAB_CONTROLLER_ADDRESS_PASS");
 }
}
