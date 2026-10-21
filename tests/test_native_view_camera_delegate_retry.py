from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
UNITY_MONO = Path(
    os.environ.get(
        "UNITY_MONO_BIN",
        "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin",
    )
)


class NativeViewCameraDelegateRetryTests(unittest.TestCase):
    def test_deferred_exact_owner_binding_preserves_original_pump_gates(self):
        mcs = UNITY_MONO / "mcs"
        mono = UNITY_MONO / "mono"
        if not mcs.is_file() or not mono.is_file():
            self.skipTest("pinned Unity Mono compiler/runtime unavailable")

        with tempfile.TemporaryDirectory(prefix="camera-delegate-retry-") as temporary:
            output = Path(temporary) / "fixture.exe"
            completed = subprocess.run(
                [
                    str(mcs),
                    "-langversion:7.2",
                    "-out:" + str(output),
                    str(REPO / "tests/fixtures/native_camera/stubs.cs"),
                    str(REPO / "tools/unity/runtime/input/AndroidNativeSourceViewOnlyRigMarker.cs"),
                    str(REPO / "tests/fixtures/native_camera/DelegateRetryProgram.cs"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = subprocess.run([str(mono), str(output)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS delayed exact-owner binding", result.stdout)


if __name__ == "__main__":
    unittest.main()
