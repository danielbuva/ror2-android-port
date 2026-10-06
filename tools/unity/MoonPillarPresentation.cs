using System;
using System.Linq;
using RoR2;
using UnityEngine;

// Read original selected batteries and FX activation. Presentation never writes
// charge, selection, mission state, collider/layer, interaction or player motion.
public sealed partial class MovementBatchProbe {
 [Serializable] public class MoonPillarMarker {
  public string name,state;public Vector3 position;public float charge,distance;public bool complete;
 }
 [Serializable] public class MoonElevatorLaunch {
  public bool active;public Vector3 position,velocity,target,predictedArrival;public float flightTime,targetError;
 }
 static bool IsMoonPillarBeam(Renderer renderer){
  if(!(renderer is ParticleSystemRenderer)||!renderer.name.StartsWith("Beam")||!renderer.transform.parent)return false;
  var parent=renderer.transform.parent.name;return parent=="InactiveFX"||parent=="ChargingFX"||parent=="ChargedFX";
 }
 void ObserveMoonPillarMarkers(HoldoutZoneController[] batteries){
  r.moon.pillarMarkers=batteries.Select(z=>{
   var state=z.GetComponent<EntityStateMachine>().state;
   return new MoonPillarMarker{name=z.name.Replace("MoonBattery",""),position=z.transform.position,charge=z.charge,
    state=state is EntityStates.Missions.Moon.MoonBatteryComplete?"Complete":state is EntityStates.Missions.Moon.MoonBatteryActive?"Charging":"Ready",
    complete=state is EntityStates.Missions.Moon.MoonBatteryComplete,distance=worldPlayer?Vector3.Distance(worldPlayer.transform.position,z.transform.position):0};
  }).ToArray();
  var beams=moonRoots.SelectMany(x=>x.GetComponentsInChildren<ParticleSystemRenderer>(true)).Where(x=>IsMoonPillarBeam(x)).ToArray();
  r.moon.restoredBeamRenderers=beams.Length;r.moon.activeBeamRenderers=beams.Count(x=>x.enabled&&x.gameObject.activeInHierarchy);
  r.moon.liveBeamParticles=beams.Where(x=>x.gameObject.activeInHierarchy).Sum(x=>x.GetComponent<ParticleSystem>().particleCount);
  r.moon.observedGravityY=Physics.gravity.y;
  r.moon.elevatorLaunches=moonRoots.SelectMany(x=>x.GetComponentsInChildren<JumpVolume>(true)).Select(x=>{
   var predicted=x.transform.position+x.jumpVelocity*x.time+Physics.gravity*(.5f*x.time*x.time);
   var target=x.targetElevationTransform?x.targetElevationTransform.position:Vector3.zero;
   return new MoonElevatorLaunch{active=x.enabled&&x.gameObject.activeInHierarchy,position=x.transform.position,velocity=x.jumpVelocity,target=target,predictedArrival=predicted,flightTime=x.time,targetError=Vector3.Distance(predicted,target)};
  }).ToArray();
 }
 void DrawMoonPillarMarkers(){
  if(r.moon==null||!r.moon.loaded||r.moon.cleaned||r.moon.pillarMarkers==null||worldView==null||!worldPlayer)return;
  var style=new GUIStyle(GUI.skin.label){fontSize=18,alignment=TextAnchor.MiddleCenter};
  int index=0;
  foreach(var marker in r.moon.pillarMarkers){
   index++;var projected=worldView.ProjectWorldPoint(marker.position+Vector3.up*10);
   var direction=new Vector2(projected.x-Screen.width*.5f,Screen.height*.5f-projected.y);
   if(projected.z<0)direction=-direction;
   bool edge=projected.z<=0||Mathf.Abs(direction.x)>Screen.width*.5f-115||Mathf.Abs(direction.y)>Screen.height*.5f-50;
   if(edge){if(direction.sqrMagnitude<.01f)direction=Vector2.up;float extentX=Screen.width*.5f-115,extentY=Screen.height*.5f-50;direction*=Mathf.Min(extentX/Mathf.Max(.01f,Mathf.Abs(direction.x)),extentY/Mathf.Max(.01f,Mathf.Abs(direction.y)));}
   var rect=new Rect(Screen.width*.5f+direction.x-105,Screen.height*.5f+direction.y-24,210,48);
   string arrow=edge?(Mathf.Abs(direction.x)>Mathf.Abs(direction.y)?direction.x>0?"> ":"< ":direction.y>0?"v ":"^ "):"";
   GUI.Box(rect,GUIContent.none);style.normal.textColor=marker.complete?Color.green:marker.state=="Charging"?Color.yellow:Color.white;
   string status=marker.state=="Charging"?"Charging "+(marker.charge*100).ToString("F0")+"%":marker.state;
   GUI.Label(rect,arrow+index+" "+marker.name+" · "+marker.distance.ToString("F0")+"m\n"+status,style);
  }
 }
}
