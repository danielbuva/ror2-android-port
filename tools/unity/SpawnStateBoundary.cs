using System;
using System.Linq;
using System.Reflection;
using EntityStates;
using RoR2;
using UnityEngine;

public sealed partial class MovementBatchProbe {
 bool ownsSpawnConfig;float priorSpawnDelay;string priorSpawnSound;
 void PrepareSpawnStateCatalog(Result cfg){
  Check(!ownsStateCatalog,"Existing state catalog ownership");
  var types=new[]{typeof(Uninitialized),typeof(Idle),typeof(SpawnTeleporterState),typeof(GenericCharacterMain)};
  var flags=BindingFlags.NonPublic|BindingFlags.Static;
  Check(((Type[])typeof(EntityStateCatalog).GetField("stateIndexToType",flags).GetValue(null)).Length==0&&((System.Collections.IDictionary)typeof(EntityStateCatalog).GetField("stateTypeToIndex",flags).GetValue(null)).Count==0&&((System.Collections.IDictionary)typeof(EntityStateCatalog).GetField("instanceFieldInitializers",flags).GetValue(null)).Count==0,"Existing state catalog; refuse replacement");
  var config=artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.spawnConfigAsset);
  Check(config&&(Type)config.targetType==typeof(SpawnTeleporterState),"Actual spawn configuration identity");
  priorSpawnDelay=SpawnTeleporterState.initialDelay;priorSpawnSound=SpawnTeleporterState.soundString;ownsSpawnConfig=true;
  ownsStateCatalog=true;r.phase="original-spawn-state-catalog";Save();BuildStateCatalog(types,new[]{config});
  foreach(var type in types){var index=EntityStateCatalog.GetStateIndex(type);Check(index!=EntityStateIndex.Invalid&&EntityStateCatalog.GetStateType(index)==type&&EntityStateCatalog.InstantiateState(index).GetType()==type,"Original spawn state identity round trip");}
  Check(cfg.sourceSpawnDelay>0&&cfg.sourceSpawnDelay<10&&SpawnTeleporterState.initialDelay==cfg.sourceSpawnDelay,"Original configured spawn delay");
  Check(SpawnTeleporterState.soundString==cfg.sourceSpawnSound,"Original configured spawn sound");
 }
 void CleanupSpawnConfig(){if(ownsSpawnConfig){SpawnTeleporterState.initialDelay=priorSpawnDelay;SpawnTeleporterState.soundString=priorSpawnSound;ownsSpawnConfig=false;}}
 void ProbeSpawnStates(CharacterBody body,Result cfg){
  PrepareSpawnStateCatalog(cfg);
  if(r.id=="body-state-spawn-state-overlay"){ProbeTeleportOverlay(body,cfg);return;}
  if(r.id=="body-state-spawn-state-buff-removal"){
   Check(RoR2Content.Buffs.MedkitHeal&&RoR2Content.Buffs.TonicBuff&&DLC2Content.Buffs.SoulCost,"Original removal definitions");
   Check(body.GetBuffCount(RoR2Content.Buffs.MedkitHeal)==0&&body.GetBuffCount(RoR2Content.Buffs.TonicBuff)==0&&body.GetBuffCount(DLC2Content.Buffs.SoulCost)==0,"Unrelated removal buffs remain absent");
   var buff=RoR2Content.Buffs.HiddenInvincibility;Check(buff&&body.GetBuffCount(buff)==0,"Original empty hidden buff");r.phase="original-hidden-buff-cycle";Save();
   body.AddBuff(buff);Check(body.GetBuffCount(buff)==1,"Original hidden buff addition");body.RemoveBuff(buff);Check(body.GetBuffCount(buff)==0,"Original hidden buff removal");
   body.AddTimedBuff(buff,3f);float duration;Check(body.GetBuffCount(buff)==1&&body.GetTimedBuffTotalDurationForIndex(buff.buffIndex,out duration)&&duration==3f,"Original timed hidden buff restoration");
   body.ClearTimedBuffs(buff);Check(body.GetBuffCount(buff)==0,"Original timed hidden buff cleanup");return;
  }
  var machine=EntityStateMachine.FindByCustomName(body.gameObject,"Body");
  var weapon=EntityStateMachine.FindByCustomName(body.gameObject,"Weapon");var slide=EntityStateMachine.FindByCustomName(body.gameObject,"Slide");
  Check(machine&&weapon&&slide&&machine.initialStateType.stateType==typeof(SpawnTeleporterState)&&machine.mainStateType.stateType==typeof(GenericCharacterMain),"Original named body state path");
  var selected=r.id=="body-state-spawn-state-idle"?new[]{weapon,slide}:new[]{machine};Exception failure=null;
  try{
   foreach(var stateMachine in selected){
    Check(stateMachine.state is Uninitialized&&stateMachine.networker==body.GetComponent<NetworkStateMachine>(),"Automatic state Awake/network cache");
    if(r.id=="body-state-spawn-state-idle"){
     Check(stateMachine.initialStateType.stateType==typeof(Idle)&&stateMachine.mainStateType.stateType==typeof(Idle),"Original Idle machine types");
     r.phase="original-idle-start:"+stateMachine.customName;Save();Call(stateMachine,"Start");Check(stateMachine.state is Idle,"Original Idle Start entry");r.idleStarts++;
    }else{
     var model=body.modelLocator.modelTransform.GetComponent<CharacterModel>();Check(model,"Original model component");var priorInvisible=model.invisibilityCount;
     Check(RoR2Content.Buffs.HiddenInvincibility&&RoR2Content.Buffs.HiddenInvincibility.buffIndex!=BuffIndex.None&&body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility)==0,"Original hidden buff context");
     r.phase="original-spawn-state-start";Save();Call(stateMachine,"Start");r.spawnState=stateMachine.state.GetType().FullName;r.hiddenBuffCount=body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility);
     Check(stateMachine.state is SpawnTeleporterState&&r.hiddenBuffCount==1&&model.invisibilityCount==priorInvisible+1,"Original spawn OnEnter and buff/model effects");r.spawnStateEntries++;
     if(r.id=="body-state-spawn-state-transition"){
      r.phase="original-spawn-state-ticks";Save();int limit=Mathf.CeilToInt(cfg.sourceSpawnDelay/Time.fixedDeltaTime)+5;
      for(int i=0;i<limit&&stateMachine.state is SpawnTeleporterState;i++)stateMachine.ManagedFixedUpdate(Time.fixedDeltaTime);
      r.spawnState=stateMachine.state.GetType().FullName;Check(stateMachine.state is GenericCharacterMain,"Original timed transition to main");
     }
    }
   }
  }catch(Exception e){failure=e;}
  if(!string.IsNullOrEmpty(cfg.teleportMaterialAsset))ObserveTeleportOverlays(body);
  // Original destruction exits selected states while their actual catalog/buff dependencies still exist.
  foreach(var stateMachine in selected){try{Call(stateMachine,"OnDestroy");}catch(Exception e){failure=failure==null?e:new AggregateException(failure,e);}}
  if(failure!=null)throw failure;
  Check(selected.All(x=>x.state==null),"Original selected state teardown");
 }
}
