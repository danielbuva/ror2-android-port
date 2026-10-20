"""Compile authored owner helpers against an authored synthetic lifecycle contract."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "tools/unity/runtime"
UNITY_MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
CSC = UNITY_MONO / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
MONO = UNITY_MONO / "bin/mono"


def extract_method(source: str, declaration: str) -> str:
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated method: {declaration}")


UNITY_CONTRACT = r"""
using System;
using System.Collections.Generic;
using System.Linq;
using RoR2;
namespace UnityEngine {
 public class Object {
   public bool destroyed;
   public static implicit operator bool(Object value) => !ReferenceEquals(value,null) && !value.destroyed;
 }
 public sealed class GameObject : Object {
   readonly List<RoR2.TeamComponent> components = new List<RoR2.TeamComponent>();
   public void Add(RoR2.TeamComponent component) { components.Add(component); component.root=this; }
   public T[] GetComponents<T>() where T:class => components.Where(x=>x is T).Cast<T>().ToArray();
   public void Activate() { foreach(var c in components) if(c && c.enabled) c.InvokeUnityStartOnce(); }
 }
}
namespace RoR2 {
 public sealed class ModelLocator {
   Action listeners;
   public int subscriptions, removals;
   public event Action Changed { add { listeners+=value; subscriptions++; } remove { listeners-=value; removals++; } }
   public void Raise() { listeners?.Invoke(); }
 }
 public sealed class TeamComponent : UnityEngine.Object {
   public UnityEngine.GameObject root;
   public bool enabled, started;
   public int setupCalls, modelChanges;
   public ModelLocator modelLocator;
   public void InvokeUnityStartOnce() {
     if(started) return;
     started=true;
     setupCalls++;
     modelLocator.Changed += OnModelChanged;
   }
   void OnModelChanged() { modelChanges++; }
   public void Destroy() { modelLocator.Changed -= OnModelChanged; destroyed=true; }
 }
 public sealed class CharacterBody : UnityEngine.Object {
   readonly UnityEngine.GameObject root;
   public CharacterBody(UnityEngine.GameObject root) { this.root=root; }
   public T[] GetComponents<T>() where T:class => root.GetComponents<T>();
 }
}
"""


class AuthoredLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CSC.is_file() or not MONO.is_file():
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn unavailable")
        spawn = (RUNTIME / "world/AutomaticSpawnBoundary.cs").read_text()
        owner = (RUNTIME / "world/TeamIndicatorQueueBoundary.cs").read_text()
        port = (RUNTIME / "session/PortSession.cs").read_text()
        cls.production = "\n".join(
            [
                extract_method(
                    spawn,
                    "internal static TeamComponent[] CaptureEnabledRootTeamComponents(CharacterBody body)",
                ),
                extract_method(
                    spawn,
                    "internal static int RestoreCapturedEnabledRootTeamComponents(TeamComponent[] captured, bool integratedWorld)",
                ),
                extract_method(
                    owner,
                    "internal static bool DispatchOriginalIndicatorQueueOnce(bool nativeApplicationActive",
                ),
                extract_method(
                    port,
                    "internal static void RecordPrimarySessionFailure(SessionReport report, Exception error)",
                ),
                extract_method(
                    port,
                    "internal static void CompleteSuccessfulSession(SessionReport report)",
                ),
            ]
        )

    def test_integrated_capture_restore_and_authored_unity_lifecycle(self):
        harness = (
            UNITY_CONTRACT
            + r"""
public sealed class SessionReport { public bool success; public string error, firstFailure, firstFailurePhase, phase; }
public static class PortSession {
"""
            + self.production
            + r"""
}
public static class Program {
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static void Main(){
   var root=new UnityEngine.GameObject(); var locator=new RoR2.ModelLocator();
   var body=new RoR2.CharacterBody(root);
   var enabled=new RoR2.TeamComponent { enabled=true, modelLocator=locator }; root.Add(enabled);
   var disabled=new RoR2.TeamComponent { enabled=false, modelLocator=locator }; root.Add(disabled);
   var foreignRoot=new UnityEngine.GameObject(); var foreign=new RoR2.TeamComponent { enabled=true, modelLocator=new RoR2.ModelLocator() }; foreignRoot.Add(foreign);
   var captured=PortSession.CaptureEnabledRootTeamComponents(body);
   Need(captured.Length==1 && Object.ReferenceEquals(captured[0],enabled),"capture is source-enabled and root-local");
   enabled.enabled=false;
   Need(PortSession.RestoreCapturedEnabledRootTeamComponents(captured,false)==0 && !enabled.enabled,"non-integrated path does not restore");
   Need(PortSession.RestoreCapturedEnabledRootTeamComponents(captured,true)==1 && enabled.enabled,"integrated path restores captured owner");
   Need(!disabled.enabled && foreign.enabled,"source-disabled and foreign owners retain state");
   root.Activate();
   Need(enabled.started && enabled.setupCalls==1 && locator.subscriptions==1,"Unity-like activation invokes one authored Start/setup/subscription");
   locator.Raise(); Need(enabled.modelChanges==1,"model changes reach the synthetic subscription");
   root.Activate(); Need(enabled.setupCalls==1 && locator.subscriptions==1,"repeat activation does not duplicate Start");
   enabled.Destroy(); Need(locator.removals==1,"synthetic teardown removes exactly its subscription");
   locator.Raise(); Need(enabled.modelChanges==1,"teardown prevents later model notifications");
   var lateRoot=new UnityEngine.GameObject(); var lateBody=new RoR2.CharacterBody(lateRoot);
   var late=new RoR2.TeamComponent { enabled=true, modelLocator=new RoR2.ModelLocator() }; lateRoot.Add(late);
   var lateCapture=PortSession.CaptureEnabledRootTeamComponents(lateBody); late.destroyed=true;
   Need(PortSession.RestoreCapturedEnabledRootTeamComponents(lateCapture,true)==0,"fake-null captured object is skipped");
   Need(PortSession.CaptureEnabledRootTeamComponents(null).Length==0,"missing body yields empty capture");
   Console.WriteLine("authored_lifecycle_contract=pass; start=1; subscription=1; teardown=1; root/source-enabled/fake-null=pass");
 }
}
"""
        )
        self.run_harness(harness, "authored_lifecycle_contract=pass")

    def test_dispatch_failure_and_completion_are_first_failure_wins(self):
        harness = (
            UNITY_CONTRACT
            + r"""
