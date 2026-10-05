using System;
using System.Collections.Generic;
using RoR2;
using RoR2.Networking;
using UnityEngine.Networking;
using PlatformID = RoR2.PlatformID;

// Scene transport only. Original Run.AdvanceStage performs RNG, difficulty and counting.
public sealed class AndroidStageTransport : NetworkManagerSystem {
 public Action<string> requested;
 // Typed scene callbacks require this base, but platform services remain unavailable.
 // The already measured local HLAPI connection owns simulation separately.
 static Exception Unavailable(){return new NotSupportedException("Platform networking/authentication/lobby services are unavailable in the Android composition");}
 protected override void Start(){}
 protected override void Update(){}
 protected override void EnsureDesiredHost(){throw Unavailable();}
 public override void ForceCloseAllConnections(){throw Unavailable();}
 public override void CreateLocalLobby(){throw Unavailable();}
 public override IEnumerator<CanPlayOnlineState> CanPlayOnline(){yield return CanPlayOnlineState.No;}
 protected override AddPlayerMessage CreateClientAddPlayerMessage(){throw Unavailable();}
 protected override void UpdateCheckInactiveConnections(){throw Unavailable();}
 protected override void StartClient(PlatformID serverID){throw Unavailable();}
 public override bool IsConnectedToServer(PlatformID serverID){return false;}
 protected override void PlatformAuth(ref ClientAuthData data,NetworkConnection conn){throw Unavailable();}
 protected override void PlatformClientSetPlayers(ConCommandArgs args){throw Unavailable();}
 protected override void PlatformDisconnect(ConCommandArgs args){throw Unavailable();}
 protected override void PlatformConnect(ConCommandArgs args){throw Unavailable();}
 protected override void PlatformConnectP2P(ConCommandArgs args){throw Unavailable();}
 protected override void PlatformHost(ConCommandArgs args){throw Unavailable();}
 protected override void PlatformGetP2PSessionState(ConCommandArgs args){throw Unavailable();}
 protected override void PlatformKick(ConCommandArgs args){throw Unavailable();}
 protected override void PlatformBan(ConCommandArgs args){throw Unavailable();}
 public override NetworkConnection GetClient(PlatformID clientId){return null;}
 public override void ServerHandleClientDisconnect(NetworkConnection conn){throw Unavailable();}
 public override void ServerBanClient(NetworkConnection conn){throw Unavailable();}
 protected override void KickClient(NetworkConnection conn,BaseKickReason reason){throw Unavailable();}
 protected override NetworkUserId AddPlayerIdFromPlatform(NetworkConnection conn,AddPlayerMessage message,byte playerControllerId){throw Unavailable();}
 protected override void UpdateServer(){throw Unavailable();}
 public override void ServerChangeScene(string sceneName){
  if(!NetworkServer.active||requested==null)throw new InvalidOperationException("Owned Android scene transport is unavailable");
  requested(sceneName);
 }
}
