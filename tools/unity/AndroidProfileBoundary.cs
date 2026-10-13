using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.AsyncOperations;
using Zio;

public sealed partial class MovementBatchProbe {
 [Serializable] public sealed class AndroidProfileReport {public bool ready,created,roundTrip,cleaned,resultApplied,assistedExcluded;public string recovery,scope,error;public int saveFields,statFields,survivors,appliedRuns,baselineRuns,reconciledRuns,unlockables,achievements,persistentStatAchievements,earnedUnlocks,availableEarnedUnlocks,discoverySlots,discoveredPickups,assistedDiscoveriesExcluded;public string[] earnedLoot;public AndroidProgressionBoundary.AwardReport awards;public AndroidProgressionBoundary.DiscoveryReport discovery;public uint earnedCoins;public ulong kills;}
 sealed class AndroidProfileSaveSystem:SaveSystem {
  public AndroidOfflineProfile local;
  static Exception Unavailable(){return new NotSupportedException("Steam identity, cloud/profile import and platform history unavailable; owned Android profile only.");}
  protected override void ProcessFileOutputQueue(){if(local!=null&&local.profile.saveRequestPending)local.Save();}
  protected override void StartSave(UserProfile profile,bool blocking){if(local==null||!ReferenceEquals(profile,local.profile))throw Unavailable();local.Save();userProfile=local.profile;}
  protected override LoadUserProfileOperationResult LoadUserProfileFromDisk(IFileSystem files,UPath path){throw Unavailable();}
  public override void LoadUserProfiles(){throw Unavailable();}
  public override UserProfile LoadPrimaryProfile(){return local==null?null:local.profile;}
  public override string GetPlatformUsernameOrDefault(string defaultName){return defaultName;}
  public override UserProfile CreateProfile(IFileSystem files,string name,ulong platformUserID=0){throw Unavailable();}
  public override void SaveHistory(byte[] data,string name){throw Unavailable();}
  public override Dictionary<string,byte[]> LoadHistory(){throw Unavailable();}
 }
 AndroidProgressionBoundary androidProgression;
 AndroidProgressionBoundary.DiscoveryReport pendingDiscovery;
 Inventory discoveryInventory;Action<ItemIndex> discoveryItem;Action<EquipmentIndex,uint> discoveryEquipment;Action<KeyItemIndex> discoveryKeyItem;
 readonly Dictionary<FieldInfo,object> priorProfileCatalog=new Dictionary<FieldInfo,object>();
 readonly Dictionary<SurvivorDef,SurvivorIndex> priorProfileSurvivors=new Dictionary<SurvivorDef,SurvivorIndex>();
 ViewablesCatalog.Node profileViewablesRoot;ViewablesCatalog.Node[] priorProfileNodes;
 Dictionary<string,ViewablesCatalog.Node> profileViewablesMap,priorProfileViewables;
 UserProfile priorDefaultProfile;object priorProfileRedirects;bool ownsProfileContext;
 AsyncOperationHandle<UserProfileRedirectData> profileRedirectLease;bool ownsProfileRedirectLease;
 void PrepareAndroidProfile(CharacterBody player){
  if(!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return;
  r.profile=new AndroidProfileReport{scope="Original UserProfile/default/XML/statistics/loadout on Android only; recoverable local generations. Native persistent-stat achievements and earned local currency; platform reporting, login, Steam/cloud import and Rewired maps unavailable. Other achievement families remain deferred."};Save();
  Check(SurvivorCatalog.survivorCount==0&&UserProfile.defaultProfile==null&&priorProfileCatalog.Count==0,"Foreign survivor/profile context");
  var flags=BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic;
  foreach(var field in typeof(SurvivorCatalog).GetFields(flags))if(!field.IsLiteral&&!field.IsInitOnly&&(field.FieldType.IsArray||field.FieldType==typeof(SurvivorDef)||field.FieldType==typeof(global::ResourceAvailability)))priorProfileCatalog.Add(field,field.GetValue(null));
  profileViewablesRoot=(ViewablesCatalog.Node)RewardField(typeof(ViewablesCatalog),"rootNode").GetValue(null);priorProfileNodes=profileViewablesRoot.children.ToArray();
  profileViewablesMap=(Dictionary<string,ViewablesCatalog.Node>)RewardField(typeof(ViewablesCatalog),"fullNameToNodeMap").GetValue(null);priorProfileViewables=new Dictionary<string,ViewablesCatalog.Node>(profileViewablesMap);
  priorDefaultProfile=UserProfile.defaultProfile;priorProfileRedirects=RewardField(typeof(XmlUtility),"ValueReplacements").GetValue(null);Check(priorProfileRedirects==null,"Foreign profile redirect owner");ownsProfileContext=true;
  var definitions=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef,Array.Empty<SurvivorDef>());
  foreach(var def in definitions)priorProfileSurvivors.Add(def,def.survivorIndex);
  StaticCall(typeof(SurvivorCatalog),"SetSurvivorDefs",new object[]{definitions});SurvivorCatalog.availability.MakeAvailable();
  Check(SurvivorCatalog.defaultSurvivor&&definitions.All(def=>SurvivorCatalog.GetSurvivorDef(def.survivorIndex)==def&&SurvivorCatalog.GetBodyIndexFromSurvivorIndex(def.survivorIndex)!=BodyIndex.None),"Original survivor identity differs");
  androidProgression=new AndroidProgressionBoundary();
  var metadata=androidProgression.Prepare(WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.unlockableDef,Array.Empty<UnlockableDef>()));
  // This original initializer yields only scheduling nulls. Any new asynchronous
  // dependency must be handled explicitly rather than discarded by this drain.
  try{while(metadata.MoveNext())Check(metadata.Current==null,"Native progression metadata acquired an asynchronous dependency");}finally{var disposable=metadata as IDisposable;if(disposable!=null)disposable.Dispose();}
  r.profile.unlockables=androidProgression.unlockables;r.profile.achievements=androidProgression.achievements;r.profile.persistentStatAchievements=androidProgression.persistentStatDefinitions.Length;
  // Native rule choices capture these catalog unlock references, and replaying
  // saved RunReports later requires RuleBook default-value metadata.
  PrepareObjectiveRuleCatalog();
  // Pair the source serializer's otherwise unretained redirect-asset load with
  // the existing composed provider owner; no extra bundle or input copy.
  profileRedirectLease=Addressables.LoadAssetAsync<UserProfileRedirectData>("RoR2/Base/Core/UserProfileRedirects.asset");ownsProfileRedirectLease=true;
  var redirects=profileRedirectLease.WaitForCompletion();Check(profileRedirectLease.Status==AsyncOperationStatus.Succeeded&&redirects,"Original profile redirect asset unavailable");RewardField(typeof(XmlUtility),"ValueReplacements").SetValue(null,redirects);
  if(UserProfile.saveFields==null)UserProfile.GenerateSaveFieldFunctions();
  Check(PickupCatalog.pickupCount>0,"Native profile requires complete pickup metadata first");
  UserProfile.LoadDefaultProfile();Check(!UserProfile.defaultProfile.canSave&&!UserProfile.defaultProfile.loggedIn&&UserProfile.defaultProfile.coins==0,"Native default profile unexpectedly has platform/currency state");
  var local=new AndroidOfflineProfile(System.IO.Path.Combine(Application.persistentDataPath,"android-profile-v1"),resultsLedger.runs.Select(ProfileRunIdentity),candidate=>{r.profile.awards=androidProgression.ApplyPersistentStatCandidate(candidate);},(candidate,pickup)=>{pendingDiscovery=androidProgression.ApplyDiscoveryCandidate(candidate,pickup);});resultsSaveSystem.local=local;resultsSaveSystem.userProfile=local.profile;resultsSaveSystem.isInitialLoadFinished=true;
  r.profile.discoverySlots=((bool[])typeof(UserProfile).GetField("discoveredPickups",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(local.profile)).Length;Check(r.profile.discoverySlots==PickupCatalog.pickupCount,"Native profile discovery capacity differs from catalog");
  ReconcileAndroidProfile(local);resultsSaveSystem.userProfile=local.profile;
  r.profile.ready=true;r.profile.created=local.recovery=="new";r.profile.roundTrip=true;r.profile.recovery=local.recovery;r.profile.saveFields=UserProfile.saveFields.Length;r.profile.statFields=local.profile.statSheet.fields.Length;r.profile.survivors=SurvivorCatalog.survivorCount;ObserveAndroidProfile();Save();
  Check(player&&player.master&&player.master.inventory&&player.master.inventory==player.inventory&&!directorPlayer.networkUser&&discoveryInventory==null,"Owned offline player pickup discovery identity missing");
  discoveryInventory=player.inventory;
  discoveryItem=index=>RecordProfileDiscovery(PickupCatalog.FindPickupIndex(index));
  discoveryEquipment=(index,slot)=>RecordProfileDiscovery(PickupCatalog.FindPickupIndex(index));
  discoveryKeyItem=index=>RecordProfileDiscovery(PickupCatalog.FindPickupIndex(index));
  discoveryInventory.onItemAddedClient+=discoveryItem;discoveryInventory.onEquipmentChangedClient+=discoveryEquipment;discoveryInventory.onKeyItemAddedClient+=discoveryKeyItem;
 }
 void RecordProfileDiscovery(PickupIndex pickup){
  if(r.profile==null||!r.profile.ready||!pickup.isValid)return;
  Check(discoveryInventory!=null&&resultsSaveSystem.local!=null&&NetworkClient.active,"Original pickup event has no owned offline player context");
  if((r.nova!=null&&r.nova.diagnosticInput)||(r.debugAcceleration!=null&&r.debugAcceleration.everAssisted)){r.profile.assistedDiscoveriesExcluded++;return;}
  pendingDiscovery=null;
  if(resultsSaveSystem.local.DiscoverPickup(pickup)){Check(pendingDiscovery!=null&&pendingDiscovery.discovered,"Native discovery report missing after profile commit");r.profile.discovery=pendingDiscovery;resultsSaveSystem.userProfile=resultsSaveSystem.local.profile;r.profile.discoveredPickups++;ObserveAndroidProfile();Save();}
 }
 Guid ProfileRunIdentity(AndroidRunEntry entry){
  var stem=System.IO.Path.GetFileNameWithoutExtension(entry.file);Guid id;
  Check(stem.StartsWith("run-")&&Guid.TryParseExact(stem.Substring(4),"N",out id)&&id!=Guid.Empty,"Owned profile result identity invalid");return Guid.ParseExact(stem.Substring(4),"N");
 }
 void ReconcileAndroidProfile(AndroidOfflineProfile local){
  // A result is written before its profile delta. Replay only post-birth,
  // unassisted native reports when a crash or backup restore lost that delta.
  foreach(var entry in resultsLedger.runs){
   var id=ProfileRunIdentity(entry);if(entry.debugAssisted||!local.ShouldApply(id))continue;
   var report=RunReport.Load(System.IO.Path.GetFileNameWithoutExtension(entry.file));
   Check(report!=null&&report.runGuid==id&&report.gameEnding&&report.gameEnding.cachedName==entry.ending&&report.gameEnding.isWin==entry.win&&report.playerInfoCount==1&&report.GetPlayerInfo(0).statSheet!=null,"Owned native result reconciliation differs");
   if(local.ApplyResult(id,report.GetPlayerInfo(0).statSheet))r.profile.reconciledRuns++;
  }
 }
 void ObserveAndroidProfile(){if(r.profile==null||!r.profile.ready)return;r.profile.appliedRuns=resultsSaveSystem.local.appliedRuns;r.profile.baselineRuns=resultsSaveSystem.local.baselineRuns;r.profile.kills=resultsSaveSystem.local.profile.statSheet.GetStatValueULong(RoR2.Stats.StatDef.totalKills);androidProgression.ValidateProfile(resultsSaveSystem.local.profile);r.profile.earnedUnlocks=resultsSaveSystem.local.profile.statSheet.GetUnlockableCount();r.profile.earnedCoins=resultsSaveSystem.local.profile.coins;}
 void PersistAndroidProfileResult(bool assisted){
  if(r.profile==null||!r.profile.ready)return;
  r.profile.assistedExcluded=assisted;if(!assisted){r.profile.resultApplied=resultsSaveSystem.local.ApplyResult(resultsRunReport.runGuid,resultsRunReport.GetPlayerInfo(0).statSheet);resultsSaveSystem.userProfile=resultsSaveSystem.local.profile;}
  ObserveAndroidProfile();
 }
 void CleanupAndroidProfile(){
  if(!ownsProfileContext)return;
  if(!ReferenceEquals(discoveryInventory,null)){
   discoveryInventory.onItemAddedClient-=discoveryItem;discoveryInventory.onEquipmentChangedClient-=discoveryEquipment;discoveryInventory.onKeyItemAddedClient-=discoveryKeyItem;
   discoveryInventory=null;discoveryItem=null;discoveryEquipment=null;discoveryKeyItem=null;
  }
  try{if(resultsSaveSystem.local!=null&&resultsSaveSystem.local.profile.saveRequestPending)resultsSaveSystem.local.Save();}
  catch(Exception error){
   // Preserve the save failure but finish every owned teardown. A failed disk
   // write must not root a previous session's globals or permit its restart.
   if(r.profile!=null)r.profile.error=error.ToString();r.error+=" Android profile save during cleanup: "+error;r.success=false;
   if(string.IsNullOrEmpty(r.firstFailure)){r.firstFailure=error.GetBaseException().Message;r.firstFailurePhase="android-profile-cleanup-save";}
  }
  pendingDiscovery=null;if(androidProgression!=null){androidProgression.Dispose();androidProgression=null;}
  UserProfile.defaultProfile=priorDefaultProfile;RewardField(typeof(XmlUtility),"ValueReplacements").SetValue(null,priorProfileRedirects);
  if(ownsProfileRedirectLease){if(profileRedirectLease.IsValid())Addressables.Release(profileRedirectLease);ownsProfileRedirectLease=false;}
  foreach(var node in profileViewablesRoot.children.ToArray())if(!priorProfileNodes.Contains(node))node.SetParent(null);
  foreach(var key in profileViewablesMap.Keys.ToArray())if(!priorProfileViewables.ContainsKey(key))profileViewablesMap.Remove(key);
  Check(priorProfileViewables.All(pair=>profileViewablesMap.ContainsKey(pair.Key)&&ReferenceEquals(profileViewablesMap[pair.Key],pair.Value)),"Foreign viewable identity changed");
  foreach(var pair in priorProfileSurvivors)pair.Key.survivorIndex=pair.Value;foreach(var pair in priorProfileCatalog)pair.Key.SetValue(null,pair.Value);
  priorProfileSurvivors.Clear();priorProfileCatalog.Clear();resultsSaveSystem.local=null;resultsSaveSystem.userProfile=null;ownsProfileContext=false;if(r.profile!=null)r.profile.cleaned=true;
 }
}
