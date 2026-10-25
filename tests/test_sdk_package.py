"""Generic Android settings/source immutability contracts, with authored inputs."""

import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/sdk_package.py"
SPEC = importlib.util.spec_from_file_location("sdk_package", PATH)
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class SDKPackageTests(unittest.TestCase):
    def test_produce_preserves_app_host_environment_for_java_and_qemu_launches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            sdk = root / "sdk"
            files = {
                "Variations/il2cpp/Development/Libs/arm64-v8a/libmain.so": b"authored main",
                "Variations/il2cpp/Development/Libs/arm64-v8a/libunity.so": b"authored unity",
            }
            android_files = {
                "Apk/LauncherManifest.xml": b'<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application/></manifest>',
                "Apk/UnityManifest.xml": b'<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application><activity/></application></manifest>',
                "Apk/res/values/strings.xml": b'<resources><string name="app_name">Authored</string></resources>',
            }
            for name, data in (files | android_files).items():
                path = sdk / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

            def rows(values):
                return {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in values.items()}

            tools = {}
            for name in ("java", "javac", "aapt", "android.jar", "tool.jar"):
                path = root / name
                path.write_bytes(("authored " + name).encode())
                tools[name] = path
            environment = {
                "ROR2LAB_BUILD_JVM": str(root / "app-host-jvm"),
                "ROR2LAB_BUILD_JAVA_HOME": str(root / "app-java-home"),
                "HOME": str(root / "app-home"),
                "LD_LIBRARY_PATH": str(root / "app-native-libs"),
                "LC_ALL": "inherited-locale",
                "TMPDIR": str(root / "inherited-tmp"),
            }
            jvm_calls = []
            aapt_calls = []

            def process(argv, *, cwd, env, **kwargs):
                # Keep NATIVE.invoke real so its sanitized default cannot hide
                # lost JVM settings or QEMU's own native-library dependencies.
                for name in ("ROR2LAB_BUILD_JVM", "ROR2LAB_BUILD_JAVA_HOME", "HOME", "LD_LIBRARY_PATH"):
                    self.assertEqual(env.get(name), environment[name])
                self.assertEqual(env.get("LC_ALL"), "C")
                self.assertEqual(env.get("TMPDIR"), str(cwd / "tmp"))
                self.assertTrue((cwd / "tmp").is_dir())
                if argv[0] in (str(tools["java"]), str(tools["javac"])):
                    if argv[0] == str(tools["javac"]):
                        jvm_calls.append("compile-helper")
                    elif "manifest" in argv:
                        jvm_calls.append("format-manifest")
                        Path(argv[-1]).write_bytes(Path(argv[-2]).read_bytes())
                    else:
                        jvm_calls.append("produce-dex")
                        dex = Path(argv[-1])
                        dex.mkdir()
                        for name in ("classes.dex", "classes2.dex", "classes3.dex", "classes4.dex"):
                            (dex / name).write_bytes(b"authored dex")
                elif "compile" in argv:
                    self.assertEqual(argv[:3], ["authored-qemu", "-E", "LD_LIBRARY_PATH=authored-guest-libs"])
                    aapt_calls.append("compile")
                    (cwd / "compiled.zip").write_bytes(b"authored compiled resources")
                else:
                    self.assertEqual(argv[:3], ["authored-qemu", "-E", "LD_LIBRARY_PATH=authored-guest-libs"])
                    aapt_calls.append("link")
                    self.assertIn("link", argv)
                    (cwd / "R.txt").write_text("authored symbols")
                    with zipfile.ZipFile(cwd / "resources.apk", "w") as archive:
                        archive.writestr("AndroidManifest.xml", b"authored binary manifest")
                        archive.writestr("resources.arsc", b"authored resource table")
                        for name in PACKAGE.SDK_ENTRIES:
                            if name.startswith("res/"):
                                archive.writestr(name, ("authored resource " + name).encode())
                return SimpleNamespace(wait=lambda timeout: 0)

            with (
                patch.multiple(PACKAGE.SDK, FILES=rows(files), ANDROID_FILES=rows(android_files)),
                patch.multiple(
                    PACKAGE,
                    TOOL_JARS={"tool.jar": PACKAGE.NATIVE.sha(tools["tool.jar"])},
                    PLATFORM_SHA=PACKAGE.NATIVE.sha(tools["android.jar"]),
                    AAPT_SHAS={PACKAGE.NATIVE.sha(tools["aapt"])},
                ),
                patch.dict(os.environ, environment),
                patch.object(PACKAGE.NATIVE.subprocess, "Popen", side_effect=process),
            ):
                result = PACKAGE.produce(
                    {
                        "sdk": str(sdk),
                        "android_jar": str(tools["android.jar"]),
                        "aapt": str(tools["aapt"]),
                        "java": str(tools["java"]),
                        "javac": str(tools["javac"]),
                        "jars": {"tool.jar": str(tools["tool.jar"])},
                        "output": str(root / "output"),
                        "aapt_prefix": ["authored-qemu", "-E", "LD_LIBRARY_PATH=authored-guest-libs"],
                    }
                )
            self.assertTrue(result["success"])
            self.assertEqual(set(result["files"]), PACKAGE.SDK_ENTRIES)
            self.assertEqual(jvm_calls, ["compile-helper", "format-manifest", "produce-dex"])
            self.assertEqual(aapt_calls, ["compile", "link"])

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
