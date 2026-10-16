using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Assets.RoR2.Scripts.Platform;
using HG;
using RoR2;
using RoR2.Achievements;
using RoR2.Stats;
using UnityEngine;
using UnityEngine.Networking;

// Calls the shipped catalog and achievement implementations. This owner supplies
// neither a platform login nor an entitlement resolver. Awards target only an
// unsaved transaction clone; platform notifications and transport stay unavailable.
public sealed class AndroidProgressionBoundary : IDisposable {
 [Serializable] public sealed class ThresholdObservation {
  public string identifier,reward,stat,blocked;
  public ulong progress,requirement;
  public uint lunarReward;
  public bool alreadyAchieved,wouldGrant,granted;
 }
 [Serializable] public sealed class AwardReport {
  public string scope="Native persistent-stat and measured stat-driven checks with local unlock APIs; Android-local currency delivery. External achievements, activities and network transport unavailable.";
  public ThresholdObservation[] observations,statDrivenObservations;
  public string[] awarded;
  public uint coinsBefore,coinsAfter,collectedBefore,collectedAfter;
  public int unavailableActivityRequests;
 }
 [Serializable] public sealed class DiscoveryReport {
  public string pickup;
  public string[] awarded=Array.Empty<string>();
  public uint coinsBefore,coinsAfter;
  public bool discovered;
 }
 [Serializable] public sealed class ThreeStageReport {
  public string identifier,reward,scene,blocked;
  public int stageOrder;public ulong deaths;
  public bool eligible,alreadyAchieved,granted;
 }
 sealed class UnavailableActivityDispatch:ActivityManager {
  public int requests;
  public override void TryToSetActivityAvailability(BaseActivitySelector selector,bool available,bool applyAsDelta=true,bool sendImmediate=true){requests++;}
 }
 sealed class DefinitionState {
  public UnlockableDef definition;public UnlockableIndex index;public int sort;
  public Func<string> locked,unlocked;
 }
 readonly Dictionary<FieldInfo,object> priorFields=new Dictionary<FieldInfo,object>();
 readonly Dictionary<IDictionary,Dictionary<object,object>> priorMaps=new Dictionary<IDictionary,Dictionary<object,object>>();
 readonly List<DefinitionState> priorDefinitions=new List<DefinitionState>();
 readonly Dictionary<Run,HashSet<UnlockableDef>[]> priorRunUnlocks=new Dictionary<Run,HashSet<UnlockableDef>[]>();
 IList identifiers;object[] priorIdentifiers;
 AchievementDef[] persistentStats=Array.Empty<AchievementDef>();
 AchievementDef[] statDrivenAchievements=Array.Empty<AchievementDef>();
 AchievementDef[] pickupAchievements=Array.Empty<AchievementDef>();
 UnlockableDef[] ownedDefinitions=Array.Empty<UnlockableDef>();
 bool acquired,disposed;
 public bool ready {get;private set;}
 public int unlockables {get{return ownedDefinitions.Length;}}
 public int achievements {get;private set;}
 public string[] duplicateUnlockNames {get;private set;}=Array.Empty<string>();
 public AchievementDef[] persistentStatDefinitions {get{return persistentStats.ToArray();}}
 public AchievementDef[] pickupDiscoveryDefinitions {get{return pickupAchievements.ToArray();}}
 const BindingFlags StaticFlags=BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic;
 static readonly string[] RunUnlockSets={"unlockablesUnlockedByAnyUser","unlockablesUnlockedByAllUsers","unlockablesAlreadyFullyObtained"};
 static FieldInfo Field(Type type,string name){var field=type.GetField(name,StaticFlags|BindingFlags.Instance);if(field==null)throw new InvalidOperationException("Original progression field absent: "+type.FullName+"."+name);return field;}
 void Remember(Type type,string name){var field=Field(type,name);priorFields.Add(field,field.GetValue(null));}
 void RememberMap(Type type,string name){var map=(IDictionary)Field(type,name).GetValue(null);var before=new Dictionary<object,object>();foreach(DictionaryEntry pair in map)before.Add(pair.Key,pair.Value);priorMaps.Add(map,before);}
 static void Check(bool condition,string message){if(!condition)throw new InvalidOperationException(message);}
 void RequireReady(){Check(ready&&!disposed,"Owned original progression metadata is not ready");}
 static void NativeSetUnlockables(UnlockableDef[] definitions){typeof(UnlockableCatalog).GetMethod("SetUnlockableDefs",StaticFlags).Invoke(null,new object[]{definitions});}

