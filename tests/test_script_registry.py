"""Synthetic CLR and native-transfer contracts for the source-only script registry."""

from collections import defaultdict
from contextlib import closing
import copy
import importlib.util
import gc
import io
import json
import weakref
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("registry_identity", ROOT / "scripts/lab/script_identity.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def field(name, code=8, public=True, **flags):
    values = dict(fdStatic=False, fdInitOnly=False, fdNotSerialized=False, fdPublic=public)
    values.update(flags)
    return N(Name=name, Signature=N(value=bytes((6, code))), Flags=N(**values))


def definition(name, fields=(), namespace="Fixture"):
    return N(
        TypeName=name,
        TypeNamespace=namespace,
        FieldList=[N(row=row, row_index=index) for index, row in enumerate(fields, 1)],
        MethodList=[],
        Extends=None,
        Flags=N(tdSerializable=True, tdAbstract=False),
    )


def reader():
    # A metadata-only fixture: dnfile parses production PE files, while these
    # tests isolate Unity's field policy from any compiler/SDK installation.
    with patch.dict(sys.modules, {"dnfile": N()}):
        result = S._RegistryTypes(Path("."), {}, lambda *args: None, None, {})
    result.attributes["Fixture.dll"] = defaultdict(set)
    return result


class ScriptRegistryTests(unittest.TestCase):
    def test_current_field_names_include_inherited_private_fields_and_old_names(self):
        base = definition("Parent", [field("inherited", public=False)])
        current = definition("Current", [field("renamed"), field("runtimeCache", public=False)])
        clr = reader()
        clr.attributes["Fixture.dll"]["Field", 1].add(("UnityEngine.Serialization", "FormerlySerializedAsAttribute", b"\x01\x00\x07oldName\x00\x00"))
        with (
            patch.object(clr, "load", return_value=N(net=N(mdtables=N(TypeDef=N(rows=[current]))))),
            patch.object(clr, "hierarchy", return_value=([("Fixture.dll", base), ("Fixture.dll", current)], True)),
        ):
            names = clr.declared_field_names("Current", "Fixture", "Fixture.dll")
        self.assertEqual(names, {"inherited", "renamed", "runtimeCache", "oldName"})
        clr.close()

    def test_stdlib_import_does_not_load_optional_clr_reader(self):
        program = "import importlib.util,sys; s=importlib.util.spec_from_file_location('x',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert 'dnfile' not in sys.modules"
        subprocess.run([sys.executable, "-c", program, str(ROOT / "scripts/lab/script_identity.py")], check=True)

    def test_round_trip_player_record_preserves_unicode_alignment_and_order(self):
        identity = ("Fixture.dll", "Lab.Épreuve", "Cläss")
        body = S._script_body(identity, bytes(range(16)), -20000)
        row = S._script_record(body)
        self.assertEqual((row["identity"], row["order"], row["properties"]), (identity, -20000, bytes(range(16))))
        self.assertEqual(len(body) % 4, 0)
        with self.assertRaisesRegex(ValueError, "body"):
            S._script_record(body + b"x")

    def test_source_namespace_ignores_comments_strings_and_tracks_nesting(self):
        text = '// namespace False { class Chosen {} }\nnamespace Outer { const string s="class Chosen {}"; namespace Inner { public class Chosen {} } }'
        self.assertEqual(S._source_namespace(text, "Chosen"), "Outer.Inner")
        self.assertEqual(S._source_namespace("public class Chosen {}", "Chosen"), "")

    def test_native_common_vocabulary_and_collection_alignment(self):
        self.assertEqual(S.COMMON[1070], "int3_storage")
        vector = ("type", "UnityEngine.CoreModule.dll", definition("Vector2Int", namespace="UnityEngine"))
        nodes = [
            S._node("int2_storage", "positions", -1),
            S._node("Array", "Array", -1, 2, 1),
            S._node("int", "size", 4, 3),
            S._node("int2_storage", "data", 8, 3, meta=0x200000),
            S._node("int", "x", 4, 4),
            S._node("int", "y", 4, 4),
        ]
        expected = copy.deepcopy(nodes)
        expected[0]["type"], expected[1]["meta"] = "vector", 0x4000
        self.assertEqual(S._native_collection(("array", vector), copy.deepcopy(nodes)), expected)
        list_type = ("type", "mscorlib.dll", definition("List`1", namespace="System.Collections.Generic"))
        self.assertEqual(S._native_collection(("generic", list_type, [vector]), copy.deepcopy(nodes)), expected)
        for value in (("array", ("primitive", 8)), ("array", ("type", "Fixture.dll", definition("Vector2Int")))):
            self.assertEqual(S._native_collection(value, copy.deepcopy(nodes)), nodes)

    def test_field_eligibility_inheritance_and_managed_reference_rejection(self):
        clr = reader()
        base = definition("Base", [field("inherited")])
        child = definition(
            "Child",
            [
                field("hidden", public=False),
                field("privateSerialized", public=False),
                field("constant", fdStatic=True),
                field("readonly", fdInitOnly=True),
                field("transient", fdNotSerialized=True),
                field("visible", code=2),
            ],
        )
        # Fixture field row indices are local to this synthetic type table.
        clr.attributes["Fixture.dll"]["Field", 2].add(("UnityEngine", "SerializeField"))
        nodes = clr.custom_fields([("Fixture.dll", base), ("Fixture.dll", child)])
        self.assertEqual([node["name"] for node in nodes], ["inherited", "privateSerialized", "visible"])
        self.assertEqual(nodes[-1]["meta"], 0x4000)
        clr.attributes["Fixture.dll"]["Field", 2] = {("UnityEngine", "SerializeReference")}
        with self.assertRaisesRegex(ValueError, "managed-reference"):
            clr.custom_fields([("Fixture.dll", child)])

    def test_closed_generic_field_binding_and_unsupported_system_fields(self):
        clr = reader()
        row = definition("Holder`1", [field("item", code=19)])
        row.FieldList[0].row.Signature.value += b"\0"
        clr.bindings["Fixture.dll", id(row)] = [("primitive", 8)]
        self.assertEqual(clr.custom_fields([("Fixture.dll", row)]), [S._node("int", "item", 4)])
        clr.bindings.clear()
        with self.assertRaisesRegex(ValueError, "unbound"):
            clr.custom_fields([("Fixture.dll", row)])
        system_type = ("type", "mscorlib.dll", definition("Dictionary`2", namespace="System.Collections.Generic"))
        self.assertIsNone(clr.emit(("generic", system_type, [("primitive", 8), ("primitive", 8)]), "map"))

    def test_clr_array_and_custom_list_roots_are_distinct(self):
        clr = reader()
        self.assertEqual(clr.emit(("array", ("primitive", 8)), "numbers")[0]["type"], "vector")
        custom = ("type", "Fixture.dll", definition("Pair"))
        clr.templates[clr.key(custom)] = [S._node("Pair", "data", 8), S._node("int", "x", 4, 2), S._node("int", "y", 4, 2)]
        list_type = ("type", "mscorlib.dll", definition("List`1", namespace="System.Collections.Generic"))
        nodes = clr.emit(("generic", list_type, [custom]), "pairs")
        self.assertEqual(nodes[0]["type"], "Pair")
        self.assertEqual(nodes[3]["level"], 3)
        self.assertEqual(nodes[3]["size"], 8)
        self.assertEqual(nodes[1]["meta"], 0)

    def test_sdk_subtree_decode_skips_unknown_unrelated_common_labels(self):
        nodes = [S._node("Root", "Base", -1, 0), S._node("Unknown", "ignored", 4), S._node("AnimationCurve", "curve", -1), S._node("int", "tangentMode", 4, 2)]
        blob = bytearray(S._tree(nodes))
        struct.pack_into("<I", blob, 8 + 32 + 4, 0x8000FFFF)
        result = S._native_subtrees(blob, "AnimationCurve")
        self.assertEqual(len(result), 1)
        self.assertEqual([node["name"] for node in result[0]], ["curve", "tangentMode"])
        self.assertEqual([node["level"] for node in result[0]], [1, 2])
        with self.assertRaisesRegex(ValueError, "common string"):
            S.tree_nodes(blob)

    def test_registry_requires_explicit_authored_identity_before_any_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = {"authored": {"runtime_sources": ["Fixture.cs"], "guids": {}}}
            with self.assertRaisesRegex(ValueError, "explicit authored"):
                S.registry(root, root, root, root, root, root, profile, None)

    def test_current_metadata_owner_closes_on_success_and_failure(self):
        for fail in (False, True):
            clr, closed = reader(), []
            clr.loaded["Fixture.dll"] = N(close=lambda: closed.append("Fixture.dll"))
            clr.bindings["Fixture.dll", 1] = [("primitive", 8)]
            clr.active.append(("primitive", 8))
            clr.templates["fixture"] = [S._node("int", "field", 4)]
            try:
                with closing(clr):
                    if fail:
                        raise ValueError("source schema rejection fixture")
            except ValueError:
                self.assertTrue(fail)
            self.assertEqual(closed, ["Fixture.dll"])
            self.assertTrue(all(not value for value in (clr.loaded, clr.attributes, clr.bindings, clr.active, clr.templates)))

    def test_acquired_pe_is_owned_before_clr_validation(self):
        for net in (None, N(mdtables=N(TypeDef=None))):
            with self.subTest(net=net):
                closed = []
                pe = N(net=net, close=lambda: closed.append(True))
                with patch.dict(sys.modules, {"dnfile": N(dnPE=lambda *args, **kwargs: pe)}):
                    clr = S._RegistryTypes(Path("."), {}, lambda *args: None, None, {})
                    with self.assertRaisesRegex(ValueError, "no CLR types"), closing(clr):
                        clr.load("Rejected.dll")
                self.assertEqual(closed, [True])
                self.assertEqual(clr.loaded, {})

    def test_registry_releases_sdk_and_witness_containers_before_clr_discovery(self):
        class Tracked(dict):
            pass

        class DiscoveryReached(Exception):
            pass

        refs = []

        def tracked(**values):
            value = Tracked(values)
            refs.append(weakref.ref(value))
            return value

        def member(*args):
            stream = io.BytesIO()
            refs.append(weakref.ref(stream))
            return stream

        def read_serialized(stream):
            name = Path(stream.name).name if hasattr(stream, "name") else "witness"
            if name == "startup":
                return {"objects": []}
            if name == "sdk":
                native = tracked(class_id=114, tree=b"authored native schema")
                unrelated = tracked(class_id=1)
                row = tracked(path_id=7, type_id=0)
                return tracked(engine="authored engine", objects=[row], types=[native, unrelated])
            return tracked(objects=[], types=[])

        def discovery(*args):
            gc.collect()
            self.assertEqual(len(refs), 12)  # SDK plus two passes over two witnesses.
            self.assertTrue(all(ref() is None for ref in refs))
            raise DiscoveryReached

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name in ("startup", "sdk", "first", "second"):
                (root / name).write_bytes(b"authored fixture")
            (root / "gameplay").mkdir()
            (root / "result.json").write_text(json.dumps({"success": True, "phase": "managed-produced", "source_commit": "authored"}))
            (root / "providers.json").write_text("{}")
            (root / "gameplay/inputs.json").write_text('{"sources": {}}')
            (root / "input-hashes.json").write_text("{}")
            profile = {
                "authored": {"runtime_sources": [], "guids": {}, "source_commit": "authored", "source_files": {}},
                "source": {"path": "startup"},
                "script_properties_sdk": {"path_id": 7},
                "schema_witnesses": [{"path": name, "member": name, "types": []} for name in ("first", "second")],
            }
            writer = N(read_serialized=read_serialized, B=N(Bundle=lambda path: N(member=member)))
            with (
                patch.object(S, "_native_subtrees", return_value=[[S._node("int", "tangentMode", 4)]]),
                patch.object(S, "_original_membership", side_effect=discovery),
            ):
                with self.assertRaises(DiscoveryReached):
                    S.registry(root, root / "sdk", root, root, root, root / "input-hashes.json", profile, writer)

    def test_original_membership_discards_parser_ownership_after_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            managed = Path(directory)
            for name in ("Fixture.dll", "UnityEngine.CoreModule.dll"):
                (managed / name).write_bytes(b"authored metadata fixture")
            scope = N(table=N(name="AssemblyRef"), row=N(Name="UnityEngine.CoreModule"))
            reference = N(TypeName="MonoBehaviour", TypeNamespace="UnityEngine", ResolutionScope=scope)
            rows = [definition("Component"), definition("Nested"), definition("Ordinary")]
            for row in rows[:2]:
                row.Extends = N(table=N(name="TypeRef"), row_index=1, row=reference)
            loaded, closed = [], []

            def parse(path, **kwargs):
                self.assertIs(kwargs.get("clr_lazy_load"), True)
                name = Path(path).name
                loaded.append(name)
                table = (
                    [raw_typedef("Component", parent=5), raw_typedef("Nested", parent=5), raw_typedef("Ordinary")]
                    if name == "Fixture.dll"
                    else [raw_typedef("MonoBehaviour", "UnityEngine")]
                )
                metadata = raw_tables(
                    TypeDef=table,
                    TypeRef=[raw_ref("MonoBehaviour")],
                    AssemblyRef=[N(Name="UnityEngine.CoreModule")],
                    NestedClass=[Raw(struct=N(NestedClass_Index=2))] if name == "Fixture.dll" else [],
                )
                return N(net=N(mdtables=metadata), close=lambda: closed.append(name))

            scripts = [{"identity": ("Fixture.dll", "Fixture", "Component")}]
            with patch.dict(sys.modules, {"dnfile": N(dnPE=parse, codedindex=metadata_coded)}):
                result = S._original_membership(managed, scripts, set(), lambda *args: None)
            self.assertEqual(result, [("Fixture.dll", "Fixture", "Component")])
            self.assertCountEqual(loaded, closed)
            self.assertEqual(len(closed), 2)
            self.assertTrue(all(isinstance(value, str) for identity in result for value in identity))

            # A failed dependency admission releases the already loaded PE too.
            closed.clear()

            def pin(path, *args):
                if Path(path).name != "Fixture.dll":
                    raise ValueError("authored provider drift fixture")

            with patch.dict(sys.modules, {"dnfile": N(dnPE=parse, codedindex=metadata_coded)}), self.assertRaisesRegex(ValueError, "provider drift"):
                S._original_membership(managed, scripts, set(), pin)
            self.assertEqual(closed, ["Fixture.dll"])


# Only tag names used by these authored CLR fixtures are needed here.
metadata_coded = N(
    ResolutionScope=N(tag_bits=2, table_names=["Module", "ModuleRef", "AssemblyRef", "TypeRef"]),
    TypeDefOrRef=N(tag_bits=2, table_names=["TypeDef", "TypeRef", "TypeSpec"]),
    HasCustomAttribute=N(tag_bits=5, table_names=["MethodDef", "Field"]),
    CustomAttributeType=N(tag_bits=3, table_names=[None, None, "MethodDef", "MemberRef"]),
    MemberRefParent=N(tag_bits=3, table_names=["TypeDef", "TypeRef", "ModuleRef", "MethodDef", "TypeSpec"]),
    Implementation=N(tag_bits=2, table_names=["File", "AssemblyRef", "ExportedType"]),
)


class Raw:
    def __init__(self, **values):
        self.__dict__.update(values)

    def __getattr__(self, name):
        raise AssertionError("cross-table loader access: " + name)


def raw_flags(**values):
    return N(tdAbstract=False, tdSerializable=True, tdForwarder=False, **values)


def raw_typedef(name, namespace="Fixture", start=1, method=1, parent=0):
    return Raw(TypeName=name, TypeNamespace=namespace, Flags=raw_flags(), struct=N(FieldList_Index=start, MethodList_Index=method, Extends_CodedIndex=parent))


def raw_field(name, signature, public=True, readonly=False):
    return Raw(Name=name, Signature=N(value=signature), Flags=N(fdPublic=public, fdStatic=False, fdInitOnly=readonly, fdNotSerialized=False))


def raw_ref(name, namespace="UnityEngine", assembly=1):
    return Raw(TypeName=name, TypeNamespace=namespace, struct=N(ResolutionScope_CodedIndex=(assembly << 2) | 2))


def raw_tables(**values):
    names = ("TypeDef", "TypeRef", "TypeSpec", "AssemblyRef", "Field", "MemberRef", "CustomAttribute", "ExportedType", "NestedClass")
    return N(**{name: N(rows=values[name]) if values.get(name) else None for name in names})


def raw_sources():
    defs = [
        raw_typedef("SerializeField", "UnityEngine", method=1),
        raw_typedef("Base", start=1, method=2, parent=5),
        raw_typedef("Derived", start=3, method=3, parent=8),
        raw_typedef("Holder`1", start=4, method=3, parent=5),
        raw_typedef("Closed", start=5, method=3, parent=6),
    ]
    fixture = raw_tables(
        TypeDef=defs,
        TypeRef=[raw_ref("MonoBehaviour"), raw_ref("SerializeField"), raw_ref("SerializeReference"), raw_ref("Forwarded", "FixtureLib", 2)],
        AssemblyRef=[N(Name="Core"), N(Name="Facade")],
        Field=[
            raw_field("baseValue", b"\x06\x08"),
            raw_field("privateValue", b"\x06\x08", False),
            raw_field("readonly", b"\x06\x08", readonly=True),
            raw_field("item", b"\x06\x13\x00"),
        ],
        TypeSpec=[N(Signature=N(value=b"\x15\x12\x10\x01\x08"))],
        MemberRef=[Raw(struct=N(Class_CodedIndex=17))],
        CustomAttribute=[Raw(struct=N(Parent_CodedIndex=65, Type_CodedIndex=10)), Raw(struct=N(Parent_CodedIndex=65, Type_CodedIndex=11))],
        NestedClass=[Raw(struct=N(NestedClass_Index=3))],
    )
    core = raw_tables(TypeDef=[raw_typedef("MonoBehaviour", "UnityEngine"), raw_typedef("Forwarded", "FixtureLib")])
    facade = raw_tables(
        TypeDef=[raw_typedef("<Module>")],
        AssemblyRef=[N(Name="Core")],
        ExportedType=[Raw(TypeName="Forwarded", TypeNamespace="FixtureLib", Flags=N(tdForwarder=True), struct=N(Implementation_CodedIndex=5))],
    )
    return {"Fixture.dll": fixture, "Core.dll": core, "Facade.dll": facade}


class CompactMetadataTests(unittest.TestCase):
    def owner(self, source=None):
        source = source or raw_sources()
        self.closed = []

        def parse(path, **kwargs):
            self.assertEqual(kwargs, {"clr_lazy_load": True})
            name = Path(path).name
            return N(net=N(mdtables=source[name]), close=lambda: self.closed.append(name))

        self.patch = patch.dict(sys.modules, {"dnfile": N(dnPE=parse, codedindex=metadata_coded)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        owner = S._RegistryTypes(Path("."), {}, lambda *a: None, None, {})
        self.addCleanup(owner.close)
        return owner

    def test_projection_never_requests_cross_table_loader_and_closes_pe(self):
        owner = self.owner()
        pe = owner.load("Fixture.dll")
        self.assertEqual(self.closed, ["Fixture.dll"])
        self.assertEqual(len(pe.net.mdtables.TypeDef.rows), 5)
        self.assertEqual(pe.net.mdtables.NestedClass.rows[0].NestedClass.row_index, 3)
        owner.close()
        self.assertEqual(self.closed, ["Fixture.dll"])

    def test_methoddef_and_memberref_attributes_are_independently_resolved(self):
        for encoding in (10, 11):
            with self.subTest(encoding=encoding):
                source = raw_sources()
                source["Fixture.dll"].CustomAttribute.rows = [Raw(struct=N(Parent_CodedIndex=65, Type_CodedIndex=encoding))]
                owner = self.owner(source)
                owner.load("Fixture.dll")
                self.assertEqual(owner.attributes["Fixture.dll"]["Field", 2], {("UnityEngine", "SerializeField")})

    def test_projected_facts_retain_no_raw_rows_and_own_their_values(self):
        source = raw_sources()
        owner = self.owner(source)
        pe = owner.load("Fixture.dll")
        visited = set()

        def visit(value):
            if id(value) in visited:
                return
            visited.add(id(value))
            self.assertNotIsInstance(value, Raw)
            if isinstance(value, N):
                for child in vars(value).values():
                    visit(child)
            elif isinstance(value, (tuple, list, set)):
                for child in value:
                    visit(child)
            elif isinstance(value, dict):
                for child in value.values():
                    visit(child)

        visit(pe)
        visit(owner.attributes)
        source["Fixture.dll"].Field.rows[0].Signature.value = b"changed source after release"
        source["Fixture.dll"].Field.rows[0].Flags.fdPublic = False
        projected = pe.net.mdtables.TypeDef.rows[1].FieldList[0].row
        self.assertEqual(projected.Signature.value, b"\x06\x08")
        self.assertTrue(projected.Flags.fdPublic)

    def test_inherited_private_serialized_fields_and_readonly_filter(self):
        owner = self.owner()
        row = owner.load("Fixture.dll").net.mdtables.TypeDef.rows[2]
        hierarchy, is_object = owner.hierarchy("Fixture.dll", row)
        self.assertTrue(is_object)
        self.assertEqual([n["name"] for n in owner.custom_fields(hierarchy)], ["baseValue", "privateValue"])

    def test_closed_generic_parent_substitutes_actual_field_signature(self):
        owner = self.owner()
        row = owner.load("Fixture.dll").net.mdtables.TypeDef.rows[4]
        hierarchy, is_object = owner.hierarchy("Fixture.dll", row)
        self.assertTrue(is_object)
        self.assertEqual(owner.custom_fields(hierarchy), [S._node("int", "item", 4)])

    def test_exported_forwarder_resolves_without_raw_row_retention(self):
        owner = self.owner()
        refrow = owner.load("Fixture.dll").net.mdtables.TypeRef.rows[3]
        assembly, row = owner.resolve("Fixture.dll", "TypeRef", refrow)
        self.assertEqual((assembly, S._type_name(row)), ("Core.dll", ("FixtureLib", "Forwarded")))
        self.assertCountEqual(self.closed, ["Fixture.dll", "Facade.dll", "Core.dll"])

    def test_serialize_reference_still_rejects_unsupported_transfer(self):
        source = raw_sources()
        source["Fixture.dll"].MemberRef.rows[0].struct.Class_CodedIndex = 25
        source["Fixture.dll"].CustomAttribute.rows = [Raw(struct=N(Parent_CodedIndex=65, Type_CodedIndex=11))]
        owner = self.owner(source)
        row = owner.load("Fixture.dll").net.mdtables.TypeDef.rows[1]
        hierarchy, _ = owner.hierarchy("Fixture.dll", row)
        with self.assertRaisesRegex(ValueError, "managed-reference"):
            owner.custom_fields(hierarchy)

    def test_validation_and_projection_failure_close_acquired_pe(self):
        for net in (None, N(mdtables=N(TypeDef=None)), N(mdtables=N(TypeDef=N(rows=[Raw()])))):
            closed = []
            with patch.dict(sys.modules, {"dnfile": N(dnPE=lambda *a, **k: N(net=net, close=lambda: closed.append(True)), codedindex=metadata_coded)}):
                owner = S._RegistryTypes(Path("."), {}, lambda *a: None, None, {})
                with self.assertRaises((ValueError, AssertionError, AttributeError)):
                    owner.load("Rejected.dll")
                owner.close()
            self.assertEqual(closed, [True])
            self.assertEqual(owner.loaded, {})


if __name__ == "__main__":
    unittest.main()
