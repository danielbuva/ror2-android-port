using System;
using System.Collections;
using System.IO;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Original direction simulation with an actual local server-owned identity; no character body.
public sealed class CharacterDirectionProbe : MonoBehaviour {
 [Serializable] public class Result {
  public string attempt,error;public int pid;
  public bool success,noAuthorityBlocked,serverActive,spawned,effectiveAuthority,identityAuthority,turned,stopped,cleanup;
  public float yaw,targetYaw,stoppedYaw;public uint netId;
 }
 Result report;GameObject host;bool ownsServer;
 static void Require(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Call(CharacterDirection d,string name,params object[] args){typeof(CharacterDirection).GetMethod(name,BindingFlags.Instance|BindingFlags.NonPublic).Invoke(d,args);}
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("CharacterDirectionProbe"))new GameObject("Direction observer").AddComponent<CharacterDirectionProbe>();}
 IEnumerator Start(){
  report=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("CharacterDirectionProbe").text);
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))report.pid=process.CallStatic<int>("myPid");
#endif
  yield return new WaitForSeconds(11);
  try{Probe();}catch(Exception e){report.error=e.ToString();}
  finally{if(host){if(ownsServer&&NetworkServer.active)NetworkServer.Destroy(host);else Destroy(host);}if(ownsServer)NetworkServer.Shutdown();report.cleanup=!NetworkServer.active;report.success=report.success&&report.cleanup;File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"character-direction-probe.json"),JsonUtility.ToJson(report,true));}
 }
 void Probe(){
  Require(!NetworkServer.active&&!NetworkClient.active,"Existing network session; refusing to alter it");
  host=new GameObject("Original direction fixture");var identity=host.AddComponent<NetworkIdentity>();
  var d=host.AddComponent<CharacterDirection>();d.enabled=false;
  var target=new GameObject("Direction target").transform;target.SetParent(host.transform,false);d.targetTransform=target;d.moveVector=Vector3.right;
  Call(d,"Start");Call(d,"Simulate",.02f);
  report.noAuthorityBlocked=!d.hasEffectiveAuthority&&Mathf.Abs(d.yaw)<.001f&&Quaternion.Angle(target.rotation,Quaternion.identity)<.001f;Require(report.noAuthorityBlocked,"Direction changed without authority");
  Require(NetworkServer.Listen("127.0.0.1",0),"Local server could not listen");ownsServer=true;report.serverActive=NetworkServer.active;
  NetworkServer.Spawn(host);report.netId=identity.netId.Value;report.spawned=identity.isServer&&report.netId!=0;
  Call(d,"Start");report.effectiveAuthority=d.hasEffectiveAuthority;report.identityAuthority=identity.hasAuthority;
  Require(report.serverActive&&report.spawned&&report.effectiveAuthority&&Util.HasEffectiveAuthority(identity),"Real server ownership did not establish effective authority");
  for(int i=0;i<100;i++)Call(d,"Simulate",.02f);
  report.yaw=d.yaw;report.targetYaw=target.eulerAngles.y;
  report.turned=Mathf.Abs(Mathf.DeltaAngle(report.yaw,90))<.1f&&Mathf.Abs(Mathf.DeltaAngle(report.targetYaw,90))<.1f;Require(report.turned,"Original turning did not converge east");
  d.moveVector=Vector3.zero;for(int i=0;i<20;i++)Call(d,"Simulate",.02f);
  report.stoppedYaw=d.yaw;report.stopped=Mathf.Abs(Mathf.DeltaAngle(report.stoppedYaw,report.yaw))<.001f;Require(report.stopped,"Neutral input changed facing");
  Require(host.transform.position==Vector3.zero,"Unexpected translation");report.success=true;
 }
}
