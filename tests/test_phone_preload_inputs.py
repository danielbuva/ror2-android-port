"""Authored CFG, register-space and copy fixtures; no captured SDK code/table."""

import importlib.util
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("preload_inputs_test", ROOT / "scripts/lab/phone_preload_inputs.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
BASE, STRINGS, GROW, INSERT = 0x10000, 0x20000, 0x30000, 0x31000


def move(destination, source):
    return 0xAA0003E0 | source << 16 | destination


def add(destination, source, value):
    return 0x91000000 | value << 10 | source << 5 | destination


def constant(register, value):
    return 0x52800000 | value << 5 | register


def call(pc, target):
    return 0x94000000 | (((target - pc) // 4) & 0x3FFFFFF)


def branch(pc, target, condition=None):
    offset = (target - pc) // 4
    return 0x14000000 | (offset & 0x3FFFFFF) if condition is None else 0x54000000 | (offset & 0x7FFFF) << 5 | condition


def address(register, pc, target):
    pages = ((target & ~4095) - (pc & ~4095)) // 4096 & 0x1FFFFF
    return [0x90000000 | (pages & 3) << 29 | (pages >> 2) << 5 | register, add(register, register, target & 4095)]


def memory(register, base, offset, width, *, vector=False, reading=False, unscaled=False):
    if unscaled:
        code = 0x3C800000 if vector else 0xF8000000
        return code | (0x400000 if reading else 0) | (offset & 511) << 12 | base << 5 | register
    code = ({4: 0xBD000000, 8: 0xFD000000, 16: 0x3D800000} if vector else {1: 0x39000000, 4: 0xB9000000, 8: 0xF9000000})[width]
    return code | (0x400000 if reading else 0) | (offset // width) << 10 | base << 5 | register


def wordmap(values):
    return {BASE + index * 4: value for index, value in enumerate(values)}


class Image:
    """Authored symbols/code and one file-backed literal section only."""

    def __init__(self, words, value):
        self.words = words
        self.symbols = {p.FUNCTION: {min(words)}, p.GROW: {GROW}, p.records.INSERT: {INSERT}, "authored_end": {max(words) + 4}}
        self.symbol_addresses = sorted(v for values in self.symbols.values() for v in values)
        self.sections = [(min(words), len(words) * 4, 0)]
        self.data = bytearray(4096)
        struct.pack_into("<I", self.data, 16, 1)
        struct.pack_into("<II", self.data, 32, 0x19, 152)
        struct.pack_into("<I", self.data, 96, 1)
        at = 104
        struct.pack_into("<QQI", self.data, at + 32, STRINGS, 256, 1024)
        struct.pack_into("<I", self.data, at + 64, 2)
        self.data[1024 : 1024 + len(value) + 1] = value.encode() + b"\0"

    def symbol(self, name):
        return next(iter(self.symbols[name]))

    def take(self, at, size):
        if not 0 <= at <= len(self.data) - size:
            raise ValueError("Authored file range exceeded")
        return self.data[at : at + size]

    def at(self, at, size):
        if STRINGS <= at <= STRINGS + 256 - size:
            return self.take(1024 + at - STRINGS, size)
        return b"".join(struct.pack("<I", self.words[pc]) for pc in range(at, at + size, 4))


def assignment(length=16, *, reuse=True, spills=False):
    value = "PLATFORM_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: length - 9]
    values = [0xD10003FF | 512 << 10, add(21, 31, 64)]
    values += address(19, BASE + len(values) * 4, STRINGS)
    if spills:
        values += [memory(0, 19, 0, 16, vector=True, reading=True), memory(0, 31, 16, 16, vector=True)]
        values += [memory(8, 19, length - 8, 8, reading=True, unscaled=True), memory(8, 31, 8, 8)]
    checks = []
    if reuse:
        checks = [len(values), len(values) + 1]
        values += [0, 0]
    values += [move(0, 21), constant(1, length)]
    grow = BASE + len(values) * 4
    values += [call(grow, GROW)]
    start = BASE + len(values) * 4
    if length == 12:
        suffix = int.from_bytes(value.encode()[8:], "little")
        values += [constant(8, suffix & 65535), 0x72800000 | (suffix >> 16) << 5 | 1 << 21 | 8, memory(8, 0, 8, 4)]
        values += [memory(8, 19, 0, 8, reading=True), memory(8, 0, 0, 8)]
    elif spills:
        values += [memory(8, 31, 8, 8, reading=True), memory(8, 0, length - 8, 8, unscaled=True)]
        values += [memory(0, 31, 16, 16, vector=True, reading=True), memory(0, 0, 0, 16, vector=True)]
    else:
        values += [memory(0, 19, 0, 16, vector=True, reading=True)]
        if length > 16:
            width = 16 if length > 24 else 8
            source = 1 if width == 16 else 8
            values += [
                memory(source, 19, length - width, width, vector=width == 16, reading=True, unscaled=True),
                memory(source, 0, length - width, width, vector=width == 16, unscaled=True),
            ]
        values += [memory(0, 0, 0, 16, vector=True)]
    terminator = BASE + len(values) * 4
    values += [memory(31, 0, length, 1), memory(8, 31, 96, 1, reading=True), 0x7100041F | 8 << 5]
    conditional = len(values)
    values += [0]
    if length in (23, 24):
        values += [memory(8 if length == 23 else 31, 31, 88, 1)]
    else:
        values += [constant(8, (24 - length) & 255), memory(8, 31, 88, 1)]
    jump = len(values)
    values += [0]
    heap = BASE + len(values) * 4
    values += [constant(8, length), memory(8, 31, 80, 8)]
    join = BASE + len(values) * 4
    values[conditional] = branch(BASE + conditional * 4, heap, 1)
    values[jump] = branch(BASE + jump * 4, join)
    values += [add(1, 31, 32)]
    insertion = BASE + len(values) * 4
    values += [call(insertion, INSERT), 0xD65F03C0]
    if reuse:
        heap_path = BASE + len(values) * 4
        values += [memory(0, 31, 64, 8, reading=True)]
        values += [branch(BASE + len(values) * 4, start)]
        inline_path = BASE + len(values) * 4
        values += [move(0, 21), branch(BASE + (len(values) + 1) * 4, start)]
        values[checks[0]] = branch(BASE + checks[0] * 4, heap_path, 0)
        values[checks[1]] = branch(BASE + checks[1] * 4, inline_path, 1)
    return Image(wordmap(values), value), dict(grow=grow, start=start, terminator=terminator, join=join, insertion=insertion, mode=terminator + 4)


class FlowTests(unittest.TestCase):
    def test_stack_alias_and_all_buffer_predecessors_include_out_of_line_paths(self):
        image, at = assignment()
        flow = p.flow_module.Flow(image.words)
        self.assertEqual(flow.stack(at["grow"], 0)[1:], (64, 512))
        field, producers = flow.buffer(at["terminator"], 0, GROW)
        self.assertEqual(field[1:], (64, 512))
        self.assertEqual(set(producers), {"grow-return", "existing-field-storage", "inline-field-address"})

    def test_unknown_effect_unreachable_origin_zero_and_midway_clobber_refuse(self):
        for index, word in ((1, move(21, 31)), (1, 0xFFFFFFFF), (1, memory(21, 31, 64, 8, reading=True))):
            image, at = assignment()
            image.words[BASE + index * 4] = word
            with self.subTest(index=index, word=word), self.assertRaises(ValueError):
                p.flow_module.Flow(image.words).stack(at["grow"], 0)
        image, _ = assignment(reuse=False)
        image.words[max(image.words)] = 0xD65F03C0
        image.words[max(image.words) + 4] = add(21, 31, 64)
        with self.assertRaisesRegex(ValueError, "Unreachable"):
            p.flow_module.Flow(image.words).stack(max(image.words), 21)

    def test_vector_namespace_does_not_write_same_numbered_gpr(self):
        for code in (memory(21, 19, 0, 16, vector=True, reading=True), memory(21, 31, 0, 8, vector=True), 0x0F000400 | 21):
            self.assertEqual(p.flow_module.effects(code), set())
        self.assertIn(21, p.flow_module.effects(memory(21, 19, 0, 8, reading=True)))

    def test_branch_escapes_and_two_insertion_paths_refuse(self):
        image, at = assignment()
        image.words[at["join"]] = branch(at["join"], max(image.words) + 4)
        with self.assertRaisesRegex(ValueError, "escapes"):
            p.flow_module.Flow(image.words)
        words = wordmap([branch(BASE, BASE + 12, 0), call(BASE + 4, INSERT), 0xD65F03C0, call(BASE + 12, INSERT), 0xD65F03C0])
        with self.assertRaises(ValueError):
            p.flow_module.Flow(words).next_insertion(BASE, INSERT)

    def test_backedge_and_call_clobbers_cannot_supply_a_unique_stack_alias(self):
        values = [
            0xD10003FF | 512 << 10,
            add(21, 31, 64),
            branch(BASE + 8, BASE + 16, 0),
            add(21, 31, 80),
            move(0, 21),
            branch(BASE + 20, BASE + 8, 1),
            0xD65F03C0,
        ]
        with self.assertRaises(ValueError):
            p.flow_module.Flow(wordmap(values)).stack(BASE + 24, 0)
        values = [0xD10003FF | 512 << 10, add(0, 31, 64), call(BASE + 8, GROW), 0xD65F03C0]
        with self.assertRaises(ValueError):
            p.flow_module.Flow(wordmap(values)).stack(BASE + 12, 0)

    def test_authored_llvm_encoding_has_expected_gpr_effects_when_available(self):
        if shutil.which("xcrun") is None:
            self.skipTest("Host Apple LLVM assembler unavailable")
        source = ".text\nsub sp, sp, #512\nadd x21, sp, #64\nadds x22, x19, #1\ncmn w8, #2\nmadd x28, x27, x8, x19\nstr w9, [x8, x19, lsl #2]\nmovi v0.2s, #2\nldr q21, [x19]\nstr d21, [sp, #8]\norr w8, w27, #8\nret\n"
        with tempfile.TemporaryDirectory() as directory:
            assembly, obj = Path(directory) / "authored.s", Path(directory) / "authored.o"
            assembly.write_text(source)
            compile_result = subprocess.run(
                ["xcrun", "clang", "-target", "arm64-apple-macos11", "-c", str(assembly), "-o", str(obj)], capture_output=True, text=True, timeout=20
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(["xcrun", "llvm-objdump", "--macho", "--disassemble", str(obj)], capture_output=True, text=True, check=True, timeout=20)
        encoded = []
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) > 2:
                raw = parts[1].split()
                if len(raw) == 4 and all(len(byte) == 2 for byte in raw):
                    encoded.append(int.from_bytes(bytes.fromhex(" ".join(raw)), "little"))
        self.assertEqual(len(encoded), 11)
        self.assertEqual([p.flow_module.effects(word) for word in encoded], [{31}, {21}, {22}, set(), {28}, set(), set(), set(), set(), {8}, set()])


class PayloadTests(unittest.TestCase):
    def test_scalar_vector_overlap_and_compressed_lengths(self):
        for length in (12, 16, 23, 24, 26):
            with self.subTest(length=length):
                image, at = assignment(length)
                flow = p.flow_module.Flow(image.words)
                value, join, paths, spills = p.payload(image, flow, at["grow"], GROW, flow.stack(at["grow"], 0))
                self.assertEqual(value, "PLATFORM_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: length - 9])
                self.assertEqual(join, at["join"])
                self.assertEqual(len(paths), 3)
                self.assertEqual(spills, 0)

    def test_direct_spill_sources_are_linked_without_memory_semantics_claim(self):
        image, at = assignment(23, spills=True)
        flow = p.flow_module.Flow(image.words)
        value, _, _, count = p.payload(image, flow, at["grow"], GROW, flow.stack(at["grow"], 0))
        self.assertTrue(value.startswith("PLATFORM_"))
        self.assertEqual(count, 2)
        with mock.patch.object(p.records, "derive", return_value={"consumer_record_string_offset": 32}):
            result = p.derive(image)
        self.assertTrue(result["every_insertion_has_platform_operand_binding"])
        for flag in (
            "all_record_inputs_complete",
            "call_memory_effects_qualified",
            "indirect_store_aliasing_qualified",
            "record_values_qualified",
            "target_support_qualified",
            "root_generation_qualified",
        ):
            self.assertFalse(result[flag])

    def test_fragment_terminator_predicate_and_alias_mutations_refuse(self):
        for kind in ("terminator", "mode", "branch", "mid-copy-entry", "heap-field"):
            image, at = assignment()
            if kind == "terminator":
                image.words[at["terminator"]] = memory(31, 0, 15, 1)
            elif kind == "mode":
                image.words[at["mode"]] = memory(8, 31, 97, 1, reading=True)
            elif kind == "branch":
                image.words[at["mode"] + 8] ^= 1
            elif kind == "mid-copy-entry":
                image.words[max(image.words)] = branch(max(image.words), at["start"] + 4)
            else:
                image.words[max(image.words) - 12] = memory(0, 31, 72, 8, reading=True)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                flow = p.flow_module.Flow(image.words)
                p.payload(image, flow, at["grow"], GROW, flow.stack(at["grow"], 0))

    def test_partial_direct_spill_overwrite_refuses(self):
        image, at = assignment(23, spills=True)
        # Replace the earlier scalar spill with a partial write into the vector home.
        image.words[BASE + 7 * 4] = memory(8, 31, 17, 1)
        with self.assertRaises(ValueError):
            flow = p.flow_module.Flow(image.words)
            p.payload(image, flow, at["grow"], GROW, flow.stack(at["grow"], 0))


class ReportTests(unittest.TestCase):
    def test_unknown_sdk_and_existing_output_refuse_without_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            binary, report = Path(directory) / "sdk", Path(directory) / "report"
            binary.write_bytes(b"authored unknown SDK")
            with self.assertRaises(ValueError):
                p.inspect(binary, report)
            self.assertFalse(report.exists())
            report.write_text("preserved")
            with self.assertRaises(FileExistsError):
                p.inspect(binary, report)
            self.assertEqual(report.read_text(), "preserved")

    def test_optimized_isolated_cli_refuses_unknown_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "sdk"
            binary.write_bytes(b"authored unknown SDK")
            for mode in ("-O", "-OO"):
                report = Path(directory) / (mode + ".json")
                result = subprocess.run(
                    [sys.executable, "-I", "-S", mode, str(ROOT / "scripts/lab/phone_preload_inputs.py"), str(binary), str(report)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Unknown owner SDK", result.stderr)
                self.assertFalse(report.exists())

    def test_optional_exact_sdk_declared_assignment_coverage(self):
        binary = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity")
        if not binary.is_file():
            self.skipTest("Pinned owner SDK absent")
        with tempfile.TemporaryDirectory() as directory:
            result = p.inspect(binary, Path(directory) / "private.json")
        self.assertEqual(len(result["rows"]), result["insertion_calls"])
        self.assertTrue(result["every_insertion_has_platform_operand_binding"])
        self.assertFalse(result["all_grow_receivers_classified"])
        self.assertGreater(len(result["unresolved_grow_calls"]), 0)
        self.assertFalse(result["record_values_qualified"])
        self.assertFalse(result["executes_sdk"])


if __name__ == "__main__":
    unittest.main()
