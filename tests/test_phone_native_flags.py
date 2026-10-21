import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phone_native_flags as flags
from test_phone_registry import fixture as macho_fixture
from test_phone_registry_literals import LiteralImage, branch


FIELDS = (64, 66, 70)  # Authored layout differs from the SDK profile.


def byte_store(register, offset):
    return 0x39000000 | (offset << 10) | (31 << 5) | register


def zero_wide(offset=64):
    return 0xF9000000 | ((offset // 8) << 10) | (31 << 5) | 31


def fixture(body):
    words = list(body) + [0x910003E1]
    words += [branch(0x1000 + len(words) * 4, 0x2000), 0xD65F03C0]
    return LiteralImage(words)


def read(image):
    return flags.literal_bytes(image, "construct", image.target, FIELDS)


class NativeFlagTests(unittest.TestCase):
    def test_three_boolean_bytes_pack_without_treating_them_as_a_word(self):
        for value in range(8):
            bits = tuple((value >> bit) & 1 for bit in range(3))
            self.assertEqual(flags.pack_flags(bits), value)
            instructions = []
            for offset, bit in zip(FIELDS, bits):
                instructions += [0x5280000C | (bit << 5), byte_store(12, offset)]
            self.assertEqual(read(fixture(instructions)), bits)
        for values in ((0, 2, 0), (-1, 0, 0), (1, 0), (1, 0, 0, 0), (True, 0, 0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                flags.pack_flags(values)

    def test_byte_override_preserves_neighboring_wide_store_bytes(self):
        image = fixture([zero_wide(), 0x5280002C, byte_store(12, 66)])
        self.assertEqual(read(image), (0, 1, 0))
        self.assertEqual(flags.pack_flags(read(image)), 2)
        # Independently selected bytes may come from separate halves of a wide literal.
        image = fixture([0xD280002B, 0xF2E0002B, 0xF900000B | (8 << 10) | (31 << 5)])
        self.assertEqual(read(image), (1, 0, 1))

    def test_vector_bytes_require_a_proven_zero_vector(self):
        store = 0x3D800000 | (4 << 10) | (31 << 5) | 7
        self.assertEqual(read(fixture([0x6F00E407, store])), (0, 0, 0))
        with self.assertRaisesRegex(ValueError, "vector"):
            read(fixture([0x6F00E406, store]))

    def test_skipped_unknown_parameter_and_missing_byte_definitions_refuse(self):
        for body in (
            [zero_wide(), 0x5280002C, 0xB500004F, byte_store(12, 66)],
            [byte_store(0, 64), byte_store(0, 66), byte_store(0, 70)],
            [byte_store(31, 64), byte_store(31, 66)],
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                read(fixture(body))
        for fields in ((), (64, 64), (-1,), (112,), (True,)):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                flags.literal_bytes(fixture([zero_wide()]), "construct", 0x2000, fields)

    def test_frame_alias_call_unknown_access_and_loop_refuse(self):
        for extra in ([0x910043FF], [0xF9000000], [branch(0x1004, 0x2400)], [0], [0xB5FFFFEF], [0xD61F00E0]):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                read(fixture([zero_wide()] + extra))

    def test_output_overwrite_unknown_sdk_and_input_drift_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary, output = root / "sdk", root / "report.json"
            binary.write_bytes(macho_fixture())
            with self.assertRaisesRegex(ValueError, "Unknown owner SDK"):
                flags.inspect(binary, output)
            self.assertFalse(output.exists())
            row = {"persistentTypeID": 23, "flags": 5}
            with (
                patch.object(flags.registry, "BINARY_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest()),
                patch.object(flags, "decode", return_value=[row]),
            ):
                report = flags.inspect(binary, output)
                self.assertEqual(report["records"], [row])
                self.assertFalse(report["executes_sdk"])
                original = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    flags.inspect(binary, output)
                self.assertEqual(output.read_bytes(), original)

                def drift(image):
                    binary.write_bytes(b"changed during reading")
                    return [row]

                absent = root / "drift.json"
                with patch.object(flags, "decode", drift), self.assertRaisesRegex(ValueError, "changed during"):
                    flags.inspect(binary, absent)
                self.assertFalse(absent.exists())

    def test_optional_pinned_sdk_decodes_complete_native_flag_identity_set(self):
        sdk = Path(os.environ.get("ROR2_FLAGS_SDK", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"))
        if not sdk.is_file() or flags.sha(sdk) != flags.registry.BINARY_SHA256:
            self.skipTest("Optional pinned owner SDK is absent")
        with tempfile.TemporaryDirectory() as temporary:
            report = flags.inspect(sdk, Path(temporary) / "flags.json")
            self.assertEqual(len(report["records"]), 318)
            self.assertEqual(len({r["persistentTypeID"] for r in report["records"]}), 318)
            self.assertTrue(all(0 <= r["flags"] <= 7 for r in report["records"]))
            self.assertFalse(report["root_generation_qualified"])
            self.assertFalse(report["cache_population_qualified"])
