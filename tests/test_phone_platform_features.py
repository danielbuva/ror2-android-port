"""Authored Mach-O/append fixtures; no captured SDK table is a test input."""

import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_platform_features as feature


BASE, CODE, STRINGS = 0x10000, 0x10400, 0x12000
STUB, GROW, ASSERT, RESERVE = 0x10300, 0x13000, 0x13004, 0x13008


def move(destination, source):
    return 0xAA0003E0 | source << 16 | destination


def immediate(destination, value):
    return 0x52800000 | value << 5 | destination


def load(destination, base, offset=0):
    return 0xF9400000 | (offset // 8) << 10 | base << 5 | destination


def store(source, base, offset=0):
    return 0xF9000000 | (offset // 8) << 10 | base << 5 | source


def branch(pc, target, condition=None):
    return (0x14000000 | (((target - pc) // 4) & 0x3FFFFFF)) if condition is None else (0x54000000 | ((((target - pc) // 4) & 0x7FFFF) << 5) | condition)


def call(pc, target):
    return 0x94000000 | (((target - pc) // 4) & 0x3FFFFFF)


def address(register, pc, pointer):
    pages = ((pointer & ~4095) - (pc & ~4095)) // 4096 & 0x1FFFFF
    return [0x90000000 | (pages & 3) << 29 | (pages >> 2) << 5 | register, 0x91000000 | (pointer & 4095) << 10 | register << 5 | register]


def authored_image(reused=False, out=19):
    tokens = {"PLATFORM_ANDROID": STRINGS, "AUTHORED_FEATURE": STRINGS + 64, "fixture.c": STRINGS + 128, "Authored overflow": STRINGS + 192}
    values = [
        move(21, 0),
        move(out, 1),
        move(23, 1),
        0xF8400C00 | 32 << 12 | 23 << 5 | 8,
        0xF100001F | 119 << 10 | 8 << 5,
        0,
        move(0, out),
        immediate(1, 60),
        immediate(2, 8),
        immediate(3, 8),
        0,
    ]
    header = CODE + len(values) * 4
    values[5] = branch(CODE + 20, header, 8)
    values[10] = call(CODE + 40, RESERVE)
    values += address(22, header, STRINGS)
    values += [move(0, 22), move(1, 21), call(header + 16, STUB), 0]
    body = CODE + len(values) * 4
    values += [load(24, out, 24), 0xB1000000 | 1 << 10 | 24 << 5 | 25, branch(body + 8, body + 44, 3)]
    values += address(1, body + 12, tokens["fixture.c"])
    values += address(4, body + 20, tokens["Authored overflow"])
    values += [
        immediate(0, 0),
        immediate(2, 123),
        0x12800003,
        call(body + 40, ASSERT),
        load(8, 23),
        0xEB40041F | 8 << 16 | 25 << 5,
        0,
        store(25, out, 24),
        load(8, out),
    ]
    if not reused:
        values += address(9, body + 64, tokens["AUTHORED_FEATURE"])
    values += [0xF8207800 | 24 << 16 | 8 << 5 | (22 if reused else 9)]
    end = CODE + len(values) * 4
    values[(header + 20 - CODE) // 4] = 0x35000000 | (((end - (header + 20)) // 4) << 5)
    values += [0xD65F03C0]
    grow = CODE + len(values) * 4
    values[(body + 52 - CODE) // 4] = branch(body + 52, grow, 8)
    values += [move(0, out), call(grow + 4, GROW), branch(grow + 8, body + 56)]
    code = b"".join(struct.pack("<I", w) for w in values)
    data = bytearray(0x4000)
    sections = []
    for name, offset, size, flags, first, stride in [
        (b"__text", 0x400, len(code), 0x80000400, 0, 0),
        (b"__stubs", 0x300, 12, 0x80000408, 0, 12),
        (b"__cstring", 0x2000, 256, 2, 0, 0),
    ]:
        sections.append(struct.pack("<16s16sQQIIIIIIII", name, b"__TEXT", BASE + offset, size, offset, 2, 0, 0, flags, first, stride, 0))
    segment = struct.pack("<II16sQQQQiiII", 0x19, 72 + 3 * 80, b"__TEXT", BASE, len(data), 0, len(data), 7, 5, 3, 0) + b"".join(sections)
    symbols = [
        ("_strcmp", 1, 0, 0x100, 0),
        (feature.FUNCTION, 0xF, 1, 0, CODE),
        ("authored_end", 0xF, 1, 0, CODE + len(code)),
        (feature.GROW, 0xF, 1, 0, GROW),
        (feature.ASSERT, 0xF, 1, 0, ASSERT),
        (feature.RESERVE, 0xF, 1, 0, RESERVE),
    ]
    strings, entries = bytearray(b"\0"), []
    for name, kind, section, description, value in symbols:
        entries.append(struct.pack("<IBBHQ", len(strings), kind, section, description, value))
        strings += name.encode() + b"\0"
    symtab = struct.pack("<6I", 2, 24, 0x1000, len(symbols), 0x1100, len(strings))
    dysymtab = bytearray(struct.pack("<20I", 0xB, 80, *([0] * 18)))
    struct.pack_into("<2I", dysymtab, 56, 0x1600, 1)
    library = b"/usr/lib/libSystem.B.dylib\0"
    length = (24 + len(library) + 7) & ~7
    dylib = struct.pack("<6I", 0xC, length, 24, 0, 0, 0) + library + b"\0" * (length - 24 - len(library))
    commands = segment + symtab + dysymtab + dylib
    data[:32] = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x100000C, 0, 2, 4, len(commands), 0, 0)
    data[32 : 32 + len(commands)] = commands
    data[0x400 : 0x400 + len(code)] = code
    data[0x1000 : 0x1000 + 16 * len(entries)] = b"".join(entries)
    data[0x1100 : 0x1100 + len(strings)] = strings
    for name, at in tokens.items():
        data[at - BASE : at - BASE + len(name) + 1] = name.encode() + b"\0"
    return bytes(data), dict(header=header, body=body, end=end, grow=grow, code_end=CODE + len(code))


def mutate_word(data, pc, value):
    result = bytearray(data)
    struct.pack_into("<I", result, pc - BASE, value)
    return bytes(result)


class PlatformDeclarationsTests(unittest.TestCase):
    def test_full_authored_metadata_flow_and_preserved_literal(self):
        for reused in (False, True):
            for out in (19, 20):
                data, positions = authored_image(reused=reused, out=out)
                result = feature.decode(feature.registry.MachO(data))
                self.assertEqual(result["comparison_stub"], STUB)
                self.assertEqual(result["parameter_bindings"]["output_register"], out)
                self.assertEqual(result["parameter_bindings"]["capacity_field"], 32)
                self.assertEqual([x["feature"] for x in result["declarations"]], ["PLATFORM_ANDROID" if reused else "AUTHORED_FEATURE"])
                self.assertEqual(result["normal_exit_end"], positions["grow"])

    def test_unknown_selected_append_instructions_refuse(self):
        data, positions = authored_image()
        for offset in range(0, 76, 4):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                feature.decode(feature.registry.MachO(mutate_word(data, positions["body"] + offset, 0xFFFFFFFF)))

    def test_growth_and_return_paths_must_preserve_the_same_append(self):
        data, p = authored_image()
        mutations = [
            (p["body"] + 52, branch(p["body"] + 52, p["body"], 8)),
            (p["grow"], move(0, 20)),
            (p["grow"] + 4, call(p["grow"] + 4, ASSERT)),
            (p["grow"] + 8, branch(p["grow"] + 8, p["body"] + 60)),
            (p["end"], move(19, 0)),
        ]
        for pc, value in mutations:
            with self.subTest(pc=pc), self.assertRaises(ValueError):
                feature.decode(feature.registry.MachO(mutate_word(data, pc, value)))

    def test_receiver_and_capacity_parameter_mutations_refuse(self):
        data, p = authored_image()
        mutations = [
            (CODE, move(21, 1)),
            (CODE + 4, move(19, 0)),
            (CODE + 12, 0xF8400C00 | 24 << 12 | 23 << 5 | 8),
            (p["header"] + 12, move(1, 20)),
            (p["body"], load(24, 19, 0)),
        ]
        for pc, value in mutations:
            with self.subTest(pc=pc), self.assertRaises(ValueError):
                feature.decode(feature.registry.MachO(mutate_word(data, pc, value)))

    def test_foreign_branch_into_literal_body_is_not_accepted(self):
        data, p = authored_image()
        image = feature.registry.MachO(data)
        words = feature.generated_words(image, feature.FUNCTION)
        case = feature.selectors(image, words, STUB)[0]
        records, growth, _, _ = feature.append_records(image, words, case, (19, 21))
        words[CODE] = branch(CODE, p["body"] + 56)
        with self.assertRaisesRegex(ValueError, "Foreign branch"):
            feature.closed_body(words, case, records, growth, p["grow"])

    def test_hoisted_selector_pointer_is_bounded_and_cannot_overwrite_result(self):
        data, p = authored_image()
        image = feature.registry.MachO(data)
        words = feature.generated_words(image, feature.FUNCTION)
        call_pc = p["header"] + 16
        words[call_pc + 4], words[call_pc + 8] = address(24, call_pc + 4, STRINGS + 64)
        words[call_pc + 12] = 0x35000000 | (((p["end"] - (call_pc + 12)) // 4) << 5)
        result = feature.selectors(image, words, STUB)
        self.assertEqual(result[0]["hoisted"], [(24, STRINGS + 64)])
        words[call_pc + 4], words[call_pc + 8] = address(0, call_pc + 4, STRINGS + 64)
        cases = feature.selectors(image, words, STUB)
        with self.assertRaisesRegex(ValueError, "clobbers"):
            feature.entry_bindings(image, words, cases, 19, 23)


class MachOFeatureMetadataTests(unittest.TestCase):
    def test_import_binding_refuses_foreign_library_symbol_or_indices(self):
        data, _ = authored_image()
        self.assertEqual(feature.imported_stub(feature.registry.MachO(data), "_strcmp"), STUB)
        for change in ("ordinal", "defined", "index", "first", "stride", "duplicate"):
            altered = bytearray(data)
            if change == "ordinal":
                struct.pack_into("<H", altered, 0x1000 + 6, 0x200)
            elif change == "defined":
                altered[0x1000 + 4] = 0xF
            elif change == "index":
                struct.pack_into("<I", altered, 0x1600, 99)
            elif change == "first":
                struct.pack_into("<I", altered, 32 + 72 + 80 + 68, 9)
            elif change == "stride":
                struct.pack_into("<I", altered, 32 + 72 + 80 + 72, 0)
            else:
                struct.pack_into("<Q", altered, 32 + 72 + 80 + 40, 24)
                # LC_DYSYMTAB follows the segment and symtab.
                struct.pack_into("<I", altered, 32 + 312 + 24 + 60, 2)
            with self.subTest(change=change), self.assertRaises(ValueError):
                feature.imported_stub(feature.registry.MachO(bytes(altered)), "_strcmp")

    def test_literals_must_be_in_file_backed_declared_string_sections(self):
        data, _ = authored_image()
        image = feature.registry.MachO(data)
        self.assertEqual(feature.literal(image, STRINGS), "PLATFORM_ANDROID")
        with self.assertRaises(ValueError):
            feature.literal(image, CODE)
        altered = bytearray(data)
        altered[0x2000:0x2100] = b"A" * 256
        with self.assertRaisesRegex(ValueError, "Unterminated"):
            feature.literal(feature.registry.MachO(bytes(altered)), STRINGS)


class PlatformFeatureCliTests(unittest.TestCase):
    def test_unknown_sdk_refuses_including_optimized_isolated_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            sdk, output = Path(temporary) / "sdk", Path(temporary) / "output.json"
            sdk.write_bytes(b"Authored unknown SDK")
            for flags in ([], ["-O"]):
                result = subprocess.run(
                    [sys.executable, *flags, "-I", "-S", feature.__file__, str(sdk), str(output)], capture_output=True, text=True, timeout=30
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Unknown owner SDK", result.stderr)
                self.assertNotIn("ModuleNotFoundError", result.stderr)
                self.assertFalse(output.exists())
            output.write_bytes(b"Existing report")
            with self.assertRaises(FileExistsError):
                feature.inspect(sdk, output)
            self.assertEqual(output.read_bytes(), b"Existing report")

    def test_optional_exact_sdk_report_is_declarations_only(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity")
        if not sdk.is_file():
            self.skipTest("Optional owner SDK absent")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            result = feature.inspect(sdk, path)
            self.assertEqual(result["selector_count"], 21)
            self.assertEqual(len(result["declarations"]), 62)
            names = [row["feature"] for row in result["declarations"]]
            self.assertIn("ENABLE_AUDIO", names)
            self.assertIn("ENABLE_CLOTH", names)
            self.assertIn("ENABLE_PHYSICS", names)
            self.assertNotIn("ENABLE_CLUSTERINPUT", names)
            self.assertNotIn("ENABLE_MOVIES", names)
            for key in (
                "executes_sdk",
                "other_platforms_qualified",
                "target_discovery_qualified",
                "module_include_qualified",
                "state_retention_qualified",
                "native_usage_qualified",
                "root_generation_qualified",
            ):
                self.assertIs(result[key], False)
            self.assertEqual(json.loads(path.read_text()), result)
