using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

// Owned Android rendering approximations. Original assets and simulation stay intact.
public static class AndroidMaterialPresentation {
 [Serializable] public class Report {public bool enabled;public int surfaces,terrain,particles,nativeParticles,opaqueClouds,intersection,intersectionKeywordBindings,distortion,water,snow,foliage,billboards,normalMaps,emissionMaps;public string shaderSource,error,scope="Original Unity particle families retained; source intersection keywords bound; custom families remain approximate unless a separate recovered-program receipt supplies them; no original shader parity";}
 sealed class Binding {public Material material;public Shader enhanced,fallback;}
 static readonly List<Binding> bindings=new List<Binding>();
 public static Report report=new Report();
 static AssetBundle shaders;
 public static void Begin(bool enabled){Finish();report=new Report{enabled=enabled,shaderSource="APK"};var path=Path.Combine(Application.persistentDataPath,"payload/android-presentation-lab");if(File.Exists(path)){shaders=AssetBundle.LoadFromFile(path);if(shaders)report.shaderSource="payload";else report.error="Android presentation payload failed to load";}}
 public static Shader LoadShader(string name){return shaders?shaders.LoadAsset<Shader>("Assets/LabLoadingScene/Resources/"+name+".shader"):Resources.Load<Shader>(name);}
 public static void SetEnabled(bool enabled){report.enabled=enabled;foreach(var b in bindings)if(b.material)b.material.shader=enabled?b.enhanced:b.fallback;}
 public static void Apply(Material source,Material copy){
  if(!source||!copy)return;
  string name=source.shader.name;bool terrain=name.IndexOf("Triplanar",StringComparison.OrdinalIgnoreCase)>=0;
  bool nativeParticle=name=="Mobile/Particles/Alpha Blended"||name=="Particles/Standard Unlit"||name=="Legacy Shaders/Particles/Additive"||name=="Legacy Shaders/Particles/Additive (Soft)";
  if(nativeParticle){
   copy.shader=source.shader;copy.shaderKeywords=source.shaderKeywords;copy.renderQueue=source.renderQueue;
   if(!copy.shader.isSupported)report.error="Original Unity particle shader unavailable: "+name;
   bindings.Add(new Binding{material=copy,enhanced=source.shader,fallback=source.shader});report.nativeParticles++;return;
  }
  bool cloud=name.IndexOf("Cloud",StringComparison.OrdinalIgnoreCase)>=0;
  bool opaqueCloud=name=="Hopoo Games/FX/Opaque Cloud Remap",distortion=name=="Hopoo Games/FX/Distortion";
  bool intersection=name=="Hopoo Games/FX/Cloud Intersection Remap";
  bool water=name.IndexOf("Water",StringComparison.OrdinalIgnoreCase)>=0;
  bool snow=name.IndexOf("Snow",StringComparison.OrdinalIgnoreCase)>=0;
  bool foliage=name.IndexOf("Speedtree",StringComparison.OrdinalIgnoreCase)>=0;
  bool billboard=name=="Nature/SpeedTree Billboard";
  var shader=LoadShader(billboard?"AndroidBillboardPresentation":terrain?"AndroidTerrainPresentation":opaqueCloud?"AndroidOpaqueParticlePresentation":intersection?"AndroidIntersectionPresentation":distortion?"AndroidDistortionPresentation":cloud?"AndroidParticlePresentation":water?"AndroidWaterPresentation":"AndroidSurfacePresentation");
  if(!shader||!shader.isSupported){report.error="Android material family unavailable: "+name;return;}
  if(billboard){
   // BillboardAsset vertices are atlas-space. Keep the dedicated geometry path
   // for both toggle settings rather than substituting the ordinary mesh shader.
   copy.shader=shader;var keys=new List<string>();
   foreach(var key in source.shaderKeywords)if(key=="EFFECT_BUMP"||key=="EFFECT_HUE_VARIATION"||key=="BILLBOARD_FACE_CAMERA_POS")keys.Add(key);
   copy.shaderKeywords=keys.ToArray();report.billboards++;
   bindings.Add(new Binding{material=copy,enhanced=shader,fallback=shader});return;
  }
  var fallback=copy.shader;copy.shader=shader;copy.shaderKeywords=new string[0];
  if(intersection){
   // Shipped keyword selections can disagree with saved inspector toggle values.
   // The recovered source dispatches these features explicitly because this
   // adapter clears the cloned material's legacy keyword set above.
   copy.SetFloat("_TriplanarOn",Array.IndexOf(source.shaderKeywords,"TRIPLANAR")>=0?1:0);
   copy.SetFloat("_FadeFromVertexColorsOn",Array.IndexOf(source.shaderKeywords,"FADE_FROM_VERTEX_COLORS")>=0?1:0);
   report.intersectionKeywordBindings++;
  }
  if(distortion){
   copy.SetFloat("_AndroidMaskEnabled",source.HasProperty("_MaskTex")&&source.GetTexture("_MaskTex")?1:0);
   // These measured materials use either the exported default or explicit4000.
   // Repair the missing native Transparent+2000 default, preserve explicit queues.
   copy.renderQueue=source.renderQueue==source.shader.renderQueue?5000:source.renderQueue;
   report.distortion++;bindings.Add(new Binding{material=copy,enhanced=shader,fallback=fallback});if(!report.enabled)copy.shader=fallback;return;
  }
  copy.SetFloat("_AndroidNormalEnabled",source.HasProperty("_NormalTex")&&source.GetTexture("_NormalTex")?1:0);
  if(source.HasProperty("_NormalTex")&&source.GetTexture("_NormalTex"))report.normalMaps++;
  if(source.HasProperty("_EmTex")&&source.GetTexture("_EmTex"))report.emissionMaps++;
  if(!terrain&&!cloud&&!water){
   copy.SetFloat("_EnableCutout",foliage?1:source.HasProperty("_EnableCutout")?source.GetFloat("_EnableCutout"):0);
   copy.SetFloat("_AndroidSnowEnabled",snow?1:0);copy.SetFloat("_EmissionEnabled",1);
   if(snow)report.snow++;if(foliage)report.foliage++;
  }
  if(cloud){
   // Intersection shaders consume these names. The material can also retain
   // obsolete standard-shader blend values that must not override them.
   if(source.HasProperty("_SrcBlendFloat"))copy.SetFloat("_SrcBlend",source.GetFloat("_SrcBlendFloat"));
   if(source.HasProperty("_DstBlendFloat"))copy.SetFloat("_DstBlend",source.GetFloat("_DstBlendFloat"));
   copy.SetFloat("_AndroidRemapEnabled",source.HasProperty("_RemapTex")&&source.GetTexture("_RemapTex")?1:0);
   copy.SetFloat("_AndroidCloud1Enabled",source.HasProperty("_Cloud1Tex")&&source.GetTexture("_Cloud1Tex")?1:0);
   copy.SetFloat("_AndroidCloud2Enabled",source.HasProperty("_Cloud2Tex")&&source.GetTexture("_Cloud2Tex")?1:0);
    copy.renderQueue=opaqueCloud?(source.renderQueue==source.shader.renderQueue?2450:source.renderQueue):3000;
    if(opaqueCloud)report.opaqueClouds++;else if(intersection)report.intersection++;else report.particles++;
  }else if(water){
   if(source.HasProperty("_BumpMap")&&source.GetTexture("_BumpMap")){copy.SetTexture("_NormalTex",source.GetTexture("_BumpMap"));copy.SetTextureScale("_NormalTex",source.GetTextureScale("_BumpMap"));}
   copy.renderQueue=3000;report.water++;
  }else if(terrain)report.terrain++;else report.surfaces++;
  bindings.Add(new Binding{material=copy,enhanced=shader,fallback=fallback});if(!report.enabled)copy.shader=fallback;
 }
 public static void Finish(){bindings.Clear();if(shaders){shaders.Unload(false);shaders=null;}}
}
