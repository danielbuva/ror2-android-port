// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup RegisterLocations; teardown —.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using Path = System.IO.Path;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using RoR2.ContentManagement;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// The original providers and ContentManager own the content phases. This boundary
// changes only asset locations; importing an entitlement never grants it.
public static class WholeCatalogLoader {
 public static string phase;
 public static float progress;
 public static ResourceLocationMap locator;
 public static readonly List<string> failures=new List<string>();
 public static readonly List<string> initializedCatalogs=new List<string>();
 sealed class ProgressSink : IProgress<float>{public void Report(float value){progress=value;}}
 public static IEnumerator Load(JObject manifest,string assetProvider,string bundlePath=null){
  if(ContentManager.allLoadedContentPacks.Length!=0)throw new InvalidOperationException("Whole catalog already registered");
  failures.Clear();phase="addressables-initialize";
  var initialization=Addressables.InitializeAsync();Addressables.ResourceManager.Acquire(initialization);yield return initialization;
  if(initialization.Status!=AsyncOperationStatus.Succeeded)throw new Exception("Whole catalog Addressables initialization failed",initialization.OperationException);
  Addressables.Release(initialization);
  RegisterLocations(manifest,assetProvider,bundlePath);
  phase="original-content-providers";
  ContentManager.CollectContentPackProvidersDelegate collect=add=>{
   foreach(var row in manifest["providers"]){var type=Type.GetType((string)row["type"],true);var provider=(IContentPackProvider)Activator.CreateInstance(type);if(provider.identifier!=(string)row["identifier"])throw new Exception("Original provider identity changed");add(provider);}
  };
  ContentManager.collectContentPackProviders+=collect;
  try{yield return ContentManager.LoadContentPacks(new ProgressSink());}
  finally{ContentManager.collectContentPackProviders-=collect;}
  if(ContentManager.allLoadedContentPacks.Length!=manifest["providers"].Count())throw new Exception("Original provider count mismatch");
  phase="content-manager-assigned";
 }
 public static void RegisterLocations(JObject manifest,string assetProvider,string bundlePath,string borrowedProvider=null,ISet<string> borrowedBundles=null,string borrowedAssetProvider=null){
  if(bundlePath!=null){var providers=Addressables.ResourceManager.ResourceProviders;if(!providers.Any(x=>x is AssetBundleProvider))providers.Add(new AssetBundleProvider());if(!providers.Any(x=>x is BundledAssetProvider))providers.Add(new BundledAssetProvider());}
  // Stock helpers use First(), so an empty initialization locator cannot precede us.
  var dynamicLocators=Addressables.ResourceLocators.Where(prior=>prior.LocatorId=="DynamicResourceLocator").ToArray();
  foreach(var prior in Addressables.ResourceLocators.ToArray())Addressables.RemoveResourceLocator(prior);
  locator=new ResourceLocationMap("original-whole-catalog");
  var locations=new Dictionary<int,IResourceLocation>();var bundles=new Dictionary<string,IResourceLocation>();
  if(bundlePath!=null)foreach(var pair in (JObject)manifest["bundles"]){string provider=borrowedBundles!=null&&borrowedBundles.Contains(pair.Key)?borrowedProvider:typeof(AssetBundleProvider).FullName;if(string.IsNullOrEmpty(provider))throw new Exception("Borrowed bundle provider absent");var dependency=new ResourceLocationBase(pair.Key,Path.Combine(bundlePath,pair.Key),provider,typeof(IAssetBundleResource));dependency.Data=new AssetBundleRequestOptions{BundleName=pair.Key};bundles.Add(pair.Key,dependency);}
  foreach(var row in manifest["locations"]){
   var type=Type.GetType((string)row["type"],false);if(type==null)throw new Exception("Original resource type unavailable: "+row["type"]);
   IResourceLocation[] dependencies=new IResourceLocation[0];string provider=assetProvider;
   if(bundlePath!=null){string owner=(string)row["bundle"];dependencies=new[]{bundles[owner]}.Concat(manifest["bundles"][owner]["dependencies"].Select(x=>bundles[(string)x])).ToArray();if(borrowedBundles!=null&&borrowedBundles.Contains(owner))provider=borrowedAssetProvider;if(type==typeof(SceneInstance))provider=typeof(SceneProvider).FullName;if(string.IsNullOrEmpty(provider))throw new Exception("Borrowed asset provider absent");}
   locations.Add((int)row["id"],new ResourceLocationBase((string)row["primaryKey"],(string)row["path"],provider,type,dependencies));
  }
  foreach(var key in manifest["keys"]){
   // Non-string keys require their original decoder; never silently stringify them.
   if(key["keyType"]!=null&&(string)key["keyType"]!="System.String")continue;
   var found=key["locations"].Select(x=>(int)x).Where(locations.ContainsKey).Select(x=>locations[x]).ToList();
   if(found.Count!=0)locator.Add((string)key["key"],found);
  }
  Addressables.AddResourceLocator(locator);
  // The original locator resolves GUID[subobject] through the typed main location.
  foreach(var dynamicLocator in dynamicLocators)Addressables.AddResourceLocator(dynamicLocator);
  if(!ReferenceEquals(Addressables.ResourceLocators.First(),locator))throw new Exception("Whole catalog locator order lost");
 }
 // Share the already measured catalog-only path between host and Android.
 // Platform/profile/audio startup is deliberately outside this owned sequence.
 public static IEnumerator InitializeCatalogs(){
  if(initializedCatalogs.Count!=0)throw new InvalidOperationException("Native catalogs already initialized by this owner");
  foreach(string name in new[]{"ItemTierCatalog","ItemCatalog","EquipmentCatalog","BuffCatalog","EliteCatalog","EntityStateCatalog","BodyCatalog","MasterCatalog","ProjectileCatalog","EffectCatalog","SkillCatalog","SurvivorCatalog","SceneCatalog"}){
   phase="catalog:"+name;
   var type=typeof(RoR2Application).Assembly.GetTypes().Single(x=>x.Name==name);
   var method=type.GetMethod("Init",BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic,null,Type.EmptyTypes,null);
   if(method==null)throw new Exception("Original catalog initializer absent: "+name);
   object value;try{value=method.Invoke(null,null);}catch(TargetInvocationException e){throw new Exception("Original catalog initializer failed: "+name,e.InnerException??e);}
   var routine=value as IEnumerator;if(routine!=null)yield return routine;
   if(failures.Count!=0)throw new Exception("Original catalog initializer reported failure: "+name);
   initializedCatalogs.Add(name);yield return null;
  }
  phase="whole-catalogs-ready";
 }
 static Dictionary<string,int?> AdditionalCounts(){
  var result=new Dictionary<string,int?>();
  foreach(string name in new[]{"craftableDefs","keyItemDefs","itemGroupProviders","itemGroupTypes","cursedBookSpellDefs"}){
   var field=typeof(ContentManager).GetField("_"+name,System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic);
   var values=field==null?null:field.GetValue(null) as Array;result.Add(name,values==null?(int?)null:values.Length);
  }
  return result;
 }
 public static object Counts(){return new{packs=ContentManager.allLoadedContentPacks.Length,bodies=(ContentManager.bodyPrefabs?.Length??0),masters=(ContentManager.masterPrefabs?.Length??0),items=(ContentManager.itemDefs?.Length??0),equipment=(ContentManager.equipmentDefs?.Length??0),buffs=(ContentManager.buffDefs?.Length??0),elites=(ContentManager.eliteDefs?.Length??0),projectiles=(ContentManager.projectilePrefabs?.Length??0),effects=(ContentManager.effectDefs?.Length??0),scenes=(ContentManager.sceneDefs?.Length??0),states=(ContentManager.entityStateConfigurations?.Length??0),skills=(ContentManager.skillDefs?.Length??0),droneDefs=(ContentManager.droneDefs?.Length??0),additionalCategories=AdditionalCounts(),initializedCatalogs,nativeEffects=initializedCatalogs.Contains("EffectCatalog")?(int?)EffectCatalog.effectCount:null,scope="Original catalog observations; no ownership, unlock, gameplay or appearance acceptance"};}
}
