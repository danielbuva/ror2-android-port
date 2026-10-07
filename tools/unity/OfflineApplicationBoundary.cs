using System.Collections;
using System.IO;
using RoR2;
using UnityEngine;

// Owned Android application flow around the original composed simulation.
// This screen is not the stock menu and creates no platform user or stock profile.
public sealed partial class MovementBatchProbe {
 bool offlineStartVisible,offlineStartSelected,returnToOfflineMenu;
 public bool skipOfflineMenu;
 NovaInputBridge.Mapping offlineMenuMapping;
 IEnumerator AwaitOfflineRunStart(Result cfg){
  if((!r.freePlay&&!(cfg.recoveredHudEnabled&&r.id.EndsWith("-bringup")))||!cfg.integratedWorld||!cfg.integratedResults||skipOfflineMenu)yield break;
  offlineMenuMapping=JsonUtility.FromJson<NovaInputBridge.Mapping>(File.ReadAllText(System.IO.Path.Combine(Application.persistentDataPath,"nova-input-mapping.json")));
  offlineMenuMapping.Validate(r.attempt);PrepareRecoveredMenu();offlineStartVisible=true;r.phase="offline-start-menu";Save();
  while(!offlineStartSelected)yield return null;
  offlineStartVisible=false;CleanupRecoveredMenu();r.phase="started";Save();
 }
 void ObserveOfflineApplicationInput(){
  if(offlineStartVisible){if(UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0+offlineMenuMapping.jump)))offlineStartSelected=true;return;}
  if(r!=null&&r.phase!="commando-defeated"&&r.freePlay&&r.results!=null&&r.results.persisted&&r.nova!=null&&UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0+r.nova.mapping.jump)))RequestResultsMenu();
 }
 bool DrawOfflineStart(){
  if(!offlineStartVisible)return false;
  if(recoveredMenu){GUI.Label(new Rect(20,Screen.height-58,Screen.width-40,55),"Offline composition · Android-only results · audio/platform profiles unavailable · source UI rendering approximation");return true;}
  var style=new GUIStyle(GUI.skin.label){fontSize=30,wordWrap=true};
  GUI.Box(new Rect(20,60,860,400),"Offline RoR2 composition");
  GUI.Label(new Rect(45,100,800,220),"Commando · Drizzle\nExplore, earn items, defeat each teleporter boss, then reach the Moon.\n\nAudio and stock platform profiles are unavailable. Run results stay on this Android device.",style);
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
}
