from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tools/unity/runtime/input/AndroidNativeSourceCameraRigContract.cs"
FIXTURE = ROOT / "tests/fixtures/CameraAdmissionEvidenceProgram.cs"
EDITOR_CONTENTS = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = EDITOR_CONTENTS / "MonoBleedingEdge/bin/mono"
CSC = EDITOR_CONTENTS / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class CameraAdmissionEvidenceTests(unittest.TestCase):
    def test_actual_production_dto_copy_contract(self) -> None:
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn host tools are unavailable")
        if not CONTRACT.is_file() or not FIXTURE.is_file():
            self.fail("production DTO contract or its C# fixture is missing")

        with tempfile.TemporaryDirectory(prefix="camera-admission-contract-") as temp_name:
            executable = Path(temp_name) / "CameraAdmissionEvidence.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:latest",
                    "-target:exe",
                    f"-out:{executable}",
                    str(CONTRACT),
                    str(FIXTURE),
                ],
                cwd=temp_name,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run(
                [str(MONO), str(executable)],
                cwd=temp_name,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("Nonrecursive camera admission DTO contract checks passed", ran.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
