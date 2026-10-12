using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using Path = System.IO.Path;
using System.Linq;
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
 sealed class ProgressSink : IProgress<float>{public void Report(float value){progress=value;}}
 public static IEnumerator Load(JObject manifest,string assetProvider,string bundlePath=null){
  if(ContentManager.allLoadedContentPacks.Length!=0)throw new InvalidOperationException("Whole catalog already registered");
  failures.Clear();phase="addressables-initialize";
  var initialization=Addressables.InitializeAsync();Addressables.ResourceManager.Acquire(initialization);yield return initialization;
  if(initialization.Status!=AsyncOperationStatus.Succeeded)throw new Exception("Whole catalog Addressables initialization failed",initialization.OperationException);
  Addressables.Release(initialization);
  if(bundlePath!=null){var providers=Addressables.ResourceManager.ResourceProviders;if(!providers.Any(x=>x is AssetBundleProvider))providers.Add(new AssetBundleProvider());if(!providers.Any(x=>x is BundledAssetProvider))providers.Add(new BundledAssetProvider());}
  // Stock helpers use First(), so an empty initialization locator cannot precede us.
  foreach(var prior in Addressables.ResourceLocators.ToArray())Addressables.RemoveResourceLocator(prior);
  locator=new ResourceLocationMap("original-whole-catalog");
  var locations=new Dictionary<int,IResourceLocation>();var bundles=new Dictionary<string,IResourceLocation>();
  if(bundlePath!=null)foreach(var pair in (JObject)manifest["bundles"]){var dependency=new ResourceLocationBase(pair.Key,Path.Combine(bundlePath,pair.Key),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));dependency.Data=new AssetBundleRequestOptions{BundleName=pair.Key};bundles.Add(pair.Key,dependency);}
  foreach(var row in manifest["locations"]){
   var type=Type.GetType((string)row["type"],false);if(type==null)throw new Exception("Original resource type unavailable: "+row["type"]);
   IResourceLocation[] dependencies=new IResourceLocation[0];string provider=assetProvider;
   if(bundlePath!=null){string owner=(string)row["bundle"];dependencies=new[]{bundles[owner]}.Concat(manifest["bundles"][owner]["dependencies"].Select(x=>bundles[(string)x])).ToArray();if(type==typeof(SceneInstance))provider=typeof(SceneProvider).FullName;}
   locations.Add((int)row["id"],new ResourceLocationBase((string)row["primaryKey"],(string)row["path"],provider,type,dependencies));
  }
  foreach(var key in manifest["keys"]){
   // Non-string keys require their original decoder; never silently stringify them.
   if(key["keyType"]!=null&&(string)key["keyType"]!="System.String")continue;
   var found=key["locations"].Select(x=>(int)x).Where(locations.ContainsKey).Select(x=>locations[x]).ToList();
   if(found.Count!=0)locator.Add((string)key["key"],found);
  }
  Addressables.AddResourceLocator(locator);
  if(!ReferenceEquals(Addressables.ResourceLocators.First(),locator))throw new Exception("Whole catalog locator order lost");
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
 public static object Counts(){return new{packs=ContentManager.allLoadedContentPacks.Length,bodies=(ContentManager.bodyPrefabs?.Length??0),masters=(ContentManager.masterPrefabs?.Length??0),items=(ContentManager.itemDefs?.Length??0),equipment=(ContentManager.equipmentDefs?.Length??0),buffs=(ContentManager.buffDefs?.Length??0),elites=(ContentManager.eliteDefs?.Length??0),projectiles=(ContentManager.projectilePrefabs?.Length??0),effects=(ContentManager.effectDefs?.Length??0),scenes=(ContentManager.sceneDefs?.Length??0),states=(ContentManager.entityStateConfigurations?.Length??0),skills=(ContentManager.skillDefs?.Length??0),droneDefs=(ContentManager.droneDefs?.Length??0),scope="Original provider registration; no ownership, unlock, gameplay or appearance acceptance"};}
}
