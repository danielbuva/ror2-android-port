using System;
using System.IO;
using UnityEditor;
using UnityEngine;

// Restore one measured input metadata value; no assembly or runtime-method patch.
public static class CharacterMotorOrderProbe {
 [Serializable] class Request { public int order; }
 [Serializable] class Receipt { public string type; public int before,after; }
 [MenuItem("Porting Lab/Restore Character Motor Order")]
 static void Restore() {
  const string root="Assets/LabLoadingScene/";
  var request=JsonUtility.FromJson<Request>(File.ReadAllText(root+"Editor/character-motor-order.json"));
  MonoScript selected=null;
  foreach(var asset in AssetDatabase.LoadAllAssetsAtPath(root+"Plugins/RoR2.dll")) {
   var script=asset as MonoScript;
   if(script!=null&&script.GetClass()!=null&&script.GetClass().FullName=="RoR2.CharacterMotor") {
    if(selected!=null)throw new Exception("Ambiguous CharacterMotor script");selected=script;
   }
  }
  if(selected==null)throw new Exception("CharacterMotor script missing");
  int before=MonoImporter.GetExecutionOrder(selected);
  MonoImporter.SetExecutionOrder(selected,request.order);
  int after=MonoImporter.GetExecutionOrder(selected);
  if(after!=request.order)throw new Exception("Execution order did not persist");
  File.WriteAllText(root+"Editor/character-motor-order-result.json",JsonUtility.ToJson(new Receipt {type="RoR2.CharacterMotor",before=before,after=after},true));
 }
}
