// Subsystem: session (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup ConnectActiveBodyClient (ActiveClientSession); teardown CleanupActiveBodyClient (Dispose), then FinishActiveClientSceneCleanup after server shutdown.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Actual local HLAPI client and original authority callbacks, with no platform/user session.
public sealed partial class PortSession {
 [Serializable] public class ActiveClientReport {
  public bool grounded,serializers,ready,bodyMapped,masterMapped,localAuthority,ownerMatched,effectiveAuthority,skillsAuthority,removed,cleaned,clientSceneCleaned;
  public bool masterAuthorityBefore,masterLocalPlayerAuthority,masterLocalAuthority,masterOwnerMatched,masterAuthorityRemoved;
  public int identities,behaviours,trackerAllocations,skillCacheInitializations,connectEvents,frames,fixedTicks,syringeCount;public uint bodyId,masterId;
  public float seconds,fixedSeconds,stateSeconds,healthBefore,healthAfter;public string scope,serializing;
  public List<string> serializerTypes=new List<string>();
 }
 NetworkClient activeBodyClient;NetworkConnection activeBodyOwner;
 ActiveClientSession activeClientSession;
 ActiveClientSession GetActiveClientSession(){if(activeClientSession==null)activeClientSession=new ActiveClientSession(this);return activeClientSession;}
 void CheckActiveClientSerializers(){GetActiveClientSession().CheckActiveClientSerializers();}
 IEnumerator ConnectActiveBodyClient(CharacterBody player){return GetActiveClientSession().ConnectActiveBodyClient(player);}
 IEnumerator ProbeActiveBodyClient(CharacterBody player,SessionConfig cfg){return GetActiveClientSession().ProbeActiveBodyClient(player,cfg);}
 void CleanupActiveBodyClient(){GetActiveClientSession().Dispose();}
 void FinishActiveClientSceneCleanup(){GetActiveClientSession().FinishActiveClientSceneCleanup();}

