"""Authored contracts for current manager graphs, metadata reads and settings."""

import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("test_" + name, ROOT / "tools/phone-build/accepted-output" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G, S, K = [load(name) for name in ("manager_graph", "manager_settings", "manager_sdk")]


def pointer(pid=0, fid=0):
    return dict(m_FileID=fid, m_PathID=pid)


class ManagerGraphTests(unittest.TestCase):
    def test_cycle_and_script_dependency_are_retained_with_leaf_visited(self):
        records = {
            ("a", 1): (dict(component=pointer(2), script=pointer(3, 1)), ["scripts"]),
            ("a", 2): (dict(owner=pointer(1), optional=pointer()), []),
            ("scripts", 3): (dict(name="Fixture"), []),
        }
        graph, seen = G.closure({"root": dict(file="a", id=1), "include": dict(file="", id=0)}, lambda *key: records[key])
        self.assertEqual(seen, set(records))
        self.assertEqual(graph, {("a", 1): [("a", 2), ("scripts", 3)], ("a", 2): [("a", 1)]})

    def test_invalid_external_is_refused_before_missing_dependency_can_be_hidden(self):
        with self.assertRaisesRegex(ValueError, "file ID"):
            G.closure({"root": dict(file="a", id=1)}, lambda *key: (dict(target=pointer(5, 2)), ["b"]))

    def test_missing_provider_is_not_an_empty_resource(self):
        def read(file, pid):
            if file == "a":
                return dict(target=pointer(5, 1)), ["absent"]
            raise ValueError("missing produced provider")

        with self.assertRaisesRegex(ValueError, "missing produced"):
            G.closure({"root": dict(file="a", id=1)}, read)


class ManagerSettingsTests(unittest.TestCase):
    def test_yaml_native_projection_preserves_unselected_fields_and_binary_arrays(self):
        yaml = b"%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!5 &1\nFixture:\n  value: 2.5\n  flags: 0100000002000000\n  objects: []\n  pointer: {fileID: 0}\n"
        selected = S.yaml_settings(yaml)
        original = dict(value=1.0, retained=True, flags=[9], objects=[dict(enabled=False)], pointer=pointer(99, 1))
        actual = S.project(original, selected)
        self.assertEqual(actual, dict(value=2.5, retained=True, flags=[1, 2], objects=[], pointer=pointer()))
        self.assertEqual(original["pointer"], pointer(99, 1))

    def test_yaml_requires_one_root(self):
        with self.assertRaisesRegex(ValueError, "one native root"):
            S.yaml_settings(b"A: {}\nB: {}\n")


class Image:
    def __init__(self, words):
        self.data = struct.pack("<" + "I" * len(words), *words)

    def at(self, address, size):
        if address < 0x1000 or address + size > 0x1000 + len(self.data):
            raise ValueError("fixture address outside bounded image")
        return self.data[address - 0x1000 : address - 0x1000 + size]


class ManagerSdkTests(unittest.TestCase):
    def test_argument_materializes_immediate_page_address_and_register_copy(self):
        # MOV w1,#21; ADRP x2,current page; ADD x2,x2,#128; MOV x3,x2.
        image = Image([0x528002A1, 0x90000002, 0x91020042, 0xAA0203E3])
        self.assertEqual(K.argument(image, 0x1010, 1), 21)
        self.assertEqual(K.argument(image, 0x1010, 3), 0x1080)

    def test_unknown_runtime_write_and_intervening_call_refuse(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            K.argument(Image([0x528002A1, 0xF9400041]), 0x1008, 1)
        with self.assertRaisesRegex(ValueError, "crosses a call"):
            K.argument(Image([0x528002A1, 0x94000000]), 0x1008, 1)


if __name__ == "__main__":
    unittest.main()
