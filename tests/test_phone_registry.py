from pathlib import Path
import struct
import tempfile
import unittest

from phone_registry import MachO, constant_calls, inspect, inspect_action, module_assignments, static_records


class Instructions:
    """Entirely authored code/metadata stand-in; no SDK bytes are embedded."""

    def __init__(self, words, extra_symbols=None):
        self.start = 0x1000
        self.code = struct.pack("<" + "I" * len(words), *words)
        self.symbols = {"function": {self.start}, "end": {self.start + len(self.code)}} | (extra_symbols or {})

    def symbol(self, name):
        values = self.symbols.get(name, set())
        if len(values) != 1:
            raise ValueError("Missing or ambiguous required SDK symbol")
        return next(iter(values))

    def at(self, address, size):
        offset = address - self.start
        if offset < 0 or offset + size > len(self.code):
            raise ValueError("Outside authored instruction fixture")
        return self.code[offset : offset + size]

    def string(self, address):
        if address != 0x3000:
            raise ValueError("Unknown authored module literal")
        return "Fixture"


def fixture():
    data = bytearray(4096)
    vm = 0x100000000
    struct.pack_into("<IiiIIIII", data, 0, 0xFEEDFACF, 0x100000C, 0, 2, 2, 96, 0, 0)
    struct.pack_into("<II16sQQQQiiII", data, 32, 0x19, 72, b"__DATA", vm, len(data), 0, len(data), 7, 3, 0, 0)
    struct.pack_into("<IIIIII", data, 104, 2, 24, 2048, 2, 2080, 256)
    for offset, text in ((512, b"FixtureChild\0"), (544, b"FixtureParent\0"), (576, b"Native\0"), (608, b"undefined\0")):
        data[offset : offset + len(text)] = text
    struct.pack_into("<14Q", data, 768, vm + 1280, 0, vm + 512, vm + 576, vm + 608, 0, 0, 0, 0, 0, vm + 1152, 0, 0, 0)
    struct.pack_into("<14Q", data, 896, 0, 0, vm + 544, vm + 576, vm + 608, 0, 0, 0, 0, 0, vm + 1280, 0, 0, 0)
    strings = b"\0"
    for index, (name, address) in enumerate(((b"__ZL32FixtureChild_TypeRegistrationDesc", vm + 768), (b"__ZL33FixtureParent_TypeRegistrationDesc", vm + 896))):
        struct.pack_into("<IBBHQ", data, 2048 + index * 16, len(strings), 0x0E, 1, 0, address)
        strings += name + b"\0"
    data[2080 : 2080 + len(strings)] = strings
    return bytes(data)


class PhoneRegistryTests(unittest.TestCase):
    def test_constant_arguments_preserve_callee_saved_and_clear_caller_saved(self):
        image = Instructions(
            [
                0xD0000013,  # ADRP x19, 0x3000 (public encoding, authored addresses).
                0x91000260,  # ADD x0, x19, 0.
                0xD28000E1,  # MOVZ x1, 7.
                0x94000400,  # BL authored external destination.
                0xAA1303E0,  # MOV x0, x19.
                0xA8C24FF4,  # LDP x20, x19, [sp], 32 invalidates restored values.
                0x94000400,
                0xAA1303E0,  # Restored x19 remains unknown.
                0x14000400,  # Terminal tail call.
            ]
        )
        calls = constant_calls(image, "function")
        self.assertEqual(calls[0]["arguments"][:2], [0x3000, 7])
        self.assertEqual(calls[1]["arguments"][:2], [0x3000, None])
        self.assertIsNone(calls[2]["arguments"][0])

    def test_word_moves_zero_extend_and_unknown_instructions_refuse(self):
        image = Instructions([0x92800000, 0x2A0003E1, 0x94000400, 0xD65F03C0])
        call = constant_calls(image, "function")[0]
        self.assertEqual(call["arguments"][:2], [0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF])
        for words in ([0x54000020, 0xD65F03C0], [0, 0xD65F03C0], [0xD503201F]):
            with self.subTest(words=words), self.assertRaises(ValueError):
                constant_calls(Instructions(words), "function")

    def test_module_literal_and_template_symbol_bind_the_native_pointer(self):
        outer = "__Z37RegisterModuleClassesGenerated_Fixturev"
        callee = "__Z18RegisterUnityClassI12FixtureClassEvPKc"
        rtti = "__ZN13TypeContainerI12FixtureClassE4rttiE"
        image = Instructions([0xD0000000, 0x14000400], {outer: {0x1000}, callee: {0x2004}, rtti: {0x4000}})
        assignments, functions = module_assignments(image)
        self.assertEqual(assignments, {0x4000: "Fixture"})
        self.assertEqual(functions, [outer])
        image.symbols[callee] = {0x3004}
        with self.assertRaisesRegex(ValueError, "Unknown SDK module-registration"):
            module_assignments(image)

    def test_authored_macho_maps_symbols_strings_and_native_parent_links(self):
        image = MachO(fixture())
        records = static_records(image)
        child = next(row for row in records if row["name"] == "FixtureChild")
        self.assertEqual(child["qualifiedName"], "Native::FixtureChild")
        self.assertEqual(child["baseName"], "FixtureParent")
        self.assertTrue(child["base_resolved"])
        self.assertIsNone(child["module"])
        self.assertEqual(image.string(0x100000000 + 576), "Native")
        with self.assertRaises(ValueError):
            image.at(0x100000000 + 4090, 16)

    def test_malformed_header_commands_tables_and_metadata_pointers_refuse(self):
        original = fixture()
        mutants = [original[:20]]
        for offset, value, fmt in ((0, 0xFEEDFACE, "I"), (4, 7, "I"), (36, 0, "I"), (20, 8, "I"), (120, 9000, "I"), (768 + 16, 0x900000000, "Q")):
            data = bytearray(original)
            struct.pack_into("<" + fmt, data, offset, value)
            mutants.append(bytes(data))
        for data in mutants:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                static_records(MachO(data))

    def test_unknown_sdk_binary_refuses_before_writing_a_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sdk").write_bytes(fixture())
            with self.assertRaisesRegex(ValueError, "Unknown owner SDK"):
                inspect(root / "sdk", root / "report.json")
            self.assertFalse((root / "report.json").exists())

    def test_stage_requires_an_explicit_request_and_pinned_sdk_before_creating_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sdk").write_bytes(fixture())
            import json

            for value in ({"binary": "relative"}, {"binary": str(root / "sdk"), "extra": True}, {"binary": str(root / "sdk")}):
                (root / "request.json").write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    inspect_action(root / "request.json")
