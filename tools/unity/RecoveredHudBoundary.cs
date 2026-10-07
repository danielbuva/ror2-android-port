using System;
using System.Reflection;
using UnityEngine;

public sealed partial class MovementBatchProbe {
 RecoveredHudPresentation recoveredHud,recoveredMenu;
 GameObject recoveredMenuEvents;
 LabDiagnostics recoveredReferenceDiagnostics;bool priorRecoveredReferenceRendering;
 TMPro.TMP_Settings recoveredTextSettings;FieldInfo recoveredTextField;object priorRecoveredText;bool ownsRecoveredText;
 void PrepareRecoveredText(){
  if(!r.recoveredHudEnabled||ownsRecoveredText)return;
  recoveredTextField=typeof(TMPro.TMP_Settings).GetField("s_Instance",BindingFlags.Static|BindingFlags.NonPublic);priorRecoveredText=recoveredTextField.GetValue(null);Check(priorRecoveredText==null,"Unowned early text settings");
  recoveredTextSettings=Resources.Load<TMPro.TMP_Settings>("TMP Settings");Check(recoveredTextSettings,"Owned early source text settings absent");recoveredTextField.SetValue(null,recoveredTextSettings);ownsRecoveredText=true;
 }
 void CleanupRecoveredText(){if(ownsRecoveredText){Check(recoveredTextField.GetValue(null)==recoveredTextSettings,"Early text settings ownership changed");recoveredTextField.SetValue(null,priorRecoveredText);ownsRecoveredText=false;recoveredTextSettings=null;}}
 void PrepareRecoveredHud(){
  if(!r.recoveredHudEnabled)return;
  var source=Resources.Load<RecoveredHudPresentation>("RecoveredUI/Hud");Check(source&&!source.gameObject.activeSelf,"Recovered inactive HUD variant absent");
  recoveredHud=Instantiate(source);recoveredHud.Validate();recoveredHud.gameObject.SetActive(true);ObserveRecoveredHud();
 }
 void PrepareRecoveredMenu(){
  if(!r.recoveredHudEnabled)return;
  PrepareRecoveredText();var source=Resources.Load<RecoveredHudPresentation>("RecoveredUI/Menu");Check(source&&!source.gameObject.activeSelf,"Recovered inactive menu variant absent");
  Check(!recoveredReferenceDiagnostics,"Unowned menu reference-rendering scope");recoveredReferenceDiagnostics=Camera.main?Camera.main.GetComponent<LabDiagnostics>():null;Check(recoveredReferenceDiagnostics,"Owned lab camera diagnostics absent");priorRecoveredReferenceRendering=recoveredReferenceDiagnostics.ReferenceRendering;recoveredReferenceDiagnostics.SetReferenceRendering(false);r.hud.menuReferenceHidden=!recoveredReferenceDiagnostics.ReferenceRendering;
  Check(!UnityEngine.EventSystems.EventSystem.current,"Unowned offline menu event system");recoveredMenuEvents=new GameObject("Owned offline UI events",typeof(UnityEngine.EventSystems.EventSystem),typeof(UnityEngine.EventSystems.StandaloneInputModule));recoveredMenuEvents.GetComponent<UnityEngine.EventSystems.EventSystem>().sendNavigationEvents=false;
  recoveredMenu=Instantiate(source);recoveredMenu.BindMenu(()=>offlineStartSelected=true);recoveredMenu.gameObject.SetActive(true);Canvas.ForceUpdateCanvases();var rect=(RectTransform)recoveredMenu.startButton.transform;var point=RectTransformUtility.WorldToScreenPoint(null,rect.TransformPoint(rect.rect.center));r.hud.menuStartX=point.x;r.hud.menuStartY=Screen.height-point.y;r.hud.screenWidth=Screen.width;r.hud.screenHeight=Screen.height;r.hud.menuVisible=true;
 }
 void ObserveRecoveredHud(){if(recoveredHud&&worldPlayer)recoveredHud.Present(worldPlayer,r,r.hud);}
 void CleanupRecoveredMenu(){if(recoveredMenu)Destroy(recoveredMenu.gameObject);if(recoveredMenuEvents)Destroy(recoveredMenuEvents);recoveredMenuEvents=null;recoveredMenu=null;if(recoveredReferenceDiagnostics){Check(!recoveredReferenceDiagnostics.ReferenceRendering,"Menu reference-rendering owner changed");recoveredReferenceDiagnostics.SetReferenceRendering(priorRecoveredReferenceRendering);recoveredReferenceDiagnostics=null;}if(r.hud!=null){r.hud.menuVisible=false;r.hud.menuReferenceHidden=false;}}
 void CleanupRecoveredHud(){if(recoveredHud){recoveredHud.CleanupFeedback(r.hud);Destroy(recoveredHud.gameObject);}recoveredHud=null;CleanupRecoveredMenu();}
}
