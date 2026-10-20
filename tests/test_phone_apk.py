import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from phone_apk import ANDROID_NAMESPACE, BUNDLE, PACKAGE, repack, update_manifest


def manifest(package=PACKAGE, *, utf8=True):
    # Independently authored binary XML, not an exported app manifest.
    strings = ["manifest", "package", package, ANDROID_NAMESPACE, "versionCode"]
    pool = bytearray()
    offsets = []
    for text in strings:
        offsets.append(len(pool))
        encoded = text.encode("utf-8" if utf8 else "utf-16-le")
        if utf8:
            pool.extend(bytes([len(text), len(encoded)]) + encoded + b"\0")
        else:
            pool.extend(struct.pack("<H", len(text)) + encoded + b"\0\0")
    pool.extend(bytes(-len(pool) % 4))
    string_chunk = struct.pack("<HHIIIIII", 1, 28, 28 + 4 * len(strings) + len(pool), len(strings), 0, 0x100 if utf8 else 0, 28 + 4 * len(strings), 0)
    string_chunk += struct.pack("<" + "I" * len(strings), *offsets) + pool
    attributes = struct.pack("<IIIHBBI", 0xFFFFFFFF, 1, 2, 8, 0, 3, 2)
    attributes += struct.pack("<IIIHBBI", 3, 4, 0xFFFFFFFF, 8, 0, 0x10, 2)
    element = struct.pack("<HHIII", 0x102, 16, 36 + len(attributes), 1, 0xFFFFFFFF)
    element += struct.pack("<IIHHHHHH", 0xFFFFFFFF, 0, 20, 20, 2, 0, 0, 0) + attributes
    return struct.pack("<HHI", 3, 8, 8 + len(string_chunk) + len(element)) + string_chunk + element


class PhoneApkTests(unittest.TestCase):
    def test_both_string_encodings_preserve_bytes_except_version_integer(self):
        for utf8 in (True, False):
            with self.subTest(utf8=utf8):
                original = manifest(utf8=utf8)
                updated, previous = update_manifest(original, 3)
                self.assertEqual(previous, 2)
                expected = original[:-4] + struct.pack("<I", 3)
                self.assertEqual(updated, expected)
                self.assertEqual(update_manifest(updated, 4)[1], 3)

    def test_refuses_wrong_identity_nonincreasing_version_and_truncated_data(self):
        for data, version in [(manifest("dev.other.app"), 3), (manifest(), 2), (manifest(), 1), (manifest(), True), (manifest()[:-1], 3)]:
            with self.subTest(version=version, size=len(data)):
                with self.assertRaises(ValueError):
                    update_manifest(data, version)
        data = bytearray(manifest())
        struct.pack_into("<I", data, 8 + 4, 0xFFFFFFF0)
        with self.assertRaises(ValueError):
            update_manifest(data, 3)

    def test_repack_preserves_native_bytes_and_inputs_drops_signatures_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            original, bundle, output = (root / name for name in ("base.apk", "candidate.bundle", "result.apk"))
            with zipfile.ZipFile(original, "w") as archive:
                for name, data in [
                    ("AndroidManifest.xml", manifest()),
                    (BUNDLE, b"old"),
                    ("lib/arm64-v8a/libfixture.so", b"authored-native-control"),
                    ("META-INF/CERT.RSA", b"old-signature"),
                    ("META-INF/NOTICE.txt", b"retain-notices"),
                ]:
                    archive.writestr(name, data)
            original_bytes = original.read_bytes()
            bundle.write_bytes(b"UnityFS\0authored-candidate")
            result = repack(original, bundle, output, 3)
            self.assertEqual((result["previous_version_code"], result["version_code"]), (2, 3))
            self.assertFalse(result["signed"])
            self.assertFalse(result["aligned"])
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read(BUNDLE), bundle.read_bytes())
                self.assertEqual(archive.read("lib/arm64-v8a/libfixture.so"), b"authored-native-control")
                self.assertEqual(archive.read("META-INF/NOTICE.txt"), b"retain-notices")
                self.assertNotIn("META-INF/CERT.RSA", archive.namelist())
            with self.assertRaises(FileExistsError):
                repack(original, bundle, output, 4)
            self.assertEqual(original.read_bytes(), original_bytes)
