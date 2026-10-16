using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;

// Ordinary selection follows the original survivor contract and the owned
// Android profile. Developer-only selections remain assisted.
public sealed partial class MovementBatchProbe {
 [Serializable] public class SourceAnimationEventReport {public string model;public float seconds;public bool componentEnabled,modelActive,characterBodyMatched,locatorPresent,cachedLocator,cachedBody;public bool[] airstrikeMuzzles;}
 float nextSourceAnimationObservation;
 GameObject selectedBodyStaging;
 HashSet<string> offlineUnlockPreview;
 void EnsureOfflineUnlockPreview(){if(offlineUnlockPreview==null)offlineUnlockPreview=AndroidOfflineProfile.PreviewUnlockNames(System.IO.Path.Combine(Application.persistentDataPath,"android-profile-v1"));}
 static string SurvivorUnlockName(SurvivorDef survivor){return survivor.unlockableDef?survivor.unlockableDef.cachedName:survivor.unlockableName;}
 bool IsOrdinarySurvivorAvailable(SurvivorDef survivor){
  if(!survivor||!survivor.bodyPrefab||survivor.hidden||survivor.GetRequiredExpansion()||survivor.GetRequiredEntitlement())return false;
  var name=SurvivorUnlockName(survivor);if(string.IsNullOrEmpty(name))return true;
  EnsureOfflineUnlockPreview();return offlineUnlockPreview.Contains(name);
 }
 SurvivorDef[] OrdinarySurvivorChoices(){
  EnsureOfflineUnlockPreview();
  var definitions=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef,Array.Empty<SurvivorDef>());
  var choices=definitions.Where(IsOrdinarySurvivorAvailable).OrderBy(value=>value.cachedName=="Commando"?0:value.cachedName=="Huntress"?1:2).ThenBy(value=>value.cachedName,StringComparer.Ordinal).ToArray();
  Check(choices.Any(value=>value.cachedName=="Commando")&&choices.Any(value=>value.cachedName=="Huntress"),"Original free survivor choices unavailable");
  return choices;
 }
 void CycleOrdinarySurvivor(int direction){
  var choices=OrdinarySurvivorChoices();var index=Array.FindIndex(choices,value=>value.cachedName==r.selectedSurvivor);
  r.selectedSurvivor=choices[(index+direction+choices.Length)%choices.Length].cachedName;Save();
 }
 void ConfirmSelectedSurvivorUnlock(){
  if(r.developerSurvivorOverride||string.IsNullOrEmpty(r.selectedSurvivor))return;
  var survivor=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef,Array.Empty<SurvivorDef>()).SingleOrDefault(value=>value&&value.cachedName==r.selectedSurvivor);
  Check(survivor!=null,"Selected survivor missing when native profile loaded");
  var name=SurvivorUnlockName(survivor);if(string.IsNullOrEmpty(name))return;
  var definition=UnlockableCatalog.GetUnlockableDef(name);
  Check(definition&&definition.cachedName==name&&(!survivor.unlockableDef||survivor.unlockableDef==definition)&&HasOwnedProfileUnlock(definition),"Selected survivor lacks its original Android profile unlock");
 }
 bool SelectedSourceSurvivor(){return r!=null&&!string.IsNullOrEmpty(r.selectedSurvivor)&&r.selectedSurvivor!="Commando";}
 GameObject SelectedPlayerPrefab(Result cfg){
  if(string.IsNullOrEmpty(r.selectedSurvivor))r.selectedSurvivor="Commando";
  if(r.selectedSurvivor=="Commando")return artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);
  Check(cfg.integratedWorld&&r.liveCatalogs!=null,"Unsupported offline survivor selection");
  var definitions=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef,Array.Empty<SurvivorDef>());
  var survivor=definitions.SingleOrDefault(value=>value&&value.cachedName==r.selectedSurvivor);
  Check(survivor&&survivor.bodyPrefab&&!survivor.hidden&&!survivor.GetRequiredExpansion()&&!survivor.GetRequiredEntitlement(),"Selected survivor requires an unavailable original expansion or entitlement");
  bool locked=!string.IsNullOrEmpty(SurvivorUnlockName(survivor));
  Check(!locked||IsOrdinarySurvivorAvailable(survivor)||r.developerSurvivorOverride&&r.debugOptions!=null&&!string.IsNullOrWhiteSpace(r.debugOptions.purpose)&&r.debugOptions.purpose.Length<=160,"Selected survivor requires an original unlock; developer selection needs an explicit diagnostic purpose");
  Check(!r.developerSurvivorOverride||locked,"Developer survivor override is limited to locked base survivors");
  var body=survivor.bodyPrefab.GetComponent<CharacterBody>();
  Check(body&&body.bodyIndex!=BodyIndex.None&&BodyCatalog.GetBodyPrefab(body.bodyIndex)==survivor.bodyPrefab,"Selected source survivor/body catalog identity differs");
  return survivor.bodyPrefab;
 }
 void ObserveSourceAnimationEvents(CharacterBody player,float elapsed){
  if(!SelectedSourceSurvivor()||r.sourceAnimationEvents!=null&&elapsed<nextSourceAnimationObservation)return;
  nextSourceAnimationObservation=elapsed+2f;
  var model=player.modelLocator?player.modelLocator.modelTransform:null;
  if(!model)return;
  var events=model.GetComponent<AnimationEvents>();var character=model.GetComponent<CharacterModel>();var locator=model.GetComponent<ChildLocator>();
  if(!events)return;
  var flags=BindingFlags.Instance|BindingFlags.NonPublic;
  var locatorField=typeof(AnimationEvents).GetField("childLocator",flags);var bodyField=typeof(AnimationEvents).GetField("bodyObject",flags);
  Check(locatorField!=null&&bodyField!=null,"Original animation-event cache contract changed");
  var cachedLocator=locatorField.GetValue(events) as ChildLocator;var cachedBody=bodyField.GetValue(events) as GameObject;
  r.sourceAnimationEvents=new SourceAnimationEventReport{model=model.name,seconds=elapsed,componentEnabled=events.enabled,modelActive=model.gameObject.activeInHierarchy,characterBodyMatched=character&&character.body==player,locatorPresent=locator,cachedLocator=cachedLocator==locator,cachedBody=cachedBody==player.gameObject,airstrikeMuzzles=r.selectedSurvivor=="Captain"?new[]{"MuzzleAirstrike1","MuzzleAirstrike2","MuzzleAirstrike3"}.Select(name=>locator&&locator.FindChild(name)).ToArray():null};
 }
}
