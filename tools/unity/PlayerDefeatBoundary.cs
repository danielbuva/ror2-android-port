using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Observe original fatal damage/death/ragdoll/lifetime; the lab provides content and a stopped-input screen.
public sealed partial class MovementBatchProbe {
 [Serializable] public class PlayerDefeatReport {public bool prefabLoaded,ragdollStarted,deathEntered,effectTargetMatched,effectDestroyed,bodyDestroyed,masterRetained,corpseObserved;public int deathEvents,effects,ragdollBodies,stateIndex;public float health,seconds,holdSeconds;public string state;}
 const string PlayerDeathPath="Prefabs/TemporaryVisualEffects/PlayerDeathEffect",PlayerDeathBundle="player-death-effect-lab";
 ResourceLocationMap playerDeathLocator;AsyncOperationHandle<GameObject> playerDeathHandle;GameObject playerDeathPrefab;
 readonly List<LocalCameraEffect> playerDeathEffects=new List<LocalCameraEffect>();CharacterBody observedDefeatBody;
 IEnumerator PreparePlayerDefeat(CharacterBody body,Result cfg){
  r.playerDefeat=new PlayerDefeatReport();Check(!Resources.FindObjectsOfTypeAll<LocalCameraEffect>().Any(x=>x.gameObject.scene.IsValid()),"Existing local death camera effects");
  var index=EntityStateCatalog.GetStateIndex(typeof(EntityStates.Commando.DeathState));Check(index!=EntityStateIndex.Invalid&&EntityStateCatalog.GetStateType(index)==typeof(EntityStates.Commando.DeathState),"Original player death state catalog identity missing");r.playerDefeat.stateIndex=(int)index;
  body.GetComponent<SfxLocator>().deathSound=""; // Original death explicitly skips an empty sound string; Android audio remains unavailable.
  string key;Check(LegacyResourcesAPI.GetGuid(PlayerDeathPath,out key)&&key==cfg.playerDeathEffectKey,"Measured original player death key mismatch");
  var bundle=new ResourceLocationBase(PlayerDeathBundle,System.IO.Path.Combine(Application.persistentDataPath,"payload",PlayerDeathBundle),typeof(AssetBundleProvider).FullName,typeof(IAssetBundleResource));bundle.Data=new AssetBundleRequestOptions{BundleName=PlayerDeathBundle};
  playerDeathLocator=new ResourceLocationMap("player-death-effect-probe");playerDeathLocator.Add(key,new ResourceLocationBase(key,cfg.playerDeathEffectAsset,typeof(BundledAssetProvider).FullName,typeof(GameObject),bundle));Addressables.AddResourceLocator(playerDeathLocator);
  playerDeathHandle=LegacyResourcesAPI.LoadAsync<GameObject>(PlayerDeathPath);float deadline=Time.realtimeSinceStartup+5;while(!playerDeathHandle.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;yield return null;
  Check(playerDeathHandle.IsDone&&playerDeathHandle.Status==AsyncOperationStatus.Succeeded&&LegacyResourcesAPI.ActiveCount==0,"Original player death effect provider failed");playerDeathPrefab=playerDeathHandle.Result;Check(playerDeathPrefab&&playerDeathPrefab.name=="PlayerDeathEffect"&&playerDeathPrefab.GetComponent<LocalCameraEffect>().effectRoot&&playerDeathPrefab.GetComponentsInChildren<Component>(true).All(x=>x),"Original player death effect serialized contract");r.playerDefeat.prefabLoaded=true;
  var model=body.modelLocator.modelTransform;var ragdoll=model.GetComponent<RagdollController>();Check(ragdoll&&ragdoll.bones.Length>0&&ragdoll.bones.All(x=>x&&x.GetComponent<Collider>()&&x.GetComponent<Rigidbody>()),"Original Commando ragdoll references missing");ragdoll.enabled=true;yield return null;
  Check(typeof(RagdollController).GetField("animator",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(ragdoll)==model.GetComponent<Animator>()&&ragdoll.bones.All(x=>x.GetComponent<Rigidbody>().isKinematic&&!x.GetComponent<Collider>().enabled),"Original ragdoll Start/cache/isolation failed");r.playerDefeat.ragdollStarted=true;
  observedDefeatBody=body;GlobalEventManager.onCharacterDeathGlobal+=ObservePlayerDeathEvent;Save();
 }
 void ObservePlayerDeathEvent(DamageReport report){if(report.victimBody==observedDefeatBody)r.playerDefeat.deathEvents++;}
 IEnumerator ObservePlayerDefeat(CharacterBody body,EntityStateMachine machine,NovaInputBridge bridge){
  Check(body&&!body.healthComponent.alive&&r.playerDefeat!=null,"Original fatal player damage missing");r.playerDefeat.health=body.healthComponent.health;
  if(r.integratedWorld&&r.world!=null){r.world.health=r.playerDefeat.health;r.world.target="";r.world.objective="Commando defeated";}
  var playerRoot=body.gameObject;var master=body.master;bridge.enabled=false;r.phase="commando-death";Save();float began=Time.realtimeSinceStartup;
  while(Time.realtimeSinceStartup-began<8){
   foreach(var effect in Resources.FindObjectsOfTypeAll<LocalCameraEffect>().Where(x=>x.gameObject.scene.IsValid()&&x.targetCharacter==playerRoot))if(!playerDeathEffects.Contains(effect)){playerDeathEffects.Add(effect);r.playerDefeat.effects++;r.playerDefeat.effectTargetMatched=true;}
   if(body&&machine&&machine.state is EntityStates.Commando.DeathState){r.playerDefeat.deathEntered=true;r.playerDefeat.state=machine.state.GetType().FullName;Check(!body.characterMotor.enabled,"Original death did not disable character motor");}
   if(ownedDetachedModel)r.playerDefeat.ragdollBodies=Math.Max(r.playerDefeat.ragdollBodies,ownedDetachedModel.GetComponentsInChildren<Rigidbody>(true).Count(x=>!x.isKinematic));
   r.playerDefeat.bodyDestroyed=!body;r.playerDefeat.effectDestroyed=playerDeathEffects.Count==1&&playerDeathEffects.All(x=>!x);r.playerDefeat.masterRetained=master&&!master.GetBody();r.playerDefeat.corpseObserved|=!body&&ownedDetachedModel&&ownedDetachedModel.GetComponent<Corpse>();r.playerDefeat.seconds=Time.realtimeSinceStartup-began;ObserveEnemy();Save();
   if(r.playerDefeat.bodyDestroyed&&r.playerDefeat.effectDestroyed)break;yield return null;
  }
  Check(r.playerDefeat.deathEvents==1&&r.playerDefeat.deathEntered&&r.playerDefeat.effects==1&&r.playerDefeat.effectTargetMatched&&r.playerDefeat.effectDestroyed&&r.playerDefeat.bodyDestroyed&&r.playerDefeat.masterRetained&&r.playerDefeat.ragdollBodies>0,"Original player death/ragdoll/effect/natural body lifetime incomplete");
  if(r.results!=null&&r.results.ready){var ending=Enumerable.Range(0,GameEndingCatalog.endingCount).Select(x=>GameEndingCatalog.GetGameEndingDef((GameEndingIndex)x)).Single(x=>x.cachedName=="StandardLoss");Check(!ending.isWin,"Original defeat ending is a victory");Run.instance.BeginGameOver(ending);float deadline=Time.realtimeSinceStartup+5;while(!r.results.persisted&&Time.realtimeSinceStartup<deadline){Call(activeBodyClient,"Update");ObserveIntegratedResults();yield return null;}Check(r.results.persisted&&r.results.clientEnding,"Original defeat report/client/persistence incomplete");}
  GlobalEventManager.onCharacterDeathGlobal-=ObservePlayerDeathEvent;r.phase="commando-defeated";Save();
  // Restart waits for original death/body lifetime, then uses the full session teardown.
  while(r.freePlay&&!restartRequested){r.playerDefeat.holdSeconds+=Time.unscaledDeltaTime;if(Time.frameCount%30==0)Save();yield return null;}
 }
 IEnumerator CleanupPlayerDeathEffect(){
  GlobalEventManager.onCharacterDeathGlobal-=ObservePlayerDeathEvent;if(playerDeathLocator==null)yield break;
  foreach(var effect in playerDeathEffects)if(effect)Destroy(effect.gameObject);yield return null;Check(playerDeathEffects.All(x=>!x),"Player death effects survived owned cleanup");
  for(int i=0;i<playerDeathEffects.Count;i++)Addressables.Release(playerDeathPrefab);if(playerDeathHandle.IsValid())Addressables.Release(playerDeathHandle);yield return null;
  Check(!AssetBundle.GetAllLoadedAssetBundles().Any(x=>x.name==PlayerDeathBundle),"Player death provider bundle retained");Addressables.RemoveResourceLocator(playerDeathLocator);playerDeathLocator=null;
 }
}