 // Create on first use and retain across cleanup. Dispose removes authority and
 // stops the client only; scene cleanup stays after the coordinator's server shutdown.
 sealed class ActiveClientSession : IDisposable {
  readonly PortSession coordinator;
  NetworkIdentity activeOwnedBody,activeOwnedMaster;bool ownsActiveClientScene;
  public ActiveClientSession(PortSession coordinator){this.coordinator=coordinator;}
  public void CheckActiveClientSerializers(){
   coordinator.Check(RoR2.EntitlementManagement.EntitlementCatalog.entitlementDefs.Length==0&&LocalUserManager.readOnlyLocalUsersList.Count==0,"Diagnostic absent-user/catalog scope changed");
   foreach(var identity in NetworkServer.objects.Values.Where(x=>x).ToArray()){
    var skills=identity.GetComponent<SkillLocator>();if(skills){if(skills.AllSkills==null){Call(skills,"Awake");coordinator.r.activeClient.skillCacheInitializations++;}coordinator.Check(skills.AllSkills.SequenceEqual(identity.GetComponents<GenericSkill>())&&skills.AllSkills.Length>=(coordinator.r.integratedWorld?1:4)&&ReferenceEquals(typeof(SkillLocator).GetField("networkIdentity",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(skills),identity),"Original active skill serializer cache mismatch");}
    var tracker=identity.GetComponent<PlayerCharacterMasterControllerEntitlementTracker>();
    if(tracker){var controller=tracker.GetComponent<PlayerCharacterMasterController>();coordinator.Check(controller&&!controller.networkUser,"Unexpected platform/user-linked master");var field=typeof(PlayerCharacterMasterControllerEntitlementTracker).GetField("entitlementsSet",BindingFlags.Instance|BindingFlags.NonPublic);var values=(bool[])field.GetValue(tracker);if(values==null){Call(tracker,"Awake");coordinator.r.activeClient.trackerAllocations++;values=(bool[])field.GetValue(tracker);}Call(tracker,"UpdateEntitlementsServer");coordinator.Check(values!=null&&values.Length==0&&ReferenceEquals(values,field.GetValue(tracker))&&!controller.networkUser,"Original absent-user tracker allocation changed");}
    var behaviours=(NetworkBehaviour[])typeof(NetworkIdentity).GetField("m_NetworkBehaviours",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(identity);coordinator.Check(behaviours!=null,"Original cached serializer list missing");var writer=new NetworkWriter();
    foreach(var behaviour in behaviours){coordinator.r.activeClient.serializing=behaviour.GetType().FullName;coordinator.Save();try{behaviour.OnSerialize(writer,true);}catch(Exception e){throw new Exception("Active-client original serializer "+coordinator.r.activeClient.serializing,e);}coordinator.r.activeClient.behaviours++;coordinator.r.activeClient.serializerTypes.Add(coordinator.r.activeClient.serializing);}
    coordinator.r.activeClient.identities++;
   }
   coordinator.Check(coordinator.r.activeClient.identities>=2&&coordinator.r.activeClient.behaviours>0,"Original active body/master serializers not observed");coordinator.r.activeClient.serializers=true;coordinator.Save();
  }
  public IEnumerator ConnectActiveBodyClient(CharacterBody player){
   if(coordinator.r.activeClient==null)coordinator.r.activeClient=new ActiveClientReport();
   var identity=player.networkIdentity;coordinator.Check(identity.localPlayerAuthority&&!identity.hasAuthority&&identity.clientAuthorityOwner==null&&player.hasEffectiveAuthority,"Original pre-client authority configuration changed");CheckActiveClientSerializers();
   NetworkServer.RegisterHandler(MsgType.Connect,msg=>{});NetworkServer.RegisterHandler(MsgType.Disconnect,msg=>{});
   coordinator.r.phase="active-local-client-ready";coordinator.Save();ownsActiveClientScene=true;coordinator.activeBodyClient=ClientScene.ConnectLocalServer();coordinator.activeBodyClient.RegisterHandler(MsgType.Connect,msg=>coordinator.r.activeClient.connectEvents++);coordinator.activeBodyClient.RegisterHandler(MsgType.Disconnect,msg=>{});Call(coordinator.activeBodyClient,"Update");
   coordinator.Check(coordinator.activeBodyClient.isConnected&&coordinator.r.activeClient.connectEvents==1&&NetworkServer.localConnections.Count==1,"Original active local connection failed");coordinator.Check(ClientScene.Ready(coordinator.activeBodyClient.connection),"Original active local readiness failed");Call(coordinator.activeBodyClient,"Update");coordinator.activeBodyOwner=NetworkServer.localConnections[0];
   coordinator.r.activeClient.bodyId=identity.netId.Value;coordinator.r.activeClient.masterId=player.master.netId.Value;coordinator.r.activeClient.ready=coordinator.activeBodyOwner.isReady&&coordinator.activeBodyClient.connection.isReady;coordinator.r.activeClient.bodyMapped=player.isClient&&ClientScene.FindLocalObject(identity.netId)==player.gameObject;coordinator.r.activeClient.masterMapped=player.master.isClient&&ClientScene.FindLocalObject(player.master.netId)==player.master.gameObject;coordinator.Check(coordinator.r.activeClient.ready&&coordinator.r.activeClient.bodyMapped&&coordinator.r.activeClient.masterMapped,"Original active client registry mapping failed");
   coordinator.Check(identity.AssignClientAuthority(coordinator.activeBodyOwner),"Original active client ownership rejected");activeOwnedBody=identity;Call(coordinator.activeBodyClient,"Update");
   coordinator.r.activeClient.localAuthority=identity.hasAuthority&&player.hasAuthority;coordinator.r.activeClient.ownerMatched=identity.clientAuthorityOwner==coordinator.activeBodyOwner;coordinator.r.activeClient.effectiveAuthority=player.hasEffectiveAuthority&&player.characterMotor.hasEffectiveAuthority;coordinator.r.activeClient.skillsAuthority=(bool)typeof(SkillLocator).GetField("hasEffectiveAuthority",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(player.skillLocator);coordinator.Check(coordinator.r.activeClient.localAuthority&&coordinator.r.activeClient.ownerMatched&&coordinator.r.activeClient.effectiveAuthority&&coordinator.r.activeClient.skillsAuthority,"Original active authority callbacks incomplete");
   if(coordinator.r.recoveredHudEnabled){
    // Original pickup notifications require the actual master, as well as its
    // body, to belong to the local connection. Preserve the source prefab flag.
    var masterIdentity=player.master.networkIdentity;coordinator.r.activeClient.masterAuthorityBefore=masterIdentity.hasAuthority;coordinator.r.activeClient.masterLocalPlayerAuthority=masterIdentity.localPlayerAuthority;
    coordinator.Check(masterIdentity.localPlayerAuthority&&!masterIdentity.hasAuthority&&masterIdentity.clientAuthorityOwner==null,"Unowned original master authority before HUD integration");
    coordinator.Check(masterIdentity.AssignClientAuthority(coordinator.activeBodyOwner),"Original local master ownership rejected");activeOwnedMaster=masterIdentity;Call(coordinator.activeBodyClient,"Update");
    coordinator.r.activeClient.masterLocalAuthority=masterIdentity.hasAuthority&&player.master.hasAuthority;coordinator.r.activeClient.masterOwnerMatched=masterIdentity.clientAuthorityOwner==coordinator.activeBodyOwner;
    coordinator.Check(coordinator.r.activeClient.masterLocalAuthority&&coordinator.r.activeClient.masterOwnerMatched&&player.master.hasEffectiveAuthority,"Original local master authority callbacks incomplete");
   }
   yield return null;
  }
  public IEnumerator ProbeActiveBodyClient(CharacterBody player,SessionConfig cfg){
   coordinator.r.activeClient=new ActiveClientReport{scope="Actual loopback local HLAPI client, original active Commando/master mapping, raw client authority callbacks and neutral ticking/teardown. No NetworkUser/LocalUser/platform session/entitlement grant, InteractionDriver/client effects/remote peers/full startup acceptance."};coordinator.r.phase="active-client-serializers";coordinator.Save();
   coordinator.Check(coordinator.r.moneyCost.paid&&coordinator.r.moneyCost.cleaned&&NetworkServer.active&&!NetworkClient.active&&NetworkClient.allClients.Count==0&&player.gameObject.activeInHierarchy&&player.master.hasBody&&player.master.GetBody()==player,"Accepted active actor/server context changed");
   var connect=ConnectActiveBodyClient(player);while(connect.MoveNext())yield return connect.Current;var identity=player.networkIdentity;
   if(cfg.originalInteractionSelection){var selection=coordinator.ProbeOriginalInteractionSelection(player,cfg);while(selection.MoveNext())yield return selection.Current;}
   if(cfg.originalClientCoin){var coin=coordinator.ProbeOriginalClientCoin(player);while(coin.MoveNext())yield return coin.Current;}
   if(cfg.originalInputBarrel){var input=coordinator.ProbeOriginalInputBarrel(player,cfg);while(input.MoveNext())yield return input.Current;}
   if(cfg.originalChestDropTable){var drops=coordinator.ProbeOriginalChestDropTable(player,cfg);while(drops.MoveNext())yield return drops.Current;}
   if(cfg.originalChestPurchase&&!cfg.originalChestEjection){var chest=coordinator.ProbeOriginalChestPurchase(player,cfg);while(chest.MoveNext())yield return chest.Current;}
   if(cfg.originalPickupDropletLoad){var droplet=coordinator.ProbeOriginalPickupDropletLoad(player,cfg);while(droplet.MoveNext())yield return droplet.Current;}
   if(cfg.originalDefaultPickup){var pickup=coordinator.ProbeOriginalDefaultPickup(player,cfg);while(pickup.MoveNext())yield return pickup.Current;}
   coordinator.r.phase="active-local-client-owned";coordinator.Save();yield return null;yield return new WaitForEndOfFrame();var state=EntityStateMachine.FindByCustomName(player.gameObject,"Body").state;coordinator.Check(state is EntityStates.GenericCharacterMain,"Original neutral state changed");float began=Time.realtimeSinceStartup,fixedBegan=Run.FixedTimeStamp.now.t,stateBegan=SpawnedStateAge(state,"fixedAge");coordinator.r.activeClient.healthBefore=player.healthComponent.health;int fixedTickBegan=coordinator.r.runClock.fixedTicks;
   while(Time.realtimeSinceStartup-began<60){yield return null;Call(coordinator.activeBodyClient,"Update");coordinator.ObserveOriginalRunClock();coordinator.r.activeClient.frames++;coordinator.r.activeClient.seconds=Time.realtimeSinceStartup-began;coordinator.r.activeClient.fixedSeconds=Run.FixedTimeStamp.now.t-fixedBegan;coordinator.r.activeClient.stateSeconds=SpawnedStateAge(state,"fixedAge")-stateBegan;coordinator.Check(coordinator.activeBodyClient.isConnected&&coordinator.activeBodyOwner.isReady&&identity.hasAuthority&&identity.clientAuthorityOwner==coordinator.activeBodyOwner&&player.hasEffectiveAuthority&&player.characterMotor.hasEffectiveAuthority&&player.master.GetBody()==player&&player.healthComponent.alive&&EntityStateMachine.FindByCustomName(player.gameObject,"Body").state==state&&!player.master.playerCharacterMasterController.networkUser&&LocalUserManager.readOnlyLocalUsersList.Count==0,"Active original client/actor lifetime contract changed");if(Time.frameCount%30==0)coordinator.Save();}
   coordinator.r.activeClient.healthAfter=player.healthComponent.health;coordinator.r.activeClient.fixedTicks=coordinator.r.runClock.fixedTicks-fixedTickBegan;coordinator.r.activeClient.grounded=player.characterMotor.isGrounded;coordinator.r.activeClient.syringeCount=player.inventory.GetItemCountPermanent(RoR2Content.Items.Syringe);coordinator.Check(coordinator.r.activeClient.seconds>=60&&coordinator.r.activeClient.frames>1000&&coordinator.r.activeClient.grounded&&coordinator.r.activeClient.syringeCount==1,"Original active-client actor/inventory hold incomplete");coordinator.Check(Mathf.Abs(coordinator.r.activeClient.fixedSeconds-coordinator.r.activeClient.fixedTicks*Time.fixedDeltaTime)<.03f&&Mathf.Abs(coordinator.r.activeClient.stateSeconds-coordinator.r.activeClient.fixedSeconds)<.03f,"Original active-client fixed callback/state intervals differ");coordinator.Check(Mathf.Abs(coordinator.r.activeClient.fixedSeconds-coordinator.r.activeClient.seconds)<.3f&&Mathf.Abs(coordinator.r.activeClient.stateSeconds-coordinator.r.activeClient.seconds)<.3f,"Original active-client fixed/wall intervals differ");
   coordinator.CleanupActiveBodyClient();yield return null;yield return null;coordinator.r.activeClient.cleaned=!NetworkClient.active&&NetworkClient.allClients.Count==0&&NetworkServer.localConnections.Count==0&&NetworkServer.active&&player&&player.master.GetBody()==player&&NetworkServer.FindLocalObject(identity.netId)==player.gameObject;coordinator.Check(coordinator.r.activeClient.removed&&coordinator.r.activeClient.cleaned,"Owned local client cleanup damaged server actor or retained client");coordinator.Save();
  }
  public void Dispose(){
   if(activeOwnedMaster&&coordinator.activeBodyOwner!=null){coordinator.Check(activeOwnedMaster.RemoveClientAuthority(coordinator.activeBodyOwner),"Original master authority removal rejected");if(coordinator.activeBodyClient!=null)Call(coordinator.activeBodyClient,"Update");coordinator.r.activeClient.masterAuthorityRemoved=activeOwnedMaster.clientAuthorityOwner==null&&!activeOwnedMaster.hasAuthority;coordinator.Check(coordinator.r.activeClient.masterAuthorityRemoved,"Original master authority removal incomplete");activeOwnedMaster=null;}
   if(activeOwnedBody&&coordinator.activeBodyOwner!=null){coordinator.Check(activeOwnedBody.RemoveClientAuthority(coordinator.activeBodyOwner),"Original active authority removal rejected");if(coordinator.activeBodyClient!=null)Call(coordinator.activeBodyClient,"Update");coordinator.r.activeClient.removed=activeOwnedBody.clientAuthorityOwner==null&&!activeOwnedBody.hasAuthority;coordinator.Check(coordinator.r.activeClient.removed,"Original active authority removal incomplete");activeOwnedBody=null;}
   if(coordinator.activeBodyClient!=null){coordinator.activeBodyClient.Disconnect();coordinator.activeBodyClient.Shutdown();coordinator.activeBodyClient=null;coordinator.activeBodyOwner=null;}
  }
  public void FinishActiveClientSceneCleanup(){if(!ownsActiveClientScene)return;coordinator.Check(!NetworkServer.active&&!NetworkClient.active,"Shared transport must outlive owned server teardown");StaticCall(typeof(ClientScene),"Shutdown");coordinator.r.activeClient.clientSceneCleaned=ClientScene.readyConnection==null&&!ClientScene.FindLocalObject(new NetworkInstanceId(coordinator.r.activeClient.bodyId))&&!ClientScene.FindLocalObject(new NetworkInstanceId(coordinator.r.activeClient.masterId));coordinator.Check(coordinator.r.activeClient.clientSceneCleaned,"Owned local client scene mapping retained");ownsActiveClientScene=false;}
 }
}
