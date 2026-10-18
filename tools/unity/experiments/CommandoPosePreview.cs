using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

// Recovered transforms/renderers only. No original gameplay component is activated.
public class CommandoPosePreview : MonoBehaviour {
 [Serializable] public class Result {public string attempt,clip,error;public int pid,bones,changedBones,gameplayComponents;public float clipLength,timeA,timeB,maxBoneAngle;public bool success,textureUsed;public Vector3 boundsCenter,boundsSize;}
 Transform model; Animator animator; AnimationClip clip; PlayableGraph graph; AnimationClipPlayable playable; SkinnedMeshRenderer skin; Result result; bool loop;
 public static void Begin(GameObject inactiveBody,RuntimeAnimatorController controller,Avatar avatar,Material source,string attempt){
  var host=new GameObject("Commando content preview");var preview=host.AddComponent<CommandoPosePreview>();
  preview.result=new Result{attempt=attempt};
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))preview.result.pid=process.CallStatic<int>("myPid");
#endif
  try{preview.Prepare(inactiveBody,controller,avatar,source);}catch(Exception e){preview.result.error=e.ToString();preview.Save();preview.enabled=false;}
 }
 void Prepare(GameObject body,RuntimeAnimatorController controller,Avatar avatar,Material source){
  if(body.activeInHierarchy)throw new Exception("Original body unexpectedly active");
  var src=body.GetComponent<RoR2.ModelLocator>().modelTransform;
  var map=new Dictionary<Transform,Transform>();model=Copy(src,transform,map);
  var shader=Resources.Load<Shader>("CommandoPreview");if(!shader||!shader.isSupported)throw new Exception("Diagnostic shader unavailable");
  var material=new Material(shader);var texture=source.HasProperty("_MainTex")?source.GetTexture("_MainTex"):null;
  result.textureUsed=texture;material.mainTexture=texture?texture:Texture2D.whiteTexture;
  foreach(var renderer in src.GetComponentsInChildren<Renderer>(true)){
   var target=map[renderer.transform];var originalSkin=renderer as SkinnedMeshRenderer;
   if(originalSkin){
    var created=target.gameObject.AddComponent<SkinnedMeshRenderer>();created.sharedMesh=originalSkin.sharedMesh;created.bones=originalSkin.bones.Select(b=>map[b]).ToArray();created.rootBone=map[originalSkin.rootBone];created.localBounds=originalSkin.localBounds;created.updateWhenOffscreen=true;created.sharedMaterials=new[]{material};skin=created;
   }else if(renderer.GetComponent<MeshFilter>()){
    target.gameObject.AddComponent<MeshFilter>().sharedMesh=renderer.GetComponent<MeshFilter>().sharedMesh;
    target.gameObject.AddComponent<MeshRenderer>().sharedMaterials=new[]{material};
   }
  }
  if(!skin)throw new Exception("No copied skin");
  animator=model.gameObject.AddComponent<Animator>();animator.avatar=avatar;animator.applyRootMotion=false;animator.fireEvents=false;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
  clip=controller.animationClips.Single(c=>c.name=="CommandoArmature|RunForward");
  result.clip=clip.name;result.clipLength=clip.length;result.bones=skin.bones.Length;
  result.gameplayComponents=model.GetComponentsInChildren<MonoBehaviour>(true).Length;
  graph=PlayableGraph.Create("Recovered clip preview");graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
  playable=AnimationClipPlayable.Create(graph,clip);playable.SetApplyFootIK(false);playable.SetApplyPlayableIK(false);
  var output=AnimationPlayableOutput.Create(graph,"Recovered skeleton",animator);output.SetSourcePlayable(playable);graph.Play();Pose(0);
  foreach(var canvas in FindObjectsOfType<Canvas>())canvas.enabled=false;
  foreach(var camera in Camera.allCameras)camera.enabled=false;
  var cameraObject=new GameObject("Commando preview camera");var cam=cameraObject.AddComponent<Camera>();cam.cullingMask=1<<30;cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color(.055f,.07f,.09f);cam.fieldOfView=35;cam.nearClipPlane=.01f;cam.farClipPlane=1000;
  var bounds=skin.bounds;result.boundsCenter=bounds.center;result.boundsSize=bounds.size;
  if(bounds.size.magnitude<.01f)throw new Exception("Empty preview bounds");
  float distance=Mathf.Max(bounds.size.y,bounds.size.x)*.5f/Mathf.Tan(cam.fieldOfView*Mathf.Deg2Rad*.5f)*1.35f;
  cameraObject.transform.position=bounds.center+new Vector3(1,.22f,1).normalized*distance;cameraObject.transform.LookAt(bounds.center);
 }
 static Transform Copy(Transform source,Transform parent,Dictionary<Transform,Transform> map){
  var target=new GameObject(source.name).transform;target.gameObject.layer=30;target.SetParent(parent,false);target.localPosition=source.localPosition;target.localRotation=source.localRotation;target.localScale=source.localScale;map[source]=target;
  foreach(Transform child in source)Copy(child,target,map);return target;
 }
 static string ScreenshotPath(string name){
#if UNITY_ANDROID && !UNITY_EDITOR
  return name; // Unity appends Android persistentDataPath itself.
#else
  return Path.Combine(Application.persistentDataPath,name);
#endif
 }
 void Pose(float time){playable.SetTime(time);graph.Evaluate(0);}
 IEnumerator Start(){
  if(!enabled)yield break;
  yield return null;Pose(0);var a=skin.bones.Select(b=>b.localRotation).ToArray();
  result.timeA=0;yield return new WaitForEndOfFrame();ScreenCapture.CaptureScreenshot(ScreenshotPath("commando-pose-A.png"));
  yield return new WaitForSeconds(2);result.timeB=clip.length*.35f;Pose(result.timeB);
  for(int i=0;i<a.Length;i++){float angle=Quaternion.Angle(a[i],skin.bones[i].localRotation);result.maxBoneAngle=Mathf.Max(result.maxBoneAngle,angle);if(angle>.1f)result.changedBones++;}
  yield return new WaitForEndOfFrame();ScreenCapture.CaptureScreenshot(ScreenshotPath("commando-pose-B.png"));
  yield return new WaitForSeconds(2);
  result.success=result.changedBones>0&&result.gameplayComponents==0;Save();loop=true;
 }
 void Update(){if(loop)Pose(Time.time%clip.length);}
 void OnGUI(){GUI.Label(new Rect(20,60,650,40),"Recovered Commando / diagnostic clip preview / gameplay inactive");}
 void Save(){var text=JsonUtility.ToJson(result,true);File.WriteAllText(Path.Combine(Application.persistentDataPath,"commando-pose.json"),text);Debug.Log("LAB_COMMANDO_POSE "+text);}
 void OnDestroy(){if(graph.IsValid())graph.Destroy();}
}
