using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.AsyncOperations;

// Original input-driven interaction and real reward messages; no direct interaction/reward calls.
public sealed partial class MovementBatchProbe {
 [Serializable] public class InputBarrelReport {
  public BarrelReport source;public ClientCoinReport coin;
  public bool selected,pressed,released,opening,opened,xpDecoded,xpCosmeticsUnavailable,rewards,repeatRejected,selectionReleased,cleaned;
  public int interactions,xpMessages,coinReferencesBefore,coinReferencesAfter,orbInstancesBefore,orbInstancesAfter;public float goldEvents;
  public string xpSettingBefore,xpSettingDeclared,xpSettingActive,xpSettingRestored,scope;
 }
 IEnumerator ProbeOriginalInputBarrel(CharacterBody player,Result cfg){
  r.inputBarrel=new InputBarrelReport{source=new BarrelReport(),scope="Original automatic InteractionDriver selection/input/server dispatch/source cash-barrel rewards and genuine client messages. Diagnostic input/manual source placement; original optional XP cosmetics disabled, no native audio/physical interaction/normal placement/purchase/drop/profile/progression/full startup acceptance."};r.phase="original-input-barrel-prepare";Save();
  Check(r.clientCoin.cleaned&&r.interactionSelection.cleaned&&player.networkIdentity.hasAuthority&&activeBodyClient.isConnected&&NetworkServer.active&&!PauseStopController.instance,"Accepted coin/selection/local ownership required");
  var driver=player.GetComponent<InteractionDriver>();var bank=player.inputBank;Check(!driver.enabled&&!driver.currentInteractable&&!driver.interactableOverride&&!bank.interact.down,"Original neutral driver/input required");
  var requesters=(HashSet<UnityEngine.Object>)typeof(OutlineHighlight).GetField("preRenderHighlightRequesters",BindingFlags.Static|BindingFlags.NonPublic).GetValue(null);int priorRequesters=requesters.Count;var priorAim=bank.aimDirection;float priorScale=Time.timeScale;GameObject pauseHost=null;
  var option=SettingsConVars.cvExpAndMoneyEffects;r.inputBarrel.xpSettingBefore=option.GetString();r.inputBarrel.xpSettingDeclared=option.defaultValue;Check(r.inputBarrel.xpSettingBefore=="0"&&r.inputBarrel.xpSettingDeclared=="1"&&!activeBodyClient.handlers.ContainsKey(55),"Original XP option/handler contract changed");
  r.inputBarrel.orbInstancesBefore=Resources.FindObjectsOfTypeAll<ExperienceOrbBehavior>().Count(x=>x.gameObject.scene.IsValid());Check(r.inputBarrel.orbInstancesBefore==0,"Unowned XP orb present");
  Action<Interactor,IInteractable,GameObject> observed=(interactor,interactable,obj)=>{if(obj!=barrelObject)return;Check(interactor==driver.interactor&&ReferenceEquals(interactable,barrelComponent),"Original input interaction event identity differs");r.inputBarrel.interactions++;};Action<float> gold=amount=>r.inputBarrel.goldEvents+=amount;
  var original=(NetworkMessageDelegate)Delegate.CreateDelegate(typeof(NetworkMessageDelegate),typeof(ExperienceManager).GetMethod("HandleCreateExpEffect",BindingFlags.NonPublic|BindingFlags.Static));
  try{
   option.AttemptSetString("0");r.inputBarrel.xpSettingActive=option.GetString();r.inputBarrel.xpCosmeticsUnavailable=!option.value;Check(r.inputBarrel.xpCosmeticsUnavailable,"Original optional XP cosmetics must stay unavailable");
   activeBodyClient.RegisterHandler(55,msg=>{r.inputBarrel.xpMessages++;original(msg);var incoming=RewardField(typeof(ExperienceManager),"currentIncomingCreateExpEffectMessage").GetValue(null);var type=incoming.GetType();r.inputBarrel.xpDecoded=(GameObject)type.GetField("targetBody").GetValue(incoming)==player.gameObject&&(ulong)type.GetField("awardAmount").GetValue(incoming)==r.inputBarrel.source.experienceExpected&&Vector3.Distance((Vector3)type.GetField("origin").GetValue(incoming),barrelObject.transform.position)<.001f;Check(r.inputBarrel.xpDecoded,"Original XP message data differs");});
   var setup=PrepareOriginalBarrelClone(player,cfg,r.inputBarrel.source);while(setup.MoveNext())yield return setup.Current;
   pauseHost=new GameObject("Owned input-barrel original pause context");pauseHost.SetActive(false);pauseHost.AddComponent<NetworkIdentity>();var pause=pauseHost.AddComponent<PauseStopController>();pauseHost.SetActive(true);yield return null;yield return null;Call(activeBodyClient,"Update");Check(PauseStopController.instance==pause&&!pause.isPaused&&Time.timeScale==priorScale&&driver.interactor.maxInteractionDistance==3,"Original input pause/range changed");
   var collider=barrelModel.GetComponentsInChildren<Collider>().First(x=>x.enabled);bank.aimDirection=(collider.bounds.center-bank.aimOrigin).normalized;driver.enabled=true;float deadline=Time.realtimeSinceStartup+3;while(driver.currentInteractable!=barrelObject&&Time.realtimeSinceStartup<deadline){yield return new WaitForEndOfFrame();Call(activeBodyClient,"Update");}
   r.inputBarrel.selected=driver.currentInteractable==barrelObject&&requesters.Contains(driver)&&!barrelComponent.Networkopened;r.phase="original-input-barrel-selected";Save();Check(r.inputBarrel.selected,"Original input target selection failed");
   barrelCoinWitness=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/Effects/CoinEmitter");ownsBarrelCoinWitness=true;yield return barrelCoinWitness;Check(barrelCoinWitness.Status==AsyncOperationStatus.Succeeded&&barrelCoinWitness.Result==rewardPrefabs[0],"Original input coin witness failed");r.inputBarrel.coinReferencesBefore=barrelCoinBaseline=BarrelCoinReferences();hasBarrelCoinBaseline=true;
   GlobalEventManager.OnInteractionsGlobal+=observed;player.master.OnGoldCollected+=gold;
   var effect=ProbeOriginalClientCoin(player,true);while(effect.MoveNext())yield return effect.Current;
   r.inputBarrel.coinReferencesAfter=BarrelCoinReferences();r.inputBarrel.rewards=r.inputBarrel.interactions==1&&r.inputBarrel.goldEvents==r.inputBarrel.source.goldExpected&&r.inputBarrel.coin.rewardsMatched&&r.inputBarrel.xpMessages==1&&r.inputBarrel.xpDecoded&&r.inputBarrel.coinReferencesAfter==r.inputBarrel.coinReferencesBefore+1;r.inputBarrel.opened|=barrelMachine.state is EntityStates.Barrel.Opened;Check(r.inputBarrel.rewards&&r.inputBarrel.opening&&r.inputBarrel.opened&&barrelComponent.Networkopened,"Original input/opening/client/reward linkage incomplete");
   uint money=player.master.money;ulong xp=TeamManager.instance.GetTeamExperience(TeamIndex.Player);bank.interact.PushState(true);yield return new WaitForFixedUpdate();yield return new WaitForEndOfFrame();bank.interact.PushState(false);yield return null;bank.interact.PushState(false);Call(activeBodyClient,"Update");r.inputBarrel.repeatRejected=barrelComponent.GetInteractability(driver.interactor)==Interactability.Disabled&&r.inputBarrel.interactions==1&&r.inputBarrel.coin.messages==1&&r.inputBarrel.xpMessages==1&&money==player.master.money&&xp==TeamManager.instance.GetTeamExperience(TeamIndex.Player);Check(r.inputBarrel.repeatRejected,"Opened input barrel paid twice");
   foreach(var ownedCollider in barrelObject.GetComponentsInChildren<Collider>(true).Concat(barrelModel.GetComponentsInChildren<Collider>(true)).Distinct())ownedCollider.enabled=false;Physics.SyncTransforms();yield return new WaitForEndOfFrame();r.inputBarrel.selectionReleased=!driver.currentInteractable&&!requesters.Contains(driver);Check(r.inputBarrel.selectionReleased,"Original opened-target selection retained");
   r.inputBarrel.orbInstancesAfter=Resources.FindObjectsOfTypeAll<ExperienceOrbBehavior>().Count(x=>x.gameObject.scene.IsValid());Check(r.inputBarrel.orbInstancesAfter==r.inputBarrel.orbInstancesBefore&&!option.value,"Unavailable original XP cosmetics spawned an orb");
  }finally{GlobalEventManager.OnInteractionsGlobal-=observed;if(player&&player.master)player.master.OnGoldCollected-=gold;driver.enabled=false;bank.interact.PushState(false);bank.interact.PushState(false);bank.aimDirection=priorAim;activeBodyClient.UnregisterHandler(55);option.AttemptSetString(r.inputBarrel.xpSettingBefore);r.inputBarrel.xpSettingRestored=option.GetString();CleanupOriginalBarrel();if(pauseHost)NetworkServer.Destroy(pauseHost);}
  yield return null;yield return null;Call(activeBodyClient,"Update");r.inputBarrel.cleaned=!pauseHost&&!PauseStopController.instance&&!barrelObject&&!barrelModel&&!barrelTemplates&&!barrelPreview&&barrelMaterials.All(x=>!x)&&!ownsBarrelCoinWitness&&!driver.enabled&&!driver.currentInteractable&&!bank.interact.down&&!activeBodyClient.handlers.ContainsKey(55)&&requesters.Count==priorRequesters&&!requesters.Contains(driver)&&r.inputBarrel.xpSettingRestored==r.inputBarrel.xpSettingBefore&&option.defaultValue==r.inputBarrel.xpSettingDeclared&&Time.timeScale==priorScale;Check(r.inputBarrel.cleaned,"Owned input/target/pause/handler/option/reference cleanup incomplete");Save();
 }
}