public sealed class SessionReport { public bool success; public string error, firstFailure, firstFailurePhase, phase; }
public static class PortSession {
"""
            + self.production
            + r"""
}
public static class Program {
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static void Main(){
   int calls=0; Exception first=null; var report=new SessionReport { phase="indicator-fixed-tick" };
   var thrown=new InvalidOperationException("synthetic processor failure");
   bool ok=PortSession.DispatchOriginalIndicatorQueueOnce(false,false,()=>{calls++;throw thrown;},e=>PortSession.RecordPrimarySessionFailure(report,e),ref first);
   Need(!ok && calls==1 && Object.ReferenceEquals(first,thrown),"dispatch failure identity retained");
   Need(report.firstFailure=="synthetic processor failure" && report.firstFailurePhase=="indicator-fixed-tick" && !report.success,"first phase/detail recorded");
   Need(!PortSession.DispatchOriginalIndicatorQueueOnce(false,false,()=>calls++,e=>{},ref first) && calls==1,"latched owner does not retry");
   try { PortSession.CompleteSuccessfulSession(report); throw new Exception("expected completion refusal"); }
   catch(InvalidOperationException) { }
   Need(!report.success,"completion cannot overwrite earlier failure");
   int gated=0; Exception noFailure=null;
   Need(!PortSession.DispatchOriginalIndicatorQueueOnce(true,false,()=>gated++,e=>{},ref noFailure) && gated==0,"active native application retains dispatcher ownership");
   Need(!PortSession.DispatchOriginalIndicatorQueueOnce(false,true,()=>gated++,e=>{},ref noFailure) && gated==0,"existing session failure suppresses dispatch");
   Need(PortSession.DispatchOriginalIndicatorQueueOnce(false,false,()=>gated++,e=>{},ref noFailure) && gated==1,"inactive healthy path calls original processor once");
   var success=new SessionReport(); PortSession.CompleteSuccessfulSession(success); Need(success.success,"clean session completes");
   Console.WriteLine("first_failure_contract=pass; retry=0; native_active_gate=pass; success_overwrite=refused");
 }
}
"""
        )
        self.run_harness(harness, "first_failure_contract=pass")

    def run_harness(self, source_text: str, expected: str):
        scratch_root = ROOT / "work/host-tests"
        scratch_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="team-indicator-", dir=scratch_root) as directory:
            scratch = Path(directory)
            source = scratch / "OwnerContractHost.cs"
            output = scratch / "OwnerContractHost.exe"
            source.write_text(source_text)
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:9",
                    "-out:" + str(output),
                    str(source),
                ],
                cwd=scratch,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(MONO), str(output)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn(expected, executed.stdout)


class RuntimeWiringContracts(unittest.TestCase):
    def test_lifecycle_order_native_gate_and_j787_cleanup_remain(self):
        spawn = (RUNTIME / "world/AutomaticSpawnBoundary.cs").read_text()
        director = (RUNTIME / "world/AutomaticDirectorBoundary.cs").read_text()
        owner = (RUNTIME / "world/TeamIndicatorQueueBoundary.cs").read_text()
        cleanup = (ROOT / "tools/unity/runtime/session/SessionResourceBoundary.cs").read_text()
        capture = spawn.index("CaptureEnabledRootTeamComponents(body)")
        blanket = spawn.index("component.enabled = false;", capture)
        restore = spawn.index("RestoreCapturedEnabledRootTeamComponents(sourceEnabledRootTeamComponents, cfg.integratedWorld)")
        clear = spawn.index("sourceEnabledRootTeamComponents = null;", restore)
        activate = spawn.index("body.gameObject.SetActive(true);", clear)
        yield_line = spawn.index("yield return null;", activate)
        self.assertLess(capture, blanket)
        self.assertLess(blanket, restore)
        self.assertLess(restore, clear)
        self.assertLess(clear, activate)
        self.assertLess(activate, yield_line)
        self.assertIn(
            "restoredSourceEnabledStateMachines + restoredSourceEnabledRootTeamComponents",
            spawn,
        )
        fixed = director[director.index("void FixedUpdate()") :]
        self.assertLess(
            fixed.index("TickTeamIndicatorQueue();"),
            fixed.index("GetAutomaticDirectorSession().FixedUpdate();"),
        )
        self.assertIn("nativeApplication && nativeApplication.isActiveAndEnabled", owner)
        self.assertIn("BindingFlags.Static | BindingFlags.NonPublic", owner)
        self.assertIn("ProcessIndicatorSetupRequests", owner)
        self.assertIn("PruneDestroyedOriginalRegistries", cleanup)
        self.assertIn("indicatorSetupQueue", cleanup)
        body = spawn[spawn.index("IEnumerator AutomaticSpawnBoundary(") :]
        body = body[: body.index("        try\n")]
        self.assertNotIn(".Start()", body)
        self.assertNotIn("TeamComponent.Init", body)
        self.assertNotIn("OnModelChanged", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
