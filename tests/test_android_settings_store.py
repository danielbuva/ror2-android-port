"""Production settings transactions on a real temporary filesystem."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
MONO = EDITOR / "bin/mono"
CSC = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class AndroidSettingsStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="android-settings-store-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe = Path(cls.temp.name) / "settings.exe"
        result = subprocess.run(
            [
                str(MONO),
                str(CSC),
                "-nologo",
                "-langversion:9",
                "-r:System.Runtime.Serialization.dll",
                "-out:" + str(cls.exe),
                str(ROOT / "tools/unity/runtime/input/AndroidOfflineSettings.cs"),
                str(ROOT / "tests/fixtures/AndroidSettingsStoreHost.cs"),
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def case(self, name):
        result = subprocess.run([str(MONO), str(self.exe), name, str(Path(self.temp.name) / name)], text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ": PASS", result.stdout)

    def test_successful_update_retains_previous_generation_and_cold_reloads(self):
        self.case("roundtrip")

    def test_partial_pending_output_never_supersedes_a_valid_primary(self):
        self.case("partial-pending")

    def test_corrupt_primary_is_preserved_and_validated_backup_restored(self):
        self.case("backup")

    def test_missing_primary_recovers_backup_over_an_incomplete_pending_write(self):
        self.case("missing-primary")

    def test_blocked_pending_write_is_honest_preserves_primary_and_can_retry(self):
        self.case("blocked-write")

    def test_invalid_values_never_replace_a_valid_primary(self):
        self.case("invalid-value")
