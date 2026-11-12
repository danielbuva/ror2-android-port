"""Compile the authored camera with exact-editor assemblies; no game input needed."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/lab"))
import perf_report

EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
MANAGED = EDITOR / "Managed/UnityEngine"


class RawFrameCaptureTests(unittest.TestCase):
    def test_authored_admission_binary_interop_and_overflow(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="raw-frame-capture-") as folder:
            executable = Path(folder) / "capture.exe"
            references = ["-r:" + str(MANAGED / name) for name in ("UnityEngine.CoreModule.dll", "UnityEngine.ProfilerModule.dll")]
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-out:" + str(executable),
                    *references,
                    str(REPO / "tools/unity/runtime/input/AndroidPresentationCamera.cs"),
                    str(REPO / "tests/fixtures/raw_frame_capture_harness.cs"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable), folder], env=dict(os.environ, MONO_PATH=str(MANAGED)), capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS raw frame admission", ran.stdout)
            trace = perf_report.read_raw_frames((Path(folder) / "capture.bin").read_bytes())
            self.assertEqual(trace["durations_ms"], [16.5, perf_report.HITCH33_MS, 51.25])
            self.assertEqual(trace["dropped_frames"], 0)
            overflow = perf_report.read_raw_frames((Path(folder) / "overflow.bin").read_bytes())
            self.assertEqual(overflow["durations_ms"], [10, 60])
            self.assertEqual((overflow["first_frame"], overflow["last_frame"], overflow["dropped_frames"]), (8, 10, 1))


if __name__ == "__main__":
    unittest.main()
