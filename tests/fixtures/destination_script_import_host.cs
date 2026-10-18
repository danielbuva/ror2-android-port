// Authored host doubles; no Unity editor is started and no game inputs are read.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace UnityEngine {
 public class Object {}
 public class Component : Object { public GameObject gameObject; public T[] GetComponents<T>() {return gameObject.GetComponents<T>();} }
 public class Transform : Component {}
 public class GameObject : Object {
  public int missing;public readonly List<Component> components=new List<Component>();
  public GameObject(){components.Add(new Transform{gameObject=this});}
  public T[] GetComponentsInChildren<T>(bool inactive){Host.Check(inactive,"includes inactive children");return components.OfType<T>().ToArray();}
  public T[] GetComponents<T>(){return components.OfType<T>().ToArray();}
 }
}
namespace RoR2.UI { public class TimerText : Component {public UnityEngine.Object targetLabel;} }
namespace UnityEditor {
 [Flags] public enum ImportAssetOptions {ForceUpdate=1,ForceSynchronousImport=2}
 public static class EditorApplication {public static bool isCompiling,isUpdating,isPlaying;}
 public class AssetImporter {public static AssetImporter GetAtPath(string path){return AssetDatabase.importers[path];}}
 public class PluginImporter : AssetImporter {public bool isNativePlugin;}
 public class MonoScript : UnityEngine.Object {public string name,guid;public long localId;public Type GetClass(){return Host.imported?typeof(RoR2.UI.TimerText):null;}}
 public static class GameObjectUtility {public static int GetMonoBehavioursWithMissingScriptCount(GameObject obj){return obj.missing;}}
 public class SerializedProperty {public UnityEngine.Object objectReferenceValue;}
 public class SerializedObject {
  readonly RoR2.UI.TimerText timer;
  public SerializedObject(Component component){timer=(RoR2.UI.TimerText)component;}
  public SerializedProperty FindProperty(string name){Host.Check(name=="targetLabel","targetLabel field");return new SerializedProperty{objectReferenceValue=timer.targetLabel};}
 }
 public static class AssetDatabase {
  public static readonly Dictionary<string,AssetImporter> importers=new Dictionary<string,AssetImporter>();
  public static readonly Dictionary<string,string[]> deps=new Dictionary<string,string[]>();
  public static readonly Dictionary<string,GameObject> prefabs=new Dictionary<string,GameObject>();
  public static readonly List<string> imports=new List<string>();
  public static string[] GetAllAssetPaths(){return importers.Keys.Concat(prefabs.Keys).Concat(new[]{Host.font,Host.scene,Host.unrelated}).ToArray();}
  public static string[] GetDependencies(string path,bool recursive){return GetDependencies(new[]{path},recursive);}
  public static string[] GetDependencies(string[] paths,bool recursive){
   var result=new HashSet<string>(paths);Action<string> visit=null;
   visit=path=>{string[] children;if(!deps.TryGetValue(path,out children))return;foreach(string child in children)if(result.Add(child)&&recursive)visit(child);};
   foreach(string path in paths)visit(path);return result.ToArray();
  }
  public static void ImportAsset(string path,ImportAssetOptions options){
   Host.Check(options==(ImportAssetOptions.ForceUpdate|ImportAssetOptions.ForceSynchronousImport),"forced synchronous import");
   imports.Add(path);if(path.EndsWith(".dll"))Host.imported=true;
   else Host.Check(Host.imported,"plugins imported before assets");
  }
  public static T LoadAssetAtPath<T>(string path) where T:class {return prefabs[path] as T;}
  public static UnityEngine.Object[] LoadAllAssetsAtPath(string path){return new UnityEngine.Object[]{new MonoScript{name="TimerText",guid=path,localId=123}};}
  public static bool TryGetGUIDAndLocalFileIdentifier(MonoScript script,out string guid,out long localId){guid=script.guid;localId=script.localId;return true;}
 }
}
public static class Host {
 public static bool imported;
 public const string hud="Assets/LabLoadingScene/Resources/RecoveredUI/Hud.prefab",menu="Assets/LabLoadingScene/Resources/RecoveredUI/Menu.prefab",
  font="Assets/Fonts/TMP.asset",scene="Assets/Stage.unity",unrelated="Assets/Other.asset";
 public static void Check(bool passed,string name){if(!passed)throw new Exception(name);}
 public static void Main(){
  var plugins=new[]{"Assets/Plugins/TMP.dll","Assets/LabLoadingScene/Plugins/RoR2.dll","Assets/Other/Derived.dll"};
  foreach(string path in plugins)AssetDatabase.importers[path]=new PluginImporter();
  AssetDatabase.importers["Assets/Native.dll"]=new PluginImporter{isNativePlugin=true};
  var hudRoot=new GameObject();var timer=new RoR2.UI.TimerText{gameObject=hudRoot,targetLabel=new UnityEngine.Object()};hudRoot.components.Add(timer);
  AssetDatabase.prefabs[hud]=hudRoot;AssetDatabase.prefabs[menu]=new GameObject();AssetDatabase.prefabs["Assets/Other.prefab"]=new GameObject{missing=3};
  AssetDatabase.deps[hud]=new[]{font,plugins[1]};AssetDatabase.deps[font]=new[]{plugins[0]};
  AssetDatabase.deps[menu]=new[]{plugins[2]};
  foreach(string path in AssetDatabase.GetAllAssetPaths()){Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,"fixture");}
  // Scenes are audited from text: one resolved reference, two unresolved (one null script).
  File.WriteAllText(scene,"  m_Script: {fileID: 123, guid: "+plugins[0]+", type: 3}\n  m_Script: {fileID: 9, guid: "+new string('a',32)+", type: 3}\n  m_Script: {fileID: 0}\n");
  var selection=new[]{hud,menu,scene,"Assets/Other.prefab",unrelated};
  var audit=JObject.Parse(LabBuild.InspectDestinationScripts(selection));Check((bool)audit["uiValid"],"initial ui");
  Check(audit["monoScripts"].All(row=>row["type"].Type==JTokenType.Null),"unresolved initial scripts");
  LabBuild.Repair(selection);
  Check(AssetDatabase.imports.Take(3).OrderBy(x=>x).SequenceEqual(plugins.OrderBy(x=>x)),"all managed plugins, including alternate directories");
  Check(!AssetDatabase.imports.Contains("Assets/Native.dll")&&!AssetDatabase.imports.Contains(unrelated),"unrelated imports excluded");
  Check(AssetDatabase.imports.IndexOf(font)<AssetDatabase.imports.IndexOf(hud),"font before HUD");
  int count=AssetDatabase.imports.Count;
  audit=JObject.Parse(LabBuild.InspectDestinationScripts(selection));
  Check((bool)audit["uiValid"]&&(int)audit["missingScripts"]==5,"non-UI counts preserved");
  Check(audit["assets"].Any(row=>(string)row["path"]==scene&&(int)row["missingScripts"]==2),"scene counts");
  Check(audit["monoScripts"].All(row=>row["type"].Type==JTokenType.String),"resolved plugin identities");
  Check(count==AssetDatabase.imports.Count,"audit performs no imports");
  timer.targetLabel=null;audit=JObject.Parse(LabBuild.InspectDestinationScripts(selection));Check(!(bool)audit["uiValid"],"null TimerText blocks");
  timer.targetLabel=new UnityEngine.Object();hudRoot.missing=114;audit=JObject.Parse(LabBuild.InspectDestinationScripts(selection));Check(!(bool)audit["uiValid"],"HUD missing scripts block");hudRoot.missing=0;
  AssetDatabase.prefabs[menu].missing=1;audit=JObject.Parse(LabBuild.InspectDestinationScripts(selection));Check(!(bool)audit["uiValid"],"Menu missing scripts block");AssetDatabase.prefabs[menu].missing=0;
  EditorApplication.isCompiling=true;bool refused=false;try{LabBuild.InspectDestinationScripts(selection);}catch(InvalidOperationException){refused=true;}Check(refused,"compilation gate");
  Console.WriteLine("destination import/audit host contracts passed");
 }
}
