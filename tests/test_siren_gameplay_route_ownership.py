"""Host checks for the authored Siren diagnostic route owner."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/input"
FIXTURES = ROOT / "tests/fixtures"
UNITY = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
MONO = UNITY / "bin/mono"
CSC = UNITY / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


def declaration(source, name):
    start = source.index(name)
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise AssertionError("unclosed declaration: " + name)


class SirenGameplayRouteOwnershipTests(unittest.TestCase):
    def test_owner_policy_and_recorder_execute_under_pinned_host_compiler(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("Pinned Unity Mono/Roslyn host compiler unavailable")
        source = (SOURCE / "SirenNavigationObservation.cs").read_text()
        names = (
            "public struct SirenNavigationObservationSample",
            "public sealed class SirenNavigationObservationReport",
            "public static class SirenNavigationObservationPolicy",
            "public interface ISirenNavigationObservationReader",
            "public sealed class SirenNavigationObservationRecorder",
        )
        declarations = [declaration(source, name) for name in names]
        stubs = (
            "namespace UnityEngine { "
            "public struct Vector2 { public float x,y; public Vector2(float x,float y){this.x=x;this.y=y;} "
            "public static Vector2 zero => new Vector2(0,0); } "
            "public struct Vector3 { public float x,y,z; } }\n"
        )
        host = (
            "using System;\nusing UnityEngine;\nnamespace RoR2 {}\n"
            + stubs
            + "\n".join(declarations)
            + (FIXTURES / "siren_gameplay_route_ownership_host.cs").read_text()
        )
        with tempfile.TemporaryDirectory(prefix="siren-route-host-") as temporary:
            directory = Path(temporary)
            source_path = directory / "SirenGameplayRouteHost.cs"
            executable = directory / "SirenGameplayRouteHost.exe"
            source_path.write_text(host)
            subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:9", "-out:" + str(executable), str(source_path)],
                check=True,
                cwd=directory,
            )
            result = subprocess.run([str(MONO), str(executable)], check=True, cwd=directory, text=True, capture_output=True)
        self.assertIn("siren-navigation-recorder-state-contract-passed", result.stdout)

    def test_selected_siren_frame_suppresses_competing_world_input_only_when_ready(self):
        source = (SOURCE / "NovaInputBoundary.cs").read_text()
        gate = source.index("bool sirenOwnsWorldInput =")
        world_call = source.index("coordinator.IntegratedWorldStimulus(body, bridge, elapsed);")
        after_world_call = source.index("coordinator.EarnedFeatherInput(body, bridge, elapsed);", world_call)
        self.assertLess(gate, world_call)
        self.assertLess(world_call, after_world_call)
        branch = source[gate:after_world_call]
        for required in (
            "coordinator.SirenEggInputSelected",
            "bridge.diagnosticInput",
            "coordinator.IsRunAssisted()",
            "coordinator.worldManualTakeover",
            "coordinator.SirenDiagnosticSceneActive",
            "coordinator.SirenDiagnosticOwnerAttached",
            "coordinator.SirenDiagnosticListenerActive",
            "!coordinator.HasNearbyHostileDirectorThreat(body)",
            "if (sirenOwnsWorldInput)",
        ):
            self.assertIn(required, branch)
        self.assertIn("coordinator.r.world.diagnosticInputEver = true;", branch)
        self.assertIn('coordinator.DebugToggle("diagnosticInput", true, "unattended route");', branch)

    def test_recorder_reads_after_siren_route_and_before_queuing_next_request(self):
        source = (SOURCE / "SirenEggDiagnosticInput.cs").read_text()
        apply = declaration(source, "public bool Apply(CharacterBody player, NovaInputBridge bridge, bool producerFrameFresh)")
        route = apply.index("context.NavigateWorldInput(player, bridge, egg.transform.position")
        pending = apply.index("navigationObservation.ObservePending(")
        queue = apply.index("navigationObservation.QueueRequest(")
        aim_write = apply.index("bridge.aim = new Vector2(aim.x, aim.z).normalized;")
        self.assertLess(route, pending)
        self.assertLess(pending, aim_write)
        self.assertLess(aim_write, queue)
        self.assertIn("context.CreateNavigationObservationReader(player, bridge)", apply[pending:queue])

    def test_navigation_request_writer_and_reader_use_stage_relative_clock(self):
        siren = (SOURCE / "SirenEggDiagnosticInput.cs").read_text()
        interface = declaration(siren, "public interface ISirenEggDiagnosticContext")
        self.assertIn("float StageElapsed { get; }", interface)
        call = declaration(siren, "public bool Apply(CharacterBody player, NovaInputBridge bridge, bool producerFrameFresh)")
        self.assertIn("float stageElapsed = context.StageElapsed;", call)
        self.assertIn('context.NavigateWorldInput(player, bridge, egg.transform.position, StopDistance, "Original Vulture egg", stageElapsed)', call)
        # The unchanged integrated-world adapter passes this elapsed argument
        # through to the route owner, whose existing request timestamp uses that
        # same argument. Sampling after this call prevents an earlier run-clock
        # world route from winning the reader snapshot.


if __name__ == "__main__":
    unittest.main()
