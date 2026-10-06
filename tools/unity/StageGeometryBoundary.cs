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
  public string scene,spawnMarker,groundColliderPath,groundColliderScene;public bool loaded,cleaned,groundHit;
  public bool mapZonesReady;public int mapZoneNetworkObjects,mapZoneCount,mapZoneEntries,mapZoneExits,mapZoneTeleports;public string lastMapZone;
  public int activeRoots,terrainMaterials,surfaceMaterials,terrainTextureMaterials;public bool terrainTexturesBound;public int objects,renderers,meshColliders,colliders,worldColliders,nonWorldColliders,missingMeshes,missingColliderMeshes,behaviours,previewDisableComponents,previewsInactive;
  public Vector3 spawnPosition,groundPosition,groundNormal,entryOrigin;
  public string[] emptyMeshPaths,emptyColliderPaths;
 }
 AssetBundle stageGeometryBundle;Scene stageGeometryScene;
 readonly List<Material> stageGeometryMaterials=new List<Material>();
 bool stageMoonVolumes;int stageZoneNetworkObjects;string[] stageZoneActiveNames;
 MapZone[] stageMapZones=new MapZone[0];Action<CharacterBody,MapZone> stageZoneEntered,stageZoneLeft;Action<CharacterBody> stageZoneTeleported;bool ownsStageMapZoneObservations;
 IEnumerator PrepareStageGeometry(int mapZones=0,string[] activeNames=null){var load=LoadStageGeometry("golemplains-spine-lab",23,null,mapZones,activeNames);while(load.MoveNext())yield return load.Current;}
 IEnumerator LoadStageGeometry(string bundleName,int previewCount,IntegratedStageSpec spec,int initialMapZones=0,string[] initialActiveNames=null){
  r.stage=new StageGeometryReport();r.phase="stage-geometry-load";Save();
  stageGeometryBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload",bundleName));
  Check(stageGeometryBundle,"Recovered stage geometry bundle missing");var scenes=stageGeometryBundle.GetAllScenePaths();Check(scenes.Length==1,"Expected one recovered stage geometry scene");
  yield return SceneManager.LoadSceneAsync(scenes[0],LoadSceneMode.Additive);stageGeometryScene=SceneManager.GetSceneByPath(scenes[0]);
  r.stage.loaded=stageGeometryScene.IsValid()&&stageGeometryScene.isLoaded;r.stage.scene=stageGeometryScene.name;Check(r.stage.loaded,"Stage geometry did not load");
  yield return null; // Allow original scene preview Start callbacks; no manual deactivation.
  var roots=stageGeometryScene.GetRootGameObjects();stageStaticRoots=new HashSet<GameObject>(roots);var transforms=roots.SelectMany(x=>x.GetComponentsInChildren<Transform>(true)).ToArray();
  r.stage.objects=transforms.Length;r.stage.behaviours=roots.Sum(x=>x.GetComponentsInChildren<MonoBehaviour>(true).Length);
  var previewCallbacks=roots.SelectMany(x=>x.GetComponentsInChildren<MonoBehaviour>(true)).ToArray();
  r.stage.previewDisableComponents=previewCallbacks.Count(x=>x&&x.GetType()==typeof(DisableOnStart));r.stage.previewsInactive=previewCallbacks.Count(x=>x&&x is DisableOnStart&&!x.gameObject.activeSelf);
  var previewNames=spec!=null&&spec.previewNames!=null?spec.previewNames:Enumerable.Repeat("EscapePodMesh",previewCount).ToArray();
  bool moon=spec!=null&&spec.moonMission;int expectedMapZones=spec==null?initialMapZones:spec.mapZoneCount;
  stageMoonVolumes=moon;stageZoneNetworkObjects=spec==null?0:spec.mapZoneNetworkObjects;stageZoneActiveNames=(spec==null?initialActiveNames:spec.mapZoneActiveNames)??new string[0];
  stageMapZones=roots.SelectMany(x=>x.GetComponentsInChildren<MapZone>(true)).ToArray();r.stage.mapZoneCount=stageMapZones.Length;
  StartStageMapZoneObservations();
  r.stage.activeRoots=roots.Count(x=>x.activeSelf);Check(moon?r.stage.behaviours==spec.missionComponents&&previewCallbacks.All(x=>x)&&r.stage.activeRoots==0:r.stage.behaviours==previewCount+expectedMapZones+stageZoneNetworkObjects*2&&stageMapZones.Length==expectedMapZones&&previewCallbacks.All(x=>x&&(x is DisableOnStart||x is MapZone||((x is NetworkIdentity||x is TeamFilter)&&x.GetComponent<MapZone>())))&&r.stage.previewDisableComponents==previewCount&&r.stage.previewsInactive==previewCount&&previewCallbacks.Where(x=>x is DisableOnStart).Select(x=>x.gameObject.name).OrderBy(x=>x).SequenceEqual(previewNames.OrderBy(x=>x))&&r.stage.activeRoots>0,"Original preview Start or scene behaviour allowlist failed");
  Shader terrainShader=Resources.Load<Shader>("StageTerrainPreview"),surfaceShader=Resources.Load<Shader>("StageSurfacePreview");
  Check(terrainShader&&terrainShader.isSupported&&surfaceShader&&surfaceShader.isSupported,"Diagnostic stage material shaders unavailable");r.stage.terrainTexturesBound=true;
  var replacements=new Dictionary<Material,Material>();var emptyMeshes=new List<string>();var emptyColliders=new List<string>();
  var beamReplacements=new Dictionary<Material,Material>();
  foreach(var renderer in roots.SelectMany(x=>x.GetComponentsInChildren<Renderer>(true))){
   // Full Moon retains original physics/interaction/presentation layer roles.
   // Renderer layer changes also change any collider on that GameObject.
   if(!moon&&!renderer.GetComponents<Collider>().Any(x=>x.isTrigger))renderer.gameObject.layer=LayerIndex.world.intVal;var filter=renderer.GetComponent<MeshFilter>();var skinned=renderer as SkinnedMeshRenderer;
   if((filter&&!filter.sharedMesh)||(skinned&&!skinned.sharedMesh)){r.stage.missingMeshes++;emptyMeshes.Add(StageObjectPath(renderer.transform));}
   var materials=renderer.sharedMaterials;
   bool pillarBeam=moon&&IsMoonPillarBeam(renderer);var materialCache=pillarBeam?beamReplacements:replacements;
   for(int i=0;i<materials.Length;i++){
    if(!materials[i])continue;Material replacement;
    if(!materialCache.TryGetValue(materials[i],out replacement)){
     bool terrain=materials[i].shader.name.IndexOf("Triplanar",StringComparison.OrdinalIgnoreCase)>=0;
     replacement=new Material(materials[i]);replacement.shader=pillarBeam?Resources.Load<Shader>("MoonPillarBeamPreview"):terrain?terrainShader:surfaceShader;replacement.shaderKeywords=new string[0];
     if(pillarBeam)Check(replacement.shader&&replacement.shader.isSupported,"Android pillar beam shader unavailable");
     if(terrain){r.stage.terrainMaterials++;if(materials[i].name.StartsWith("matGPTerrain",StringComparison.Ordinal)){r.stage.terrainTextureMaterials++;r.stage.terrainTexturesBound&=replacement.GetTexture("_RedChannelTopTex")&&replacement.GetTexture("_RedChannelSideTex")&&replacement.GetTexture("_GreenChannelTex")&&replacement.GetTexture("_BlueChannelTex");}}else r.stage.surfaceMaterials++;
     materialCache.Add(materials[i],replacement);stageGeometryMaterials.Add(replacement);
    }
    materials[i]=replacement;
   }
   renderer.sharedMaterials=materials;r.stage.renderers++;
  }
  foreach(var collider in roots.SelectMany(x=>x.GetComponentsInChildren<Collider>(true))){
   // A non-trigger ambient/post-process volume is not world geometry. Promoting
   // Moon's source layer20 sphere ejects the landing body through KCC penetration.
   if(!moon&&!collider.isTrigger)collider.gameObject.layer=LayerIndex.world.intVal;if(collider.isTrigger)continue;r.stage.colliders++;
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
  if(!stageMoonVolumes){
   foreach(var zone in stageMapZones)if(stageZoneActiveNames.Contains(zone.name))zone.gameObject.SetActive(true);
   if(stageZoneNetworkObjects>0){
    var identities=Resources.FindObjectsOfTypeAll<NetworkIdentity>().Where(x=>x.gameObject.hideFlags!=HideFlags.NotEditable&&x.gameObject.hideFlags!=HideFlags.HideAndDontSave&&!x.sceneId.IsEmpty()).ToArray();
    Check(identities.Length==stageZoneNetworkObjects&&identities.All(x=>x.gameObject.scene==stageGeometryScene&&x.GetComponent<MapZone>()),"Unowned stage out-of-bounds scene identities");
    Check(NetworkServer.SpawnObjects(),"Original out-of-bounds server activation failed");r.stage.mapZoneNetworkObjects=identities.Length;
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
  foreach(var material in stageGeometryMaterials)if(material)Destroy(material);stageGeometryMaterials.Clear();
  if(stageGeometryBundle){stageGeometryBundle.Unload(true);stageGeometryBundle=null;}
  if(r.stage!=null){r.stage.cleaned=!stageGeometryScene.isLoaded;Check(r.stage.cleaned,"Owned stage geometry cleanup incomplete");Save();}
 }
}
