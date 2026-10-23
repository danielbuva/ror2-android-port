"""Check real ZIP geometry and unchanged content using only authored entries."""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/assemble.py"
SPEC = importlib.util.spec_from_file_location("accepted_output_assembly", SCRIPT)
ASSEMBLY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSEMBLY)


def fixture(root, prefix_length):
    targets = root / "targets"
    contents = {
        "AndroidManifest.xml": b"authored manifest" * prefix_length,
        "resources.arsc": b"authored table",
        "classes.dex": b"authored code",
        "META-INF/old.sf": b"stale",
    }
    rows = []
    for index, (name, data) in enumerate(contents.items()):
        path = targets / "apk" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        rows.append(
            {
                "path": "apk/" + name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "mode": "private-target-frame",
                "patch": f"patches/{index}.zst",
                "patch_bytes": 1,
            }
        )
    data = json.dumps({"schema": "private-accepted-output-delta-v1", "tool": {"flags": ["-3", "--single-thread"]}, "targets": rows}).encode()
    manifest = root / "manifest.json"
    manifest.write_bytes(data)
    return targets, contents, manifest, hashlib.sha256(data).hexdigest()


class AcceptedOutputAssemblyTests(unittest.TestCase):
    def test_resource_local_data_is_stored_aligned_and_content_unchanged(self):
        for prefix_length in range(1, 9):
            with self.subTest(prefix_length=prefix_length), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                targets, contents, manifest, pin = fixture(root, prefix_length)
                output = root / "unsigned.apk"
                result = ASSEMBLY.assemble(manifest, pin, targets, output)
                self.assertFalse(result["signed"])
                self.assertFalse(result["install_qualified"])
                with zipfile.ZipFile(output) as archive, output.open("rb") as raw:
                    self.assertEqual(set(archive.namelist()), set(contents) - {"META-INF/old.sf"})
                    for name in archive.namelist():
                        self.assertEqual(archive.read(name), contents[name])
                    resource = archive.getinfo("resources.arsc")
                    self.assertEqual(resource.compress_type, zipfile.ZIP_STORED)
                    raw.seek(resource.header_offset)
                    local = raw.read(30)
                    name_bytes, extra_bytes = struct.unpack_from("<HH", local, 26)
                    data_offset = resource.header_offset + 30 + name_bytes + extra_bytes
                    self.assertEqual(data_offset % 4, 0)
                    raw.seek(data_offset)
                    self.assertEqual(raw.read(resource.file_size), contents["resources.arsc"])
                with self.assertRaises(FileExistsError):
                    ASSEMBLY.assemble(manifest, pin, targets, output)
                self.assertEqual((targets / "apk/resources.arsc").read_bytes(), contents["resources.arsc"])

    def test_refuses_input_drift_and_never_overwrites_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            targets, contents, manifest, pin = fixture(root, 1)
            original = targets / "apk/resources.arsc"
            with self.assertRaisesRegex(ValueError, "overlaps"):
                ASSEMBLY.assemble(manifest, pin, targets, original)
            self.assertEqual(original.read_bytes(), contents["resources.arsc"])
            original.write_bytes(b"different")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                ASSEMBLY.assemble(manifest, pin, targets, root / "failed.apk")