 public IEnumerator Prepare(UnlockableDef[] completeDefinitions){
  Check(!acquired&&!disposed,"Progression owner cannot be reused");
  Check(completeDefinitions!=null&&completeDefinitions.Length>0&&completeDefinitions.All(def=>def&&!string.IsNullOrEmpty(def.cachedName))&&completeDefinitions.Distinct().Count()==completeDefinitions.Length,"Original unlock definitions absent or repeated");
  Check(BodyCatalog.bodyCount>0&&ItemCatalog.itemCount>0&&EquipmentCatalog.equipmentCount>0&&SurvivorCatalog.survivorCount>0&&ArtifactCatalog.artifactCount>0,"Native unlock metadata requires complete body/item/equipment/survivor/artifact catalogs");
  Check(UnlockableCatalog.unlockableCount==0&&AchievementManager.readOnlyAchievementIdentifiers.Count==0,"Foreign unlock/achievement catalog owner");
  var map=(Dictionary<string,AchievementDef>)Field(typeof(AchievementManager),"achievementNamesToDefs").GetValue(null);
  Check(map.Count==0&&((IDictionary)Field(typeof(AchievementManager),"userToManagerMap").GetValue(null)).Count==0,"Foreign achievement manager owner");
  Check(Field(typeof(AchievementManager),"onAchievementsRegistered").GetValue(null)==null,"Unowned achievement-registration callback");
  Remember(typeof(UnlockableCatalog),"indexToDefTable");Remember(typeof(UnlockableCatalog),"availability");
  RememberMap(typeof(UnlockableCatalog),"nameToDefTable");RememberMap(typeof(UnlockableCatalog),"unlockableToExpansionTable");
  Remember(typeof(AchievementManager),"achievementDefs");Remember(typeof(AchievementManager),"serverAchievementDefs");Remember(typeof(AchievementManager),"availability");RememberMap(typeof(AchievementManager),"achievementNamesToDefs");
  identifiers=(IList)Field(typeof(AchievementManager),"achievementIdentifiers").GetValue(null);priorIdentifiers=identifiers.Cast<object>().ToArray();
  ownedDefinitions=completeDefinitions.ToArray();
  foreach(var def in ownedDefinitions)priorDefinitions.Add(new DefinitionState{definition=def,index=def.index,sort=def.sortScore,locked=def.getHowToUnlockString,unlocked=def.getUnlockedString});
  acquired=true;NativeSetUnlockables(ownedDefinitions);UnlockableCatalog.availability.MakeAvailable();
  foreach(var def in ownedDefinitions)Check(def.index!=UnlockableIndex.None&&UnlockableCatalog.GetUnlockableDef(def.index)==def,"Native unlock index identity differs");
  // Some original log definitions share a name. Keep native array order and
  // native last-name lookup; only its canonical result can be persisted/granted.
  duplicateUnlockNames=ownedDefinitions.GroupBy(def=>def.cachedName).Where(group=>group.Count()>1).Select(group=>group.Key).OrderBy(name=>name,StringComparer.Ordinal).ToArray();
  foreach(var group in ownedDefinitions.GroupBy(def=>def.cachedName))Check(UnlockableCatalog.GetUnlockableDef(group.Key)==group.Last(),"Native duplicate-name lookup differs");
  // Collect metadata without DoInit's user-login/update subscriptions. Collection
  // still uses the original attributes, sorting, reward lookup and icon references.
  var collection=AchievementManager.CollectAchievementDefs(map);
  try{while(collection.MoveNext())yield return collection.Current;}finally{var disposable=collection as IDisposable;if(disposable!=null)disposable.Dispose();}
  var expected=typeof(BaseAchievement).Assembly.GetTypes().Where(type=>!type.IsAbstract&&type.IsSubclassOf(typeof(BaseAchievement))&&Attribute.IsDefined(type,typeof(RegisterAchievementAttribute),false)).ToArray();
  Check(map.Count==expected.Length&&map.Values.All(def=>expected.Contains(def.type)),"Original achievement type/metadata coverage differs");
  foreach(var def in map.Values)if(!string.IsNullOrEmpty(def.unlockableRewardIdentifier))RequireDefinition(UnlockableCatalog.GetUnlockableDef(def.unlockableRewardIdentifier));
  persistentStats=map.Values.Where(def=>typeof(BaseStatMilestoneAchievement).IsAssignableFrom(def.type)).OrderBy(def=>def.identifier,StringComparer.Ordinal).ToArray();
  Check(persistentStats.Length>0&&persistentStats.All(def=>def.type.BaseType==typeof(BaseStatMilestoneAchievement)&&def.serverTrackerType==null&&def.type.GetMethod("OnInstall").DeclaringType==typeof(BaseStatMilestoneAchievement)&&def.type.GetMethod("OnUninstall").DeclaringType==typeof(BaseStatMilestoneAchievement)&&def.type.GetMethod("OnGranted").DeclaringType==typeof(BaseAchievement)),"Unmeasured persistent-stat achievement implementation");
  statDrivenAchievements=new[]{map["RepeatFirstTeleporter"],map["UseThreePortals"]};
  Check(statDrivenAchievements[0].type==typeof(RepeatFirstTeleporterAchievement)&&statDrivenAchievements[0].serverTrackerType!=null&&statDrivenAchievements[0].unlockableRewardIdentifier=="Characters.Toolbot"&&statDrivenAchievements[0].serverIndex.intValue>=0&&statDrivenAchievements[0].serverIndex.intValue<AchievementManager.serverAchievementCount&&statDrivenAchievements[1].type==typeof(UseThreePortalsAchievement)&&statDrivenAchievements[1].serverTrackerType==null&&statDrivenAchievements[1].unlockableRewardIdentifier=="Items.Tonic"&&statDrivenAchievements.All(def=>def.type.BaseType==typeof(BaseAchievement)&&def.type.GetMethod("OnGranted").DeclaringType==typeof(BaseAchievement)),"Original stat-driven achievement contract changed");
  pickupAchievements=new[]{"Discover10UniqueTier1","Discover5Equipment"}.Select(id=>map[id]).ToArray();
  Check(pickupAchievements[0].type==typeof(Discover10UniqueTier1Achievement)&&pickupAchievements[1].type==typeof(Discover5EquipmentAchievement)&&pickupAchievements.All(def=>def.serverTrackerType==null&&def.type.BaseType==typeof(BaseAchievement)&&def.type.GetMethod("OnGranted").DeclaringType==typeof(BaseAchievement)),"Original pickup-discovery achievement contract changed");
  achievements=map.Count;AchievementManager.availability.MakeAvailable();ready=true;
 }

