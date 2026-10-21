from pathlib import Path
import struct
import tempfile
import unittest

from phone_registry import (
    MachO,
    call_argument,
    constant_calls,
    direct_calls,
    direct_module_assignments,
    inspect,
    inspect_action,
    module_assignments,
    static_records,
    validate_persistent_ids,
)


class Instructions:
    """Entirely authored code/metadata stand-in; no SDK bytes are embedded."""

    def __init__(self, words, extra_symbols=None):
        self.start = 0x1000
        self.code = struct.pack("<" + "I" * len(words), *words)
        self.data = self.code
        self.sections = [(self.start, len(self.code), 0)]
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
    struct.pack_into("<14Q", data, 896, 0, 0, vm + 544, vm + 640, vm + 608, 0, 0, 0, 0, 0, vm + 1280, 0, 0, 0)
    struct.pack_into("<i", data, 768 + 40, 42)
    struct.pack_into("<i", data, 896 + 40, 7)
    strings = b"\0"
    for index, (name, address) in enumerate(((b"__ZL32FixtureChild_TypeRegistrationDesc", vm + 768), (b"__ZL33FixtureParent_TypeRegistrationDesc", vm + 896))):
        struct.pack_into("<IBBHQ", data, 2048 + index * 16, len(strings), 0x0E, 1, 0, address)
        strings += name + b"\0"
    data[2080 : 2080 + len(strings)] = strings
    return bytes(data)


class PhoneRegistryTests(unittest.TestCase):
    def test_declared_instruction_section_is_bounded_and_address_mapped(self):
        data = bytearray(fixture())
        vm = 0x100000000
        struct.pack_into("<I", data, 20, 176)
        struct.pack_into("<I", data, 36, 152)
        struct.pack_into("<I", data, 96, 1)
        struct.pack_into("<16s16sQQIIIIIIII", data, 104, b"__text", b"__TEXT", vm + 1536, 8, 1536, 2, 0, 0, 0x80000400, 0, 0, 0)
        struct.pack_into("<IIIIII", data, 184, 2, 24, 2048, 2, 2080, 256)
        struct.pack_into("<II", data, 1536, 0x94000002, 0xD65F03C0)
        image = MachO(bytes(data))
        self.assertEqual(image.sections, [(vm + 1536, 8, 1536)])
        self.assertEqual(direct_calls(image, {vm + 1544}), [(vm + 1536, vm + 1544)])
        for offset, value, fmt in ((104 + 40, 4096, "Q"), (104 + 48, 1537, "I"), (96, 2, "I")):
            damaged = bytearray(data)
            struct.pack_into("<" + fmt, damaged, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                MachO(bytes(damaged))

    def test_backward_arguments_match_forward_constants_and_call_clobbers(self):
        image = Instructions([0xD0000013, 0x91000260, 0xD28000E1, 0x94000400, 0xAA1303E0, 0xA8C24FF4, 0x94000400, 0xAA1303E0, 0x14000400])
        calls = constant_calls(image, "function")
        for call in calls:
            for register in (0, 1):
                self.assertEqual(call_argument(image, call["pc"], register), call["arguments"][register])

    def test_incoming_branch_and_loop_join_cannot_supply_skipped_constants(self):
        # A conditional can bypass the apparent definition immediately before a call.
        conditional = Instructions([0xB5000042, 0xD28000E0, 0x94000400, 0xD65F03C0])
        self.assertIsNone(call_argument(conditional, 0x1008, 0))
        # A later loop backedge can reach the call without repeating its definition.
        loop = Instructions([0xD28000E0, 0x94000400, 0xD503201F, 0xB5FFFFC2, 0xD65F03C0])
        self.assertIsNone(call_argument(loop, 0x1004, 0))
        self.assertIsNone(call_argument(Instructions([0, 0x94000400, 0xD65F03C0]), 0x1004, 0))

    def test_direct_branch_index_excludes_identical_words_outside_code_section(self):
        image = Instructions([0x94000400, 0xD65F03C0])
        image.data += struct.pack("<I", 0x940003FE)
        self.assertEqual(direct_calls(image, {0x2000}), [(0x1000, 0x2000)])
        image.sections = []
        with self.assertRaises(ValueError):
            direct_calls(image, {0x2000})

    def test_non_generated_registration_calls_resolve_only_explicit_arguments(self):
        callee = "__Z18RegisterUnityClassI12FixtureClassEvPKc"
        rtti = "__ZN13TypeContainerI12FixtureClassE4rttiE"
        image = Instructions([0xD0000000, 0x14000400], {callee: {0x2004}, rtti: {0x4000}})
        self.assertEqual(direct_module_assignments(image), ({0x4000: "Fixture"}, []))
        image.code = struct.pack("<II", 0xD503201F, 0x14000400)
        image.data = image.code
        self.assertEqual(direct_module_assignments(image), ({}, [0x1004]))
        image.symbols["__Z18RegisterUnityClassI12OtherFixtureEvPKc"] = {0x2004}
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            direct_module_assignments(image)

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
        self.assertEqual(child["persistentTypeID"], 42)
        self.assertTrue(child["base_resolved"])
        self.assertIsNone(child["module"])
        parent = next(row for row in records if row["name"] == "FixtureParent")
        self.assertEqual(parent["nativeNamespace"], "")
        self.assertEqual(parent["qualifiedName"], "FixtureParent")
        self.assertEqual(parent["persistentTypeID"], 7)
        self.assertEqual(image.string(0x100000000 + 576), "Native")
        with self.assertRaises(ValueError):
            image.at(0x100000000 + 4090, 16)

    def test_persistent_id_validation_refuses_duplicate_unknown_and_invalid_ids(self):
        validate_persistent_ids([{"persistentTypeID": 0}, {"persistentTypeID": 0x7FFFFFFF}])
        for identifiers in ([1, 1], [None], [-1], [0x80000000], [True], ["42"]):
            with self.subTest(identifiers=identifiers), self.assertRaises(ValueError):
                validate_persistent_ids([{"persistentTypeID": value} for value in identifiers])

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
