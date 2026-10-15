using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

// Bind the original CharacterBody temporary-visual references from the exact
// shipped initializer's field/path pairs. Handles remain owned by this session.
public sealed partial class MovementBatchProbe {
 readonly Dictionary<FieldInfo,GameObject> priorBodyVisualSlots=new Dictionary<FieldInfo,GameObject>();
 readonly List<AsyncOperationHandle<GameObject>> ownedBodyVisualHandles=new List<AsyncOperationHandle<GameObject>>();
 IEnumerator PrepareOriginalBodyVisualReferences(){
  var descriptor=JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);
  Check(OriginalBodyVisualMap.InputId==(string)descriptor["input_id"],"Original body visuals belong to another input");
  var owner=typeof(CharacterBody).GetNestedType("AssetReferences",BindingFlags.NonPublic);
  Check(owner!=null,"Original CharacterBody visual-reference owner changed");
  var pending=new List<KeyValuePair<FieldInfo,AsyncOperationHandle<GameObject>>>();
  var unavailable=new List<string>();
  foreach(var row in OriginalBodyVisualMap.Rows){
   Check(row.Length==3,"Original body visual mapping changed");
   var field=owner.GetField(row[2],BindingFlags.Public|BindingFlags.Static);
   Check(field!=null&&field.FieldType==typeof(GameObject),"Original body visual slot changed: "+row[2]);
   // Other owned adapters may already provide the same source asset.
   if((GameObject)field.GetValue(null))continue;
   string key;
   if(row[0]=="LegacyResourcesAPI"){
    if(!LegacyResourcesAPI.GetGuid(row[1],out key)){unavailable.Add(row[2]+": legacy alias absent");continue;}
   }else Check(row[0]=="Addressables","Unknown original body visual loader");
   var handle=row[0]=="LegacyResourcesAPI"?LegacyResourcesAPI.LoadAsync<GameObject>(row[1]):Addressables.LoadAssetAsync<GameObject>(row[1]);
   ownedBodyVisualHandles.Add(handle);pending.Add(new KeyValuePair<FieldInfo,AsyncOperationHandle<GameObject>>(field,handle));
  }
  var deadline=Time.realtimeSinceStartup+45f;
  while(pending.Any(entry=>!entry.Value.IsDone)&&Time.realtimeSinceStartup<deadline)yield return null;
  Check(pending.All(entry=>entry.Value.IsDone),"Original CharacterBody visual-reference load timed out");
  foreach(var entry in pending){
   var handle=entry.Value;
   if(handle.Status!=AsyncOperationStatus.Succeeded||!handle.Result){unavailable.Add(entry.Key.Name+": original asset load failed");continue;}
   Check(!((GameObject)entry.Key.GetValue(null)),"Original body visual slot changed during load");
   priorBodyVisualSlots.Add(entry.Key,null);entry.Key.SetValue(null,handle.Result);
  }
  var exposed=owner.GetField("mercExposeEffectPrefab",BindingFlags.Public|BindingFlags.Static);
  Check(exposed!=null&&(GameObject)exposed.GetValue(null),"Original Merc expose visual missing after source reference load");
  r.world.bodyVisualSlots=priorBodyVisualSlots.Count;r.world.bodyVisualUnavailable=unavailable.ToArray();Save();
 }
 void CleanupOriginalBodyVisualReferences(){
  foreach(var entry in priorBodyVisualSlots)entry.Key.SetValue(null,entry.Value);
  priorBodyVisualSlots.Clear();
  foreach(var handle in ownedBodyVisualHandles)if(handle.IsValid())Addressables.Release(handle);
  ownedBodyVisualHandles.Clear();
  if(r.world!=null)r.world.bodyVisualCleaned=true;
 }
}
