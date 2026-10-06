using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

// Owned Android rendering approximations. Original assets and simulation stay intact.
public static class AndroidMaterialPresentation {
 [Serializable] public class Report {public bool enabled;public int surfaces,terrain,particles,water,snow,foliage,normalMaps,emissionMaps;public string shaderSource,error,scope="Android authored lighting/normal/emission/snow/particle approximations; no original shader parity";}
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
  bool cloud=name.IndexOf("Cloud",StringComparison.OrdinalIgnoreCase)>=0;
  bool water=name.IndexOf("Water",StringComparison.OrdinalIgnoreCase)>=0;
  bool snow=name.IndexOf("Snow",StringComparison.OrdinalIgnoreCase)>=0;
  bool foliage=name.IndexOf("Speedtree",StringComparison.OrdinalIgnoreCase)>=0;
  var shader=LoadShader(terrain?"AndroidTerrainPresentation":cloud?"AndroidParticlePresentation":water?"AndroidWaterPresentation":"AndroidSurfacePresentation");
  if(!shader||!shader.isSupported){report.error="Android material family unavailable: "+name;return;}
  var fallback=copy.shader;copy.shader=shader;copy.shaderKeywords=new string[0];
  copy.SetFloat("_AndroidNormalEnabled",source.HasProperty("_NormalTex")&&source.GetTexture("_NormalTex")?1:0);
  if(source.HasProperty("_NormalTex")&&source.GetTexture("_NormalTex"))report.normalMaps++;
  if(source.HasProperty("_EmTex")&&source.GetTexture("_EmTex"))report.emissionMaps++;
  if(!terrain&&!cloud&&!water){
   copy.SetFloat("_EnableCutout",foliage?1:source.HasProperty("_EnableCutout")?source.GetFloat("_EnableCutout"):0);
   copy.SetFloat("_AndroidSnowEnabled",snow?1:0);copy.SetFloat("_EmissionEnabled",1);
   if(snow)report.snow++;if(foliage)report.foliage++;
  }
  if(cloud){
   copy.SetFloat("_AndroidRemapEnabled",source.HasProperty("_RemapTex")&&source.GetTexture("_RemapTex")?1:0);
   copy.SetFloat("_AndroidCloud1Enabled",source.HasProperty("_Cloud1Tex")&&source.GetTexture("_Cloud1Tex")?1:0);
   copy.SetFloat("_AndroidCloud2Enabled",source.HasProperty("_Cloud2Tex")&&source.GetTexture("_Cloud2Tex")?1:0);
   copy.renderQueue=3000;report.particles++;
  }else if(water){
   if(source.HasProperty("_BumpMap")&&source.GetTexture("_BumpMap")){copy.SetTexture("_NormalTex",source.GetTexture("_BumpMap"));copy.SetTextureScale("_NormalTex",source.GetTextureScale("_BumpMap"));}
   copy.renderQueue=3000;report.water++;
  }else if(terrain)report.terrain++;else report.surfaces++;
  bindings.Add(new Binding{material=copy,enhanced=shader,fallback=fallback});if(!report.enabled)copy.shader=fallback;
 }
 public static void Finish(){bindings.Clear();if(shaders){shaders.Unload(false);shaders=null;}}
}
