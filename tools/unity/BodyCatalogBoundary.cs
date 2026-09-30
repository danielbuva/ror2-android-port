using System;
using System.Collections;
using System.IO;
using Path = System.IO.Path;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;

public sealed partial class MovementBatchProbe {
 IEnumerator RegisterBodyCatalog(){
  Check(BodyCatalog.bodyCount==0&&LegacyResourcesAPI.ActiveCount==0,"Existing catalog/request ownership");
  r.phase="body-catalog-initialize";Save();
  var directory=Path.Combine(Application.persistentDataPath,"body-catalog-probe");Directory.CreateDirectory(directory);
  var catalog=Path.Combine(directory,"catalog.json");var settings=Path.Combine(directory,"settings.json");
  // Reuse the accepted controller probe's real, empty Addressables initialization.
  File.WriteAllText(catalog,"{\"m_LocatorId\":\"body-catalog-probe\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
  var data=new ResourceManagerRuntimeData{BuildTarget="Android",DisableCatalogUpdateOnStartup=true,LogResourceManagerExceptions=true};
  data.CatalogLocations.Add(new ResourceLocationData(new[]{ResourceManagerRuntimeData.kCatalogAddress},catalog,typeof(ContentCatalogProvider),typeof(ContentCatalogData)));
  File.WriteAllText(settings,JsonUtility.ToJson(data));var originalSettings=Addressables.RuntimePath+"/settings.json";
  Addressables.InternalIdTransformFunc=loc=>loc.InternalId==originalSettings?settings:loc.InternalId;
  var init=Addressables.InitializeAsync();Addressables.ResourceManager.Acquire(init);
  var deadline=Time.realtimeSinceStartup+8;while(!init.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;
  Check(init.IsDone&&init.Status==AsyncOperationStatus.Succeeded,"Real Addressables initialization failed");Addressables.Release(init);
  string mapped;const string key="Textures/BodyIcons/CommandoBody";
  Check(!LegacyResourcesAPI.GetGuid(key,out mapped),"Unexpected legacy portrait alias");
  var missing=LegacyResourcesAPI.LoadAsync<Texture2D>(key);deadline=Time.realtimeSinceStartup+3;
  while(!missing.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;
  yield return null;
  Check(missing.IsDone&&missing.Status==AsyncOperationStatus.Failed&&missing.Result==null,"Missing portrait did not fail honestly");
  Check(missing.OperationException is InvalidKeyException,"Unexpected portrait failure class");Addressables.Release(missing);
  Check(LegacyResourcesAPI.ActiveCount==0,"Missing request callback not drained");
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  artifactBundle=AssetBundle.LoadFromFile(Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Body bundle missing");
  var prefab=artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);Check(prefab&&!prefab.activeSelf&&prefab.name=="CommandoBody","Unexpected body prefab");
  var body=prefab.GetComponent<CharacterBody>();var portrait=body.portraitIcon;
  Check(portrait&&portrait.name=="texCommandoIcon","Serialized portrait missing");
  r.phase="original-body-catalog-register";Save();
  StaticCall(typeof(BodyCatalog),"SetBodyPrefabs",(object)new[]{prefab});
  deadline=Time.realtimeSinceStartup+3;while(LegacyResourcesAPI.ActiveCount!=0&&Time.realtimeSinceStartup<deadline)yield return null;
  yield return null;yield return null;
  Check(LegacyResourcesAPI.ActiveCount==0,"Catalog portrait callback still pending");
  Check(BodyCatalog.bodyCount==1&&body.bodyIndex!=(BodyIndex)(-1),"Original index assignment failed");
  Check(BodyCatalog.FindBodyIndex("CommandoBody")==body.bodyIndex&&BodyCatalog.FindBodyIndex("CommandoBody(Clone)")==body.bodyIndex,"Original name/index lookup failed");
  Check(BodyCatalog.GetBodyPrefab(body.bodyIndex)==prefab,"Original prefab lookup failed");
  Check(body.portraitIcon==portrait,"Missing-key callback replaced serialized portrait");
  Check(!prefab.activeSelf,"Catalog registration activated gameplay");
 }
}
