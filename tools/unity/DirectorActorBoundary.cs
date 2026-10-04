using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.CharacterAI;
using UnityEngine;
using UnityEngine.Networking;

// Per-actor observations and ownership; original callbacks retain all simulation/reward logic.
public sealed partial class MovementBatchProbe {
 [Serializable] public class DirectorActorReport {
  public uint masterId,bodyId,gold,experience;public float spawnedAt,spawnDistance,levelBeforeStart,levelAfterStart,health,pathBeforeDamage,maxFallBeforeDamage,damageReceived,damageToPlayer,deathAt;
  public bool started,linked,authority,target,route,reachable,dead,bodyDestroyed,masterDestroyed,corpse,cleaned;public int groundedBeforeDamage,damageEvents,deathEvents;public Vector3 spawnPosition,position;
  public int motorStarts;public float maxPhysicsStepBeforeDamage,maxRenderGap,maxSettledRenderGap;public List<DirectorPoseSample> initialPoses=new List<DirectorPoseSample>();
 }
 [Serializable] public class DirectorPoseSample {public float seconds;public Vector3 render,physics;public int motorStarts;}
 sealed class DirectorActor {
  public CharacterMaster master;public CharacterBody body;public BaseAI ai;public GameObject model;public Vector3 previous;public DirectorActorReport report;
  public Action<CharacterBody> motorStarted;
 }
 readonly List<DirectorActor> directorActors=new List<DirectorActor>();
 void RecordDirectorActor(GameObject obj,CharacterBody player){
  var master=obj.GetComponent<CharacterMaster>();var body=master.GetBody();var rewards=body.GetComponent<DeathRewards>();
  Check(body&&rewards&&!directorActors.Any(x=>x.master==master),"Director emitted missing/duplicate actor");
  var row=new DirectorActorReport{masterId=master.netId.Value,bodyId=body.netId.Value,spawnedAt=Time.realtimeSinceStartup-automaticDirectorBegan,spawnDistance=Vector3.Distance(player.transform.position,body.transform.position),spawnPosition=body.transform.position,position=body.transform.position,levelBeforeStart=body.level,gold=rewards.goldReward,experience=rewards.expReward,deathAt=-1};
  var actor=new DirectorActor{master=master,body=body,ai=master.GetComponent<BaseAI>(),model=body.modelLocator.modelTransform.gameObject,previous=body.transform.position,report=row};directorActors.Add(actor);r.director.actors.Add(row);
  actor.motorStarted=started=>{Check(started==body,"Original motor event body mismatch");row.motorStarts++;};body.characterMotor.onMotorStart+=actor.motorStarted;
  Check(row.masterId!=0&&row.bodyId!=0&&(r.integratedWorld?row.gold>0&&row.experience>0:row.gold==3&&row.experience==1)&&body.cost==8&&master.inventory.GetItemCountPermanent(RoR2Content.Items.UseAmbientLevel)==1&&master.inventory.itemAcquisitionOrder.Count==1&&master.inventory.currentEquipmentIndex==EquipmentIndex.None,"Original per-actor spawn/reward/inventory contract changed");
  Check(directorActors.Select(x=>x.report.masterId).Distinct().Count()==directorActors.Count&&directorActors.Select(x=>x.report.bodyId).Distinct().Count()==directorActors.Count,"Director reused actor network identities");
 }
 void ObserveDirectorActors(){
  if(r.director==null)return;int live=0;
  foreach(var actor in directorActors){
   var row=actor.report;var body=actor.body;
   if(body){
    if(!row.started&&row.motorStarts==1&&actor.ai&&actor.ai.body==body&&(r.integratedWorld?body.level>=1:body.level==1)){
     row.started=true;row.levelAfterStart=body.level;row.linked=actor.master.GetBody()==body&&body.master==actor.master;row.authority=body.isServer&&body.hasEffectiveAuthority;
     Check(row.linked&&row.authority,"Original batch actor Start/link/authority failed");
     // Same measured world-only collision scope as the accepted first actor, applied to each owned clone.
     var solver=body.characterMotor.Motor;solver.CollidableLayers=LayerIndex.world.mask;solver.StableGroundLayers=LayerIndex.world.mask;solver.SetGroundSolvingActivation(true);
    }
    row.health=body.healthComponent.health;row.dead|=!body.healthComponent.alive;if(!row.dead)live++;
    // Interpolated render transforms are not the original solver's simulation position.
    row.position=body.characterMotor.Motor.TransientPosition;float age=Time.realtimeSinceStartup-automaticDirectorBegan-row.spawnedAt,gap=Vector3.Distance(body.transform.position,row.position);row.maxRenderGap=Mathf.Max(row.maxRenderGap,gap);
    if(row.initialPoses.Count<18)row.initialPoses.Add(new DirectorPoseSample{seconds=age,render=body.transform.position,physics=row.position,motorStarts=row.motorStarts});
    var delta=row.position-actor.previous;delta.y=0;
    if(row.damageEvents==0){row.maxPhysicsStepBeforeDamage=Mathf.Max(row.maxPhysicsStepBeforeDamage,delta.magnitude);row.pathBeforeDamage+=delta.magnitude;row.maxFallBeforeDamage=Mathf.Max(row.maxFallBeforeDamage,row.spawnPosition.y-row.position.y);if(body.characterMotor.isGrounded)row.groundedBeforeDamage++;if(age>.25f)row.maxSettledRenderGap=Mathf.Max(row.maxSettledRenderGap,gap);}actor.previous=row.position;
   }
   if(actor.ai){row.target|=actor.ai.currentEnemy.characterBody==enemyPlayer;var output=actor.ai.broadNavigationAgent.output;row.route|=output.nextPosition.HasValue;row.reachable|=output.targetReachable;}
   if(row.dead){row.bodyDestroyed=!body;row.masterDestroyed=!actor.master;row.corpse|=!body&&actor.model&&actor.model.GetComponent<Corpse>();}
  }
  r.director.livePeak=Math.Max(r.director.livePeak,live);
 }
 void ObserveDirectorDamage(DamageReport damage){
  foreach(var actor in directorActors){var row=actor.report;if(damage.victimBody==actor.body){row.damageEvents++;row.damageReceived+=damage.damageDealt;}if(damage.attackerBody==actor.body&&damage.victimBody==enemyPlayer)row.damageToPlayer+=damage.damageDealt;}
 }
 void ObserveDirectorDeath(DamageReport damage){foreach(var actor in directorActors)if(damage.victimBody==actor.body){actor.report.deathEvents++;actor.report.dead=true;actor.report.deathAt=Time.realtimeSinceStartup;}}
 bool DirectorBatch(){return r.director!=null&&r.director.spawnLimit==3;}
 CharacterBody DirectorReturnFireTarget(){return directorActors.Where(x=>x.body&&!x.report.dead&&x.report.pathBeforeDamage>4&&x.report.groundedBeforeDamage>100).Select(x=>x.body).FirstOrDefault();}
 void VerifyDirectorBatch(){
  ObserveDirectorActors();ObserveEnemyRewards();Check(r.director.stopped&&!rewardDirector.enabled&&directorActors.Count==3&&r.rewards.spawnEvents==3&&r.rewards.summonEvents==3,"Original three-spawn scheduling incomplete");
  foreach(var actor in directorActors){var row=actor.report;Check(row.started&&row.motorStarts==1&&row.linked&&row.authority&&row.levelBeforeStart==0&&row.levelAfterStart==1&&row.target&&row.route&&row.reachable,"Original batch actor lifecycle/AI/navigation incomplete: "+row.masterId);Check(row.spawnDistance>=r.director.minDistance-.1f&&row.spawnDistance<=r.director.maxDistance+.1f&&row.pathBeforeDamage>4&&row.groundedBeforeDamage>100&&row.maxFallBeforeDamage<10&&row.maxPhysicsStepBeforeDamage<1.5f&&row.maxSettledRenderGap<1,"Original batch actor placement/continuous physics/grounded pursuit failed: "+row.masterId);Check(row.dead&&row.damageEvents>0&&row.damageReceived>=80&&row.deathEvents==1&&row.bodyDestroyed&&row.masterDestroyed&&row.corpse,"Original batch actor death/lifetime incomplete: "+row.masterId);}
  Check(r.director.livePeak>=2&&r.director.navigationAgentPeak>=2,"Multiple original actors never coexisted/navigated");
  var gold=(uint)directorActors.Sum(x=>(long)x.report.gold);var xp=(ulong)directorActors.Sum(x=>(long)x.report.experience);Check(r.rewards.moneyAfter-r.rewards.moneyBefore==gold&&r.rewards.experienceAfter-r.rewards.experienceBefore==xp&&r.rewards.goldEvents==gold&&r.rewards.queuedExperience&&r.rewards.pendingPeak>=1&&r.rewards.teamLevel==1,"Original aggregate gold/timed XP incomplete");
  r.director.totalSpent=rewardDirector.totalCreditsSpent;r.director.totalCreditAfter=rewardDirector.monsterCredit;var waves=(Array)typeof(CombatDirector).GetField("moneyWaves",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(rewardDirector);var wave=waves.GetValue(0);var wt=wave.GetType();float timer=(float)wt.GetField("timer").GetValue(wave),fraction=(float)wt.GetField("accumulatedAward",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(wave);
  float rate=rewardDirector.creditMultiplier*(1+.4f*r.rewards.compensatedDifficulty)*(.5f+.5f*Run.instance.participatingPlayerCount);r.director.batchCreditConserved=r.director.totalSpent==24&&r.director.totalCreditAfter>=0&&Mathf.Abs((r.director.totalCreditAfter+r.director.totalSpent+fraction)/rate+timer-r.director.stoppedAt)<.3f;Check(r.director.batchCreditConserved,"Original three-spawn cost/timing conservation failed");Save();
 }
 void CleanupDirectorActors(){foreach(var actor in directorActors){if(actor.body){actor.body.characterMotor.onMotorStart-=actor.motorStarted;NetworkServer.Destroy(actor.body.gameObject);}if(actor.master)NetworkServer.Destroy(actor.master.gameObject);if(actor.model)Destroy(actor.model);}}
 void VerifyDirectorActorCleanup(){foreach(var actor in directorActors){actor.report.cleaned=!actor.body&&!actor.master&&!actor.model;Check(actor.report.cleaned,"Owned batch actor/model remains: "+actor.report.masterId);}}
}
