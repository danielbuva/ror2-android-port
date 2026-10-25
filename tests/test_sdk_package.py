"""Generic Android settings/source immutability contracts, with authored inputs."""

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/sdk_package.py"
SPEC = importlib.util.spec_from_file_location("sdk_package", PATH)
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class SDKPackageTests(unittest.TestCase):
    def test_manifest_retains_sdk_entry_points_and_applies_fixed_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Apk").mkdir()
            launcher = b'<manifest xmlns:android="http://schemas.android.com/apk/res/android"><supports-screens android:anyDensity="true"/><application android:label="@string/app_name" android:icon="@mipmap/app_icon"/></manifest>'
            unity = b'<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application><activity android:name="com.unity3d.player.UnityPlayerActivity" android:theme="@style/UnityThemeSelector"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter><meta-data android:name="unityplayer.UnityActivity" android:value="true"/></activity></application></manifest>'
            (root / "Apk/LauncherManifest.xml").write_bytes(launcher)
            (root / "Apk/UnityManifest.xml").write_bytes(unity)
            output = ET.fromstring(PACKAGE.manifest(root))
            a = PACKAGE.attr
            self.assertEqual(output.get("package"), "dev.ror2lab.arm64")
            self.assertEqual(output.find("uses-sdk").attrib, {a("minSdkVersion"): "23", a("targetSdkVersion"): "30"})
            self.assertEqual(output.find("supports-screens").get(a("anyDensity")), "true")
            app = output.find("application")
            self.assertEqual(app.get(a("extractNativeLibs")), "true")
            activity = app.find("activity")
            self.assertEqual(activity.get(a("name")), "com.unity3d.player.UnityPlayerActivity")
            self.assertEqual(activity.get(a("launchMode")), "singleTask")
            self.assertEqual(activity.find("intent-filter/action").get(a("name")), "android.intent.action.MAIN")
            self.assertEqual(
                {p.get(a("name")) for p in output.findall("uses-permission")}, {"android.permission.INTERNET", "android.permission.CHANGE_WIFI_MULTICAST_STATE"}
            )
            self.assertEqual((root / "Apk/LauncherManifest.xml").read_bytes(), launcher)
            self.assertEqual((root / "Apk/UnityManifest.xml").read_bytes(), unity)

    def test_unknown_and_redirected_sdk_member_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            data = b"authored SDK fixture"
            (root / "input").write_bytes(data)
            rows = {"input": (len(data), hashlib.sha256(data).hexdigest())}
            with patch.multiple(PACKAGE.SDK, FILES=rows, ANDROID_FILES={}):
                self.assertEqual(PACKAGE.sdk_state(root), {"input": rows["input"][1]})
                (root / "input").write_bytes(b"other SDK bytes")
                with self.assertRaisesRegex(ValueError, "pinned Android SDK"):
                    PACKAGE.sdk_state(root)
                (root / "input").unlink()
                (root / "original").write_bytes(data)
                (root / "input").symlink_to(root / "original")
                with self.assertRaisesRegex(ValueError, "pinned Android SDK"):
                    PACKAGE.sdk_state(root)
