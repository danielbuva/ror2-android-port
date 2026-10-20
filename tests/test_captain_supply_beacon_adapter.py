"""Execute production Captain runtime-adapter helpers with host collaborators."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs"
UNITY = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))

STUBS = r"""
using System;
public struct NetworkInstanceId { public uint Value; public NetworkInstanceId(uint value){Value=value;}
 public static bool operator ==(NetworkInstanceId a,NetworkInstanceId b)=>a.Value==b.Value;
 public static bool operator !=(NetworkInstanceId a,NetworkInstanceId b)=>a.Value!=b.Value;
 public override bool Equals(object o)=>o is NetworkInstanceId n&&n.Value==Value; public override int GetHashCode()=>(int)Value; }
public sealed class GameObject { public bool alive=true; public static implicit operator bool(GameObject x)=>x!=null&&x.alive; }
public sealed class CharacterBody { public bool alive=true; public CharacterMaster master; public static implicit operator bool(CharacterBody x)=>x!=null&&x.alive; }
public sealed class CharacterMaster { public int instanceId; public NetworkInstanceId netId; public bool isServer,hasBody,alive=true; public GameObject gameObject; public CharacterBody body;
 public int GetInstanceID()=>instanceId; public CharacterBody GetBody()=>body; public static implicit operator bool(CharacterMaster x)=>x!=null&&x.alive; }
public static class NetworkServer { public static object mapped; public static object FindLocalObject(NetworkInstanceId id)=>mapped; }
"""

FIXTURE = r"""
public static class AdapterHarness
{
 static void Need(bool value,string name){if(!value)throw new Exception(name);}
 public static void Main()
 {
  var report=new SurvivorSkillInputCoverage.Report();
  bool current=SurvivorSkillInputCoverage.UpdateCaptainPlacementWitness(true,true,report);
  Need(current&&report.captainSupplyBeaconPlacementValid,"valid current placement and report latch");
  current=SurvivorSkillInputCoverage.UpdateCaptainPlacementWitness(false,false,report);
  Need(!current&&report.captainSupplyBeaconPlacementValid&&
    report.captainSupplyBeaconPlacementObservation=="native-setup-placement-valid",
    "placement report must retain positive witness while policy sees current false");

  report=new SurvivorSkillInputCoverage.Report();
  SurvivorSkillInputCoverage.CaptureCaptainCallbackBaselinesForRequest(0,0,0,0,0,report);
  int callbackAuthority=1, callbackServer=1;
  Need(report.captainSupplyAuthorityBefore==0&&report.captainSupplyServerBefore==0&&
    callbackAuthority>report.captainSupplyAuthorityBefore&&callbackServer>report.captainSupplyServerBefore,
    "zero baseline must survive the subsequent zero-to-one native callbacks");
  SurvivorSkillInputCoverage.CaptureCaptainCallbackBaselinesForRequest(3,1,1,callbackAuthority,callbackServer,report);
  Need(report.captainSpecialAuthorityBefore==1&&report.captainSpecialServerBefore==1&&
    report.captainSupplyAuthorityBefore==0&&report.captainSupplyServerBefore==0,
    "special request must not replace the supply callback snapshot");

  var originalMaster=new CharacterMaster{instanceId=31,netId=new NetworkInstanceId(41),isServer=true,hasBody=true,gameObject=new GameObject()};
  var body=new CharacterBody{master=originalMaster}; originalMaster.body=body; NetworkServer.mapped=originalMaster.gameObject;
  Need(SurvivorSkillInputCoverage.CaptainMasterIdentityMatches(body,originalMaster,31,new NetworkInstanceId(41),originalMaster.gameObject),
    "exact reciprocal master identity");
  body.master=new CharacterMaster{instanceId=32,netId=new NetworkInstanceId(42),isServer=true,hasBody=true,gameObject=new GameObject(),body=body};
  Need(!SurvivorSkillInputCoverage.CaptainMasterIdentityMatches(body,originalMaster,31,new NetworkInstanceId(41),originalMaster.gameObject),
    "replacement master must be refused despite reciprocal body relation");

  var coverage=new SurvivorSkillInputCoverage(); coverage.captainPulseActive=true;
  if(coverage.ObserveCaptainPulseBeforePolicy(1)){coverage.policyCalls++;coverage.requestCalls++;}
  Need(coverage.edgeObserved&&coverage.report.completed&&coverage.policyCalls==0&&coverage.requestCalls==0,
    "terminal edge refusal must stop the frame before policy or a new request");
  Console.WriteLine("captain-production-adapter-regressions-passed");
 }
}
"""


def declaration(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
    raise AssertionError("unterminated " + marker)


class CaptainProductionAdapterTests(unittest.TestCase):
    def test_production_adapters_latch_snapshots_and_stop_after_edge_refusal(self):
        mono = UNITY / "MonoBleedingEdge/bin/mono"
        csc = UNITY / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity Roslyn/Mono unavailable")
        source = OWNER.read_text()
        methods = [
            declaration(source, "public static bool UpdateCaptainPlacementWitness("),
            declaration(source, "public static void CaptureCaptainCallbackBaselinesForRequest("),
            declaration(source, "public static bool CaptainMasterIdentityMatches("),
            declaration(source, "internal bool ObserveCaptainPulseBeforePolicy("),
        ]
        owner = declaration(source, "void ApplyCaptainSupplyBeacon(float elapsed)")
        self.assertIn("captainBeganAt = float.NaN", source)
        self.assertIn("if (!ObserveCaptainPulseBeforePolicy(elapsed)) return;", owner)
        self.assertLess(owner.index("if (!ObserveCaptainPulseBeforePolicy(elapsed)) return;"), owner.index("captainSupplyBeaconSequence.Step(observation)"))
        request_branch = owner.split("if (decision.requestInputSlot >= 0)", 1)[1].split("if (decision.completed || decision.refused)", 1)[0]
        self.assertIn("CaptureCaptainCallbackBaselinesForRequest", request_branch)
        self.assertEqual(owner.count("CaptureCaptainCallbackBaselinesForRequest"), 1)
        self.assertNotIn("captainSupplyBeaconRequests >= 2", owner)
        self.assertNotIn("captainSupplyBeaconSequence.CurrentPhase == CaptainSupplyBeaconSequence.Phase.WaitingForNativeReadiness", owner)
        self.assertIn("captainSupplyBeaconMasterInstanceId", source)
        self.assertIn("CaptainMasterIdentityMatches(body, captainSupplyBeaconMaster", owner)
        code = (
            STUBS
            + "public sealed class SurvivorSkillInputCoverage {\n"
            + "public class Report { public bool captainSupplyBeaconPlacementValid,completed; public string captainSupplyBeaconPlacementObservation; public int captainSpecialAuthorityBefore,captainSpecialServerBefore,captainSupplyAuthorityBefore,captainSupplyServerBefore; }\n"
            + "public Report report=new Report(); public bool captainPulseActive,edgeObserved; public float captainPulseUntil; public int policyCalls,requestCalls; void ObserveCaptainInputBankEdge(){edgeObserved=true;report.completed=true;} void ReleaseCaptainPulse(){captainPulseActive=false;}\n"
            + "\n".join(methods)
            + "\n}\n"
            + FIXTURE
        )
        with tempfile.TemporaryDirectory(prefix="captain-adapter-") as temp:
            root = Path(temp)
            cs = root / "adapter.cs"
            exe = root / "adapter.exe"
            cs.write_text(code)
            compiled = subprocess.run([str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(exe), str(cs)], cwd=root, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            run = subprocess.run([str(mono), str(exe)], cwd=root, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("captain-production-adapter-regressions-passed", run.stdout)
