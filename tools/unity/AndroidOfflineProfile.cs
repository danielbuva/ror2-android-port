using System;
using System.Collections.Generic;
using System.IO;
using Path=System.IO.Path;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Xml;
using System.Xml.Linq;
using RoR2;
using RoR2.Stats;
using UnityEngine;

// A local, unauthenticated profile. Native XML and original statistics are kept
// in one recoverable generation with the result IDs already applied to it.
// Steam/cloud profiles and Rewired controller-map import are deliberately absent.
public sealed class AndroidOfflineProfile {
 [Serializable] sealed class Generation {public int version=2;public string xml,sha256;public List<string> appliedRuns=new List<string>(),baselineRuns=new List<string>();}
 public readonly string directory;public string recovery="new";public UserProfile profile {get;private set;}
 Generation generation;readonly List<string> initialBaseline;readonly bool baselineProvided;readonly Action<UserProfile> progression;
 public int appliedRuns {get{return generation.appliedRuns.Count;}}
 public int baselineRuns {get{return generation.baselineRuns.Count;}}
 string primary {get{return Path.Combine(directory,"profile.json");}}
 public AndroidOfflineProfile(string directory,IEnumerable<Guid> baselineRuns=null,Action<UserProfile> progression=null){this.directory=directory;this.progression=progression;baselineProvided=baselineRuns!=null;initialBaseline=(baselineRuns??Enumerable.Empty<Guid>()).Select(id=>{if(id==Guid.Empty)throw new ArgumentException("Baseline run identity is empty");return id.ToString("N");}).Distinct().OrderBy(id=>id,StringComparer.Ordinal).ToList();Directory.CreateDirectory(directory);Load();EnsureBaselineBackup();}
 static string Hash(Generation value){var text=value.xml+"\n"+string.Join("\n",value.appliedRuns);if(value.version==2)text="2\n"+value.xml.Length+"\n"+text+"\nbaseline\n"+string.Join("\n",value.baselineRuns);using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-","").ToLowerInvariant();}
 static bool ValidIds(List<string> ids){return ids!=null&&ids.Distinct().Count()==ids.Count&&ids.All(id=>{Guid result;return id!=null&&Guid.TryParseExact(id,"N",out result)&&result!=Guid.Empty&&id==result.ToString("N");});}
 static XDocument Parse(string text){using(var input=new StringReader(text))using(var reader=XmlReader.Create(input,new XmlReaderSettings{DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null}))return XDocument.Load(reader);}
 static UnlockableDef RequireUnlock(string name){
  var definition=string.IsNullOrEmpty(name)?null:UnlockableCatalog.GetUnlockableDef(name);
  if(!definition||definition.cachedName!=name||definition.index==UnlockableIndex.None||UnlockableCatalog.GetUnlockableDef(definition.index)!=definition)throw new InvalidOperationException("Original profile unlock catalog unavailable or incompatible: "+name);
  return definition;
 }
 static UnlockableDef[] ProfileUnlocks(UserProfile value){
  var result=new UnlockableDef[value.statSheet.GetUnlockableCount()];
  for(int i=0;i<result.Length;i++){
   var definition=value.statSheet.GetUnlockable(i);
   if(!definition||RequireUnlock(definition.cachedName)!=definition||definition.index!=value.statSheet.GetUnlockableIndex(i))throw new InvalidOperationException("Original profile unlock index/name identity differs");
   result[i]=definition;
  }
  if(result.Distinct().Count()!=result.Length)throw new InvalidOperationException("Original profile contains duplicate unlock identities");return result;
 }
 static bool SameUnlocks(UnlockableDef[] first,UnlockableDef[] second){return first.Select(def=>def.cachedName).SequenceEqual(second.Select(def=>def.cachedName))&&first.Select(def=>def.index).SequenceEqual(second.Select(def=>def.index));}
 static UserProfile Decode(Generation value){
  if(value==null||(value.version!=1&&value.version!=2)||string.IsNullOrEmpty(value.xml)||!ValidIds(value.appliedRuns)||(value.version==2&&(!ValidIds(value.baselineRuns)||value.baselineRuns.Intersect(value.appliedRuns).Any()))||value.sha256!=Hash(value))throw new InvalidDataException("Android profile generation checksum/schema invalid");
  var doc=Parse(value.xml);if(doc.Root==null||doc.Root.Name!="UserProfile")throw new InvalidDataException("Original profile root invalid");
  foreach(var field in UserProfile.saveFields)if(doc.Root.Elements(field.fieldName).Count()!=1)throw new InvalidDataException("Original profile field missing/duplicated: "+field.fieldName);
  // This store does not import PC or legacy Rewired maps. Empty native fields
  // round-trip to null; the Android input preferences keep their separate owner.
  foreach(var name in new[]{"keyboardMap","mouseMap","joystickMap"})if(!string.IsNullOrEmpty(doc.Root.Element(name).Value))throw new InvalidDataException("Rewired profile map import unavailable");
  var hardware=JsonUtility.FromJson<SaveFieldAttribute.HardwareMapWrapper>(doc.Root.Element("HardwareJoystickMaps2").Value);
  if(hardware.Entries==null||hardware.Entries.Length!=0)throw new InvalidDataException("Rewired hardware map import unavailable");
  // Native XML silently drops unknown unlock names. Catalog incompatibility is
  // not file corruption: stop without replacing this generation with a backup.
  if(doc.Root.Elements("stats").Count()!=1)throw new InvalidDataException("Original profile statistics field missing/duplicated");
  var unlockElements=doc.Root.Element("stats").Elements("unlock").ToArray();
  if(unlockElements.Any(element=>element.HasElements)||unlockElements.Select(element=>element.Value).Distinct().Count()!=unlockElements.Length)throw new InvalidOperationException("Original profile unlock names malformed or duplicated");
  var expectedUnlocks=unlockElements.Select(element=>RequireUnlock(element.Value)).ToArray();
  if(AchievementManager.readOnlyAchievementIdentifiers.Count>0)foreach(var name in new[]{"achievementsList","unviewedAchievementsList"})foreach(var identifier in doc.Root.Element(name).Value.Split(new[]{' '},StringSplitOptions.RemoveEmptyEntries))if(AchievementManager.GetAchievementDef(identifier)==null)throw new InvalidOperationException("Original profile achievement catalog incompatible: "+identifier);
  var loaded=UserProfile.FromXml(doc);
  if(loaded.statSheet==null||loaded.statSheet.fields.Length==0||loaded.loggedIn||loaded.saveID!=0||loaded.isClaimed||loaded.keyboardMap!=null||loaded.mouseMap!=null||loaded.joystickMap!=null||loaded.HardwareJoystickMaps2.Count!=0)throw new InvalidDataException("Original Android profile contract differs");
  if(!SameUnlocks(expectedUnlocks,ProfileUnlocks(loaded)))throw new InvalidOperationException("Original profile unlock identity changed during XML decode");
  return loaded;
 }
 static Generation Encode(UserProfile profile,IEnumerable<string> runs,IEnumerable<string> baseline){var value=new Generation{xml=UserProfile.ToXml(profile).ToString(SaveOptions.DisableFormatting),appliedRuns=runs.ToList(),baselineRuns=baseline.ToList()};value.sha256=Hash(value);return value;}
 static Generation Read(string path){var value=new Generation{version=0,appliedRuns=null,baselineRuns=null};JsonUtility.FromJsonOverwrite(File.ReadAllText(path),value);Decode(value);return value;}
 static void Write(string path,Generation value){using(var stream=new FileStream(path,FileMode.Create,FileAccess.Write,FileShare.None)){using(var writer=new StreamWriter(stream,new UTF8Encoding(false),1024,true)){writer.Write(JsonUtility.ToJson(value));writer.Flush();}stream.Flush(true);}}
 static bool IsCorrupt(Exception error){return error is InvalidDataException||error is XmlException||error is ArgumentException;}
 static Generation ReadRecoverable(string path){try{return Read(path);}catch(Exception error){if(!IsCorrupt(error))throw;return null;}}
 static void Reject(string path){if(File.Exists(path))File.Move(path,path+".rejected-"+Guid.NewGuid().ToString("N"));}
 void Adopt(Generation value,string source){generation=value;profile=Decode(value);profile.canSave=true;recovery=source;if(value.version==1){if(!baselineProvided)throw new InvalidOperationException("Owned run-ledger baseline required for profile migration");generation=new Generation{xml=value.xml,appliedRuns=value.appliedRuns.ToList(),baselineRuns=initialBaseline.Except(value.appliedRuns).ToList()};generation.sha256=Hash(generation);ReplacePrimary(generation);recovery+="-migrated-v1";}}
 void ReplacePrimary(Generation next){var pending=primary+".pending";Write(pending,next);Read(pending);if(File.Exists(primary)){Read(primary);File.Replace(pending,primary,primary+".backup");}else File.Move(pending,primary);generation=Read(primary);}
 void EnsureBaselineBackup(){
  // Migration is complete only when recovery cannot resurrect a baseline-free
  // generation. A restart between the two replacements finishes this step.
  var path=primary+".backup";var prior=File.Exists(path)?ReadRecoverable(path):null;
  if(prior!=null&&prior.version==2&&prior.baselineRuns.SequenceEqual(generation.baselineRuns))return;
  var pending=path+".pending";Write(pending,generation);Read(pending);
  if(File.Exists(path))File.Replace(pending,path,path+".rejected-"+Guid.NewGuid().ToString("N"));else File.Move(pending,path);
  Read(path);
 }
 void Load(){
  if(File.Exists(primary)){var current=ReadRecoverable(primary);if(current!=null){Adopt(current,"validated-primary");return;}}
  string backup=primary+".backup",pending=primary+".pending";
  foreach(var source in new[]{backup,pending})if(File.Exists(source)){
   // A good primary wins over interrupted pending output. If it is absent/bad,
   // prefer the verified previous generation; never replace it with corrupt data.
   var restored=ReadRecoverable(source);if(restored==null)continue;
   string recovered=primary+".recovering";Write(recovered,restored);Read(recovered);
   Reject(primary);File.Move(recovered,primary);Adopt(Read(primary),source==backup?"validated-backup":"validated-pending");return;
  }
  if(File.Exists(primary)||File.Exists(backup)||File.Exists(pending))throw new InvalidDataException("Android profile corrupt and no verified recovery generation exists");
  profile=UserProfile.FromXml(UserProfile.ToXml(UserProfile.defaultProfile));profile.canSave=true;Save();
 }
 void Commit(UserProfile candidate,IEnumerable<string> ids){
  var unlocks=ProfileUnlocks(candidate);var next=Encode(candidate,ids,generation==null?initialBaseline:generation.baselineRuns);var roundTrip=Decode(next);
  if(UserProfile.saveFields.Any(field=>field.getter(roundTrip)!=field.getter(candidate))||roundTrip.statSheet.fields.Length!=candidate.statSheet.fields.Length||!roundTrip.statSheet.fields.Select(field=>field.ToString()).SequenceEqual(candidate.statSheet.fields.Select(field=>field.ToString()))||!XNode.DeepEquals(roundTrip.loadout.ToXml("loadout"),candidate.loadout.ToXml("loadout")))throw new InvalidDataException("Native Android profile XML round trip differs");
  if(!SameUnlocks(unlocks,ProfileUnlocks(roundTrip)))throw new InvalidOperationException("Original profile unlock identity changed during commit");
  ReplacePrimary(next);profile=candidate;profile.canSave=true;profile.saveRequestPending=false;
 }
 public void Save(){Commit(profile,generation==null?Enumerable.Empty<string>():generation.appliedRuns);}
 public bool ShouldApply(Guid run){if(run==Guid.Empty)throw new ArgumentException("Genuine run identity required");var id=run.ToString("N");return !generation.baselineRuns.Contains(id)&&!generation.appliedRuns.Contains(id);}
 public bool ApplyResult(Guid run,StatSheet delta){
  if(run==Guid.Empty||delta==null)throw new ArgumentException("Genuine run identity/statistics required");var id=run.ToString("N");if(!ShouldApply(run))return false;
  var candidate=Decode(Encode(profile,generation.appliedRuns,generation.baselineRuns));candidate.canSave=false;candidate.ApplyDeltaStatSheet(delta);progression?.Invoke(candidate);Commit(candidate,generation.appliedRuns.Concat(new[]{id}));return true;
 }
}
