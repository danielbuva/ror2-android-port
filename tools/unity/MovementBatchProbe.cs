using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using RoR2;
using KinematicCharacterController;
using UnityEngine;
using UnityEngine.Networking;

// Each experiment runs in a fresh process. Automatic probes enable only their measured callbacks.
public sealed partial class MovementBatchProbe : MonoBehaviour {
 // Required Moon metadata is separate from the earned-item/drop domain.
 // These exact definitions register identities; original eligibility remains authoritative.
 [Serializable] public class MoonCatalogSpec {public string[] items,buffs,equipment;}
 [Serializable] public class Result {
  public string visualCaptureStage,visualCaptureRenderer,visualCapturePath;public bool visualCaptureActive;public Vector3 visualCaptureCenter;
  public bool originalAimPresentation,recoveredHudEnabled;public RecoveredHudPresentation.Observation hud;public bool enhancedPresentation,pauseBeforeMoon;public AndroidMaterialPresentation.Report presentation;public AndroidPresentationCamera.Report framePacing;public DebugAccelerationOptions debugOptions;public DebugAccelerationReport debugAcceleration;public MoonCatalogSpec moonCatalog;public bool integratedResults;public IntegratedResultsReport results;public string[] resultsEndingAssets;public string[] runEventFlagsToResetOnLoop;public bool moonMission;public MoonMissionReport moon;public bool teleporterLoop;public ObjectiveReport objective;public ObjectiveActorSpec[] objectiveActors;public string teleporterAsset,lunarTeleporterAsset,teleporterIndicatorAsset,teleporterIndicatorKey;public string objectiveWardBuffAsset;public string[] objectiveWardVisualAssets;public IntegratedStageSpec[] integratedStages;public int integratedTransitionTarget,integratedRuntimeSeconds;public StageProgressReport stageProgress;public string[] objectiveSupportAssets,objectiveSupportKeys,objectiveSupportPaths;public string objectiveTMPSettingsAsset,objectiveTMPSettingsKey,objectiveStunAsset;public string[] objectiveEffectAssets,objectiveConfigAssets,objectiveItemAssets,objectiveItemNames,objectiveArtifactAssets,runSceneDefAssets;public int session;public string[] worldAdditionalLootItems,worldLootSupportPaths,worldCommerceAssets;public string worldLootSlowBuffAsset;public string worldGlassesAsset,worldSlugAsset,worldLunarCoinAsset;public bool integratedWorld;public WorldReport world;public CommerceReport commerce;public string firstFailure,firstFailurePhase;public ChestEjectionReport chestEjection;public bool originalChestEjection;public DefaultPickupReport defaultPickup;public bool originalDefaultPickup;public string genericPickupKey;public PickupDropletCollisionReport pickupDropletCollision;public bool originalPickupDropletCollision;public PickupDropletFlightReport pickupDropletFlight;public bool originalPickupDropletFlight;public string commandArtifactAsset;public PickupDropletLoadReport pickupDropletLoad;public bool originalPickupDropletLoad;public string pickupDropletAsset,pickupDropletKey;public ChestPurchaseReport chestPurchase;public bool originalChestPurchase;public string chestAsset,freeUnlockBuffAsset,lowerPricedConsumedAsset,delusionArtifactAsset;public ChestDropTableReport chestDropTable;public bool originalChestDropTable;public string chestDropTableAsset,randomlyLunarAsset,chestLootItemAsset;public InputBarrelReport inputBarrel;public bool originalInputBarrel;public ClientCoinReport clientCoin;public bool originalClientCoin;public InteractionSelectionReport interactionSelection;public bool originalInteractionSelection;public string recycleAsset,lowerPricedChestsAsset;public ItemPickupReport itemPickup;public ActiveClientReport activeClient;public bool originalActiveClient;public MoneyCostReport moneyCost;public bool originalMoneyCost;public string moneySourceSha256,multiShopCardAsset;public int moneySourceCost;public bool originalItemPickup;public string pickupAsset,statItemAsset,junkAsset;public BarrelReport barrel;public bool barrelInteraction;public string barrelAsset;public RunClockReport runClock;public bool originalRunClock;public string runSceneDefAsset;public DirectorReport director;public int directorSpawnLimit;public bool automaticDirector,sourceQueriesHitTriggers;public string enemyDirectorAsset,enemyDirectorDeckAsset,enemyHonorArtifactAsset;public string[] enemyDirectorTeamAssets,enemyDirectorTeamKeys;public RewardReport rewards;public bool enemyRewards;public string enemySpawnCardAsset;public string[] enemySpawnItems,enemyRewardAssets,enemyRewardKeys;public PlayerDefeatReport playerDefeat;public string playerDeathEffectAsset,playerDeathEffectKey;public bool enemySpine;public EnemyReport enemy;public string enemyBodyAsset,enemyMasterAsset,enemyControllerAsset,enemyAvatarAsset,enemyMaterialAsset,enemyGroundGraphAsset,enemyAirGraphAsset,enemySpawnConfigAsset,enemyAttackConfigAsset,enemySleepConfigAsset,enemyDeathBuffAsset,enemyWispArtifactAsset;public string[] enemyDeathItems,enemyDeathEquipment,enemyEliteAssets;public bool stageGeometry;public int stageMapZoneCount;public string[] stageMapZoneActiveNames;public StageGeometryReport stage;public bool combatSpine,freePlay,launchPlayableSlice;public string secondaryConfigAsset,utilityConfigAsset,specialConfigAsset;public CombatReport combat;public PrimaryFireReport primary;public string primaryFireConfigAsset,primaryReloadConfigAsset,primaryItemAsset;public NovaReport nova;public bool rewiredReadyBefore,rewiredReadyAfter,rewiredAndroidContract;public string rewiredPlatform,rewiredBackend,rewiredApi;public int rewiredAndroidApi,androidApi;public string[] unityJoystickNames;public string[] automaticSkillNames,automaticSkillTypes;public int[] automaticSkillInitialStocks,automaticSkillFinalStocks;public float skillRechargeExpected,skillRechargeObserved;public bool skillRestocked;public bool modelDetached,modelDestroyed;public string modelTarget,modelParent;public int modelFollowFrames;public float modelPositionError,modelRotationError;public bool automaticDirectionStarted,directionAimExpired;public string directionTarget;public float directionTurnSpeed,directionStartYaw,directionEastYaw,directionEastTargetYaw,directionWestYaw,directionAimYaw,directionFinalYaw;public string barrierEffectAsset,barrierEffectKey,barrierCompletionType,barrierCompletionMethod;public int barrierCompletionCalls,barrierMaterialCopies,barrierMaterialCopiesAliveAfterEffect;public bool barrierMaterialCopiesReleased;public bool barrierCompletionSucceeded;public int barrierSyncLoads,barrierInitCalls,barrierEffectEntries;public bool barrierPrefabLoaded,barrierInitCompleted,barrierBundleReleased,barrierEffectExited,barrierEffectDestroyed;public float healthTickSeconds,healthRegen,regenBefore,regenAfter,barrierBefore,barrierAfter,barrierExpected;public bool automaticHealthEnabled;public int automaticBodyStatsEvents;public float stationarySeconds,spawnExitBuffSeconds;public bool automaticBodyRegistered,spawnBuffExpired;public float gravitySeconds,fallVelocity,landingHeight,landingVelocity;public bool grounded;public string[] automaticCallbacks;public float automaticSeconds;public int automaticFrames;public bool automaticSolverRegistered;public int spawnedBodyIndex;public uint spawnedSkinIndex;public string teleportMaterialAsset,teleportMaterialKey,teleportMaterialName,teleportShader;public bool teleportMaterialLoaded,teleportBundleReleased,teleportOverlayRemoved;public int teleportOverlays,teleportSyncLoads;public string spawnConfigAsset,hiddenBuffAsset,intangibleBuffAsset,medkitBuffAsset,tonicBuffAsset,soulBuffAsset,sourceSpawnSound,spawnState;public float spawnedMoveSpeed,spawnedAcceleration,spawnedStateAge,spawnedFixedAge;public int spawnedMainTicks;public float sourceSpawnDelay;public int idleStarts,spawnStateEntries,hiddenBuffCount;public bool initializeLoadoutTables;public string gummyAsset;public int masterStartEvents,bodyStartEvents;public float spawnedHealth;public string attempt,id,phase,error,artifactAsset,jumpBoostAsset,jumpStrikeAsset,bodyAsset,masterAsset,lunarPrimaryAsset,lunarSecondaryAsset,lunarUtilityAsset,lunarSpecialAsset,batteryAsset,glassAsset,voidEquipmentAsset,potionAsset,knockBuffAsset,juggleBuffAsset;public string[] displayAssets;public int pid;public bool success,cleanup,statBuffs;public float x,y,z,gravity,peak,sourceGravity,maxHealth,moveSpeed,damage,jumpPower,level;public bool rawAuthority,effectiveAuthority,playerAuthority,hasClientOwner,clientActive,ownedAuthority,ownerMatched;public int spawnCloneCount;public bool spawnedTeamCached,spawnedSkillCached,spawnedMasterMatches,spawnedNetworked;public int connectEvents;public int motorStartEvents,landingEvents;public int levelEvents;public float raisedHealth,raisedDamage,computedAcceleration;public int assertions,jumpEvents,awakeEvents,inventoryEvents,statsEvents,skillCount;public uint bodyId,masterId;}
 bool ownsStateCatalog,ownsBodyCatalog;
 NetworkClient recoveredClient;NetworkConnection recoveredOwner;NetworkIdentity recoveredOwnedIdentity;
 Result r;GameObject host,obstacle,eventHost,artifactHost;bool ownsServer;ArtifactDef[] priorArtifacts;ArtifactDef priorFallArtifact;AssetBundle artifactBundle;RunArtifactManager artifactManager;
 void Check(bool value,string message){r.assertions++;if(!value){if(string.IsNullOrEmpty(r.firstFailure)){r.firstFailure=message;r.firstFailurePhase=r.phase;try{Save();}catch(Exception){/* Preserve the original predicate when evidence writing also fails. */}}throw new Exception(message);}}
 static void Call(object obj,string method,params object[] args){obj.GetType().GetMethod(method,BindingFlags.NonPublic|BindingFlags.Instance).Invoke(obj,args);}
 void Save(){
  var path=System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-"+r.id+".json");
  var pending=path+".pending";File.WriteAllText(pending,JsonUtility.ToJson(r,false));
  // Same-volume rename keeps adb readers on a complete previous or next report.
  if(File.Exists(path))File.Replace(pending,path,null);else File.Move(pending,path);
 }
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("MovementBatchProbe"))new GameObject("Isolated movement batch").AddComponent<MovementBatchProbe>();}
 IEnumerator Start(){
  yield return new WaitForSeconds(8);
  var path=System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-selection.json");var config=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  if(File.Exists(path)){r=JsonUtility.FromJson<Result>(File.ReadAllText(path));if(r.attempt!=config.attempt)yield break;}
  else{
   if(!config.launchPlayableSlice)yield break;
   // Existing sync pushes this attempt-bound mapping only after the complete payload sync.
   var mappingPath=System.IO.Path.Combine(Application.persistentDataPath,"nova-input-mapping.json");
   while(!File.Exists(mappingPath)||JsonUtility.FromJson<NovaInputBridge.Mapping>(File.ReadAllText(mappingPath)).attempt!=config.attempt)yield return new WaitForSeconds(1);
   r=new Result{attempt=config.attempt,id="body-state-spawn-state-auto-nova-spine",freePlay=true};
  }
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))r.pid=process.CallStatic<int>("myPid");
#endif
  r.recoveredHudEnabled=config.recoveredHudEnabled;if(r.recoveredHudEnabled)r.hud=new RecoveredHudPresentation.Observation();
  AndroidMaterialPresentation.Begin(config.enhancedPresentation);r.enhancedPresentation=config.enhancedPresentation;r.pauseBeforeMoon=config.pauseBeforeMoon;r.presentation=AndroidMaterialPresentation.report;
  r.session=sessionIndex;r.phase="started";Save();
  var applicationStart=AwaitOfflineRunStart(config);while(applicationStart.MoveNext())yield return applicationStart.Current;
  bool catalogOnly=r.id=="body-catalog-registration";bool catalogFixture=r.id.StartsWith("body-state-spawn-state-")||r.id=="body-state-spawn-loadout-catalog"||r.id=="body-state-spawn-body-start-catalog";
  if(catalogOnly||catalogFixture){
   var routine=RegisterBodyCatalog();
   while(true){bool more=false;object current=null;try{more=routine.MoveNext();if(more)current=routine.Current;}catch(Exception e){r.error=e.ToString();break;}if(!more)break;yield return current;}
   if(string.IsNullOrEmpty(r.error)&&!string.IsNullOrEmpty(config.teleportMaterialAsset)){
    routine=PrepareTeleportMaterial(config);
    while(true){bool more=false;object current=null;try{more=routine.MoveNext();if(more)current=routine.Current;}catch(Exception e){r.error=e.ToString();break;}if(!more)break;yield return current;}
   }
   if(string.IsNullOrEmpty(r.error)&&!string.IsNullOrEmpty(config.barrierEffectAsset)){
    routine=PrepareBarrierEffect(config);
    while(true){bool more=false;object current=null;try{more=routine.MoveNext();if(more)current=routine.Current;}catch(Exception e){r.error=e.ToString();break;}if(!more)break;yield return current;}
   }
   if(catalogOnly||r.id=="body-state-spawn-state-barrier-asset"||r.id=="body-state-spawn-state-barrier-init"||r.id=="body-state-spawn-state-barrier-completion"||!string.IsNullOrEmpty(r.error)){
    r.success=string.IsNullOrEmpty(r.error);try{CleanupBodyCatalog();r.cleanup=true;}catch(Exception e){r.error+=" Catalog cleanup: "+e;r.success=false;}
    var release=CleanupBarrierEffect();while(release.MoveNext())yield return release.Current;release=CleanupTeleportMaterial();while(release.MoveNext())yield return release.Current;r.phase="complete";Save();yield break;
   }
  }
  var selected=RunSelectedProbe(catalogFixture);
  while(true){bool more=false;object current=null;try{more=selected.MoveNext();if(more)current=selected.Current;}catch(Exception e){r.error=e.ToString();if(string.IsNullOrEmpty(r.firstFailure)){r.firstFailure=e.GetBaseException().Message;r.firstFailurePhase=r.phase;}r.success=false;Save();break;}if(!more)break;yield return current;}
  if(catalogFixture){
   yield return null; // Let deferred owned clone/root destruction finish before releasing catalog assets.
   var enemyRelease=VerifyEnemyCleanup();while(true){bool more=false;object current=null;try{more=enemyRelease.MoveNext();if(more)current=enemyRelease.Current;}catch(Exception e){r.error+=" Enemy cleanup: "+e;r.success=false;r.cleanup=false;break;}if(!more)break;yield return current;}
   if(r.integratedWorld){var worldRelease=VerifyIntegratedWorldCleanup();while(true){bool more=false;object current=null;try{more=worldRelease.MoveNext();if(more)current=worldRelease.Current;}catch(Exception e){r.error+=" World cleanup: "+e;r.success=false;r.cleanup=false;break;}if(!more)break;yield return current;}}
   var modelRelease=VerifyAutomaticModelDestruction();while(true){bool more=false;object current=null;try{more=modelRelease.MoveNext();if(more)current=modelRelease.Current;}catch(Exception e){r.error+=" Model cleanup: "+e;r.success=false;r.cleanup=false;break;}if(!more)break;yield return current;}
   var rewardRelease=CleanupEnemyRewards();while(rewardRelease.MoveNext())yield return rewardRelease.Current;
   var deathRelease=CleanupPlayerDeathEffect();while(deathRelease.MoveNext())yield return deathRelease.Current;
   try{Check(!host,"Owned body root destruction pending");CleanupBodyCatalog();}catch(Exception e){r.error+=" Catalog cleanup: "+e;r.success=false;r.cleanup=false;}
   var release=CleanupTeleportMaterial();while(true){bool more=false;object current=null;try{more=release.MoveNext();if(more)current=release.Current;}catch(Exception e){r.error+=" Material cleanup: "+e;r.success=false;r.cleanup=false;break;}if(!more)break;yield return current;}
   release=CleanupBarrierEffect();while(true){bool more=false;object current=null;try{more=release.MoveNext();if(more)current=release.Current;}catch(Exception e){r.error+=" Effect cleanup: "+e;r.success=false;r.cleanup=false;break;}if(!more)break;yield return current;}
   CleanupSpawnConfig();var geometryRelease=CleanupStageGeometry();while(geometryRelease.MoveNext())yield return geometryRelease.Current;AndroidMaterialPresentation.Finish();r.phase="complete";Save();
   RestartWorldAfterCleanup();
  }
 }
 IEnumerator RunSelectedProbe(bool catalogFixture){
  try{
   switch(r.id){case "nova-unity-raw":{var rawRoutine=NovaRawBoundary();while(rawRoutine.MoveNext())yield return rawRoutine.Current;}break;case "rewired-platform-contract":RewiredPlatformBoundary();break;case "network-local-connect":case "network-local-owner":LocalOwnership();break;case "team-manager-context":TeamContextProbe();break;case "run-singleton-context":RunContextProbe();break;case "body-state-spawn-state-primary-contract":case "body-state-spawn-state-primary-native":case "body-stat-buffs":case "body-knockback-handler":case "body-motor-awake":case "body-skill-awake":case "body-team-context":case "body-state-spawn-state-barrier-effect":case "body-state-spawn-state-auto-nova-spine-bringup":case "body-state-spawn-state-auto-nova-spine":case "body-state-spawn-state-auto-nova-controls":case "body-state-spawn-state-auto-skill-neutral":case "body-state-spawn-state-auto-skill-primary":case "body-state-spawn-state-auto-skill-secondary":case "body-state-spawn-state-auto-skill-utility":case "body-state-spawn-state-auto-skill-special":case "body-state-spawn-state-auto-model-neutral":case "body-state-spawn-state-auto-model-motion":case "body-state-spawn-state-auto-model-reverse":case "body-state-spawn-state-auto-model-aim":case "body-state-spawn-state-auto-direction-neutral":case "body-state-spawn-state-auto-direction-motion":case "body-state-spawn-state-auto-direction-reverse":case "body-state-spawn-state-auto-direction-aim":case "body-state-spawn-state-auto-health":case "body-state-spawn-state-auto-barrier":case "body-state-spawn-state-auto-body":case "body-state-spawn-state-auto-body-ground":case "body-state-spawn-state-auto-gravity":case "body-state-spawn-state-auto-land":case "body-state-spawn-state-auto-ground-stop":case "body-state-spawn-state-auto-ground-wall":case "body-state-spawn-state-auto-state":case "body-state-spawn-state-auto-motor":case "body-state-spawn-state-auto-motion":case "body-state-spawn-state-main-motor":case "body-state-spawn-state-main-neutral":case "body-state-spawn-state-main-motion":case "body-state-spawn-state-material":case "body-state-spawn-state-overlay":case "body-state-spawn-state-buff-removal":case "body-state-spawn-state-catalog":case "body-state-spawn-state-idle":case "body-state-spawn-state-entry":case "body-state-spawn-state-transition":case "body-state-spawn-loadout-catalog":case "body-state-spawn-body-start-catalog":case "body-state-spawn-master-start":case "body-state-spawn-body-start":case "body-state-spawn-automatic":case "body-state-spawn-awake":case "body-state-spawn-loadout":case "body-state-spawn-original":case "body-state-jump-serialize-body":case "body-state-jump-serialize-master":case "body-state-jump-catalog":case "body-state-jump-client":case "body-state-jump-owner":case "body-state-jump-client-event":case "body-state-jump-client-input":case "body-state-jump-authority":case "body-state-jump-context":case "body-state-jump-event":case "body-state-jump-input":case "body-state-ground-visual":case "body-state-ground-stop":case "body-state-ground-reverse":case "body-state-ground-wall":case "body-state-start":case "body-state-gravity":case "body-state-land":case "body-state-entry":case "body-state-input":case "body-state-motion":case "body-level-stats":case "body-computed-motor":case "body-original-stats":case "body-adoption-content":case "body-inventory-adoption":case "body-network-state":case "body-network-spawn":case "master-network-spawn":case "body-master-id":case "body-buff-storage":case "body-awake":case "body-registration":case "master-awake":{var bodyRoutine=BodyLifecycle();while(bodyRoutine.MoveNext())yield return bodyRoutine.Current;}break;case "state-jump-items":case "state-jump-inventory":case "state-jump-event":case "state-jump-input":LandingContext();break;case "gravity-rules":GravityRules();break;case "gravity-source-jump":case "state-ground-motion":case "state-ground-reverse":case "state-ground-wall":case "gravity-fall":case "gravity-jump-land":case "state-input":case "state-motion":LandingContext();break;case "buttons":Buttons();break;case "input":Input();break;case "motor-output":MotorOutput();break;case "motor-acceleration":MotorAcceleration();break;case "global-lifecycle":case "artifact-catalog":case "artifact-manager":case "landing-context":LandingContext();break;case "integrated-free":case "integrated-wall":case "integrated-jump":case "integrated-land":Integrated();break;default:throw new Exception("Unknown experiment");}
   r.success=true;
  }
  finally{try{CleanupLanding();}catch(Exception e){r.error+=" Cleanup: "+e;r.success=false;}if(obstacle)Destroy(obstacle);if(host)Destroy(host);if(recoveredClient!=null){recoveredClient.Disconnect();recoveredClient.Shutdown();if(ownsServer){NetworkServer.Shutdown();ownsServer=false;}StaticCall(typeof(ClientScene),"Shutdown");Check(!NetworkClient.active&&NetworkClient.allClients.Count==0,"Recovered client cleanup");}if(ownsServer)NetworkServer.Shutdown();FinishActiveClientSceneCleanup();if(ownsStateCatalog){BuildStateCatalog(Array.Empty<Type>());ownsStateCatalog=false;}r.cleanup=!ownsServer||!NetworkServer.active;r.success&=r.cleanup;r.phase=catalogFixture?"catalog-cleanup-pending":"complete";Save();}
 }
 void Buttons(){
  var b=new InputBankTest.ButtonState();Check(!b.justPressed&&!b.justReleased,"Initial edge");
  b.PushState(true);Check(b.justPressed&&!b.justReleased,"Press edge");b.hasPressBeenClaimed=true;
  b.PushState(true);Check(!b.justPressed&&b.down&&b.hasPressBeenClaimed,"Hold/claim");
  b.PushState(false);Check(b.justReleased&&!b.hasPressBeenClaimed,"Release/claim reset");b.PushState(false);Check(!b.justReleased,"Repeated release");
  b.PushState(true);Check(b.justPressed,"Second press");
 }
 InputBankTest InactiveInput(){host=new GameObject("Inactive input fixture");host.SetActive(false);return host.AddComponent<InputBankTest>();}
 void Input(){
  var bank=InactiveInput();Check(!host.activeInHierarchy,"Body lifecycle unexpectedly active");
  bank.SetRawMoveStates(new Vector2(.8f,0));Check(!bank.rawMoveRight.down,"Press threshold");
  bank.SetRawMoveStates(new Vector2(1,0));Check(bank.rawMoveRight.justPressed,"Right press");
  bank.SetRawMoveStates(new Vector2(.2f,0));Check(bank.rawMoveRight.down&&!bank.rawMoveRight.justPressed,"Hysteresis hold");
  bank.SetRawMoveStates(new Vector2(.05f,0));Check(bank.rawMoveRight.justReleased,"Hysteresis release");
  bank.SetRawMoveStates(new Vector2(-1,-1));Check(bank.rawMoveLeft.justPressed&&bank.rawMoveDown.justPressed&&!bank.rawMoveUp.down,"Opposite axes");
  bank.aimDirection=new Vector3(3,0,4);Check(Vector3.Distance(bank.aimDirection,new Vector3(.6f,0,.8f))<.00001f,"Aim normalization");
  bank.aimDirection=Vector3.zero;Check(bank.aimDirection==host.transform.forward,"Zero aim fallback");
  Check(!bank.CheckAnyButtonDown(),"Empty button set");bank.jump.PushState(true);Check(bank.CheckAnyButtonDown(),"Jump aggregation");
 }
 CharacterMotor InactiveMotor(){
  host=new GameObject("Inactive motor fixture");host.SetActive(false);host.AddComponent<CapsuleCollider>();return host.AddComponent<CharacterMotor>();
 }
 void MotorOutput(){
  var motor=InactiveMotor();motor.velocity=new Vector3(2,3,-4);var v=Vector3.zero;motor.UpdateVelocity(ref v,.02f);
  Check(v==motor.velocity,"Velocity callback changed value");var q=Quaternion.Euler(10,20,30);motor.UpdateRotation(ref q,.02f);Check(q==Quaternion.identity,"Motor rotation callback");
  Check(!host.activeInHierarchy,"Body lifecycle active");r.x=v.x;r.y=v.y;r.z=v.z;
 }
 void MotorAcceleration(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Existing network session");
  host=new GameObject("Owned motor identity");var identity=host.AddComponent<NetworkIdentity>();
  Check(NetworkServer.Listen("127.0.0.1",0),"Local listen failed");ownsServer=true;NetworkServer.Spawn(host);Check(identity.isServer&&identity.netId.Value!=0,"Spawn failed");
  host.SetActive(false);host.AddComponent<CapsuleCollider>();var motor=host.AddComponent<CharacterMotor>();var kinematic=host.AddComponent<KinematicCharacterMotor>();
  Call(motor,"Awake");motor.SetupCharacterMotor(kinematic);Call(motor,"UpdateAuthority");Check(motor.hasEffectiveAuthority&&Util.HasEffectiveAuthority(identity),"Original authority failed");
  var body=host.GetComponent<CharacterBody>();
  // Explicit diagnostic stat inputs; this does not exercise RecalculateStats or body startup.
  typeof(CharacterBody).GetProperty("moveSpeed").SetValue(body,7f);typeof(CharacterBody).GetProperty("acceleration").SetValue(body,10f);
  motor.airControl=1;motor.moveDirection=Vector3.right;motor.velocity=Vector3.zero;
  Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-1)<.0001f,"First acceleration step");
  for(int i=0;i<9;i++)Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-7)<.0001f,"Speed cap");r.x=motor.velocity.x;
  motor.moveDirection=Vector3.zero;for(int i=0;i<10;i++)Call(motor,"PreMove",.1f);Check(motor.velocity.sqrMagnitude<.000001f,"Braking");
  Check(!host.activeInHierarchy&&host.transform.position==Vector3.zero,"Unexpected activation/translation");
  NetworkServer.UnSpawn(host);
 }
 void Integrated(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Existing session");host=new GameObject("Original integrated motor");host.layer=30;var identity=host.AddComponent<NetworkIdentity>();
  Check(NetworkServer.Listen("127.0.0.1",0),"Local listen failed");ownsServer=true;NetworkServer.Spawn(host);Check(identity.isServer&&identity.netId.Value!=0,"Spawn failed");
  host.SetActive(false);host.AddComponent<CapsuleCollider>();var motor=host.AddComponent<CharacterMotor>();var k=host.AddComponent<KinematicCharacterMotor>();
  Call(motor,"Awake");Call(k,"Awake");motor.SetupCharacterMotor(k);Call(motor,"UpdateAuthority");Check(motor.hasEffectiveAuthority,"Original authority failed");
  k.SetCapsuleDimensions(.5f,2,1);k.CollidableLayers=1<<30;k.StableGroundLayers=1<<30;k.InteractiveRigidbodyHandling=false;k.SetGroundSolvingActivation(false);k.SetPosition(new Vector3(0,10,0));
  var body=host.GetComponent<CharacterBody>();typeof(CharacterBody).GetProperty("moveSpeed").SetValue(body,7f);typeof(CharacterBody).GetProperty("acceleration").SetValue(body,10f);typeof(CharacterBody).GetProperty("jumpPower").SetValue(body,5f);
  if(r.id=="landing-context"||r.id.StartsWith("gravity-")||r.id.StartsWith("state-")){typeof(CharacterBody).GetProperty("characterMotor").SetValue(body,motor);typeof(CharacterBody).GetField("transform",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(body,host.transform);}
  motor.airControl=1;motor.moveDirection=Vector3.right;motor.velocity=Vector3.zero;
  if(r.id.StartsWith("gravity-")||r.id.StartsWith("state-")){Additional(motor,k,body);NetworkServer.UnSpawn(host);return;}
  if(r.id=="integrated-wall"||(r.id=="integrated-land"||r.id=="landing-context")){
   obstacle=new GameObject("Owned integrated collision fixture");obstacle.layer=30;var box=obstacle.AddComponent<BoxCollider>();
   if(r.id=="integrated-wall"){obstacle.transform.position=new Vector3(2,11,0);box.size=new Vector3(1,10,20);motor.disableAirControlUntilCollision=true;motor.velocity=Vector3.right*7;}
   else{obstacle.transform.position=new Vector3(0,9.5f,0);box.size=new Vector3(20,1,20);k.SetPosition(new Vector3(0,10.2f,0));k.SetGroundSolvingActivation(true);motor.moveDirection=Vector3.zero;motor.velocity=Vector3.down;}
   Physics.SyncTransforms();
  }
  if(r.id=="integrated-jump"){motor.Jump(1,1);Check(motor.velocity==new Vector3(7,5,0),"Original Jump impulse mismatch");}
  r.phase="original-motor-solver";Save();
  Step(k,r.id=="integrated-jump"?25:50);r.x=k.TransientPosition.x;r.y=k.TransientPosition.y;r.z=k.TransientPosition.z;
  if(r.id=="integrated-free"){
   Check(Mathf.Abs(r.x-4.62f)<.01f,"Integrated acceleration displacement");Check(Mathf.Abs(motor.velocity.x-7)<.001f,"Velocity cap");motor.moveDirection=Vector3.zero;Step(k,50);Check(motor.velocity.sqrMagnitude<.000001f,"Integrated braking");
  }else if(r.id=="integrated-wall"){Check(r.x>.9f&&r.x<1.01f,"Original motor wall position outside expected boundary");Check(!motor.disableAirControlUntilCollision,"Original movement callback not observed");}
  else if(r.id=="integrated-jump")Check(Mathf.Abs(r.x-3.5f)<.01f&&Mathf.Abs(r.y-12.5f)<.01f,"Jump velocity integration");
  else Check(k.GroundingStatus.IsStableOnGround,"Original landing not stable");
  Check(!host.activeInHierarchy,"Unexpected body lifecycle");NetworkServer.UnSpawn(host);
 }
 static void Step(KinematicCharacterMotor k,int ticks){for(int i=0;i<ticks;i++){k.UpdatePhase1(.02f,true);k.UpdatePhase2(.02f,true);k.SetPositionAndRotation(k.TransientPosition,k.TransientRotation);}}

 static void StaticCall(Type type,string name,params object[] args){type.GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,args);}
 void LandingContext(){
  Check(!GlobalEventManager.instance&&!RunArtifactManager.instance,"Existing game manager context");
  if(r.id=="global-lifecycle"||r.id=="landing-context"||r.id.StartsWith("gravity-")||r.id.StartsWith("state-")){
   eventHost=new GameObject("Owned event context");eventHost.SetActive(false);var manager=eventHost.AddComponent<GlobalEventManager>();Call(manager,"OnEnable");Check(GlobalEventManager.instance==manager,"Original event singleton assignment failed");
   if(r.id=="global-lifecycle"){Call(manager,"OnDisable");Check(!GlobalEventManager.instance,"Original event singleton release failed");return;}
  }
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  artifactBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Artifact bundle missing");
  var artifact=artifactBundle.LoadAsset<ArtifactDef>(cfg.artifactAsset);Check(artifact&&artifact.cachedName=="WeakAssKnees"&&artifact.nameToken=="ARTIFACT_WEAKASSKNEES_NAME","Wrong recovered artifact");
  Check(artifact.unlockableDef&&artifact.smallIconSelectedSprite&&artifact.smallIconDeselectedSprite&&artifact.pickupModelPrefab,"Artifact closure incomplete");
  var defs=typeof(ArtifactCatalog).GetField("artifactDefs",BindingFlags.NonPublic|BindingFlags.Static);priorArtifacts=(ArtifactDef[])defs.GetValue(null);priorFallArtifact=RoR2Content.Artifacts.weakAssKneesArtifactDef;Check(priorArtifacts.Length==0,"Existing artifact catalog; refusing replacement");
  StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{new[]{artifact}});Check(ArtifactCatalog.artifactCount==1&&ArtifactCatalog.GetArtifactDef(artifact.artifactIndex)==artifact,"Original catalog identity failed");
  if(r.id=="artifact-catalog")return;
  StaticCall(typeof(RunArtifactManager),"Init");artifactHost=new GameObject("Inactive artifact context");artifactHost.SetActive(false);artifactManager=artifactHost.AddComponent<RunArtifactManager>();
  Call(artifactManager,"Awake");Call(artifactManager,"OnEnable");Check(RunArtifactManager.instance==artifactManager&&!artifactManager.IsArtifactEnabled(artifact),"Original artifact manager disabled-state mismatch");
  Check(!artifactHost.activeInHierarchy,"Run lifecycle unexpectedly active");
  if(r.id=="artifact-manager")return;
  priorFallArtifact=RoR2Content.Artifacts.weakAssKneesArtifactDef;Check(!priorFallArtifact,"Existing fall artifact binding");RoR2Content.Artifacts.WeakAssKnees=artifact;
  Integrated();
 }
 void CleanupLanding(){
  if(artifactManager){Call(artifactManager,"OnDisable");Call(artifactManager,"OnDestroy");}
  if(artifactHost)Destroy(artifactHost);
  if(eventHost){Call(eventHost.GetComponent<GlobalEventManager>(),"OnDisable");Destroy(eventHost);}
  if(priorArtifacts!=null){RoR2Content.Artifacts.WeakAssKnees=priorFallArtifact;StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{priorArtifacts});StaticCall(typeof(RunArtifactManager),"Init");}
  if(artifactBundle&&!ownsBodyCatalog)artifactBundle.Unload(true);
 }

 void GravityRules(){
  var g=new CharacterGravityParameters();Check(g.CheckShouldUseGravity(),"Default gravity");g.channeledAntiGravityGranterCount=1;Check(!g.CheckShouldUseGravity(),"Channeled antigravity");g.antiGravityNeutralizerCount=1;Check(g.CheckShouldUseGravity(),"Neutralizer precedence");g.environmentalAntiGravityGranterCount=1;Check(!g.CheckShouldUseGravity(),"Environmental precedence");
 }
 void Additional(CharacterMotor motor,KinematicCharacterMotor k,CharacterBody body){
  if(r.id.StartsWith("state-jump-")){JumpInputContext(motor,k,body);return;}
  if(r.id.StartsWith("state-ground-")){GroundedState(motor,k);return;}
  if(r.id.StartsWith("gravity-")){
   var savedGravity=Physics.gravity;try{
   if(r.id=="gravity-source-jump"){var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);Check(cfg.sourceGravity<0,"Missing measured source gravity");Physics.gravity=new Vector3(0,cfg.sourceGravity,0);}
   motor.gravityParameters=new CharacterGravityParameters{environmentalAntiGravityGranterCount=1};Check(!motor.useGravity,"Antigravity setter");motor.gravityParameters=new CharacterGravityParameters();Check(motor.useGravity,"Gravity setter did not enable original gravity");r.gravity=Physics.gravity.y;Check(r.gravity<0,"Expected downward gravity");motor.moveDirection=Vector3.zero;
   if(r.id=="gravity-fall"){
    Step(k,25);r.y=k.TransientPosition.y;Check(Mathf.Abs(motor.velocity.y-r.gravity*.5f)<.001f,"Gravity velocity");Check(Mathf.Abs(r.y-(10+r.gravity*.02f*.02f*325))<.001f,"Gravity integration");
   }else{
    obstacle=new GameObject("Owned gravity floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9.5f,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(20,1,20);Physics.SyncTransforms();k.SetGroundSolvingActivation(true);k.SetPosition(new Vector3(0,10.2f,0));Step(k,40);Check(k.GroundingStatus.IsStableOnGround,"Initial gravity landing");
    motor.Jump(0,1);r.peak=k.TransientPosition.y;for(int i=0;i<100;i++){Step(k,1);r.peak=Mathf.Max(r.peak,k.TransientPosition.y);}r.y=k.TransientPosition.y;Check(r.peak>(r.id=="gravity-source-jump"?10.2f:10.5f),"Jump did not rise");Check(k.GroundingStatus.IsStableOnGround&&Mathf.Abs(r.y-10.01f)<.02f,"Gravity jump did not land");Check(motor.jumpCount==0,"Original landing jump reset");
   }
   }finally{Physics.gravity=savedGravity;}
   Check(Physics.gravity==savedGravity,"Gravity restoration");
  }else{
   var input=host.AddComponent<InputBankTest>();var machine=host.AddComponent<EntityStateMachine>();Call(machine,"Awake");var state=new EntityStates.GenericCharacterMain();machine.SetState(state);Check(machine.state==state&&machine.commonComponents.inputBank==input,"Original state entry or component cache");
   input.moveVector=Vector3.right;input.aimDirection=new Vector3(3,0,4);
   if(r.id=="state-input"){
    input.emoteRequest=2;input.jump.PushState(true);Call(state,"GatherInputs");var flags=BindingFlags.NonPublic|BindingFlags.Instance;
    Check((Vector3)typeof(EntityStates.GenericCharacterMain).GetField("moveVector",flags).GetValue(state)==Vector3.right,"State move input");Check((bool)typeof(EntityStates.GenericCharacterMain).GetField("jumpInputReceived",flags).GetValue(state),"State jump edge");Check(input.emoteRequest==-1,"Emote consumption");input.jump.hasPressBeenClaimed=true;Call(state,"GatherInputs");Check(!(bool)typeof(EntityStates.GenericCharacterMain).GetField("jumpInputReceived",flags).GetValue(state),"Claimed jump not excluded");
   }else{
    motor.moveDirection=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}r.x=k.TransientPosition.x;Check(Mathf.Abs(r.x-4.62f)<.01f,"Original state-driven displacement");input.moveVector=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}Check(motor.moveDirection==Vector3.zero&&motor.velocity.sqrMagnitude<.000001f,"State-driven stop");
   }
   Call(machine,"OnDestroy");Check(machine.state==null&&motor.moveDirection==Vector3.zero,"Original state exit cleanup");
  }
  Check(!host.activeInHierarchy,"Unexpected body activation");
 }

 void GroundedState(CharacterMotor motor,KinematicCharacterMotor k){
  var savedGravity=Physics.gravity;EntityStateMachine machine=null;
  try{
   var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);Check(cfg.sourceGravity<0,"Missing source gravity");Physics.gravity=new Vector3(0,cfg.sourceGravity,0);r.gravity=Physics.gravity.y;
   motor.gravityParameters=new CharacterGravityParameters{environmentalAntiGravityGranterCount=1};motor.gravityParameters=new CharacterGravityParameters();Check(motor.useGravity,"Original gravity not active");motor.moveDirection=Vector3.zero;
   obstacle=new GameObject("Owned grounded state floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9.5f,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(40,1,40);
   if(r.id=="state-ground-wall"){var wall=new GameObject("Owned state wall");wall.transform.SetParent(obstacle.transform);wall.layer=30;wall.transform.position=new Vector3(2,11,0);wall.AddComponent<BoxCollider>().size=new Vector3(1,10,20);}
   Physics.SyncTransforms();k.SetGroundSolvingActivation(true);k.SetPosition(new Vector3(0,10.2f,0));Step(k,40);Check(k.GroundingStatus.IsStableOnGround,"State fixture failed initial landing");
   var input=host.AddComponent<InputBankTest>();machine=host.AddComponent<EntityStateMachine>();Call(machine,"Awake");var state=new EntityStates.GenericCharacterMain();machine.SetState(state);Check(machine.state==state,"Original grounded state entry");input.moveVector=Vector3.right;
   for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}r.x=k.TransientPosition.x;r.y=k.TransientPosition.y;
   Check(k.GroundingStatus.IsStableOnGround&&Mathf.Abs(r.y-10.01f)<.02f,"State movement lost grounding");
   if(r.id=="state-ground-wall")Check(r.x>.9f&&r.x<1.01f,"State movement crossed wall boundary");
   else Check(Mathf.Abs(r.x-4.62f)<.02f,"Grounded state acceleration displacement");
   if(r.id=="state-ground-reverse"){
    input.moveVector=Vector3.left;for(int i=0;i<100;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}r.z=k.TransientPosition.x;
    Check(r.z<r.x-3&&Mathf.Abs(motor.velocity.x+7)<.001f,"Original input reversal failed");Check(k.GroundingStatus.IsStableOnGround,"Reversal lost grounding");
   }
   input.moveVector=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}Check(Mathf.Abs(motor.velocity.x)<.001f&&motor.moveDirection==Vector3.zero,"Grounded state failed to stop");Check(k.GroundingStatus.IsStableOnGround,"Stopped state lost grounding");Check(!host.activeInHierarchy,"Body unexpectedly active");
  }finally{if(machine)Call(machine,"OnDestroy");Physics.gravity=savedGravity;}
  Check(machine.state==null&&motor.moveDirection==Vector3.zero,"Grounded state exit cleanup");Check(Physics.gravity==savedGravity,"Gravity not restored");
 }

 void JumpInputContext(CharacterMotor motor,KinematicCharacterMotor k,CharacterBody body){
  if(r.id=="state-jump-event"){
   Check(body.isServer&&body.hasAuthority&&body.netId.Value!=0,"Body server identity not available");
   body.onJump+=CountJump;try{body.TriggerJumpEventGlobally();Check(r.jumpEvents==1,"Original authority jump event missing");}finally{body.onJump-=CountJump;}
   Check(!NetworkClient.active,"Unexpected client; server-only dispatch fixture");return;
  }
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  var boost=artifactBundle.LoadAsset<ItemDef>(cfg.jumpBoostAsset);var strike=artifactBundle.LoadAsset<ItemDef>(cfg.jumpStrikeAsset);
  Check(boost&&strike&&boost.name=="JumpBoost"&&strike.name=="JumpDamageStrike","Wrong recovered jump items");
  Check(boost.pickupIconSprite&&strike.pickupIconSprite&&boost.pickupModelPrefab&&strike.pickupModelPrefab,"Missing serialized item references");
  Check(ItemCatalog.itemCount==0&&ItemCatalog.tier1ItemList.Count==0&&ItemCatalog.tier2ItemList.Count==0&&ItemCatalog.tier3ItemList.Count==0&&ItemCatalog.lunarItemList.Count==0,"Existing item catalog; refuse replacement");
  var priorItems=RoR2.ContentManagement.ContentManager._itemDefs;
  var oldBoost=RoR2Content.Items.JumpBoost;var oldStrike=DLC3Content.Items.JumpDamageStrike;Inventory inventory=null;GameObject inventoryHost=null;var savedGravity=Physics.gravity;EntityStateMachine machine=null;
  try{
   RoR2.ContentManagement.ContentManager._itemDefs=new ItemDef[0];
   StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{new[]{boost,strike}});
   Check(ItemCatalog.itemCount==2&&boost.itemIndex!=strike.itemIndex&&ItemCatalog.GetItemDef(boost.itemIndex)==boost&&ItemCatalog.GetItemDef(strike.itemIndex)==strike,"Original item catalog identity");
   Check(ItemCatalog.FindItemIndex("JumpBoost")==boost.itemIndex&&ItemCatalog.FindItemIndex("JumpDamageStrike")==strike.itemIndex,"Original item name lookup");
   if(r.id!="state-jump-items"){
    inventoryHost=new GameObject("Inactive original inventory");inventoryHost.SetActive(false);inventoryHost.AddComponent<NetworkIdentity>();inventory=inventoryHost.AddComponent<Inventory>();Call(inventory,"Awake");
    Check(inventory.GetItemCountEffective(boost)==0&&inventory.GetItemCountEffective(strike)==0,"Empty original inventory counts");
    Check(inventory.GetItemCountPermanent(boost)==0&&inventory.GetItemCountPermanent(strike)==0,"Empty permanent inventory counts");
    var stacks=typeof(Inventory).GetField("effectiveItemStacks",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.Public);
    Check(((ItemCollection)stacks.GetValue(inventory)).isValid,"Original pooled item storage invalid");
    if(r.id=="state-jump-input"){
     Check(!oldBoost&&!oldStrike,"Existing original item bindings");RoR2Content.Items.JumpBoost=boost;DLC3Content.Items.JumpDamageStrike=strike;
     typeof(CharacterBody).GetProperty("inventory").SetValue(body,inventory);typeof(CharacterBody).GetProperty("maxJumpCount").SetValue(body,1);body.baseJumpCount=1;
     Check(body.isServer&&body.hasAuthority,"Original body authority missing");body.onJump+=CountJump;
     Check(cfg.sourceGravity<0,"Missing original gravity");Physics.gravity=new Vector3(0,cfg.sourceGravity,0);r.gravity=Physics.gravity.y;
     motor.gravityParameters=new CharacterGravityParameters{environmentalAntiGravityGranterCount=1};motor.gravityParameters=new CharacterGravityParameters();motor.moveDirection=Vector3.zero;
     obstacle=new GameObject("Owned input jump floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9.5f,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(40,1,40);Physics.SyncTransforms();k.SetGroundSolvingActivation(true);k.SetPosition(new Vector3(0,10.2f,0));Step(k,40);Check(k.GroundingStatus.IsStableOnGround,"Jump input initial grounding");
     var input=host.AddComponent<InputBankTest>();machine=host.AddComponent<EntityStateMachine>();Call(machine,"Awake");machine.SetState(new EntityStates.GenericCharacterMain());
     input.jump.PushState(true);machine.ManagedFixedUpdate(.02f);Check(motor.jumpCount==1&&motor.velocity.y>0&&r.jumpEvents==1,"Original input did not produce jump/event");
     input.jump.PushState(false);r.peak=k.TransientPosition.y;
     for(int i=0;i<100;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);r.peak=Mathf.Max(r.peak,k.TransientPosition.y);}
     r.y=k.TransientPosition.y;Check(r.peak>10.2f,"Input jump did not rise");Check(k.GroundingStatus.IsStableOnGround&&Mathf.Abs(r.y-10.01f)<.02f&&motor.jumpCount==0,"Input jump did not land/reset");Check(r.jumpEvents==1,"Unexpected repeated jump events");
    }
    Call(inventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");Check(!((ItemCollection)stacks.GetValue(inventory)).isValid,"Original inventory disposal failed");inventory=null;
   }
  }finally{
   try{if(machine)Call(machine,"OnDestroy");body.onJump-=CountJump;if(inventory){Call(inventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");}}
   finally{Physics.gravity=savedGravity;RoR2Content.Items.JumpBoost=oldBoost;DLC3Content.Items.JumpDamageStrike=oldStrike;typeof(CharacterBody).GetProperty("inventory").SetValue(body,null);StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{new ItemDef[0]});ItemCatalog.tier1ItemList.Clear();ItemCatalog.tier2ItemList.Clear();ItemCatalog.tier3ItemList.Clear();ItemCatalog.lunarItemList.Clear();RoR2.ContentManagement.ContentManager._itemDefs=priorItems;if(inventoryHost)Destroy(inventoryHost);}
  }
  Check(ItemCatalog.itemCount==0&&RoR2.ContentManagement.ContentManager._itemDefs==priorItems&&Physics.gravity==savedGravity,"Jump fixture restoration");Check(!host.activeInHierarchy,"Body lifecycle unexpectedly active");
 }
 void CountJump(){r.jumpEvents++;}

 IEnumerator BodyLifecycle(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Unexpected network session");
  if(r.id=="master-awake"||r.id=="master-network-spawn"){MasterLifecycle();yield break;}
  var fields=typeof(BuffCatalog).GetFields(BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);var previous=new System.Collections.Generic.Dictionary<FieldInfo,object>();
  foreach(var f in fields)if(f.FieldType.IsArray)previous[f]=f.GetValue(null);
  var names=(IDictionary)typeof(BuffCatalog).GetField("nameToBuffIndex",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);Check(names.Count==0,"Existing buff catalog; refuse diagnostic replacement");
  BuffDef medkitBuff=null,tonicBuff=null,soulBuff=null;var oldMedkit=RoR2Content.Buffs.MedkitHeal;var oldTonic=RoR2Content.Buffs.TonicBuff;var oldSoul=DLC2Content.Buffs.SoulCost;BuffDef intangibleBuff=null;var oldIntangible=RoR2Content.Buffs.Intangible;BuffDef hiddenBuff=null;var oldHidden=RoR2Content.Buffs.HiddenInvincibility;BuffDef knockBuff=null,juggleBuff=null;var oldKnock=DLC2Content.Buffs.KnockUpHitEnemies;var oldJuggle=DLC2Content.Buffs.KnockUpHitEnemiesJuggleCount;
  Action restoreAdoption=null;TeamComponent team=null;GenericSkill[] initializedSkills=null;CharacterMotor initializedMotor=null;
  GameObject linkedMasterHost=null;CharacterMaster linkedMaster=null;Inventory linkedInventory=null;
  CharacterBody body=null;Action<Transform> modelSubscription=null;Action<CharacterBody> awake=observed=>{if(observed==body)r.awakeEvents++;};bool registered=false;
  try{
   StaticCall(typeof(BuffCatalog),"SetBuffDefs",new object[]{new BuffDef[0]});Check(BuffCatalog.buffCount==0,"Empty diagnostic buff catalog initialization");
   var first=BuffCatalog.GetPerBuffBuffer<int>();var second=BuffCatalog.GetPerBuffBuffer<int>();Check(first.Length==0&&second.Length==0&&!ReferenceEquals(first,second),"Original buff buffer allocation");
   if(r.id!="body-buff-storage"){
    var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);if(!artifactBundle)artifactBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Body bundle missing");var prefab=artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);Check(prefab&&!prefab.activeSelf,"Recovered body root not isolated");
    if(cfg.statBuffs&&r.id!="body-awake"){
     Check(!oldKnock&&!oldJuggle,"Existing knockback buff bindings");knockBuff=artifactBundle.LoadAsset<BuffDef>(cfg.knockBuffAsset);juggleBuff=artifactBundle.LoadAsset<BuffDef>(cfg.juggleBuffAsset);Check(knockBuff&&juggleBuff&&knockBuff.name=="bdKnockUpHitEnemies"&&juggleBuff.name=="bdKnockUpHitEnemiesJuggleCount","Recovered buff identities");StaticCall(typeof(BuffCatalog),"SetBuffDefs",new object[]{string.IsNullOrEmpty(cfg.hiddenBuffAsset)?new[]{knockBuff,juggleBuff}:new[]{knockBuff,juggleBuff,hiddenBuff=artifactBundle.LoadAsset<BuffDef>(cfg.hiddenBuffAsset),intangibleBuff=artifactBundle.LoadAsset<BuffDef>(cfg.intangibleBuffAsset),medkitBuff=artifactBundle.LoadAsset<BuffDef>(cfg.medkitBuffAsset),tonicBuff=artifactBundle.LoadAsset<BuffDef>(cfg.tonicBuffAsset),soulBuff=artifactBundle.LoadAsset<BuffDef>(cfg.soulBuffAsset)}.Concat(EnemyDeathBuffs(cfg)).Concat(ChestPurchaseBuffs(cfg)).Concat(ObjectiveBuffs(cfg)).Concat(MoonBuffs(cfg)).Concat(WorldLootBuffs(cfg)).ToArray()});if(hiddenBuff){Check(!oldHidden&&hiddenBuff.name=="bdHiddenInvincibility","Actual hidden buff identity/context");RoR2Content.Buffs.HiddenInvincibility=hiddenBuff;Check(!oldIntangible&&intangibleBuff&&intangibleBuff.name=="bdIntangible","Actual Intangible buff identity/context");RoR2Content.Buffs.Intangible=intangibleBuff;Check(!oldMedkit&&!oldTonic&&!oldSoul&&medkitBuff&&tonicBuff&&soulBuff&&medkitBuff.name=="bdMedkitHeal"&&tonicBuff.name=="bdTonicBuff"&&soulBuff.name=="bdSoulCost","Complete original removal-definition context");RoR2Content.Buffs.MedkitHeal=medkitBuff;RoR2Content.Buffs.TonicBuff=tonicBuff;DLC2Content.Buffs.SoulCost=soulBuff;}DLC2Content.Buffs.KnockUpHitEnemies=knockBuff;DLC2Content.Buffs.KnockUpHitEnemiesJuggleCount=juggleBuff;
     Check(BuffCatalog.buffCount==(hiddenBuff?7+(cfg.enemySpine?1:0)+(cfg.originalChestPurchase?1:0)+(cfg.teleporterLoop?1:0)+(cfg.moonMission?2:0)+(cfg.worldAdditionalLootItems!=null&&cfg.worldAdditionalLootItems.Contains("SlowOnHit")?1:0):2)&&knockBuff.buffIndex!=juggleBuff.buffIndex,"Original diagnostic buff indices");foreach(var def in new[]{knockBuff,juggleBuff})Check(BuffCatalog.GetBuffDef(def.buffIndex)==def&&BuffCatalog.FindBuffIndex(def.name)==def.buffIndex,"Original buff lookup identity");
    }
    if(r.id=="body-adoption-content"||r.id=="body-inventory-adoption"||IsStatsProbe()){restoreAdoption=PrepareAdoption(cfg);if(r.id=="body-adoption-content")yield break;}
    host=Instantiate(prefab);body=host.GetComponent<CharacterBody>();Check(body&&!host.activeInHierarchy,"Recovered body missing or active");foreach(var component in host.GetComponentsInChildren<Component>(true))Check(component,"Missing recovered body script");
    CharacterBody.onBodyAwakeGlobal+=awake;try{Call(body,"Awake");}finally{CharacterBody.onBodyAwakeGlobal-=awake;}
    modelSubscription=(Action<Transform>)Delegate.CreateDelegate(typeof(Action<Transform>),body,typeof(CharacterBody).GetMethod("OnModelChanged",BindingFlags.NonPublic|BindingFlags.Instance));
    Check(r.awakeEvents==1,"Original body awake event");Check(body.networkIdentity==host.GetComponent<NetworkIdentity>()&&body.characterMotor==host.GetComponent<CharacterMotor>()&&body.inputBank==host.GetComponent<InputBankTest>(),"Original body component caches");
    Check(body.healthComponent==host.GetComponent<HealthComponent>()&&body.skillLocator==host.GetComponent<SkillLocator>(),"Original health/skill references");Check(body.modelLocator&&body.modelLocator.modelTransform&&body.hurtBoxGroup&&body.mainHurtBox&&body.coreTransform,"Recovered model/hurtbox/core linkage: locator="+(bool)body.modelLocator+", model="+(body.modelLocator&&(bool)body.modelLocator.modelTransform)+", group="+(bool)body.hurtBoxGroup+", main="+(bool)body.mainHurtBox+", core="+(bool)body.coreTransform+", objects="+host.GetComponentsInChildren<Transform>(true).Length);
    Check(body.hurtBoxGroup==body.modelLocator.modelTransform.GetComponent<HurtBoxGroup>()&&body.mainHurtBox==body.hurtBoxGroup.mainHurtBox,"Original hurtbox identity");Check(Mathf.Abs(body.radius-host.GetComponent<CapsuleCollider>().radius)<.0001f,"Original capsule radius cache");
    var buffs=(int[])typeof(CharacterBody).GetField("buffs",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(body);Check(buffs!=null&&buffs.Length==BuffCatalog.buffCount,"Original body buff storage");
    var network=host.GetComponent<NetworkStateMachine>();Check(network,"Recovered network state-machine missing");var machines=(EntityStateMachine[])typeof(NetworkStateMachine).GetField("stateMachines",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(network);Check(machines.Length>0,"Recovered network state-machine list");foreach(var machine in machines)Check(machine&&machine.gameObject==host,"Recovered state-machine linkage");
    if(r.id=="body-motor-awake"||IsStatsProbe()||r.id=="body-knockback-handler"){initializedMotor=body.characterMotor;Call(initializedMotor,"Awake");var capsule=host.GetComponent<CapsuleCollider>();Check(initializedMotor.capsuleHeight==capsule.height&&initializedMotor.capsuleRadius==capsule.radius,"Original motor capsule cache");Check(initializedMotor.initialCapsuleHeight==capsule.height&&initializedMotor.initialCapsuleRadius==capsule.radius,"Original initial capsule dimensions");Check(Mathf.Abs(body.bestFitRadius-Mathf.Max(body.radius,capsule.height))<.0001f,"Original body effect bounds");}
    if(cfg.statBuffs&&r.id!="body-awake"){Check(body.GetBuffCount(knockBuff.buffIndex)==0&&body.GetBuffCount(juggleBuff.buffIndex)==0,"Original empty buff counts");}
    if(r.id=="body-knockback-handler"){
     Check(!body.characterMotor.hasEffectiveAuthority&&!body.characterMotor.isGrounded,"Unexpected diagnostic motor authority/grounding branch");r.phase="original-knockback-handler";Save();typeof(CharacterBody).GetMethod("UpdateKnockBackHitVisualsAndGracePeriod",BindingFlags.NonPublic|BindingFlags.Instance,null,Type.EmptyTypes,null).Invoke(body,null);Check(body.GetBuffCount(knockBuff.buffIndex)==0&&body.GetBuffCount(juggleBuff.buffIndex)==0,"Empty handler changed buff counts");
    }
    if(r.id=="body-skill-awake"){initializedSkills=host.GetComponents<GenericSkill>();InitializeSkills(body,initializedSkills);}
    if(r.id=="body-team-context"){team=body.teamComponent;Check(team,"Recovered team component missing");Call(team,"Awake");Check(team.body==body,"Original team body cache");team.teamIndex=TeamIndex.None;team.teamIndex=TeamIndex.Player;Check(TeamComponent.GetTeamMembers(TeamIndex.Player).Contains(team),"Original team membership");foreach(var hurt in body.hurtBoxGroup.hurtBoxes)Check(hurt.teamIndex==TeamIndex.Player,"Original hurtbox team propagation");Call(team,"OnDestroy");Check(!TeamComponent.GetTeamMembers(TeamIndex.Player).Contains(team),"Original team removal");team=null;}
    if(r.id=="body-network-state"){
     Call(network,"Awake");for(int i=0;i<machines.Length;i++)Check(machines[i].networkIndex==i&&machines[i].networker==network&&machines[i].networkIdentity==body.networkIdentity,"Original network state-machine binding");
    }
    if(r.id=="body-network-spawn"||r.id=="body-master-id"||r.id=="body-inventory-adoption"||IsStatsProbe()){
     SpawnRecovered(host);Call(body,"UpdateAuthority");r.bodyId=body.networkIdentity.netId.Value;Check(body.hasEffectiveAuthority&&Util.HasEffectiveAuthority(body.networkIdentity),"Recovered body effective authority");
     if(r.id=="body-master-id"||r.id=="body-inventory-adoption"||IsStatsProbe()){
      var masterPrefab=artifactBundle.LoadAsset<GameObject>(cfg.masterAsset);Check(masterPrefab&&!masterPrefab.activeSelf,"Recovered master not isolated");linkedMasterHost=Instantiate(masterPrefab);linkedInventory=linkedMasterHost.GetComponent<Inventory>();Call(linkedInventory,"Awake");linkedMaster=linkedMasterHost.GetComponent<CharacterMaster>();Call(linkedMaster,"Awake");SpawnRecovered(linkedMasterHost);Call(linkedMaster,"UpdateAuthority");r.masterId=linkedMaster.networkIdentity.netId.Value;
      Check(r.masterId!=r.bodyId&&linkedMaster.hasEffectiveAuthority,"Distinct recovered master identity/authority");Check(!body.inventory,"Unexpected adopted inventory before link");body.masterObject=linkedMasterHost;
      Check(body.GetMasterObjectId()==linkedMaster.networkIdentity.netId,"Original body master ID setter");Check(NetworkServer.FindLocalObject(body.GetMasterObjectId())==linkedMasterHost,"Actual server master resolution");Check(!body.inventory&&!linkedMaster.hasBody,"Unexpected inventory adoption or reciprocal link");Check(!linkedMasterHost.activeInHierarchy,"Master activation occurred");
      if(r.id=="body-inventory-adoption"||IsStatsProbe()){
       r.phase="original-master-getter";Save();Action observed=()=>r.inventoryEvents++;body.onInventoryChanged+=observed;
       try{Check(body.masterObject==linkedMasterHost&&body.master==linkedMaster,"Original master getter identity");Check(body.inventory==linkedInventory&&body.isPlayerControlled,"Original inventory/player-controller adoption");Check(r.inventoryEvents==1,"Original inventory callback count");Check(body.masterObject==linkedMasterHost&&r.inventoryEvents==1,"Cached getter repeated callback");Check(!linkedMaster.hasBody,"Unexpected reciprocal link");Check(!host.GetComponent<CharacterBody.QuestVolatileBatteryBehaviorServer>(),"Empty equipment created quest behavior");}
       finally{body.onInventoryChanged-=observed;}
       if(IsStatsProbe()){initializedSkills=host.GetComponents<GenericSkill>();InitializeSkills(body,initializedSkills);var statsRoutine=OriginalStats(body,cfg);while(statsRoutine.MoveNext())yield return statsRoutine.Current;}
      }
     }
    }
    if(r.id=="body-registration"){
     var count=CharacterBody.readOnlyInstancesList.Count;Call(body,"OnEnable");registered=true;Check(CharacterBody.readOnlyInstancesList.Count==count+1&&CharacterBody.readOnlyInstancesList.Contains(body),"Original body registration");Call(body,"OnDisable");registered=false;Check(CharacterBody.readOnlyInstancesList.Count==count&&!CharacterBody.readOnlyInstancesList.Contains(body),"Original body unregistration");
    }
    Check(!host.activeInHierarchy,"Broad body activation occurred");
   }
  }finally{
   if(initializedMotor)Call(initializedMotor,"OnDestroy");
   if(initializedSkills!=null)foreach(var skill in initializedSkills)Call(skill,"OnDestroy");
   if(team)Call(team,"OnDestroy");
   if(body&&body.inventory){var callback=(Action)Delegate.CreateDelegate(typeof(Action),body,typeof(CharacterBody).GetMethod("OnInventoryChanged",BindingFlags.NonPublic|BindingFlags.Instance));body.inventory.onInventoryChanged-=callback;}
   if(linkedMasterHost){NetworkServer.UnSpawn(linkedMasterHost);if(linkedMaster)Call(linkedMaster,"OnDestroy");if(linkedInventory){Call(linkedInventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");}Destroy(linkedMasterHost);}
   if(host&&ownsServer){var id=host.GetComponent<NetworkIdentity>().netId;NetworkServer.UnSpawn(host);Check(!NetworkServer.FindLocalObject(id),"Body network object not removed");}
   if(registered)Call(body,"OnDisable");if(body&&body.modelLocator&&modelSubscription!=null)body.modelLocator.onModelChanged-=modelSubscription;
   RoR2Content.Buffs.MedkitHeal=oldMedkit;RoR2Content.Buffs.TonicBuff=oldTonic;DLC2Content.Buffs.SoulCost=oldSoul;RoR2Content.Buffs.Intangible=oldIntangible;RoR2Content.Buffs.HiddenInvincibility=oldHidden;DLC2Content.Buffs.KnockUpHitEnemies=oldKnock;DLC2Content.Buffs.KnockUpHitEnemiesJuggleCount=oldJuggle;names.Clear();
   foreach(var pair in previous)pair.Key.SetValue(null,pair.Value);Check(names.Count==0,"Buff name mapping restoration");if(restoreAdoption!=null)restoreAdoption();
  }
  foreach(var pair in previous)Check(ReferenceEquals(pair.Key.GetValue(null),pair.Value),"Buff catalog restoration");
 }
 void RestoreAdoption(ItemDef[] priorItems,FieldInfo[] fields,ItemDef[] old,EquipmentDef oldBattery){
  for(int i=0;i<fields.Length;i++)fields[i].SetValue(null,old[i]);RoR2Content.Equipment.QuestVolatileBattery=oldBattery;
  StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{new ItemDef[0]});ItemCatalog.tier1ItemList.Clear();ItemCatalog.tier2ItemList.Clear();ItemCatalog.tier3ItemList.Clear();ItemCatalog.lunarItemList.Clear();RoR2.ContentManagement.ContentManager._itemDefs=priorItems;
  StaticCall(typeof(EquipmentCatalog),"SetEquipmentDefs",new object[]{new EquipmentDef[0]});
 }
 Action PrepareAdoption(Result cfg){
  Check(ItemCatalog.itemCount==0&&EquipmentCatalog.equipmentCount==0,"Existing catalog; refuse replacement");
  var paths=new System.Collections.Generic.List<string>{cfg.lunarPrimaryAsset,cfg.lunarSecondaryAsset,cfg.lunarUtilityAsset,cfg.lunarSpecialAsset};var names=new System.Collections.Generic.List<string>{"LunarPrimaryReplacement","LunarSecondaryReplacement","LunarUtilityReplacement","LunarSpecialReplacement"};
  if(r.id.StartsWith("body-state-jump-")||IsNovaInput()){paths.Add(cfg.jumpBoostAsset);paths.Add(cfg.jumpStrikeAsset);names.Add("JumpBoost");names.Add("JumpDamageStrike");}
  if(IsPrimaryFire()||IsPlayableSpine()){paths.Add(cfg.primaryItemAsset);names.Add("IncreasePrimaryDamage");}
  if(!string.IsNullOrEmpty(cfg.gummyAsset)){paths.Add(cfg.gummyAsset);names.Add("GummyCloneIdentifier");}
  if(cfg.enemySpine){paths.AddRange(cfg.enemyDeathItems);names.AddRange(new[]{"ExtraLife","ExtraLifeConsumed","ExtraLifeVoid","ExtraLifeVoidConsumed"});}
  if(cfg.enemyRewards){paths.AddRange(cfg.enemySpawnItems);names.AddRange(new[]{"UseAmbientLevel","BoostHp","BoostDamage"});}
  if(cfg.originalItemPickup){paths.Add(cfg.statItemAsset);paths.Add(cfg.junkAsset);names.Add("Syringe");names.Add("Junk");}
  if(cfg.originalInteractionSelection){paths.Add(cfg.lowerPricedChestsAsset);names.Add("LowerPricedChests");}
  if(cfg.originalChestDropTable){paths.Add(cfg.randomlyLunarAsset);paths.Add(cfg.chestLootItemAsset);names.Add("RandomlyLunar");names.Add("ChainLightning");}
  if(cfg.originalChestPurchase){paths.Add(cfg.lowerPricedConsumedAsset);names.Add("LowerPricedChestsConsumed");}
  if(cfg.integratedWorld){paths.AddRange(new[]{cfg.worldGlassesAsset,cfg.worldSlugAsset});names.AddRange(new[]{"CritGlasses","HealWhileSafe"});}
  if(cfg.teleporterLoop){paths.AddRange(cfg.objectiveItemAssets);names.AddRange(cfg.objectiveItemNames);}
  var defs=new ItemDef[paths.Count];var fields=new FieldInfo[paths.Count];var old=new ItemDef[paths.Count];
  for(int i=0;i<defs.Length;i++){defs[i]=artifactBundle.LoadAsset<ItemDef>(paths[i]);Check(defs[i]&&defs[i].name==names[i],"Required recovered ItemDef identity "+names[i]);fields[i]=((names[i]=="IncreasePrimaryDamage"||names[i]=="LowerPricedChests"||names[i]=="LowerPricedChestsConsumed")?typeof(DLC2Content.Items):(names[i]=="GummyCloneIdentifier"||names[i]=="RandomlyLunar"||names[i].StartsWith("ExtraLifeVoid"))?typeof(DLC1Content.Items):(names[i]=="JumpDamageStrike"||names[i]=="Junk")?typeof(DLC3Content.Items):typeof(RoR2Content.Items)).GetField(names[i]);old[i]=(ItemDef)fields[i].GetValue(null);Check(!old[i],"Existing item binding");}
  var battery=artifactBundle.LoadAsset<EquipmentDef>(cfg.batteryAsset);Check(battery&&battery.name=="QuestVolatileBattery","Required original EquipmentDef identity");var oldBattery=RoR2Content.Equipment.QuestVolatileBattery;Check(!oldBattery,"Existing equipment binding");var priorItems=RoR2.ContentManagement.ContentManager._itemDefs;var allDefs=defs.Concat(MoonItems(cfg)).ToArray();Check(allDefs.Select(x=>x.name).Distinct().Count()==allDefs.Length,"Duplicate composed ItemDef identities");
  Action restore=()=>RestoreAdoption(priorItems,fields,old,oldBattery);
  try{
   RoR2.ContentManagement.ContentManager._itemDefs=new ItemDef[0];StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{allDefs});StaticCall(typeof(EquipmentCatalog),"SetEquipmentDefs",new object[]{new[]{battery}});
   for(int i=0;i<defs.Length;i++){Check(defs[i].itemIndex!=ItemIndex.None&&ItemCatalog.GetItemDef(defs[i].itemIndex)==defs[i]&&ItemCatalog.FindItemIndex(names[i])==defs[i].itemIndex,"Original Lunar catalog identity");fields[i].SetValue(null,defs[i]);}
   RoR2Content.Equipment.QuestVolatileBattery=battery;Check(battery.equipmentIndex!=EquipmentIndex.None&&EquipmentCatalog.GetEquipmentDef(battery.equipmentIndex)==battery,"Original battery catalog identity");Check(!EquipmentCatalog.GetEquipmentDef(EquipmentIndex.None),"Empty equipment must remain absent");Check(ItemCatalog.itemCount==allDefs.Length&&EquipmentCatalog.equipmentCount==1,"Diagnostic catalog size");
   return restore;
  }catch{restore();throw;}
 }
 void InitializeSkills(CharacterBody body,GenericSkill[] skills){
  Check(skills.Length>=4,"Recovered skill slots missing");r.phase="original-skill-awake";Save();
  foreach(var skill in skills){Check(skill.skillFamily&&skill.skillFamily.defaultSkillDef,"Recovered default skill missing");Call(skill,"Awake");Check(skill.characterBody==body&&skill.skillDef==skill.skillFamily.defaultSkillDef,"Original default skill assignment");Check(skill.stateMachine&&skill.stateMachine.gameObject==host,"Original skill state-machine resolution");var cooldown=(float)typeof(GenericSkill).GetField("finalRechargeInterval",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(skill);Check(!float.IsNaN(cooldown)&&!float.IsInfinity(cooldown),"Invalid original cooldown");r.skillCount++;}
 }
 TeamManager CreateTeamContext(out GameObject owned){
  Check(!TeamManager.instance,"Existing team manager");owned=new GameObject("Inactive team context");owned.SetActive(false);owned.AddComponent<NetworkIdentity>();var manager=owned.AddComponent<TeamManager>();Call(manager,"OnEnable");Check(TeamManager.instance==manager,"Original team singleton assignment");Call(manager,"Start");
  for(TeamIndex index=TeamIndex.Neutral;index<TeamIndex.Count;index++)Check(manager.GetTeamExperience(index)==0&&manager.GetTeamLevel(index)==1&&manager.GetTeamNextLevelExperience(index)==20,"Original initial team level/experience");return manager;
 }
 void TeamContextProbe(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Existing network session");Check(NetworkServer.Listen("127.0.0.1",0),"Team server listen");ownsServer=true;GameObject owned=null;TeamManager manager=null;
  try{manager=CreateTeamContext(out owned);manager.GiveTeamExperience(TeamIndex.Player,19);Check(manager.GetTeamLevel(TeamIndex.Player)==1,"Premature team level");manager.GiveTeamExperience(TeamIndex.Player,1);Check(manager.GetTeamExperience(TeamIndex.Player)==20&&manager.GetTeamLevel(TeamIndex.Player)==2,"Original level threshold");manager.SetTeamLevel(TeamIndex.Player,1);Check(manager.GetTeamLevel(TeamIndex.Player)==1&&manager.GetTeamExperience(TeamIndex.Player)==0,"Original level reset");}
  finally{if(manager)Call(manager,"OnDisable");if(owned)Destroy(owned);}Check(!TeamManager.instance,"Team singleton cleanup");
 }
 void RunContextProbe(){
  Check(!Run.instance,"Existing Run");var owned=new GameObject("Inactive Run singleton probe");owned.SetActive(false);var run=owned.AddComponent<Run>();
  try{Call(run,"OnEnable");Check(Run.instance==run&&!owned.activeInHierarchy,"Original Run singleton assignment");}finally{Call(run,"OnDisable");Destroy(owned);}Check(!Run.instance,"Original Run singleton cleanup");
 }
 bool IsStatsProbe(){return r.id=="body-original-stats"||r.id=="body-level-stats"||r.id=="body-computed-motor"||r.id.StartsWith("body-state-");}
 IEnumerator OriginalStats(CharacterBody body,Result cfg){
  Check(!Run.instance&&!RunArtifactManager.instance&&!TeamManager.instance,"Existing stats context");GameObject teamHost=null,runHost=null;TeamManager manager=null;Run run=null;RunArtifactManager artifacts=null;var team=body.teamComponent;bool healthAwake=false;
  var priorDefs=(ArtifactDef[])typeof(ArtifactCatalog).GetField("artifactDefs",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);var priorGlass=RoR2Content.Artifacts.glassArtifactDef;var oldVoid=DLC1Content.Equipment.EliteVoidEquipment;var oldPotion=RoR2Content.Equipment.LunarPotion;var oldFall=RoR2Content.Artifacts.weakAssKneesArtifactDef;
  Check(priorDefs.Length==0&&!priorGlass&&!oldVoid&&!oldPotion,"Existing stats content bindings");
  Action<CharacterBody> observed=b=>{if(b==body)r.statsEvents++;};
  try{
   var glass=artifactBundle.LoadAsset<ArtifactDef>(cfg.glassAsset);var elite=artifactBundle.LoadAsset<EquipmentDef>(cfg.voidEquipmentAsset);var potion=artifactBundle.LoadAsset<EquipmentDef>(cfg.potionAsset);Check(glass&&elite&&potion,"Missing recovered stats definitions");
   StaticCall(typeof(EquipmentCatalog),"SetEquipmentDefs",new object[]{new[]{RoR2Content.Equipment.QuestVolatileBattery,elite,potion}.Concat(EnemyDeathEquipment(cfg)).Concat(InteractionSelectionEquipment(cfg)).Concat(MoonEquipment(cfg)).ToArray()});DLC1Content.Equipment.EliteVoidEquipment=elite;RoR2Content.Equipment.LunarPotion=potion;StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{new[]{glass}});RoR2Content.Artifacts.Glass=glass;StaticCall(typeof(RunArtifactManager),"Init");
   if(IsRecoveredLanding()){
    Check(!GlobalEventManager.instance&&!oldFall,"Existing landing context");var fall=artifactBundle.LoadAsset<ArtifactDef>(cfg.artifactAsset);Check(fall&&fall.cachedName=="WeakAssKnees","Recovered fall definition");StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{new[]{glass}.Concat(EnemyArtifacts(cfg,fall)).Concat(ChestPurchaseArtifacts(cfg)).Concat(DropletFlightArtifacts(cfg)).Concat(ObjectiveArtifacts(cfg)).Distinct().ToArray()});RoR2Content.Artifacts.WeakAssKnees=fall;StaticCall(typeof(RunArtifactManager),"Init");eventHost=new GameObject("Recovered landing event context");eventHost.SetActive(false);Call(eventHost.AddComponent<GlobalEventManager>(),"OnEnable");Check(GlobalEventManager.instance==eventHost.GetComponent<GlobalEventManager>(),"Original landing event singleton");
   }
   manager=CreateTeamContext(out teamHost);Call(team,"Awake");team.teamIndex=TeamIndex.None;team.teamIndex=TeamIndex.Player;Check(team.body==body&&TeamComponent.GetTeamMembers(TeamIndex.Player).Contains(team),"Recovered player team context");
   runHost=new GameObject("Inactive stat Run context");runHost.SetActive(false);artifacts=runHost.AddComponent<RunArtifactManager>();run=runHost.GetComponent<Run>();Call(run,"OnEnable");Call(artifacts,"Awake");Call(artifacts,"OnEnable");Check(Run.instance==run&&!artifacts.IsArtifactEnabled(glass),"Original disabled Glass context");
   Call(body.healthComponent,"Awake");healthAwake=true;Check(body.healthComponent.body==body,"Original health body cache");body.onRecalculateStats+=observed;r.phase="original-recalculate-stats";Save();body.RecalculateStats();
   r.maxHealth=body.maxHealth;r.moveSpeed=body.moveSpeed;r.damage=body.damage;r.jumpPower=body.jumpPower;r.level=body.level;
   Check(r.statsEvents==1&&r.level==1,"Original stat completion/level");Check(Mathf.Abs(r.maxHealth-110)<.001f&&Mathf.Abs(r.moveSpeed-7)<.001f&&Mathf.Abs(r.damage-12)<.001f&&Mathf.Abs(r.jumpPower-15)<.001f,"Recovered Commando base stats");Check(!host.activeInHierarchy&&!runHost.activeInHierarchy,"Broad gameplay activation");
   if(r.id=="body-level-stats"){
    Action<CharacterBody> levelObserved=b=>{if(b==body)r.levelEvents++;};GlobalEventManager.onCharacterLevelUp+=levelObserved;
    try{
     var dirty=typeof(CharacterBody).GetField("statsDirty",BindingFlags.NonPublic|BindingFlags.Instance);Check(!(bool)dirty.GetValue(body),"Base stats remain dirty");
     manager.SetTeamLevel(TeamIndex.Player,2);Check((bool)dirty.GetValue(body)&&manager.GetTeamLevel(TeamIndex.Player)==2,"Original team change did not dirty body");body.RecalculateStats();r.raisedHealth=body.maxHealth;r.raisedDamage=body.damage;
     Check(body.level==2&&r.statsEvents==2&&r.levelEvents==1,"Original level-up events");Check(Mathf.Abs(r.raisedHealth-143)<.001f&&Mathf.Abs(r.raisedDamage-14.4f)<.001f&&body.moveSpeed==7&&body.jumpPower==15,"Original level-two stats");
     manager.SetTeamLevel(TeamIndex.Player,1);Check((bool)dirty.GetValue(body),"Reset did not dirty body");body.RecalculateStats();Check(body.level==1&&Mathf.Abs(body.maxHealth-110)<.001f&&Mathf.Abs(body.damage-12)<.001f&&r.statsEvents==3&&r.levelEvents==1&&!(bool)dirty.GetValue(body),"Original level reset");
    }finally{GlobalEventManager.onCharacterLevelUp-=levelObserved;}
   }
   if(r.id.StartsWith("body-state-spawn-")){var spawnRoutine=SpawnBoundary(body,cfg);while(spawnRoutine.MoveNext())yield return spawnRoutine.Current;}else if(r.id.StartsWith("body-state-"))RecoveredState(body);
   if(r.id=="body-computed-motor"){
    var motor=body.characterMotor;var solver=host.GetComponent<KinematicCharacterMotor>();Check(solver,"Recovered solver absent");Call(solver,"Awake");motor.SetupCharacterMotor(solver);Call(motor,"UpdateAuthority");Check(motor.Motor==solver&&motor.hasEffectiveAuthority,"Recovered solver/authority binding");
    r.computedAcceleration=body.acceleration;Check(r.computedAcceleration>0&&body.moveSpeed==7,"Original computed movement stats");var origin=host.transform.position;motor.moveDirection=Vector3.right;motor.velocity=Vector3.zero;float expected=Mathf.Min(body.moveSpeed,body.acceleration*motor.airControl*.1f);Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-expected)<.001f,"Computed-stat first acceleration");
    for(int i=0;i<99;i++)Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-body.moveSpeed)<.001f,"Computed-stat speed cap");motor.moveDirection=Vector3.zero;for(int i=0;i<100;i++)Call(motor,"PreMove",.1f);Check(motor.velocity.sqrMagnitude<.000001f,"Computed-stat braking");Check(host.transform.position==origin&&!host.activeInHierarchy,"Unexpected solver translation or activation");
   }

  }finally{
   body.onRecalculateStats-=observed;if(healthAwake)Call(body.healthComponent,"OnDestroy");if(team)Call(team,"OnDestroy");if(artifacts){Call(artifacts,"OnDisable");Call(artifacts,"OnDestroy");}if(run)Call(run,"OnDisable");if(runHost)Destroy(runHost);if(manager)Call(manager,"OnDisable");if(teamHost)Destroy(teamHost);
   RoR2Content.Artifacts.WeakAssKnees=oldFall;RoR2Content.Artifacts.Glass=priorGlass;StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{priorDefs});StaticCall(typeof(RunArtifactManager),"Init");DLC1Content.Equipment.EliteVoidEquipment=oldVoid;RoR2Content.Equipment.LunarPotion=oldPotion;
  }
 }
 IEnumerator SpawnBoundary(CharacterBody body,Result cfg){
  var master=body.master;Check(master&&!master.hasBody&&master.GetBody()==null&&body.master==master,"Expected one-way diagnostic link");Check(master.loadout!=null,"Original master loadout missing");var writer=new NetworkWriter();master.loadout.Serialize(writer);var bytes=writer.ToArray();var decoded=new Loadout();var reader=new NetworkReader(bytes);decoded.Deserialize(reader);Check(reader.Position==bytes.Length&&decoded.ValueEquals(master.loadout),"Original master loadout round trip");Check(bytes.Length==1&&bytes[0]==0,"Expected untouched default loadout");
  if(r.id=="body-state-spawn-state-catalog"||r.id=="body-state-spawn-state-material"){PrepareSpawnStateCatalog(cfg);yield break;}
  if(r.id=="body-state-spawn-loadout-catalog"){
   Check(ownsBodyCatalog&&BodyCatalog.GetBodyPrefab(body.bodyIndex)==artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset),"Catalog/body prefab identity");
   Check(master.loadout.bodyLoadoutManager.GetSkinIndex(body.bodyIndex)==0&&decoded.bodyLoadoutManager.GetSkinIndex(body.bodyIndex)==0,"Original catalog-aware default skin selection");yield break;
  }
  if(r.id=="body-state-spawn-loadout")yield break;
  bool automaticSpawn=r.id.StartsWith("body-state-spawn-state-")||r.id=="body-state-spawn-body-start-catalog"||r.id=="body-state-spawn-automatic"||r.id=="body-state-spawn-master-start"||r.id=="body-state-spawn-body-start";
  if(r.id=="body-state-spawn-awake"){
   var root=Instantiate(artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset));var fresh=root.GetComponent<CharacterBody>();int observed=0;Action<CharacterBody> awake=b=>{if(b==fresh)observed++;};CharacterBody.onBodyAwakeGlobal+=awake;
   try{Check(!root.activeInHierarchy&&!fresh.teamComponent&&!fresh.skillLocator,"Fresh inactive body context");foreach(Transform child in root.transform)child.gameObject.SetActive(false);r.phase="automatic-root-awake";Save();root.SetActive(true);r.awakeEvents=observed;Check(observed==1&&fresh.teamComponent==root.GetComponent<TeamComponent>()&&fresh.skillLocator==root.GetComponent<SkillLocator>()&&fresh.networkIdentity==root.GetComponent<NetworkIdentity>(),"Automatic original body caches");Check(CharacterBody.readOnlyInstancesList.Contains(fresh),"Automatic original body registration");r.phase="automatic-root-disable";Save();root.SetActive(false);Check(!CharacterBody.readOnlyInstancesList.Contains(fresh),"Automatic original body deregistration");}
   finally{CharacterBody.onBodyAwakeGlobal-=awake;if(root){root.SetActive(false);r.phase="automatic-root-destroy";Save();Destroy(root);}}yield break;
  }
  var prefab=artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);Check(prefab&&!prefab.activeSelf&&prefab.GetComponent<CharacterBody>()&&prefab.GetComponent<TeamComponent>()&&prefab.GetComponent<SkillLocator>(),"Recovered spawn prefab contract");var previous=master.bodyPrefab;var before=new System.Collections.Generic.HashSet<int>();foreach(var candidate in Resources.FindObjectsOfTypeAll<CharacterBody>())before.Add(candidate.GetInstanceID());master.bodyPrefab=prefab;var childStates=new System.Collections.Generic.Dictionary<GameObject,bool>();
  try{if(automaticSpawn){foreach(Transform child in prefab.transform){childStates.Add(child.gameObject,child.gameObject.activeSelf);child.gameObject.SetActive(false);}prefab.SetActive(true);}
  if(cfg.stageGeometry){var geometry=PrepareStageGeometry(cfg.stageMapZoneCount,cfg.stageMapZoneActiveNames);while(geometry.MoveNext())yield return geometry.Current;}
  r.phase="original-master-spawn";Save();var spawned=master.SpawnBody(cfg.stageGeometry?r.stage.spawnPosition:new Vector3(0,12,0),Quaternion.identity);if(spawned)spawned.gameObject.SetActive(false);Check(spawned&&spawned!=body,"Original body creation");Check(master.hasBody&&master.GetBody()==spawned&&spawned.master==master,"Original reciprocal linkage");Check(NetworkServer.FindLocalObject(spawned.netId)==spawned.gameObject,"Original spawned body server mapping");
   if(r.id=="body-state-spawn-body-start-catalog"||r.id.StartsWith("body-state-spawn-state-")){r.spawnedBodyIndex=(int)spawned.bodyIndex;Check(ownsBodyCatalog&&spawned.bodyIndex==prefab.GetComponent<CharacterBody>().bodyIndex&&BodyCatalog.GetBodyPrefab(spawned.bodyIndex)==prefab,"Spawn retained original catalog-assigned identity");}
   if(!IsAutomaticBody()&&(r.id=="body-state-spawn-master-start"||r.id=="body-state-spawn-body-start"||r.id=="body-state-spawn-body-start-catalog"||r.id.StartsWith("body-state-spawn-state-"))){
    Check(DLC1Content.Items.GummyCloneIdentifier&&DLC1Content.Items.GummyCloneIdentifier.itemIndex!=ItemIndex.None&&master.inventory.GetItemCountEffective(DLC1Content.Items.GummyCloneIdentifier)==0,"Original empty gummy item context");Action<CharacterBody> started=b=>{if(b==spawned)r.masterStartEvents++;};Action<CharacterBody> bodyStarted=b=>{if(b==spawned)r.bodyStartEvents++;};master.onBodyStart+=started;CharacterBody.onBodyStartGlobal+=bodyStarted;
    try{r.phase=r.id=="body-state-spawn-master-start"?"original-master-body-start":"original-body-start";Save();if(r.id=="body-state-spawn-master-start")master.OnBodyStart(spawned);else Call(spawned,"Start");r.spawnedHealth=spawned.healthComponent.health;r.spawnedSkinIndex=spawned.skinIndex;Check(r.masterStartEvents==1&&r.spawnedHealth==spawned.healthComponent.fullHealth&&r.spawnedHealth>0,"Original master body-start health/event");if(r.id=="body-state-spawn-body-start"||r.id=="body-state-spawn-body-start-catalog"||r.id.StartsWith("body-state-spawn-state-"))Check(r.bodyStartEvents==1,"Original body Start completion");if(r.id=="body-state-spawn-body-start-catalog")Check(r.spawnedSkinIndex==master.loadout.bodyLoadoutManager.GetSkinIndex(spawned.bodyIndex),"Original UpdateMasterLink skin selection");}finally{master.onBodyStart-=started;CharacterBody.onBodyStartGlobal-=bodyStarted;}
   }
   if(r.id.StartsWith("body-state-spawn-state-auto-")){var autoRoutine=AutomaticSpawnBoundary(spawned,cfg);while(autoRoutine.MoveNext())yield return autoRoutine.Current;}else if(r.id=="body-state-spawn-state-barrier-effect"){var effectRoutine=ProbeBarrierEffectLifecycle(spawned);while(effectRoutine.MoveNext())yield return effectRoutine.Current;}else if(IsPrimaryFire())PrimaryFireBoundary(spawned,cfg);else if(r.id.StartsWith("body-state-spawn-state-"))ProbeSpawnStates(spawned,cfg);
}
  finally{foreach(var candidate in Resources.FindObjectsOfTypeAll<CharacterBody>()){if(!candidate||before.Contains(candidate.GetInstanceID())||!candidate.gameObject.scene.IsValid())continue;r.spawnCloneCount++;r.spawnedTeamCached=candidate.teamComponent;r.spawnedSkillCached=candidate.skillLocator;r.spawnedMasterMatches=candidate.GetMasterObjectId()==master.netId;var identity=candidate.GetComponent<NetworkIdentity>();r.spawnedNetworked=identity&&NetworkServer.FindLocalObject(identity.netId)==candidate.gameObject;Save();if(r.spawnedNetworked)NetworkServer.UnSpawn(candidate.gameObject);Destroy(candidate.gameObject);}master.bodyPrefab=previous;if(automaticSpawn){prefab.SetActive(false);foreach(var pair in childStates)pair.Key.SetActive(pair.Value);}}
 }
 bool IsAutomaticHealth(){return IsAutomaticDirection()||r.id=="body-state-spawn-state-auto-health"||r.id=="body-state-spawn-state-auto-barrier";}
 bool IsAutomaticBody(){return IsAutomaticHealth()|| r.id=="body-state-spawn-state-auto-body"||r.id=="body-state-spawn-state-auto-body-ground";}
 bool IsRecoveredLanding(){return IsNovaInput()||r.id=="body-state-spawn-state-auto-body-ground"|| r.id=="body-state-spawn-state-auto-land"||r.id=="body-state-spawn-state-auto-ground-stop"||r.id=="body-state-spawn-state-auto-ground-wall"||r.id=="body-state-land"||r.id.StartsWith("body-state-ground-")||r.id.StartsWith("body-state-jump-");}
 void RecoveredState(CharacterBody body){
  var motor=body.characterMotor;var solver=host.GetComponent<KinematicCharacterMotor>();Check(solver,"Recovered solver absent");Call(solver,"Awake");motor.SetupCharacterMotor(solver);Call(motor,"UpdateAuthority");Check(motor.Motor==solver&&motor.hasEffectiveAuthority,"Recovered solver authority");
  var input=host.GetComponent<InputBankTest>();var machine=EntityStateMachine.FindByCustomName(host,"Body");Check(input&&machine&&machine.mainStateType.stateType==typeof(EntityStates.GenericCharacterMain),"Recovered main-state/input identity");Call(input,"Awake");Call(machine,"Awake");var savedGravity=Physics.gravity;
  try{
   r.phase="recovered-state-entry";Save();var state=new EntityStates.GenericCharacterMain();machine.SetState(state);Check(machine.state==state&&machine.commonComponents.inputBank==input&&(bool)typeof(EntityStates.EntityState).GetProperty("isAuthority",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(state),"Recovered original state entry/cache/authority");
   if(r.id=="body-state-input"){
    input.moveVector=Vector3.right;input.aimDirection=Vector3.forward;input.jump.PushState(true);Call(state,"GatherInputs");var flags=BindingFlags.NonPublic|BindingFlags.Instance;Check((Vector3)typeof(EntityStates.GenericCharacterMain).GetField("moveVector",flags).GetValue(state)==Vector3.right,"Recovered state movement input");Check((bool)typeof(EntityStates.GenericCharacterMain).GetField("jumpInputReceived",flags).GetValue(state),"Recovered state jump edge");input.jump.hasPressBeenClaimed=true;Call(state,"GatherInputs");Check(!(bool)typeof(EntityStates.GenericCharacterMain).GetField("jumpInputReceived",flags).GetValue(state),"Recovered state claimed jump");
   }
   if(r.id=="body-state-start"||r.id=="body-state-gravity"||IsRecoveredLanding()){
    var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);Check(cfg.sourceGravity<0,"Missing source gravity");Physics.gravity=new Vector3(0,cfg.sourceGravity,0);r.gravity=Physics.gravity.y;Action<CharacterBody> started=b=>{if(b==body)r.motorStartEvents++;};motor.onMotorStart+=started;try{Call(motor,"Start");}finally{motor.onMotorStart-=started;}Check(r.motorStartEvents==1&&motor.useGravity&&motor.hasEffectiveAuthority&&motor.Motor==solver,"Original motor Start contract");
    if(r.id!="body-state-start"){
     solver.SetGroundSolvingActivation(IsRecoveredLanding());solver.CollidableLayers=IsRecoveredLanding()?1<<30:0;solver.StableGroundLayers=1<<30;solver.SetPosition(new Vector3(0,IsRecoveredLanding()?12:10,0));motor.velocity=Vector3.zero;input.moveVector=Vector3.zero;
     if(r.id=="body-state-gravity"){
      for(int i=0;i<25;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);}r.y=solver.TransientPosition.y;Check(Mathf.Abs(motor.velocity.y-r.gravity*.5f)<.001f&&Mathf.Abs(r.y-(10+r.gravity*.0004f*325))<.002f,"Recovered gravity velocity/displacement");
     }else{
      obstacle=new GameObject("Owned recovered landing floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(20,1,20);Physics.SyncTransforms();
      CharacterMotor.HitGroundDelegate landed=(ref CharacterMotor.HitGroundInfo hit)=>{r.landingEvents++;};motor.onHitGroundAuthority+=landed;try{for(int i=0;i<60;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);}}finally{motor.onHitGroundAuthority-=landed;}
      r.y=solver.TransientPosition.y;Check(r.landingEvents==1&&solver.GroundingStatus.IsStableOnGround&&Mathf.Abs(motor.velocity.y)<.001f,"Recovered original landing callback/grounding");Check(r.y>9&&r.y<10.5f&&motor.jumpCount==0,"Recovered landing position/jump reset");
      if(r.id.StartsWith("body-state-jump-")){
       var sfx=host.GetComponent<SfxLocator>();Check(sfx&&string.IsNullOrEmpty(sfx.jumpSound)&&!string.IsNullOrEmpty(sfx.landingSound),"Recovered sound contract changed; no suppression allowed");Check(RoR2Content.Items.JumpBoost&&DLC3Content.Items.JumpDamageStrike&&body.inventory.GetItemCountEffective(RoR2Content.Items.JumpBoost)==0&&body.inventory.GetItemCountEffective(DLC3Content.Items.JumpDamageStrike)==0,"Recovered empty jump inventory");Check(body.maxJumpCount==1&&body.baseJumpCount==1&&Mathf.Abs(body.jumpPower-15)<.001f,"Original computed normal jump contract");
       if(r.id=="body-state-jump-authority"){
        r.rawAuthority=body.hasAuthority;r.effectiveAuthority=Util.HasEffectiveAuthority(body.networkIdentity);r.playerAuthority=body.networkIdentity.localPlayerAuthority;r.hasClientOwner=body.networkIdentity.clientAuthorityOwner!=null;r.clientActive=NetworkClient.active;Check(r.playerAuthority&&!r.rawAuthority&&r.effectiveAuthority&&!r.hasClientOwner&&!r.clientActive,"Recovered server-only ownership distinction");
       }
       if(r.id=="body-state-jump-catalog")PrepareStateCatalog(body);
       if(r.id=="body-state-jump-serialize-body"||r.id=="body-state-jump-serialize-master"){
        PrepareStateCatalog(body);if(r.id.EndsWith("-master"))PrepareMasterTracker(body);Call(body.skillLocator,"Awake");Check(body.skillLocator.AllSkills.Length>=4,"Original skill locator serialization cache");var identity=r.id.EndsWith("-body")?body.networkIdentity:body.master.GetComponent<NetworkIdentity>();var behaviours=(NetworkBehaviour[])typeof(NetworkIdentity).GetField("m_NetworkBehaviours",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(identity);Check(behaviours!=null&&behaviours.Length>0,"Original serializer list");var writer=new NetworkWriter();foreach(var behaviour in behaviours){r.phase="serialize:"+behaviour.GetType().FullName;Save();try{behaviour.OnSerialize(writer,true);}catch(Exception e){throw new Exception("Original serializer "+behaviour.GetType().FullName,e);}}Check(writer.Position>0,"Original identity payload empty");
       }
       if(r.id=="body-state-jump-client"||r.id=="body-state-jump-owner"||r.id=="body-state-jump-client-event"||r.id=="body-state-jump-client-input")ConnectRecoveredClient(body,r.id!="body-state-jump-client");
       body.onJump+=CountJump;try{
        if(r.id=="body-state-jump-event"||r.id=="body-state-jump-client-event"){body.TriggerJumpEventGlobally();Check(r.jumpEvents==1&&motor.jumpCount==0,"Recovered server jump event");}
        if(r.id=="body-state-jump-input"||r.id=="body-state-jump-client-input"){
         r.phase="recovered-jump-input";Save();input.jump.PushState(true);machine.ManagedFixedUpdate(.02f);Check(motor.jumpCount==1&&Mathf.Abs(motor.velocity.y-body.jumpPower)<.001f&&r.jumpEvents==1,"Recovered original input jump/event");input.jump.PushState(false);r.peak=solver.TransientPosition.y;
         motor.onHitGroundAuthority+=landed;try{for(int i=0;i<100;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);r.peak=Mathf.Max(r.peak,solver.TransientPosition.y);}}finally{motor.onHitGroundAuthority-=landed;}
         Check(r.peak>r.y+3&&r.peak<r.y+4,"Recovered computed jump height");Check(solver.GroundingStatus.IsStableOnGround&&Mathf.Abs(solver.TransientPosition.y-r.y)<.02f&&motor.jumpCount==0&&r.jumpEvents==1&&r.landingEvents==2,"Recovered jump landing/reset/events");
        }
       }finally{body.onJump-=CountJump;}
      }
      if(r.id.StartsWith("body-state-ground-")){
       if(r.id=="body-state-ground-wall"){var wall=new GameObject("Owned recovered state wall");wall.transform.SetParent(obstacle.transform);wall.layer=30;wall.transform.position=new Vector3(2,11,0);wall.AddComponent<BoxCollider>().size=new Vector3(1,10,20);Physics.SyncTransforms();}
       if(r.id=="body-state-ground-visual")CommandoMaterialPreview.CaptureMotion(host,artifactBundle,cfg.displayAssets,"recovered-motion-before.png");
       r.phase="recovered-grounded-motion";Save();input.moveVector=Vector3.right;input.aimDirection=Vector3.right;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);}r.x=solver.TransientPosition.x;Check(solver.GroundingStatus.IsStableOnGround&&Mathf.Abs(solver.TransientPosition.y-r.y)<.02f,"Recovered motion lost grounding");
       if(r.id=="body-state-ground-wall")Check(r.x>.9f&&r.x<1.01f,"Recovered movement crossed wall");else Check(Mathf.Abs(r.x-6.76f)<.02f&&Mathf.Abs(motor.velocity.x-7)<.001f,"Recovered grounded acceleration/displacement");
       if(r.id=="body-state-ground-reverse"){input.moveVector=Vector3.left;for(int i=0;i<100;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);}r.z=solver.TransientPosition.x;Check(r.z<r.x-10&&Mathf.Abs(motor.velocity.x+7)<.001f&&solver.GroundingStatus.IsStableOnGround,"Recovered grounded reversal");}
       input.moveVector=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);}Check(motor.moveDirection==Vector3.zero&&motor.velocity.sqrMagnitude<.000001f&&solver.GroundingStatus.IsStableOnGround,"Recovered grounded stop");
       if(r.id=="body-state-ground-visual"){r.z=solver.TransientPosition.x;CommandoMaterialPreview.CaptureMotion(host,artifactBundle,cfg.displayAssets,"recovered-motion-after.png");Check(Mathf.Abs(r.z-7)<.02f,"Visual snapshot measured stop position");}
      }

     }
    }
   }
   if(r.id=="body-state-motion"){
    r.phase="recovered-state-motion";Save();solver.SetGroundSolvingActivation(false);solver.CollidableLayers=0;solver.SetPosition(new Vector3(0,10,0));motor.moveDirection=Vector3.zero;motor.velocity=Vector3.zero;Check(!motor.useGravity,"Unexpected gravity before motor Start");input.moveVector=Vector3.right;input.aimDirection=Vector3.right;
    for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);}r.x=solver.TransientPosition.x;r.y=solver.TransientPosition.y;Check(r.x>5&&r.x<7&&Mathf.Abs(r.y-10)<.001f&&Mathf.Abs(motor.velocity.x-7)<.001f,"Recovered original state/solver displacement");
    input.moveVector=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(solver,1);}r.z=solver.TransientPosition.x;Check(r.z>=r.x&&r.z<r.x+2&&motor.velocity.sqrMagnitude<.000001f&&motor.moveDirection==Vector3.zero,"Recovered original state braking");
   }
  }finally{if(recoveredOwnedIdentity){Check(recoveredOwnedIdentity.RemoveClientAuthority(recoveredOwner),"Recovered authority removal");Call(recoveredClient,"Update");Check(recoveredOwnedIdentity.clientAuthorityOwner==null,"Recovered owner release");recoveredOwnedIdentity=null;}Physics.gravity=savedGravity;Call(machine,"OnDestroy");}Check(Physics.gravity==savedGravity,"Recovered gravity restoration");Check(machine.state==null&&motor.moveDirection==Vector3.zero&&!host.activeInHierarchy,"Recovered state exit/cleanup");
 }

 static void BuildStateCatalog(Type[] types,EntityStateConfiguration[] configs=null){
  var routine=(IEnumerator)typeof(EntityStateCatalog).GetMethod("SetElements",BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,new object[]{types,configs??Array.Empty<EntityStateConfiguration>()});while(routine.MoveNext()){};
 }
 void PrepareStateCatalog(CharacterBody body){
  r.phase="recovered-state-catalog";Save();var flags=BindingFlags.Static|BindingFlags.NonPublic;
  Check(((Type[])typeof(EntityStateCatalog).GetField("stateIndexToType",flags).GetValue(null)).Length==0&&((IDictionary)typeof(EntityStateCatalog).GetField("stateTypeToIndex",flags).GetValue(null)).Count==0&&((IDictionary)typeof(EntityStateCatalog).GetField("instanceFieldInitializers",flags).GetValue(null)).Count==0,"Existing state catalog; refusing replacement");
  var network=body.GetComponent<NetworkStateMachine>();var machines=(EntityStateMachine[])typeof(NetworkStateMachine).GetField("stateMachines",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(network);var types=new System.Collections.Generic.List<Type>();foreach(var machine in machines)if(machine.state!=null&&!types.Contains(machine.state.GetType()))types.Add(machine.state.GetType());Check(types.Count==1&&types[0]==typeof(EntityStates.GenericCharacterMain),"Unexpected active diagnostic states");
  ownsStateCatalog=true;BuildStateCatalog(types.ToArray());foreach(var type in types){var index=EntityStateCatalog.GetStateIndex(type);Check(index!=EntityStateIndex.Invalid&&EntityStateCatalog.GetStateType(index)==type&&EntityStateCatalog.InstantiateState(index).GetType()==type,"Original state catalog identity round trip");}
  var writer=new NetworkWriter();Check(network.OnSerialize(writer,true),"Original state serialization");var bytes=writer.ToArray();var reader=new NetworkReader(bytes);foreach(var machine in machines){var index=reader.ReadEntityStateIndex();if(machine.state==null){Check(index==EntityStateIndex.Invalid,"Null state serialization");continue;}Check(EntityStateCatalog.GetStateType(index)==machine.state.GetType(),"Serialized state identity");var decoded=EntityStateCatalog.InstantiateState(index);decoded.OnDeserialize(reader);}Check(reader.Position==bytes.Length,"State serialization byte consumption");
 }

 void PrepareMasterTracker(CharacterBody body){
  r.phase="master-tracker-awake";Save();var master=body.master;var tracker=master.GetComponent<PlayerCharacterMasterControllerEntitlementTracker>();var controller=master.GetComponent<PlayerCharacterMasterController>();Check(tracker&&controller&&!controller.networkUser,"Original master tracker without user");var field=typeof(PlayerCharacterMasterControllerEntitlementTracker).GetField("entitlementsSet",BindingFlags.Instance|BindingFlags.NonPublic);Check(field.GetValue(tracker)==null,"Tracker already initialized");var defs=RoR2.EntitlementManagement.EntitlementCatalog.entitlementDefs;Check(defs.Length==0,"Diagnostic entitlement catalog changed; review required");Call(tracker,"Awake");var values=(bool[])field.GetValue(tracker);Check(values!=null&&values.Length==defs.Length,"Original tracker storage allocation");Call(tracker,"UpdateEntitlementsServer");Check(ReferenceEquals(values,field.GetValue(tracker))&&!controller.networkUser,"Absent-user tracker path changed context");foreach(var value in values)Check(!value,"Unexpected entitlement grant");Check(RoR2.EntitlementManagement.EntitlementCatalog.entitlementDefs.Length==defs.Length,"Entitlement catalog mutation");
 }

 void ConnectRecoveredClient(CharacterBody body,bool assign){
  PrepareStateCatalog(body);PrepareMasterTracker(body);
  Check(!NetworkClient.active&&NetworkClient.allClients.Count==0&&recoveredClient==null,"Existing recovered client");Call(body.skillLocator,"Awake");Check(body.skillLocator.AllSkills.Length>=4,"Original skill locator cache");NetworkServer.RegisterHandler(MsgType.Connect,msg=>{});NetworkServer.RegisterHandler(MsgType.Disconnect,msg=>{});
  r.phase="recovered-local-client";Save();recoveredClient=ClientScene.ConnectLocalServer();recoveredClient.RegisterHandler(MsgType.Connect,msg=>r.connectEvents++);recoveredClient.RegisterHandler(MsgType.Disconnect,msg=>{});Call(recoveredClient,"Update");Check(recoveredClient.isConnected&&r.connectEvents==1&&NetworkServer.localConnections.Count==1,"Recovered local connection");Check(ClientScene.Ready(recoveredClient.connection),"Recovered local readiness");Call(recoveredClient,"Update");recoveredOwner=NetworkServer.localConnections[0];r.clientActive=NetworkClient.active;Check(recoveredOwner.isReady&&body.isClient&&body.master.isClient&&ClientScene.FindLocalObject(body.netId)==host&&ClientScene.FindLocalObject(body.master.netId)==body.master.gameObject,"Recovered client object mapping");
  r.rawAuthority=body.hasAuthority;r.effectiveAuthority=body.hasEffectiveAuthority;r.playerAuthority=body.networkIdentity.localPlayerAuthority;r.hasClientOwner=body.networkIdentity.clientAuthorityOwner!=null;Check(r.playerAuthority&&!r.rawAuthority&&!r.hasClientOwner,"Unexpected pre-assignment recovered owner");
  if(assign){r.phase="recovered-local-owner";Save();Check(body.networkIdentity.AssignClientAuthority(recoveredOwner),"Recovered authority assignment");recoveredOwnedIdentity=body.networkIdentity;Call(recoveredClient,"Update");r.ownedAuthority=body.hasAuthority;r.ownerMatched=body.networkIdentity.clientAuthorityOwner==recoveredOwner;Check(r.ownedAuthority&&r.ownerMatched&&body.hasEffectiveAuthority&&body.characterMotor.hasEffectiveAuthority&&(bool)typeof(SkillLocator).GetField("hasEffectiveAuthority",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(body.skillLocator),"Recovered original authority callbacks");}
 }

 void LocalOwnership(){
  Check(!NetworkServer.active&&!NetworkClient.active&&NetworkClient.allClients.Count==0,"Existing network context");NetworkClient client=null;NetworkIdentity identity=null;NetworkConnection owner=null;bool assigned=false;
  try{
   Check(NetworkServer.Listen("127.0.0.1",0),"Owned local server listen");ownsServer=true;NetworkServer.RegisterHandler(MsgType.Connect,msg=>{});NetworkServer.RegisterHandler(MsgType.Disconnect,msg=>{});
   host=new GameObject("Owned diagnostic local identity");identity=host.AddComponent<NetworkIdentity>();identity.localPlayerAuthority=true;host.SetActive(false);NetworkServer.Spawn(host);r.rawAuthority=identity.hasAuthority;r.effectiveAuthority=Util.HasEffectiveAuthority(identity);r.playerAuthority=identity.localPlayerAuthority;Check(!r.rawAuthority&&r.effectiveAuthority&&r.playerAuthority,"Minimal server-only ownership baseline");
   r.phase="local-client-connect";Save();client=ClientScene.ConnectLocalServer();client.RegisterHandler(MsgType.Connect,msg=>r.connectEvents++);client.RegisterHandler(MsgType.Disconnect,msg=>{});Call(client,"Update");r.clientActive=NetworkClient.active;Check(client.isConnected&&r.clientActive&&r.connectEvents==1&&NetworkServer.localConnections.Count==1,"Original local connection");Check(ClientScene.Ready(client.connection),"Original local client ready");Call(client,"Update");owner=NetworkServer.localConnections[0];Check(owner.isReady&&client.connection.isReady&&ClientScene.FindLocalObject(identity.netId)==host,"Original ready/object mapping");
   if(r.id=="network-local-owner"){
    r.phase="local-client-ownership";Save();Check(identity.AssignClientAuthority(owner),"Original authority assignment rejected");assigned=true;Call(client,"Update");r.ownedAuthority=identity.hasAuthority;r.ownerMatched=identity.clientAuthorityOwner==owner;Check(r.ownedAuthority&&r.ownerMatched&&Util.HasEffectiveAuthority(identity),"Original local authority message delivery");Check(identity.RemoveClientAuthority(owner),"Original authority removal rejected");assigned=false;Call(client,"Update");Check(identity.clientAuthorityOwner==null,"Original authority owner release");
   }
  }finally{
   if(assigned&&identity&&owner!=null)identity.RemoveClientAuthority(owner);if(identity&&NetworkServer.active)NetworkServer.UnSpawn(host);if(client!=null){client.Disconnect();client.Shutdown();NetworkServer.Shutdown();ownsServer=false;StaticCall(typeof(ClientScene),"Shutdown");}Check(!NetworkClient.active&&NetworkClient.allClients.Count==0&&NetworkServer.localConnections.Count==0,"Owned local client cleanup");
  }
 }

 void MasterLifecycle(){
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);artifactBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Master bundle missing");var prefab=artifactBundle.LoadAsset<GameObject>(cfg.masterAsset);Check(prefab&&!prefab.activeSelf,"Recovered master root not isolated");host=Instantiate(prefab);var master=host.GetComponent<CharacterMaster>();var inventory=host.GetComponent<Inventory>();Check(master&&inventory&&!host.activeInHierarchy,"Original master components missing or active");foreach(var c in host.GetComponentsInChildren<Component>(true))Check(c,"Missing recovered master script");
  bool inventoryAwake=false,masterAwake=false,registered=false;
  try{
   Call(inventory,"Awake");inventoryAwake=true;Call(master,"Awake");masterAwake=true;
   Check(master.inventory==inventory&&master.networkIdentity==host.GetComponent<NetworkIdentity>(),"Original master component caches");Check(master.playerCharacterMasterController==host.GetComponent<PlayerCharacterMasterController>()&&master.playerCharacterMasterController,"Original player-master controller linkage");Check(!master.GetBody()&&!master.hasBody,"Unexpected spawned body");
   if(r.id=="master-network-spawn"){SpawnRecovered(host);Call(master,"UpdateAuthority");r.masterId=master.networkIdentity.netId.Value;Check(master.hasEffectiveAuthority&&Util.HasEffectiveAuthority(master.networkIdentity),"Recovered master effective authority");}
   var count=CharacterMaster.readOnlyInstancesList.Count;Call(master,"OnEnable");registered=true;Check(CharacterMaster.readOnlyInstancesList.Count==count+1&&CharacterMaster.readOnlyInstancesList.Contains(master),"Original master registration");Call(master,"OnDisable");registered=false;Check(CharacterMaster.readOnlyInstancesList.Count==count,"Original master unregistration");Check(!host.activeInHierarchy,"Master startup unexpectedly active");
  }finally{if(ownsServer){var id=host.GetComponent<NetworkIdentity>().netId;NetworkServer.UnSpawn(host);Check(!NetworkServer.FindLocalObject(id),"Master network object not removed");}if(registered)Call(master,"OnDisable");if(masterAwake)Call(master,"OnDestroy");if(inventoryAwake){Call(inventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");}}
 }

 void SpawnRecovered(GameObject target){
  if(!ownsServer){Check(!NetworkServer.active&&!NetworkClient.active,"Existing network session");Check(NetworkServer.Listen("127.0.0.1",0),"Owned server listen failed");ownsServer=true;}
  Check(!target.activeInHierarchy,"Recovered root unexpectedly active");var identity=target.GetComponent<NetworkIdentity>();Check(identity,"Recovered identity missing");NetworkServer.Spawn(target);Check(identity.isServer&&identity.netId.Value!=0&&NetworkServer.FindLocalObject(identity.netId)==target,"Original recovered object spawn/lookup failed");
 }

}
