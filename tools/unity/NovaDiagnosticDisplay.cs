using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Renderer-only view of the original detached model. Never writes the actor/model pose.
public sealed class NovaDiagnosticDisplay : IDisposable {
 public GameObject root;public Camera camera;Material material,floorMaterial;Texture2D grid;
 Transform copy,source;LineRenderer aim;bool actualModel;
 public NovaThirdPersonView thirdPerson;
 static Transform Copy(Transform s,Transform parent,Dictionary<Transform,Transform> map){var t=new GameObject(s.name).transform;t.gameObject.layer=30;t.SetParent(parent,false);t.localPosition=s.localPosition;t.localRotation=s.localRotation;t.localScale=s.localScale;map[s]=t;foreach(Transform child in s)Copy(child,t,map);return t;}
 public NovaDiagnosticDisplay(Transform model,AssetBundle bundle,string[] assets,GameObject floor,bool actual=false){
  actualModel=actual;
  source=model;root=new GameObject("Nova recovered Commando display");
  var map=new Dictionary<Transform,Transform>();if(!actual)copy=Copy(model,root.transform,map);
  else foreach(var component in model.GetComponentsInChildren<MonoBehaviour>(true)){
   component.enabled=false;
   // Optional native sound producers cannot enter Awake on this silent Android instance.
   if(component.GetType().Name.StartsWith("Ak",StringComparison.Ordinal))UnityEngine.Object.DestroyImmediate(component);
  }
  var shader=Resources.Load<Shader>("CommandoMaterialPreview");var simple=Resources.Load<Shader>("CommandoPreview");
  if(assets==null||assets.Length!=6||!shader||!shader.isSupported||!simple)throw new Exception("Nova display contract unavailable");
  material=new Material(bundle.LoadAsset<Material>(assets[5]));material.shader=shader;material.shaderKeywords=new string[0];material.SetFloat("_EmissionEnabled",1);
  var renderers=model.GetComponentsInChildren<Renderer>(true);
  foreach(var path in assets.Skip(2).Take(3)){
   var mesh=bundle.LoadAsset<Mesh>(path);if(!mesh)throw new Exception("Recovered display mesh missing");var src=renderers.Single(x=>x.name==mesh.name);var target=actual?src.transform:map[src.transform];Renderer renderer;
   if(actual){renderer=src;renderer.enabled=true;target.gameObject.layer=30;if(src is SkinnedMeshRenderer original){original.sharedMesh=mesh;original.updateWhenOffscreen=true;}else target.GetComponent<MeshFilter>().sharedMesh=mesh;}
   else if(src is SkinnedMeshRenderer skin){var sk=target.gameObject.AddComponent<SkinnedMeshRenderer>();sk.sharedMesh=mesh;sk.bones=skin.bones.Select(x=>map[x]).ToArray();sk.rootBone=map[skin.rootBone];sk.localBounds=skin.localBounds;sk.updateWhenOffscreen=true;renderer=sk;}
   else{target.gameObject.AddComponent<MeshFilter>().sharedMesh=mesh;renderer=target.gameObject.AddComponent<MeshRenderer>();}renderer.sharedMaterial=material;
  }
  if(root.GetComponentsInChildren<MonoBehaviour>(true).Length!=0)throw new Exception("Display unexpectedly contains gameplay behaviours");
  if(actual){
   foreach(var collider in model.GetComponentsInChildren<Collider>(true))collider.enabled=false;
   var animator=model.GetComponent<Animator>();animator.runtimeAnimatorController=bundle.LoadAsset<RuntimeAnimatorController>(assets[0]);animator.avatar=bundle.LoadAsset<Avatar>(assets[1]);animator.applyRootMotion=false;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;animator.enabled=true;model.gameObject.SetActive(true);
  }
  grid=new Texture2D(64,64);for(int y=0;y<64;y++)for(int x=0;x<64;x++)grid.SetPixel(x,y,x<2||y<2?new Color(.2f,.24f,.3f):new Color(.075f,.09f,.12f));grid.Apply();grid.wrapMode=TextureWrapMode.Repeat;
  floorMaterial=new Material(simple);floorMaterial.mainTexture=grid;floorMaterial.mainTextureScale=Vector2.one*50;if(floor)floor.GetComponent<Renderer>().sharedMaterial=floorMaterial;
  camera=new GameObject("Nova diagnostic camera").AddComponent<Camera>();camera.transform.SetParent(root.transform,false);camera.depth=100;camera.cullingMask=1<<30;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.04f,.05f,.07f);camera.orthographic=true;camera.orthographicSize=8;camera.nearClipPlane=.01f;camera.farClipPlane=200;
  var light=new GameObject("Nova diagnostic light").AddComponent<Light>();light.transform.SetParent(root.transform,false);light.type=LightType.Directional;light.transform.rotation=Quaternion.Euler(45,-30,0);
  aim=new GameObject("Input aim indicator").AddComponent<LineRenderer>();aim.transform.SetParent(root.transform,false);aim.gameObject.layer=30;aim.sharedMaterial=floorMaterial;aim.positionCount=2;aim.startWidth=aim.endWidth=.1f;
 }
 public void ConfigureThirdPerson(RoR2.CharacterBody body){thirdPerson=new NovaThirdPersonView(camera,body);aim.enabled=false;}
 public void Observe(Vector3 bodyPosition,Vector3 direction){if(!actualModel)copy.SetPositionAndRotation(source.position,source.rotation);if(thirdPerson!=null){thirdPerson.Place();return;}camera.transform.position=new Vector3(bodyPosition.x,bodyPosition.y+10,bodyPosition.z-12);camera.transform.LookAt(bodyPosition+Vector3.up);aim.SetPosition(0,bodyPosition+Vector3.up);aim.SetPosition(1,bodyPosition+Vector3.up+direction*3);}
 public void Dispose(){if(actualModel&&source)source.gameObject.SetActive(false);if(root)UnityEngine.Object.Destroy(root);if(material)UnityEngine.Object.Destroy(material);if(floorMaterial)UnityEngine.Object.Destroy(floorMaterial);if(grid)UnityEngine.Object.Destroy(grid);}
}
