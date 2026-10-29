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
    def test_siren_and_combat_navigation_share_world_clock(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("Pinned Unity Mono/Roslyn host compiler unavailable")
        source = (SOURCE.parent / "world/IntegratedWorldBoundary.cs").read_text()
        context = declaration(source, "sealed class IntegratedWorldSirenContext")
        start = context.index("public void NavigateWorldInput(")
        adapter = context[start : context.index(";", start) + 1]
        host = (
            """
using System;
class CharacterBody {} class NovaInputBridge {} struct Vector3 {}
class World { public float seconds; }
class Report { public World world = new World(); }
class Coordinator {
    public Report r = new Report(); public float captured;
    public void NavigateWorldInput(CharacterBody p, NovaInputBridge b, Vector3 v,
        float d, string n, float elapsed) { captured = elapsed; }
}
class Adapter {
    public Coordinator coordinator = new Coordinator();
"""
            + adapter
            + """
    static void Main() {
        var owner = new Adapter();
        // Siren -> ordinary combat -> Siren must not rewind shared timers.
        foreach (float world in new float[] {700, 701, 704}) {
            owner.coordinator.r.world.seconds = world;
            owner.NavigateWorldInput(null, null, new Vector3(), 1,
                "Original Vulture egg", world - 520);
            if (owner.coordinator.captured != world)
                throw new Exception("Siren rewound the shared navigation clock");
        }
    }
}
"""
        )
        with tempfile.TemporaryDirectory(prefix="siren-clock-host-") as temporary:
            directory = Path(temporary)
            source_path = directory / "Clock.cs"
            executable = directory / "Clock.exe"
            source_path.write_text(host)
            subprocess.run([str(MONO), str(CSC), "-nologo", "-out:" + str(executable), str(source_path)], check=True)
            subprocess.run([str(MONO), str(executable)], check=True)
        observer = declaration(context, "public ISirenNavigationObservationReader CreateNavigationObservationReader(")
        self.assertIn("float navigationSeconds = coordinator.r.world.seconds;", observer)
        self.assertIn("float requestAge = navigationSeconds - session.worldPathRequested;", observer)
        self.assertNotIn("StageElapsed", observer)

    def test_terrain_steering_cannot_reset_native_waypoint_progress(self):
        source = (SOURCE.parent / "world/IntegratedWorldBoundary.cs").read_text()
        route = declaration(source, "public void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 destination,")
        captured = route.index("var pathWaypoint = waypoint;")
        fallback = route.index("waypoint = TerrainTravelWaypoint(")
        progress = route.index("var pathRemaining = Vector3.Distance(position, pathWaypoint);")
        self.assertLess(captured, fallback)
        self.assertLess(fallback, progress)
        # r5's ground steering changed while the same source node remained
        # blocked. Only source-node distance/identity may reset its stall clock.
        clock = route[progress : route.index("navigationStalledSeconds =", progress)]
        self.assertIn("Vector3.Distance(pathWaypoint, worldNavigationProgressWaypoint)", clock)
        self.assertIn("pathRemaining < worldNavigationProgressDistance - .5f", clock)
        self.assertIn("worldNavigationProgressWaypoint = pathWaypoint;", clock)
        self.assertIn("worldNavigationProgressDistance = pathRemaining;", clock)
        self.assertNotIn("worldNavigationProgressWaypoint = waypoint;", route)

    def test_rejected_terrain_does_not_disable_stalled_path_recovery(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("Pinned Unity Mono/Roslyn host compiler unavailable")
        source = (SOURCE.parent / "world/IntegratedWorldBoundary.cs").read_text()
        route = declaration(source, "public void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 destination,")
        start = route.index("coordinator.r.world.navigationRecoveryJump =")
        expression = route[start : route.index(";", start) + 1]
        host = (
            """
using System;
class World { public bool navigationRecoveryJump, navigationTerrainFallback;
    public float navigationStalledSeconds, navigationObjectiveStalledSeconds; }
class Report { public World world = new World(); }
class Coordinator { public Report r = new Report(); }
class Mathf { public static float Max(float a, float b) => Math.Max(a,b); }
class RecoveryContract {
    static void Main() {
        var coordinator = new Coordinator();
        float stopDistance = 1.5f;
        // r6: terrain rejected every candidate and returned position (remaining=0),
        // while the original waypoint was still 11.46 m away after a 29.57 s stall.
        float pathRemaining = 11.461334f, remaining = 0;
        coordinator.r.world.navigationTerrainFallback = true;
        coordinator.r.world.navigationStalledSeconds = 29.576721f;
        coordinator.r.world.navigationObjectiveStalledSeconds = 21.995178f;
        """
            + expression
            + """
        if (!coordinator.r.world.navigationRecoveryJump)
            throw new Exception("neutral terrain suppressed unfinished-path recovery");
        // A completed native waypoint must not manufacture a recovery jump.
        pathRemaining = 0;
        """
            + expression
            + """
        if (coordinator.r.world.navigationRecoveryJump)
            throw new Exception("completed path requested recovery");
        // A healthy path must still wait for the existing stall threshold.
        pathRemaining = 11.461334f;
        coordinator.r.world.navigationStalledSeconds = 0;
        coordinator.r.world.navigationObjectiveStalledSeconds = 0;
        """
            + expression
            + """
        if (coordinator.r.world.navigationRecoveryJump)
            throw new Exception("progressing path requested recovery");
    }
}
"""
        )
        with tempfile.TemporaryDirectory(prefix="neutral-terrain-host-") as temporary:
            directory = Path(temporary)
            source_path = directory / "Recovery.cs"
            executable = directory / "Recovery.exe"
            source_path.write_text(host)
            subprocess.run([str(MONO), str(CSC), "-nologo", "-out:" + str(executable), str(source_path)], check=True)
            subprocess.run([str(MONO), str(executable)], check=True)

    def test_native_detour_keeps_graph_input_until_waypoint_stalls(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("Pinned Unity Mono/Roslyn host compiler unavailable")
        source = (SOURCE.parent / "world/IntegratedWorldBoundary.cs").read_text()
        policy = declaration(source, "public static class NavigationRecoveryPolicy")
        host = (
            "using System;\n"
            + policy
            + """
class DetourContract {
    static void Need(bool value) { if (!value) throw new Exception("native detour recovery contract"); }
    static void Main() {
        // R58: the egg remains farther away while a reachable 13-node path
        // advances around the terrain. Euclidean distance alone cannot reject it.
        Need(!NavigationRecoveryPolicy.ObjectiveRecovery(true, true, false, 13, false));
        Need(NavigationRecoveryPolicy.ObjectiveRecovery(true, true, false, 13, true));
        Need(NavigationRecoveryPolicy.ObjectiveRecovery(true, false, false, 13, false));
        Need(NavigationRecoveryPolicy.ObjectiveRecovery(true, true, true, 13, false));
        Need(NavigationRecoveryPolicy.ObjectiveRecovery(true, true, false, 1, false));
        Need(!NavigationRecoveryPolicy.ObjectiveRecovery(false, false, true, 0, true));
    }
}
"""
        )
        with tempfile.TemporaryDirectory(prefix="native-detour-host-") as temporary:
            directory = Path(temporary)
            source_path = directory / "Detour.cs"
            executable = directory / "Detour.exe"
            source_path.write_text(host)
            subprocess.run([str(MONO), str(CSC), "-nologo", "-out:" + str(executable), str(source_path)], check=True)
            subprocess.run([str(MONO), str(executable)], check=True)
        route = declaration(source, "public void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 destination,")
        self.assertIn("NavigationRecoveryPolicy.ObjectiveRecovery(", route)
        self.assertIn("|| stalled ||\n                               objectiveRecovery", route)

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
