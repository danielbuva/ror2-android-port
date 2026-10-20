from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures/native_item_display_dispatch_assertions.cs"
SOURCE = REPO / "tools/unity/runtime/input/AndroidNativeItemDisplayDispatch.cs"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class NativeItemDisplayDispatchTests(unittest.TestCase):
    def test_exclusive_native_writer_and_owned_observer_cleanup(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="native-item-dispatch-") as temporary:
            executable = Path(temporary) / "dispatch.exe"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-out:" + str(executable), str(SOURCE), str(FIXTURE)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS 18 ownership/dispatch assertions", ran.stdout)


if __name__ == "__main__":
    unittest.main()
