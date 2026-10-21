import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_manager_context as manager


def move(destination, source):
    return 0xAA0003E0 | source << 16 | destination


def store(source, base, offset):
    return 0xF9000000 | (offset // 8) << 10 | base << 5 | source


def adr(destination, pc, address, page=False):
    value = (address - (pc & ~4095)) // 4096 if page else address - pc
    value &= 0x1FFFFF
    return (0x90000000 if page else 0x10000000) | (value & 3) << 29 | (value >> 2) << 5 | destination


class Image:
    def __init__(self, words=None, strings=None, extra=None, start=0x1000):
        self.start = start
        self.words = dict(words or {})
        self.strings = dict(strings or {})
        self.extra = dict(extra or {})
        end = max(self.words, default=start) + 4
        self.symbol_addresses = [start, end, 0x9000, 0x9004]
        self.symbols = {"authored": {start}, "end": {end}, "lookup": {0x9000}, "lookup-end": {0x9004}}

    def at(self, address, size):
        for start, value in self.extra.items():
            if start <= address and address + size <= start + len(value):
                return value[address - start : address - start + size]
        for start, value in self.strings.items():
            data = value.encode() + b"\0"
            if start <= address and address + size <= start + len(data):
                return data[address - start : address - start + size]
        return b"".join(struct.pack("<I", self.words[pc]) for pc in range(address, address + size, 4))


def registration_image(order=(0, 2, 1), between=(), skip_definition=False, duplicate_name=False):
    start = 0x1000
    values = [move(19, 0)]
    strings = {}
    for index in order:
        pointer = 0x4000 + 64 * index
        strings[pointer] = "Authored" + str(0 if duplicate_name else index)
        if skip_definition:
            values.append(0xB4000040)  # CBZ X0 skips the defining ADR on one path.
        values.extend([adr(20, start + 4 * len(values), pointer), move(1, 20), 0x52800002])
        pc = start + 4 * len(values)
        values.append(0x94000000 | ((0x9000 - pc) // 4))
        values.extend(between)
        values.extend([store(0, 19, 24 + 8 * index), store(20, 19, 48 + 8 * index)])
    values.append(0xD65F03C0)
    return Image({start + 4 * i: v for i, v in enumerate(values)}, strings)


def predicate_image(indices=(0, 1), base=10, first=12, second=13):
    start, address = 0x3000, 0x8000
    values = [
        adr(base, start, address, page=True),
        0x91000000 | base << 5 | base,
        0x29400000 | second << 10 | base << 5 | first,
        0x6B00001F | first << 5,
        0x1A9F07E0 | first,
        0x6B00001F | second << 5,
        0x1A9F07E0 | second,
        0x0A000000 | second << 16 | first << 5,
        0xD65F03C0,
    ]
    return Image({start + 4 * i: v for i, v in enumerate(values)}, extra={address: struct.pack("<2I", *indices)}, start=start)


class ManagerDeclarationTests(unittest.TestCase):
    def test_context_bound_is_the_incoming_parameter_with_a_forward_guard(self):
        words = {0x1000: 0x71000C1F, 0x1004: 0x5400002B, 0x1008: 0xD65F03C0}
        image = Image(words)
        self.assertEqual(manager.capacity(image, words), 3)
        for change in ("zero", "clobber", "backward", "wrong-condition"):
            with self.subTest(change=change):
                mutant = dict(words)
                if change == "zero":
                    mutant[0x1000] = 0x7100001F
                elif change == "clobber":
                    mutant[0xFFC] = 0x52800000
                elif change == "backward":
                    mutant[0x1004] = 0x54FFFFEB
                else:
                    mutant[0x1004] = 0x54000020
                with self.assertRaises(ValueError):
                    manager.capacity(Image(mutant, start=min(mutant)), mutant)

    def test_slot_offsets_define_order_and_dead_local_initialization_is_proven_safe(self):
        for between in ((), (0xD2800016,)):
            image = registration_image(between=between)
            rows = manager.entries(image, image.words, 3, 0x9000)
            self.assertEqual([r["context_index"] for r in rows], [0, 1, 2])
            self.assertEqual([r["name"] for r in rows], ["Authored0", "Authored1", "Authored2"])
            self.assertGreater(rows[1]["lookup_pc"], rows[2]["lookup_pc"])

    def test_clobbered_skipped_and_escaping_store_operands_refuse(self):
        for instruction in (0xD2800000, 0xD2800013, 0xD2800014, 0x14000001, 0x94000001, 0xFFFFFFFF):
            with self.subTest(instruction=hex(instruction)):
                image = registration_image(between=(instruction,))
                with self.assertRaises(ValueError):
                    manager.entries(image, image.words, 3, 0x9000)
        image = registration_image(skip_definition=True)
        with self.assertRaisesRegex(ValueError, "another path"):
            manager.entries(image, image.words, 3, 0x9000)

    def test_incomplete_duplicate_or_mismatched_declarations_refuse(self):
        for image in (registration_image(order=(0, 2)), registration_image(order=(0, 0, 2)), registration_image(duplicate_name=True)):
            with self.subTest(image=image), self.assertRaises(ValueError):
                manager.entries(image, image.words, 3, 0x9000)
        image = registration_image()
        position = next(pc for pc, word in image.words.items() if word == store(20, 19, 48))
        image.words[position] = store(20, 19, 56)
        with self.assertRaisesRegex(ValueError, "mismatched"):
            manager.entries(image, image.words, 3, 0x9000)

    def test_pair_predicate_reads_literal_data_and_refuses_changed_semantics(self):
        image = predicate_image()
        self.assertEqual(manager.dependency_exclusions(image, image.words, 2)["context_indices"], [0, 1])
        for image in (predicate_image(indices=(0, 0)), predicate_image(indices=(0, 2)), predicate_image(base=0), predicate_image(first=13, second=13)):
            with self.subTest(image=image), self.assertRaises(ValueError):
                manager.dependency_exclusions(image, image.words, 2)
        for index in (0, 1, 2, 3, 4, 5, 6, 7, 8):
            image = predicate_image()
            image.words[image.start + 4 * index] = 0xFFFFFFFF
            with self.subTest(index=index), self.assertRaises(ValueError):
                manager.dependency_exclusions(image, image.words, 2)

    def test_native_identity_role_and_graph_refusals(self):
        rows = [
            dict(self=1, parent=0, name="Object", qualifiedName="Object", persistentTypeID=1),
            dict(self=2, parent=1, name="GlobalGameManager", qualifiedName="GlobalGameManager", persistentTypeID=2),
            dict(self=3, parent=1, name="LevelGameManager", qualifiedName="LevelGameManager", persistentTypeID=3),
            *(
                dict(self=4 + i, parent=2 if i < 2 else 3, name="Authored" + str(i), qualifiedName="Authored" + str(i), persistentTypeID=20 + i)
                for i in range(3)
            ),
        ]
        image = registration_image()
        declarations = manager.entries(image, image.words, 3, 0x9000)
        actual, globals = manager.classify(declarations, rows)
        self.assertEqual(globals, 2)
        self.assertEqual([r["persistent_type_id"] for r in actual], [20, 21, 22])
        for parent in (5, 999):
            mutant = copy.deepcopy(rows)
            mutant[4]["parent"] = parent
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                manager.classify(declarations, mutant)
        ambiguous = rows + [dict(rows[3], self=9, persistentTypeID=29)]
        with self.assertRaisesRegex(ValueError, "ambiguous declared"):
            manager.classify(declarations, ambiguous)
        with self.assertRaisesRegex(ValueError, "partition"):
            manager.classify([declarations[0], declarations[2], declarations[1]], rows)


class PinnedManagerSdkTests(unittest.TestCase):
    def test_actual_sdk_metadata_keeps_all_runtime_retention_qualifications_false(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity")
        if not sdk.is_file():
            self.skipTest("Optional owner SDK absent")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "manager.json"
            result = manager.inspect(sdk, output)
            self.assertEqual((result["context_capacity"], result["global_count"], result["level_count"]), (24, 20, 4))
            self.assertEqual(len({r["persistent_type_id"] for r in result["registrations"]}), 24)
            self.assertEqual(len(result["asset_dependency_exclusions"]["native_types"]), 2)
            for key in ("executes_sdk", "live_context_qualified", "target_retention_qualified", "root_generation_qualified"):
                self.assertIs(result[key], False)
            self.assertEqual(json.loads(output.read_text()), result)
            with self.assertRaises(FileExistsError):
                manager.inspect(sdk, output)
            unknown = Path(temporary) / "unknown-sdk"
            unknown.write_bytes(b"authored unknown SDK control")
            with self.assertRaisesRegex(ValueError, "Unknown owner SDK"):
                manager.inspect(unknown, Path(temporary) / "unknown.json")
            self.assertFalse((Path(temporary) / "unknown.json").exists())


class ManagerStandaloneLaunchTests(unittest.TestCase):
    def test_isolated_cli_loads_authored_siblings_before_refusing_unknown_sdk(self):
        with tempfile.TemporaryDirectory() as temporary:
            unknown = Path(temporary) / "unknown-sdk"
            unknown.write_bytes(b"authored unknown SDK control")
            output = Path(temporary) / "output.json"
            result = subprocess.run([sys.executable, "-I", "-S", manager.__file__, str(unknown), str(output)], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unknown owner SDK", result.stderr)
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
