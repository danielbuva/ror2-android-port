using System;
using System.Reflection;
using Rewired;
using UnityEngine;

// Invoke original detector methods on an inactive owned component; never initialize ReInput.
public sealed partial class MovementBatchProbe {
 void RewiredPlatformBoundary(){
  r.rewiredReadyBefore=ReInput.isReady;Check(!r.rewiredReadyBefore,"ReInput already initialized");
  host=new GameObject("Inactive original Rewired platform fixture");host.SetActive(false);
  var manager=host.AddComponent<InputManager>();Check(!host.activeInHierarchy&&!ReInput.isReady,"Input manager activated unexpectedly");
  var flags=BindingFlags.Instance|BindingFlags.NonPublic;
  typeof(InputManager).GetMethod("DetectPlatform",flags).Invoke(manager,null);
  r.rewiredPlatform=typeof(InputManager_Base).GetField("platform",flags).GetValue(manager).ToString();
  r.rewiredBackend=typeof(InputManager_Base).GetField("scriptingBackend",flags).GetValue(manager).ToString();
  r.rewiredApi=typeof(InputManager_Base).GetField("scriptingAPILevel",flags).GetValue(manager).ToString();
  var external=typeof(InputManager).GetMethod("GetExternalTools",flags).Invoke(manager,null);
  r.rewiredAndroidApi=(int)external.GetType().GetMethod("GetAndroidAPILevel").Invoke(external,null);
  r.unityJoystickNames=UnityEngine.Input.GetJoystickNames();
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var version=new AndroidJavaClass("android.os.Build$VERSION"))r.androidApi=version.GetStatic<int>("SDK_INT");
#endif
  r.rewiredAndroidContract=r.rewiredPlatform=="Android"&&r.rewiredBackend=="IL2CPP"&&r.rewiredAndroidApi==r.androidApi;
  Save();
  Check(Application.platform==RuntimePlatform.Android&&r.androidApi>=23,"Actual Android runtime not established");
  Check(r.rewiredPlatform=="Windows"&&r.rewiredBackend=="Mono"&&r.rewiredApi=="NetStandard20"&&r.rewiredAndroidApi==-1,"Original platform selection differs from audited input; reassess");
  r.rewiredReadyAfter=ReInput.isReady;Check(!r.rewiredReadyAfter&&!r.rewiredAndroidContract,"Diagnostic detector initialized or misclassified ReInput");
 }
}
