using System.Collections;
using System.IO;
using System.Linq;
using RoR2;
using UnityEngine;

// Owned Android application flow around the original composed simulation.
// This screen is not the stock menu and creates no platform user or stock profile.
public sealed partial class MovementBatchProbe {
 bool offlineStartVisible,offlineStartSelected,returnToOfflineMenu,offlineSurvivorStickLatched;
 string pendingOfflineSurvivor="Commando";
 public bool skipOfflineMenu;
 NovaInputBridge.Mapping offlineMenuMapping;
 NovaInputBridge.ControllerPresence offlineUiPresence;
 bool OfflineUiControllerPresent(){
  var names=UnityEngine.Input.GetJoystickNames();
  if(names.Length==0||string.IsNullOrEmpty(names[0])||names.Skip(1).Any(name=>!string.IsNullOrEmpty(name))){offlineUiPresence?.Suspend();return false;}
  var map=offlineMenuMapping??(r!=null&&r.nova!=null?r.nova.mapping:null);
  if(map==null)return false;
  if(offlineUiPresence==null)offlineUiPresence=new NovaInputBridge.ControllerPresence(names[0]);
  var raw=NovaInputBridge.ReadRaw();
  bool neutral=raw.buttons.All(down=>!down)&&new[]{map.moveX,map.moveY,map.aimX,map.aimY}.All(axis=>Mathf.Abs(raw.axes[axis])<=AndroidOfflineSettings.current.deadzone);
  return offlineUiPresence.Observe(names,neutral,Time.realtimeSinceStartup);
 }
 void OnApplicationFocus(bool focused){if(!focused)offlineUiPresence?.Suspend();}
 void OnApplicationPause(bool paused){if(paused)offlineUiPresence?.Suspend();}
 static bool AllowsOfflineSessionMenu(Result session){return session!=null&&(session.freePlay||session.recoveredHudEnabled&&session.id!=null&&session.id.EndsWith("-bringup",System.StringComparison.Ordinal));}
 IEnumerator AwaitOfflineRunStart(Result cfg){
  if(cfg.integratedWorld&&cfg.integratedResults)PrepareOfflineSettings();
  if(string.IsNullOrEmpty(r.selectedSurvivor))r.selectedSurvivor=pendingOfflineSurvivor;
  // A developer-only survivor override is never shown as an earned menu choice.
  if(!AllowsOfflineSessionMenu(r)||!cfg.integratedWorld||!cfg.integratedResults||skipOfflineMenu||r.developerSurvivorOverride)yield break;
  offlineUnlockPreview=null;var choices=OrdinarySurvivorChoices();
  if(!choices.Any(value=>value.cachedName==r.selectedSurvivor))r.selectedSurvivor=choices[0].cachedName;
  offlineMenuMapping=JsonUtility.FromJson<NovaInputBridge.Mapping>(File.ReadAllText(System.IO.Path.Combine(Application.persistentDataPath,"nova-input-mapping.json")));
  offlineMenuMapping.Validate(r.attempt);PrepareRecoveredMenu();offlineStartVisible=true;r.phase="offline-start-menu";Save();
  while(!offlineStartSelected)yield return null;
  offlineStartVisible=false;CleanupRecoveredMenu();pendingOfflineSurvivor=r.selectedSurvivor;SelectedPlayerPrefab(cfg);r.phase="started";Save();
 }
 void ObserveOfflineApplicationInput(){
  if(offlineStartVisible){if(OfflineUiControllerPresent()){var horizontal=NovaInputBridge.ReadRaw().axes[offlineMenuMapping.moveX];if(Mathf.Abs(horizontal)<.3f)offlineSurvivorStickLatched=false;else if(!offlineSurvivorStickLatched&&Mathf.Abs(horizontal)>.65f){CycleOrdinarySurvivor(horizontal>0?1:-1);offlineSurvivorStickLatched=true;}if(UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0+offlineMenuMapping.jump)))offlineStartSelected=true;}return;}
  ObserveOfflineSettingsControllerInput();
  if(r!=null&&r.phase!="commando-defeated"&&r.freePlay&&r.results!=null&&r.results.persisted&&r.nova!=null&&!offlineSettingsVisible&&OfflineUiControllerPresent()&&UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0+r.nova.mapping.jump)))RequestResultsMenu();
 }
 bool DrawOfflineStart(){
  if(!offlineStartVisible)return false;
  var selected=string.IsNullOrEmpty(r.selectedSurvivor)?"Commando":r.selectedSurvivor;
  if(recoveredMenu){GUI.Box(new Rect(20,Screen.height-156,470,88),"Original base survivor · Android profile");if(GUI.Button(new Rect(40,Screen.height-127,430,48),selected+"  ◀  ▶"))CycleOrdinarySurvivor(1);GUI.Label(new Rect(20,Screen.height-58,Screen.width-40,55),"Offline composition · original unlocks verified when run starts · audio/Steam profiles unavailable · source UI rendering approximation");return true;}
  var style=new GUIStyle(GUI.skin.label){fontSize=30,wordWrap=true};
  GUI.Box(new Rect(20,60,860,400),"Offline RoR2 composition");
  GUI.Label(new Rect(45,100,800,220),selected+" · Drizzle\nExplore, earn items, defeat each teleporter boss, then reach the Moon.\n\nOriginal profile data and results stay on this Android device. Audio and Steam/cloud profiles are unavailable.",style);
  if(GUI.Button(new Rect(45,270,370,55),"Survivor: "+selected+"  ◀  ▶"))CycleOrdinarySurvivor(1);
  if(GUI.Button(new Rect(45,340,370,65),"Start run (A)"))offlineStartSelected=true;
  if(GUI.Button(new Rect(440,340,370,65),"Quit"))Application.Quit();
  return true;
 }
 void RequestResultsMenu(){
  if(r==null||!r.freePlay||r.results==null||!r.results.persisted)return;
  Check(r.results.serverEnding&&r.results.clientEnding&&r.results.reportReloaded,"Return requested before original ending/report persistence");
  returnToOfflineMenu=true;restartRequested=true;r.phase="returning-to-offline-menu";Save();
 }
 bool CompletedResultsReturn(){return returnToOfflineMenu&&r.results!=null&&r.results.persisted&&r.results.clientEnding;}
 bool CanAbandonOfflineRun(){return AllowsOfflineSessionMenu(r)&&r.integratedWorld&&r.world!=null&&r.world.ready&&worldPlayer&&worldPlayer.healthComponent.alive&&r.results!=null&&r.results.ready&&!r.results.serverEnding&&!r.results.reportGenerated&&!r.results.persisted&&!restartRequested;}
 void RequestAbandonOfflineRun(){
  if(!CanAbandonOfflineRun())return;
  // Leaving a local session is not an original game ending or a saved result.
  Check(UnityEngine.Networking.NetworkServer.active&&Run.instance,"Live offline session ownership absent");
  ShowOfflineSettings(false);r.settings.sessionAbandoned=true;returnToOfflineMenu=true;restartRequested=true;r.phase="abandoning-offline-session";Save();
 }
 bool CompletedOfflineAbandon(){return returnToOfflineMenu&&r.settings!=null&&r.settings.sessionAbandoned&&r.results!=null&&!r.results.serverEnding&&!r.results.reportGenerated&&!r.results.persisted;}
}
