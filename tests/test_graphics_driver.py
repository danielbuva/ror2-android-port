"""Execute actual driver package/admission owners on authored ZIPs, never real drivers."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class GraphicsDriverTests(unittest.TestCase):
    def test_production_owners_compile_with_android_bootclasspath(self):
        compiler = Path(os.environ.get("JAVA_HOME", "/absent")) / "bin/javac"
        if not compiler.is_file():
            found = shutil.which("javac")
            if not found:
                self.skipTest("Java compiler absent")
            compiler = Path(found)
        sdk = Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or "/absent")
        android = sdk / "platforms/android-33/android.jar"
        if not android.is_file():
            self.skipTest("Android API 33 compile jar absent")
        # The ordinary JDK classpath hid the observed #274 Android bootstrap
        # failure. Compile production owners only, not the desktop Java harness.
        source = ROOT / "tools/phone-build/owner-apk/graphics"
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [
                    str(compiler),
                    "-source",
                    "8",
                    "-target",
                    "8",
                    "-bootclasspath",
                    str(android),
                    "-d",
                    temporary,
                    str(source / "GraphicsDriverPackage.java"),
                    str(source / "GraphicsDriverPolicy.java"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_package_and_launch_recovery_contracts(self):
        home = Path(os.environ.get("JAVA_HOME", "/absent"))
        compiler = home / "bin/javac"
        if not compiler.is_file():
            found = shutil.which("javac")
            if not found:
                self.skipTest("Java compiler absent; custom drivers are not host-qualified")
            compiler = Path(found)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classes = root / "classes"
            classes.mkdir()
            library = bytearray(64)
            library[:7] = b"\x7fELF\x02\x01\x01"
            library[16:20] = b"\x03\x00\xb7\x00"
            metadata = b"authored metadata fixture"

            def archive(name, entries):
                with zipfile.ZipFile(root / name, "w", compression=zipfile.ZIP_DEFLATED) as output:
                    for path, body in entries:
                        output.writestr(path, body)

            good = [("meta.json", metadata), ("libvulkan_test.so", library), ("extra.so", b"never extracted")]
            archive("good.zip", good)
            archive("adrenotools.zip", [("meta.json", metadata), ("vulkan.ad07XX.so", library)])
            archive("other.zip", good + [("LICENSE", b"authored extra bytes change archive identity")])
            archive("traversal.zip", good + [("../escaped", b"not written")])
            archive("nested.zip", good + [("directory/file", b"not written")])
            archive("missing-meta.zip", good[1:])
            archive("large-meta.zip", [("meta.json", b"x" * 65537)] + good[1:])
            archive("wrong-arch.zip", [("meta.json", metadata), ("libvulkan_test.so", b"x" * 64)])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive("duplicate.zip", good + [good[0]])
            (root / "hash.txt").write_text(hashlib.sha256((root / "good.zip").read_bytes()).hexdigest())
            source = ROOT / "tools/phone-build/owner-apk/graphics"
            compiled = subprocess.run(
                [
                    str(compiler),
                    "-source",
                    "8",
                    "-target",
                    "8",
                    "-d",
                    str(classes),
                    *map(str, sorted(source.glob("*.java"))),
                    str(ROOT / "tests/fixtures/graphics_driver/GraphicsDriverHarness.java"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(compiler.with_name("java")), "-cp", str(classes), "dev.ror2owner.graphics.GraphicsDriverHarness", str(root)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"success":true', result.stdout)
            self.assertIn('"synthetic_only":true', result.stdout)

    def test_default_bootstrap_is_unchanged(self):
        # These are foundation owners only, not an unverified native driver switch.
        for path in ("PayloadBootstrapActivity.java", "build_owner_apk.py"):
            content = (ROOT / "tools/phone-build/owner-apk" / path).read_text()
            self.assertNotIn("GraphicsDriverPolicy", content)
            self.assertNotIn("adrenotools", content)
