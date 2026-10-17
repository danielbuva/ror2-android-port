// Subsystem: stage transport (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareStageGeometry, LoadStageGeometry; teardown DeactivateSourceGameManager, DeactivateSourceSceneInfo, CleanupStageGeometry.
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
 readonly List<BillboardAsset> stageGeometryBillboards=new List<BillboardAsset>();
 bool stageMoonVolumes,stageSourceObjects;GameObject sourceSceneInfoRoot,sourceGameManagerRoot;int stageZoneNetworkObjects;string[] stageZoneActiveNames,stageSourceNames=new string[0];
 void ActivateSourceGameManager(){
  var previous=eventHost?eventHost.GetComponent<GlobalEventManager>():null;
  Check(stageSourceObjects&&!sourceGameManagerRoot&&previous&&GlobalEventManager.instance==previous,"Original source event owner requires the existing local event context");
  var roots=stageGeometryScene.GetRootGameObjects().Where(x=>x.name=="GameManager").ToArray();
  Check(roots.Length==1&&!roots[0].activeSelf,"Original source GameManager root absent or already active");
  var root=roots[0];var manager=root.GetComponent<GlobalEventManager>();
  Check(manager&&root.GetComponents<MonoBehaviour>().Length==1,"Original source GameManager component contract changed");
  Call(previous,"OnDisable");
  try{root.SetActive(true);Check(GlobalEventManager.instance==manager,"Original source GlobalEventManager did not adopt the singleton");sourceGameManagerRoot=root;}
  catch{root.SetActive(false);Call(previous,"OnEnable");throw;}
 }
 void DeactivateSourceGameManager(){
  if(!sourceGameManagerRoot)return;
  sourceGameManagerRoot.SetActive(false);sourceGameManagerRoot=null;
  Check(!GlobalEventManager.instance,"Original source event owner survived stage teardown");
  var previous=eventHost.GetComponent<GlobalEventManager>();Call(previous,"OnEnable");
  Check(GlobalEventManager.instance==previous,"Local event owner was not restored after source stage");
 }
 SceneInfo ActivateSourceSceneInfo(){
  Check(stageSourceObjects&&Run.instance&&NetworkServer.active&&!SceneInfo.instance&&!ClassicStageInfo.instance&&!sourceSceneInfoRoot,"Original source context requires an active owned run and no duplicate context");
  var roots=stageGeometryScene.GetRootGameObjects().Where(x=>x.name=="SceneInfo").ToArray();Check(roots.Length==1&&!roots[0].activeSelf,"Original source SceneInfo root absent or already activated");
  var root=roots[0];var info=root.GetComponent<SceneInfo>();var population=root.GetComponent<ClassicStageInfo>();
  Check(info&&population&&root.GetComponents<MonoBehaviour>().All(x=>x&&!x.GetType().FullName.StartsWith("Ak")&&x.GetType().Name!="RTPCController"),"Original source scene context contains missing/native-audio components");
  ActivateSourceGameManager();
  try{sourceSceneInfoRoot=root;root.SetActive(true);Check(SceneInfo.instance==info&&ClassicStageInfo.instance==population,"Original source scene owner did not initialize");return info;}
  catch{root.SetActive(false);sourceSceneInfoRoot=null;DeactivateSourceGameManager();throw;}
 }
 void DeactivateSourceSceneInfo(){if(sourceSceneInfoRoot){sourceSceneInfoRoot.SetActive(false);sourceSceneInfoRoot=null;}Check(!SceneInfo.instance&&!ClassicStageInfo.instance,"Original source scene context survived deactivation");DeactivateSourceGameManager();}
 MapZone[] stageMapZones=new MapZone[0];Action<CharacterBody,MapZone> stageZoneEntered,stageZoneLeft;Action<CharacterBody> stageZoneTeleported;bool ownsStageMapZoneObservations;
 IntegratedStageSpec firstStageSpec;string firstStageName;bool firstStagePolicyConsumed;float firstStageSelectionValue;
 IEnumerator PrepareStageGeometry(Result cfg){
  firstStageSpec=null;firstStageName="golemplains";firstStagePolicyConsumed=false;stageSourceNames=r.originalStageSceneNames??cfg.originalStageSceneNames??new string[0];
  if(cfg.integratedWorld&&cfg.teleporterLoop&&r.freePlay){
   // Run.Start is unavailable behind the stock platform boundary. Use its shipped
   // scene group, weighted selector and RNG before the body needs stage geometry.
   var group=WholeCatalogComposed.LoadOwnedContent<SceneCollection>("Assets/WholeGame/RoR2/Base/SceneGroups/sgStage1.asset");
   Check(group&&group.name=="sgStage1","Original starting scene group unavailable");
   var choices=new WeightedSelection<SceneDef>();group.AddToWeightedSelection(choices,scene=>scene&&!scene.requiredExpansion);
   var names=choices.choices.Take(choices.Count).Select(choice=>choice.value.cachedName).OrderBy(name=>name).ToArray();
   Check(names.SequenceEqual(new[]{"blackbeach","blackbeach2","golemplains","golemplains2","lakes"})&&Mathf.Abs(choices.GetTotalWeight()-3f)<.001f,"Original eligible starting scenes or weights changed");
   var runRng=new Xoroshiro128Plus(SelectOwnedRunSeed(cfg));var stageRng=new Xoroshiro128Plus(runRng.nextUlong);
   firstStageSelectionValue=stageRng.nextNormalizedFloat;var selected=choices.Evaluate(firstStageSelectionValue);
   Check(selected&&selected.stageOrder==1,"Original starting scene selection failed");firstStageName=selected.cachedName;firstStagePolicyConsumed=true;
   if(firstStageName!="golemplains"){
    firstStageSpec=cfg.integratedStages.SingleOrDefault(stage=>stage.name==firstStageName);
    Check(firstStageSpec!=null&&!firstStageSpec.moonMission,"Original starting scene has no converted Android content: "+firstStageName);
   }
  }
  var load=firstStageSpec==null?LoadStageGeometry("golemplains-spine-lab",cfg.stagePreviewCallbacks,null,cfg.stageMapZoneCount,cfg.stageMapZoneActiveNames,cfg.stagePreviewNames):LoadStageGeometry(firstStageSpec.bundle,firstStageSpec.previewCallbacks,firstStageSpec);
  while(load.MoveNext())yield return load.Current;
  Check(stageGeometryScene.name==firstStageName,"Selected original starting scene differs from loaded Android geometry");
 }
 IEnumerator LoadStageGeometry(string bundleName,int previewCount,IntegratedStageSpec spec,int initialMapZones=0,string[] initialActiveNames=null,string[] initialPreviewNames=null){
  r.stage=new StageGeometryReport();r.phase="stage-geometry-load";Save();
  string stageName=bundleName.Replace("-spine-lab","");
  stageSourceObjects=stageSourceNames.Contains(stageName);
  if(stageSourceObjects){Check(bundleName==stageName+"-spine-lab","Unreviewed original stage-scene switch");bundleName=stageName+"-source-lab";}
  r.stage.originalStageObjects=stageSourceObjects;
  stageGeometryBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload",bundleName));
  Check(stageGeometryBundle,"Recovered stage geometry bundle missing");var scenes=stageGeometryBundle.GetAllScenePaths();Check(scenes.Length==1,"Expected one recovered stage geometry scene");
  yield return SceneManager.LoadSceneAsync(scenes[0],LoadSceneMode.Additive);stageGeometryScene=SceneManager.GetSceneByPath(scenes[0]);
  r.stage.loaded=stageGeometryScene.IsValid()&&stageGeometryScene.isLoaded;r.stage.scene=stageGeometryScene.name;Check(r.stage.loaded,"Stage geometry did not load");
  yield return null; // Allow original scene preview Start callbacks; no manual deactivation.
  var roots=stageGeometryScene.GetRootGameObjects();stageStaticRoots=new HashSet<GameObject>(roots);var transforms=roots.SelectMany(x=>x.GetComponentsInChildren<Transform>(true)).ToArray();
  r.stage.objects=transforms.Length;r.stage.behaviours=roots.Sum(x=>x.GetComponentsInChildren<MonoBehaviour>(true).Length);
  if(stageSourceObjects){
   var rocks=roots.SelectMany(x=>x.GetComponentsInChildren<MaulingRockZoneManager>(true)).ToArray();
   r.stage.sourceRockZones=rocks.Length;
   foreach(var rock in rocks){
    if(rock.maulingRockProjectilePrefabs!=null){r.stage.sourceRockPrefabSlots+=rock.maulingRockProjectilePrefabs.Count;
     foreach(var prefab in rock.maulingRockProjectilePrefabs)if(prefab){r.stage.sourceRockPrefabsResolved++;if(prefab.GetComponent<MaulingRock>())r.stage.sourceRockComponentsResolved++;}}
    if(rock.startZonePoint1&&rock.startZonePoint2&&rock.endZonePoint1&&rock.endZonePoint2)r.stage.sourceRockZonePointsResolved++;
   }
   var dust=roots.SelectMany(x=>x.GetComponentsInChildren<RoR2.DustStreakManager>(true)).ToArray();r.stage.sourceDustManagers=dust.Length;
   foreach(var manager in dust){if(manager.dustStreakPrefab)r.stage.sourceDustPrefabsResolved++;if(manager.dustStreakLocations!=null)r.stage.sourceDustLocationsResolved+=manager.dustStreakLocations.Count(x=>x);}
  }
  var previewCallbacks=roots.SelectMany(x=>x.GetComponentsInChildren<MonoBehaviour>(true)).ToArray();
  // Shipped inactive variant parents legitimately prevent Start from running.
  r.stage.previewDisableComponents=previewCallbacks.Count(x=>x&&x.GetType()==typeof(DisableOnStart));r.stage.previewsInactive=previewCallbacks.Count(x=>x&&x is DisableOnStart&&!x.gameObject.activeInHierarchy);r.stage.previewsInactiveByParent=previewCallbacks.Count(x=>x&&x is DisableOnStart&&x.gameObject.activeSelf&&!x.gameObject.activeInHierarchy);
  var previewNames=spec!=null&&spec.previewNames!=null?spec.previewNames:initialPreviewNames??Enumerable.Repeat("EscapePodMesh",previewCount).ToArray();
  bool moon=spec!=null&&spec.moonMission;int expectedMapZones=spec==null?initialMapZones:spec.mapZoneCount;
  stageMoonVolumes=moon;stageZoneNetworkObjects=spec==null?0:spec.mapZoneNetworkObjects;stageZoneActiveNames=(spec==null?initialActiveNames:spec.mapZoneActiveNames)??new string[0];
  stageMapZones=roots.SelectMany(x=>x.GetComponentsInChildren<MapZone>(true)).ToArray();r.stage.mapZoneCount=stageMapZones.Length;
  StartStageMapZoneObservations();
  r.stage.activeRoots=roots.Count(x=>x.activeSelf);
  bool previewContract=r.stage.previewDisableComponents==previewCount&&r.stage.previewsInactive==previewCount&&previewCallbacks.Where(x=>x is DisableOnStart).Select(x=>x.gameObject.name).OrderBy(x=>x).SequenceEqual(previewNames.OrderBy(x=>x));
  Check(moon?r.stage.behaviours==spec.missionComponents&&previewCallbacks.All(x=>x)&&r.stage.activeRoots==0:
   stageSourceObjects?roots.Count(x=>new[]{"RoR2Application","SceneInfo","Director","GameManager","Main Camera"}.Contains(x.name)&&x.activeSelf)==0&&r.stage.behaviours>previewCount+expectedMapZones+stageZoneNetworkObjects*2&&stageMapZones.Length==expectedMapZones&&previewCallbacks.All(x=>x)&&r.stage.previewsInactive==r.stage.previewDisableComponents&&r.stage.activeRoots>0:
   r.stage.behaviours==previewCount+expectedMapZones+stageZoneNetworkObjects*2&&stageMapZones.Length==expectedMapZones&&previewCallbacks.All(x=>x&&(x is DisableOnStart||x is MapZone||((x is NetworkIdentity||x is TeamFilter)&&x.GetComponent<MapZone>())))&&previewContract&&r.stage.activeRoots>0,
   "Original stage scene missing scripts, duplicate global owners, or preview contract mismatch");
  Shader terrainShader=Resources.Load<Shader>("StageTerrainPreview"),surfaceShader=Resources.Load<Shader>("StageSurfacePreview");
  Check(terrainShader&&terrainShader.isSupported&&surfaceShader&&surfaceShader.isSupported,"Diagnostic stage material shaders unavailable");r.stage.terrainTexturesBound=true;
  var replacements=new Dictionary<Material,Material>();var emptyMeshes=new List<string>();var emptyColliders=new List<string>();
  var billboardCopies=new Dictionary<BillboardAsset,BillboardAsset>();
  var beamReplacements=new Dictionary<Material,Material>();
  foreach(var renderer in roots.SelectMany(x=>x.GetComponentsInChildren<Renderer>(true))){
   // Full Moon retains original physics/interaction/presentation layer roles.
   // Renderer layer changes also change any collider on that GameObject.
   if(!moon&&!stageSourceObjects&&!renderer.GetComponents<Collider>().Any(x=>x.isTrigger))renderer.gameObject.layer=LayerIndex.world.intVal;var filter=renderer.GetComponent<MeshFilter>();var skinned=renderer as SkinnedMeshRenderer;
   if((filter&&!filter.sharedMesh)||(skinned&&!skinned.sharedMesh)){r.stage.missingMeshes++;emptyMeshes.Add(StageObjectPath(renderer.transform));}
   var billboard=renderer as BillboardRenderer;
   if(billboard){r.stage.billboards++;if(!billboard.billboard)r.stage.missingBillboardAssets++;Check(billboard.billboard&&billboard.billboard.material,"Original billboard asset/material missing");}
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
     if(pillarBeam)Check(replacement.shader&&replacement.shader.isSupported,"Android pillar beam shader unavailable");
     if(terrain){r.stage.terrainMaterials++;if(materials[i].name.StartsWith("matGPTerrain",StringComparison.Ordinal)){r.stage.terrainTextureMaterials++;r.stage.terrainTexturesBound&=replacement.GetTexture("_RedChannelTopTex")&&replacement.GetTexture("_RedChannelSideTex")&&replacement.GetTexture("_GreenChannelTex")&&replacement.GetTexture("_BlueChannelTex");}}else r.stage.surfaceMaterials++;
     materialCache.Add(materials[i],replacement);stageGeometryMaterials.Add(replacement);
    }
    materials[i]=replacement;
   }
   if(billboard){BillboardAsset owned;
    if(!billboardCopies.TryGetValue(billboard.billboard,out owned)){owned=Instantiate(billboard.billboard);owned.material=materials[0];billboardCopies.Add(billboard.billboard,owned);stageGeometryBillboards.Add(owned);}
    billboard.billboard=owned;
   }else renderer.sharedMaterials=materials;
   r.stage.renderers++;
  }
  r.stage.emptyLODRendererSlots=roots.SelectMany(x=>x.GetComponentsInChildren<LODGroup>(true)).Sum(x=>x.GetLODs().Sum(lod=>lod.renderers.Count(renderer=>!renderer)));
  // Original Frozen/Sky scenes contain explicit empty LOD slots. Conversion
  // separately verifies that every nonempty native renderer reference survives.
  if(r.stage.billboards>0)Check(r.stage.missingBillboardAssets==0,"Recovered billboard asset missing");
  foreach(var collider in roots.SelectMany(x=>x.GetComponentsInChildren<Collider>(true))){
   // A non-trigger ambient/post-process volume is not world geometry. Promoting
   // Moon's source layer20 sphere ejects the landing body through KCC penetration.
   if(!moon&&!stageSourceObjects&&!collider.isTrigger)collider.gameObject.layer=LayerIndex.world.intVal;if(collider.isTrigger)continue;r.stage.colliders++;
   if(collider.gameObject.layer==LayerIndex.world.intVal)r.stage.worldColliders++;else r.stage.nonWorldColliders++;
   var mesh=collider as MeshCollider;if(mesh){r.stage.meshColliders++;if(!mesh.sharedMesh){r.stage.missingColliderMeshes++;emptyColliders.Add(StageObjectPath(mesh.transform));}}
  }
  r.stage.emptyMeshPaths=emptyMeshes.ToArray();r.stage.emptyColliderPaths=emptyColliders.ToArray();
  var expectedMeshes=spec==null?new string[0]:spec.emptyMeshPaths??new string[0];var expectedColliders=spec==null?new string[0]:spec.emptyColliderPaths??new string[0];
  Check(r.stage.renderers>100&&r.stage.meshColliders>50&&emptyMeshes.OrderBy(x=>x).SequenceEqual(expectedMeshes.OrderBy(x=>x))&&emptyColliders.OrderBy(x=>x).SequenceEqual(expectedColliders.OrderBy(x=>x)),"Recovered stage mesh/collision closure differs from measured source-empty objects");
  Check((spec!=null||r.stage.terrainTextureMaterials>=2)&&r.stage.terrainTexturesBound,"Original terrain channel textures did not bind to the owned preview material");
  if(moon){Check(SceneManager.SetActiveScene(stageGeometryScene),"Moon active scene context missing");ActivateMoonSource(spec);}
  Physics.SyncTransforms();
  Vector3 entryOrigin=Vector3.zero;
  if(moon){var locator=SceneInfo.instance.GetComponent<ChildLocator>();var origin=locator?locator.FindChild("PlayerSpawnOrigin"):null;Check(origin&&origin.gameObject.scene==stageGeometryScene,"Original Moon player spawn origin missing");entryOrigin=origin.position;r.stage.entryOrigin=entryOrigin;}
  foreach(var marker in transforms.Where(x=>!moon&&x.name=="SurvivorPodSpawnPoint"&&x.gameObject.activeInHierarchy)){
   RaycastHit hit;if(!Physics.Raycast(marker.position+Vector3.up*30,Vector3.down,out hit,100,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||hit.normal.y<.9f)continue;
   if(hit.collider.gameObject.scene!=stageGeometryScene)continue;r.stage.groundColliderPath=StageObjectPath(hit.collider.transform);r.stage.groundColliderScene=hit.collider.gameObject.scene.name;r.stage.spawnMarker=marker.name;r.stage.groundHit=true;r.stage.groundPosition=hit.point;r.stage.groundNormal=hit.normal;r.stage.spawnPosition=hit.point+Vector3.up*2.5f;break;
  }
  if(!r.stage.groundHit&&spec!=null){
   var graph=artifactBundle.LoadAsset<RoR2.Navigation.NodeGraph>(spec.groundGraph);Check(graph&&graph.GetNodeCount()>0,"Original next-stage ground graph unavailable");
   var candidates=new List<Vector3>();for(int i=0;i<graph.GetNodeCount();i++){Vector3 point;if(graph.GetNodePosition(new RoR2.Navigation.NodeGraph.NodeIndex(i),out point))candidates.Add(point);}
   foreach(var point in candidates.OrderBy(x=>moon?(x-entryOrigin).sqrMagnitude:x.x*x.x+x.z*x.z)){
    RaycastHit hit;if(!Physics.Raycast(point+Vector3.up*8,Vector3.down,out hit,18,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||hit.normal.y<.98f)continue;
    if(hit.collider.gameObject.scene!=stageGeometryScene)continue;
    int clear=0;foreach(var offset in new[]{Vector3.right*5,Vector3.left*5,Vector3.forward*6,Vector3.back*3}){RaycastHit nearby;if(Physics.Raycast(hit.point+offset+Vector3.up*8,Vector3.down,out nearby,18,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)&&nearby.collider.gameObject.scene==stageGeometryScene&&nearby.normal.y>.95f&&Mathf.Abs(nearby.point.y-hit.point.y)<1)clear++;}
    if(clear<4)continue;r.stage.groundColliderPath=StageObjectPath(hit.collider.transform);r.stage.groundColliderScene=hit.collider.gameObject.scene.name;r.stage.spawnMarker=moon?"Original PlayerSpawnOrigin / ground graph / measured Android entry":"Original ground graph / measured Android entry";r.stage.groundHit=true;r.stage.groundPosition=hit.point;r.stage.groundNormal=hit.normal;r.stage.spawnPosition=hit.point+Vector3.up*2.5f;break;
   }
  }
  Check(r.stage.groundHit,"No measured walkable original stage entry");Save();
 }
 void EnableStageMapZones(){
  if(stageMapZones.Length==0)return;
  if(r.stage.mapZonesReady)return;
  if(stageGeometryScene.name=="goldshores"){
   // The exported Gold Shores out-of-bounds box starts disabled, but its
   // original network identity and TriggerExit teleport are required by this
   // additive scene lifecycle. Activate only that measured source object;
   // no position or teleport behavior is replaced.
   Check(stageMapZones.Length==1&&stageZoneNetworkObjects==1&&stageZoneActiveNames.Length==0,"Gold Shores source out-of-bounds contract changed");
   var zone=stageMapZones[0];var box=zone.GetComponent<BoxCollider>();var identity=zone.GetComponent<NetworkIdentity>();
   Check(zone.name=="HOLDER: Map Zone"&&!zone.gameObject.activeSelf&&zone.triggerType==MapZone.TriggerType.TriggerExit&&zone.zoneType==MapZone.ZoneType.OutOfBounds&&box&&box.isTrigger&&identity&&!identity.sceneId.IsEmpty(),"Gold Shores original out-of-bounds volume differs");
   stageZoneActiveNames=new[]{zone.name};
  }
  if(!stageMoonVolumes){
   foreach(var zone in stageMapZones)if(stageZoneActiveNames.Contains(zone.name))zone.gameObject.SetActive(true);
   if(stageZoneNetworkObjects>0){
    var identities=stageMapZones.Select(x=>x.GetComponent<NetworkIdentity>()).Where(x=>x).ToArray();
    Check(identities.Length==stageZoneNetworkObjects&&identities.All(x=>x.gameObject.scene==stageGeometryScene&&x.GetComponent<MapZone>()),"Unowned stage out-of-bounds scene identities");
    r.stage.mapZoneIdentityComponents=identities.Length;r.stage.mapZoneEmptySceneIds=identities.Count(x=>x.sceneId.IsEmpty());
    // SpawnObjects enables every scene identity. Preserve source-disabled volumes
    // when their mission/controller lifecycle is unavailable in this composition.
    int sourceActive=identities.Count(x=>stageZoneActiveNames.Contains(x.name));
    Check(sourceActive==0||sourceActive==identities.Length,"Mixed source map-zone activation requires its original lifecycle");
    if(sourceActive>0){
     if(stageGeometryScene.name=="goldshores"){
      // The source scene also contains unrelated network identities. A global
      // SpawnObjects would activate their lifecycles before the Gold mission.
      Check(identities.Length==1&&!identities[0].isServer,"Gold Shores map-zone identity was already spawned");
      NetworkServer.Spawn(identities[0].gameObject);
      Check(identities[0].isServer&&identities[0].netId.Value!=0,"Original Gold Shores out-of-bounds identity did not spawn");
     }else{
      var spawnable=Resources.FindObjectsOfTypeAll<NetworkIdentity>().Where(x=>x.gameObject.hideFlags!=HideFlags.NotEditable&&x.gameObject.hideFlags!=HideFlags.HideAndDontSave&&!x.sceneId.IsEmpty()).ToArray();
      Check(spawnable.Length==identities.Length&&spawnable.All(x=>identities.Contains(x)),"Unowned spawnable stage identity or missing native scene ID");
      Check(NetworkServer.SpawnObjects(),"Original out-of-bounds server activation failed");
     }
     r.stage.mapZoneNetworkObjects=identities.Length;
    }else {Check(identities.All(x=>!x.gameObject.activeInHierarchy),"Source-disabled map volume unexpectedly active");r.stage.mapZoneNetworkObjects=0;}
   }
  }
  foreach(var zone in stageMapZones){var collider=zone.GetComponent<Collider>();Check(collider&&collider.isTrigger&&zone.gameObject.layer==15,"Original stage MapZone collider/layer differs");Check(collider.enabled,"Original MapZone collider must remain source-enabled");}
  Physics.SyncTransforms();r.stage.mapZonesReady=true;Save();
 }
 void PauseStageMapZones(){foreach(var zone in stageMapZones)if(zone)zone.gameObject.SetActive(false);if(r.stage!=null)r.stage.mapZonesReady=false;}
 bool InsideSourceStageBounds(Vector3 point){
  // Original spawn bounds allow alternative exit volumes. Enter volumes remain
  // unsafe diagnostic destinations/targets; actual callbacks own their effects.
  return Util.IsPositionWithinMapBounds(point)&&stageMapZones.Where(x=>x&&x.gameObject.activeInHierarchy&&x.GetComponent<Collider>().enabled&&x.zoneType==MapZone.ZoneType.OutOfBounds&&x.triggerType==MapZone.TriggerType.TriggerEnter).All(x=>!x.IsPointInsideMapZone(point));
 }
 void StartStageMapZoneObservations(){
  if(ownsStageMapZoneObservations)return;
  stageZoneEntered=(body,zone)=>{if(zone&&zone.gameObject.scene==stageGeometryScene){r.stage.mapZoneEntries++;r.stage.lastMapZone=zone.name+"|enter";}};
  stageZoneLeft=(body,zone)=>{if(zone&&zone.gameObject.scene==stageGeometryScene){r.stage.mapZoneExits++;r.stage.lastMapZone=zone.name+"|exit";}};
  stageZoneTeleported=body=>{if(r.stage!=null&&r.stage.mapZonesReady)r.stage.mapZoneTeleports++;};
  MapZone.OnEnterMapZone+=stageZoneEntered;MapZone.OnLeaveMapZone+=stageZoneLeft;MapZone.onBodyTeleportGlobal+=stageZoneTeleported;ownsStageMapZoneObservations=true;
 }
 void StopStageMapZoneObservations(){if(!ownsStageMapZoneObservations)return;MapZone.OnEnterMapZone-=stageZoneEntered;MapZone.OnLeaveMapZone-=stageZoneLeft;MapZone.onBodyTeleportGlobal-=stageZoneTeleported;ownsStageMapZoneObservations=false;stageMapZones=new MapZone[0];}
 static string StageObjectPath(Transform target){var path=target.name;while(target.parent){target=target.parent;path=target.name+"/"+path;}return path;}
 IEnumerator CleanupStageGeometry(){PauseStageMapZones();StopStageMapZoneObservations();
  if(stageGeometryScene.IsValid()&&stageGeometryScene.isLoaded)yield return SceneManager.UnloadSceneAsync(stageGeometryScene);
  foreach(var billboard in stageGeometryBillboards)if(billboard)Destroy(billboard);stageGeometryBillboards.Clear();
  foreach(var material in stageGeometryMaterials)if(material)Destroy(material);stageGeometryMaterials.Clear();
  if(stageGeometryBundle){stageGeometryBundle.Unload(true);stageGeometryBundle=null;}
  if(r.stage!=null){r.stage.cleaned=!stageGeometryScene.isLoaded;Check(r.stage.cleaned,"Owned stage geometry cleanup incomplete");Save();}
 }
}
