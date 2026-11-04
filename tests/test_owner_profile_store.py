"""Compile/run actual local-retention code with authored, non-game data only."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OwnerProfileStoreTests(unittest.TestCase):
    def test_synthetic_snapshot_restore_interruption_and_trust(self):
        homes = [
            Path(os.environ.get("JAVA_HOME", "/absent")),
            ROOT / ".local/jdk",
            Path("/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer/OpenJDK"),
        ]
        javac = next((home / "bin/javac" for home in homes if (home / "bin/javac").is_file()), None)
        if javac is None and shutil.which("javac"):
            javac = Path(shutil.which("javac"))
        if javac is None:
            self.skipTest("Java compiler absent; retention is not host-qualified")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            classes, data = base / "classes", base / "data"
            classes.mkdir()
            data.mkdir()
            compile_result = subprocess.run(
                [
                    str(javac),
                    "-source",
                    "8",
                    "-target",
                    "8",
                    "-d",
                    str(classes),
                    str(ROOT / "tools/phone-build/owner-apk/ProfileStore.java"),
                    str(ROOT / "tests/fixtures/owner_profile/ProfileStoreHarness.java"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(
                [str(javac.with_name("java")), "-cp", str(classes), "dev.ror2owner.bootstrap.ProfileStoreHarness", str(data)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"success":true', result.stdout)
            self.assertIn('"synthetic_only":true', result.stdout)

    def test_bridge_is_control_only_and_runtime_launch_is_gated(self):
        provider = (ROOT / "tools/phone-build/owner-apk/ProfileRetentionProvider.java").read_text()
        activity = (ROOT / "tools/phone-build/owner-apk/PayloadBootstrapActivity.java").read_text()
        self.assertIn("getPackagesForUid(Binder.getCallingUid())", provider)
        self.assertIn("info.applicationInfo.uid != Binder.getCallingUid()", provider)
        self.assertIn("ProfileStore.authorized(", provider)
        self.assertIn("getApkContentsSigners()", provider)
        self.assertIn("if (unityStarted) throw new IOException(", provider)
        self.assertLess(provider.index('if ("status".equals(method))'), provider.index("if (unityStarted) throw new IOException("))
        self.assertIn('response.putString("state", state.state)', provider)
        self.assertIn("writes != ProfileStore.DATA_SCHEMA || reads.length != 1", provider)
        self.assertIn('context.getNoBackupFilesDir().getCanonicalFile(), "owner-profile-retention"', provider)
        self.assertIn('extras.getBoolean("user_requested", false)', provider)
        self.assertIn("openFile(Uri uri, String mode) { throw noData(); }", provider)
        self.assertEqual(activity.count("ProfileRetentionProvider.beforeUnityLaunch("), 2)
        self.assertNotIn("openPipeHelper", provider)
        self.assertNotIn("android.permission.INTERNET", provider)
