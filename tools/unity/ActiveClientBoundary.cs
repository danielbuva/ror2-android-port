using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Actual local HLAPI client and original authority callbacks, with no platform/user session.
public sealed partial class MovementBatchProbe {
 [Serializable] public class ActiveClientReport {
  public bool grounded,serializers,ready,bodyMapped,masterMapped,localAuthority,ownerMatched,effectiveAuthority,skillsAuthority,removed,cleaned,clientSceneCleaned;
  public bool masterAuthorityBefore,masterLocalPlayerAuthority,masterLocalAuthority,masterOwnerMatched,masterAuthorityRemoved;
  public int identities,behaviours,trackerAllocations,skillCacheInitializations,connectEvents,frames,fixedTicks,syringeCount;public uint bodyId,masterId;
  public float seconds,fixedSeconds,stateSeconds,healthBefore,healthAfter;public string scope,serializing;
  public List<string> serializerTypes=new List<string>();
 }
 NetworkClient activeBodyClient;NetworkConnection activeBodyOwner;NetworkIdentity activeOwnedBody,activeOwnedMaster;bool ownsActiveClientScene;
 void CheckActiveClientSerializers(){
  Check(RoR2.EntitlementManagement.EntitlementCatalog.entitlementDefs.Length==0&&LocalUserManager.readOnlyLocalUsersList.Count==0,"Diagnostic absent-user/catalog scope changed");
  foreach(var identity in NetworkServer.objects.Values.Where(x=>x).ToArray()){
   var skills=identity.GetComponent<SkillLocator>();if(skills){if(skills.AllSkills==null){Call(skills,"Awake");r.activeClient.skillCacheInitializations++;}Check(skills.AllSkills.SequenceEqual(identity.GetComponents<GenericSkill>())&&skills.AllSkills.Length>=(r.integratedWorld?1:4)&&ReferenceEquals(typeof(SkillLocator).GetField("networkIdentity",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(skills),identity),"Original active skill serializer cache mismatch");}
   var tracker=identity.GetComponent<PlayerCharacterMasterControllerEntitlementTracker>();
   if(tracker){var controller=tracker.GetComponent<PlayerCharacterMasterController>();Check(controller&&!controller.networkUser,"Unexpected platform/user-linked master");var field=typeof(PlayerCharacterMasterControllerEntitlementTracker).GetField("entitlementsSet",BindingFlags.Instance|BindingFlags.NonPublic);var values=(bool[])field.GetValue(tracker);if(values==null){Call(tracker,"Awake");r.activeClient.trackerAllocations++;values=(bool[])field.GetValue(tracker);}Call(tracker,"UpdateEntitlementsServer");Check(values!=null&&values.Length==0&&ReferenceEquals(values,field.GetValue(tracker))&&!controller.networkUser,"Original absent-user tracker allocation changed");}
   var behaviours=(NetworkBehaviour[])typeof(NetworkIdentity).GetField("m_NetworkBehaviours",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(identity);Check(behaviours!=null,"Original cached serializer list missing");var writer=new NetworkWriter();
   foreach(var behaviour in behaviours){r.activeClient.serializing=behaviour.GetType().FullName;Save();try{behaviour.OnSerialize(writer,true);}catch(Exception e){throw new Exception("Active-client original serializer "+r.activeClient.serializing,e);}r.activeClient.behaviours++;r.activeClient.serializerTypes.Add(r.activeClient.serializing);}
   r.activeClient.identities++;
  }
  Check(r.activeClient.identities>=2&&r.activeClient.behaviours>0,"Original active body/master serializers not observed");r.activeClient.serializers=true;Save();
 }
 IEnumerator ConnectActiveBodyClient(CharacterBody player){
  if(r.activeClient==null)r.activeClient=new ActiveClientReport();
  var identity=player.networkIdentity;Check(identity.localPlayerAuthority&&!identity.hasAuthority&&identity.clientAuthorityOwner==null&&player.hasEffectiveAuthority,"Original pre-client authority configuration changed");CheckActiveClientSerializers();
  NetworkServer.RegisterHandler(MsgType.Connect,msg=>{});NetworkServer.RegisterHandler(MsgType.Disconnect,msg=>{});
  r.phase="active-local-client-ready";Save();ownsActiveClientScene=true;activeBodyClient=ClientScene.ConnectLocalServer();activeBodyClient.RegisterHandler(MsgType.Connect,msg=>r.activeClient.connectEvents++);activeBodyClient.RegisterHandler(MsgType.Disconnect,msg=>{});Call(activeBodyClient,"Update");
  Check(activeBodyClient.isConnected&&r.activeClient.connectEvents==1&&NetworkServer.localConnections.Count==1,"Original active local connection failed");Check(ClientScene.Ready(activeBodyClient.connection),"Original active local readiness failed");Call(activeBodyClient,"Update");activeBodyOwner=NetworkServer.localConnections[0];
  r.activeClient.bodyId=identity.netId.Value;r.activeClient.masterId=player.master.netId.Value;r.activeClient.ready=activeBodyOwner.isReady&&activeBodyClient.connection.isReady;r.activeClient.bodyMapped=player.isClient&&ClientScene.FindLocalObject(identity.netId)==player.gameObject;r.activeClient.masterMapped=player.master.isClient&&ClientScene.FindLocalObject(player.master.netId)==player.master.gameObject;Check(r.activeClient.ready&&r.activeClient.bodyMapped&&r.activeClient.masterMapped,"Original active client registry mapping failed");
  Check(identity.AssignClientAuthority(activeBodyOwner),"Original active client ownership rejected");activeOwnedBody=identity;Call(activeBodyClient,"Update");
  r.activeClient.localAuthority=identity.hasAuthority&&player.hasAuthority;r.activeClient.ownerMatched=identity.clientAuthorityOwner==activeBodyOwner;r.activeClient.effectiveAuthority=player.hasEffectiveAuthority&&player.characterMotor.hasEffectiveAuthority;r.activeClient.skillsAuthority=(bool)typeof(SkillLocator).GetField("hasEffectiveAuthority",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(player.skillLocator);Check(r.activeClient.localAuthority&&r.activeClient.ownerMatched&&r.activeClient.effectiveAuthority&&r.activeClient.skillsAuthority,"Original active authority callbacks incomplete");
  if(r.recoveredHudEnabled){
   // Original pickup notifications require the actual master, as well as its
   // body, to belong to the local connection. Preserve the source prefab flag.
   var masterIdentity=player.master.networkIdentity;r.activeClient.masterAuthorityBefore=masterIdentity.hasAuthority;r.activeClient.masterLocalPlayerAuthority=masterIdentity.localPlayerAuthority;
   Check(masterIdentity.localPlayerAuthority&&!masterIdentity.hasAuthority&&masterIdentity.clientAuthorityOwner==null,"Unowned original master authority before HUD integration");
   Check(masterIdentity.AssignClientAuthority(activeBodyOwner),"Original local master ownership rejected");activeOwnedMaster=masterIdentity;Call(activeBodyClient,"Update");
   r.activeClient.masterLocalAuthority=masterIdentity.hasAuthority&&player.master.hasAuthority;r.activeClient.masterOwnerMatched=masterIdentity.clientAuthorityOwner==activeBodyOwner;
   Check(r.activeClient.masterLocalAuthority&&r.activeClient.masterOwnerMatched&&player.master.hasEffectiveAuthority,"Original local master authority callbacks incomplete");
  }
  yield return null;
 }
 IEnumerator ProbeActiveBodyClient(CharacterBody player,Result cfg){
  r.activeClient=new ActiveClientReport{scope="Actual loopback local HLAPI client, original active Commando/master mapping, raw client authority callbacks and neutral ticking/teardown. No NetworkUser/LocalUser/platform session/entitlement grant, InteractionDriver/client effects/remote peers/full startup acceptance."};r.phase="active-client-serializers";Save();
  Check(r.moneyCost.paid&&r.moneyCost.cleaned&&NetworkServer.active&&!NetworkClient.active&&NetworkClient.allClients.Count==0&&player.gameObject.activeInHierarchy&&player.master.hasBody&&player.master.GetBody()==player,"Accepted active actor/server context changed");
  var connect=ConnectActiveBodyClient(player);while(connect.MoveNext())yield return connect.Current;var identity=player.networkIdentity;
  if(cfg.originalInteractionSelection){var selection=ProbeOriginalInteractionSelection(player,cfg);while(selection.MoveNext())yield return selection.Current;}
  if(cfg.originalClientCoin){var coin=ProbeOriginalClientCoin(player);while(coin.MoveNext())yield return coin.Current;}
  if(cfg.originalInputBarrel){var input=ProbeOriginalInputBarrel(player,cfg);while(input.MoveNext())yield return input.Current;}
  if(cfg.originalChestDropTable){var drops=ProbeOriginalChestDropTable(player,cfg);while(drops.MoveNext())yield return drops.Current;}
  if(cfg.originalChestPurchase&&!cfg.originalChestEjection){var chest=ProbeOriginalChestPurchase(player,cfg);while(chest.MoveNext())yield return chest.Current;}
  if(cfg.originalPickupDropletLoad){var droplet=ProbeOriginalPickupDropletLoad(player,cfg);while(droplet.MoveNext())yield return droplet.Current;}
  if(cfg.originalDefaultPickup){var pickup=ProbeOriginalDefaultPickup(player,cfg);while(pickup.MoveNext())yield return pickup.Current;}
  r.phase="active-local-client-owned";Save();yield return null;yield return new WaitForEndOfFrame();var state=EntityStateMachine.FindByCustomName(player.gameObject,"Body").state;Check(state is EntityStates.GenericCharacterMain,"Original neutral state changed");float began=Time.realtimeSinceStartup,fixedBegan=Run.FixedTimeStamp.now.t,stateBegan=SpawnedStateAge(state,"fixedAge");r.activeClient.healthBefore=player.healthComponent.health;int fixedTickBegan=r.runClock.fixedTicks;
  while(Time.realtimeSinceStartup-began<60){yield return null;Call(activeBodyClient,"Update");ObserveOriginalRunClock();r.activeClient.frames++;r.activeClient.seconds=Time.realtimeSinceStartup-began;r.activeClient.fixedSeconds=Run.FixedTimeStamp.now.t-fixedBegan;r.activeClient.stateSeconds=SpawnedStateAge(state,"fixedAge")-stateBegan;Check(activeBodyClient.isConnected&&activeBodyOwner.isReady&&identity.hasAuthority&&identity.clientAuthorityOwner==activeBodyOwner&&player.hasEffectiveAuthority&&player.characterMotor.hasEffectiveAuthority&&player.master.GetBody()==player&&player.healthComponent.alive&&EntityStateMachine.FindByCustomName(player.gameObject,"Body").state==state&&!player.master.playerCharacterMasterController.networkUser&&LocalUserManager.readOnlyLocalUsersList.Count==0,"Active original client/actor lifetime contract changed");if(Time.frameCount%30==0)Save();}
  r.activeClient.healthAfter=player.healthComponent.health;r.activeClient.fixedTicks=r.runClock.fixedTicks-fixedTickBegan;r.activeClient.grounded=player.characterMotor.isGrounded;r.activeClient.syringeCount=player.inventory.GetItemCountPermanent(RoR2Content.Items.Syringe);Check(r.activeClient.seconds>=60&&r.activeClient.frames>1000&&r.activeClient.grounded&&r.activeClient.syringeCount==1,"Original active-client actor/inventory hold incomplete");Check(Mathf.Abs(r.activeClient.fixedSeconds-r.activeClient.fixedTicks*Time.fixedDeltaTime)<.03f&&Mathf.Abs(r.activeClient.stateSeconds-r.activeClient.fixedSeconds)<.03f,"Original active-client fixed callback/state intervals differ");Check(Mathf.Abs(r.activeClient.fixedSeconds-r.activeClient.seconds)<.3f&&Mathf.Abs(r.activeClient.stateSeconds-r.activeClient.seconds)<.3f,"Original active-client fixed/wall intervals differ");
  CleanupActiveBodyClient();yield return null;yield return null;r.activeClient.cleaned=!NetworkClient.active&&NetworkClient.allClients.Count==0&&NetworkServer.localConnections.Count==0&&NetworkServer.active&&player&&player.master.GetBody()==player&&NetworkServer.FindLocalObject(identity.netId)==player.gameObject;Check(r.activeClient.removed&&r.activeClient.cleaned,"Owned local client cleanup damaged server actor or retained client");Save();
 }
 void CleanupActiveBodyClient(){
  if(activeOwnedMaster&&activeBodyOwner!=null){Check(activeOwnedMaster.RemoveClientAuthority(activeBodyOwner),"Original master authority removal rejected");if(activeBodyClient!=null)Call(activeBodyClient,"Update");r.activeClient.masterAuthorityRemoved=activeOwnedMaster.clientAuthorityOwner==null&&!activeOwnedMaster.hasAuthority;Check(r.activeClient.masterAuthorityRemoved,"Original master authority removal incomplete");activeOwnedMaster=null;}
  if(activeOwnedBody&&activeBodyOwner!=null){Check(activeOwnedBody.RemoveClientAuthority(activeBodyOwner),"Original active authority removal rejected");if(activeBodyClient!=null)Call(activeBodyClient,"Update");r.activeClient.removed=activeOwnedBody.clientAuthorityOwner==null&&!activeOwnedBody.hasAuthority;Check(r.activeClient.removed,"Original active authority removal incomplete");activeOwnedBody=null;}
  if(activeBodyClient!=null){activeBodyClient.Disconnect();activeBodyClient.Shutdown();activeBodyClient=null;activeBodyOwner=null;}
 }
 void FinishActiveClientSceneCleanup(){if(!ownsActiveClientScene)return;Check(!NetworkServer.active&&!NetworkClient.active,"Shared transport must outlive owned server teardown");StaticCall(typeof(ClientScene),"Shutdown");r.activeClient.clientSceneCleaned=ClientScene.readyConnection==null&&!ClientScene.FindLocalObject(new NetworkInstanceId(r.activeClient.bodyId))&&!ClientScene.FindLocalObject(new NetworkInstanceId(r.activeClient.masterId));Check(r.activeClient.clientSceneCleaned,"Owned local client scene mapping retained");ownsActiveClientScene=false;}
}
