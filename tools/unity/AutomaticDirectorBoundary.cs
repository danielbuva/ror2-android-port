using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Networking;
using RoR2.Navigation;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Supplies measured source contexts; original enabled callbacks select, fund and place the NPC.
public sealed partial class MovementBatchProbe {
 [Serializable] public class DirectorReport {
  public bool automatic,sourceSettings,playerRegistered,originalTarget,preloaded,creditConserved,placement,stopped,cleaned,navigationNext,navigationReachable;public int navigationTicks,navigationAgents,navigationAgentPeak;public float navigationTime,navigationPathUpdate;public string navigationError;
  public int participatingPlayers,livingPlayers,creditSteps,monsterLimit,masterIndex,selectedCardWeight;public float seconds,creditPeak,creditAfter,spent,spawnDistance,minDistance,maxDistance;public Vector3 position;
  public string scope;
  public int spawnLimit,livePeak;public float stoppedAt,totalSpent,totalCreditAfter;public bool batchCreditConserved;
  public List<DirectorActorReport> actors=new List<DirectorActorReport>();
 }
 GameObject automaticDirectorHost;DirectorCardCategorySelection automaticDeck;PlayerCharacterMasterController directorPlayer;
 bool directorPlayerRegistered;GameObject[] directorTeamEffects;object priorDirectorEliteTiers;
 readonly Dictionary<FieldInfo,object> directorMasterFields=new Dictionary<FieldInfo,object>();IDictionary directorMasterMap;
 float automaticDirectorBegan;
 Action ownedNavigationTick;BroadNavigationSystem navigationSystem;
 void StartOriginalNavigation(){
  Check(!RoR2Application.instance||!RoR2Application.instance.isActiveAndEnabled,"Original application already schedules navigation");navigationSystem=RoR2.CharacterAI.BaseAI.nodeGraphNavigationSystem;
  var systems=(IList)RewardField(typeof(BroadNavigationSystem),"instancesList").GetValue(null);Check(systems.Count==1&&ReferenceEquals(systems[0],navigationSystem)&&NavigationAgentCount()==0,"Unexpected pre-existing navigation agents/system");
  ownedNavigationTick=(Action)Delegate.CreateDelegate(typeof(Action),typeof(BroadNavigationSystem).GetMethod("StaticUpdate",BindingFlags.NonPublic|BindingFlags.Static));
 }
 int NavigationAgentCount(){return navigationSystem==null?0:(int)typeof(BroadNavigationSystem).GetProperty("agentCount",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(navigationSystem,null);}
 void FixedUpdate(){TickOriginalRunClock();if(ownedNavigationTick==null)return;try{ownedNavigationTick();r.director.navigationTicks++;}catch(Exception e){r.director.navigationError=e.ToString();ownedNavigationTick=null;Save();}}
 void ObserveOriginalNavigation(){
  if(r.director==null||navigationSystem==null)return;r.director.navigationAgents=NavigationAgentCount();r.director.navigationAgentPeak=Math.Max(r.director.navigationAgentPeak,r.director.navigationAgents);r.director.navigationTime=(float)typeof(BroadNavigationSystem).GetField("localTime",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(navigationSystem);Check(string.IsNullOrEmpty(r.director.navigationError),"Original navigation scheduler failed: "+r.director.navigationError);
  if(enemyAI){var output=enemyAI.broadNavigationAgent.output;r.director.navigationNext|=output.nextPosition.HasValue;r.director.navigationReachable|=output.targetReachable;r.director.navigationPathUpdate=output.lastPathUpdate;}
 }
 IEnumerator PrepareDirectorAssets(Result cfg,IResourceLocation bundle){
  Check(cfg.enemyDirectorTeamKeys.Length==2&&cfg.enemyDirectorTeamAssets.Length==2,"Measured director team asset count");
  var names=new[]{"Prefabs/Effects/LevelUpEffect","Prefabs/Effects/LevelUpEffectEnemy"};
  for(int i=0;i<2;i++){string key;Check(LegacyResourcesAPI.GetGuid(names[i],out key)&&key==cfg.enemyDirectorTeamKeys[i],"Original team effect legacy identity");rewardLocator.Add(key,new ResourceLocationBase(key,cfg.enemyDirectorTeamAssets[i],typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));}
  // Natural TeamCatalog constructor retains its real limit, effect and sound contracts.
  var player=TeamCatalog.GetTeamDef(TeamIndex.Player);var monster=TeamCatalog.GetTeamDef(TeamIndex.Monster);
  // The static constructor runs only once. Owned teardown releases and clears its four
  // original provider leases; a restarted session must acquire those exact assets again.
  if(r.session>1){
   var teams=new[]{TeamIndex.Player,TeamIndex.Monster,TeamIndex.Lunar,TeamIndex.Void};
   Check(teams.All(x=>!TeamCatalog.GetTeamDef(x).levelUpEffect),"Previous session retained team effect ownership");
   foreach(var team in teams)TeamCatalog.GetTeamDef(team).levelUpEffect=LegacyResourcesAPI.Load<GameObject>(names[team==TeamIndex.Player?0:1]);
  }
  directorTeamEffects=new[]{player.levelUpEffect,monster.levelUpEffect};
  Check(directorTeamEffects.All(x=>x)&&directorTeamEffects[0].name=="LevelUpEffect"&&directorTeamEffects[1].name=="LevelUpEffectEnemy"&&monster.softCharacterLimit==40,"Original team limit/effect contracts missing");
  yield return null;
 }
 IEnumerator SpawnAutomaticEnemy(GameObject template,CharacterBody player,Result cfg){
  int limit=cfg.integratedWorld?int.MaxValue:cfg.directorSpawnLimit==0?1:cfg.directorSpawnLimit;Check(cfg.integratedWorld||limit==1||limit==3,"Unmeasured director batch limit");r.director=new DirectorReport{automatic=true,spawnLimit=limit,monsterLimit=TeamCatalog.GetTeamDef(TeamIndex.Monster).softCharacterLimit,scope="Original enabled fast director; source timing/credits/target/team limit/approximate placement, one base Beetle card, bounded "+limit+" spawns; no connected user, full stage, elite or full wave acceptance"};if(cfg.integratedWorld)r.director.scope="Continuous original enabled fast director, one original base Beetle card and real team limit/credits/placement; no artificial spawn cutoff. Original Run clock with unavailable stock startup/user/profile/progression.";r.phase="automatic-director-context";Save();
  Check(RunArtifactManager.instance&&!RunArtifactManager.instance.IsArtifactEnabled(RoR2Content.Artifacts.eliteOnlyArtifactDef),"Original disabled Honor artifact missing");
  priorDirectorEliteTiers=RewardField(typeof(CombatDirector),"eliteTiers").GetValue(null);Check(priorDirectorEliteTiers==null,"Existing original elite tiers");StaticCall(typeof(CombatDirector),"Init");
  foreach(var name in new[]{"masterPrefabs","masterPrefabMasterComponents","aiMasterPrefabs","masterNames"}){var field=RewardField(typeof(MasterCatalog),name);var old=field.GetValue(null);Check(old==null||((Array)old).Length==0,"Existing master catalog "+name);directorMasterFields[field]=old;}
  directorMasterMap=(IDictionary)RewardField(typeof(MasterCatalog),"nameToIndexMap").GetValue(null);Check(directorMasterMap.Count==0&&NetworkPreloadManager.previouslyRequestedMasters.Count==0&&NetworkPreloadManager.requestMasterList.Count==0,"Existing preload/catalog state");StaticCall(typeof(MasterCatalog),"SetEntries",new object[]{new[]{template}});
  var index=MasterCatalog.FindMasterIndex(template);Check(MasterCatalog.GetMasterPrefab(index)==template,"Original master catalog identity");r.director.masterIndex=(int)index;
  directorPlayer=player.master.GetComponent<PlayerCharacterMasterController>();Check(directorPlayer&&!directorPlayer.gameObject.activeInHierarchy&&!directorPlayer.networkUser&&PlayerCharacterMasterController.instances.Count==0,"Measured local player registration scope changed");
  if(!directorPlayer.master)Call(directorPlayer,"Awake");Check(directorPlayer.master==player.master,"Original player controller master binding");directorPlayerRegistered=true;Call(directorPlayer,"OnEnable");r.director.playerRegistered=PlayerCharacterMasterController.instances.Count==1&&PlayerCharacterMasterController.instances[0]==directorPlayer;Check(r.director.playerRegistered,"Original player registration missing");
  r.director.participatingPlayers=Run.instance.participatingPlayerCount;r.director.livingPlayers=Run.instance.livingPlayerCount;Check(r.director.participatingPlayers==PlayerCharacterMasterController.instances.Count&&r.director.participatingPlayers==1&&r.director.livingPlayers==PlayerCharacterMasterController.GetPlayersWithBodiesCount()&&r.director.livingPlayers==1&&!directorPlayer.isConnected&&!directorPlayer.networkUser,"Original participant/body counts or unavailable user contract changed");
  StartOriginalRunClock();
  automaticDeck=Instantiate(artifactBundle.LoadAsset<DirectorCardCategorySelection>(cfg.enemyDirectorDeckAsset));Check(automaticDeck&&automaticDeck.categories.Length==1&&automaticDeck.categories[0].cards.Length==1,"Measured one-card director subset missing");
  var card=automaticDeck.categories[0].cards[0];Check(card.spawnCard.name==rewardCard.name&&card.selectionWeight==2&&card.spawnDistance==DirectorCore.MonsterSpawnDistance.Standard&&!card.preventOverhead&&card.minimumStageCompletions==0&&!card.requiredUnlockableDef&&!card.forbiddenUnlockableDef&&string.IsNullOrEmpty(card.requiredUnlockable)&&string.IsNullOrEmpty(card.forbiddenUnlockable),"Source Beetle card metadata changed");card.spawnCard=rewardCard;r.director.selectedCardWeight=card.selectionWeight;Check(card.IsAvailable(),"Original base card availability failed");
  automaticDirectorHost=Instantiate(artifactBundle.LoadAsset<GameObject>(cfg.enemyDirectorAsset));Check(automaticDirectorHost&&!automaticDirectorHost.activeSelf,"Source director root isolation missing");rewardDirector=automaticDirectorHost.GetComponent<CombatDirector>();Check(rewardDirector&&rewardDirector.enabled&&automaticDirectorHost.GetComponents<MonoBehaviour>().Length==1,"Source fast director component scope changed");
  r.director.sourceSettings=rewardDirector.monsterCredit==0&&rewardDirector.creditMultiplier==.75f&&rewardDirector.moneyWaveIntervals.Length==1&&rewardDirector.moneyWaveIntervals[0].min==1&&rewardDirector.moneyWaveIntervals[0].max==1&&rewardDirector.minRerollSpawnInterval==4.5f&&rewardDirector.maxRerollSpawnInterval==9&&rewardDirector.targetPlayers&&!rewardDirector.ignoreTeamSizeLimit&&rewardDirector.maximumNumberToSpawnBeforeSkipping==6&&rewardDirector.spawnDistanceMultiplier==1&&rewardDirector.minSpawnRange==0&&!rewardDirector.shouldSpawnOneWave;
  Check(r.director.sourceSettings,"Original fast director settings changed");rewardDirector.monsterCards=automaticDeck;rewardDirector.onSpawnedServer.AddListener(obj=>{RecordRewardSpawn(obj);RecordDirectorActor(obj,player);if(r.director.actors.Count==1){r.director.position=enemyBody.transform.position;r.director.spawnDistance=Vector3.Distance(player.transform.position,enemyBody.transform.position);r.director.originalTarget=rewardDirector.currentSpawnTarget==player.gameObject;}if(r.director.actors.Count==limit){rewardDirector.enabled=false;r.director.stopped=true;r.director.stoppedAt=Time.realtimeSinceStartup-automaticDirectorBegan;}});
  StartOriginalNavigation();automaticDirectorBegan=Time.realtimeSinceStartup;automaticDirectorHost.SetActive(true);Check(CombatDirector.instancesList.Contains(rewardDirector),"Original natural director registration missing");float previous=0;
  try{
   while(!enemyBody&&Time.realtimeSinceStartup-automaticDirectorBegan<55){yield return new WaitForEndOfFrame();r.director.seconds=Time.realtimeSinceStartup-automaticDirectorBegan;var credit=rewardDirector.monsterCredit;if(credit>previous)r.director.creditSteps++;previous=credit;r.director.creditPeak=Mathf.Max(r.director.creditPeak,credit);r.director.originalTarget|=rewardDirector.currentSpawnTarget==player.gameObject;if(Time.frameCount%30==0)Save();}
  }finally{CaptureRewardSummons(template.GetComponent<CharacterMaster>().bodyPrefab,template);}
  Check(enemyBody&&r.rewards.spawnEvents==1&&r.rewards.summonEvents==1,"Original scheduled spawn timed out");yield return null;
  r.director.creditAfter=rewardDirector.monsterCredit;r.director.spent=rewardDirector.totalCreditsSpent;r.director.preloaded=NetworkPreloadManager.previouslyRequestedMasters.Count==1&&NetworkPreloadManager.previouslyRequestedMasters[0].Equals(index);
  // Original participant/body getters count the real registered master, without a NetworkUser.
  var waves=(Array)typeof(CombatDirector).GetField("moneyWaves",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(rewardDirector);var wave=waves.GetValue(0);var wt=wave.GetType();float timer=(float)wt.GetField("timer").GetValue(wave),fraction=(float)wt.GetField("accumulatedAward",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(wave);
  float rate=rewardDirector.creditMultiplier*(1+.4f*Run.instance.compensatedDifficultyCoefficient)*(.5f+.5f*Run.instance.participatingPlayerCount);float earned=r.director.creditAfter+r.director.spent+fraction,scheduled=earned/rate+timer;r.director.creditConserved=r.director.spent==8&&r.director.creditAfter>=0&&r.director.creditSteps>=7&&Mathf.Abs(scheduled-r.director.seconds)<.15f;
  DirectorCore.GetMonsterSpawnDistance(card.spawnDistance,out r.director.minDistance,out r.director.maxDistance);r.director.placement=r.director.spawnDistance>=r.director.minDistance-.1f&&r.director.spawnDistance<=r.director.maxDistance+.1f;
  Check(r.director.originalTarget&&r.director.preloaded&&r.director.creditConserved&&r.director.placement&&(cfg.integratedWorld||limit==3?rewardDirector.enabled:!rewardDirector.enabled),"Original targeting/preload/credit/placement assertions failed");Save();
 }
 void CleanupAutomaticDirector(){
  ownedNavigationTick=null;
  if(directorPlayerRegistered&&directorPlayer){Call(directorPlayer,"OnDisable");directorPlayerRegistered=false;}
  if(automaticDirectorHost)Destroy(automaticDirectorHost);if(automaticDeck)Destroy(automaticDeck);
  if(directorMasterMap!=null){directorMasterMap.Clear();foreach(var entry in directorMasterFields)entry.Key.SetValue(null,entry.Value);directorMasterFields.Clear();NetworkPreloadManager.previouslyRequestedMasters.Clear();NetworkPreloadManager.requestMasterList.Clear();RewardField(typeof(CombatDirector),"eliteTiers").SetValue(null,priorDirectorEliteTiers);}
 }
 void ReleaseDirectorAssets(){
  if(directorTeamEffects==null)return;
  foreach(var team in new[]{TeamIndex.Player,TeamIndex.Monster,TeamIndex.Lunar,TeamIndex.Void}){var def=TeamCatalog.GetTeamDef(team);var effect=def.levelUpEffect;Check(effect==directorTeamEffects[team==TeamIndex.Player?0:1],"Owned team effect reference changed before release");def.levelUpEffect=null;Addressables.Release(effect);}
  directorTeamEffects=null;r.director.navigationAgents=NavigationAgentCount();r.director.cleaned=!automaticDirectorHost&&!automaticDeck&&!directorPlayerRegistered&&PlayerCharacterMasterController.instances.Count==0&&directorMasterMap.Count==0&&r.director.navigationAgents==0;Check(r.director.cleaned,"Automatic director owned teardown incomplete");
 }
}
