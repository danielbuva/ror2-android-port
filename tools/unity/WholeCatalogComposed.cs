using System;
using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;
using Newtonsoft.Json.Linq;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.ResourceProviders;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.Util;
using System.Collections.Generic;

// The expanded build gives old assets a shared bundle owner. Keep that owner
// loaded before the existing composed game deserializes its body/support assets.
public static class WholeCatalogComposed {
 static AssetBundle owned;
 static IResourceLocator[] priorLocators;
 static IResourceLocator ownedLocator;
 static HashSet<string> borrowedNames;
 delegate bool ExtractSubObjectKey(object key,out string mainKey,out string subKey);
 static readonly ExtractSubObjectKey originalSubObjectKey=(ExtractSubObjectKey)Delegate.CreateDelegate(typeof(ExtractSubObjectKey),typeof(ResourceManagerConfig).GetMethod("ExtractKeyAndSubKey",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic));
 sealed class BorrowedBundle : IAssetBundleResource {
  readonly string name;public BorrowedBundle(string value){name=value;}
  public AssetBundle GetAssetBundle(){
   if(!owned||borrowedNames==null||!borrowedNames.Contains(name))throw new Exception("Borrowed bundle outlived its composed owner: "+name);
   var bundle=AssetBundle.GetAllLoadedAssetBundles().SingleOrDefault(value=>value.name==name);
   if(!bundle)throw new Exception("Composed bundle owner released before its consumers: "+name);return bundle;
  }
 }
 sealed class BorrowedBundleProvider : ResourceProviderBase {
  public override Type GetDefaultType(IResourceLocation location){return typeof(IAssetBundleResource);}
  public override void Provide(ProvideHandle handle){
   try{var resource=new BorrowedBundle(handle.Location.PrimaryKey);resource.GetAssetBundle();handle.Complete<IAssetBundleResource>(resource,true,null);}
   catch(Exception error){handle.Complete<IAssetBundleResource>(null,false,error);}
  }
  // Existing manual/provider leases keep these bundles alive; this bridge owns none.
  public override void Release(IResourceLocation location,object asset){}
 }
 sealed class BorrowedAssetProvider : ResourceProviderBase {
  // Match the shipped provider's broad request contract (including Object loads).
  public override Type GetDefaultType(IResourceLocation location){return typeof(object);}
  public override void Provide(ProvideHandle handle){
   try{
    var dependencies=new List<object>();handle.GetDependencies(dependencies);
    var resource=dependencies.OfType<IAssetBundleResource>().FirstOrDefault();
    if(resource==null)throw new Exception("Borrowed asset bundle dependency absent");
    string path=handle.ResourceManager.TransformInternalId(handle.Location);
    if(handle.Type.IsArray)throw new Exception("Unmeasured borrowed array contract: "+path);
    string mainKey,subKey;var bundle=resource.GetAssetBundle();
    // Match the shipped provider's exact subobject name/type selection.
    var asset=originalSubObjectKey(path,out mainKey,out subKey)
     ?bundle.LoadAssetWithSubAssets(mainKey,handle.Type).FirstOrDefault(value=>value&&value.name==subKey&&handle.Type.IsAssignableFrom(value.GetType()))
     :bundle.LoadAsset(path,handle.Type);
    if(!asset)throw new Exception("Borrowed typed asset missing: "+path+" / "+handle.Type.FullName);
    handle.Complete<UnityEngine.Object>(asset,true,null);
   }catch(Exception error){handle.Complete<UnityEngine.Object>(null,false,error);}
  }
  public override void Release(IResourceLocation location,object asset){}
 }
 public static IEnumerator Prepare(){
  if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))yield break;
  if(owned)throw new Exception("Shared whole-content dependency already owned");
  string path=Path.Combine(Application.persistentDataPath,"payload","whole-game-content");
  if(!File.Exists(path))throw new Exception("Shared whole-content dependency not synchronized");
  if(AssetBundle.GetAllLoadedAssetBundles().Any(x=>x.name=="whole-game-content"))throw new Exception("Shared dependency has a foreign owner");
  var load=AssetBundle.LoadFromFileAsync(path);yield return load;owned=load.assetBundle;
  if(!owned)throw new Exception("Shared whole-content dependency failed to load");
 }
 public static void ConfigureLocations(){
  if(!owned||ownedLocator!=null)throw new Exception("Shared content location ownership invalid");
  string payload=Path.Combine(Application.persistentDataPath,"payload");
  var manifest=JObject.Parse(File.ReadAllText(Path.Combine(payload,"whole-catalog.json")));
  var descriptor=JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);
  if((string)manifest["input_id"]!=(string)descriptor["input_id"]||(string)manifest["attempt"]!=(string)descriptor["attempt"])throw new Exception("Composed APK/catalog generation mismatch");
  priorLocators=Addressables.ResourceLocators.ToArray();
  borrowedNames=new HashSet<string>(AssetBundle.GetAllLoadedAssetBundles().Select(bundle=>bundle.name));
  var providers=Addressables.ResourceManager.ResourceProviders;if(!providers.Any(provider=>provider is BorrowedBundleProvider))providers.Add(new BorrowedBundleProvider());
  if(!providers.Any(provider=>provider is BorrowedAssetProvider))providers.Add(new BorrowedAssetProvider());
  WholeCatalogLoader.RegisterLocations(manifest,typeof(BundledAssetProvider).FullName,payload,typeof(BorrowedBundleProvider).FullName,borrowedNames,typeof(BorrowedAssetProvider).FullName);ownedLocator=WholeCatalogLoader.locator;
 }
 public static void Release(){
  if(ownedLocator!=null){Addressables.RemoveResourceLocator(ownedLocator);foreach(var locator in priorLocators){Addressables.RemoveResourceLocator(locator);Addressables.AddResourceLocator(locator);}WholeCatalogLoader.locator=null;ownedLocator=null;priorLocators=null;}
  borrowedNames=null;if(owned){owned.Unload(true);owned=null;}
 }
 public static RoR2.BuffDef[] BuffDefinitions(){if(!owned)throw new Exception("Shared original buff owner unavailable");return owned.LoadAllAssets<RoR2.BuffDef>();}
 public static RoR2.ItemDef[] ItemDefinitions(){if(!owned)throw new Exception("Shared original item owner unavailable");return owned.LoadAllAssets<RoR2.ItemDef>();}
 public static RoR2.EliteDef[] EliteDefinitions(){if(!owned)throw new Exception("Shared original elite owner unavailable");return owned.LoadAllAssets<RoR2.EliteDef>();}
 public static RoR2.KeyItemDef[] KeyItemDefinitions(){if(!owned)throw new Exception("Shared original key-item owner unavailable");return owned.LoadAllAssets<RoR2.KeyItemDef>();}
 public static RoR2.ItemGroupType[] ItemGroupTypes(){if(!owned)throw new Exception("Shared original item-group owner unavailable");return owned.LoadAllAssets<RoR2.ItemGroupType>();}
 public static RoR2.ItemGroupProvider[] ItemGroupProviders(){if(!owned)throw new Exception("Shared original item-group provider owner unavailable");return owned.LoadAllAssets<RoR2.ItemGroupProvider>();}
 public static RoR2.CharacterBody[] BodyComparisons(Type holder){
  if(!owned)throw new Exception("Shared original body owner unavailable");
  var manifest=JObject.Parse(File.ReadAllText(Path.Combine(Application.persistentDataPath,"payload","whole-catalog.json")));
  var locations=manifest["locations"].Where(row=>((string)row["type"]).StartsWith("UnityEngine.GameObject,",StringComparison.Ordinal)).ToLookup(row=>Path.GetFileName((string)row["path"]),StringComparer.OrdinalIgnoreCase);
  return holder.GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Static).Select(field=>{
   var matches=locations[field.Name+".prefab"].ToArray();
   if(field.FieldType!=typeof(RoR2.CharacterBody)||matches.Length!=1)throw new Exception("Original comparison body owner ambiguous: "+field.Name);
   string owner=(string)matches[0]["bundle"];var bundle=AssetBundle.GetAllLoadedAssetBundles().SingleOrDefault(value=>value.name==owner);
   if(!bundle)throw new Exception("Original comparison body owner not loaded: "+field.Name+" / "+owner);
   var prefab=bundle.LoadAsset<GameObject>((string)matches[0]["path"]);var body=prefab?prefab.GetComponent<RoR2.CharacterBody>():null;
   if(!body||prefab.name!=field.Name)throw new Exception("Original comparison body identity differs: "+field.Name);return body;
  }).ToArray();
 }
}
