using System;
using RoR2;
using UnityEngine;

// Android view/input adapter. Original camera parameters/recoil and character simulation
// remain original; no LocalUser, platform session or stock CameraRig is fabricated.
public sealed class NovaThirdPersonView {
 [Serializable] public class Report {
  public bool perspective,originalParams,relativeMovement,rayAim;
  public string parameters;public int frames,collisions,physicalFrames,lookFrames;
  public float yaw,pitch,distance,minDistance=999,maxDistance,maxAimError;
  public Vector3 position,direction,move;public float fov;
 }
 public readonly Report report=new Report();
 public Vector3 ProjectWorldPoint(Vector3 point){return camera.WorldToScreenPoint(point);}
 public void MoonVisibility(bool active){camera.farClipPlane=active?3000:600;}
 readonly Camera camera;readonly CharacterBody body;readonly CameraTargetParams target;
 readonly RaycastHit[] hits=new RaycastHit[64];float yaw,pitch=15;
 public NovaThirdPersonView(Camera camera,CharacterBody body){
  this.camera=camera;this.body=body;target=body.GetComponent<CameraTargetParams>();
  if(!target||!target.cameraParams)throw new Exception("Original Commando camera parameters missing");
  target.enabled=true;camera.orthographic=false;camera.nearClipPlane=.05f;camera.farClipPlane=600;
  yaw=body.characterDirection.yaw;report.parameters=target.cameraParams.name;report.originalParams=true;report.perspective=true;
  Place();
 }
 public void Look(Vector2 stick){
  report.physicalFrames++;if(stick.sqrMagnitude>0)report.lookFrames++;
  yaw+=stick.x*180*Time.deltaTime;pitch-=stick.y*120*Time.deltaTime;
  Place();
 }
 public Vector3 Movement(Vector2 stick){
  var rotation=Quaternion.Euler(0,yaw,0);var vector=rotation*new Vector3(stick.x,0,stick.y);
  report.relativeMovement=true;report.move=vector;return vector;
 }
 public Vector3 Aim(){
  var ray=camera.ViewportPointToRay(new Vector3(.5f,.5f,0));var point=ray.origin+ray.direction*500;float closest=500;
  int count=Physics.RaycastNonAlloc(ray,hits,500,LayerIndex.world.mask|LayerIndex.entityPrecise.mask,QueryTriggerInteraction.Ignore);
  for(int i=0;i<count;i++){var hit=hits[i];if(!hit.collider||hit.collider.transform.IsChildOf(body.transform)||hit.distance>=closest)continue;closest=hit.distance;point=hit.point;}
  var direction=(point-body.inputBank.aimOrigin).normalized;report.rayAim=true;report.direction=direction;return direction;
 }
 public void DiagnosticDirection(Vector3 direction){
  // The integrated replay supplies original world-space input, independent of the physical orbit.
  if(direction.sqrMagnitude>.001f){yaw=Mathf.Atan2(direction.x,direction.z)*Mathf.Rad2Deg;pitch=Mathf.Clamp(-Mathf.Asin(direction.normalized.y)*Mathf.Rad2Deg,-35,45);}
  Place();
 }
 public void Place(){
  if(!body||!target)return;CharacterCameraParamsData data;target.CalcParams(out data);
  pitch=Mathf.Clamp(pitch,data.minPitch.value,data.maxPitch.value);var rotation=Quaternion.Euler(pitch+target.recoil.x,yaw+target.recoil.y,0);
  var pivot=body.transform.position+Vector3.up*data.pivotVerticalOffset.value;
  var offset=rotation*data.idealLocalCameraPos.value;float wanted=offset.magnitude;
  if(wanted<.5f)throw new Exception("Original third-person camera offset invalid");
  RaycastHit hit;float distance=wanted;
  if(Physics.SphereCast(pivot,.2f,offset/wanted,out hit,wanted,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)){distance=Mathf.Max(.35f,hit.distance-Mathf.Max(.05f,data.wallCushion.value));report.collisions++;}
  camera.transform.SetPositionAndRotation(pivot+offset/wanted*distance,rotation);
  camera.fieldOfView=data.fov.alpha>0&&data.fov.value>1?data.fov.value:CharacterCameraParamsData.basic.fov.value;
  report.frames++;report.yaw=yaw;report.pitch=pitch;report.distance=distance;report.minDistance=Mathf.Min(report.minDistance,distance);report.maxDistance=Mathf.Max(report.maxDistance,distance);report.position=camera.transform.position;report.fov=camera.fieldOfView;
 }
 public void DrawReticle(){var color=GUI.color;GUI.color=Color.white;GUI.DrawTexture(new Rect(Screen.width*.5f-7,Screen.height*.5f-1,14,2),Texture2D.whiteTexture);GUI.DrawTexture(new Rect(Screen.width*.5f-1,Screen.height*.5f-7,2,14),Texture2D.whiteTexture);GUI.color=color;}
}
