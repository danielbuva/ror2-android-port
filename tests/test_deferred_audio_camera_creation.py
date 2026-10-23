"""Compile and execute the current production deferred-camera lifecycle bodies."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/world/IntegratedWorldBoundary.cs"
FIXTURE = Path(__file__).resolve().parent / "fixtures/DeferredAudioCameraCreationProgram.cs"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


def extract_block(source: str, declaration: str) -> str:
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
    raise AssertionError(f"unterminated production block: {declaration}")


class DeferredAudioCameraCreationTests(unittest.TestCase):
    def test_current_production_schedule_and_cleanup_helper(self) -> None:
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        production = SOURCE.read_text(encoding="utf-8")
        schedule = extract_block(production, "        internal sealed class OriginalAudioCameraContextCreationSchedule")
        cleanup_helper = extract_block(production, "        void CancelPendingOriginalAudioCameraContextCreationForCleanup()")
        cleanup = extract_block(production, "        public void CleanupIntegratedWorld()")
        cancel_call = cleanup.index("CancelPendingOriginalAudioCameraContextCreationForCleanup();")
        release_call = cleanup.index("ReleaseOriginalAudioCameraContext();")
        self.assertLess(cancel_call, release_call, "pending work must be canceled before owner release")
        self.assertIn("CancelPending()", schedule)
        self.assertIn("deferred_creation_cancelled_by_world_cleanup", cleanup_helper)
        self.assertIn("!report.originalAudioCameraContextCreated", cleanup_helper)
        prepare = extract_block(
            production,
            "            public BeginResult Begin(bool integratedWorldPlaying, object updatePlayer, object ownedWorldPlayer, bool alreadyAttempted)",
        )
        self.assertIn("ReferenceEquals(updatePlayer, ownedWorldPlayer)", prepare)

        harness = FIXTURE.read_text(encoding="utf-8")
        harness = harness.replace("__PRODUCTION_SCHEDULE__", schedule)
        harness = harness.replace("__PRODUCTION_CLEANUP_HELPER__", cleanup_helper)
        self.assertNotIn("__PRODUCTION_", harness)
        with tempfile.TemporaryDirectory(prefix="deferred-audio-camera-public-test-") as temp_name:
            temp = Path(temp_name)
            source = temp / "DeferredAudioCameraCreationProgram.cs"
            source.write_text(harness, encoding="utf-8")
            executable = temp / "DeferredAudioCameraCreationProgram.exe"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:latest", "-target:exe", f"-out:{executable}", str(source)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: production deferred-camera lifecycle and cleanup contract", ran.stdout)


if __name__ == "__main__":
    unittest.main()
