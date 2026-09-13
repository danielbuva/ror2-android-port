using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.ResourceLocations;

// Decode locations only: never initialize providers or load assets/services.
public static class CatalogAddressProbe {
 [Serializable] class Config {public string catalog,output,attempt;public string[] keys;}
 [Serializable] class Location {public string key,internalId,provider,type;public string[] dependencies;}
 [Serializable] class Report {public string attempt,error;public Location[] locations;public string[] missing;}
 [MenuItem("Porting Lab/Inspect Catalog Addresses")]
 public static void Inspect(){
  var cfg=JsonUtility.FromJson<Config>(File.ReadAllText("Assets/LabCatalogQuery.json"));var report=new Report{attempt=cfg.attempt};
  try{
   var locator=JsonUtility.FromJson<ContentCatalogData>(File.ReadAllText(cfg.catalog)).CreateLocator();
   var rows=new List<Location>();var missing=new List<string>();
   foreach(var key in cfg.keys){
    IList<IResourceLocation> locations;
    if(!locator.Locate(key,null,out locations)){missing.Add(key);continue;}
    foreach(var loc in locations)rows.Add(new Location{key=key,internalId=loc.InternalId,provider=loc.ProviderId,type=loc.ResourceType.FullName,dependencies=loc.HasDependencies?loc.Dependencies.Select(d=>d.InternalId).ToArray():new string[0]});
   }
   report.locations=rows.ToArray();report.missing=missing.ToArray();
  }catch(Exception e){report.error=e.ToString();}
  File.WriteAllText(cfg.output,JsonUtility.ToJson(report,true));Debug.Log("LAB_CATALOG_ADDRESSES "+cfg.attempt);
 }
}
