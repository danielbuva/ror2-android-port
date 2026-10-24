using System;
using System.Linq;
using UnityEngine;
using RoR2;
using UnityEngine.Networking;

namespace UnityEngine {
 public class Object { public static implicit operator bool(Object value) { return !ReferenceEquals(value,null); } }
 public class MonoBehaviour : Object { public bool enabled=true; }
 public class GameObject : Object {
  public string name="SceneInfo"; public bool activeSelf,throwOnEnable;
  public MonoBehaviour[] components;
  public T GetComponent<T>() where T:class { return components.OfType<T>().FirstOrDefault(); }
  public T[] GetComponents<T>() where T:class { return components.Cast<T>().ToArray(); }
  public void SetActive(bool value) {
   activeSelf=value;
   SceneInfo.instance=value?GetComponent<SceneInfo>():null;
   ClassicStageInfo.instance=value?GetComponent<ClassicStageInfo>():null;
   if(value && throwOnEnable)throw new InvalidOperationException("injected activation failure");
  }
 }
}
namespace RoR2 {
 public class Run : UnityEngine.Object { public static Run instance=new Run(); }
 public class SceneInfo : MonoBehaviour { public static SceneInfo instance; }
 public class ClassicStageInfo : MonoBehaviour { public static ClassicStageInfo instance; }
 public class RTPCController : MonoBehaviour {}
}
namespace UnityEngine.Networking { public static class NetworkServer { public static bool active=true; } }
public class AkEvent : MonoBehaviour {}
public static class GameAudioOriginalOwner { public static bool Ready; }
public class Scene { public GameObject root; public GameObject[] GetRootGameObjects() { return new[]{root}; } }
public class Coordinator {
 public bool stageSourceObjects=true; public GameObject sourceSceneInfoRoot;
 public Scene stageGeometryScene;
 public void Check(bool value,string message) { if(!value)throw new InvalidOperationException(message); }
}
public class Harness {
 public Coordinator coordinator=new Coordinator();
 public Scene stageGeometryScene { get { return coordinator.stageGeometryScene; } set { coordinator.stageGeometryScene=value; } }
 public int activated,retired; public bool managerActive;
 void ActivateSourceGameManager() { activated++;managerActive=true; }
 void DeactivateSourceGameManager() { retired++;managerActive=false; }
 __METHODS__
 static void Assert(bool value,string message) { if(!value)throw new Exception(message); }
 static Harness New(bool native) {
  SceneInfo.instance=null;ClassicStageInfo.instance=null;
  var root=new GameObject {components=native
   ?new MonoBehaviour[]{new SceneInfo(),new ClassicStageInfo(),new AkEvent {enabled=false},new RTPCController()}
   :new MonoBehaviour[]{new SceneInfo(),new ClassicStageInfo()}};
  return new Harness {stageGeometryScene=new Scene {root=root}};
 }
 static void Refused(Harness h) {
  bool refused=false;try { h.ActivateSourceSceneInfo(); }catch(InvalidOperationException) { refused=true; }
  Assert(refused,"unavailable/missing/duplicate source context admitted");
  Assert(h.activated==0 && !h.stageGeometryScene.root.activeSelf && !h.coordinator.sourceSceneInfoRoot,
         "refusal mutated source or event ownership");
 }
 public static void Main() {
  GameAudioOriginalOwner.Ready=false;
  var h=New(true);Refused(h);
  h=New(false);var info=h.ActivateSourceSceneInfo();
  Assert(info==SceneInfo.instance && h.managerActive,"default-off source context did not activate");
  h.DeactivateSourceSceneInfo();
  Assert(!SceneInfo.instance && !ClassicStageInfo.instance && !h.managerActive && h.retired==1,"default-off teardown changed");
  GameAudioOriginalOwner.Ready=true;h=New(true);var audio=h.stageGeometryScene.root.components.OfType<AkEvent>().Single();
  info=h.ActivateSourceSceneInfo();
  Assert(info==SceneInfo.instance && h.stageGeometryScene.root.components.Count(IsOriginalSceneAudio)==2,"native source census changed");
  Assert(!audio.enabled,"authored disabled audio component was enabled");
  h.DeactivateSourceSceneInfo();
  Assert(!h.coordinator.sourceSceneInfoRoot && !SceneInfo.instance && !ClassicStageInfo.instance && !h.managerActive && h.retired==1,
         "ready source teardown retained ownership");
  h=New(true);h.stageGeometryScene.root.components=h.stageGeometryScene.root.components.Concat(new MonoBehaviour[]{null}).ToArray();Refused(h);
  h=New(true);SceneInfo.instance=new SceneInfo();Refused(h);
  h=New(true);h.stageGeometryScene.root.throwOnEnable=true;bool failed=false;
  try { h.ActivateSourceSceneInfo(); }catch(InvalidOperationException) { failed=true; }
  Assert(failed && h.activated==1 && h.retired==1 && !h.managerActive && !h.coordinator.sourceSceneInfoRoot &&
         !h.stageGeometryScene.root.activeSelf && !SceneInfo.instance && !ClassicStageInfo.instance,
         "failed native context activation did not restore source ownership");
 }
}
