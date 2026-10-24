"""Execute the production automatic-mobility admission with synthetic geometry."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def member(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for i in range(opening, len(source)):
        depth += (source[i] == "{") - (source[i] == "}")
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(signature)


STUBS = r"""
using System;
using System.Collections.Generic;
using UnityEngine;
namespace UnityEngine {
 public class Object { public static implicit operator bool(Object x) { return x != null; } }
 public struct Vector3 {
  public float x,y,z; public Vector3(float x,float y,float z) { this.x=x;this.y=y;this.z=z; }
  public static Vector3 zero=>new Vector3(); public static Vector3 up=>new Vector3(0,1,0);
  public static Vector3 down=>new Vector3(0,-1,0); public static Vector3 right=>new Vector3(1,0,0);
  public static Vector3 left=>new Vector3(-1,0,0); public static Vector3 forward=>new Vector3(0,0,1);
  public static Vector3 back=>new Vector3(0,0,-1);
  public Vector3 normalized { get { float n=(float)Math.Sqrt(x*x+y*y+z*z); return n>0?this*(1/n):zero; } }
  public static Vector3 operator +(Vector3 a,Vector3 b)=>new Vector3(a.x+b.x,a.y+b.y,a.z+b.z);
  public static Vector3 operator *(Vector3 a,float b)=>new Vector3(a.x*b,a.y*b,a.z*b);
  public static float Angle(Vector3 a,Vector3 b) { a=a.normalized;b=b.normalized;return (float)(Math.Acos(a.x*b.x+a.y*b.y+a.z*b.z)*180/Math.PI); }
 }
 public struct Quaternion { public Vector3 forward; public static Vector3 operator *(Quaternion q,Vector3 a)=>new Vector3(q.forward.z*a.x+q.forward.x*a.z,a.y,-q.forward.x*a.x+q.forward.z*a.z); }
 public static class Mathf { public static float Max(float a,float b)=>Math.Max(a,b);public static float Abs(float a)=>Math.Abs(a); }
 public class GameObject { public int scene=1; }
 public class Collider { public GameObject gameObject=new GameObject(); }
 public struct RaycastHit { public Collider collider;public Vector3 point,normal; }
 public enum QueryTriggerInteraction { Ignore }
 public static class Physics {
  public static Func<Vector3,RaycastHit?> Sample;public static List<Vector3> Origins=new List<Vector3>();
  public static bool Raycast(Vector3 p,Vector3 direction,out RaycastHit hit,float depth,int mask,QueryTriggerInteraction triggers) {
   Origins.Add(p);var value=Sample==null?null:Sample(p);hit=value.GetValueOrDefault();return value.HasValue;
  }
 }
}
namespace EntityStates { public class EntityState {} namespace Huntress {
 public class BlinkState:EntityState { public static int Created;public BlinkState(){Created++;}public float duration=.4f,speedCoefficient=2; }
 public class BeginArrowRain:EntityState {public static int Created;public BeginArrowRain(){Created++;}public Vector3 blinkVector=Vector3.up;public float jumpCoefficient=2,blinkDuration=.5f;}
}}
public static class Util {public static Quaternion QuaternionSafeLookRotation(Vector3 aim,Vector3 up)=>new Quaternion{forward=aim};}
public static class LayerIndex {public static class world {public const int mask=1;}}
public class SlotState {public Type stateType;}
public class SkillDef:UnityEngine.Object {public SlotState activationState=new SlotState();}
public class GenericSkill:UnityEngine.Object {public SkillDef skillDef=new SkillDef();}
public class SkillLocator:UnityEngine.Object {public GenericSkill utility=new GenericSkill(),special=new GenericSkill();}
public class Capsule {public float radius=.5f;}
public class Motor {public Capsule Capsule=new Capsule();public float MaxStableSlopeAngle=70;}
public class CharacterMotor {public bool isGrounded=true;public Motor Motor=new Motor();}
public class CharacterBody:UnityEngine.Object {
 public CharacterMotor characterMotor=new CharacterMotor();public SkillLocator skillLocator=new SkillLocator();
 public float moveSpeed=10,baseJumpPower=8,maxJumpHeight=4;public Vector3 temporaryPathfindingFootpositionDoNotUseWillBePatchedOut;
}
public class NovaInputBridge:UnityEngine.Object {public bool diagnosticInput=true,diagnosticUtility,diagnosticSpecial,diagnosticPrimary=true,diagnosticSecondary=true;public Vector3 diagnosticAim=Vector3.right;}
public class Report {public int combatMobilityChecks,combatMobilityRejectedRequests;public string combatMobilityLastRejection;}
public class Runtime {public Report world=new Report();}
public class Coordinator {public Runtime r=new Runtime();public int stageGeometryScene=1;public bool inside=true;public bool InsideSourceStageBounds(Vector3 p)=>inside;}
public class Harness {
 readonly Coordinator coordinator=new Coordinator();
 EntityStates.Huntress.BlinkState diagnosticBlink;
 EntityStates.Huntress.BeginArrowRain diagnosticArrowRain;
 MEMBERS
 static void Assert(bool yes,string why) {if(!yes)throw new Exception(why);}
 static RaycastHit Floor(Vector3 p,int scene=1,float y=0) {return new RaycastHit{collider=new Collider{gameObject=new GameObject{scene=scene}},point=new Vector3(p.x,y,p.z),normal=Vector3.up};}
 void Run() {
  var player=new CharacterBody();var bridge=new NovaInputBridge{diagnosticUtility=true};
  player.skillLocator.utility.skillDef.activationState.stateType=typeof(EntityStates.Huntress.BlinkState);
  player.skillLocator.special.skillDef.activationState.stateType=typeof(EntityStates.Huntress.BeginArrowRain);
  Physics.Sample=p=>Floor(p);ApplyWorldMobilityLanding(player,bridge);
  Assert(bridge.diagnosticUtility&&Physics.Origins.Count==5&&Math.Abs(Physics.Origins[0].x-8)<.001,"configured Blink displacement and five-point footprint");
  for(int i=0;i<30;i++)ApplyWorldMobilityLanding(player,bridge);
  Assert(EntityStates.Huntress.BlinkState.Created==1,"rejected/ready requests must not allocate native states per tick");
  Assert(diagnosticBlink.duration==.4f&&diagnosticBlink.speedCoefficient==2,"native template fields unchanged");
  Physics.Sample=null;ApplyWorldMobilityLanding(player,bridge);
  Assert(!bridge.diagnosticUtility&&bridge.diagnosticPrimary&&bridge.diagnosticSecondary,"missing floor releases only requested mobility");
  Assert(coordinator.r.world.combatMobilityLastRejection=="no supported source landing","explicit rejection evidence");
  bridge.diagnosticUtility=true;player.characterMotor.isGrounded=false;int before=Physics.Origins.Count;ApplyWorldMobilityLanding(player,bridge);
  Assert(!bridge.diagnosticUtility&&Physics.Origins.Count==before,"airborne request does not query/guess floor");
  bridge.diagnosticInput=false;bridge.diagnosticUtility=true;ApplyWorldMobilityLanding(player,bridge);
  Assert(bridge.diagnosticUtility,"manual input unchanged");bridge.diagnosticInput=true;player.characterMotor.isGrounded=true;
  foreach(int scene in new[]{2,1}) {Physics.Sample=p=>Floor(p,scene,-6);bridge.diagnosticUtility=true;ApplyWorldMobilityLanding(player,bridge);Assert(!bridge.diagnosticUtility,"foreign scene or deep drop rejected");}
  Physics.Sample=p=>{var hit=Floor(p);hit.normal=Vector3.right;return hit;};bridge.diagnosticUtility=true;ApplyWorldMobilityLanding(player,bridge);Assert(!bridge.diagnosticUtility,"unstable slope rejected");
  Physics.Sample=p=>Floor(p);coordinator.inside=false;bridge.diagnosticUtility=true;ApplyWorldMobilityLanding(player,bridge);Assert(!bridge.diagnosticUtility,"source bounds preserved");coordinator.inside=true;
  Physics.Sample=p=>p.x>8.4f?(RaycastHit?)null:Floor(p);bridge.diagnosticUtility=true;ApplyWorldMobilityLanding(player,bridge);Assert(!bridge.diagnosticUtility,"center-only ledge is not a landing footprint");
  Physics.Sample=p=>Floor(p);player.moveSpeed=float.NaN;bridge.diagnosticUtility=true;ApplyWorldMobilityLanding(player,bridge);Assert(!bridge.diagnosticUtility,"invalid source displacement rejected");player.moveSpeed=10;
  bridge.diagnosticUtility=false;bridge.diagnosticSpecial=true;ApplyWorldMobilityLanding(player,bridge);ApplyWorldMobilityLanding(player,bridge);
  Assert(bridge.diagnosticSpecial&&EntityStates.Huntress.BeginArrowRain.Created==1,"configured original vertical leap and bounded template");
  player.skillLocator.utility.skillDef.activationState.stateType=typeof(object);Physics.Sample=null;bridge.diagnosticUtility=true;bridge.diagnosticSpecial=false;ApplyWorldMobilityLanding(player,bridge);Assert(bridge.diagnosticUtility,"other survivor/state policies unchanged");
 }
 public static void Main(){new Harness().Run();Console.WriteLine("PASS automatic mobility source landing");}
}
"""


class WorldMobilityLandingTests(unittest.TestCase):
    def test_production_admission(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("exact editor Mono/Roslyn unavailable")
        source = (ROOT / "tools/unity/runtime/stage/TeleporterWorldBoundary.cs").read_text()
        methods = "\n".join(
            member(source, signature)
            for signature in (
                "public void ApplyWorldMobilityLanding(",
                "static Vector3 DiagnosticMobilityOffset(",
                "bool WorldMobilityHasLanding(",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "Fixture.cs"
            path.write_text(STUBS.replace("MEMBERS", methods))
            assembly = root / "Fixture.exe"
            compiled = subprocess.run([str(mono), str(csc), "/nologo", "/out:" + str(assembly), str(path)], text=True, capture_output=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(mono), str(assembly)], text=True, capture_output=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS automatic mobility source landing", ran.stdout)


if __name__ == "__main__":
    unittest.main()
