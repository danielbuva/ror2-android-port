"""Execute native sound-catalog admission decisions against controlled API observations."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class OriginalAudioNetworkSoundHostTests(unittest.TestCase):
    def test_production_catalog_admission_and_startup_gate(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        fixture = ROOT / "tests/fixtures/original_audio/network_sound"
        with tempfile.TemporaryDirectory(prefix="network-sound-host-") as name:
            executable = Path(name) / "CatalogOwner.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-target:exe",
                    f"-out:{executable}",
                    str(ROOT / "tools/unity/runtime/session/OriginalNetworkSoundEventCatalogOwner.cs"),
                    str(fixture / "CatalogOwnerStubs.cs"),
                    str(fixture / "CatalogOwnerHarness.cs"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            for scenario, checks in {
                "success": 7,
                "no-audio": 2,
                "foreign": 2,
                "zero-id": 2,
                "setter-throws": 2,
                "startup-gate": 6,
                "aliases": 3,
                "preexisting": 2,
                "empty-family": 5,
                "empty-truncation": 3,
                "null-event-name": 3,
                "null-definition": 1,
                "null-source": 2,
                "empty-source": 2,
            }.items():
                with self.subTest(scenario=scenario):
                    ran = subprocess.run([str(MONO), str(executable), scenario], capture_output=True, text=True, timeout=30)
                    self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                    self.assertIn(f"PASS {scenario} {checks}", ran.stdout)


if __name__ == "__main__":
    unittest.main()
