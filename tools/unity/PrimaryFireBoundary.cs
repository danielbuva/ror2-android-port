using System;
using System.Linq;
using System.Reflection;
using EntityStates;
using EntityStates.Commando.CommandoWeapon;
using RoR2;
using RoR2.Skills;
using UnityEngine;

// Diagnostic scheduling isolates the original skill factory/activation from its first native consumer.
public sealed partial class MovementBatchProbe {
 bool IsPlayableSpine(){return r.id.StartsWith("body-state-spawn-state-auto-nova-spine");}
 FieldInfo[] spineFields;object[] spinePrior;EntityStateConfiguration spineReload;
 EntityState lastSpineWeaponState;
 EntityStateConfiguration[] PrepareSpineConfigs(Result cfg,EntityStateConfiguration spawn){
  spineFields=(cfg.combatSpine?new[]{typeof(FirePistol2),typeof(FireBarrage),typeof(EntityStates.Commando.DodgeState)}:new[]{typeof(FirePistol2)}).SelectMany(t=>t.GetFields(BindingFlags.Public|BindingFlags.Static|BindingFlags.DeclaredOnly)).ToArray();spinePrior=spineFields.Select(x=>x.GetValue(null)).ToArray();
  var fire=artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryFireConfigAsset);
  var reload=artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryReloadConfigAsset);
  Check(fire&&reload,"Spine primary configurations missing");spineReload=Instantiate(reload);
  spineReload.serializedFieldsCollection.serializedFields=reload.serializedFieldsCollection.serializedFields.ToArray();
  int index=Array.FindIndex(spineReload.serializedFieldsCollection.serializedFields,x=>x.fieldName=="enterSoundString");Check(index>=0,"Spine reload sound field missing");
  spineReload.serializedFieldsCollection.serializedFields[index].fieldValue.stringValue="";
  r.primary=new PrimaryFireReport{silentFixture=true};var configs=new[]{spawn,fire,spineReload};return cfg.combatSpine?configs.Concat(PrepareCombatConfigs(cfg)).ToArray():configs;
 }
 void ApplySpineExclusions(){
  FirePistol2.firePistolSoundString="";FirePistol2.muzzleEffectPrefab=null;FirePistol2.hitEffectPrefab=null;FirePistol2.tracerEffectPrefab=null;
  r.primary.damageCoefficient=FirePistol2.damageCoefficient;r.primary.force=FirePistol2.force;r.primary.baseDuration=FirePistol2.baseDuration;
  if(r.combat!=null){FireBarrage.fireBarrageSoundString="";FireBarrage.effectPrefab=null;FireBarrage.hitEffectPrefab=null;FireBarrage.tracerEffectPrefab=null;EntityStates.Commando.DodgeState.dodgeSoundString="";EntityStates.Commando.DodgeState.jetEffect=null;}
 }
 void ObserveSpinePrimary(CharacterBody body){
  var weapon=body.skillLocator.primary.stateMachine;var state=weapon.state;
  if(state!=lastSpineWeaponState){
   if(state is FirePistol2){r.primary.shots++;r.primary.entered=true;r.primary.firingAvailable=true;r.primary.spreadAfter=body.spreadBloomAngle;}
   if(state is ReloadPistols)r.primary.reloads++;
   lastSpineWeaponState=state;
  }
  r.primary.stockAfter=body.skillLocator.primary.stock;r.primary.state=state.GetType().FullName;
 }
 void CleanupSpineConfig(){
  CleanupCombatConfigs();
  if(spineFields!=null){for(int i=0;i<spineFields.Length;i++)spineFields[i].SetValue(null,spinePrior[i]);spineFields=null;}
  if(spineReload)Destroy(spineReload);
 }
 [Serializable] public class PrimaryFireReport {
  public string skill,state,firstFailure,audioException,weaponInitialState,definitionType;
  public bool weaponEnabled,slotWeaponMatched,rootActive;
  public int stockBefore,stockAfter,stepBefore,stepAfter,authorityEvents,serverEvents;
  public float damageCoefficient,force,baseDuration;
  public bool scheduled,entered,firingAvailable,audioAvailable,silentFixture;public int shots,reloads;public float spreadAfter;
 }
 bool IsPrimaryFire(){return r.id.StartsWith("body-state-spawn-state-primary-");}
 void PrimaryFireBoundary(CharacterBody body,Result cfg){
  r.primary=new PrimaryFireReport();
  var report=r.primary;var weapon=EntityStateMachine.FindByCustomName(body.gameObject,"Weapon");
  var skill=body.skillLocator.primary;var def=skill.skillDef as SteppedSkillDef;
  report.weaponEnabled=weapon&&weapon.enabled;report.rootActive=body.gameObject.activeInHierarchy;report.weaponInitialState=weapon&&weapon.state!=null?weapon.state.GetType().FullName:"null";report.definitionType=skill.skillDef?skill.skillDef.GetType().FullName:"null";report.slotWeaponMatched=skill.stateMachine==weapon;Save();
  Check(weapon&&!report.rootActive&&weapon.state is Uninitialized&&def&&skill.stateMachine==weapon,"Original primary/Weapon pre-Start contract");
  Check(def==skill.skillFamily.defaultSkillDef&&((ScriptableObject)def).name=="CommandoBodyFirePistol"&&def.activationState.stateType==typeof(FirePistol2)&&def.stepCount==2&&def.stepGraceDuration==.1f,"Original primary definition/state/step identity");
  var fire=artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryFireConfigAsset);
  var reload=artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryReloadConfigAsset);
  Check(fire&&reload&&(Type)fire.targetType==typeof(FirePistol2)&&(Type)reload.targetType==typeof(ReloadPistols),"Original primary state configuration identities");
  Check(!ownsStateCatalog,"Existing state catalog; refuse primary replacement");
  var fields=typeof(FirePistol2).GetFields(BindingFlags.Public|BindingFlags.Static|BindingFlags.DeclaredOnly);
  var prior=fields.Select(x=>x.GetValue(null)).ToArray();
  Action<GenericSkill> authority=s=>{if(s==skill)report.authorityEvents++;},server=s=>{if(s==skill)report.serverEvents++;};
  body.onSkillActivatedAuthority+=authority;body.onSkillActivatedServer+=server;
  try{
   ownsStateCatalog=true;BuildStateCatalog(new[]{typeof(Uninitialized),typeof(Idle),typeof(FirePistol2),typeof(ReloadPistols)},new[]{fire,reload});
   report.skill=((ScriptableObject)def).name;report.damageCoefficient=FirePistol2.damageCoefficient;report.force=FirePistol2.force;report.baseDuration=FirePistol2.baseDuration;
   Check(report.damageCoefficient==1&&report.force==200&&report.baseDuration==.15f&&FirePistol2.firePistolSoundString=="Play_commando_R"&&FirePistol2.muzzleEffectPrefab&&FirePistol2.hitEffectPrefab&&FirePistol2.tracerEffectPrefab,"Original pistol configuration fields/references");
   var state=typeof(SteppedSkillDef).GetMethod("InstantiateNextState",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(def,new object[]{skill}) as FirePistol2;
   var pistol=typeof(FirePistol2).GetField("pistol",BindingFlags.Instance|BindingFlags.NonPublic);
   Check(state!=null&&state.activatorSkillSlot==skill&&(int)pistol.GetValue(state)==0,"Original factory/ISkillState/step setter result");
   var reloadState=EntityStateCatalog.InstantiateState(EntityStateCatalog.GetStateIndex(typeof(ReloadPistols))) as ReloadPistols;
   Check(reloadState!=null&&reloadState.enterSoundString=="Play_loader_m2_launch","Original reload instance initializer");
   r.phase="original-primary-weapon-start";Save();Call(weapon,"Start");
   Check(weapon.state is Idle&&!weapon.HasPendingState()&&skill.stock==1&&skill.maxStock==1&&skill.CanExecute(),"Original Weapon Idle/primary readiness");
   Check(DLC2Content.Items.IncreasePrimaryDamage&&body.inventory.GetItemCountEffective(DLC2Content.Items.IncreasePrimaryDamage)==0,"Original empty primary activation item contract");
   report.stockBefore=skill.stock;report.stepBefore=(int)pistol.GetValue(state);
   r.phase="original-primary-execute-if-ready";Save();
   Check(skill.ExecuteIfReady(),"Original primary execution rejected");
   report.stockAfter=skill.stock;report.scheduled=weapon.HasPendingState();
   var next=typeof(SteppedSkillDef).GetMethod("InstantiateNextState",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(def,new object[]{skill}) as FirePistol2;report.stepAfter=(int)pistol.GetValue(next);
   Check(report.scheduled&&weapon.state is Idle&&report.stockAfter==0&&report.stepAfter==1&&report.authorityEvents==1&&report.serverEvents==1,"Original activation/stock/step/authority events");
   Check(!skill.CanExecute()&&!skill.ExecuteIfReady()&&report.authorityEvents==1&&report.serverEvents==1,"Original pending-state/empty-stock rejection");
   if(r.id.EndsWith("-native")){
    r.phase="original-primary-on-enter";Save();
    try{weapon.ManagedFixedUpdate(.02f);report.entered=true;report.firingAvailable=true;}
    catch(DllNotFoundException e){report.audioException=e.ToString();report.firstFailure="Wwise native event posting";report.entered=weapon.state is FirePistol2;Check(report.audioException.Contains("AkSoundEngine")&&report.audioException.Contains("FirePistol2"),"Native failure did not belong to original pistol audio path");}
    Check(report.entered&&!report.firingAvailable&&!report.audioAvailable&&!string.IsNullOrEmpty(report.audioException),"Expected bounded unavailable native-audio observation changed; review result");
   }
   report.state=weapon.state.GetType().FullName;Save();
  }finally{
   body.onSkillActivatedAuthority-=authority;body.onSkillActivatedServer-=server;
   Call(weapon,"OnDestroy");Check(weapon.state==null,"Original primary Weapon cleanup");
   for(int i=0;i<fields.Length;i++)fields[i].SetValue(null,prior[i]);
  }
 }
}
