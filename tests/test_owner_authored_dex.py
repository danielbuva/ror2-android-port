"""Authored Android plugin compilation and APK class completeness contracts."""

import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("authored_dex_owner", ROOT / "tools/phone-build/owner-apk/build_owner_apk.py")
OWNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OWNER)


def dex_fixture(defined, referenced):
    """Minimal authored class/type/string tables; references aren't definitions."""
    names = defined + referenced
    data = bytearray(112 + len(names) * 8 + len(defined) * 32)
    data[:8] = b"dex\n035\0"
    strings, types, classes = 112, 112 + len(names) * 4, 112 + len(names) * 8
    struct.pack_into("<4I", data, 56, len(names), strings, len(names), types)
    struct.pack_into("<2I", data, 96, len(defined), classes)
    for i, name in enumerate(names):
        struct.pack_into("<I", data, strings + i * 4, len(data))
        struct.pack_into("<I", data, types + i * 4, i)
        data += bytes([len(name)]) + name.encode() + b"\0"
    for i in range(len(defined)):
        struct.pack_into("<I", data, classes + i * 32, i)
    struct.pack_into("<I", data, 32, len(data))
    return bytes(data)


class AuthoredDexTests(unittest.TestCase):
    def test_referenced_missing_class_does_not_satisfy_contract(self):
        required = "Ldev/ror2lab/diagnostics/LabDisplayPreference;"
        actual = OWNER.dex_classes(dex_fixture(["Lfixture/Main;"], [required]))
        self.assertNotIn(required, actual)
        with self.assertRaisesRegex(ValueError, "LabDisplayPreference"):
            OWNER.authored_class_contract({required}, actual)
        self.assertEqual(OWNER.authored_class_contract({required, "Landroid/App;"}, actual | {required})["verified_count"], 1)

    def test_all_dex_entries_contribute_defined_classes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.apk"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("classes.dex", dex_fixture(["Lfixture/First;"], []))
                archive.writestr("classes5.dex", dex_fixture(["Lfixture/Second;"], []))
            self.assertEqual(OWNER.apk_classes(path), {"Lfixture/First;", "Lfixture/Second;"})

    def test_authored_plugin_compiles_with_bundled_sdk_and_retains_existing_classes(self):
        sdk = Path(os.environ.get("UNITY_ANDROID_ROOT", "/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer"))
        roots = dict(
            java=sdk / "OpenJDK/bin/java",
            javac=sdk / "OpenJDK/bin/javac",
            android_jar=sdk / "SDK/platforms/android-30/android.jar",
            d8_jar=sdk / "SDK/build-tools/34.0.0/lib/d8.jar",
        )
        if not all(path.is_file() for path in roots.values()):
            self.skipTest("bundled Android SDK/JDK absent")
        retained = "Ldev/ror2lab/diagnostics/LabPendingWriteStop;"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)

            def run(command, label):
                result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, label + result.stdout + result.stderr)

            dex = OWNER.compile_authored(roots, output, {retained}, run)
            classes = OWNER.dex_classes(dex.read_bytes())
            self.assertNotIn(retained, classes)
            for name in ("LabDisplayPreference", "LabSettingsWriteObserver", "BuildConfig", "LabPendingWriteStop$1"):
                self.assertIn("Ldev/ror2lab/diagnostics/" + name + ";", classes)
            self.assertIn("Ldev/ror2owner/bootstrap/PayloadBootstrapActivity;", classes)


if __name__ == "__main__":
    unittest.main()
