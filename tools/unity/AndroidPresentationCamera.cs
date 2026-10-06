using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.SceneManagement;

// Camera-only presentation pass and bounded measurements; source grading remains pending.
public sealed class AndroidPresentationCamera:MonoBehaviour {
 [Serializable] public class Sample {public string scene,skybox,sun;public bool fog,sourceCubemap,fallbackLight;public int fogMode;public Color fogColor,ambientLight;public float fogStart,fogEnd,fogDensity,ambientIntensity;public float seconds,meanMs,maxMs;public long allocatedBytes,reservedBytes,managedBytes;public int frames,over33ms,over50ms,gcCollections;}
 [Serializable] public class Report {public int frames,colorPasses,over33ms,over50ms;public float meanMs,maxMs;public bool sourceCubemap,sourceSun;public string skybox,sun,skyboxStatus,error;public List<Sample> samples=new List<Sample>();}
 public Light fallbackLight;
 public readonly Report report=new Report();Material grade;Camera view;double sum;float next,began;int lightingScene=-1;bool sourceDirectional;
 void Awake(){view=GetComponent<Camera>();view.depthTextureMode|=DepthTextureMode.Depth;began=Time.realtimeSinceStartup;var shader=AndroidMaterialPresentation.LoadShader("AndroidColorGrade");if(shader&&shader.isSupported)grade=new Material(shader);else report.error="Android camera presentation pass unavailable";}
 void LateUpdate(){
  // Four measured base-stage skies use Unity's original built-in cubemap shader.
  // Preserve their recovered cubemap, tint, exposure and rotation unchanged.
  var sky=RenderSettings.skybox;report.skybox=sky?sky.name:null;report.sourceCubemap=sky&&sky.shader&&sky.shader.name=="Skybox/Cubemap"&&sky.shader.isSupported;
  view.clearFlags=report.sourceCubemap?CameraClearFlags.Skybox:CameraClearFlags.SolidColor;report.skyboxStatus=report.sourceCubemap?"Original Unity cubemap material":"Source sky unavailable or unverified; no replacement sky";
  var sun=RenderSettings.sun;report.sun=sun?sun.name:null;report.sourceSun=sun&&sun.isActiveAndEnabled;
  // A null sun reference does not mean that the source scene has no directional light.
  var scene=SceneManager.GetActiveScene();
  if(lightingScene!=scene.handle||Time.realtimeSinceStartup>=next){lightingScene=scene.handle;sourceDirectional=report.sourceSun;
   if(!sourceDirectional&&scene.IsValid()&&scene.isLoaded)foreach(var root in scene.GetRootGameObjects())foreach(var light in root.GetComponentsInChildren<Light>(false))if(light!=fallbackLight&&light.isActiveAndEnabled&&light.type==LightType.Directional){sourceDirectional=true;break;}
  }
  if(fallbackLight)fallbackLight.enabled=!sourceDirectional;
  float ms=Time.unscaledDeltaTime*1000;report.frames++;sum+=ms;report.meanMs=(float)(sum/report.frames);report.maxMs=Mathf.Max(report.maxMs,ms);if(ms>33.334f)report.over33ms++;if(ms>50)report.over50ms++;
  if(Time.realtimeSinceStartup>=next){next=Time.realtimeSinceStartup+30;if(report.samples.Count>=120)report.samples.RemoveAt(0);report.samples.Add(new Sample{scene=scene.name,skybox=report.skybox,sun=report.sun,sourceCubemap=report.sourceCubemap,fallbackLight=fallbackLight&&fallbackLight.enabled,fog=RenderSettings.fog,fogMode=(int)RenderSettings.fogMode,fogColor=RenderSettings.fogColor,fogStart=RenderSettings.fogStartDistance,fogEnd=RenderSettings.fogEndDistance,fogDensity=RenderSettings.fogDensity,ambientLight=RenderSettings.ambientLight,ambientIntensity=RenderSettings.ambientIntensity,seconds=Time.realtimeSinceStartup-began,meanMs=report.meanMs,maxMs=report.maxMs,frames=report.frames,over33ms=report.over33ms,over50ms=report.over50ms,allocatedBytes=Profiler.GetTotalAllocatedMemoryLong(),reservedBytes=Profiler.GetTotalReservedMemoryLong(),managedBytes=Profiler.GetMonoUsedSizeLong(),gcCollections=GC.CollectionCount(0)});}
 }
 void OnRenderImage(RenderTexture source,RenderTexture destination){if(grade&&AndroidMaterialPresentation.report.enabled){Graphics.Blit(source,destination,grade);report.colorPasses++;}else Graphics.Blit(source,destination);}
 void OnDestroy(){if(grade)Destroy(grade);}
}
