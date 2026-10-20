import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

from phone_native_apk import METADATA, NATIVE, repack
from tests.test_phone_apk import manifest


class PhoneNativeApkTests(unittest.TestCase):
    def test_standalone_native_swap_preserves_metadata_assets_notices_and_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            apk, library, output = (root / name for name in ("base.apk", "native.so", "result.apk"))
            native = bytearray(64)
            native[:7] = b"\x7fELF\x02\x01\x01"
            struct.pack_into("<HH", native, 16, 3, 183)
            library.write_bytes(native)
            metadata = b"authored-metadata"
            with zipfile.ZipFile(apk, "w") as archive:
                for name, data in [
                    ("AndroidManifest.xml", manifest()),
                    (NATIVE, b"old-native"),
                    (METADATA, metadata),
                    ("assets/phone-fixture.bundle", b"authored-bundle"),
                    ("META-INF/NOTICE.txt", b"retain-notice"),
                    ("META-INF/CERT.RSA", b"obsolete"),
                ]:
                    archive.writestr(name, data)
            original = apk.read_bytes()
            hashes = {
                "apk_sha256": hashlib.sha256(original).hexdigest(),
                "library_sha256": hashlib.sha256(native).hexdigest(),
                "metadata_sha256": hashlib.sha256(metadata).hexdigest(),
            }
            script = Path(__file__).resolve().parents[1] / "scripts/lab/phone_native_apk.py"
            command = [sys.executable, "-I", "-S", str(script), str(apk), str(library), str(output), "--version-code", "3"]
            for name, digest in hashes.items():
                command += ["--" + name.replace("_", "-"), digest]
            subprocess.run(command, capture_output=True, check=True)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read(NATIVE), native)
                self.assertEqual(archive.read(METADATA), metadata)
                self.assertEqual(archive.read("assets/phone-fixture.bundle"), b"authored-bundle")
                self.assertEqual(archive.read("META-INF/NOTICE.txt"), b"retain-notice")
                self.assertNotIn("META-INF/CERT.RSA", archive.namelist())
            self.assertEqual(apk.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                repack(apk, library, output, 3, **hashes)
            for key in hashes:
                refused = root / (key + ".apk")
                with self.subTest(key=key), self.assertRaises(ValueError):
                    repack(apk, library, refused, 3, **(hashes | {key: "0" * 64}))
                self.assertFalse(refused.exists())
            native[18:20] = struct.pack("<H", 62)
            library.write_bytes(native)
            with self.assertRaisesRegex(ValueError, "ARM64"):
                repack(apk, library, root / "wrong-abi.apk", 3, **(hashes | {"library_sha256": hashlib.sha256(native).hexdigest()}))
