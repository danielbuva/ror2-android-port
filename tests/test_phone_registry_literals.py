import struct
import unittest

from phone_registry import call_argument
from phone_registry_literals import descriptor


class LiteralImage:
    """Entirely authored descriptor/ABI fixture, with no SDK instruction sequence."""

    def __init__(self, words, extra=None):
        self.start, self.target = 0x1000, 0x2000
        self.words = words
        self.data = struct.pack("<" + "I" * len(words), *words)
        self.symbols = {"construct": {self.start}, "end": {self.start + len(self.data)}, "register": {self.target}} | (extra or {})

    def symbol(self, name):
        values = self.symbols.get(name, set())
        if len(values) != 1:
            raise ValueError("Missing/ambiguous authored symbol")
        return next(iter(values))

    def at(self, address, size):
        if 0x3000 <= address < 0x3100 and size == 1:
            return b"x"
        offset = address - self.start
        if offset < 0 or offset + size > len(self.data):
            raise ValueError("Outside authored fixture")
        return self.data[offset : offset + size]


def branch(pc, target):
    return 0x94000000 | (((target - pc) // 4) & 0x3FFFFFF)


def root_fixture(intermediate=(), first=0x6F00E400):
    # Public ARM encodings describe an authored stack literal with synthetic values.
    words = [
        first,  # MOVI vector 0, zero.
        0xAD0003E0,  # STP Q0, Q0, [SP]: parent bytes are zero.
        0xD2860002,  # MOVZ X2, 0x3000.
        0xD2860803,  # MOVZ X3, 0x3040.
        0xA9010FE2,  # STP X2, X3, [SP, 16]: name and namespace.
        0xD2861004,  # MOVZ X4, 0x3080.
        0xF90013E4,  # STR X4, [SP, 32]: module.
        0xD2880005,  # MOVZ X5, 0x4000.
        0xF9002BE5,  # STR X5, [SP, 80]: self pointer.
    ] + list(intermediate)
    words.append(0x910003E1)  # ADD X1, SP, 0: the descriptor address.
    words += [branch(0x1000 + len(words) * 4, 0x2000), 0xD65F03C0]
    return LiteralImage(words)


class LiteralRecordTests(unittest.TestCase):
    def read(self, image):
        return descriptor(image, "construct", image.target, call_argument)

    def test_authored_stack_literal_recovers_constants_and_zero_parent(self):
        self.assertEqual(
            self.read(root_fixture()),
            {0: ("constant", 0), 16: ("constant", 0x3000), 24: ("constant", 0x3040), 32: ("constant", 0x3080), 80: ("constant", 0x4000)},
        )

    def test_conditional_and_partial_overwrites_cannot_supply_metadata(self):
        for intermediate in ((0xB5000046, 0xF9000BFF), (0xB90017FF,)):
            with self.subTest(intermediate=intermediate), self.assertRaisesRegex(ValueError, "skipped or partially"):
                self.read(root_fixture(intermediate))

    def test_frame_change_alias_store_unknown_call_and_indirect_flow_refuse(self):
        for intermediate in ((0x910043FF,), (0xF9000000,), (branch(0x1024, 0x2800),), (0xD61F00E0,), (0xB5FFFF26,)):
            with self.subTest(intermediate=intermediate), self.assertRaises(ValueError):
                self.read(root_fixture(intermediate))

    def test_an_unproven_vector_value_cannot_become_a_zero_parent(self):
        with self.assertRaisesRegex(ValueError, "literal zero"):
            self.read(root_fixture(first=0x6F00E401))

    def test_simple_constructor_preserves_explicit_entry_argument_origins(self):
        words = [0x6F00E400, 0xAD0003E0, 0xA90113E3, 0xD2861008, 0xF90013E8, 0xF9002BE2, 0x910003E1]
        words += [branch(0x1000 + len(words) * 4, 0x2000), 0xD65F03C0]
        image = LiteralImage(words)
        self.assertEqual(self.read(image), {0: ("constant", 0), 16: ("parameter", 3), 24: ("parameter", 4), 32: ("constant", 0x3080), 80: ("parameter", 2)})
        modified = words[:2] + [0x91000443] + words[2:-2]
        modified += [branch(0x1000 + len(modified) * 4, 0x2000), 0xD65F03C0]
        with self.assertRaisesRegex(ValueError, "Unknown metadata field origin"):
            self.read(LiteralImage(modified))

    def test_only_qualified_assertions_with_literal_strings_may_intervene(self):
        intermediate = [0xD2860001, 0xD28003E2, 0x12800003, 0xD2860804]
        intermediate.append(branch(0x1024 + len(intermediate) * 4, 0x2400))
        image = root_fixture(intermediate)
        image.symbols["__Z20AssertImplementationiPKciiS0_"] = {0x2400}
        self.assertEqual(self.read(image)[80], ("constant", 0x4000))
        intermediate[0] = 0x910003E1  # A stack address cannot masquerade as a string literal.
        image = root_fixture(intermediate)
        image.symbols["__Z20AssertImplementationiPKciiS0_"] = {0x2400}
        with self.assertRaisesRegex(ValueError, "Unknown assertion string"):
            self.read(image)
