"""Packaged observer shares the CLI operation and compiles against the pinned SDK."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import build

ROOT = Path(__file__).resolve().parents[1]
ANDROID = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer")
LIBRARY = "Assets/Plugins/Android/SettingsWriteObserver.androidlib"


class SettingsObserverPackagingTests(unittest.TestCase):
    def test_staging_declares_private_same_uid_service_and_shared_operation(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            build.stage_android_assets(project)
            library = project / LIBRARY
            service = ET.parse(library / "AndroidManifest.xml").find("application/service")
            attr = lambda name: service.attrib["{http://schemas.android.com/apk/res/android}" + name]
            self.assertEqual(attr("process"), ":settings_write_observer")
            self.assertEqual(attr("exported"), "false")
            self.assertEqual(attr("isolatedProcess"), "false")
            shared = library / "src/dev/ror2lab/diagnostics/LabPendingWriteStop.java"
            self.assertEqual(shared.read_bytes(), (ROOT / "tools/android-write-interruption/LabPendingWriteStop.java").read_bytes())
            javac = Path(os.environ.get("JAVA_HOME", ANDROID / "OpenJDK")) / "bin/javac"
            android = ANDROID / "SDK/platforms/android-30/android.jar"
            if not javac.is_file() or not android.is_file():
                self.skipTest("pinned bundled JDK/SDK unavailable")
            result = subprocess.run(
                [str(javac), "-source", "8", "-target", "8", "-cp", str(android), "-d", str(project / "classes"), *map(str, sorted(library.rglob("*.java")))],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
