using System;
using System.IO;
using System.Collections;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;

// Isolated recovered scene probe. The application startup object stays inactive.
public class LoadingSceneProbe : MonoBehaviour {
 [Serializable] public class Config {public string attempt,bundle,scene,prefab;public string[] prefabAssets;}
 [Serializable] public class Report {public string attempt,error,scene;public int pid,objects,missingScripts,activeCameras,persistentObjects,persistentMissingScripts,spriteChanges,activeTextObjects,missingFonts;public string[] persistentRoots;public bool loaded,startupInactive,success;public PrefabReport prefab;}
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
 static void Init(){if(Resources.Load<TextAsset>("LoadingSceneProbe"))new GameObject("Loading scene probe").AddComponent<LoadingSceneProbe>();}
 IEnumerator Start(){
  DontDestroyOnLoad(gameObject);
  var cfg=JsonUtility.FromJson<Config>(Resources.Load<TextAsset>("LoadingSceneProbe").text);
  var report=new Report{attempt=cfg.attempt,scene=cfg.scene};
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))report.pid=process.CallStatic<int>("myPid");
#endif
  yield return new WaitForSeconds(6);
  var path=System.IO.Path.Combine(Application.persistentDataPath,"payload",cfg.bundle);
  if(!File.Exists(path))yield break;
  var bundle=AssetBundle.LoadFromFile(path);
  if(!bundle){report.error="Scene bundle failed to load";Save(report);yield break;}
  var paths=bundle.GetAllScenePaths();
  if(paths.Length!=1){report.error="Expected exactly one scene";Save(report);yield break;}
  var before=new System.Collections.Generic.HashSet<int>(RuntimeObjects().Select(t=>t.GetInstanceID()));
  var oldCameras=Camera.allCameras;
  yield return SceneManager.LoadSceneAsync(paths[0],LoadSceneMode.Additive);
  var scene=SceneManager.GetSceneByPath(paths[0]);report.loaded=scene.IsValid()&&scene.isLoaded;
  if(report.loaded){
   SceneManager.SetActiveScene(scene);
   var objects=scene.GetRootGameObjects().SelectMany(x=>x.GetComponentsInChildren<Transform>(true)).ToArray();
   report.objects=objects.Length;report.missingScripts=objects.Sum(t=>t.GetComponents<Component>().Count(c=>!c));
   var startup=objects.FirstOrDefault(t=>t.name=="RoR2Application");report.startupInactive=startup&&!startup.gameObject.activeInHierarchy&&RoR2.RoR2Application.instance==null;
   foreach(var camera in oldCameras)camera.enabled=false;
   report.activeCameras=Camera.allCamerasCount;
  }
  yield return new WaitForSeconds(10);
  var added=RuntimeObjects().Where(t=>!before.Contains(t.GetInstanceID())).ToArray();
  var persistent=added.Where(t=>t.gameObject.scene.name=="DontDestroyOnLoad").ToArray();
  report.persistentObjects=persistent.Length;
  report.persistentMissingScripts=persistent.Sum(t=>t.GetComponents<Component>().Count(c=>!c));
  report.persistentRoots=persistent.Where(t=>!t.parent).Select(t=>t.name).ToArray();
  var texts=added.SelectMany(t=>t.GetComponents<TMPro.TMP_Text>()).Where(t=>t.isActiveAndEnabled).ToArray();
  report.activeTextObjects=texts.Length;report.missingFonts=texts.Count(t=>!t.font);
  var images=added.SelectMany(t=>t.GetComponents<UnityEngine.UI.Image>()).Where(i=>i.isActiveAndEnabled).ToArray();
  var sprites=images.Select(i=>i.sprite).ToArray();
  for(int sample=0;sample<8;sample++){
   yield return new WaitForSeconds(0.25f);
   for(int i=0;i<images.Length;i++)if(images[i]&&images[i].sprite!=sprites[i]){report.spriteChanges++;sprites[i]=images[i].sprite;}
  }
  report.success=report.loaded&&report.objects>0&&report.missingScripts==0&&report.persistentMissingScripts==0&&report.persistentObjects>0&&report.startupInactive;
  if(!string.IsNullOrEmpty(cfg.prefab)){report.prefab=InspectPrefab(cfg);report.success=report.success&&report.prefab.success;}
  Save(report);
 }
 [Serializable] public class Skin {public string name,mesh;public int vertices,bones,missingBones,bindPoses,missingMaterials;public string[] shaders;}
 [Serializable] public class PrefabReport {public string error;public bool success,inactive,hasBody,hasModel,hasAvatar,diagnosticDefaultBinding;public int meshFilters,missingFilterMeshes;public int objects,missingScripts,animators,controllers,clips;public Skin[] skins;}
 static PrefabReport InspectPrefab(Config cfg){
  var r=new PrefabReport();
  try{
   var bundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));
   if(!bundle)throw new Exception("Prefab bundle missing or failed to load");
   var asset=bundle.LoadAsset<GameObject>(cfg.prefab);
   if(!asset||asset.activeSelf)throw new Exception("Expected an inactive Commando prefab asset");
   var instance=Instantiate(asset);r.inactive=!instance.activeInHierarchy;
   if(cfg.prefabAssets==null||cfg.prefabAssets.Length!=6)throw new Exception("Expected six measured default assets");
   var controller=bundle.LoadAsset<RuntimeAnimatorController>(cfg.prefabAssets[0]);
   var avatar=bundle.LoadAsset<Avatar>(cfg.prefabAssets[1]);
   var material=bundle.LoadAsset<Material>(cfg.prefabAssets[5]);
   if(!controller||!avatar||!material)throw new Exception("Default controller/avatar/material missing");
   var meshAssets=cfg.prefabAssets.Skip(2).Take(3).Select(p=>bundle.LoadAsset<Mesh>(p)).ToArray();
   if(meshAssets.Any(m=>!m))throw new Exception("Default mesh missing");
   foreach(var mesh in meshAssets){
    var renderer=instance.GetComponentsInChildren<Renderer>(true).Single(x=>x.name==mesh.name);
    var skin=renderer as SkinnedMeshRenderer;
    if(skin)skin.sharedMesh=mesh;
    else {var filter=renderer.GetComponent<MeshFilter>();if(!filter)throw new Exception("MeshFilter missing");filter.sharedMesh=mesh;}
    renderer.sharedMaterials=new[]{material};
   }
   foreach(var animator in instance.GetComponentsInChildren<Animator>(true)){animator.runtimeAnimatorController=controller;animator.avatar=avatar;}
   r.diagnosticDefaultBinding=true;
   var filters=instance.GetComponentsInChildren<MeshFilter>(true);r.meshFilters=filters.Length;r.missingFilterMeshes=filters.Count(f=>!f.sharedMesh);
   var objects=instance.GetComponentsInChildren<Transform>(true);r.objects=objects.Length;
   r.missingScripts=objects.Sum(t=>t.GetComponents<Component>().Count(c=>!c));
   r.hasBody=instance.GetComponent<RoR2.CharacterBody>();
   var locator=instance.GetComponent<RoR2.ModelLocator>();r.hasModel=locator&&locator.modelTransform;
   var animators=instance.GetComponentsInChildren<Animator>(true);r.animators=animators.Length;
   r.controllers=animators.Count(a=>a.runtimeAnimatorController);r.clips=animators.Where(a=>a.runtimeAnimatorController).Sum(a=>a.runtimeAnimatorController.animationClips.Length);
   r.hasAvatar=animators.Any(a=>a.avatar&&a.avatar.isValid);
   r.skins=instance.GetComponentsInChildren<SkinnedMeshRenderer>(true).Select(x=>new Skin{name=x.name,mesh=x.sharedMesh?x.sharedMesh.name:null,vertices=x.sharedMesh?x.sharedMesh.vertexCount:0,bones=x.bones.Length,missingBones=x.bones.Count(b=>!b),bindPoses=x.sharedMesh?x.sharedMesh.bindposes.Length:0,missingMaterials=x.sharedMaterials.Count(m=>!m),shaders=x.sharedMaterials.Select(m=>m&&m.shader?m.shader.name:null).ToArray()}).ToArray();
   r.success=r.inactive&&r.diagnosticDefaultBinding&&r.missingFilterMeshes==0&&r.hasBody&&r.hasModel&&r.missingScripts==0&&r.skins.Length>0&&r.skins.All(x=>x.vertices>0&&x.bones>0&&x.missingBones==0&&x.bindPoses==x.bones&&x.missingMaterials==0)&&r.controllers>0&&r.clips>0&&r.hasAvatar;
  }catch(Exception e){r.error=e.ToString();}
  return r;
 }
 static Transform[] RuntimeObjects(){return Resources.FindObjectsOfTypeAll<Transform>().Where(t=>t.gameObject.scene.IsValid()&&t.gameObject.scene.isLoaded).ToArray();}
 static void Save(Report report){var text=JsonUtility.ToJson(report,true);File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"loading-scene-probe.json"),text);Debug.Log("LAB_LOADING_SCENE "+text);}
}
