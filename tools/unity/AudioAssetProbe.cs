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

// Asset-only audio boundary: never instantiate either returned prefab.
public static class AudioAssetProbe {
 [Serializable] public class Config {public string[] paths,keys,assets,names;}
 static void Require(bool value,string error){if(!value)throw new Exception(error);}
 public static IEnumerator Run(Action<string> observe){
 var cfg=JsonUtility.FromJson<Config>(Resources.Load<TextAsset>("AudioAssetProbe").text);
  var directory=Path.Combine(Application.persistentDataPath,"audio-catalog");Directory.CreateDirectory(directory);
  var catalogPath=Path.Combine(directory,"catalog.json");var settingsPath=Path.Combine(directory,"settings.json");
  // Valid zero-entry serialized catalog; the typed local mapping is registered after real initialization.
  File.WriteAllText(catalogPath,"{\"m_LocatorId\":\"controller-init\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
  var data=new ResourceManagerRuntimeData{BuildTarget="Android",DisableCatalogUpdateOnStartup=true,LogResourceManagerExceptions=true};
  data.CatalogLocations.Add(new ResourceLocationData(new[]{ResourceManagerRuntimeData.kCatalogAddress},catalogPath,typeof(ContentCatalogProvider),typeof(ContentCatalogData)));
  File.WriteAllText(settingsPath,JsonUtility.ToJson(data));
  string defaultSettings=Addressables.RuntimePath+"/settings.json";
  Addressables.InternalIdTransformFunc=location=>location.InternalId==defaultSettings?settingsPath:location.InternalId;
  var init=Addressables.InitializeAsync();Addressables.ResourceManager.Acquire(init);while(!init.IsDone)yield return null;
  Require(init.Status==AsyncOperationStatus.Succeeded,"Addressables initialization failed: "+init.OperationException);Addressables.Release(init);
  Addressables.ResourceManager.ResourceProviders.Add(new AssetBundleProvider());Addressables.ResourceManager.ResourceProviders.Add(new BundledAssetProvider());
  var bundleLocation=new ResourceLocationBase("controller-android-bundle",Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));
  bundleLocation.Data=new AssetBundleRequestOptions{BundleName="commando-prefab-lab"};

 var locator=new ResourceLocationMap("audio-local");
 for(int i=0;i<2;i++)locator.Add(cfg.keys[i],new ResourceLocationBase(cfg.keys[i],cfg.assets[i],typeof(BundledAssetProvider).FullName,typeof(GameObject),bundleLocation));
 Addressables.AddResourceLocator(locator);
 int baseline=RoR2.LegacyResourcesAPI.ActiveCount;
 Require(UnityEngine.Object.FindObjectOfType<AkInitializer>()==null,"Unexpected active audio initializer");
 for(int i=0;i<2;i++){
  Require(RoR2.LegacyResourcesAPI.GetPathGuidString(cfg.paths[i])==cfg.keys[i],"Legacy audio mapping mismatch");
  var handle=RoR2.LegacyResourcesAPI.LoadAsync<GameObject>(cfg.paths[i]);
  try{
   while(!handle.IsDone)yield return null;yield return null;
   Require(handle.Status==AsyncOperationStatus.Succeeded&&handle.Result,"Audio asset load failed: "+handle.OperationException);
   var asset=handle.Result;Require(asset.name==cfg.names[i]&&!asset.scene.IsValid(),"Audio result is not expected prefab asset");
   var components=asset.GetComponents<MonoBehaviour>();Require(components.All(x=>x),"Missing audio prefab script");
   Require(components.Length==(i==0?10:4),"Audio component count mismatch");
   Require(RoR2.LegacyResourcesAPI.ActiveCount==baseline,"Legacy pending count did not balance");
   observe(asset.name+":"+components.Length+":Succeeded");
  }finally{if(handle.IsValid())Addressables.Release(handle);}
  Require(!handle.IsValid(),"Audio handle remains valid after release");
 }
 Require(UnityEngine.Object.FindObjectOfType<AkInitializer>()==null,"Audio initializer activated unexpectedly");
 Addressables.RemoveResourceLocator(locator);
 }
}
