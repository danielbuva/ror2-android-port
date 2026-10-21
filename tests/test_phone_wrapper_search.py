"""Authored A64/data fixtures; no owner SDK instructions or tables are copied."""

from pathlib import Path
import struct
import tempfile
import unittest

from phone_wrapper_search import SearchReader, inspect


def mov(destination, source):
    return 0xAA0003E0 | source << 16 | destination


def stack_address(destination, offset):
    return 0x910003E0 | offset << 10 | destination


def load(destination, base, offset, width=8):
    return {1: 0x39400000, 4: 0xB9400000, 8: 0xF9400000}[width] | (offset // width) << 10 | base << 5 | destination


def pair(first, second, offset, *, reading=False):
    return (0xA9400000 if reading else 0xA9000000) | (offset // 8) << 15 | second << 10 | 31 << 5 | first


class AuthoredSearch:
    start = 0x1000
    formatter, lookup = 0x5000, 0x6000

    def __init__(self, *, zero_inline=False, zero_sret=False):
        self.words, self.labels, self.branches = [], {}, []
        self.memory = {}
        self.zero_inline = zero_inline
        self.emit(0xD10003FF | 160 << 10)  # One fixed frame, deliberately different registers/layout.
        self.emit(pair(24, 25, 96))
        self.emit(pair(21, 22, 112))
        self.mark("name")
        self.emit(mov(25, 0))
        self.mark("module")
        self.emit(0xF90003E1)  # Darwin variadic argument slot: original parameter 1.
        self.mark("sret")
        if zero_sret:
            self.emit(mov(8, 31))
            self.emit(0x91000000 | 32 << 10 | 8 << 5 | 8)
        else:
            self.emit(stack_address(8, 32))
        self.address(0, 0x9100)
        self.call(self.formatter)
        self.format_pointer("first")
        self.search(0x8000, "first")
        self.guard("first")
        self.address(21, 0x8000)  # Preserved page reused across separate lookup/guard blocks.
        self.emit(load(0, 21, 32))
        self.search(0x8008, "middle")
        self.guard("middle")
        self.mark("retained")
        self.emit(load(0, 21, 32))
        self.search(0x8010, "duplicate")
        self.guard("duplicate")
        self.format_pointer("last")
        self.search(0x8018, "last")
        self.mark("exit")
        self.emit(0xD503201F)
        self.mark("return_value")
        self.emit(mov(0, 24))
        self.emit(pair(24, 25, 96, reading=True))  # Restoration follows the actual operand use.
        self.emit(pair(21, 22, 112, reading=True))
        self.emit(stack_address(31, 160))
        self.emit(0xD65F03C0)
        for index in self.branches:
            self.words[index] = self.branch(self.start + index * 4, self.pc("exit"))
        self.symbols = {
            "authored_search": {self.start},
            "end": {self.start + len(self.words) * 4},
            "authored_format": {self.formatter},
            "authored_lookup": {self.lookup},
        }
        for slot, pointer, value in [
            (0x8000, 0x9200, "Fixture.First"),
            (0x8008, 0x9240, "Fixture.Shared"),
            (0x8010, 0x9280, "Fixture.Shared"),
            (0x8018, 0x92C0, "Fixture.Last"),
            (0x8020, 0x9300, "Authored.Editor.dll"),
        ]:
            self.put(slot, struct.pack("<Q", pointer))
            self.put(pointer, value.encode() + b"\0")
        self.put(0x9100, b"Tool.%sFacet.dll\0")

    def emit(self, word):
        self.words.append(word)

    def mark(self, name):
        self.labels[name] = len(self.words)

    def pc(self, name):
        return self.start + self.labels[name] * 4

    def address(self, register, address):
        pc = self.start + len(self.words) * 4
        pages = ((address & ~4095) - (pc & ~4095)) // 4096
        self.emit(0x90000000 | (pages & 3) << 29 | ((pages >> 2) & 0x7FFFF) << 5 | register)
        if address & 4095:
            self.emit(0x91000000 | (address & 4095) << 10 | register << 5 | register)

    def call(self, target):
        pc = self.start + len(self.words) * 4
        self.emit(0x94000000 | ((target - pc) // 4) & 0x3FFFFFF)

    def format_pointer(self, label):
        if self.zero_inline and label == "first":
            self.emit(mov(12, 31))
        self.mark(label + "_tag")
        self.emit(load(10, 31, 56, 1))
        self.emit(load(9, 31, 32))
        self.mark(label + "_compare")
        self.emit(0x7100001F | 3 << 10 | 10 << 5)
        self.emit((0x91000000 | 32 << 10 | 12 << 5 | 12) if self.zero_inline and label == "first" else stack_address(12, 32))
        self.mark(label + "_selector")
        self.emit(0x9A800000 | 9 << 16 | 12 << 5)  # EQ, inline vs heap of the same result object.

    def search(self, slot, label):
        self.address(8, slot & ~4095)
        self.mark(label + "_namespace")
        self.emit(load(1, 8, slot & 4095))
        self.emit(mov(2, 25))
        self.mark(label + "_call")
        self.call(self.lookup)
        self.emit(mov(24, 0))

    @staticmethod
    def branch(pc, target):
        return 0xB5000000 | (((target - pc) // 4) & 0x7FFFF) << 5

    def guard(self, label):
        self.mark(label + "_guard")
        self.branches.append(len(self.words))
        self.emit(0)

    def put(self, address, data):
        self.memory.update({address + index: value for index, value in enumerate(data)})

    def at(self, address, size):
        code = struct.pack("<" + "I" * len(self.words), *self.words)
        if self.start <= address and address + size <= self.start + len(code):
            return code[address - self.start : address - self.start + size]
        try:
            return bytes(self.memory[address + index] for index in range(size))
        except KeyError as error:
            raise ValueError("Outside authored file-backed data") from error

    def symbol(self, name):
        return next(iter(self.symbols[name]))

    def read(self):
        return SearchReader(self, "authored_search", "authored_format", "authored_lookup").decode()


class WrapperSearchTests(unittest.TestCase):
    def test_zero_register_arithmetic_cannot_forge_stack_buffer_origins(self):
        for kwargs in [{"zero_inline": True}, {"zero_sret": True}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AuthoredSearch(**kwargs).read()

    def test_ordered_scopes_duplicates_and_module_format_come_from_supplied_data(self):
        image = AuthoredSearch()
        report = image.read()
        self.assertTrue(report["normal_path_qualified"])
        rows = report["lookup_sequence"]
        self.assertEqual([row["namespace"] for row in rows], ["Fixture.First", "Fixture.Shared", "Fixture.Shared", "Fixture.Last"])
        self.assertEqual(rows[0]["assembly"], {"kind": "module-format", "template": "Tool.%sFacet.dll"})
        self.assertEqual(rows[1]["assembly"]["name"], "Authored.Editor.dll")
        self.assertEqual(rows[2]["assembly"], rows[1]["assembly"])
        self.assertNotEqual(rows[1]["namespace_slot"], rows[2]["namespace_slot"])
        image.put(0x9300, b"Authored.Other.dll\0")
        self.assertEqual(image.read()["lookup_sequence"][1]["assembly"]["name"], "Authored.Other.dll")

    def test_wrong_entry_arguments_and_partial_variadic_writes_refuse(self):
        for label, word in [("name", mov(25, 1)), ("module", 0xB90003E1), ("module", 0xF90007E1), ("sret", stack_address(8, 40))]:
            image = AuthoredSearch()
            image.words[image.labels[label]] = word
            with self.subTest(label=label, word=word), self.assertRaises(ValueError):
                image.read()

    def test_runtime_pointer_and_truncated_pointer_loads_never_supply_namespaces(self):
        for word in [load(1, 17, 0), load(1, 8, 0, 4)]:
            image = AuthoredSearch()
            image.words[image.labels["first_namespace"]] = word
            with self.subTest(word=word), self.assertRaises(ValueError):
                image.read()
        image = AuthoredSearch()
        image.put(0x8000, struct.pack("<Q", 0xF000))
        with self.assertRaises(ValueError):
            image.read()

    def test_selector_flags_object_identity_and_format_are_not_guessed(self):
        for label, word in [
            ("first_selector", 0x9A801000 | 9 << 16 | 12 << 5),  # NE unsupported.
            ("first_tag", load(10, 31, 168, 1)),
            ("first_compare", 0x7100001F | 3 << 10 | 11 << 5),
        ]:
            image = AuthoredSearch()
            image.words[image.labels[label]] = word
            with self.subTest(label=label), self.assertRaises(ValueError):
                image.read()
        image = AuthoredSearch()
        image.put(0x9100, b"Tool.%dFacet.dll\0")
        with self.assertRaisesRegex(ValueError, "format"):
            image.read()

    def test_short_circuit_branch_width_polarity_destination_and_unknown_flow_refuse(self):
        for mutation in [lambda word: word ^ 0x80000000, lambda word: word ^ 0x01000000, lambda word: word + 1, lambda word: 0xD503201F]:
            image = AuthoredSearch()
            index = image.labels["first_guard"]
            image.words[index] = mutation(image.words[index])
            with self.subTest(word=image.words[index]), self.assertRaises(ValueError):
                image.read()
        image = AuthoredSearch()
        image.words[image.labels["exit"]] = image.branch(image.pc("exit"), image.pc("first_call"))
        with self.assertRaisesRegex(ValueError, "Backward"):
            image.read()

    def test_result_restore_timing_and_retained_global_origin_are_proven(self):
        for label, word in [("exit", mov(24, 31)), ("exit", pair(24, 25, 96, reading=True)), ("return_value", mov(0, 25)), ("retained", mov(21, 0))]:
            image = AuthoredSearch()
            image.words[image.labels[label]] = word
            with self.subTest(label=label), self.assertRaises(ValueError):
                image.read()
        image = AuthoredSearch()
        image.words[1] = 0
        with self.assertRaisesRegex(ValueError, "Unknown"):
            image.read()
        image = AuthoredSearch()
        image.words[image.labels["return_value"] + 1] = 0xD65F03C0
        with self.assertRaisesRegex(ValueError, "one bounded normal return"):
            image.read()

    def test_unknown_sdk_and_existing_output_refuse_without_modification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk, output = root / "authored-sdk", root / "report.json"
            sdk.write_bytes(b"Authored unsupported owner input\n")
            with self.assertRaisesRegex(ValueError, "Unknown owner"):
                inspect(sdk, output)
            self.assertFalse(output.exists())
            output.write_bytes(b"Preserved report\n")
            with self.assertRaises(FileExistsError):
                inspect(sdk, output)
            self.assertEqual(output.read_bytes(), b"Preserved report\n")
