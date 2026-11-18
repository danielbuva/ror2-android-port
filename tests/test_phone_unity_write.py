"""Authored structural fixtures and independent UnityPy decoding, no game data."""

import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import lz4.block
import UnityPy

from phone_bundle import ASSET, make_bundle


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("unity_writer", ROOT / "tools/phone-build/accepted-output/unity_write.py")
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


def compress(data, method):
    return data if method == 0 else lz4.block.compress(data, store_size=False, mode="high_compression", compression=12)


def member(data):
    result = io.BytesIO(data)
    result.size = len(data)
    return result


class UnityWriteTests(unittest.TestCase):
    def test_structural_reconstruction_retains_complete_authored_native_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.write_bytes(make_bundle("authored 𐐷 text"))
            bundle = W.B.Bundle(source)
            name = next(iter(bundle.members))
            original = bundle.member(name)
            layout = W.read_serialized(original)
            output = io.BytesIO()

            def body(row):
                original.seek(layout["data_offset"] + row["offset"])
                return original

            W.write_serialized(output, layout, body)
            original.seek(0)
            self.assertEqual(output.getvalue(), original.read())
            parsed = UnityPy.load(output.getvalue())
            self.assertEqual(parsed.container[ASSET].read().m_Script, "authored 𐐷 text")

    def test_physical_body_order_independent_of_table_order_and_no_tail_alignment(self):
        types = [{"class_id": 49, "stripped": 0, "script_type": -1, "hash": bytes(16)}]
        layout = {
            "engine": "2021.3.45f2",
            "platform": 13,
            "trees": False,
            "types": types,
            "objects": [{"path_id": -9, "offset": 8, "bytes": 3, "type_id": 0}, {"path_id": 7, "offset": 0, "bytes": 5, "type_id": 0}],
            "scripts": [(2, -987)],
            "externals": [{"empty": "", "guid": bytes(range(16)), "type": 2, "path": "archive:/CAB-external/CAB-external"}],
            "ref_types": [{"class_id": 114, "stripped": 1, "script_type": 3, "script_id": bytes(range(16)), "hash": bytes(16)}],
            "user": "authored",
        }
        output = io.BytesIO()
        W.write_serialized(output, layout, lambda row: io.BytesIO({7: b"FIRST", -9: b"end"}[row["path_id"]]))
        data = output.getvalue()
        parsed = W.read_serialized(member(data))
        self.assertEqual(parsed["objects"], layout["objects"])
        self.assertEqual(parsed["scripts"], layout["scripts"])
        self.assertEqual(parsed["externals"], layout["externals"])
        self.assertEqual(parsed["ref_types"], layout["ref_types"])
        self.assertEqual(data[4096:], b"FIRST\0\0\0end")
        env = UnityPy.load(data)
        self.assertEqual([obj.path_id for obj in env.objects], [-9, 7])
        self.assertEqual(env.objects[0].get_raw_data(), b"end")

    def test_lz4_bundle_cross_member_blocks_directory_position_and_raw_fallback(self):
        data = (b"repeat repeated 1234" * 30, bytes(range(256)), b"suffix")
        members = [
            (name, 4 if i == 0 else 0, len(value), lambda value=value: io.BytesIO(value))
            for i, (name, value) in enumerate(zip(("CAB-authored", "CAB-authored.resS", "extra"), data))
        ]
        for version in (7, 8):
            for flags in (0x40, 0x43, 0x243, 0x2C3):
                with self.subTest(version=version, flags=flags), tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "bundle"
                    with path.open("xb") as output:
                        report = W.write_bundle(output, members, compress, version=version, flags=flags, block_size=256, hash_output=True)
                    self.assertEqual(report["bytes"], path.stat().st_size)
                    self.assertEqual(report["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                    parsed = W.B.Bundle(path)
                    self.assertEqual([parsed.member(name).read() for name, *_ in members], list(data))
                    if flags & 63:
                        self.assertTrue(any(block[3] == 0 for block in parsed.blocks))
                    self.assertEqual(parsed.read(0, sum(map(len, data))), b"".join(data))

    def test_compressed_native_fixture_is_independently_loadable(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "raw"
            source.write_bytes(make_bundle())
            raw = W.B.Bundle(source)
            name = next(iter(raw.members))
            data = raw.member(name).read()
            result = io.BytesIO()
            W.write_bundle(result, [(name, 4, len(data), lambda: io.BytesIO(data))], compress)
            self.assertEqual(UnityPy.load(result.getvalue()).container[ASSET].read().m_Name, "phone-fixture")

    def test_rejects_duplicate_members_bad_extents_and_destination_overlap(self):
        row = ("CAB-authored", 4, 1, lambda: io.BytesIO(b"x"))
        for members in (
            [row, row],
            [("bad\0name", 4, 0, lambda: io.BytesIO())],
            [("short", 0, 2, lambda: io.BytesIO(b"x"))],
            [("long", 0, 0, lambda: io.BytesIO(b"x"))],
        ):
            with self.subTest(members=members), self.assertRaises(ValueError):
                W.write_bundle(io.BytesIO(), members, compress)
        with self.assertRaises(ValueError):
            W.write_bundle(io.BytesIO(), [row], compress, block_size=0)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "raw"
            path.write_bytes(make_bundle())
            raw = W.B.Bundle(path)
            layout = W.read_serialized(raw.member(next(iter(raw.members))))
            layout["objects"][1]["offset"] = 0
            with self.assertRaisesRegex(ValueError, "overlapping"):
                W.write_serialized(io.BytesIO(), layout, lambda row: io.BytesIO(bytes(row["bytes"])))

    def test_native_codec_child_is_pinned_and_reaped(self):
        with tempfile.TemporaryDirectory() as temporary:
            tool = Path(temporary) / "codec"
            tool.write_text("#!/usr/bin/env python3\nimport sys\nsys.stdin.buffer.read()\n")
            tool.chmod(0o700)
            with self.assertRaisesRegex(ValueError, "codec drift"):
                W.Codec(tool, "0" * 64)
            with W.codec(tool, hashlib.sha256(tool.read_bytes()).hexdigest()) as child:
                process = child.child
                self.assertIsNone(process.poll())
            self.assertEqual(process.returncode, 0)

    def test_native_codec_pipeline_preserves_scalar_layout_and_checked_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            tool = Path(temporary) / "codec"
            tool.write_text(
                f"#!{sys.executable}\n"
                "import struct, sys, lz4.block\n"
                "while header := sys.stdin.buffer.read(8):\n"
                "    size, method = struct.unpack('<II', header)\n"
                "    data = sys.stdin.buffer.read(size)\n"
                "    assert len(data) == size and method == 3\n"
                "    encoded = lz4.block.compress(data, store_size=False, mode='high_compression', compression=12)\n"
                "    sys.stdout.buffer.write(struct.pack('<I', len(encoded)) + encoded)\n"
                "    sys.stdout.buffer.flush()\n"
            )
            tool.chmod(0o700)
            data = (b"authored content" * 12_000, hashlib.shake_256(b"authored entropy").digest(300_000))
            members = [(str(i), 0, len(part), lambda part=part: io.BytesIO(part)) for i, part in enumerate(data)]
            expected, actual = io.BytesIO(), io.BytesIO()
            pin = hashlib.sha256(tool.read_bytes()).hexdigest()
            with W.codec(tool, pin) as child:
                W.write_bundle(expected, members, lambda raw, method: child(raw, method))
            with W.codec(tool, pin) as child:
                report = W.write_bundle(actual, members, child, hash_output=True)
            self.assertEqual(actual.getvalue(), expected.getvalue())
            self.assertEqual(report["sha256"], hashlib.sha256(expected.getvalue()).hexdigest())

            with self.assertRaisesRegex(ValueError, "roundtrip differs"), patch.object(W.B, "decompress", return_value=b"invalid"):
                with W.codec(tool, pin) as child:
                    W.write_bundle(io.BytesIO(), members, child)
            self.assertIsNotNone(child.child.poll())

    def test_serialized_metadata_requires_v22_and_valid_identity_extents(self):
        with self.assertRaises(ValueError):
            W.read_serialized(member(bytes(48)))
        with self.assertRaises(ValueError):
            W.type_record({"class_id": 49, "stripped": 0, "script_type": -1, "hash": b"bad"}, False)
        with self.assertRaises(ValueError):
            W.type_record({"class_id": 49, "stripped": 0, "script_type": -1, "hash": bytes(16), "tree": struct.pack("<II", 1, 0)}, True)


if __name__ == "__main__":
    unittest.main()
