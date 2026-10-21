"""Authored manager ABI/operand controls; the owner SDK is an optional fixture."""

import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_manager_retention as manager


class Image:
    def __init__(self):
        self.symbols = {manager.context.CONTEXT: {0x9000}}
        self.symbol_addresses = [0x9000]
        self.memory = {}

    def symbol(self, name):
        values = self.symbols.get(name, set())
        if len(values) != 1:
            raise ValueError("Missing or ambiguous authored symbol")
        return next(iter(values))

    def at(self, address, size):
        for start, data in self.memory.items():
            if start <= address and address + size <= start + len(data):
                return data[address - start : address - start + size]
        raise ValueError("Authored range not file backed")


def move(destination, source):
    return 0xAA0003E0 | source << 16 | destination


def load(destination, base, offset=0):
    return 0xF9400000 | (offset // 8) << 10 | base << 5 | destination


def consumer(extra_before=(), extra_after=(), offset=24):
    start = 0x1000
    values = [0x94000000 | ((0x9000 - start) // 4), *extra_before, 0x9A9F3000 | 19, *extra_after]
    values.extend([load(8, 19), load(9, 8, offset), move(0, 19), 0xD63F0000 | 9 << 5, 0xD65F03C0])
    return {start + 4 * i: word for i, word in enumerate(values)}


def table_fixture(name="Authored"):
    image = Image()
    encoded = manager.encoded_type(name)
    suffix = "N" + encoded + "E" if "::" in name else encoded
    image.symbols.update(
        {"__ZTV" + suffix: {0x4000}, "__ZTI" + suffix: {0x5000}, "__ZTS" + suffix: {0x5100}, "__ZNK11GameManager19ShouldWriteForBuildEv": {0xB000}}
    )
    image.memory = {
        0x4000: struct.pack("<6Q", 0, 0x5000, 0xB100, 0xB000, 0xB108, 0xB110),
        0x5000: struct.pack("<2Q", 0, 0x5100),
        0x5100: suffix.encode() + b"\0",
    }
    image.symbol_addresses = sorted({0x4030, *[v for values in image.symbols.values() for v in values]})
    records = [
        dict(self=1, parent=0, qualifiedName="Object", persistentTypeID=1),
        dict(self=2, parent=1, qualifiedName="GameManager", persistentTypeID=2),
        dict(self=3, parent=2, qualifiedName=name, persistentTypeID=3),
    ]
    row = dict(context_index=0, qualified_name=name, persistent_type_id=3, role="global")
    return image, row, records


class ManagerDispatchTests(unittest.TestCase):
    def test_nullable_receiver_and_derived_virtual_offset(self):
        for offset in (8, 24, 328):
            words = consumer(offset=offset)
            result = manager.dispatch(Image(), words)
            self.assertEqual(result["function_offset"], offset)
            self.assertEqual(result["nonzero_receiver_source"], "manager-context")
            self.assertIs(result["nullable_receiver"], True)

    def test_known_arithmetic_has_only_destination_effects(self):
        # Authored SUB W8, W8, W9; ADD X8, X22, X8; LSR; AND-immediate.
        for instruction in (0x4B090108, 0x8B0802C8, 0x53000008, 0x92400008):
            self.assertEqual(manager.effects(instruction), {8})
            manager.dispatch(Image(), consumer(extra_before=(instruction,), extra_after=(instruction,)))
            for position in ("before", "after"):
                clobber = (instruction & ~31) | (0 if position == "before" else 19)
                with self.subTest(instruction=hex(instruction), position=position), self.assertRaises(ValueError):
                    manager.dispatch(Image(), consumer(**{"extra_" + position: (clobber,)}))
        # An ABI call preserves X19 after the nullable receiver was saved.
        manager.dispatch(Image(), consumer(extra_after=(0x94000000,)))

    def test_receiver_call_null_alternative_and_unknown_effect_refuse(self):
        for change in ("foreign-call", "foreign-alternative", "unknown-before", "unknown-after", "call-clobber"):
            words = consumer()
            if change == "foreign-call":
                words[0x1000] = 0x94000000 | ((0xA000 - 0x1000) // 4)
            elif change == "foreign-alternative":
                words[0x1004] = (words[0x1004] & ~(31 << 16)) | 2 << 16
            elif change == "unknown-before":
                words = consumer(extra_before=(0xFFFFFFFF,))
            elif change == "unknown-after":
                words = consumer(extra_after=(0xFFFFFFFF,))
            else:
                words = consumer(extra_before=(0x94000000,))
            with self.subTest(change=change), self.assertRaises(ValueError):
                manager.dispatch(Image(), words)

    def test_skipped_and_mismatched_virtual_definitions_refuse(self):
        for change in ("first-offset", "second-base", "receiver", "call-register", "skipped", "multiple", "zero-slot"):
            words = consumer()
            call = max(words) - 4
            if change == "first-offset":
                words[call - 12] = load(8, 19, 8)
            elif change == "second-base":
                words[call - 8] = load(9, 20, 24)
            elif change == "receiver":
                words[call - 4] = move(0, 20)
            elif change == "call-register":
                words[call] = 0xD63F0000 | 10 << 5
            elif change == "skipped":
                words[0x1000] = 0xB4000000 | (((call - 8 - 0x1000) // 4) << 5)
            elif change == "multiple":
                words[max(words)] = words[call]
            else:
                words = consumer(offset=0)
            with self.subTest(change=change), self.assertRaises(ValueError):
                manager.dispatch(Image(), words)

    def test_missing_and_ambiguous_consumer_names_refuse(self):
        image = Image()
        with self.assertRaises(ValueError):
            manager.unique_symbol(image, "authored")
        image.symbols.update({"authored-one": {1}, "authored-two": {2}})
        with self.assertRaises(ValueError):
            manager.unique_symbol(image, "authored")


class ManagerVtableTests(unittest.TestCase):
    def test_primary_rtti_identity_and_native_ancestor_binding(self):
        for name in ("Authored", "Lab::Authored"):
            image, row, records = table_fixture(name)
            result = manager.table_binding(image, row, records, 8)
            self.assertEqual(result["address_point"], 0x4010)
            self.assertEqual(result["implementation_owner"], "GameManager")
            self.assertEqual(result["persistent_type_id"], 3)
            self.assertEqual(result["function_offset"], 8)
        for name in ("", "A<int>", "A::", "../A", "1A"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                manager.encoded_type(name)

    def test_unknown_secondary_or_ambiguous_tables_and_types_refuse(self):
        for change in (
            "secondary",
            "typeinfo",
            "typename",
            "identity",
            "extent",
            "outside",
            "unaligned",
            "target",
            "missing-parent",
            "cycle",
            "duplicate-record",
            "ambiguous-override",
        ):
            image, row, records = table_fixture()
            offset = 8
            if change in ("secondary", "typeinfo"):
                values = list(struct.unpack("<6Q", image.memory[0x4000]))
                values[0 if change == "secondary" else 1] = 0xFFFF
                image.memory[0x4000] = struct.pack("<6Q", *values)
            elif change == "typename":
                image.memory[0x5100] = b"8Intruder\0"
            elif change == "identity":
                row["persistent_type_id"] = 99
            elif change == "extent":
                image.symbol_addresses.insert(1, 0x4008)
            elif change == "outside":
                offset = 40
            elif change == "unaligned":
                offset = 3
            elif change == "target":
                image.memory[0x4000] = struct.pack("<6Q", 0, 0x5000, 0, 0xC000, 0, 0)
            elif change == "missing-parent":
                records[-1]["parent"] = 99
            elif change == "cycle":
                records[1]["parent"] = 3
            elif change == "duplicate-record":
                records.append(dict(records[1]))
            else:
                image.symbols["__ZNK8Authored19ShouldWriteForBuildEv"] = {0xB000}
            with self.subTest(change=change), self.assertRaises(ValueError):
                manager.table_binding(image, row, records, offset)


class ManagerRetentionCliTests(unittest.TestCase):
    def test_isolated_unknown_sdk_refuses_without_output_and_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            sdk, output = Path(temporary) / "sdk", Path(temporary) / "output.json"
            sdk.write_bytes(b"Authored unknown SDK")
            result = subprocess.run([sys.executable, "-I", "-S", manager.__file__, str(sdk), str(output)], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unknown owner SDK", result.stderr)
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertFalse(output.exists())
            output.write_bytes(b"existing receipt")
            with self.assertRaises(FileExistsError):
                manager.inspect(sdk, output)
            self.assertEqual(output.read_bytes(), b"existing receipt")

    def test_optional_exact_sdk_metadata_keeps_all_retention_qualifications_false(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity")
        if not sdk.is_file():
            self.skipTest("Optional owner SDK absent")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            result = manager.inspect(sdk, output)
            self.assertEqual((result["global_count"], result["level_count"]), (20, 4))
            self.assertEqual(len(result["consumers"]), 2)
            self.assertEqual(len({r["function_offset"] for r in result["consumers"]}), 1)
            self.assertEqual(len(result["bindings"]), 24)
            self.assertEqual(sum(r["implementation_owner"] == "GameManager" for r in result["bindings"]), 21)
            self.assertEqual(
                {r["qualified_name"] for r in result["bindings"] if r["implementation_owner"] != "GameManager"},
                {"ClusterInputManager", "UnityConnectSettings", "OcclusionCullingSettings"},
            )
            for key in (
                "executes_sdk",
                "live_context_qualified",
                "target_retention_qualified",
                "state_retention_qualified",
                "native_usage_qualified",
                "root_generation_qualified",
            ):
                self.assertIs(result[key], False)
            self.assertEqual(json.loads(output.read_text()), result)
