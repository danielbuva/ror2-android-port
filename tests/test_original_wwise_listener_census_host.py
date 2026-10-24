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
OWNER = ROOT / "tools/unity/runtime/session/PortSessionOriginalAudioOwner.cs"
CONTRACT = ROOT / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs"
STUBS = FIXTURES / "original_wwise_listener_census_stubs.cs"
HARNESS = FIXTURES / "original_wwise_listener_census_harness.cs"


class OriginalWwiseListenerCensusHostTests(unittest.TestCase):
    def test_census_and_termination_delegate_keep_owned_boundaries(self) -> None:
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn host compiler is unavailable")
        for source in (OWNER, CONTRACT, STUBS, HARNESS):
            self.assertTrue(source.is_file(), f"missing host contract source: {source}")
        with tempfile.TemporaryDirectory(prefix="original-wwise-listener-census-") as temp_name:
            temp = Path(temp_name)
            executable = temp / "ListenerCensusHarness.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:latest",
                    "-target:exe",
                    f"-out:{executable}",
                    str(CONTRACT),
                    str(STUBS),
                    str(OWNER),
                    str(HARNESS),
                ],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], cwd=temp, capture_output=True, text=True, check=False)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("default-off/pre-ready do not read", ran.stdout)
            self.assertIn("original termination wakeup admission", ran.stdout)


if __name__ == "__main__":
    unittest.main()
