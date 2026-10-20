"""Execute authored event-owner methods with host doubles; no game input or Unity process."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def source_method(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise AssertionError("Production method does not close: " + declaration)


def production_host():
    source = (ROOT / "tools/unity/runtime/world/EnemySpineBoundary.cs").read_text()
    declarations = (
        "void SubscribeEnemyActorEvents()",
        "void UnsubscribeEnemyActorEvents()",
        "public void EnemyDamage(",
        "public void EnemyDeath(",
        "public void CleanupEnemy()",
    )
    methods = [source_method(source, declaration) for declaration in declarations]
    context = source_method(source, "public IEnumerator PrepareEnemyContext(")
    gate_start = context.index("if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)")
    gate_end = context.index("SubscribeEnemyActorEvents();", gate_start) + len("SubscribeEnemyActorEvents();")
    owner = "public partial class FixtureOwner {\n" + "\n".join(methods) + "\n public void NativeContextTail() { " + context[gate_start:gate_end] + " }\n}\n"
    observation = (ROOT / "tools/unity/runtime/world/DirectorActorBoundary.cs").read_text()
    callbacks = [source_method(observation, name) for name in ("void ObserveDirectorDamage(", "void ObserveDirectorDeath(")]
    reports = "public partial class FixtureCoordinator {\n" + "\n".join("public " + callback for callback in callbacks) + "\n}\n"
    return (ROOT / "tests/fixtures/enemy_actor_observation_host.cs").read_text() + "\n" + owner + reports


class EnemyActorObservationTests(unittest.TestCase):
    def test_owned_events_default_native_recovery_and_partial_setup(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.exists() or not csc.exists():
            self.skipTest("matching Unity Mono compiler is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            source = scratch / "EnemyActorObservationHost.cs"
            output = scratch / "EnemyActorObservationHost.exe"
            source.write_text(production_host())
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(output), str(source)],
                cwd=scratch,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(
                json.loads(executed.stdout),
                dict(
                    normal_default_native_cases=2,
                    partial_subscription_failures=3,
                    unprepared_cleanup_case=True,
                    all_passed=True,
                    native_event_execution_claimed=False,
                ),
            )


if __name__ == "__main__":
    unittest.main()
