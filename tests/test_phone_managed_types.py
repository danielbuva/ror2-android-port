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
        with self.assertRaisesRegex(ValueError, "Ambiguous type"):
            universe(row | {"types": row["types"] * 2})
        conflict = universe(row | {"exported_types": [exported("Fixture.Root", "Elsewhere")]})
        with self.assertRaisesRegex(ValueError, "Ambiguous type"):
            conflict.resolve(identity("Implementation"), "Fixture.Root")

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


class ManagedFieldContractTests(unittest.TestCase):
    def setUp(self):
        import hashlib

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

        def named(name, module="Game", local=True):
            return {"kind": "named", "name": name, "scope": scope(module, local=local)}

        def typ(name, base=None, fields=(), generic=()):
            return {"name": name, "base_signature": base, "fields": list(fields), "generic_parameters": list(generic)}

        def field(name, signature, **flags):
            return {"name": name, "signature": signature, "is_static": False, "is_not_serialized": False} | flags

        self.named, self.field, self.typ = named, field, typ
        target = named("Fixture.Target")
        list_type = {"kind": "generic_instance", "definition": named("System.Collections.Generic.List`1", "mscorlib", False), "arguments": [target]}
        parameter = {"kind": "generic_parameter", "owner": "Type", "position": 0}
        generic = [{"name": "T", "position": 0}]
        rows = [
            assembly(
                "Game",
                references=["mscorlib"],
                types=[
                    typ("Fixture.Target"),
                    typ("Fixture.Child", target),
                    typ("Fixture.Other"),
                    typ("Fixture.Parent`1", fields=[field("target", parameter)], generic=generic),
                    typ(
                        "Fixture.Owner",
                        {"kind": "generic_instance", "definition": named("Fixture.Parent`1"), "arguments": [target]},
                        [
                            field("targets", {"kind": "array", "rank": 1, "element": target}),
                            field("children", list_type),
                            field("nested", named("Fixture.Outer/Nested")),
                            field("shared", target, is_static=True),
                            field("transient", target, is_not_serialized=True),
                        ],
                    ),
                    typ("Fixture.Outer/Nested", fields=[field("value", target)]),
                ],
            ),
            assembly("mscorlib", types=[typ("System.Collections.Generic.List`1", generic=generic)]),
        ]
        self.providers = {}
        for row in rows:
            path = self.root / row["module_name"]
            path.write_bytes(row["assembly"].encode())
            pin = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            row.update(pin)
            self.providers[row["module_name"]] = pin
        self.rows = rows
        self.resolver = universe(*rows)
        self.resolver.bind_current_providers(self.providers)
        self.owner = ["Game.dll", "Fixture", "Owner"]
        self.child = ["Game.dll", "Fixture", "Child"]

    def test_inherited_generic_array_list_and_nested_fields_accept_subclass(self):
        for path in [["target"], ["targets", "Array", "0"], ["children", "Array", "2"], ["nested", "value"]]:
            with self.subTest(path=path):
                proof = self.resolver.prove_field_endpoint(self.owner, path, self.child)
                self.assertEqual(proof["field_signature"]["name"], "Fixture.Target")
        self.assertEqual(self.resolver.registry(["Game.dll", "Fixture", "Outer+Nested"])["name"], "Fixture.Outer/Nested")

    def test_unrelated_scope_version_and_provider_hash_refuse(self):
        with self.assertRaisesRegex(ValueError, "not assignable"):
            self.resolver.prove_field_endpoint(self.owner, ["target"], ["Game.dll", "Fixture", "Other"])
        with self.assertRaisesRegex(ValueError, "module absent"):
            self.resolver.registry(["Absent.dll", "Fixture", "Child"])
        for signature in [self.named("Fixture.Target", "Game", False), self.named("Fixture.Target")]:
            signature["scope"]["assembly_identity"] = identity("Game", "2.0.0.0")
            with self.assertRaises(ValueError):
                self.resolver.scoped_signature(identity("Game"), signature)
        (self.root / "Game.dll").write_bytes(b"newer-build")
        with self.assertRaisesRegex(ValueError, "provider drift"):
            self.resolver.bind_current_providers(self.providers)
        wrong = copy.deepcopy(self.providers)
        wrong["Game.dll"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "path/hash differs"):
            self.resolver.bind_current_providers(wrong)

    def test_missing_static_transient_hidden_and_malformed_paths_refuse(self):
        for path in [["shared"], ["transient"], ["missing"], ["targets", "Array"], ["targets", "Array", "-1"], ["target", "Array", "0"]]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.resolver.field_type(self.owner, path)
        self.rows[0]["types"][4]["fields"].append(self.field("target", self.named("Fixture.Target")))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.resolver.field_type(self.owner, ["target"])

    def test_field_scope_forwarding_and_generic_base_context(self):
        facade = assembly("Facade", exports=[exported("Fixture.Target", "Game")], references=["Game"])
        self.resolver.assemblies[identity("Facade")] = facade
        self.resolver.exports[identity("Facade"), "Fixture.Target"] = facade["exported_types"][0]
        self.rows[0]["references"].append(identity("Facade"))
        self.rows[0]["types"][4]["fields"].append(self.field("forwarded", self.named("Fixture.Target", "Facade", False)))
        self.assertTrue(self.resolver.prove_field_endpoint(self.owner, ["forwarded"], self.child))
        # A second generic base substitutes the intermediate argument, not the child list.
        self.rows[0]["types"][4]["base_signature"] = {
            "kind": "generic_instance",
            "definition": self.named("Fixture.Middle`1"),
            "arguments": [self.named("Fixture.Target")],
        }
        middle = self.typ(
            "Fixture.Middle`1",
            {
                "kind": "generic_instance",
                "definition": self.named("Fixture.Parent`1"),
                "arguments": [{"kind": "array", "rank": 1, "element": {"kind": "generic_parameter", "owner": "Type", "position": 0}}],
            },
            generic=[{"name": "T", "position": 0}],
        )
        self.resolver.types[identity("Game"), middle["name"]] = middle
        self.assertTrue(self.resolver.prove_field_endpoint(self.owner, ["target", "Array", "0"], self.child))

    def test_serialized_fields_stop_at_bound_native_object_without_framework_alias(self):
        native_identity = identity("UnityEngine.CoreModule")
        framework = self.named("System.Object", "mscorlib", False)
        framework["scope"]["assembly_identity"] = identity("mscorlib", "2.0.0.0")
        native = assembly("UnityEngine.CoreModule", references=["mscorlib"])
        native["references"] = [identity("mscorlib", "2.0.0.0")]
        native["types"] = [self.typ("UnityEngine.Object", framework)]
        self.resolver.assemblies[native_identity] = native
        self.resolver.modules["UnityEngine.CoreModule.dll"] = native
        self.resolver.types[native_identity, "UnityEngine.Object"] = native["types"][0]
        parent = self.rows[0]["types"][3]
        parent["base_signature"] = self.named("UnityEngine.Object", "UnityEngine.CoreModule", False)
        self.rows[0]["references"].append(native_identity)
        self.assertTrue(self.resolver.prove_field_endpoint(self.owner, ["target"], self.child))
        with self.assertRaisesRegex(ValueError, "field absent"):
            self.resolver.field_type(self.owner, ["missing"])
        # Managed inheritance still requires the exact framework dependency.
        with self.assertRaisesRegex(ValueError, "Missing exact assembly"):
            list(self.resolver.hierarchy(self.resolver.registry(self.owner)))
        # A same-name type in the game assembly cannot create a native boundary.
        parent["base_signature"] = self.named("UnityEngine.Object")
        self.resolver.types[identity("Game"), "UnityEngine.Object"] = self.typ("UnityEngine.Object", framework)
        self.rows[0]["references"].append(identity("mscorlib", "2.0.0.0"))
        with self.assertRaisesRegex(ValueError, "Missing exact assembly"):
            self.resolver.field_type(self.owner, ["target"])
