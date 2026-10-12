using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using Path = System.IO.Path;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Optional whole-catalog boot in the same APK. Ordinary launches keep the working
// composed game until the broad initialization path has device acceptance.
public sealed class WholeCatalogBootstrap : MonoBehaviour {
 public static bool Requested {get{return File.Exists(Path.Combine(Application.persistentDataPath,"whole-catalog-selection.json"));}}
 JObject selection,manifest;string reportPath,error;int errors;float started;readonly List<string> messages=new List<string>();
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]static void Initialize(){if(Requested)new GameObject("Original whole-catalog boot").AddComponent<WholeCatalogBootstrap>();}
 void Log(string message,string trace,LogType kind){if(kind==LogType.Exception||kind==LogType.Error||kind==LogType.Assert){errors++;WholeCatalogLoader.failures.Add(message+"\n"+trace);if(messages.Count<32)messages.Add(message+"\n"+trace);}}
 void Save(bool finished,bool success){File.WriteAllText(reportPath,Newtonsoft.Json.JsonConvert.SerializeObject(new{finished,success,phase=WholeCatalogLoader.phase,progress=WholeCatalogLoader.progress,error,errors,messages,seconds=Time.realtimeSinceStartup-started,counts=WholeCatalogLoader.Counts(),input=manifest?["input_id"],attempt=manifest?["attempt"],scope="Original whole catalogs; platform startup and unavailable audio remain deferred"}));}
 IEnumerator Start(){
  // The historical Windows-bundle negative control belongs to lab startup, not
  // to this content phase. Begin attribution after that startup has completed.
  var diagnostic=FindObjectOfType<LabDiagnostics>();while(diagnostic&&!diagnostic.Ready)yield return null;
  started=Time.realtimeSinceStartup;reportPath=Path.Combine(Application.persistentDataPath,"whole-catalog-result.json");
  selection=JObject.Parse(File.ReadAllText(Path.Combine(Application.persistentDataPath,"whole-catalog-selection.json")));
  string path=Path.Combine(Application.persistentDataPath,"payload","whole-catalog.json");
  var routines=new Stack<IEnumerator>();routines.Push(Boot(path));Application.logMessageReceived+=Log;
  while(routines.Count!=0){
   object current=null;bool more=false;
   try{if(Time.realtimeSinceStartup-started>420)throw new TimeoutException("Whole catalog initialization stalled");var top=routines.Peek();more=top.MoveNext();if(more)current=top.Current;else routines.Pop();}
   catch(Exception e){error=e.ToString();break;}
   if(more){var nested=current as IEnumerator;if(nested!=null){routines.Push(nested);continue;}yield return current;}
   Save(false,false);
  }
  Application.logMessageReceived-=Log;Save(true,error==null&&errors==0);Debug.Log("WHOLE_CATALOG_RESULT "+File.ReadAllText(reportPath));
 }
 IEnumerator Boot(string path){
  if(!File.Exists(path))throw new Exception("Whole catalog payload not synchronized");
  string hash;using(var stream=File.OpenRead(path))using(var sha=System.Security.Cryptography.SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
  if(hash!=(string)selection["manifest_sha256"])throw new Exception("Whole catalog payload identity mismatch");
  manifest=JObject.Parse(File.ReadAllText(path));
  var descriptor=JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);
  if((string)descriptor["attempt"]!=(string)manifest["attempt"]||(string)descriptor["input_id"]!=(string)manifest["input_id"])throw new Exception("APK/catalog generation mismatch");
  foreach(var pair in (JObject)manifest["bundles"]){var file=new FileInfo(Path.Combine(Application.persistentDataPath,"payload",pair.Key));if(!file.Exists||file.Length!=(long)pair.Value["bytes"])throw new Exception("Incomplete catalog generation: "+pair.Key);}
  string directory=Path.Combine(Application.persistentDataPath,"whole-catalog-init");Directory.CreateDirectory(directory);string catalog=Path.Combine(directory,"catalog.json"),settings=Path.Combine(directory,"settings.json");
  File.WriteAllText(catalog,"{\"m_LocatorId\":\"whole-android-init\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
  var data=new ResourceManagerRuntimeData{BuildTarget="Android",DisableCatalogUpdateOnStartup=true,LogResourceManagerExceptions=true};data.CatalogLocations.Add(new ResourceLocationData(new[]{ResourceManagerRuntimeData.kCatalogAddress},catalog,typeof(ContentCatalogProvider),typeof(ContentCatalogData)));File.WriteAllText(settings,JsonUtility.ToJson(data));
  string original=Addressables.RuntimePath+"/settings.json";Addressables.InternalIdTransformFunc=location=>location.InternalId==original?settings:location.InternalId;
  yield return WholeCatalogLoader.Load(manifest,typeof(BundledAssetProvider).FullName,Path.Combine(Application.persistentDataPath,"payload"));
  if(errors!=0)throw new Exception("Original provider loading reported errors; refuse incomplete catalog initialization");
  yield return WholeCatalogLoader.InitializeCatalogs();
  if(errors!=0)throw new Exception("Original catalog initialization logged failure");
 }
 void OnGUI(){GUI.Label(new Rect(24,24,900,140),"Original catalog integration\n"+WholeCatalogLoader.phase+" "+(WholeCatalogLoader.progress*100).ToString("F0")+"%\n"+(error??""));}
}
