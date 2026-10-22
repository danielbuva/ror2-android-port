"""Authored ARM64 operand fixtures; no captured SDK instructions or target table."""

import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("record_links_test", ROOT / "scripts/lab/phone_target_records.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
BASE, ASSIGN, RECORD, PAIR = 0x10000, 0x80000, 0x90000, 0xA0000


def move(destination, source):
    return 0xAA0003E0 | source << 16 | destination


def add(destination, source, value):
    return 0x91000000 | value << 10 | source << 5 | destination


def load(destination, source, field, width):
    return (0x39400000 if width == 1 else 0xF9400000) | (field // width) << 10 | source << 5 | destination


def call(pc, target):
    return 0x94000000 | (((target - pc) // 4) & 0x3FFFFFF)


def words(values, base=BASE):
    return {base + index * 4: value for index, value in enumerate(values)}


def copies(spacing=48, count=7):
    values = [move(19, 0), move(20, 1)]
    for index in range(count):
        values += [add(0, 19, index * spacing), add(1, 20, index * spacing)]
        values += [call(BASE + len(values) * 4, ASSIGN)]
    return words([*values, 0xD65F03C0])


def pair(spacing=48):
    values = [move(20, 0), move(21, 3), move(22, 2), move(23, 1), 0x52800029, 0x39000000 | 32 << 10 | 20 << 5 | 9, move(0, 20), move(1, 23)]
    values += [call(BASE + len(values) * 4, ASSIGN), add(0, 20, spacing), move(1, 22), move(2, 21)]
    values += [call(BASE + len(values) * 4, RECORD), 0xD65F03C0]
    return words(values)


def node(displacement=8):
    values = [add(3, 20, 20), add(0, 23, displacement), move(1, 22), move(2, 21)]
    values += [call(BASE + len(values) * 4, PAIR), 0xB9000000 | 23 << 5 | 24, 0xD65F03C0]
    return words(values)


def consumer(field=200):
    return words([add(19, 0, field), load(8, 0, field + 32, 1), 0x7100041F | 8 << 5, 0x54000000 | 2 << 5, load(19, 19, 0, 8), 0xD65F03C0])


class CopyTests(unittest.TestCase):
    def test_offsets_are_derived_for_different_authored_layouts(self):
        for spacing, count in ((48, 7), (40, 3)):
            with self.subTest(spacing=spacing, count=count):
                self.assertEqual(r.copied_strings(copies(spacing, count), ASSIGN), (list(range(0, spacing * count, spacing)), spacing))
                self.assertEqual(r.pair_value(pair(spacing), ASSIGN, RECORD, spacing), (spacing, 32))

    def test_changed_source_destination_call_and_skipped_copy_refuse(self):
        mutations = [(BASE + 12, add(1, 20, 8)), (BASE + 20, add(0, 19, 49)), (BASE + 28, 0xD503201F), (BASE, 0x54000000 | 5 << 5)]
        for pc, word in mutations:
            with self.subTest(pc=pc, word=word), self.assertRaises(ValueError):
                mutated = copies()
                mutated[pc] = word
                r.copied_strings(mutated, ASSIGN)

    def test_pair_value_source_memlabel_and_mode_mutations_refuse(self):
        for index, word in ((9, add(0, 20, 96)), (10, move(1, 23)), (11, move(2, 22)), (4, 0x52800049), (5, 0x39000000 | 64 << 10 | 20 << 5 | 9)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                mutated = pair()
                mutated[BASE + index * 4] = word
                r.pair_value(mutated, ASSIGN, RECORD, 48)


class LocalGeometryTests(unittest.TestCase):
    def test_node_displacement_is_relative_to_same_header_write(self):
        for displacement in (8, 16, 24):
            self.assertEqual(r.local_node_geometry(node(displacement), PAIR), displacement)
        for index, value in ((1, add(0, 31, 8)), (1, add(0, 23, 0)), (5, 0xB9000000 | 22 << 5 | 24), (5, 0xF9000000 | 23 << 5 | 24)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                mutated = node()
                mutated[BASE + index * 4] = value
                r.local_node_geometry(mutated, PAIR)

    def test_consumer_inline_heap_and_mode_offsets(self):
        for field in (88, 200, 248):
            self.assertEqual(r.consumer_geometry(consumer(field)), (field, 32))
        for index, value in (
            (0, add(19, 1, 200)),
            (1, load(8, 1, 232, 1)),
            (2, 0x7100081F | 8 << 5),
            (3, 0x54000001 | 2 << 5),
            (3, 0x54000000 | 3 << 5),
            (4, load(19, 20, 0, 8)),
        ):
            with self.subTest(index=index), self.assertRaises(ValueError):
                mutated = consumer()
                mutated[BASE + index * 4] = value
                r.consumer_geometry(mutated)


class Image:
    """Independent authored functions with only the symbol/byte interface needed here."""

    def __init__(self, spacing=48, count=7, displacement=8, field_index=3):
        self.symbols, self.words = {}, {}
        self.ends = {}
        self.emplace = "__ZN4core8hash_map_Authored_DiscoveredTargetInfo7emplace"
        check = "__ZN20BuildTargetDiscovery14CheckRenderersEPNS_20DiscoveredTargetInfoE"
        module = "__ZN20BuildTargetDiscovery19HandleEditorModulesERKNS_20DiscoveredTargetInfoE"
        reset = "__ZN20BuildTargetDiscovery20DiscoveredTargetInfo5ResetEv"
        names = (r.RECORD, r.ASSIGN, r.PAIR, self.emplace, r.INSERT, r.CONSUMER, check, module, r.LOWER, reset, "authored_cleanup")
        for index, name in enumerate(names):
            self.symbols[name] = {BASE + index * 0x1000}
        functions = {
            r.RECORD: copies(spacing, count),
            r.PAIR: pair(spacing),
            self.emplace: node(displacement),
            r.CONSUMER: consumer(displacement + spacing + field_index * spacing),
        }
        targets = {ASSIGN: self.symbol(r.ASSIGN), RECORD: self.symbol(r.RECORD), PAIR: self.symbol(r.PAIR)}
        for name, original in functions.items():
            base = self.symbol(name)
            for pc, word in original.items():
                target = r.f.call_target(original, pc)
                self.words[base + pc - BASE] = call(base + pc - BASE, targets[target]) if target is not None else word
            self.ends[name] = base + len(original) * 4
        base = self.symbol(r.INSERT)
        values = [move(19, 1), move(20, 0), move(0, 19)]
        values += [call(base + len(values) * 4, self.symbol(check)), load(8, 19, 512, 1), 0x37000000 | 4 << 5 | 8, move(0, 20), move(1, 19)]
        values += [call(base + len(values) * 4, self.symbol(module)), load(0, 19, 352, 8), add(8, 31, 24)]
        values += [call(base + len(values) * 4, self.symbol(r.LOWER)), move(0, 20), move(2, 19)]
        values += [call(base + len(values) * 4, self.symbol(self.emplace))]
        values += [call(base + len(values) * 4, self.symbol("authored_cleanup")), move(0, 19)]
        values += [call(base + len(values) * 4, self.symbol(reset)), 0xD65F03C0]
        self.words.update(words(values, base))
        self.ends[r.INSERT] = base + len(values) * 4
        for name in names:
            if name not in self.ends:
                self.words[self.symbol(name)] = 0xD65F03C0
                self.ends[name] = self.symbol(name) + 4
        for name, end in self.ends.items():
            self.symbols[name + "_authored_end"] = {end}

    def symbol(self, name):
        return next(iter(self.symbols[name]))

    def at(self, address, size):
        return b"".join(struct.pack("<I", self.words[pc]) for pc in range(address, address + size, 4))


class JoinedTests(unittest.TestCase):
    def test_join_derives_field_alignment_without_any_live_gate(self):
        for arguments, field in (({}, 144), ({"spacing": 40, "count": 3, "displacement": 16, "field_index": 1}, 40)):
            result = r.derive(Image(**arguments))
            self.assertEqual(result["consumer_record_string_offset"], field)
            self.assertTrue(result["field_operand_alignment_qualified"])
            self.assertTrue(result["conditional_module_handler_precedes_insertion"])
            self.assertTrue(result["record_reset_follows_insertion"])
            self.assertTrue(all(not value for key, value in result.items() if key.endswith("_qualified") and key != "field_operand_alignment_qualified"))

    def test_unjoined_consumer_and_insertion_mutations_refuse(self):
        for symbol, index, replacement in (
            (r.CONSUMER, 0, add(19, 0, 208)),
            (r.INSERT, 5, 0x36000000 | 4 << 5 | 8),
            (r.INSERT, 7, move(1, 20)),
            (r.INSERT, 13, move(2, 20)),
            (r.INSERT, 16, move(0, 20)),
        ):
            with self.subTest(symbol=symbol, index=index), self.assertRaises(ValueError):
                image = Image()
                image.words[image.symbol(symbol) + index * 4] = replacement
                r.derive(image)

    def test_private_report_guards_refuse_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, output = Path(tmp) / "sdk", Path(tmp) / "report"
            binary.write_bytes(b"authored unknown SDK")
            with self.assertRaisesRegex(ValueError, "Unknown owner SDK"):
                r.inspect(binary, output)
            self.assertFalse(output.exists())
            output.write_text("existing")
            with self.assertRaises(FileExistsError):
                r.inspect(binary, output)
            self.assertEqual(output.read_text(), "existing")

    def test_optional_exact_sdk_static_links(self):
        binary = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity")
        if not binary.is_file():
            self.skipTest("Pinned owner SDK is absent")
        with tempfile.TemporaryDirectory() as tmp:
            result = r.inspect(binary, Path(tmp) / "private.json")
        self.assertEqual(result["consumer_record_string_offset"], 144)
        self.assertFalse(result["executes_sdk"])
        self.assertFalse(result["root_generation_qualified"])


if __name__ == "__main__":
    unittest.main()
