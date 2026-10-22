"""Authored operand/interval/payload fixtures; no captured SDK table or code."""

import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("target_keys_test", ROOT / "scripts/lab/phone_target_keys.py")
keys = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(keys)
ctor, geometry = keys.ctor, keys.geometry_module
START, OBJECT, NODE, PAIR = 0x10000, 0x30000, 0x40000, 0x50000


def move(destination, source):
    return 0xAA0003E0 | source << 16 | destination


def add(destination, source, value):
    return 0x91000000 | value << 10 | source << 5 | destination


def constant(register, value):
    return 0x52800000 | value << 5 | register


def store(register, base, offset, width):
    size = {1: 0, 2: 1, 4: 2, 8: 3}[width]
    return 0x39000000 | size << 30 | (offset // width) << 10 | base << 5 | register


def load(register, base, offset, width):
    return store(register, base, offset, width) | 0x400000


def call(pc, target):
    return 0x94000000 | (((target - pc) // 4) & 0x3FFFFFF)


def branch(pc, target, condition=None):
    displacement = (target - pc) // 4
    if condition is None:
        return 0x14000000 | (displacement & 0x3FFFFFF)
    return 0x54000000 | ((displacement & 0x7FFFF) << 5) | condition


def address(register, pc, value):
    pages = ((value & ~4095) - (pc & ~4095)) // 4096 & 0x1FFFFF
    return [0x90000000 | (pages & 3) << 29 | (pages >> 2) << 5 | register, add(register, register, value & 4095)]


class Image:
    """Only the public fixture's instructions and symbol identities exist."""

    def __init__(self, words):
        self.words = words
        self.symbols = {
            geometry.FUNCTION: {min(words)},
            geometry.OBJECT: {OBJECT},
            "authored_end": {max(words) + 4},
            "authored__treeINS_12__value_typeI19BuildTargetPlatformN4core12basic_string16__construct_nodeIJRKNS_4pair": {NODE},
            "__ZNSt3__14pairIK19BuildTargetPlatformN4core12basic_stringIcNS3_20StringStorageDefaultIcEEEEEC1IS1_RA4_KcLb0EEEOT_OT0_": {PAIR},
        }

    def symbol(self, name):
        values = self.symbols[name]
        if len(values) != 1:
            raise ValueError("Ambiguous authored symbol")
        return next(iter(values))

    def at(self, at, size):
        if size % 4:
            raise ValueError("No authored byte table")
        try:
            return b"".join(struct.pack("<I", self.words[pc]) for pc in range(at, at + size, 4))
        except KeyError as error:
            raise ValueError("No fixture bytes outside its instructions") from error


def interval(count=2):
    values = [0xD10003FF | 256 << 10, add(20, 31, 32)]
    setup = START + len(values) * 4
    values += address(19, setup, OBJECT)
    values += [move(8, 19), 0xF8000C00 | 8 << 12 | 8 << 5 | 31, store(31, 19, 16, 8), store(8, 19, 0, 8), add(21, 20, count * 56)]
    values += address(22, START + len(values) * 4, OBJECT + 8)
    loop = START + len(values) * 4
    values += [0xD503201F, add(8, 31, 8), move(0, 19), move(1, 20)]
    node = START + len(values) * 4
    values += [call(node, NODE), add(20, 20, 56), 0xEB00001F | 21 << 16 | 20 << 5]
    jump = START + len(values) * 4
    values += [branch(jump, jump + 8, 0), branch(jump + 4, loop), 0xD65F03C0]
    return Image({START + index * 4: value for index, value in enumerate(values)}), dict(setup=setup, node=node, step=node + 4, loop=loop)


def inline_payload():
    record = 32
    values = [constant(11, 24), store(11, 31, record + 32, 1), add(0, 31, record + 8), constant(1, 3)]
    grow = START + len(values) * 4
    values += [call(grow, NODE), constant(9, 0x6261), store(9, 0, 0, 2), constant(9, 0x63), store(9, 0, 2, 1), store(31, 0, 3, 1)]
    tag = START + len(values) * 4
    values += [load(9, 31, record + 40, 1), 0x7100001F | 9 << 5 | 1 << 10, 0]
    values += [constant(10, 21), store(10, 31, record + 32, 1), 0, constant(10, 3), store(10, 31, record + 24, 8), 0xD65F03C0]
    values[(tag - START) // 4 + 2] = branch(tag + 8, tag + 24, 1)
    values[(tag - START) // 4 + 5] = branch(tag + 20, tag + 32)
    words = {START + index * 4: value for index, value in enumerate(values)}
    return words, grow, record, tag, max(words)


class OperandTests(unittest.TestCase):
    def test_saved_parameter_survives_call_and_offset_aliases(self):
        words = {
            START: move(19, 0),
            START + 4: move(20, 2),
            START + 8: call(START + 8, NODE),
            START + 12: add(21, 19, 8),
            START + 16: move(0, 21),
            START + 20: 0xD65F03C0,
        }
        origin = ctor.Origins(words)
        self.assertEqual(origin.at(START + 20, 0), ("add", ("parameter", 0), 8))
        self.assertEqual(origin.at(START + 20, 20), ("parameter", 2))
        self.assertEqual(origin.at(START + 20, 2), ("return", NODE, START + 8, 2))

    def test_skipped_or_unknown_definition_refuses(self):
        words = {START: branch(START, START + 8, 0), START + 4: move(19, 0), START + 8: move(0, 19), START + 12: 0xD65F03C0}
        with self.assertRaisesRegex(ValueError, "skipped"):
            ctor.Origins(words).at(START + 12, 0)
        words = {START: move(19, 0), START + 4: 0xFFFFFFFF, START + 8: 0xD65F03C0}
        with self.assertRaisesRegex(ValueError, "Unknown"):
            ctor.Origins(words).at(START + 8, 19)

    def test_preindexed_store_updates_base_without_replacing_its_value(self):
        words = {START: move(19, 0), START + 4: move(21, 19), START + 8: 0xF8000C00 | 24 << 12 | 21 << 5, START + 12: 0xD65F03C0}
        self.assertEqual(ctor.Origins(words).at(START + 12, 21), ("add", ("parameter", 0), 24))

    def test_zero_register_and_invalid_scalar_widths_refuse(self):
        self.assertEqual(keys.scalar_immediate(constant(9, 17)), 17)
        for word in (constant(31, 17), constant(9, 17) | 0x80000000, constant(9, 17) | 2 << 21):
            with self.subTest(word=word), self.assertRaises(ValueError):
                keys.scalar_immediate(word)


class GeometryTests(unittest.TestCase):
    def derive(self, image):
        # The interval component consumes the separately tested record contract.
        with mock.patch.object(geometry.ctor, "prove", return_value={"record_write_extent": 56}):
            return geometry.derive(image)

    def test_interval_count_comes_from_operands(self):
        for count in (2, 3, 4):
            with self.subTest(count=count):
                result = self.derive(interval(count)[0])
                self.assertEqual((result["list_base"], result["list_span"], result["list_stride"], result["list_count"]), (32, count * 56, 56, count))
                self.assertFalse(result["tree_population_qualified"])

    def test_invalid_span_stride_receiver_and_loop_effect_refuse(self):
        original, positions = interval()
        setup, node, step = (positions[key] for key in ("setup", "node", "step"))
        mutations = [
            (setup - 4, add(20, 1, 32)),
            (setup + 24, add(21, 20, 0)),
            (setup + 24, add(21, 20, 113)),
            (setup + 24, add(21, 20, 280)),
            (node - 4, move(1, 19)),
            (step, add(20, 20, 28)),
            (step + 8, original.words[step + 8] ^ 1),
            (positions["loop"], 0xFFFFFFFF),
        ]
        for pc, word in mutations:
            with self.subTest(pc=pc, word=word):
                image = Image(dict(original.words))
                image.words[pc] = word
                with self.assertRaises(ValueError):
                    self.derive(image)


class PayloadTests(unittest.TestCase):
    def run_payload(self, words, grow, record, setup):
        return keys.payload(None, words, ctor.Origins(words), grow, record, setup)

    def test_immediate_fragments_have_complete_byte_and_null_coverage(self):
        words, grow, record, _, setup = inline_payload()
        self.assertEqual(self.run_payload(words, grow, record, setup), ("abc", setup))

    def test_buffer_clobber_missing_null_and_reversed_mode_refuse(self):
        original, grow, record, tag, setup = inline_payload()
        for pc, word in ((grow + 4, 0xD2800000), (grow + 20, 0xD503201F), (tag + 8, original[tag + 8] ^ 1), (tag + 24, constant(10, 2))):
            with self.subTest(pc=pc):
                words = dict(original)
                words[pc] = word
                with self.assertRaises(ValueError):
                    self.run_payload(words, grow, record, setup)


class CliTests(unittest.TestCase):
    def test_unknown_sdk_refuses_including_optimized_isolated_cli_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk, output = root / "authored-unknown", root / "report.json"
            sdk.write_bytes(b"Authored SDK refusal control")
            for flags in ([], ["-O"]):
                run = subprocess.run(
                    [sys.executable, *flags, "-I", "-S", str(ROOT / "scripts/lab/phone_target_keys.py"), str(sdk), str(output)], capture_output=True, text=True
                )
                self.assertNotEqual(run.returncode, 0)
                self.assertIn("Unknown owner SDK", run.stderr)
                self.assertFalse(output.exists())
            output.write_bytes(b"keep authored output")
            with self.assertRaises(FileExistsError):
                keys.inspect(sdk, output)
            self.assertEqual(output.read_bytes(), b"keep authored output")

    def test_optional_exact_sdk_has_only_input_bindings(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity")
        if not sdk.is_file():
            self.skipTest("Exact owner SDK is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            result = keys.inspect(sdk, output)
            self.assertEqual(len(result["rows"]), 34)
            self.assertEqual(len({row["key"] for row in result["rows"]}), 34)
            self.assertTrue(result["source_argument_slots_complete"])
            self.assertEqual(len(result["sources"]), len(set(keys.SOURCES)))
            for key in (
                "constructor_result_qualified",
                "tree_population_qualified",
                "target_support_qualified",
                "target_discovery_qualified",
                "module_inclusion_qualified",
                "native_usage_qualified",
                "root_generation_qualified",
                "executes_sdk",
                "game_inputs",
            ):
                self.assertIs(result[key], False)
            self.assertEqual(json.loads(output.read_text()), result)
