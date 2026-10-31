"""Native scene reference, parser-schema and SDK declaration contracts."""

import importlib.util
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace as N
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    s = importlib.util.spec_from_file_location("scene_test_" + name, ROOT / "tools/phone-build/accepted-output" / (name + ".py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


C, K, D = [load(name) for name in ("player_scene", "scene_sdk", "manager_sdk")]


def elf_pair():
    code = bytearray(1024)
    symbols = bytearray(1024)
    for data in (code, symbols):
        data[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", data, 18, 183)
    struct.pack_into("<Q", code, 32, 64)
    struct.pack_into("<HH", code, 54, 56, 1)
    struct.pack_into("<IIQQQQQQ", code, 64, 1, 5, 512, 0x1000, 0, 64, 64, 4096)
    code[512:528] = b"fixture-code-123"
    struct.pack_into("<Q", symbols, 40, 64)
    struct.pack_into("<HH", symbols, 58, 64, 4)
    # Section one is NOBITS: it cannot supply instructions. Tables two/three
    # describe actual function names and addresses, independently of code bytes.
    struct.pack_into("<IIQQQQIIQQ", symbols, 128, 0, 8, 6, 0x1000, 0, 64, 0, 0, 4, 0)
    struct.pack_into("<IIQQQQIIQQ", symbols, 192, 0, 2, 0, 0, 512, 48, 3, 0, 8, 24)
    names = b"\x00fixture\x00after\x00"
    struct.pack_into("<IIQQQQIIQQ", symbols, 256, 0, 3, 0, 0, 768, len(names), 0, 0, 1, 0)
    symbols[768 : 768 + len(names)] = names
    struct.pack_into("<IBBHQQ", symbols, 512, 1, 2, 0, 1, 0x1000, 16)
    struct.pack_into("<IBBHQQ", symbols, 536, 9, 2, 0, 1, 0x1010, 4)
    return code, symbols


class SceneSdkTests(unittest.TestCase):
    def test_symbol_only_nobits_text_never_substitutes_for_code(self):
        code, symbols = elf_pair()
        image = K.Elf(code, symbols)
        self.assertEqual(image.symbol("fixture"), 0x1000)
        self.assertEqual(image.at(image.symbol("fixture"), 16), b"fixture-code-123")
        self.assertEqual(D.bounds(image, "fixture"), (0x1000, 0x1010))
        with self.assertRaisesRegex(ValueError, "file-backed"):
            image.at(0x2000, 4)

    def test_zero_register_and_unknown_runtime_values_are_distinct(self):
        class Image:
            def at(self, address, size):
                self.last = address
                return struct.pack("<I", 0x2A1F03E1)  # MOV W1,WZR

        self.assertEqual(D.argument(Image(), 0x1004, 1), 0)

    def test_truncated_symbol_and_wrong_architecture_refuse(self):
        code, symbols = elf_pair()
        with self.assertRaisesRegex(ValueError, "extent"):
            K.Elf(code, symbols[:520])
        struct.pack_into("<H", code, 18, 62)
        with self.assertRaisesRegex(ValueError, "ARM64"):
            K.Elf(code, symbols)


class SceneReferenceTests(unittest.TestCase):
    def source(self, fields, externals):
        return N(read_typetree=lambda: fields, node=True, type=N(value=23), asset=N(externals=[dict(path=x) for x in externals]))

    def test_preserved_cookie_rebinds_by_name_while_replaced_material_needs_no_donor(self):
        original = dict(cookie=C.pointer(41, 3), material=C.pointer(7, 1), items=[C.pointer()], count=2)
        obj = self.source(original, ["archive:/unused", "other", "Library/unity default resources"])
        actual = C.native_copy(obj, dict(material=C.pointer(2, 1)))
        self.assertEqual(actual["cookie"], C.pointer(41, 2))
        self.assertEqual(actual["material"], C.pointer(2, 1))
        self.assertEqual(original["cookie"], C.pointer(41, 3))

    def test_unbound_local_or_external_reference_is_never_silently_kept(self):
        with self.assertRaisesRegex(ValueError, "scene-local"):
            C.native_copy(self.source(dict(target=C.pointer(4)), []), {})
        with self.assertRaisesRegex(ValueError, "provider"):
            C.native_copy(self.source(dict(target=C.pointer(4, 1)), ["unknown"]), {})

    def test_pinned_native_schema_without_optional_type_flags_survives_emission(self):
        from UnityPy.helpers.Tpk import get_typetree_node
        from UnityPy.helpers.UnityVersion import UnityVersion

        node = get_typetree_node(1, UnityVersion.from_str("2021.3.45f2"))
        fields = C.U.zero(node)
        fields.update(m_Name="authored fixture", m_IsActive=True)
        typ = dict(class_id=1, stripped=0, script_type=-1, hash=bytes(16))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            C.emit([dict(id=1, role="fixture/GameObject", fields=fields, node=node, typ=typ)], 0, root)
            rebuilt = C.U.node_from_tree((root / "schema-0.tree").read_bytes())
            self.assertEqual(C.U.encode(fields, rebuilt), C.U.encode(fields, node))
            with (root / "level0").open("rb") as stream:
                stream.size = (root / "level0").stat().st_size
                layout = C.U.W.read_serialized(stream)
                row = layout["objects"][0]
                stream.seek(layout["data_offset"] + row["offset"])
                self.assertEqual(stream.read(row["bytes"]), C.U.encode(fields, node))

    def test_public_rotation_acts_on_forward_axis(self):
        q = C.rotation([0, 90, 0])
        self.assertAlmostEqual(sum(v * v for v in q.values()), 1, places=6)
        # q * (0,0,1) * conjugate(q) points right for a positive Y rotation.
        self.assertAlmostEqual(2 * (q["x"] * q["z"] + q["w"] * q["y"]), 1, places=6)
        self.assertAlmostEqual(1 - 2 * (q["x"] ** 2 + q["y"] ** 2), 0, places=6)


if __name__ == "__main__":
    unittest.main()
