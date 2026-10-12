using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

public sealed class WholeItemBehaviorPreservation : UnityEditor.Build.IPreprocessBuildWithReport {
 public int callbackOrder {get{return -100;}}
 public void OnPreprocessBuild(UnityEditor.Build.Reporting.BuildReport report){
  var types=typeof(RoR2.CharacterBody).Assembly.GetTypes().SelectMany(type=>type.GetMethods(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.DeclaredOnly)).Where(method=>Attribute.IsDefined(method,typeof(RoR2.Items.BaseItemBodyBehavior.ItemDefAssociationAttribute))).SelectMany(method=>{
   var association=(RoR2.Items.BaseItemBodyBehavior.ItemDefAssociationAttribute)Attribute.GetCustomAttribute(method,typeof(RoR2.Items.BaseItemBodyBehavior.ItemDefAssociationAttribute));
   return new[]{method.DeclaringType,association.behaviorTypeOverride??method.DeclaringType};
  }).Distinct().OrderBy(type=>type.FullName).ToArray();
  string directory="Assets/LabLoadingScene/WholeCatalogPreservation";if(!Directory.Exists(directory))return;
  var root=new System.Xml.Linq.XElement("linker",new System.Xml.Linq.XElement("assembly",new System.Xml.Linq.XAttribute("fullname",typeof(RoR2.CharacterBody).Assembly.GetName().Name),types.Select(type=>new System.Xml.Linq.XElement("type",new System.Xml.Linq.XAttribute("fullname",type.FullName.Replace('+','/')),new System.Xml.Linq.XAttribute("preserve","all")))));
  directory=Path.Combine(directory,"item-behaviors");Directory.CreateDirectory(directory);string path=Path.Combine(directory,"link.xml");File.WriteAllText(path,root.ToString());AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
 }
}
public static class WholeCatalogBuild {
 static JObject catalog;static string root;
 public static void Append(string work,List<AssetBundleBuild> builds){
  string recipe=Path.Combine(work,"whole-catalog-build.json");if(!File.Exists(recipe)){catalog=null;return;}
  root=work;var config=JObject.Parse(File.ReadAllText(recipe));string manifest=Path.GetFullPath((string)config["manifest"]);
  if(!manifest.StartsWith(Path.Combine(work,"experiments/whole-catalog")+Path.DirectorySeparatorChar,StringComparison.Ordinal))throw new Exception("Whole catalog recipe outside owned input");
  catalog=JObject.Parse(File.ReadAllText(manifest));
  var owners=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
  foreach(var build in builds)foreach(string path in build.assetNames){if(owners.ContainsKey(path))throw new Exception("Duplicate explicit bundle ownership: "+path);owners.Add(path,build.assetBundleName);}
  var paths=catalog["locations"].Select(x=>(string)x["path"]).Distinct(StringComparer.OrdinalIgnoreCase).Where(x=>!owners.ContainsKey(x)).ToArray();
  foreach(var path in paths)if(!path.StartsWith("Assets/",StringComparison.Ordinal)||!File.Exists(path))throw new Exception("Whole catalog input missing: "+path);
  var ordinary=paths.Where(x=>!x.EndsWith(".unity",StringComparison.OrdinalIgnoreCase)).ToArray();
  builds.Add(new AssetBundleBuild{assetBundleName="whole-game-content",assetNames=ordinary});
  foreach(var path in ordinary)owners.Add(path,"whole-game-content");
  foreach(string path in paths.Where(x=>x.EndsWith(".unity",StringComparison.OrdinalIgnoreCase))){string name="whole-scene-"+Path.GetFileNameWithoutExtension(path).ToLowerInvariant();if(builds.Any(x=>x.assetBundleName==name))throw new Exception("Scene bundle name collision");builds.Add(new AssetBundleBuild{assetBundleName=name,assetNames=new[]{path}});owners.Add(path,name);}
  foreach(var row in catalog["locations"])row["bundle"]=owners[(string)row["path"]];
 }
 public static void Complete(AssetBundleManifest manifest){
  if(catalog==null)return;
  var bundles=new JObject();string output=Path.Combine(root,"generated-android-data");
  foreach(string name in manifest.GetAllAssetBundles()){
   string path=Path.Combine(output,name);string hash;using(var stream=File.OpenRead(path))using(var sha=System.Security.Cryptography.SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
   bundles[name]=JObject.FromObject(new{sha256=hash,bytes=new FileInfo(path).Length,dependencies=manifest.GetAllDependencies(name)});
  }
  catalog["bundles"]=bundles;
  File.WriteAllText(Path.Combine(output,"whole-catalog.json"),catalog.ToString(Newtonsoft.Json.Formatting.None));
 }
}
