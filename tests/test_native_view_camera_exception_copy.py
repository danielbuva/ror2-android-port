from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]


class NativeViewCameraExceptionCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        editor = Path(os.environ.get("UNITY_EDITOR", ""))
        baseline = Path(os.environ.get("CAMERA_EH_BASELINE", ""))
        output = Path(os.environ.get("CAMERA_EH_OUTPUT", ""))
        helper = Path(os.environ.get("CAMERA_EH_HELPER", ""))
        verifier = Path(os.environ.get("CAMERA_EH_VERIFIER", ""))
        resolver = Path(os.environ.get("CAMERA_EH_RESOLVER", ""))
        if not all(path.is_file() for path in (editor, baseline, output, helper, verifier)) or not resolver.is_dir():
            raise unittest.SkipTest("set UNITY_EDITOR and CAMERA_EH_* from a completed exact camera profile")
        contents = editor.resolve().parent.parent
        cls.mcs = contents / "MonoBleedingEdge/bin/mcs"
        cls.mono = contents / "MonoBleedingEdge/bin/mono"
        cls.cecil = contents / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
        if not all(path.is_file() for path in (cls.mcs, cls.mono, cls.cecil)):
            raise unittest.SkipTest("pinned Unity Mono/Cecil host tools unavailable")
        cls.baseline, cls.output, cls.helper, cls.verifier, cls.resolver = baseline, output, helper, verifier, resolver
        cls.scratch_context = tempfile.TemporaryDirectory(prefix="camera-eh-mutant-")
        cls.addClassCleanup(cls.scratch_context.cleanup)
        cls.scratch = Path(cls.scratch_context.name)
        cls.mutator = cls.scratch / "RemoveMarkerExceptionHandlers.exe"
        fixture = CANDIDATE / "tests/fixtures/native_camera/RemoveMarkerExceptionHandlers.cs"
        subprocess.run([str(cls.mcs), "-sdk:4.7.2", "-out:" + str(cls.mutator), "-r:" + str(cls.cecil), str(fixture)], check=True)

    def test_exact_copied_exception_table_is_accepted(self):
        result = subprocess.run(
            [str(self.mono), str(self.verifier), str(self.baseline), str(self.output), str(self.helper)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_missing_eh_table_mutant_is_rejected(self):
        mutant = self.scratch / "RoR2.missing-marker-eh.dll"
        subprocess.run([str(self.mono), str(self.mutator), str(self.output), str(mutant), str(self.resolver)], check=True)
        result = subprocess.run(
            [str(self.mono), str(self.verifier), str(self.baseline), str(mutant), str(self.helper)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("copied marker exception handlers changed", result.stdout)


if __name__ == "__main__":
    unittest.main()
