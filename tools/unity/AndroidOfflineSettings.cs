using System;
using System.IO;
using UnityEngine;

// Android-only input preferences. No platform identity, unlocks or Steam files.
public sealed class AndroidOfflineSettings {
 [Serializable] public sealed class Values {public int version=1;public float deadzone=.18f,lookSensitivity=1;public bool invertY;}
 public static Values current=new Values();
 public readonly string directory;public string recovery="none";public Values values;
 public AndroidOfflineSettings(string directory){this.directory=directory;Directory.CreateDirectory(directory);Load();}
 public static void Validate(Values value){if(value==null||value.version!=1||float.IsNaN(value.deadzone)||float.IsInfinity(value.deadzone)||value.deadzone<.05f||value.deadzone>.4f||float.IsNaN(value.lookSensitivity)||float.IsInfinity(value.lookSensitivity)||value.lookSensitivity<.25f||value.lookSensitivity>3)throw new InvalidDataException("Android input preference schema/range invalid");}
 Values Read(string path){var value=new Values{version=0,deadzone=0,lookSensitivity=0};JsonUtility.FromJsonOverwrite(File.ReadAllText(path),value);Validate(value);return value;}
 void Load(){
  var path=Path.Combine(directory,"preferences.json");var backup=path+".backup";values=new Values();bool hasPrimary=File.Exists(path);
  if(hasPrimary){try{values=Read(path);recovery="validated-primary";return;}catch(Exception error){if(!(error is InvalidDataException)&&!(error is ArgumentException))throw;}}
  else if(!File.Exists(backup))return;
  var restored=Read(backup);var pending=path+".pending";Write(pending,restored);Read(pending);
  if(hasPrimary)File.Move(path,path+".rejected-"+Guid.NewGuid().ToString("N"));File.Move(pending,path);values=Read(path);recovery="validated-backup";
 }
 static void Write(string path,Values value){using(var stream=new FileStream(path,FileMode.Create,FileAccess.Write,FileShare.None)){using(var writer=new StreamWriter(stream,System.Text.Encoding.UTF8,1024,true)){writer.Write(JsonUtility.ToJson(value,true));writer.Flush();}stream.Flush(true);}}
 public void Save(){Validate(values);var path=Path.Combine(directory,"preferences.json");var pending=path+".pending";Write(pending,values);Read(pending);if(File.Exists(path)){Read(path);File.Replace(pending,path,path+".backup");}else File.Move(pending,path);values=Read(path);}
}
