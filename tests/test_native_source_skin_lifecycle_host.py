from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
OWNER = REPO / "tools/unity/runtime/input/AndroidNativeSourceSkinLifecycle.cs"
DISPATCH = REPO / "tools/unity/runtime/input/AndroidNativeItemDisplayDispatch.cs"
POLICY = REPO / "tools/unity/runtime/input/AndroidNativeSkinActivationPolicy.cs"
STUBS = FIXTURES / "native_source_skin_stubs.cs"
ASSERTIONS = FIXTURES / "native_source_skin_assertions.cs"
CAMERA_OWNER_CONTRACT = FIXTURES / "native_source_skin_camera_owner_contract.cs"
LISTENER_CONTRACT = REPO / "tools/unity/runtime/input/OriginalWwiseCameraListenerContract.cs"


class NativeSourceSkinLifecycleHostTests(unittest.TestCase):
    def test_actual_runtime_owner_and_policy_against_synthetic_contracts(self) -> None:
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn host compiler is unavailable")
        for source in (OWNER, DISPATCH, POLICY, STUBS, CAMERA_OWNER_CONTRACT, LISTENER_CONTRACT, ASSERTIONS):
            self.assertTrue(source.is_file(), f"missing host contract source: {source}")
        with tempfile.TemporaryDirectory(prefix="native-source-skin-host-") as temp:
            temp_path = Path(temp)
            executable = temp_path / "NativeSourceSkinLifecycle.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:latest",
                    "-target:exe",
                    f"-out:{executable}",
                    str(STUBS),
                    str(OWNER),
                    str(DISPATCH),
                    str(POLICY),
                    str(CAMERA_OWNER_CONTRACT),
                    str(LISTENER_CONTRACT),
                    str(ASSERTIONS),
                ],
                cwd=temp_path,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], cwd=temp_path, capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: 66 adapter/selection/lifecycle/report assertions", ran.stdout)


if __name__ == "__main__":
    unittest.main()