 public static void RequireDefinition(UnlockableDef definition){
  Check(definition&&definition.index!=UnlockableIndex.None&&UnlockableCatalog.GetUnlockableDef(definition.index)==definition&&UnlockableCatalog.GetUnlockableDef(definition.cachedName)==definition,"Null, unresolved or unindexed original unlock definition");
 }
 public void ValidateProfile(UserProfile profile){
  RequireReady();Check(profile!=null&&profile.statSheet!=null&&!profile.loggedIn&&!profile.isClaimed&&profile.saveID==0,"Android progression requires an unauthenticated local profile");
  var seen=new HashSet<UnlockableIndex>();
  for(int i=0;i<profile.statSheet.GetUnlockableCount();i++){
   var index=profile.statSheet.GetUnlockableIndex(i);Check(index!=UnlockableIndex.None&&seen.Add(index),"Unresolved or duplicate saved unlock index");RequireDefinition(profile.statSheet.GetUnlockable(i));
  }
 }
 public static StatDef GetPersistentStat(AchievementDef definition){
  Check(definition!=null&&definition.type.BaseType==typeof(BaseStatMilestoneAchievement),"Not an original persistent-stat family definition");
  var instance=(BaseStatMilestoneAchievement)Activator.CreateInstance(definition.type);
  return (StatDef)definition.type.GetProperty("statDef",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(instance,null);
 }
 public static ulong GetPersistentRequirement(AchievementDef definition){
  Check(definition!=null&&definition.type.BaseType==typeof(BaseStatMilestoneAchievement),"Not an original persistent-stat family definition");
  var instance=(BaseStatMilestoneAchievement)Activator.CreateInstance(definition.type);
  return (ulong)definition.type.GetProperty("statRequirement",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(instance,null);
 }
 ThresholdObservation Evaluate(UserProfile candidate,AchievementDef definition,bool award){
  ValidateProfile(candidate);Check(persistentStats.Contains(definition),"Achievement does not belong to the owned native family");
  var reward=UnlockableCatalog.GetUnlockableDef(definition.unlockableRewardIdentifier);RequireDefinition(reward);
  var stat=GetPersistentStat(definition);Check(stat!=null&&stat.index>=0&&stat.index<candidate.statSheet.fields.Length,"Original achievement statistic is uninitialized");
  var observation=new ThresholdObservation{identifier=definition.identifier,reward=reward.cachedName,stat=stat.name,progress=candidate.statSheet.GetStatValueULong(stat),requirement=GetPersistentRequirement(definition),alreadyAchieved=candidate.HasAchievement(definition.identifier),lunarReward=definition.lunarCoinReward};
  if(observation.alreadyAchieved)return observation;
  var expansion=UnlockableCatalog.GetExpansionDefForUnlockable(reward.index);
  if(expansion&&expansion.requiredEntitlement){observation.blocked="Original reward requires unavailable platform entitlement context";return observation;}
  Check(!candidate.canSave&&candidate.onStatsReceived==null,"Achievement evaluation requires a detached unsaveable profile clone");
  string before=UserProfile.ToXml(candidate).ToString();
  var user=new LocalUser{userProfile=candidate};
  Check(user.inputPlayer==null&&!user.currentNetworkUser&&LocalUserManager.readOnlyLocalUsersList.Count==0&&NetworkUser.readOnlyInstancesList.Count==0,"Threshold evaluation acquired a user/platform context");
  var owner=new UserAchievementManager{localUser=user,userProfile=candidate};
  var achievement=(BaseStatMilestoneAchievement)Activator.CreateInstance(definition.type);achievement.achievementDef=definition;achievement.owner=owner;
  var priorStatCallbacks=stat.onChangeCallback;bool entered=false;
  try{
   entered=true;achievement.OnInstall();observation.wouldGrant=achievement.shouldGrant;Check(owner.dirtyGrantsCount==(observation.wouldGrant?1:0),"Native threshold grant observation differs");
   if(award&&observation.wouldGrant){
    // This native API explicitly distinguishes local achievement data from
    // external service reporting. OnGranted retains native unlock behavior.
    candidate.AddAchievement(definition.identifier,false);achievement.OnGranted();
    // RpcAwardLunarCoins has no standalone local entry point. Supply its two
    // profile updates with the original saturating helper and metadata reward;
    // there is no synthetic NetworkUser, RPC or server-balance claim.
    candidate.coins=HGMath.UintSafeAdd(candidate.coins,definition.lunarCoinReward);
    candidate.totalCollectedCoins=HGMath.UintSafeAdd(candidate.totalCollectedCoins,definition.lunarCoinReward);
    Check(candidate.HasAchievement(definition.identifier)&&candidate.statSheet.HasUnlockable(reward),"Native local achievement reward differs");observation.granted=true;
   }
  }
  finally{if(entered)achievement.OnUninstall();}
  Check((observation.granted||UserProfile.ToXml(candidate).ToString()==before)&&candidate.onStatsReceived==null&&stat.onChangeCallback==priorStatCallbacks,"Achievement evaluation changed unearned data or retained callbacks");return observation;
 }
 public ThresholdObservation InspectPersistentStatCandidate(UserProfile candidate,AchievementDef definition){ValidateProfile(candidate);var clone=UserProfile.FromXml(UserProfile.ToXml(candidate));clone.canSave=false;return Evaluate(clone,definition,false);}
 public ThresholdObservation[] InspectPersistentStatCandidate(UserProfile candidate){return persistentStats.Select(def=>InspectPersistentStatCandidate(candidate,def)).ToArray();}
 ThresholdObservation EvaluateStatDriven(UserProfile candidate,AchievementDef definition){
  ValidateProfile(candidate);Check(statDrivenAchievements.Contains(definition)&&!candidate.canSave&&candidate.onStatsReceived==null,"Stat-driven award requires an owned detached profile");
  var reward=UnlockableCatalog.GetUnlockableDef(definition.unlockableRewardIdentifier);RequireDefinition(reward);
  var observation=new ThresholdObservation{identifier=definition.identifier,reward=reward.cachedName,stat=definition.identifier=="RepeatFirstTeleporter"?StatDef.firstTeleporterCompleted.name:"per-stage portal visits",requirement=definition.identifier=="RepeatFirstTeleporter"?5uL:3uL,alreadyAchieved=candidate.HasAchievement(definition.identifier),lunarReward=definition.lunarCoinReward};
  if(observation.alreadyAchieved)return observation;
  var expansion=UnlockableCatalog.GetExpansionDefForUnlockable(reward.index);
  if(expansion&&expansion.requiredEntitlement){observation.blocked="Original reward requires unavailable platform entitlement context";return observation;}
  var before=UserProfile.ToXml(candidate).ToString();var user=new LocalUser{userProfile=candidate};
  Check(user.inputPlayer==null&&!user.currentNetworkUser&&LocalUserManager.readOnlyLocalUsersList.Count==0&&NetworkUser.readOnlyInstancesList.Count==0,"Stat-driven award acquired a user/platform identity");
  var owner=new UserAchievementManager{localUser=user,userProfile=candidate};
  var achievement=(BaseAchievement)Activator.CreateInstance(definition.type);achievement.achievementDef=definition;achievement.owner=owner;
  bool entered=false;
  try{
   entered=true;achievement.OnInstall();candidate.onStatsReceived?.Invoke();
   observation.progress=(ulong)Mathf.Max(0,Mathf.RoundToInt(achievement.ProgressForAchievement()*observation.requirement));
   observation.wouldGrant=achievement.shouldGrant;Check(owner.dirtyGrantsCount==(observation.wouldGrant?1:0),"Original stat-driven grant observation differs");
   if(observation.wouldGrant){
    candidate.AddAchievement(definition.identifier,false);achievement.OnGranted();
    candidate.coins=HGMath.UintSafeAdd(candidate.coins,definition.lunarCoinReward);
    candidate.totalCollectedCoins=HGMath.UintSafeAdd(candidate.totalCollectedCoins,definition.lunarCoinReward);
    Check(candidate.HasAchievement(definition.identifier)&&candidate.statSheet.HasUnlockable(reward),"Original stat-driven reward differs");observation.granted=true;
   }
  }finally{if(entered)achievement.OnUninstall();}
  Check(candidate.onStatsReceived==null&&(observation.granted||UserProfile.ToXml(candidate).ToString()==before),"Stat-driven evaluation retained callbacks or unearned data");return observation;
 }
 static void ValidateUnlockNotifications(){
  Check(LocalUserManager.readOnlyLocalUsersList.Count==0&&NetworkUser.readOnlyInstancesList.Count==0,"Local award transaction has a registered user");
  var callbacks=Field(typeof(UserProfile),"onUnlockableGranted").GetValue(null) as Delegate;
  if(callbacks==null)return;
  foreach(var callback in callbacks.GetInvocationList()){
   var method=callback.Method;var parameters=method.GetParameters();
   Check(method.DeclaringType!=null&&method.DeclaringType.DeclaringType==typeof(NetworkUser)&&method.Name.StartsWith("<Init>b__",StringComparison.Ordinal)&&method.ReturnType==typeof(void)&&parameters.Length==2&&parameters[0].ParameterType==typeof(UserProfile)&&parameters[1].ParameterType==typeof(UnlockableDef),"Unowned pre-commit unlock notification subscriber");
  }
 }
 public AwardReport ApplyPersistentStatCandidate(UserProfile candidate){
  ValidateProfile(candidate);Check(!candidate.canSave&&!candidate.saveRequestPending,"Awards require the unsaveable post-delta transaction clone");ValidateUnlockNotifications();
  var prior=PlatformSystems.activityManager;Check(prior==null,"Foreign platform activity owner");
  var unavailable=new UnavailableActivityDispatch();var report=new AwardReport{coinsBefore=candidate.coins,collectedBefore=candidate.totalCollectedCoins};
  PlatformSystems.activityManager=unavailable;
  try{report.observations=persistentStats.Select(def=>Evaluate(candidate,def,true)).ToArray();report.statDrivenObservations=statDrivenAchievements.Select(def=>EvaluateStatDriven(candidate,def)).ToArray();report.awarded=report.observations.Concat(report.statDrivenObservations).Where(row=>row.granted).Select(row=>row.identifier).ToArray();report.coinsAfter=candidate.coins;report.collectedAfter=candidate.totalCollectedCoins;report.unavailableActivityRequests=unavailable.requests;Check(!unavailable.IsInitialized,"Offline activity adapter claimed initialization");return report;}
  finally{bool owned=ReferenceEquals(PlatformSystems.activityManager,unavailable);PlatformSystems.activityManager=prior;Check(owned,"Platform activity ownership changed during local transaction");}
 }

 public ThreeStageReport ApplyThreeStageCandidate(UserProfile candidate,StatSheet runStats,SceneDef scene){
  ValidateProfile(candidate);Check(!candidate.canSave&&!candidate.saveRequestPending&&runStats!=null,"Three-stage award requires an unsaveable profile and original run statistics");ValidateUnlockNotifications();
  var definition=AchievementManager.GetAchievementDef("CompleteThreeStages");
  Check(definition!=null&&definition.type==typeof(CompleteThreeStagesAchievement)&&definition.serverTrackerType==null&&definition.unlockableRewardIdentifier=="Characters.Bandit2","Original Bandit achievement contract changed");
  var reward=UnlockableCatalog.GetUnlockableDef(definition.unlockableRewardIdentifier);RequireDefinition(reward);
  var report=new ThreeStageReport{identifier=definition.identifier,reward=reward.cachedName,scene=scene?scene.cachedName:string.Empty,stageOrder=scene?scene.stageOrder:0,deaths=runStats.GetStatValueULong(StatDef.totalDeaths),alreadyAchieved=candidate.HasAchievement(definition.identifier)};
  report.eligible=Run.instance&&Run.instance.GetType()==typeof(Run)&&scene&&scene.stageOrder==3&&report.deaths==0;
  if(!report.eligible||report.alreadyAchieved)return report;
  var expansion=UnlockableCatalog.GetExpansionDefForUnlockable(reward.index);
  if(expansion&&expansion.requiredEntitlement){report.blocked="Original reward requires unavailable platform entitlement context";return report;}
  var prior=PlatformSystems.activityManager;Check(prior==null,"Foreign platform activity owner");
  var unavailable=new UnavailableActivityDispatch();var user=new LocalUser{userProfile=candidate};
  Check(user.inputPlayer==null&&!user.currentNetworkUser&&LocalUserManager.readOnlyLocalUsersList.Count==0&&NetworkUser.readOnlyInstancesList.Count==0,"Three-stage award acquired a platform or network identity");
  var owner=new UserAchievementManager{localUser=user,userProfile=candidate};
  var achievement=new CompleteThreeStagesAchievement{achievementDef=definition,owner=owner};
  PlatformSystems.activityManager=unavailable;
  try{
   achievement.OnInstall();
   try{
    // The shipped handler reads currentNetworkUser for its death statistic.
    // This offline boundary supplies the same measured predicate, then calls
    // the original Grant and OnGranted paths on an unsaveable profile clone.
    achievement.Grant();Check(achievement.shouldGrant&&owner.dirtyGrantsCount==1,"Original Bandit grant rejected the eligible local event");
    candidate.AddAchievement(definition.identifier,false);achievement.OnGranted();
    candidate.coins=HGMath.UintSafeAdd(candidate.coins,definition.lunarCoinReward);
    candidate.totalCollectedCoins=HGMath.UintSafeAdd(candidate.totalCollectedCoins,definition.lunarCoinReward);
    Check(candidate.HasAchievement(definition.identifier)&&candidate.statSheet.HasUnlockable(reward),"Original Bandit unlock was not awarded locally");report.granted=true;
   }finally{achievement.OnUninstall();}
   Check(!unavailable.IsInitialized,"Offline activity adapter claimed initialization");return report;
  }finally{bool owned=ReferenceEquals(PlatformSystems.activityManager,unavailable);PlatformSystems.activityManager=prior;Check(owned,"Platform activity ownership changed during three-stage award");}
 }

 // The original PlayerCharacterMasterController forwards these exact inventory
 // client events to UserProfile.DiscoverPickup. Android owns only the missing
 // unauthenticated profile link; both achievement classes and grants are native.
 public DiscoveryReport ApplyDiscoveryCandidate(UserProfile candidate,PickupIndex pickup){
  ValidateProfile(candidate);Check(!candidate.canSave&&!candidate.saveRequestPending&&pickup.isValid&&!candidate.HasDiscoveredPickup(pickup),"Discovery requires a new pickup on an unsaveable profile transaction");
  var pickupDef=PickupCatalog.GetPickupDef(pickup);Check(pickupDef!=null,"Original pickup identity differs");ValidateUnlockNotifications();
  var prior=PlatformSystems.activityManager;Check(prior==null,"Foreign platform activity owner");
  var unavailable=new UnavailableActivityDispatch();var report=new DiscoveryReport{pickup=pickupDef.internalName,coinsBefore=candidate.coins};
  var user=new LocalUser{userProfile=candidate};Check(user.inputPlayer==null&&!user.currentNetworkUser&&LocalUserManager.readOnlyLocalUsersList.Count==0&&NetworkUser.readOnlyInstancesList.Count==0,"Discovery acquired a user/platform context");
  var owner=new UserAchievementManager{localUser=user,userProfile=candidate};
  var installed=new List<BaseAchievement>();var callbacks=candidate.onPickupDiscovered;
  PlatformSystems.activityManager=unavailable;
  try{
   foreach(var definition in pickupAchievements){
    if(candidate.HasAchievement(definition.identifier))continue;
    var reward=UnlockableCatalog.GetUnlockableDef(definition.unlockableRewardIdentifier);RequireDefinition(reward);
    var expansion=UnlockableCatalog.GetExpansionDefForUnlockable(reward.index);
    if(expansion&&expansion.requiredEntitlement)continue;
    var achievement=(BaseAchievement)Activator.CreateInstance(definition.type);achievement.achievementDef=definition;achievement.owner=owner;
    installed.Add(achievement);achievement.OnInstall();
   }
   candidate.DiscoverPickup(pickup);report.discovered=candidate.HasDiscoveredPickup(pickup);
   var awarded=new List<string>();
   foreach(var achievement in installed)if(achievement.shouldGrant){
    var definition=achievement.achievementDef;var reward=UnlockableCatalog.GetUnlockableDef(definition.unlockableRewardIdentifier);RequireDefinition(reward);
    candidate.AddAchievement(definition.identifier,false);achievement.OnGranted();
    candidate.coins=HGMath.UintSafeAdd(candidate.coins,definition.lunarCoinReward);
    candidate.totalCollectedCoins=HGMath.UintSafeAdd(candidate.totalCollectedCoins,definition.lunarCoinReward);
    Check(candidate.HasAchievement(definition.identifier)&&candidate.statSheet.HasUnlockable(reward),"Original pickup-discovery award differs");awarded.Add(definition.identifier);
   }
   report.awarded=awarded.ToArray();report.coinsAfter=candidate.coins;
   Check(owner.dirtyGrantsCount==awarded.Count&&report.discovered,"Original pickup-discovery grant count differs");
  }
  finally{
   for(int i=installed.Count-1;i>=0;i--)installed[i].OnUninstall();
   bool owned=ReferenceEquals(PlatformSystems.activityManager,unavailable);PlatformSystems.activityManager=prior;
   Check(owned&&candidate.onPickupDiscovered==callbacks&&!unavailable.IsInitialized,"Original pickup callbacks or unavailable activity owner retained");
  }
  return report;
 }

 public int PopulateEarnedRunAvailability(Run run,UserProfile profile){
  ValidateProfile(profile);Check(run&&NetworkServer.active&&run.participatingPlayerCount==1&&NetworkUser.readOnlyInstancesList.Count==0,"Earned availability requires the owned offline single-player Run");
  var sets=RunUnlockSets.Select(name=>(HashSet<UnlockableDef>)Field(typeof(Run),name).GetValue(run)).ToArray();
  if(!priorRunUnlocks.ContainsKey(run)){Check(sets.All(set=>set.Count==0),"Foreign run unlock availability");priorRunUnlocks.Add(run,sets.Select(set=>new HashSet<UnlockableDef>(set)).ToArray());}
  var earned=new HashSet<UnlockableDef>();
  for(int i=0;i<profile.statSheet.GetUnlockableCount();i++){
   var def=profile.statSheet.GetUnlockable(i);RequireDefinition(def);
   var expansion=UnlockableCatalog.GetExpansionDefForUnlockable(def.index);if(expansion&&!run.IsExpansionEnabled(expansion))continue;
   earned.Add(def);
  }
  // One local profile supplies all/any participant data. Native Run queries and
  // drop-table generation remain unchanged; this never changes the profile.
  foreach(var set in sets){set.Clear();set.UnionWith(earned);}return earned.Count;
 }
 public void Dispose(){
  if(disposed)return;disposed=true;ready=false;
  foreach(var entry in priorRunUnlocks)if(entry.Key)for(int i=0;i<RunUnlockSets.Length;i++){var set=(HashSet<UnlockableDef>)Field(typeof(Run),RunUnlockSets[i]).GetValue(entry.Key);set.Clear();set.UnionWith(entry.Value[i]);}priorRunUnlocks.Clear();
  if(!acquired)return;
  foreach(var state in priorDefinitions){state.definition.index=state.index;state.definition.sortScore=state.sort;state.definition.getHowToUnlockString=state.locked;state.definition.getUnlockedString=state.unlocked;}
  foreach(var entry in priorMaps){entry.Key.Clear();foreach(var pair in entry.Value)entry.Key.Add(pair.Key,pair.Value);}
  foreach(var entry in priorFields)entry.Key.SetValue(null,entry.Value);
  identifiers.Clear();foreach(var value in priorIdentifiers)identifiers.Add(value);
  priorDefinitions.Clear();priorMaps.Clear();priorFields.Clear();ownedDefinitions=Array.Empty<UnlockableDef>();persistentStats=Array.Empty<AchievementDef>();pickupAchievements=Array.Empty<AchievementDef>();acquired=false;
 }
}
