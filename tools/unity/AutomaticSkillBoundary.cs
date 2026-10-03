using System;
using System.Linq;
using RoR2;
using RoR2.Skills;
using UnityEngine;

// Public stock stimulus and observations only; original Unity/SkillDef callbacks recharge stocks.
public sealed partial class MovementBatchProbe {
 GenericSkill[] automaticSkills;
 GenericSkill rechargeSkill;
 float rechargeBegan;
 bool IsAutomaticSkill(){return r.id.StartsWith("body-state-spawn-state-auto-skill-");}
 int AutomaticSkillCount(){return !IsAutomaticSkill()?0:r.id.EndsWith("-neutral")?4:1;}
 GenericSkill[] SelectedAutomaticSkills(CharacterBody body){
  var slots=new[]{body.skillLocator.primary,body.skillLocator.secondary,body.skillLocator.utility,body.skillLocator.special};
  var suffix=r.id.Substring(r.id.LastIndexOf('-')+1);int index=Array.IndexOf(new[]{"primary","secondary","utility","special"},suffix);
  Check(slots.All(x=>x&&x.characterBody==body)&&slots.Distinct().Count()==4,"Original spawned skill slot/body identities");
  return suffix=="neutral"?slots:new[]{slots[index]};
 }
 void EnableAutomaticSkills(CharacterBody body){
  automaticSkills=SelectedAutomaticSkills(body);foreach(var skill in automaticSkills){Check(!skill.enabled,"Skill callback was already enabled");skill.enabled=true;}
 }
 void StartAutomaticSkillTiming(CharacterBody body){
  r.automaticSkillNames=automaticSkills.Select(x=>((ScriptableObject)x.skillDef).name).ToArray();r.automaticSkillTypes=automaticSkills.Select(x=>x.skillDef.GetType().FullName).ToArray();r.automaticSkillInitialStocks=automaticSkills.Select(x=>x.stock).ToArray();
  var names=new[]{"CommandoBodyFirePistol","CommandoBodyFireFMJ","CommandoBodyRoll","CommandoBodyBarrage"};var intervals=new[]{0f,3f,4f,9f};var slots=new[]{body.skillLocator.primary,body.skillLocator.secondary,body.skillLocator.utility,body.skillLocator.special};
  foreach(var skill in automaticSkills){int index=Array.IndexOf(slots,skill);Check(skill.skillDef==skill.skillFamily.defaultSkillDef&&((ScriptableObject)skill.skillDef).name==names[index]&&skill.skillDef.GetType()==(index==0?typeof(SteppedSkillDef):typeof(SkillDef)),"Original default SkillDef identity/type");Check(skill.maxStock==1&&skill.stock==1&&skill.baseRechargeInterval==intervals[index]&&skill.CalculateFinalRechargeInterval()==intervals[index]&&skill.stateMachine,"Measured original stock/recharge/machine contract");}
  if(!r.id.EndsWith("-neutral")){rechargeSkill=automaticSkills[0];r.skillRechargeExpected=intervals[Array.IndexOf(slots,rechargeSkill)];rechargeSkill.RemoveAllStocks();Check(rechargeSkill.stock==0&&rechargeSkill.rechargeStopwatch==0,"Original public stock-reset stimulus");rechargeBegan=Time.fixedTime;}
  Save();
 }
 void ObserveAutomaticSkills(){
  foreach(var skill in automaticSkills)Check(skill.enabled&&skill.skillDef==skill.skillFamily.defaultSkillDef&&skill.stock>=0&&skill.stock<=skill.maxStock,"Original automatic skill identity/stock bounds");
  if(rechargeSkill){float elapsed=Time.fixedTime-rechargeBegan;if(!r.skillRestocked&&rechargeSkill.stock==1){r.skillRechargeObserved=elapsed;Check(elapsed+.001f>=r.skillRechargeExpected&&elapsed<=r.skillRechargeExpected+.08f,"Original automatic stock recharge timing");r.skillRestocked=true;Save();}if(!r.skillRestocked)Check(elapsed<=r.skillRechargeExpected+.08f&&rechargeSkill.stock==0,"Original automatic recharge missed deadline");else Check(rechargeSkill.stock==1&&rechargeSkill.rechargeStopwatch==0,"Original full-stock recharge hold");}
  else foreach(var skill in automaticSkills)Check(skill.stock==1,"Original neutral full-stock hold");
 }
 void FinishAutomaticSkills(){Check(!rechargeSkill||r.skillRestocked,"Original automatic skill recharge incomplete");r.automaticSkillFinalStocks=automaticSkills.Select(x=>x.stock).ToArray();Save();}
}
