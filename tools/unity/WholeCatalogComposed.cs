using System;
using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;

// The expanded build gives old assets a shared bundle owner. Keep that owner
// loaded before the existing composed game deserializes its body/support assets.
public static class WholeCatalogComposed {
 static AssetBundle owned;
 public static IEnumerator Prepare(){
  if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))yield break;
  if(owned)throw new Exception("Shared whole-content dependency already owned");
  string path=Path.Combine(Application.persistentDataPath,"payload","whole-game-content");
  if(!File.Exists(path))throw new Exception("Shared whole-content dependency not synchronized");
  if(AssetBundle.GetAllLoadedAssetBundles().Any(x=>x.name=="whole-game-content"))throw new Exception("Shared dependency has a foreign owner");
  var load=AssetBundle.LoadFromFileAsync(path);yield return load;owned=load.assetBundle;
  if(!owned)throw new Exception("Shared whole-content dependency failed to load");
 }
 public static void Release(){if(owned){owned.Unload(true);owned=null;}}
}
