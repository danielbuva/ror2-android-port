using System;
using System.Collections;
using System.IO;
using System.Reflection;
using EntityStates;
using RoR2;
using UnityEngine;

// Original state-machine scheduling only. No body, authority, catalog registration or gameplay claim.
public sealed class EntityStateTickProbe : MonoBehaviour {
 [Serializable] public class Result {
  public string attempt,error,initial,final;
  public int pid,manualFixedTicks;
  public bool success,queued,updateDidNotTransition,fixedTransition,updateTransition,automaticTicks,cleanup;
  public float fixedAge,automaticAge,automaticFixedAge;
 }
 Result report; GameObject host;
 static void Require(bool ok,string message){if(!ok)throw new Exception(message);}
 static float Age(EntityState state,string name){return (float)typeof(EntityState).GetProperty(name,BindingFlags.Instance|BindingFlags.NonPublic).GetValue(state);}
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("EntityStateTickProbe"))new GameObject("State tick observer").AddComponent<EntityStateTickProbe>();}
 IEnumerator Start(){
  report=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("EntityStateTickProbe").text);
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))report.pid=process.CallStatic<int>("myPid");
#endif
  yield return new WaitForSeconds(8);
  var routine=Probe();
  while(true){bool more;object current=null;try{more=routine.MoveNext();if(more)current=routine.Current;}catch(Exception e){report.error=e.ToString();Save();if(host)Destroy(host);yield break;}if(!more)break;yield return current;}
  Save();
 }
 IEnumerator Probe(){
  host=new GameObject("Isolated original EntityStateMachine");
  var machine=host.AddComponent<EntityStateMachine>();machine.enabled=false;
  report.initial=machine.state.GetType().FullName;Require(machine.state is Uninitialized,"Original Awake did not initialize state");
  Require(machine.commonComponents.transform==host.transform&&machine.commonComponents.characterBody==null&&machine.networker==null&&machine.networkIdentity==null,"Unexpected component or network context");
  var first=new Idle();machine.SetNextState(first);
  report.queued=machine.HasPendingState()&&!ReferenceEquals(machine.state,first);Require(report.queued,"Queue transitioned synchronously");
  machine.ManagedUpdate();report.updateDidNotTransition=machine.state is Uninitialized&&machine.HasPendingState();Require(report.updateDidNotTransition,"Wrong scheduling branch");
  machine.ManagedFixedUpdate(Time.fixedDeltaTime);report.fixedTransition=ReferenceEquals(machine.state,first)&&first.outer==machine&&!machine.HasPendingState();Require(report.fixedTransition,"Fixed transition failed");
  for(int i=0;i<4;i++)machine.ManagedFixedUpdate(Time.fixedDeltaTime);
  report.manualFixedTicks=5;report.fixedAge=Age(first,"fixedAge");Require(Mathf.Abs(report.fixedAge-5*Time.fixedDeltaTime)<.00001f,"Original fixed age mismatch");
  machine.ShouldStateTransitionOnUpdate=true;var second=new Idle();Require(machine.SetInterruptState(second,InterruptPriority.Any),"Idle interruption rejected");
  machine.ManagedFixedUpdate(Time.fixedDeltaTime);Require(ReferenceEquals(machine.state,first)&&machine.HasPendingState(),"Update mode transitioned in fixed phase");
  machine.ManagedUpdate();report.updateTransition=ReferenceEquals(machine.state,second)&&!machine.HasPendingState()&&second.outer==machine;Require(report.updateTransition,"Update transition failed");
  // State is already initialized; original Start must leave it intact. Let Unity drive both callbacks.
  machine.enabled=true;yield return new WaitForSeconds(1);
  report.automaticAge=Age(second,"age");report.automaticFixedAge=Age(second,"fixedAge");
  report.automaticTicks=ReferenceEquals(machine.state,second)&&report.automaticAge>.5f&&report.automaticFixedAge>.5f;Require(report.automaticTicks,"Unity-driven original ticks missing");
  report.final=machine.state.GetType().FullName;Destroy(host);yield return null;
  report.cleanup=machine.destroying&&machine.state==null;Require(report.cleanup,"Original OnDestroy did not clear state");report.success=true;
 }
 void Save(){File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"entity-state-tick-probe.json"),JsonUtility.ToJson(report,true));}
}
