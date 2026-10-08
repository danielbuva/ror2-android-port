using System;
using System.IO;
using Path=System.IO.Path;
using RoR2;
using UnityEngine;

// Owned Android settings/pause screen around the composed local session.
public sealed partial class MovementBatchProbe {
 [Serializable] public class OfflineSettingsReport {public bool ready,visible,paused,persisted,canEndRun,sessionAbandoned;public string recovery,error;public float deadzone,lookSensitivity,buttonX,buttonY,endRunButtonX,endRunButtonY,timeScale,runSeconds;public int fixedTicks,observations;public bool invertY;public int saves,pauses,resumes;}
 AndroidOfflineSettings offlineSettings;bool offlineSettingsVisible,offlineSettingsPaused;float offlineSettingsTimeScale;
 void PrepareOfflineSettings(){
  if(offlineSettings!=null)return;
  offlineSettings=new AndroidOfflineSettings(Path.Combine(Application.persistentDataPath,"offline-settings-v1"));AndroidOfflineSettings.current=offlineSettings.values;r.settings=new OfflineSettingsReport{ready=true,recovery=offlineSettings.recovery};ObserveOfflineSettings();
 }
 void ObserveOfflineSettings(){if(offlineSettings==null)return;var v=offlineSettings.values;r.settings.buttonX=Screen.width-112.5f;r.settings.buttonY=30;r.settings.deadzone=v.deadzone;r.settings.lookSensitivity=v.lookSensitivity;r.settings.invertY=v.invertY;r.settings.visible=offlineSettingsVisible;r.settings.paused=offlineSettingsPaused;r.settings.timeScale=Time.timeScale;r.settings.runSeconds=Run.instance?Run.instance.GetRunStopwatch():0;r.settings.fixedTicks=r.runClock==null?0:r.runClock.fixedTicks;}
 void ShowOfflineSettings(bool show){
  if(offlineSettings==null)return;
  if(show==offlineSettingsVisible)return;
  if(show&&worldPause&&worldPlayer&&worldPlayer.healthComponent.alive){Check(PauseStopController.instance&&!PauseStopController.instance.isPaused&&Time.timeScale>0,"Unowned pause state");offlineSettingsTimeScale=Time.timeScale;PauseStopController.instance.NetworkisPaused=true;Time.timeScale=0;offlineSettingsPaused=true;r.settings.pauses++;var bridge=worldPlayer.GetComponent<NovaInputBridge>();if(bridge)bridge.Neutral();}
  if(!show&&offlineSettingsPaused){Check(PauseStopController.instance&&PauseStopController.instance.isPaused&&Time.timeScale==0,"Owned pause context changed");PauseStopController.instance.NetworkisPaused=false;Time.timeScale=offlineSettingsTimeScale;offlineSettingsPaused=false;r.settings.resumes++;}
  offlineSettingsVisible=show;ObserveOfflineSettings();Save();
 }
 void DrawOfflineSettings(){
  if(offlineSettings==null)return;
  var button=new Rect(Screen.width-205,10,185,40);r.settings.buttonX=button.center.x;r.settings.buttonY=button.center.y;
  if(GUI.Button(button,offlineSettingsVisible?"Close settings":"Settings / pause"))ShowOfflineSettings(!offlineSettingsVisible);
  if(!offlineSettingsVisible)return;
  GUI.Box(new Rect(Screen.width*.5f-240,Screen.height*.5f-200,480,400),"Android offline input settings");var x=Screen.width*.5f-210;var y=Screen.height*.5f-155;
  GUI.Label(new Rect(x,y,420,28),"Stick deadzone: "+offlineSettings.values.deadzone.ToString("F2"));offlineSettings.values.deadzone=GUI.HorizontalSlider(new Rect(x,y+35,420,25),offlineSettings.values.deadzone,.05f,.4f);
  GUI.Label(new Rect(x,y+68,420,28),"Camera sensitivity: "+offlineSettings.values.lookSensitivity.ToString("F2"));offlineSettings.values.lookSensitivity=GUI.HorizontalSlider(new Rect(x,y+103,420,25),offlineSettings.values.lookSensitivity,.25f,3);
  offlineSettings.values.invertY=GUI.Toggle(new Rect(x,y+139,420,30),offlineSettings.values.invertY,"Invert vertical camera");
  if(GUI.Button(new Rect(x,y+180,200,45),"Save and close")){offlineSettings.Save();AndroidOfflineSettings.current=offlineSettings.values;r.settings.saves++;r.settings.persisted=true;ShowOfflineSettings(false);}
  if(GUI.Button(new Rect(x+220,y+180,200,45),"Resume"))ShowOfflineSettings(false);
  r.settings.canEndRun=CanAbandonOfflineRun();var end=new Rect(x,y+245,420,45);r.settings.endRunButtonX=end.center.x;r.settings.endRunButtonY=end.center.y;
  if(r.settings.canEndRun&&GUI.Button(end,"End run and return to menu"))RequestAbandonOfflineRun();
  ObserveOfflineSettings();if(offlineSettingsPaused&&Event.current.type==EventType.Repaint&&Time.frameCount%30==0){r.settings.observations++;Save();}
 }
 void CleanupOfflineSettingsPause(){if(offlineSettingsPaused)ShowOfflineSettings(false);}
}
