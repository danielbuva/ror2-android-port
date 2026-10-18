using System;
using System.Collections;
using System.IO;
using System.Reflection;
using KinematicCharacterController;
using UnityEngine;

// Supplies diagnostic velocity only. All integration, sweeps, sliding and grounding use the shipped solver.
public sealed class KinematicBatchProbe : MonoBehaviour, ICharacterController {
 [Serializable] public class Result {public string attempt,id,phase,error;public int pid,assertions,hits;public bool success,cleanup,grounded;public float x,y,z;}
 Result r;GameObject host,obstacle;KinematicCharacterMotor motor;Vector3 velocity;
 void Check(bool ok,string message){r.assertions++;if(!ok)throw new Exception(message);}
 void Save(){File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-"+r.id+".json"),JsonUtility.ToJson(r,true));}
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("KinematicBatchProbe"))new GameObject("Kinematic batch observer").AddComponent<KinematicBatchProbe>();}
 IEnumerator Start(){
  yield return new WaitForSeconds(8);var path=System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-selection.json");if(!File.Exists(path))yield break;
  r=JsonUtility.FromJson<Result>(File.ReadAllText(path));var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("KinematicBatchProbe").text);if(r.attempt!=cfg.attempt)yield break;
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))r.pid=process.CallStatic<int>("myPid");
#endif
  r.phase="started";Save();try{Run();r.success=true;}catch(Exception e){r.error=e.ToString();}
  finally{if(host)Destroy(host);if(obstacle)Destroy(obstacle);}
  yield return null;r.cleanup=!host&&!obstacle;r.success&=r.cleanup;r.phase="complete";Save();
 }
 void Run(){
  host=new GameObject("Inactive original kinematic fixture");host.SetActive(false);host.layer=30;host.AddComponent<CapsuleCollider>();motor=host.AddComponent<KinematicCharacterMotor>();
  typeof(KinematicCharacterMotor).GetMethod("Awake",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(motor,null);motor.CharacterController=this;
  motor.SetCapsuleDimensions(.5f,2f,1f);motor.CollidableLayers=1<<30;motor.StableGroundLayers=1<<30;motor.InteractiveRigidbodyHandling=false;motor.SetPosition(new Vector3(0,10,0));
  motor.SetGroundSolvingActivation(false);
  if(r.id=="free"){velocity=Vector3.right*2;Step(50);Check(Mathf.Abs(motor.TransientPosition.x-2)<.001f,"Free displacement differs from two metres");}
  else if(r.id=="wall"||r.id=="slide"){
   Box(new Vector3(2,11,0),new Vector3(1,10,20));velocity=r.id=="wall"?Vector3.right*4:new Vector3(4,0,2);Step(50);
   Check(motor.TransientPosition.x>.9f&&motor.TransientPosition.x<1.01f,"Wall penetration or premature stop");Check(r.hits>0,"No original movement hit callback");
   if(r.id=="slide")Check(motor.TransientPosition.z>1.5f,"Wall tangent motion missing");
  }else if(r.id=="ground"||r.id=="unground"){
   Box(new Vector3(0,9.5f,0),new Vector3(20,1,20));motor.SetPosition(new Vector3(0,10.2f,0));motor.SetGroundSolvingActivation(true);velocity=Vector3.down;Step(30);
   Check(motor.GroundingStatus.IsStableOnGround,"Stable floor not found");Check(Mathf.Abs(motor.TransientPosition.y-10)<.05f,"Floor height mismatch");
   if(r.id=="unground"){motor.ForceUnground(.1f);velocity=Vector3.up*3;Step(20);Check(!motor.GroundingStatus.IsStableOnGround&&motor.TransientPosition.y>10.5f,"Original unground did not leave floor");}
  }else throw new Exception("Unknown kinematic probe");
  r.x=motor.TransientPosition.x;r.y=motor.TransientPosition.y;r.z=motor.TransientPosition.z;r.grounded=motor.GroundingStatus.IsStableOnGround;
  Check(!host.activeInHierarchy,"Unexpected automatic solver lifecycle");
 }
 void Box(Vector3 position,Vector3 size){obstacle=new GameObject("Owned collision fixture");obstacle.layer=30;obstacle.transform.position=position;obstacle.AddComponent<BoxCollider>().size=size;Physics.SyncTransforms();}
 void Step(int count){for(int i=0;i<count;i++){motor.UpdatePhase1(.02f,true);motor.UpdatePhase2(.02f,true);motor.SetPositionAndRotation(motor.TransientPosition,motor.TransientRotation);}}
 public void SetupCharacterMotor(KinematicCharacterMotor value){motor=value;}
 public void UpdateRotation(ref Quaternion q,float dt){}
 public void UpdateVelocity(ref Vector3 v,float dt){v=velocity;}
 public void BeforeCharacterUpdate(float dt){}
 public void PostGroundingUpdate(float dt){}
 public void AfterCharacterUpdate(float dt){}
 public bool IsColliderValidForCollisions(Collider c){return c.gameObject==obstacle;}
 public void OnGroundHit(Collider c,Vector3 n,Vector3 p,ref HitStabilityReport s){r.hits++;}
 public void OnMovementHit(Collider c,Vector3 n,Vector3 p,ref HitStabilityReport s){r.hits++;}
 public void ProcessHitStabilityReport(Collider c,Vector3 n,Vector3 p,Vector3 position,Quaternion rotation,ref HitStabilityReport s){}
 public void OnDiscreteCollisionDetected(Collider c){}
}
