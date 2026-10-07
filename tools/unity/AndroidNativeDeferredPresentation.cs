using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

// Owned lifecycle for privately recovered programs. Other families remain approximate.
public static class AndroidNativeDeferredPresentation {
 [Serializable] public class Variant {public string resource;public string[] keywords;}
 [Serializable] public class Manifest {public string[] features;public Variant[] variants;public int source_material_count;public string scope;}
 [Serializable] public class Report {public bool available,active,globalsRestored,pipelineRestored;public int variantCount,materialBindings;public string activeColorSpace,requestedPath,actualPath,error;public string scope="Native Standard/lighting candidate; static mono/noninstanced SH/HDR features; reflections and other families unresolved; no PC parity";}
 public static Report report=new Report();
 static Manifest manifest;static Shader lighting,previousLighting,previousReflections;static BuiltinShaderMode previousLightingMode,previousReflectionMode;static bool ownsPipeline;
 static readonly Dictionary<string,Shader> variants=new Dictionary<string,Shader>();
 static readonly string[] globals={"_GlobalWarpRamp","_EliteRamp"};
 static readonly string[] textures={"AndroidNativeWarpRamp","AndroidNativeEliteRamp"};
 static readonly List<Texture> previousTextures=new List<Texture>();
 static string Key(string[] keys){var copy=(string[])keys.Clone();Array.Sort(copy,StringComparer.Ordinal);return string.Join(",",copy);}
 public static void Begin(){
  Finish();report=new Report();var text=AndroidMaterialPresentation.LoadResource<TextAsset>("AndroidNativeStandardVariants","json");if(!text)return;
  try {
   manifest=JsonUtility.FromJson<Manifest>(text.text);if(manifest==null||manifest.features==null||manifest.variants==null||manifest.variants.Length==0)throw new Exception("Native shader manifest missing");
   foreach(var entry in manifest.variants){if(entry==null||entry.keywords==null||string.IsNullOrEmpty(entry.resource)||!entry.resource.StartsWith("AndroidNativeStandard",StringComparison.Ordinal))throw new Exception("Native material variant invalid");var shader=AndroidMaterialPresentation.LoadShader(entry.resource);if(!shader||!shader.isSupported)throw new Exception("Native material variant unavailable: "+entry.resource);variants.Add(Key(entry.keywords),shader);}
   lighting=AndroidMaterialPresentation.LoadShader("AndroidNativeDeferredLighting");if(!lighting||!lighting.isSupported)throw new Exception("Native custom lighting unavailable");
   if(QualitySettings.activeColorSpace!=ColorSpace.Linear)throw new Exception("Native HDR pipeline requires original linear color space");report.activeColorSpace=QualitySettings.activeColorSpace.ToString();
   for(int i=0;i<globals.Length;i++){var texture=AndroidMaterialPresentation.LoadResource<Texture>(textures[i],"png");if(!texture)throw new Exception("Native global ramp missing: "+textures[i]);previousTextures.Add(Shader.GetGlobalTexture(globals[i]));Shader.SetGlobalTexture(globals[i],texture);}
   previousLighting=GraphicsSettings.GetCustomShader(BuiltinShaderType.DeferredShading);previousLightingMode=GraphicsSettings.GetShaderMode(BuiltinShaderType.DeferredShading);
   previousReflections=GraphicsSettings.GetCustomShader(BuiltinShaderType.DeferredReflections);previousReflectionMode=GraphicsSettings.GetShaderMode(BuiltinShaderType.DeferredReflections);ownsPipeline=true;
   GraphicsSettings.SetCustomShader(BuiltinShaderType.DeferredShading,lighting);GraphicsSettings.SetShaderMode(BuiltinShaderType.DeferredShading,BuiltinShaderMode.UseCustom);
   // Unity's ordinary reflection pass interprets a different GBuffer packing.
   // Explicitly unavailable until the original custom reflection pass is recovered.
   GraphicsSettings.SetShaderMode(BuiltinShaderType.DeferredReflections,BuiltinShaderMode.Disabled);
   report.available=true;report.active=AndroidMaterialPresentation.report.enabled;report.variantCount=variants.Count;
  }catch(Exception e){report.error=e.Message;Finish();}
 }
 public static bool Apply(Material source,Material copy){
  if(!report.available||source.shader.name!="Hopoo Games/Deferred/Standard")return false;
  var selected=new List<string>();foreach(var feature in manifest.features)if(Array.IndexOf(source.shaderKeywords,feature)>=0)selected.Add(feature);
  Shader shader;if(!variants.TryGetValue(Key(selected.ToArray()),out shader))throw new Exception("Unmeasured native Standard feature combination: "+Key(selected.ToArray()));
  copy.shader=shader;copy.shaderKeywords=new string[0];copy.renderQueue=source.renderQueue;report.materialBindings++;return true;
 }
 public static void Configure(Camera view){
  if(!report.available||view.orthographic)return;
  report.active=AndroidMaterialPresentation.report.enabled;var path=report.active?RenderingPath.DeferredShading:RenderingPath.Forward;if(view.renderingPath!=path)view.renderingPath=path;
  if(report.active)view.allowHDR=true;
  report.requestedPath=view.renderingPath.ToString();report.actualPath=view.actualRenderingPath.ToString();
  if(report.active&&view.actualRenderingPath!=RenderingPath.DeferredShading)report.error="Native custom buffer pipeline fell back from DeferredShading";
 }
 public static void Finish(){
  for(int i=0;i<previousTextures.Count;i++)Shader.SetGlobalTexture(globals[i],previousTextures[i]);
  if(previousTextures.Count>0)report.globalsRestored=true;previousTextures.Clear();
  if(ownsPipeline){GraphicsSettings.SetCustomShader(BuiltinShaderType.DeferredShading,previousLighting);GraphicsSettings.SetShaderMode(BuiltinShaderType.DeferredShading,previousLightingMode);GraphicsSettings.SetCustomShader(BuiltinShaderType.DeferredReflections,previousReflections);GraphicsSettings.SetShaderMode(BuiltinShaderType.DeferredReflections,previousReflectionMode);report.pipelineRestored=true;ownsPipeline=false;}
  variants.Clear();manifest=null;lighting=null;report.active=false;
 }
}
