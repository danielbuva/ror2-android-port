"""Exercise authored Siren continuation clock and identity witnesses."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get("SIREN_CONTINUATION_SOURCE_ROOT", ROOT / "tools/unity/runtime")).resolve()
OWNER = SOURCE_ROOT / "stage/SirenEncounterBoundary.cs"
INPUT = SOURCE_ROOT / "input/NovaInputBoundary.cs"
WORLD = SOURCE_ROOT / "world/IntegratedWorldBoundary.cs"
SESSION = SOURCE_ROOT / "session/PortSession.cs"
FIXTURE = Path(__file__).with_name("fixtures") / "siren_native_encounter_continuation.cs"
HOST_TEMP = ROOT / "work/host-tests/siren-native-continuation"


def extract_declaration(source, declaration):
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
    raise AssertionError(f"unclosed production declaration: {declaration}")


class SirenNativeEncounterContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        editor = Path(
            os.environ.get(
                "UNITY_EDITOR_PATH",
                "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
            )
        )
        cls.mono = editor / "MonoBleedingEdge/bin/mono"
        cls.compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not cls.mono.is_file() or not cls.compiler.is_file():
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 host compiler unavailable")
        HOST_TEMP.mkdir(parents=True, exist_ok=True)

    def test_production_clock_and_exact_native_boss_witness(self):
        owner = OWNER.read_text()
        continuation = extract_declaration(owner, "public static class SirenNativeEncounterContinuationContract")
        witness = extract_declaration(owner, "public bool TryGetExactNativeBossNetworkIds(out uint[] networkIds)")
        fixture = FIXTURE.read_text()
        source = fixture.replace("__PRODUCTION_CONTRACT__", continuation).replace("__PRODUCTION_METHOD__", witness)
        self.assertNotIn("__PRODUCTION_", source)

        with tempfile.TemporaryDirectory(prefix="siren-continuation-", dir=HOST_TEMP) as temporary_directory:
            temporary = Path(temporary_directory)
            source_path = temporary / "SirenContinuation.cs"
            executable = temporary / "SirenContinuation.exe"
            source_path.write_text(source)
            compiled = subprocess.run(
                [
                    str(self.mono),
                    str(self.compiler),
                    "-nologo",
                    "-langversion:9",
                    "-target:exe",
                    "-out:" + str(executable),
                    str(source_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            run = subprocess.run([str(self.mono), str(executable)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("siren-native-boss-production-witness-all-passed", run.stdout)

    def test_selector_defaults_and_world_clock_wiring_remain_scoped(self):
        session = SESSION.read_text()
        source_files = [path.read_text() for path in SOURCE_ROOT.rglob("*.cs")]
        self.assertIn("public bool sirenNativeEncounterContinuationRequested", session)
        self.assertIn("public bool diagnosticSirenEggInput;", session)
        self.assertNotIn("diagnosticSirenEggInput = true", "\n".join(source_files))

        input_source = INPUT.read_text()
        self.assertIn("TryGetStageElapsedSeconds(", input_source)
        self.assertIn("Time.realtimeSinceStartup, began, coordinator.stageEnteredAt", input_source)
        self.assertIn("continuationStageElapsed >= SirenEggDiagnosticInput.MaximumStageSeconds", input_source)

        world = WORLD.read_text()
        self.assertIn("TryGetWorldStageElapsedSeconds(", world)
        self.assertIn("coordinator.r.world.seconds", world)
        self.assertNotIn("Time.realtimeSinceStartup - coordinator.stageEnteredAt", world)
        self.assertIn("coordinator.SirenEggInputSelected", world)


if __name__ == "__main__":
    unittest.main(verbosity=2)
