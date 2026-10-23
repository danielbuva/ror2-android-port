"""Reproduce and stream a complete authored packet through the real producer."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/package.py"
SPEC = importlib.util.spec_from_file_location("accepted_output_package", SCRIPT)
PACKET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKET)


class AcceptedOutputPackageTests(unittest.TestCase):
    def test_wrong_profile_pin_refuses_before_parsing_or_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "profile.json"
            manifest.write_bytes(b"not even JSON")
            with self.assertRaisesRegex(ValueError, "pin differs"):
                PACKET.profile(manifest, "0" * 64)
            self.assertEqual(list(Path(temporary).iterdir()), [manifest])

    def test_complete_packet_reproduction_and_stream_integrity(self):
        codec = shutil.which("zstd")
        if codec is None:
            self.skipTest("optional upstream zstd CLI absent; complete Android proof is separate")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, targets, sdk = (root / x for x in ("pc", "targets", "sdk"))
            for path in (pc, targets, sdk):
                path.mkdir()
            original = b"authored original bytes " * 1000
            (pc / "original").write_bytes(original)
            (sdk / "engine").write_bytes(b"authored generic SDK fixture")
            contents = {
                "apk/engine": (sdk / "engine").read_bytes(),
                "payload/changed": original.replace(b"bytes", b"other"),
                "apk/standalone": b"authored new data" * 100,
            }
            rows = []
            frames = []
            reference = {"path": "original", "bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()}
            for index, (name, content) in enumerate(contents.items()):
                target = targets / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                row = {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                if index == 0:
                    row.update(mode="sdk-copy", reference={"path": "engine", "bytes": len(content), "sha256": row["sha256"]})
                    frames.append(content)
                else:
                    command = [codec, "-3", "--single-thread", "-q", "-c"]
                    if index == 1:
                        command += ["--patch-from", str(pc / "original")]
                        row["reference"] = reference
                    frame = subprocess.check_output(command + ["--", str(target)])
                    row.update(
                        mode="private-delta" if index == 1 else "private-target-frame",
                        patch=f"patches/{index:04d}.zst",
                        patch_bytes=len(frame),
                        patch_sha256=hashlib.sha256(frame).hexdigest(),
                    )
                    frames.append(frame)
                rows.append(row)
            manifest = root / "profile.json"
            data = json.dumps(
                {
                    "schema": "private-accepted-output-delta-v1",
                    "tool": {"sha256": PACKET.sha(Path(codec)), "flags": ["-3", "--single-thread"]},
                    "sources": [reference],
                    "targets": rows,
                }
            ).encode()
            manifest.write_bytes(data)
            pin = hashlib.sha256(data).hexdigest()
            output = root / "packet"
            result = PACKET.create(manifest, pin, targets, pc, sdk, codec, output)
            self.assertTrue(result["success"])
            self.assertEqual(result["targets_verified"], 3)
            self.assertEqual((output / "manifest.json").read_bytes(), data)
            self.assertEqual((pc / "original").read_bytes(), original)
            emitted = io.BytesIO()
            PACKET.stream(output, pin, sdk, emitted)
            wire = emitted.getvalue()
            self.assertEqual(wire[:8], b"R2DLT01\n")
            size = struct.unpack(">I", wire[8:12])[0]
            self.assertEqual(wire[12 : 12 + size], data)
            self.assertEqual(wire[12 + size :], b"".join(frames))
            for index, row in enumerate(rows[1:], 1):
                command = [codec, "-d", "-q", "-c"]
                if index == 1:
                    command += ["--patch-from", str(pc / "original")]
                restored = subprocess.check_output(command + ["--", str(output / row["patch"])])
                self.assertEqual(restored, contents[row["path"]])
            with self.assertRaises(FileExistsError):
                PACKET.create(manifest, pin, targets, pc, sdk, codec, output)
            self.assertEqual((output / "manifest.json").read_bytes(), data)
            # A damaged frame must refuse before the transport receives a header.
            (output / rows[-1]["patch"]).write_bytes(b"damaged")
            refused = io.BytesIO()
            with self.assertRaisesRegex(ValueError, "hash differs"):
                PACKET.stream(output, pin, sdk, refused)
            self.assertEqual(refused.getvalue(), b"")

    def test_packet_output_cannot_write_into_an_input_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "overlaps"):
                PACKET.create(root / "unused", "unused", root, root, root, root, root / "packet")
            self.assertFalse((root / "packet").exists())
