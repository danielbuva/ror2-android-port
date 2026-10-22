from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "PORTING_STATE.md").is_file())
UNITY = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
MONO = UNITY / "bin/mono"
CSC = UNITY / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
SOURCE = ROOT / "tools/unity/support/audio/bootstrap/GameAudioOriginalPayloadCopy.cs"
HARNESS = ROOT / "tests/fixtures/original_audio/streamed_media/PayloadCopyReceiptHarness.cs"
STUBS = ROOT / "tests/fixtures/original_audio/streamed_media/UnityAudioStubs.cs"


class PayloadCopyReceiptTests(unittest.TestCase):
    @unittest.skipUnless(MONO.is_file() and CSC.is_file(), "pinned Unity Mono/Roslyn is unavailable")
    def test_actual_copier_receipt_validation_accepts_only_canonical_media_closure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "payload-copy-harness.exe"
            subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:latest",
                    "-nowarn:0649",
                    f"-out:{executable}",
                    str(STUBS),
                    str(HARNESS),
                    str(SOURCE),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run([str(MONO), str(executable)], check=True, capture_output=True, text=True)
            self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
