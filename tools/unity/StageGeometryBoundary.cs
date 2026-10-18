// Subsystem: stage transport (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareStageGeometry, LoadStageGeometry (StageGeometrySession); teardown DeactivateSourceGameManager, DeactivateSourceSceneInfo, CleanupStageGeometry (coroutine); Dispose is a no-op.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Networking;

// Recovered geometry and original out-of-bounds volumes; owned Android entry/material boundary.
public sealed partial class MovementBatchProbe {
 [Serializable] public class StageGeometryReport {
  public string scene,spawnMarker,groundColliderPath,groundColliderScene;public bool loaded,cleaned,groundHit,originalStageObjects,sourceSceneInfoActive,sourceStagePopulationActive;
  public bool mapZonesReady;public int mapZoneNetworkObjects,mapZoneIdentityComponents,mapZoneEmptySceneIds,mapZoneCount,mapZoneEntries,mapZoneExits,mapZoneTeleports;public string lastMapZone;
  public int activeRoots,terrainMaterials,surfaceMaterials,terrainTextureMaterials;public bool terrainTexturesBound;public int objects,renderers,billboards,missingBillboardAssets,emptyLODRendererSlots,meshColliders,colliders,worldColliders,nonWorldColliders,missingMeshes,missingColliderMeshes,behaviours,previewDisableComponents,previewsInactive,previewsInactiveByParent;
  public int sourceRockZones,sourceRockPrefabSlots,sourceRockPrefabsResolved,sourceRockComponentsResolved,sourceRockZonePointsResolved,sourceDustManagers,sourceDustPrefabsResolved,sourceDustLocationsResolved;
  public Vector3 spawnPosition,groundPosition,groundNormal,entryOrigin;
  public string[] emptyMeshPaths,emptyColliderPaths;
 }
 AssetBundle stageGeometryBundle;Scene stageGeometryScene;
 readonly List<Material> stageGeometryMaterials=new List<Material>();
 bool stageSourceObjects;GameObject sourceSceneInfoRoot,sourceGameManagerRoot;
 IntegratedStageSpec firstStageSpec;string firstStageName;bool firstStagePolicyConsumed;float firstStageSelectionValue;
 StageGeometrySession stageGeometrySession;
 StageGeometrySession GetStageGeometrySession(){if(stageGeometrySession==null)stageGeometrySession=new StageGeometrySession(this);return stageGeometrySession;}
 void ActivateSourceGameManager(){GetStageGeometrySession().ActivateSourceGameManager();}
 void DeactivateSourceGameManager(){GetStageGeometrySession().DeactivateSourceGameManager();}
 SceneInfo ActivateSourceSceneInfo(){return GetStageGeometrySession().ActivateSourceSceneInfo();}
 void DeactivateSourceSceneInfo(){GetStageGeometrySession().DeactivateSourceSceneInfo();}
 IEnumerator PrepareStageGeometry(SessionConfig cfg){return GetStageGeometrySession().PrepareStageGeometry(cfg);}
 IEnumerator LoadStageGeometry(string bundleName,int previewCount,IntegratedStageSpec spec,int initialMapZones=0,string[] initialActiveNames=null,string[] initialPreviewNames=null){return GetStageGeometrySession().LoadStageGeometry(bundleName,previewCount,spec,initialMapZones,initialActiveNames,initialPreviewNames);}
 void EnableStageMapZones(){GetStageGeometrySession().EnableStageMapZones();}
 void PauseStageMapZones(){GetStageGeometrySession().PauseStageMapZones();}
 bool InsideSourceStageBounds(Vector3 point){return GetStageGeometrySession().InsideSourceStageBounds(point);}
 void StartStageMapZoneObservations(){GetStageGeometrySession().StartStageMapZoneObservations();}
 void StopStageMapZoneObservations(){GetStageGeometrySession().StopStageMapZoneObservations();}
 static string StageObjectPath(Transform target){return StageGeometrySession.StageObjectPath(target);}
 IEnumerator CleanupStageGeometry(){return GetStageGeometrySession().CleanupStageGeometry();}

