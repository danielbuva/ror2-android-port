// Subsystem: HUD/UI (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareRecoveredText, PrepareRecoveredMenu, PrepareRecoveredHud (RecoveredHudSession); teardown CleanupRecoveredHud (Dispose), CleanupRecoveredMenu, CleanupRecoveredText.
using System;
using System.Reflection;
using UnityEngine;

public sealed partial class MovementBatchProbe {
 // Shared with world/developer UI, the offline menu and teleporter text setup.
 RecoveredHudPresentation recoveredHud,recoveredMenu;
 TMPro.TMP_Settings recoveredTextSettings;bool ownsRecoveredText;
 RecoveredHudSession recoveredHudSession;
 RecoveredHudSession GetRecoveredHudSession(){if(recoveredHudSession==null)recoveredHudSession=new RecoveredHudSession(this);return recoveredHudSession;}
 void PrepareRecoveredText(){GetRecoveredHudSession().PrepareRecoveredText();}
 void CleanupRecoveredText(){GetRecoveredHudSession().CleanupRecoveredText();}
 void PrepareRecoveredHud(){GetRecoveredHudSession().PrepareRecoveredHud();}
 void PrepareRecoveredMenu(){GetRecoveredHudSession().PrepareRecoveredMenu();}
 void ObserveRecoveredHud(){GetRecoveredHudSession().ObserveRecoveredHud();}
 void CleanupRecoveredMenu(){GetRecoveredHudSession().CleanupRecoveredMenu();}
 void CleanupRecoveredHud(){GetRecoveredHudSession().Dispose();}

 // Nested to keep shared coordinator state private. Retain the owner after
 // Dispose for partial setup, repeated cleanup and later sessions. HUD/menu
 // disposal does not release text: catalog teardown owns that later phase.
 sealed class RecoveredHudSession : IDisposable {
  readonly MovementBatchProbe coordinator;
  GameObject recoveredMenuEvents;
  LabDiagnostics recoveredReferenceDiagnostics;bool priorRecoveredReferenceRendering;
  FieldInfo recoveredTextField;object priorRecoveredText;
  public RecoveredHudSession(MovementBatchProbe coordinator){this.coordinator=coordinator;}
  public void PrepareRecoveredText(){
   if(!coordinator.r.recoveredHudEnabled||coordinator.ownsRecoveredText)return;
   recoveredTextField=typeof(TMPro.TMP_Settings).GetField("s_Instance",BindingFlags.Static|BindingFlags.NonPublic);priorRecoveredText=recoveredTextField.GetValue(null);coordinator.Check(priorRecoveredText==null,"Unowned early text settings");
   coordinator.recoveredTextSettings=Resources.Load<TMPro.TMP_Settings>("TMP Settings");coordinator.Check(coordinator.recoveredTextSettings,"Owned early source text settings absent");recoveredTextField.SetValue(null,coordinator.recoveredTextSettings);coordinator.ownsRecoveredText=true;
  }
  public void CleanupRecoveredText(){if(coordinator.ownsRecoveredText){coordinator.Check(recoveredTextField.GetValue(null)==coordinator.recoveredTextSettings,"Early text settings ownership changed");recoveredTextField.SetValue(null,priorRecoveredText);coordinator.ownsRecoveredText=false;coordinator.recoveredTextSettings=null;}}
  public void PrepareRecoveredHud(){
   if(!coordinator.r.recoveredHudEnabled)return;
   var source=Resources.Load<RecoveredHudPresentation>("RecoveredUI/Hud");coordinator.Check(source&&!source.gameObject.activeSelf,"Recovered inactive HUD variant absent");
   coordinator.recoveredHud=Instantiate(source);coordinator.recoveredHud.Validate();coordinator.recoveredHud.gameObject.SetActive(true);ObserveRecoveredHud();
  }
  public void PrepareRecoveredMenu(){
   if(!coordinator.r.recoveredHudEnabled)return;
   PrepareRecoveredText();var source=Resources.Load<RecoveredHudPresentation>("RecoveredUI/Menu");coordinator.Check(source&&!source.gameObject.activeSelf,"Recovered inactive menu variant absent");
   coordinator.Check(!recoveredReferenceDiagnostics,"Unowned menu reference-rendering scope");recoveredReferenceDiagnostics=Camera.main?Camera.main.GetComponent<LabDiagnostics>():null;coordinator.Check(recoveredReferenceDiagnostics,"Owned lab camera diagnostics absent");priorRecoveredReferenceRendering=recoveredReferenceDiagnostics.ReferenceRendering;recoveredReferenceDiagnostics.SetReferenceRendering(false);coordinator.r.hud.menuReferenceHidden=!recoveredReferenceDiagnostics.ReferenceRendering;
   coordinator.Check(!UnityEngine.EventSystems.EventSystem.current,"Unowned offline menu event system");recoveredMenuEvents=new GameObject("Owned offline UI events",typeof(UnityEngine.EventSystems.EventSystem),typeof(UnityEngine.EventSystems.StandaloneInputModule));recoveredMenuEvents.GetComponent<UnityEngine.EventSystems.EventSystem>().sendNavigationEvents=false;
   coordinator.recoveredMenu=Instantiate(source);coordinator.recoveredMenu.BindMenu(()=>coordinator.offlineStartSelected=true);coordinator.recoveredMenu.gameObject.SetActive(true);Canvas.ForceUpdateCanvases();var rect=(RectTransform)coordinator.recoveredMenu.startButton.transform;var point=RectTransformUtility.WorldToScreenPoint(null,rect.TransformPoint(rect.rect.center));coordinator.r.hud.menuStartX=point.x;coordinator.r.hud.menuStartY=Screen.height-point.y;coordinator.r.hud.screenWidth=Screen.width;coordinator.r.hud.screenHeight=Screen.height;coordinator.r.hud.menuVisible=true;
  }
  public void ObserveRecoveredHud(){if(coordinator.recoveredHud&&coordinator.worldPlayer)coordinator.recoveredHud.Present(coordinator.worldPlayer,coordinator.r,coordinator.r.hud);}
  public void CleanupRecoveredMenu(){if(coordinator.recoveredMenu)Destroy(coordinator.recoveredMenu.gameObject);if(recoveredMenuEvents)Destroy(recoveredMenuEvents);recoveredMenuEvents=null;coordinator.recoveredMenu=null;if(recoveredReferenceDiagnostics){coordinator.Check(!recoveredReferenceDiagnostics.ReferenceRendering,"Menu reference-rendering owner changed");recoveredReferenceDiagnostics.SetReferenceRendering(priorRecoveredReferenceRendering);recoveredReferenceDiagnostics=null;}if(coordinator.r.hud!=null){coordinator.r.hud.menuVisible=false;coordinator.r.hud.menuReferenceHidden=false;}}
  public void Dispose(){if(coordinator.recoveredHud){coordinator.recoveredHud.CleanupFeedback(coordinator.r.hud);Destroy(coordinator.recoveredHud.gameObject);}coordinator.recoveredHud=null;CleanupRecoveredMenu();}
 }
}
