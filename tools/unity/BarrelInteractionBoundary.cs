using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

// Configures/observes an owned source prefab; all query, interaction, state and reward code is original.
public sealed partial class MovementBatchProbe {
 [Serializable] public class BarrelReport {
  public bool sourceReady,queryMatched,serverDispatched,opening,opened,repeatRejected,cleaned;
  public int sourceGold,goldExpected,interactions,stateIndex,renderers,colliders,pendingAwards,coinReferencesBefore,coinReferencesAfter;public uint sourceExperience,experienceExpected,moneyBefore,moneyAfter,netId;
  public ulong experienceBefore,experienceAfter;public float difficulty,goldEvents,openingSeconds,experienceSeconds,experienceFirstSeconds,experienceExpectedSeconds;public string state,scope;
 }
 GameObject barrelTemplates,barrelObject;Transform barrelModel;BarrelInteraction barrelComponent;EntityStateMachine barrelMachine;
 readonly List<Material> barrelMaterials=new List<Material>();CharacterMaster barrelPlayer;bool observesBarrel,ownsBarrelCoinWitness,hasBarrelCoinBaseline;AsyncOperationHandle<GameObject> barrelCoinWitness;
 void BarrelGold(float amount){r.barrel.goldEvents+=amount;}
 void BarrelInteracted(Interactor interactor,IInteractable interactable,GameObject obj){if(obj==barrelObject){Check(interactor.GetComponent<CharacterBody>().master==barrelPlayer&&ReferenceEquals(interactable,barrelComponent),"Original barrel interaction event identity changed");r.barrel.interactions++;}}
 IEnumerator ProbeOriginalBarrel(CharacterBody player,Result cfg){
  r.barrel=new BarrelReport{scope="Original cash-barrel query/server interaction/Opening/Opened/gold/timed XP; manually placed owned source clone, explicit no audio/diagnostic materials. No original InteractionDriver/physical/client/purchase/item/drop-table/stage progression proof."};r.phase="original-barrel-prepare";Save();
  Check(NetworkServer.active&&!NetworkClient.active&&Run.instance&&r.runClock.cleaned==false&&ExperienceManager.instance,"Accepted server clock/reward context required");
  var source=artifactBundle.LoadAsset<GameObject>(cfg.barrelAsset);Check(source&&source.name=="Barrel1"&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original barrel prefab/reference contract missing");
  var original=source.GetComponent<BarrelInteraction>();Check(original&&original.goldReward==8&&original.expReward==4,"Original source barrel rewards changed");r.barrel.sourceGold=original.goldReward;r.barrel.sourceExperience=original.expReward;
  barrelTemplates=new GameObject("Owned inactive barrel staging");barrelTemplates.SetActive(false);barrelObject=Instantiate(source,barrelTemplates.transform);barrelObject.name=source.name;
  var allowed=new[]{typeof(NetworkIdentity),typeof(NetworkStateMachine),typeof(EntityStateMachine),typeof(BarrelInteraction),typeof(ModelLocator),typeof(EntityLocator),typeof(ChildLocator),typeof(PingInfoProvider)};
  foreach(var behaviour in barrelObject.GetComponentsInChildren<MonoBehaviour>(true))behaviour.enabled=allowed.Contains(behaviour.GetType());
  // Only the owned clone omits native audio. Original Opening sees no SfxLocator; no fake middleware success.
  var sound=barrelObject.GetComponent<SfxLocator>();Check(sound,"Original barrel sound component absent");DestroyImmediate(sound);
  var model=barrelObject.GetComponent<ModelLocator>();Check(model&&model.modelTransform,"Original barrel model binding missing");barrelModel=model.modelTransform;
  var shader=Resources.Load<Shader>("StageSurfacePreview");Check(shader&&shader.isSupported,"Accepted diagnostic material shader unavailable");
  foreach(var renderer in barrelObject.GetComponentsInChildren<Renderer>(true)){
   var copies=renderer.sharedMaterials.Select(material=>{Check(material,"Original barrel material missing");var copy=new Material(material);copy.shader=shader;barrelMaterials.Add(copy);return copy;}).ToArray();renderer.sharedMaterials=copies;r.barrel.renderers++;
  }
  foreach(var collider in barrelObject.GetComponentsInChildren<Collider>(true)){collider.enabled=true;r.barrel.colliders++;}
  Check(r.barrel.renderers>0&&r.barrel.colliders>0,"Original barrel display/collision absent");
  barrelObject.transform.position=player.characterMotor.Motor.TransientPosition+Vector3.right*2;barrelComponent=barrelObject.GetComponent<BarrelInteraction>();barrelMachine=barrelObject.GetComponent<EntityStateMachine>();Check(barrelMachine&&barrelMachine.initialStateType.stateType==typeof(Idle),"Original barrel initial state changed");
  r.barrel.difficulty=Run.instance.difficultyCoefficient;r.barrel.goldExpected=(int)(r.barrel.sourceGold*r.barrel.difficulty);r.barrel.experienceExpected=(uint)(r.barrel.sourceExperience*r.barrel.difficulty);
  barrelObject.transform.SetParent(null,true);barrelObject.SetActive(true);NetworkServer.Spawn(barrelObject);Physics.SyncTransforms();yield return null;yield return null;
  r.barrel.netId=barrelObject.GetComponent<NetworkIdentity>().netId.Value;r.barrel.stateIndex=(int)EntityStateCatalog.GetStateIndex(barrelMachine.state.GetType());
  r.barrel.sourceReady=r.barrel.netId!=0&&barrelComponent.goldReward==r.barrel.goldExpected&&barrelComponent.expReward==r.barrel.experienceExpected&&barrelMachine.state is Idle;
  Check(r.barrel.sourceReady,"Original natural barrel Start/network/state contract failed");
  var interactor=player.GetComponent<Interactor>();Check(interactor&&barrelComponent.GetInteractability(interactor)==Interactability.Available,"Original body interactor/available barrel missing");
  var colliders=barrelModel.GetComponentsInChildren<Collider>(true);Check(colliders.Any(x=>x.enabled),"Original detached barrel model collider missing");var target=colliders.First(x=>x.enabled).bounds.center;
  var origin=player.corePosition;var found=interactor.FindBestInteractableObject(new Ray(origin,(target-origin).normalized),Vector3.Distance(origin,target)+2,origin,4);
  r.barrel.queryMatched=found==barrelObject;Check(r.barrel.queryMatched,"Original Interactor query did not select recovered barrel");
  barrelPlayer=player.master;r.barrel.moneyBefore=barrelPlayer.money;r.barrel.experienceBefore=TeamManager.instance.GetTeamExperience(TeamIndex.Player);
  // Freeze the already-verified enemy reward observation before starting this independent reward phase.
  rewardPlayerMaster.OnGoldCollected-=RewardGold;barrelPlayer.OnGoldCollected+=BarrelGold;GlobalEventManager.OnInteractionsGlobal+=BarrelInteracted;observesBarrel=true;
  barrelCoinWitness=LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/Effects/CoinEmitter");ownsBarrelCoinWitness=true;yield return barrelCoinWitness;Check(barrelCoinWitness.Status==AsyncOperationStatus.Succeeded&&barrelCoinWitness.Result==rewardPrefabs[0]&&LegacyResourcesAPI.ActiveCount==0,"Original coin-reference witness failed");r.barrel.coinReferencesBefore=BarrelCoinReferences();hasBarrelCoinBaseline=true;
  float began=Time.realtimeSinceStartup;interactor.AttemptInteraction(found);r.barrel.coinReferencesAfter=BarrelCoinReferences();Check(r.barrel.coinReferencesAfter==r.barrel.coinReferencesBefore+1,"Original CoinDrop acquisition count changed");r.barrel.serverDispatched=barrelComponent.Networkopened&&r.barrel.interactions==1;Check(r.barrel.serverDispatched,"Original server interaction dispatch/open flag failed");
  var pending=(IList)typeof(ExperienceManager).GetField("pendingAwards",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(rewardExperience);float managerTime=(float)typeof(ExperienceManager).GetField("localTime",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(rewardExperience);ulong queued=0;
  r.barrel.pendingAwards=pending.Count;foreach(var award in pending){var type=award.GetType();queued+=(ulong)type.GetField("awardAmount").GetValue(award);Check((TeamIndex)type.GetField("recipient").GetValue(award)==TeamIndex.Player,"Original barrel queued XP recipient changed");r.barrel.experienceExpectedSeconds=Mathf.Max(r.barrel.experienceExpectedSeconds,(float)type.GetField("awardTime").GetValue(award)-managerTime);}
  Check(r.barrel.pendingAwards>1&&queued==r.barrel.experienceExpected&&TeamManager.instance.GetTeamExperience(TeamIndex.Player)==r.barrel.experienceBefore,"Original barrel multi-installment XP queue incomplete");
  r.phase="original-barrel-opening";Save();float deadline=began+5;
  while(Time.realtimeSinceStartup<deadline){
   yield return new WaitForEndOfFrame();ObserveOriginalRunClock();r.barrel.state=barrelMachine.state.GetType().FullName;r.barrel.opening|=barrelMachine.state is EntityStates.Barrel.Opening;
   if(barrelMachine.state is EntityStates.Barrel.Opened&&!r.barrel.opened){r.barrel.opened=true;r.barrel.openingSeconds=Time.realtimeSinceStartup-began;}
   r.barrel.moneyAfter=barrelPlayer.money;r.barrel.experienceAfter=TeamManager.instance.GetTeamExperience(TeamIndex.Player);
   if(r.barrel.experienceAfter>r.barrel.experienceBefore&&r.barrel.experienceFirstSeconds==0)r.barrel.experienceFirstSeconds=Time.realtimeSinceStartup-began;
   if(r.barrel.experienceAfter-r.barrel.experienceBefore==r.barrel.experienceExpected&&r.barrel.experienceSeconds==0)r.barrel.experienceSeconds=Time.realtimeSinceStartup-began;
   Save();if(r.barrel.opened&&r.barrel.experienceAfter-r.barrel.experienceBefore==r.barrel.experienceExpected)break;
  }
  Check(r.barrel.opening&&r.barrel.opened&&r.barrel.openingSeconds>=EntityStates.Barrel.Opening.duration&&r.barrel.openingSeconds<2,"Original barrel timed state transition incomplete");
  Check(r.barrel.moneyAfter-r.barrel.moneyBefore==r.barrel.goldExpected&&r.barrel.goldEvents==r.barrel.goldExpected&&r.barrel.experienceAfter-r.barrel.experienceBefore==r.barrel.experienceExpected&&r.barrel.experienceFirstSeconds<r.barrel.experienceSeconds&&Mathf.Abs(r.barrel.experienceSeconds-r.barrel.experienceExpectedSeconds)<.1f,"Original barrel gold/timed XP delivery incomplete");
  interactor.AttemptInteraction(barrelObject);yield return null;
  r.barrel.repeatRejected=barrelComponent.GetInteractability(interactor)==Interactability.Disabled&&r.barrel.interactions==1&&barrelPlayer.money==r.barrel.moneyAfter&&TeamManager.instance.GetTeamExperience(TeamIndex.Player)==r.barrel.experienceAfter;
  Check(r.barrel.repeatRejected,"Opened barrel paid twice or remained interactable");CleanupOriginalBarrel();yield return null;yield return null;
  r.barrel.cleaned=!barrelObject&&!barrelTemplates&&!barrelModel&&barrelMaterials.All(x=>!x);Check(r.barrel.cleaned,"Owned barrel/model/material teardown incomplete");Save();
 }
 int BarrelCoinReferences(){return (int)typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(barrelCoinWitness);}
 void CleanupOriginalBarrel(){
  if(observesBarrel){GlobalEventManager.OnInteractionsGlobal-=BarrelInteracted;if(barrelPlayer)barrelPlayer.OnGoldCollected-=BarrelGold;observesBarrel=false;}
  if(barrelObject){if(NetworkServer.active)NetworkServer.Destroy(barrelObject);else Destroy(barrelObject);}if(barrelTemplates)Destroy(barrelTemplates);
  foreach(var material in barrelMaterials)if(material)Destroy(material);
  if(ownsBarrelCoinWitness){if(barrelCoinWitness.IsValid()){if(hasBarrelCoinBaseline){int extra=BarrelCoinReferences()-r.barrel.coinReferencesBefore;Check(extra==0||extra==1,"Unowned coin acquisition during barrel teardown");if(extra==1)Addressables.Release(barrelCoinWitness.Result);}Addressables.Release(barrelCoinWitness);}barrelCoinWitness=default;ownsBarrelCoinWitness=false;hasBarrelCoinBaseline=false;}
 }
}
