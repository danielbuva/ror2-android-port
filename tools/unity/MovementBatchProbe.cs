using System;
using System.Collections;
using System.IO;
using System.Reflection;
using RoR2;
using KinematicCharacterController;
using UnityEngine;
using UnityEngine.Networking;

// Each selected experiment runs in a fresh process. Inactive body fixtures never run gameplay lifecycle.
public sealed class MovementBatchProbe : MonoBehaviour {
 [Serializable] public class Result {public string attempt,id,phase,error;public int pid;public bool success,cleanup;public float x,y,z;public int assertions;}
 Result r;GameObject host;bool ownsServer;
 void Check(bool value,string message){r.assertions++;if(!value)throw new Exception(message);}
 static void Call(object obj,string method,params object[] args){obj.GetType().GetMethod(method,BindingFlags.NonPublic|BindingFlags.Instance).Invoke(obj,args);}
 void Save(){File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-"+r.id+".json"),JsonUtility.ToJson(r,true));}
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("MovementBatchProbe"))new GameObject("Isolated movement batch").AddComponent<MovementBatchProbe>();}
 IEnumerator Start(){
  yield return new WaitForSeconds(8);
  var path=System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-selection.json");if(!File.Exists(path))yield break;
  r=JsonUtility.FromJson<Result>(File.ReadAllText(path));var config=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);if(r.attempt!=config.attempt)yield break;
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))r.pid=process.CallStatic<int>("myPid");
#endif
  r.phase="started";Save();
  try{
   switch(r.id){case "buttons":Buttons();break;case "input":Input();break;case "motor-output":MotorOutput();break;case "motor-acceleration":MotorAcceleration();break;default:throw new Exception("Unknown experiment");}
   r.success=true;
  }catch(Exception e){r.error=e.ToString();}
  finally{if(host)Destroy(host);if(ownsServer)NetworkServer.Shutdown();r.cleanup=!ownsServer||!NetworkServer.active;r.success&=r.cleanup;r.phase="complete";Save();}
 }
 void Buttons(){
  var b=new InputBankTest.ButtonState();Check(!b.justPressed&&!b.justReleased,"Initial edge");
  b.PushState(true);Check(b.justPressed&&!b.justReleased,"Press edge");b.hasPressBeenClaimed=true;
  b.PushState(true);Check(!b.justPressed&&b.down&&b.hasPressBeenClaimed,"Hold/claim");
  b.PushState(false);Check(b.justReleased&&!b.hasPressBeenClaimed,"Release/claim reset");b.PushState(false);Check(!b.justReleased,"Repeated release");
  b.PushState(true);Check(b.justPressed,"Second press");
 }
 InputBankTest InactiveInput(){host=new GameObject("Inactive input fixture");host.SetActive(false);return host.AddComponent<InputBankTest>();}
 void Input(){
  var bank=InactiveInput();Check(!host.activeInHierarchy,"Body lifecycle unexpectedly active");
  bank.SetRawMoveStates(new Vector2(.8f,0));Check(!bank.rawMoveRight.down,"Press threshold");
  bank.SetRawMoveStates(new Vector2(1,0));Check(bank.rawMoveRight.justPressed,"Right press");
  bank.SetRawMoveStates(new Vector2(.2f,0));Check(bank.rawMoveRight.down&&!bank.rawMoveRight.justPressed,"Hysteresis hold");
  bank.SetRawMoveStates(new Vector2(.05f,0));Check(bank.rawMoveRight.justReleased,"Hysteresis release");
  bank.SetRawMoveStates(new Vector2(-1,-1));Check(bank.rawMoveLeft.justPressed&&bank.rawMoveDown.justPressed&&!bank.rawMoveUp.down,"Opposite axes");
  bank.aimDirection=new Vector3(3,0,4);Check(Vector3.Distance(bank.aimDirection,new Vector3(.6f,0,.8f))<.00001f,"Aim normalization");
  bank.aimDirection=Vector3.zero;Check(bank.aimDirection==host.transform.forward,"Zero aim fallback");
  Check(!bank.CheckAnyButtonDown(),"Empty button set");bank.jump.PushState(true);Check(bank.CheckAnyButtonDown(),"Jump aggregation");
 }
 CharacterMotor InactiveMotor(){
  host=new GameObject("Inactive motor fixture");host.SetActive(false);host.AddComponent<CapsuleCollider>();return host.AddComponent<CharacterMotor>();
 }
 void MotorOutput(){
  var motor=InactiveMotor();motor.velocity=new Vector3(2,3,-4);var v=Vector3.zero;motor.UpdateVelocity(ref v,.02f);
  Check(v==motor.velocity,"Velocity callback changed value");var q=Quaternion.Euler(10,20,30);motor.UpdateRotation(ref q,.02f);Check(q==Quaternion.identity,"Motor rotation callback");
  Check(!host.activeInHierarchy,"Body lifecycle active");r.x=v.x;r.y=v.y;r.z=v.z;
 }
 void MotorAcceleration(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Existing network session");
  host=new GameObject("Owned motor identity");var identity=host.AddComponent<NetworkIdentity>();
  Check(NetworkServer.Listen("127.0.0.1",0),"Local listen failed");ownsServer=true;NetworkServer.Spawn(host);Check(identity.isServer&&identity.netId.Value!=0,"Spawn failed");
  host.SetActive(false);host.AddComponent<CapsuleCollider>();var motor=host.AddComponent<CharacterMotor>();var kinematic=host.AddComponent<KinematicCharacterMotor>();
  Call(motor,"Awake");motor.SetupCharacterMotor(kinematic);Call(motor,"UpdateAuthority");Check(motor.hasEffectiveAuthority&&Util.HasEffectiveAuthority(identity),"Original authority failed");
  var body=host.GetComponent<CharacterBody>();
  // Explicit diagnostic stat inputs; this does not exercise RecalculateStats or body startup.
  typeof(CharacterBody).GetProperty("moveSpeed").SetValue(body,7f);typeof(CharacterBody).GetProperty("acceleration").SetValue(body,10f);
  motor.airControl=1;motor.moveDirection=Vector3.right;motor.velocity=Vector3.zero;
  Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-1)<.0001f,"First acceleration step");
  for(int i=0;i<9;i++)Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-7)<.0001f,"Speed cap");r.x=motor.velocity.x;
  motor.moveDirection=Vector3.zero;for(int i=0;i<10;i++)Call(motor,"PreMove",.1f);Check(motor.velocity.sqrMagnitude<.000001f,"Braking");
  Check(!host.activeInHierarchy&&host.transform.position==Vector3.zero,"Unexpected activation/translation");
  NetworkServer.UnSpawn(host);
 }
}
