"""Authored CLR facts and native prototypes produce exact release metadata."""

import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pointer_schema_identity", ROOT / "scripts/lab/script_identity.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


class PointerSchemaTests(unittest.TestCase):
    def test_original_field_context_rechecks_pinned_assemblies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / "Managed"
            directory.mkdir()
            assembly = directory / "Fixture.dll"
            assembly.write_bytes(b"authored original metadata")
            managed = {"path": "Managed", "files": {assembly.name: hashlib.sha256(assembly.read_bytes()).hexdigest()}}

            class CLR:
                def __init__(self, directory, providers, pin, native, templates):
                    self.pin = pin

                def declared_field_names(self, *names):
                    self.pin(assembly)
                    return {"live"}

                def close(self):
                    pass

            script = S._script_body(("Fixture.dll", "Fixture", "Current"), bytes(16))
            with patch.object(S, "_RegistryTypes", CLR):
                fields = S.OriginalScriptFields(root, managed)
                self.assertEqual(fields.names(script), {"live"})
                fields.verify()
                assembly.write_bytes(b"changed metadata")
                with self.assertRaisesRegex(ValueError, "assembly drift"):
                    fields.verify()
                fields.close()

    def fixture(self, root):
        directory = root / "Managed"
        directory.mkdir()
        assembly = directory / "Fixture.dll"
        assembly.write_bytes(b"authored metadata fixture")
        managed = dict(path="Managed", files={assembly.name: hashlib.sha256(assembly.read_bytes()).hexdigest()})
        base = [S._node("MonoBehaviour", "Base", -1, level=0, meta=0x8000), S._node("int", "m_Base", 4)]
        sdk = base + [S._node("string", "m_EditorClassIdentifier", -1)]
        original = [
            S._node("PPtr<$Object>", "oldTarget", 12),
            S._node("int", "m_FileID", 4, level=2, meta=0x800001),
            S._node("SInt64", "m_PathID", 8, level=2, meta=0x800001),
        ]
        custom = [S._node("PPtr<$GameObject>", "chosenTarget", 12), S._node("int", "m_FileID", 4, level=2), S._node("SInt64", "m_PathID", 8, level=2)]
        release = copy.deepcopy(original)
        for a, b in zip(release, custom, strict=True):
            a.update(type=b["type"], name=b["name"])
        expected = S._tree(base + release, common_strings=True)
        properties = S.properties_hash("Trigger", "Fixture", "Fixture.dll", expected, S._tree(sdk))
        script = S._script_body(("Fixture.dll", "Fixture", "Trigger"), properties)

        class CLR:
            closed = False

            def __init__(self, path, providers, pin, native, templates):
                self.pin = pin

            def load(self, name):
                self.pin(directory / name)
                return N(net=N(mdtables=N(TypeDef=N(rows=[N(TypeName="Trigger", TypeNamespace="Fixture")]))))

            def hierarchy(self, name, row):
                return [(name, row)], True

            def custom_fields(self, hierarchy):
                return copy.deepcopy(custom)

            def close(self):
                CLR.closed = True

        args = root, managed, script, S._tree(base), S._tree(base + original), S._tree(sdk)
        return args, CLR, expected, properties, assembly

    def test_source_fields_transfer_native_flags_and_preserve_script_properties(self):
        with tempfile.TemporaryDirectory() as temp:
            args, clr, expected, properties, assembly = self.fixture(Path(temp))
            with patch.object(S, "_RegistryTypes", clr):
                result, pins = S.pointer_script_schema(*args)
            self.assertEqual(result, dict(tree=expected, hash=properties, script_id=S.md4(b"TriggerFixtureFixture.dll")))
            self.assertEqual(pins, {"Managed/Fixture.dll": hashlib.sha256(assembly.read_bytes()).hexdigest()})
            self.assertEqual([n["name"] for n in S.tree_nodes(result["tree"])[-3:]], ["chosenTarget", "m_FileID", "m_PathID"])
            self.assertEqual(S.tree_nodes(result["tree"])[-1]["meta"], 0x800001)
            self.assertTrue(clr.closed)

    def test_changed_assembly_and_incompatible_clr_fields_or_script_hash_refuse(self):
        for failure in ("assembly", "fields", "properties"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                args, clr, _, _, assembly = self.fixture(Path(temp))
                args = list(args)
                if failure == "assembly":
                    assembly.write_bytes(b"changed")
                elif failure == "fields":
                    clr.custom_fields = lambda self, hierarchy: [S._node("float", "value", 4)]
                else:
                    args[2] = S._script_body(("Fixture.dll", "Fixture", "Trigger"), bytes(16))
                with patch.object(S, "_RegistryTypes", clr), self.assertRaises(ValueError):
                    S.pointer_script_schema(*args)
                self.assertTrue(clr.closed)


if __name__ == "__main__":
    unittest.main()
