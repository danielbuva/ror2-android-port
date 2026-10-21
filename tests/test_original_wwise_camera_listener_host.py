from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CONTRACT = ROOT / "tools/unity/runtime/input/OriginalWwiseCameraListenerContract.cs"
HARNESS = FIXTURES / "original_wwise_camera_listener_harness.cs"


class OriginalWwiseCameraListenerHostTests(unittest.TestCase):
    def test_listener_lifecycle_evidence_contract(self) -> None:
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn host compiler is unavailable")
        for source in (CONTRACT, HARNESS):
            self.assertTrue(source.is_file(), f"missing host contract source: {source}")
        with tempfile.TemporaryDirectory(prefix="original-wwise-camera-listener-") as temp_name:
            temp = Path(temp_name)
            executable = temp / "ListenerContractHarness.exe"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-target:exe", f"-out:{executable}", str(CONTRACT), str(HARNESS)],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], cwd=temp, capture_output=True, text=True, check=False)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: 44 listener lifecycle and evidence assertions", ran.stdout)


if __name__ == "__main__":
    unittest.main()
