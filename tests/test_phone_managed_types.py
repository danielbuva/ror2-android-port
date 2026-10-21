import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import phone_managed_types
from phone_managed_types import MetadataUniverse, inspect_file


def identity(name, version="1.0.0.0"):
    return f"{name}, Version={version}, Culture=neutral, PublicKeyToken=null"


def scope(name, *, local=False, version="1.0.0.0"):
    return {
        "kind": "ModuleDefinition" if local else "AssemblyNameReference",
        "name": name + (".dll" if local else ""),
        "assembly_identity": identity(name, version),
    }


def defined(name, base=None, base_scope=None):
    return {"name": name, "base_type": base, "base_scope": base_scope}


def exported(name, target, parent=None, forwarder=True):
    return {"name": name, "scope": scope(target), "declaring_type": parent, "is_forwarder": forwarder}


def assembly(name, *, types=(), exports=(), references=(), group="selected"):
    return {
        "group": group,
        "assembly": name,
        "assembly_identity": identity(name),
        "module_name": name + ".dll",
        "types": list(types),
        "exported_types": list(exports),
        "references": [identity(x) for x in references],
    }


def universe(*rows):
    return MetadataUniverse({"schema": 2, "executes_inputs": False, "assemblies": list(rows)}, "selected")


class ManagedTypeResolutionTests(unittest.TestCase):
    def test_standalone_report_refuses_overwrite_and_incomplete_dependencies(self):
        rows = [
            assembly("Implementation", types=[defined("Fixture.Root")]),
            assembly("Facade", exports=[exported("Fixture.Root", "Implementation")], references=["Implementation"]),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metadata, report = root / "metadata.json", root / "report.json"
            metadata.write_text(json.dumps({"schema": 2, "executes_inputs": False, "assemblies": rows}))
            command = [sys.executable, "-I", "-S", phone_managed_types.__file__, str(metadata), "selected", str(report)]
            subprocess.run(command, check=True, capture_output=True)
            before = report.read_bytes()
            result = json.loads(before)
            self.assertEqual(result["exported_types"], 1)
            self.assertEqual(result["resolved"][0]["to_assembly"], identity("Implementation"))
            self.assertFalse(result["root_generation_qualified"])
            self.assertIs(result["executes_inputs"], False)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(report.read_bytes(), before)
            metadata.write_text(json.dumps({"schema": 2, "executes_inputs": False, "assemblies": rows[1:]}))
            with self.assertRaisesRegex(ValueError, "Missing exact assembly"):
                inspect_file(metadata, "selected", root / "missing.json")
            self.assertFalse((root / "missing.json").exists())

    def test_forwarded_nested_type_and_external_base_resolve_by_exact_scope(self):
        target = assembly(
            "Implementation", types=[defined("Fixture.Root"), defined("Fixture.Root/Nested", "Fixture.Root", scope("Implementation", local=True))]
        )
        facade = assembly(
            "Facade",
            exports=[exported("Fixture.Root", "Implementation"), exported("Fixture.Root/Nested", "Implementation", "Fixture.Root", False)],
            references=["Implementation"],
        )
        user = assembly("User", types=[defined("Fixture.Child", "Fixture.Root/Nested", scope("Facade"))], references=["Facade"])
        resolver = universe(target, facade, user)
        result = resolver.resolve(identity("Facade"), "Fixture.Root/Nested")
        self.assertEqual(result["assembly_identity"], identity("Implementation"))
        self.assertEqual(result["forwarders"], [{"assembly_identity": identity("Facade"), "name": "Fixture.Root/Nested"}])
        self.assertTrue(resolver.derives_from(identity("User"), "Fixture.Child", identity("Facade"), "Fixture.Root"))
        self.assertFalse(resolver.derives_from(identity("Implementation"), "Fixture.Root", identity("User"), "Fixture.Child"))
        self.assertIsNone(resolver.resolve(identity("Implementation"), "Fixture.Absent"))

    def test_other_group_or_same_short_name_never_fills_dependency(self):
        facade = assembly("Facade", exports=[exported("Fixture.Root", "Implementation")], references=["Implementation"])
        wrong_group = assembly("Implementation", group="other", types=[defined("Fixture.Root")])
        resolver = universe(facade, wrong_group)
        with self.assertRaisesRegex(ValueError, "Missing exact assembly"):
            resolver.resolve(identity("Facade"), "Fixture.Root")
        target = assembly("Implementation", types=[defined("Fixture.Root")])
        target["assembly_identity"] = identity("Implementation", "2.0.0.0")
        with self.assertRaisesRegex(ValueError, "Missing exact assembly"):
            universe(facade, target).resolve(identity("Facade"), "Fixture.Root")

    def test_duplicate_assembly_or_type_refuses_instead_of_selecting_first(self):
        row = assembly("Implementation", types=[defined("Fixture.Root")])
        for duplicate in (copy.deepcopy(row), row | {"assembly_identity": identity("Implementation", "2.0.0.0")}):
            with self.assertRaisesRegex(ValueError, "Ambiguous assembly"):
                universe(row, duplicate)
        for duplicate in (row | {"types": row["types"] * 2}, row | {"exported_types": [exported("Fixture.Root", "Elsewhere")]}):
            with self.assertRaisesRegex(ValueError, "Ambiguous type"):
                universe(duplicate)

    def test_missing_forwarded_definition_and_forwarding_cycles_refuse(self):
        facade = assembly("Facade", exports=[exported("Fixture.Root", "Implementation")], references=["Implementation"])
        with self.assertRaisesRegex(ValueError, "Forwarded definition"):
            universe(facade, assembly("Implementation")).resolve(identity("Facade"), "Fixture.Root")
        cyclic = assembly("Implementation", exports=[exported("Fixture.Root", "Facade")], references=["Facade"])
        with self.assertRaisesRegex(ValueError, "Cyclic type forwarding"):
            universe(facade, cyclic).resolve(identity("Facade"), "Fixture.Root")

    def test_nonforwarding_exports_missing_parents_and_bad_scopes_refuse(self):
        target = assembly("Implementation", types=[defined("Fixture.Root"), defined("Fixture.Root/Nested")])
        cases = [
            exported("Fixture.Root", "Implementation", forwarder=False),
            exported("Fixture.Root/Nested", "Implementation", "Fixture.Root", False),
            exported("Fixture.Root", "Implementation") | {"scope": scope("Implementation") | {"kind": "ModuleReference"}},
        ]
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValueError):
                universe(target, assembly("Facade", exports=[item], references=["Implementation"])).resolve(identity("Facade"), item["name"])
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            universe(target, assembly("Facade", exports=[exported("Fixture.Root", "Implementation")])).resolve(identity("Facade"), "Fixture.Root")

    def test_unresolved_or_cyclic_managed_bases_never_become_negative_matches(self):
        target = assembly("Implementation", types=[defined("Fixture.Root"), defined("Fixture.Child", "Fixture.Absent", scope("Implementation", local=True))])
        with self.assertRaisesRegex(ValueError, "Missing inheritance"):
            universe(target).derives_from(identity("Implementation"), "Fixture.Child", identity("Implementation"), "Fixture.Root")
        target["types"][1]["base_type"] = "Fixture.Child"
        with self.assertRaisesRegex(ValueError, "Cyclic inheritance"):
            universe(target).derives_from(identity("Implementation"), "Fixture.Child", identity("Implementation"), "Fixture.Root")
        target["types"][1]["base_scope"] = scope("Other", local=True)
        with self.assertRaisesRegex(ValueError, "Foreign local"):
            universe(target).derives_from(identity("Implementation"), "Fixture.Child", identity("Implementation"), "Fixture.Root")
