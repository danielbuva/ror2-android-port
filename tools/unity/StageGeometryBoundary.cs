using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.SceneManagement;

// Recovered static stage geometry; directors, scene lifecycle and progression remain separate.
public sealed partial class MovementBatchProbe {
 [Serializable] public class StageGeometryReport {
  public string scene,spawnMarker;public bool loaded,cleaned,groundHit;
  public int activeRoots,terrainMaterials,surfaceMaterials,terrainTextureMaterials;public bool terrainTexturesBound;public int objects,renderers,meshColliders,colliders,missingMeshes,missingColliderMeshes,behaviours;
  public Vector3 spawnPosition,groundPosition,groundNormal;
 }
 AssetBundle stageGeometryBundle;Scene stageGeometryScene;
 readonly List<Material> stageGeometryMaterials=new List<Material>();
 IEnumerator PrepareStageGeometry(){
  r.stage=new StageGeometryReport();r.phase="stage-geometry-load";Save();
  stageGeometryBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","golemplains-spine-lab"));
  Check(stageGeometryBundle,"Recovered stage geometry bundle missing");var scenes=stageGeometryBundle.GetAllScenePaths();Check(scenes.Length==1,"Expected one recovered stage geometry scene");
  yield return SceneManager.LoadSceneAsync(scenes[0],LoadSceneMode.Additive);stageGeometryScene=SceneManager.GetSceneByPath(scenes[0]);
  r.stage.loaded=stageGeometryScene.IsValid()&&stageGeometryScene.isLoaded;r.stage.scene=stageGeometryScene.name;Check(r.stage.loaded,"Stage geometry did not load");
  var roots=stageGeometryScene.GetRootGameObjects();var transforms=roots.SelectMany(x=>x.GetComponentsInChildren<Transform>(true)).ToArray();
  r.stage.objects=transforms.Length;r.stage.behaviours=roots.Sum(x=>x.GetComponentsInChildren<MonoBehaviour>(true).Length);
  r.stage.activeRoots=roots.Count(x=>x.activeSelf);Check(r.stage.behaviours==0&&r.stage.activeRoots>0,"Geometry scene contains behaviours or no active source roots");
  Shader terrainShader=Resources.Load<Shader>("StageTerrainPreview"),surfaceShader=Resources.Load<Shader>("StageSurfacePreview");
  Check(terrainShader&&terrainShader.isSupported&&surfaceShader&&surfaceShader.isSupported,"Diagnostic stage material shaders unavailable");r.stage.terrainTexturesBound=true;
  var replacements=new Dictionary<Material,Material>();
  foreach(var renderer in roots.SelectMany(x=>x.GetComponentsInChildren<Renderer>(true))){
   renderer.gameObject.layer=LayerIndex.world.intVal;var filter=renderer.GetComponent<MeshFilter>();var skinned=renderer as SkinnedMeshRenderer;
   if((filter&&!filter.sharedMesh)||(skinned&&!skinned.sharedMesh))r.stage.missingMeshes++;
   var materials=renderer.sharedMaterials;
   for(int i=0;i<materials.Length;i++){
    if(!materials[i])continue;Material replacement;
    if(!replacements.TryGetValue(materials[i],out replacement)){
     bool terrain=materials[i].shader.name.IndexOf("Triplanar",StringComparison.OrdinalIgnoreCase)>=0;
     replacement=new Material(materials[i]);replacement.shader=terrain?terrainShader:surfaceShader;replacement.shaderKeywords=new string[0];
     if(terrain){r.stage.terrainMaterials++;if(materials[i].name.StartsWith("matGPTerrain",StringComparison.Ordinal)){r.stage.terrainTextureMaterials++;r.stage.terrainTexturesBound&=replacement.GetTexture("_RedChannelTopTex")&&replacement.GetTexture("_RedChannelSideTex")&&replacement.GetTexture("_GreenChannelTex")&&replacement.GetTexture("_BlueChannelTex");}}else r.stage.surfaceMaterials++;
     replacements.Add(materials[i],replacement);stageGeometryMaterials.Add(replacement);
    }
    materials[i]=replacement;
   }
   renderer.sharedMaterials=materials;r.stage.renderers++;
  }
  foreach(var collider in roots.SelectMany(x=>x.GetComponentsInChildren<Collider>(true))){
   collider.gameObject.layer=LayerIndex.world.intVal;if(collider.isTrigger)continue;r.stage.colliders++;
   var mesh=collider as MeshCollider;if(mesh){r.stage.meshColliders++;if(!mesh.sharedMesh)r.stage.missingColliderMeshes++;}
  }
  Check(r.stage.renderers>100&&r.stage.meshColliders>50&&r.stage.missingMeshes==0&&r.stage.missingColliderMeshes==0,"Recovered stage mesh/collision closure incomplete");
  Check(r.stage.terrainTextureMaterials>=2&&r.stage.terrainTexturesBound,"Original terrain channel textures did not bind to the owned preview material");
  Physics.SyncTransforms();
  foreach(var marker in transforms.Where(x=>x.name=="SurvivorPodSpawnPoint"&&x.gameObject.activeInHierarchy)){
   RaycastHit hit;if(!Physics.Raycast(marker.position+Vector3.up*30,Vector3.down,out hit,100,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||hit.normal.y<.9f)continue;
   r.stage.spawnMarker=marker.name;r.stage.groundHit=true;r.stage.groundPosition=hit.point;r.stage.groundNormal=hit.normal;r.stage.spawnPosition=hit.point+Vector3.up*2.5f;break;
  }
  Check(r.stage.groundHit,"No original survivor spawn marker has a measured walkable stage collider");Save();
 }
 IEnumerator CleanupStageGeometry(){
  if(stageGeometryScene.IsValid()&&stageGeometryScene.isLoaded)yield return SceneManager.UnloadSceneAsync(stageGeometryScene);
  foreach(var material in stageGeometryMaterials)if(material)Destroy(material);stageGeometryMaterials.Clear();
  if(stageGeometryBundle){stageGeometryBundle.Unload(true);stageGeometryBundle=null;}
  if(r.stage!=null){r.stage.cleaned=!stageGeometryScene.isLoaded;Check(r.stage.cleaned,"Owned stage geometry cleanup incomplete");Save();}
 }
}
