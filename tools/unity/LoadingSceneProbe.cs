using System;
using System.IO;
using System.Collections;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;

// Isolated recovered scene probe. The application startup object stays inactive.
public class LoadingSceneProbe : MonoBehaviour {
 [Serializable] public class Config {public string attempt,bundle,scene;}
 [Serializable] public class Report {public string attempt,error,scene;public int pid,objects,missingScripts,activeCameras;public bool loaded,startupInactive,success;}
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
  report.success=report.loaded&&report.objects>0&&report.missingScripts==0&&report.startupInactive;
  Save(report);
 }
 static void Save(Report report){var text=JsonUtility.ToJson(report,true);File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"loading-scene-probe.json"),text);Debug.Log("LAB_LOADING_SCENE "+text);}
}
