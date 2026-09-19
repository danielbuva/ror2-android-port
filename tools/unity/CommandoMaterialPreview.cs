using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEngine;

// Diagnostic display copies only; source slots are populated by original CharacterModel code.
public sealed class CommandoMaterialPreview {
 [Serializable] public class Result {
  public string attempt,error,graphics;public int pid,rendererCount,changedPixels,backgroundChanges;
  public bool success,shaderSupported,sourceIdentity,contextRestored;public float meanDifference;
  public string[] sourceMaterials,albedoTextures,emissionTextures;public float[] emissionPowers;
 }
 static void Require(bool value,string message){if(!value)throw new Exception(message);}
 public static bool AssignOriginal(RoR2.CharacterModel model){
  var type=typeof(RoR2.CharacterModel);var flags=BindingFlags.NonPublic|BindingFlags.Instance;
  var names=new[]{"_visibility","_isGhost","_isDoppelganger","activeOverlayCount","particleMaterialOverride"};
  var fields=names.Select(n=>type.GetField(n,flags)).ToArray();Require(fields.All(f=>f!=null),"Detached material context fields missing");
  var old=fields.Select(f=>f.GetValue(model)).ToArray();var oldBody=model.body;
  var values=new object[]{RoR2.VisibilityLevel.Visible,false,false,0,null};
  try{
   model.body=null;for(int i=0;i<fields.Length;i++)fields[i].SetValue(model,values[i]);
   type.GetMethod("InitSharedMaterialsArrays",BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,null);
   var update=type.GetMethod("UpdateRendererMaterials",flags);var infos=model.baseRendererInfos;
   Require(infos.Length==3&&infos.All(x=>x.renderer.sharedMaterials.Length==0),"Expected empty original source slots");
   foreach(var info in infos)update.Invoke(model,new object[]{info.renderer,info.defaultMaterial,info.ignoreOverlays});
   Require(infos.All(x=>x.renderer.sharedMaterials.Length==1&&x.renderer.sharedMaterial==x.defaultMaterial),"Original source material assignment failed");
  }finally{model.body=oldBody;for(int i=0;i<fields.Length;i++)fields[i].SetValue(model,old[i]);}
  return model.body==oldBody&&fields.Select((f,i)=>Equals(f.GetValue(model),old[i])).All(x=>x);
 }
 public static void Begin(GameObject source,Renderer[] renderers,Material[] expected,string attempt,Action<Result> done){
  var r=new Result{attempt=attempt,rendererCount=renderers.Length,graphics=SystemInfo.graphicsDeviceType.ToString(),contextRestored=true};
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))r.pid=process.CallStatic<int>("myPid");
#endif
  GameObject host=null;var materials=new List<Material>();
  try{
   r.sourceIdentity=renderers.Length==3&&renderers.Select((x,i)=>x.sharedMaterial==expected[i]).All(x=>x);Require(r.sourceIdentity,"Source material identity changed");
   var shader=Resources.Load<Shader>("CommandoMaterialPreview");var control=Resources.Load<Shader>("CommandoPreview");
   r.shaderSupported=shader&&shader.isSupported&&control&&control.isSupported;Require(r.shaderSupported,"Diagnostic shaders unavailable");
   host=new GameObject("Owned material display");var map=new Dictionary<Transform,Transform>();var root=Copy(source.transform,host.transform,map);
   var copies=new List<Renderer>();
   foreach(var src in renderers){
    var target=map[src.transform];Renderer dst;
    if(src is SkinnedMeshRenderer skin){var sk=target.gameObject.AddComponent<SkinnedMeshRenderer>();sk.sharedMesh=skin.sharedMesh;sk.bones=skin.bones.Select(x=>map[x]).ToArray();sk.rootBone=map[skin.rootBone];sk.localBounds=skin.localBounds;sk.updateWhenOffscreen=true;dst=sk;}
    else{target.gameObject.AddComponent<MeshFilter>().sharedMesh=src.GetComponent<MeshFilter>().sharedMesh;dst=target.gameObject.AddComponent<MeshRenderer>();}
    var mat=new Material(src.sharedMaterial);mat.shader=shader;mat.shaderKeywords=new string[0];Require(mat.GetTexture("_MainTex")&&mat.GetTexture("_EmTex"),"Recovered texture missing");dst.sharedMaterial=mat;materials.Add(mat);copies.Add(dst);
   }
   r.sourceMaterials=renderers.Select(x=>x.sharedMaterial.name).ToArray();r.albedoTextures=materials.Select(x=>x.GetTexture("_MainTex").name).ToArray();r.emissionTextures=materials.Select(x=>x.GetTexture("_EmTex").name).ToArray();r.emissionPowers=materials.Select(x=>x.GetFloat("_EmPower")).ToArray();
   var cameraObject=new GameObject("Owned capture camera");cameraObject.transform.SetParent(host.transform,false);var cam=cameraObject.AddComponent<Camera>();cam.cullingMask=1<<30;cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color(.055f,.07f,.09f);cam.fieldOfView=35;cam.nearClipPlane=.01f;
   var bounds=copies[0].bounds;foreach(var x in copies.Skip(1))bounds.Encapsulate(x.bounds);Require(bounds.size.magnitude>.01f,"Empty display bounds");
   float distance=Mathf.Max(bounds.size.x,bounds.size.y)*.5f/Mathf.Tan(cam.fieldOfView*Mathf.Deg2Rad*.5f)*1.35f;cam.transform.position=bounds.center+new Vector3(1,.22f,1).normalized*distance;cam.transform.LookAt(bounds.center);
   foreach(var m in materials)m.shader=control;Read(cam,"commando-material-control.png");
   foreach(var m in materials){m.shader=shader;m.SetFloat("_EmissionEnabled",0);}var a=Read(cam,"commando-material-albedo.png");
   foreach(var m in materials)m.SetFloat("_EmissionEnabled",1);var b=Read(cam,"commando-material-emission.png");
   double sum=0;for(int i=0;i<a.Length;i++){int x=i%512,y=i/512;float d=Mathf.Abs(a[i].r-b[i].r)+Mathf.Abs(a[i].g-b[i].g)+Mathf.Abs(a[i].b-b[i].b);bool border=x<8||x>=504||y<8||y>=760;if(border&&d>.001f)r.backgroundChanges++;if(!border){sum+=d;if(d>.003f)r.changedPixels++;}}
   r.meanDifference=(float)(sum/a.Length);Require(r.changedPixels>0&&r.backgroundChanges==0,"Emission sensitivity/background assertion failed");r.success=true;
  }catch(Exception e){r.error=e.ToString();}
  finally{if(host)UnityEngine.Object.Destroy(host);foreach(var m in materials)UnityEngine.Object.Destroy(m);File.WriteAllText(Path.Combine(Application.persistentDataPath,"commando-material-probe.json"),JsonUtility.ToJson(r,true));done(r);}
 }
 static Transform Copy(Transform s,Transform p,Dictionary<Transform,Transform> map){var t=new GameObject(s.name).transform;t.gameObject.layer=30;t.SetParent(p,false);t.localPosition=s.localPosition;t.localRotation=s.localRotation;t.localScale=s.localScale;map[s]=t;foreach(Transform c in s)Copy(c,t,map);return t;}
 static Color[] Read(Camera c,string name){var rt=new RenderTexture(512,768,24);var oldTarget=c.targetTexture;var oldActive=RenderTexture.active;Texture2D tex=null;try{c.targetTexture=rt;c.Render();RenderTexture.active=rt;tex=new Texture2D(512,768,TextureFormat.RGB24,false);tex.ReadPixels(new Rect(0,0,512,768),0,0);tex.Apply();File.WriteAllBytes(Path.Combine(Application.persistentDataPath,name),tex.EncodeToPNG());return tex.GetPixels();}finally{c.targetTexture=oldTarget;RenderTexture.active=oldActive;rt.Release();UnityEngine.Object.Destroy(rt);if(tex)UnityEngine.Object.Destroy(tex);}}
}