 // Retain across stage handoffs and partial setup. All release stays in the
 // awaited cleanup coroutine at its existing call sites; Dispose does not run it.
 sealed class StageGeometrySession : IDisposable {
  readonly MovementBatchProbe coordinator;
  readonly List<BillboardAsset> stageGeometryBillboards=new List<BillboardAsset>();
  bool stageMoonVolumes;int stageZoneNetworkObjects;string[] stageZoneActiveNames,stageSourceNames=new string[0];
  MapZone[] stageMapZones=new MapZone[0];Action<CharacterBody,MapZone> stageZoneEntered,stageZoneLeft;Action<CharacterBody> stageZoneTeleported;bool ownsStageMapZoneObservations;
  public StageGeometrySession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public void ActivateSourceGameManager(){
   var previous=coordinator.eventHost?coordinator.eventHost.GetComponent<GlobalEventManager>():null;
   coordinator.Check(coordinator.stageSourceObjects&&!coordinator.sourceGameManagerRoot&&previous&&GlobalEventManager.instance==previous,"Original source event owner requires the existing local event context");
   var roots=coordinator.stageGeometryScene.GetRootGameObjects().Where(x=>x.name=="GameManager").ToArray();
   coordinator.Check(roots.Length==1&&!roots[0].activeSelf,"Original source GameManager root absent or already active");
   var root=roots[0];var manager=root.GetComponent<GlobalEventManager>();
   coordinator.Check(manager&&root.GetComponents<MonoBehaviour>().Length==1,"Original source GameManager component contract changed");
   Call(previous,"OnDisable");
   try{root.SetActive(true);coordinator.Check(GlobalEventManager.instance==manager,"Original source GlobalEventManager did not adopt the singleton");coordinator.sourceGameManagerRoot=root;}
   catch{root.SetActive(false);Call(previous,"OnEnable");throw;}
  }
  public void DeactivateSourceGameManager(){
   if(!coordinator.sourceGameManagerRoot)return;
   coordinator.sourceGameManagerRoot.SetActive(false);coordinator.sourceGameManagerRoot=null;
   coordinator.Check(!GlobalEventManager.instance,"Original source event owner survived stage teardown");
   var previous=coordinator.eventHost.GetComponent<GlobalEventManager>();Call(previous,"OnEnable");
   coordinator.Check(GlobalEventManager.instance==previous,"Local event owner was not restored after source stage");
  }
  public SceneInfo ActivateSourceSceneInfo(){
   coordinator.Check(coordinator.stageSourceObjects&&Run.instance&&NetworkServer.active&&!SceneInfo.instance&&!ClassicStageInfo.instance&&!coordinator.sourceSceneInfoRoot,"Original source context requires an active owned run and no duplicate context");
   var roots=coordinator.stageGeometryScene.GetRootGameObjects().Where(x=>x.name=="SceneInfo").ToArray();coordinator.Check(roots.Length==1&&!roots[0].activeSelf,"Original source SceneInfo root absent or already activated");
   var root=roots[0];var info=root.GetComponent<SceneInfo>();var population=root.GetComponent<ClassicStageInfo>();
   coordinator.Check(info&&population&&root.GetComponents<MonoBehaviour>().All(x=>x&&!x.GetType().FullName.StartsWith("Ak")&&x.GetType().Name!="RTPCController"),"Original source scene context contains missing/native-audio components");
   ActivateSourceGameManager();
   try{coordinator.sourceSceneInfoRoot=root;root.SetActive(true);coordinator.Check(SceneInfo.instance==info&&ClassicStageInfo.instance==population,"Original source scene owner did not initialize");return info;}
   catch{root.SetActive(false);coordinator.sourceSceneInfoRoot=null;DeactivateSourceGameManager();throw;}
  }
  public void DeactivateSourceSceneInfo(){if(coordinator.sourceSceneInfoRoot){coordinator.sourceSceneInfoRoot.SetActive(false);coordinator.sourceSceneInfoRoot=null;}coordinator.Check(!SceneInfo.instance&&!ClassicStageInfo.instance,"Original source scene context survived deactivation");DeactivateSourceGameManager();}
  public IEnumerator PrepareStageGeometry(SessionConfig cfg){
   coordinator.firstStageSpec=null;coordinator.firstStageName="golemplains";coordinator.firstStagePolicyConsumed=false;stageSourceNames=coordinator.r.originalStageSceneNames??cfg.originalStageSceneNames??new string[0];
   if(cfg.integratedWorld&&cfg.teleporterLoop&&coordinator.r.freePlay){
    // Run.Start is unavailable behind the stock platform boundary. Use its shipped
    // scene group, weighted selector and RNG before the body needs stage geometry.
    var group=WholeCatalogComposed.LoadOwnedContent<SceneCollection>("Assets/WholeGame/RoR2/Base/SceneGroups/sgStage1.asset");
    coordinator.Check(group&&group.name=="sgStage1","Original starting scene group unavailable");
    var choices=new WeightedSelection<SceneDef>();group.AddToWeightedSelection(choices,scene=>scene&&!scene.requiredExpansion);
    var names=choices.choices.Take(choices.Count).Select(choice=>choice.value.cachedName).OrderBy(name=>name).ToArray();
    coordinator.Check(names.SequenceEqual(new[]{"blackbeach","blackbeach2","golemplains","golemplains2","lakes"})&&Mathf.Abs(choices.GetTotalWeight()-3f)<.001f,"Original eligible starting scenes or weights changed");
    var runRng=new Xoroshiro128Plus(coordinator.SelectOwnedRunSeed(cfg));var stageRng=new Xoroshiro128Plus(runRng.nextUlong);
    coordinator.firstStageSelectionValue=stageRng.nextNormalizedFloat;var selected=choices.Evaluate(coordinator.firstStageSelectionValue);
    coordinator.Check(selected&&selected.stageOrder==1,"Original starting scene selection failed");coordinator.firstStageName=selected.cachedName;coordinator.firstStagePolicyConsumed=true;
    if(coordinator.firstStageName!="golemplains"){
     coordinator.firstStageSpec=cfg.integratedStages.SingleOrDefault(stage=>stage.name==coordinator.firstStageName);
     coordinator.Check(coordinator.firstStageSpec!=null&&!coordinator.firstStageSpec.moonMission,"Original starting scene has no converted Android content: "+coordinator.firstStageName);
    }
   }
   var load=coordinator.firstStageSpec==null?LoadStageGeometry("golemplains-spine-lab",cfg.stagePreviewCallbacks,null,cfg.stageMapZoneCount,cfg.stageMapZoneActiveNames,cfg.stagePreviewNames):LoadStageGeometry(coordinator.firstStageSpec.bundle,coordinator.firstStageSpec.previewCallbacks,coordinator.firstStageSpec);
   while(load.MoveNext())yield return load.Current;
   coordinator.Check(coordinator.stageGeometryScene.name==coordinator.firstStageName,"Selected original starting scene differs from loaded Android geometry");
  }
  public IEnumerator LoadStageGeometry(string bundleName,int previewCount,IntegratedStageSpec spec,int initialMapZones=0,string[] initialActiveNames=null,string[] initialPreviewNames=null){
   coordinator.r.stage=new StageGeometryReport();coordinator.r.phase="stage-geometry-load";coordinator.Save();
   string stageName=bundleName.Replace("-spine-lab","");
   coordinator.stageSourceObjects=stageSourceNames.Contains(stageName);
   if(coordinator.stageSourceObjects){coordinator.Check(bundleName==stageName+"-spine-lab","Unreviewed original stage-scene switch");bundleName=stageName+"-source-lab";}
   coordinator.r.stage.originalStageObjects=coordinator.stageSourceObjects;
   coordinator.stageGeometryBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload",bundleName));
   coordinator.Check(coordinator.stageGeometryBundle,"Recovered stage geometry bundle missing");var scenes=coordinator.stageGeometryBundle.GetAllScenePaths();coordinator.Check(scenes.Length==1,"Expected one recovered stage geometry scene");
   yield return SceneManager.LoadSceneAsync(scenes[0],LoadSceneMode.Additive);coordinator.stageGeometryScene=SceneManager.GetSceneByPath(scenes[0]);
   coordinator.r.stage.loaded=coordinator.stageGeometryScene.IsValid()&&coordinator.stageGeometryScene.isLoaded;coordinator.r.stage.scene=coordinator.stageGeometryScene.name;coordinator.Check(coordinator.r.stage.loaded,"Stage geometry did not load");
   yield return null; // Allow original scene preview Start callbacks; no manual deactivation.
   var roots=coordinator.stageGeometryScene.GetRootGameObjects();coordinator.stageStaticRoots=new HashSet<GameObject>(roots);var transforms=roots.SelectMany(x=>x.GetComponentsInChildren<Transform>(true)).ToArray();
   coordinator.r.stage.objects=transforms.Length;coordinator.r.stage.behaviours=roots.Sum(x=>x.GetComponentsInChildren<MonoBehaviour>(true).Length);
   if(coordinator.stageSourceObjects){
    var rocks=roots.SelectMany(x=>x.GetComponentsInChildren<MaulingRockZoneManager>(true)).ToArray();
    coordinator.r.stage.sourceRockZones=rocks.Length;
    foreach(var rock in rocks){
     if(rock.maulingRockProjectilePrefabs!=null){coordinator.r.stage.sourceRockPrefabSlots+=rock.maulingRockProjectilePrefabs.Count;
      foreach(var prefab in rock.maulingRockProjectilePrefabs)if(prefab){coordinator.r.stage.sourceRockPrefabsResolved++;if(prefab.GetComponent<MaulingRock>())coordinator.r.stage.sourceRockComponentsResolved++;}}
     if(rock.startZonePoint1&&rock.startZonePoint2&&rock.endZonePoint1&&rock.endZonePoint2)coordinator.r.stage.sourceRockZonePointsResolved++;
    }
    var dust=roots.SelectMany(x=>x.GetComponentsInChildren<RoR2.DustStreakManager>(true)).ToArray();coordinator.r.stage.sourceDustManagers=dust.Length;
    foreach(var manager in dust){if(manager.dustStreakPrefab)coordinator.r.stage.sourceDustPrefabsResolved++;if(manager.dustStreakLocations!=null)coordinator.r.stage.sourceDustLocationsResolved+=manager.dustStreakLocations.Count(x=>x);}
   }
   var previewCallbacks=roots.SelectMany(x=>x.GetComponentsInChildren<MonoBehaviour>(true)).ToArray();
   // Shipped inactive variant parents legitimately prevent Start from running.
   coordinator.r.stage.previewDisableComponents=previewCallbacks.Count(x=>x&&x.GetType()==typeof(DisableOnStart));coordinator.r.stage.previewsInactive=previewCallbacks.Count(x=>x&&x is DisableOnStart&&!x.gameObject.activeInHierarchy);coordinator.r.stage.previewsInactiveByParent=previewCallbacks.Count(x=>x&&x is DisableOnStart&&x.gameObject.activeSelf&&!x.gameObject.activeInHierarchy);
   var previewNames=spec!=null&&spec.previewNames!=null?spec.previewNames:initialPreviewNames??Enumerable.Repeat("EscapePodMesh",previewCount).ToArray();
   bool moon=spec!=null&&spec.moonMission;int expectedMapZones=spec==null?initialMapZones:spec.mapZoneCount;
   stageMoonVolumes=moon;stageZoneNetworkObjects=spec==null?0:spec.mapZoneNetworkObjects;stageZoneActiveNames=(spec==null?initialActiveNames:spec.mapZoneActiveNames)??new string[0];
   stageMapZones=roots.SelectMany(x=>x.GetComponentsInChildren<MapZone>(true)).ToArray();coordinator.r.stage.mapZoneCount=stageMapZones.Length;
   StartStageMapZoneObservations();
   coordinator.r.stage.activeRoots=roots.Count(x=>x.activeSelf);
   bool previewContract=coordinator.r.stage.previewDisableComponents==previewCount&&coordinator.r.stage.previewsInactive==previewCount&&previewCallbacks.Where(x=>x is DisableOnStart).Select(x=>x.gameObject.name).OrderBy(x=>x).SequenceEqual(previewNames.OrderBy(x=>x));
   coordinator.Check(moon?coordinator.r.stage.behaviours==spec.missionComponents&&previewCallbacks.All(x=>x)&&coordinator.r.stage.activeRoots==0:
    coordinator.stageSourceObjects?roots.Count(x=>new[]{"RoR2Application","SceneInfo","Director","GameManager","Main Camera"}.Contains(x.name)&&x.activeSelf)==0&&coordinator.r.stage.behaviours>previewCount+expectedMapZones+stageZoneNetworkObjects*2&&stageMapZones.Length==expectedMapZones&&previewCallbacks.All(x=>x)&&coordinator.r.stage.previewsInactive==coordinator.r.stage.previewDisableComponents&&coordinator.r.stage.activeRoots>0:
    coordinator.r.stage.behaviours==previewCount+expectedMapZones+stageZoneNetworkObjects*2&&stageMapZones.Length==expectedMapZones&&previewCallbacks.All(x=>x&&(x is DisableOnStart||x is MapZone||((x is NetworkIdentity||x is TeamFilter)&&x.GetComponent<MapZone>())))&&previewContract&&coordinator.r.stage.activeRoots>0,
    "Original stage scene missing scripts, duplicate global owners, or preview contract mismatch");
   Shader terrainShader=Resources.Load<Shader>("StageTerrainPreview"),surfaceShader=Resources.Load<Shader>("StageSurfacePreview");
   coordinator.Check(terrainShader&&terrainShader.isSupported&&surfaceShader&&surfaceShader.isSupported,"Diagnostic stage material shaders unavailable");coordinator.r.stage.terrainTexturesBound=true;
   var replacements=new Dictionary<Material,Material>();var emptyMeshes=new List<string>();var emptyColliders=new List<string>();
   var billboardCopies=new Dictionary<BillboardAsset,BillboardAsset>();
   var beamReplacements=new Dictionary<Material,Material>();
   foreach(var renderer in roots.SelectMany(x=>x.GetComponentsInChildren<Renderer>(true))){
    // Full Moon retains original physics/interaction/presentation layer roles.
    // Renderer layer changes also change any collider on that GameObject.
    if(!moon&&!coordinator.stageSourceObjects&&!renderer.GetComponents<Collider>().Any(x=>x.isTrigger))renderer.gameObject.layer=LayerIndex.world.intVal;var filter=renderer.GetComponent<MeshFilter>();var skinned=renderer as SkinnedMeshRenderer;
    if((filter&&!filter.sharedMesh)||(skinned&&!skinned.sharedMesh)){coordinator.r.stage.missingMeshes++;emptyMeshes.Add(StageObjectPath(renderer.transform));}
    var billboard=renderer as BillboardRenderer;
    if(billboard){coordinator.r.stage.billboards++;if(!billboard.billboard)coordinator.r.stage.missingBillboardAssets++;coordinator.Check(billboard.billboard&&billboard.billboard.material,"Original billboard asset/material missing");}
    // Native BillboardRenderer's source material is on BillboardAsset, while
    // its serialized renderer slot is null. Never mutate the shared source asset.
    var materials=billboard?new[]{billboard.billboard.material}:renderer.sharedMaterials;
    bool pillarBeam=moon&&IsMoonPillarBeam(renderer);var materialCache=pillarBeam?beamReplacements:replacements;
    for(int i=0;i<materials.Length;i++){
     if(!materials[i])continue;Material replacement;
     if(!materialCache.TryGetValue(materials[i],out replacement)){
      bool terrain=materials[i].shader.name.IndexOf("Triplanar",StringComparison.OrdinalIgnoreCase)>=0;
      replacement=new Material(materials[i]);replacement.shader=pillarBeam?Resources.Load<Shader>("MoonPillarBeamPreview"):terrain?terrainShader:surfaceShader;replacement.shaderKeywords=new string[0];
      if(!pillarBeam)AndroidMaterialPresentation.Apply(materials[i],replacement);
      if(pillarBeam)coordinator.Check(replacement.shader&&replacement.shader.isSupported,"Android pillar beam shader unavailable");
      if(terrain){coordinator.r.stage.terrainMaterials++;if(materials[i].name.StartsWith("matGPTerrain",StringComparison.Ordinal)){coordinator.r.stage.terrainTextureMaterials++;coordinator.r.stage.terrainTexturesBound&=replacement.GetTexture("_RedChannelTopTex")&&replacement.GetTexture("_RedChannelSideTex")&&replacement.GetTexture("_GreenChannelTex")&&replacement.GetTexture("_BlueChannelTex");}}else coordinator.r.stage.surfaceMaterials++;
      materialCache.Add(materials[i],replacement);coordinator.stageGeometryMaterials.Add(replacement);
     }
     materials[i]=replacement;
    }
    if(billboard){BillboardAsset owned;
     if(!billboardCopies.TryGetValue(billboard.billboard,out owned)){owned=Instantiate(billboard.billboard);owned.material=materials[0];billboardCopies.Add(billboard.billboard,owned);stageGeometryBillboards.Add(owned);}
     billboard.billboard=owned;
    }else renderer.sharedMaterials=materials;
    coordinator.r.stage.renderers++;
   }
   coordinator.r.stage.emptyLODRendererSlots=roots.SelectMany(x=>x.GetComponentsInChildren<LODGroup>(true)).Sum(x=>x.GetLODs().Sum(lod=>lod.renderers.Count(renderer=>!renderer)));
   // Original Frozen/Sky scenes contain explicit empty LOD slots. Conversion
   // separately verifies that every nonempty native renderer reference survives.
   if(coordinator.r.stage.billboards>0)coordinator.Check(coordinator.r.stage.missingBillboardAssets==0,"Recovered billboard asset missing");
   foreach(var collider in roots.SelectMany(x=>x.GetComponentsInChildren<Collider>(true))){
    // A non-trigger ambient/post-process volume is not world geometry. Promoting
    // Moon's source layer20 sphere ejects the landing body through KCC penetration.
    if(!moon&&!coordinator.stageSourceObjects&&!collider.isTrigger)collider.gameObject.layer=LayerIndex.world.intVal;if(collider.isTrigger)continue;coordinator.r.stage.colliders++;
    if(collider.gameObject.layer==LayerIndex.world.intVal)coordinator.r.stage.worldColliders++;else coordinator.r.stage.nonWorldColliders++;
    var mesh=collider as MeshCollider;if(mesh){coordinator.r.stage.meshColliders++;if(!mesh.sharedMesh){coordinator.r.stage.missingColliderMeshes++;emptyColliders.Add(StageObjectPath(mesh.transform));}}
   }
   coordinator.r.stage.emptyMeshPaths=emptyMeshes.ToArray();coordinator.r.stage.emptyColliderPaths=emptyColliders.ToArray();
   var expectedMeshes=spec==null?new string[0]:spec.emptyMeshPaths??new string[0];var expectedColliders=spec==null?new string[0]:spec.emptyColliderPaths??new string[0];
   coordinator.Check(coordinator.r.stage.renderers>100&&coordinator.r.stage.meshColliders>50&&emptyMeshes.OrderBy(x=>x).SequenceEqual(expectedMeshes.OrderBy(x=>x))&&emptyColliders.OrderBy(x=>x).SequenceEqual(expectedColliders.OrderBy(x=>x)),"Recovered stage mesh/collision closure differs from measured source-empty objects");
   coordinator.Check((spec!=null||coordinator.r.stage.terrainTextureMaterials>=2)&&coordinator.r.stage.terrainTexturesBound,"Original terrain channel textures did not bind to the owned preview material");
   if(moon){coordinator.Check(SceneManager.SetActiveScene(coordinator.stageGeometryScene),"Moon active scene context missing");coordinator.ActivateMoonSource(spec);}
   Physics.SyncTransforms();
   Vector3 entryOrigin=Vector3.zero;
   if(moon){var locator=SceneInfo.instance.GetComponent<ChildLocator>();var origin=locator?locator.FindChild("PlayerSpawnOrigin"):null;coordinator.Check(origin&&origin.gameObject.scene==coordinator.stageGeometryScene,"Original Moon player spawn origin missing");entryOrigin=origin.position;coordinator.r.stage.entryOrigin=entryOrigin;}
   foreach(var marker in transforms.Where(x=>!moon&&x.name=="SurvivorPodSpawnPoint"&&x.gameObject.activeInHierarchy)){
    RaycastHit hit;if(!Physics.Raycast(marker.position+Vector3.up*30,Vector3.down,out hit,100,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||hit.normal.y<.9f)continue;
    if(hit.collider.gameObject.scene!=coordinator.stageGeometryScene)continue;coordinator.r.stage.groundColliderPath=StageObjectPath(hit.collider.transform);coordinator.r.stage.groundColliderScene=hit.collider.gameObject.scene.name;coordinator.r.stage.spawnMarker=marker.name;coordinator.r.stage.groundHit=true;coordinator.r.stage.groundPosition=hit.point;coordinator.r.stage.groundNormal=hit.normal;coordinator.r.stage.spawnPosition=hit.point+Vector3.up*2.5f;break;
   }
   if(!coordinator.r.stage.groundHit&&spec!=null){
    var graph=coordinator.artifactBundle.LoadAsset<RoR2.Navigation.NodeGraph>(spec.groundGraph);coordinator.Check(graph&&graph.GetNodeCount()>0,"Original next-stage ground graph unavailable");
    var candidates=new List<Vector3>();for(int i=0;i<graph.GetNodeCount();i++){Vector3 point;if(graph.GetNodePosition(new RoR2.Navigation.NodeGraph.NodeIndex(i),out point))candidates.Add(point);}
    foreach(var point in candidates.OrderBy(x=>moon?(x-entryOrigin).sqrMagnitude:x.x*x.x+x.z*x.z)){
     RaycastHit hit;if(!Physics.Raycast(point+Vector3.up*8,Vector3.down,out hit,18,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||hit.normal.y<.98f)continue;
     if(hit.collider.gameObject.scene!=coordinator.stageGeometryScene)continue;
     int clear=0;foreach(var offset in new[]{Vector3.right*5,Vector3.left*5,Vector3.forward*6,Vector3.back*3}){RaycastHit nearby;if(Physics.Raycast(hit.point+offset+Vector3.up*8,Vector3.down,out nearby,18,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)&&nearby.collider.gameObject.scene==coordinator.stageGeometryScene&&nearby.normal.y>.95f&&Mathf.Abs(nearby.point.y-hit.point.y)<1)clear++;}
     if(clear<4)continue;coordinator.r.stage.groundColliderPath=StageObjectPath(hit.collider.transform);coordinator.r.stage.groundColliderScene=hit.collider.gameObject.scene.name;coordinator.r.stage.spawnMarker=moon?"Original PlayerSpawnOrigin / ground graph / measured Android entry":"Original ground graph / measured Android entry";coordinator.r.stage.groundHit=true;coordinator.r.stage.groundPosition=hit.point;coordinator.r.stage.groundNormal=hit.normal;coordinator.r.stage.spawnPosition=hit.point+Vector3.up*2.5f;break;
    }
   }
   coordinator.Check(coordinator.r.stage.groundHit,"No measured walkable original stage entry");coordinator.Save();
  }
  public void EnableStageMapZones(){
   if(stageMapZones.Length==0)return;
   if(coordinator.r.stage.mapZonesReady)return;
   if(coordinator.stageGeometryScene.name=="goldshores"){
    // The exported Gold Shores out-of-bounds box starts disabled, but its
    // original network identity and TriggerExit teleport are required by this
    // additive scene lifecycle. Activate only that measured source object;
    // no position or teleport behavior is replaced.
    coordinator.Check(stageMapZones.Length==1&&stageZoneNetworkObjects==1&&stageZoneActiveNames.Length==0,"Gold Shores source out-of-bounds contract changed");
    var zone=stageMapZones[0];var box=zone.GetComponent<BoxCollider>();var identity=zone.GetComponent<NetworkIdentity>();
    coordinator.Check(zone.name=="HOLDER: Map Zone"&&!zone.gameObject.activeSelf&&zone.triggerType==MapZone.TriggerType.TriggerExit&&zone.zoneType==MapZone.ZoneType.OutOfBounds&&box&&box.isTrigger&&identity&&!identity.sceneId.IsEmpty(),"Gold Shores original out-of-bounds volume differs");
    stageZoneActiveNames=new[]{zone.name};
   }
   if(!stageMoonVolumes){
    foreach(var zone in stageMapZones)if(stageZoneActiveNames.Contains(zone.name))zone.gameObject.SetActive(true);
    if(stageZoneNetworkObjects>0){
     var identities=stageMapZones.Select(x=>x.GetComponent<NetworkIdentity>()).Where(x=>x).ToArray();
     coordinator.Check(identities.Length==stageZoneNetworkObjects&&identities.All(x=>x.gameObject.scene==coordinator.stageGeometryScene&&x.GetComponent<MapZone>()),"Unowned stage out-of-bounds scene identities");
     coordinator.r.stage.mapZoneIdentityComponents=identities.Length;coordinator.r.stage.mapZoneEmptySceneIds=identities.Count(x=>x.sceneId.IsEmpty());
     // SpawnObjects enables every scene identity. Preserve source-disabled volumes
     // when their mission/controller lifecycle is unavailable in this composition.
     int sourceActive=identities.Count(x=>stageZoneActiveNames.Contains(x.name));
     coordinator.Check(sourceActive==0||sourceActive==identities.Length,"Mixed source map-zone activation requires its original lifecycle");
     if(sourceActive>0){
      if(coordinator.stageGeometryScene.name=="goldshores"){
       // The source scene also contains unrelated network identities. A global
       // SpawnObjects would activate their lifecycles before the Gold mission.
       coordinator.Check(identities.Length==1&&!identities[0].isServer,"Gold Shores map-zone identity was already spawned");
       NetworkServer.Spawn(identities[0].gameObject);
       coordinator.Check(identities[0].isServer&&identities[0].netId.Value!=0,"Original Gold Shores out-of-bounds identity did not spawn");
      }else{
       var spawnable=Resources.FindObjectsOfTypeAll<NetworkIdentity>().Where(x=>x.gameObject.hideFlags!=HideFlags.NotEditable&&x.gameObject.hideFlags!=HideFlags.HideAndDontSave&&!x.sceneId.IsEmpty()).ToArray();
       coordinator.Check(spawnable.Length==identities.Length&&spawnable.All(x=>identities.Contains(x)),"Unowned spawnable stage identity or missing native scene ID");
       coordinator.Check(NetworkServer.SpawnObjects(),"Original out-of-bounds server activation failed");
      }
      coordinator.r.stage.mapZoneNetworkObjects=identities.Length;
     }else {coordinator.Check(identities.All(x=>!x.gameObject.activeInHierarchy),"Source-disabled map volume unexpectedly active");coordinator.r.stage.mapZoneNetworkObjects=0;}
    }
   }
   foreach(var zone in stageMapZones){var collider=zone.GetComponent<Collider>();coordinator.Check(collider&&collider.isTrigger&&zone.gameObject.layer==15,"Original stage MapZone collider/layer differs");coordinator.Check(collider.enabled,"Original MapZone collider must remain source-enabled");}
   Physics.SyncTransforms();coordinator.r.stage.mapZonesReady=true;coordinator.Save();
  }
  public void PauseStageMapZones(){foreach(var zone in stageMapZones)if(zone)zone.gameObject.SetActive(false);if(coordinator.r.stage!=null)coordinator.r.stage.mapZonesReady=false;}
  public bool InsideSourceStageBounds(Vector3 point){
   // Original spawn bounds allow alternative exit volumes. Enter volumes remain
   // unsafe diagnostic destinations/targets; actual callbacks own their effects.
   return Util.IsPositionWithinMapBounds(point)&&stageMapZones.Where(x=>x&&x.gameObject.activeInHierarchy&&x.GetComponent<Collider>().enabled&&x.zoneType==MapZone.ZoneType.OutOfBounds&&x.triggerType==MapZone.TriggerType.TriggerEnter).All(x=>!x.IsPointInsideMapZone(point));
  }
  public void StartStageMapZoneObservations(){
   if(ownsStageMapZoneObservations)return;
   stageZoneEntered=(body,zone)=>{if(zone&&zone.gameObject.scene==coordinator.stageGeometryScene){coordinator.r.stage.mapZoneEntries++;coordinator.r.stage.lastMapZone=zone.name+"|enter";}};
   stageZoneLeft=(body,zone)=>{if(zone&&zone.gameObject.scene==coordinator.stageGeometryScene){coordinator.r.stage.mapZoneExits++;coordinator.r.stage.lastMapZone=zone.name+"|exit";}};
   stageZoneTeleported=body=>{if(coordinator.r.stage!=null&&coordinator.r.stage.mapZonesReady)coordinator.r.stage.mapZoneTeleports++;};
   MapZone.OnEnterMapZone+=stageZoneEntered;MapZone.OnLeaveMapZone+=stageZoneLeft;MapZone.onBodyTeleportGlobal+=stageZoneTeleported;ownsStageMapZoneObservations=true;
  }
  public void StopStageMapZoneObservations(){if(!ownsStageMapZoneObservations)return;MapZone.OnEnterMapZone-=stageZoneEntered;MapZone.OnLeaveMapZone-=stageZoneLeft;MapZone.onBodyTeleportGlobal-=stageZoneTeleported;ownsStageMapZoneObservations=false;stageMapZones=new MapZone[0];}
  public static string StageObjectPath(Transform target){var path=target.name;while(target.parent){target=target.parent;path=target.name+"/"+path;}return path;}
  public IEnumerator CleanupStageGeometry(){PauseStageMapZones();StopStageMapZoneObservations();
   if(coordinator.stageGeometryScene.IsValid()&&coordinator.stageGeometryScene.isLoaded)yield return SceneManager.UnloadSceneAsync(coordinator.stageGeometryScene);
   foreach(var billboard in stageGeometryBillboards)if(billboard)Destroy(billboard);stageGeometryBillboards.Clear();
   foreach(var material in coordinator.stageGeometryMaterials)if(material)Destroy(material);coordinator.stageGeometryMaterials.Clear();
   if(coordinator.stageGeometryBundle){coordinator.stageGeometryBundle.Unload(true);coordinator.stageGeometryBundle=null;}
   if(coordinator.r.stage!=null){coordinator.r.stage.cleaned=!coordinator.stageGeometryScene.isLoaded;coordinator.Check(coordinator.r.stage.cleaned,"Owned stage geometry cleanup incomplete");coordinator.Save();}
  }
  public void Dispose(){}
 }
}
