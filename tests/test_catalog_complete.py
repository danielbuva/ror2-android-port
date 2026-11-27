"""Final produced-container checks are independent of profile declarations."""

import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools/phone-build/accepted-output" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


C = module("catalog_completion_test", "catalog_complete.py")
M = module("catalog_manifest_fixture", "bundle_manifest.py")


def registry_bytes():
    output = io.BytesIO()
    C.W.write_serialized(
        output, dict(engine="2021.3.45f2", platform=13, trees=False, types=[], objects=[], scripts=[], externals=[], ref_types=[], user=""), lambda row: None
    )
    return output.getvalue()


def pin(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=C.W.B.sha(path))


class CatalogCompletionTests(unittest.TestCase):
    def test_physics_route_follows_asset_and_ordered_siblings_across_new_ids(self):
        dependencies = {name: module("physics_" + name, name + ".py") for name in ("manager_graph", "manager_settings", "player_ui")}
        with patch.dict(sys.modules, dependencies):
            physics = module("physics_routes", "catalog_physics.py")
        index = physics.PhysicsObjects.__new__(physics.PhysicsObjects)

        def pointer(pid=0):
            return dict(m_FileID=0, m_PathID=pid)

        def routes(member, base):
            root, first, second = [(member, base + i) for i in range(3)]
            index.catalog = SimpleNamespace(endpoint=lambda member, ptr: (member, ptr[1]) if ptr[1] else None)
            objects = {root: {"m_Name": "Prefab"}, first: {"m_Name": "Collider"}, second: {"m_Name": "Collider"}}
            transforms = {
                (member, base + 10): dict(m_GameObject=pointer(base), m_Father=pointer(), m_Children=[pointer(base + 12), pointer(base + 11)]),
                (member, base + 11): dict(m_GameObject=pointer(first[1]), m_Father=pointer(base + 10)),
                (member, base + 12): dict(m_GameObject=pointer(second[1]), m_Father=pointer(base + 10)),
            }
            indexed = index.game_object_routes(objects, transforms, {root: ["asset.prefab"]})
            return indexed[root], indexed[first], indexed[second]

        root, first, second = routes("original", 1)
        self.assertEqual((root, first, second), routes("rebuilt", 100))
        self.assertEqual(first, root + (("Collider", 2),))
        self.assertEqual(second, root + (("Collider", 1),))

    def test_objective_slot_uses_ordered_indices_and_confirmed_hierarchy(self):
        mesh = module("objective_slot_mesh", "unity_mesh.py")
        records = module("objective_slot_records", "record_produce.py")
        with patch.dict(sys.modules, catalog_complete=C, unity_mesh=mesh):
            compare = module("objective_slot_catalog", "catalog_compare.py")
        with patch.dict(sys.modules, catalog_compare=compare, record_produce=records):
            slots = module("objective_slot_test", "objective_slots.py")

        catalog = compare.Catalog.__new__(compare.Catalog)
        layout = {"externals": [], "types": [{"class_id": 4}, {"class_id": 114}]}
        catalog.members = {"prefab": (None, layout, {pid: {"type_id": typ, "path_id": pid} for pid, typ in [(1, 0), (2, 0), (3, 0), (4, 0), (5, 1)]})}
        catalog.names = {"prefab": "bundle"}
        prefabs = slots.ObjectivePrefabs.__new__(slots.ObjectivePrefabs)
        prefabs.catalog = catalog
        prefabs.assets = {"model.prefab": {("prefab", 1)}}
        prefabs.bundle_names = {"bundle": "runtime-name"}
        refs = {
            1: {("m_Component", "Array", 0, "component"): (0, 2)},
            2: {("m_Children", "Array", 1): (0, 3)},
            3: {("#374",): (0, 4)},
            4: {("m_Component", "Array", 0, "component"): (0, 3), ("m_Component", "Array", 1, "component"): (0, 5)},
        }

        def field_rows(_, endpoint):
            pid = endpoint[1]
            name = b"Root" if pid == 1 else b"Leaf"
            return 1, struct.pack("<I", 4) + name, None, refs[pid]

        failure = dict(asset="Model.prefab", route="1", hierarchy="Root/Leaf", componentCount=2, slot=1)
        with (
            patch.object(slots, "fields", side_effect=field_rows),
            patch.object(records, "fields", return_value=(None, {("m_Name",): (0, 8)})),
            patch.object(catalog, "record", return_value=("prefab", {"class_id": 114}, bytes(32))),
        ):
            result = prefabs.slot(failure, [])
            self.assertEqual(result["component"], dict(file_id=0, path_id=5, member="prefab", expected_bundle="runtime-name", bundle_loaded=False))
            self.assertIsNone(result["script"])
            with self.assertRaisesRegex(ValueError, "hierarchy or slots differ"):
                prefabs.slot(dict(failure, componentCount=3), [])
            with self.assertRaisesRegex(ValueError, "sibling index absent"):
                prefabs.slot(dict(failure, route="0"), [])

    def test_differential_retains_array_indices_and_resolves_file_ids_per_member(self):
        mesh = module("catalog_comparison_mesh", "unity_mesh.py")
        with patch.dict(sys.modules, catalog_complete=C, unity_mesh=mesh):
            compare = module("catalog_comparison_test", "catalog_compare.py")

        array = mesh.Node(0, 1, "Array", "Array", -1, 0)
        count = mesh.Node(1, 0, "int", "size", 4, 0)
        element = mesh.Node(1, 0, "PPtr<Component>", "data", 12, 0)
        element.children = [mesh.Node(2, 0, "int", "m_FileID", 4, 0), mesh.Node(2, 0, "SInt64", "m_PathID", 8, 0)]
        array.children = [count, element]
        with patch.object(mesh, "type_tree", return_value=array):
            root, _ = compare.schema(b"fixture")
        body = struct.pack("<Iiqiq", 2, 1, 7, 0, 8)
        self.assertEqual(compare.pointers(body, root), {(0,): (1, 7), (1,): (0, 8)})
        with self.assertRaisesRegex(ValueError, "incomplete serialized object"):
            compare.pointers(body + bytes(4), root)

        child = mesh.Node(1, 0, "string", "childName", -1, 0)
        child.children = [mesh.Node(2, 1, "Array", "Array", -1, 0x4000)]
        child.children[0].children = [mesh.Node(3, 0, "int", "size", 4, 0), mesh.Node(3, 0, "char", "data", 1, 0)]
        record = mesh.Node(0, 0, "ItemDisplayRule", "Base", -1, 0)
        rule_type = mesh.Node(1, 0, "int", "ruleType", 4, 0)
        angles = mesh.Node(1, 0, "Vector3f", "localAngles", 12, 0)
        angles.children = [mesh.Node(2, 0, "float", name, 4, 0) for name in ("x", "y", "z")]
        record.children = [child, element, rule_type, angles]
        with patch.object(mesh, "type_tree", return_value=record):
            root, _ = compare.schema(b"display-field-fixture")
        display = {}
        transform = struct.pack("<3f", 0, 90, 180)
        self.assertEqual(compare.pointers(struct.pack("<I3sxiqi", 3, b"Gun", 1, 7, 1) + transform, root, display), {("data",): (1, 7)})
        self.assertEqual(display, {("childName",): "Gun", ("ruleType",): "01000000", ("localAngles",): transform.hex()})

        failures = [dict(check="child", rule=0, follower=None, address="child-only"), dict(check="follower", rule=0, address="follower")]
        failures.extend([dict(rule=0, follower=None, address="legacy"), dict(rule=0, follower="loaded", address="legacy-child")])
        self.assertEqual(compare.missing_display_addresses(dict(failures=failures)), {"follower", "legacy"})
        with self.assertRaisesRegex(ValueError, "has no address"):
            compare.missing_display_addresses(dict(failures=[dict(check="follower", address=None)]))

        catalog = compare.Catalog.__new__(compare.Catalog)
        catalog.members = {"base": (None, {"externals": [{"path": "archive:/other/CAB"}]}, {8: {}}), "CAB": (None, {}, {7: {}})}
        self.assertEqual(catalog.endpoint("base", (1, 7)), ("CAB", 7))
        self.assertEqual(catalog.endpoint("base", (1, 8)), ("missing-target", "CAB", 8))
        self.assertIsNone(catalog.endpoint("base", (0, 0)))

    def test_differential_joins_identity_only_for_matching_candidate_catalog(self):
        mesh = module("catalog_identity_mesh", "unity_mesh.py")
        with patch.dict(sys.modules, catalog_complete=C, unity_mesh=mesh):
            compare = module("catalog_identity_comparison", "catalog_compare.py")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = root / "catalog.json"
            metadata.write_text("{}")
            apk, receipt = root / "candidate.apk", root / "typed.json"
            with ZipFile(apk, "w") as archive:
                archive.write(metadata, "assets/owner-bootstrap/data/whole-catalog.json")
            evidence = dict(complete=True, bodies=2, masters=1, metadataSha256=pin(metadata)["sha256"], bundles={"fixture": "digest"}, failures=[])
            receipt.write_text(json.dumps(dict(masterBodyIdentity=evidence)))
            request = dict(bundles={"fixture": dict(sha256="digest")})
            self.assertEqual(compare.typed_catalog_identity(receipt, request, apk), (evidence, None, None))
            with self.assertRaisesRegex(ValueError, "bundle pins differ"):
                compare.typed_catalog_identity(receipt, dict(bundles={}), apk)
            definitions = dict(sourceMetadataSha256="original")
            displays = dict(complete=True, bodies=[dict(path="body", groups=1)], prefabs=1, failures=[])
            receipt.write_text(json.dumps(dict(masterBodyIdentity=evidence, definitionIdentity=definitions, displayIdentity=displays)))
            with self.assertRaisesRegex(ValueError, "definition source metadata differs"):
                compare.typed_catalog_identity(receipt, request, apk)
            request["source_additions"] = dict(metadata=dict(sha256="original"))
            self.assertEqual(compare.typed_catalog_identity(receipt, request, apk), (evidence, definitions, displays))
            receipt.write_text(json.dumps(dict(masterBodyIdentity=dict(evidence, metadataSha256="wrong"))))
            with self.assertRaisesRegex(ValueError, "metadata differs"):
                compare.typed_catalog_identity(receipt, request, apk)

    def test_player_binding_uses_image_identity_and_serialized_script_table(self):
        def text(value):
            raw = struct.pack("<I", len(value)) + value.encode()
            return raw + bytes(-len(raw) % 4)

        identity = ("Behaviour", "Package", "Plugin.dll")
        strings = b"Plugin.dll\0Behaviour\0Package\0"
        metadata = bytearray(176)
        struct.pack_into("<II", metadata, 0, 0xFAB11BAF, 31)
        struct.pack_into("<II", metadata, 24, len(metadata), len(strings))
        metadata.extend(strings)
        struct.pack_into("<II", metadata, 160, len(metadata), 88)
        metadata.extend(struct.pack("<ii", 11, 21) + bytes(80))
        struct.pack_into("<II", metadata, 168, len(metadata), 40)
        metadata.extend(struct.pack("<iiii", 0, 0, 0, 1) + bytes(24))
        self.assertEqual(C.il2cpp_type_identities(metadata), {identity})
        with self.assertRaisesRegex(ValueError, "invalid Android IL2CPP metadata table"):
            C.il2cpp_type_identities(metadata[:-1])

        members = C.ProducedMembers()
        component = struct.pack("<iqIiq", 0, 1, 1, 1, 3)
        definition = struct.pack("<iqIiq", 0, 0, 1, 1, 3)
        script = text(identity[0]) + bytes(20) + b"".join(map(text, identity))
        typ = dict(class_id=114, script_type=0, script_id=C.S.md4("".join(identity).encode()))
        layout = dict(data_offset=0, types=[typ], externals=[dict(path="CAB-plugin")], scripts=[(1, 3)])
        members.members["CAB-prefab"] = (
            io.BytesIO(component + definition),
            layout,
            {2: dict(type_id=0, offset=0, bytes=len(component)), 4: dict(type_id=0, offset=len(component), bytes=len(definition))},
        )
        members.members["CAB-plugin"] = (io.BytesIO(script), dict(data_offset=0, types=[dict(class_id=115)]), {3: dict(type_id=0, offset=0, bytes=len(script))})
        self.assertEqual(
            C.prefab_script_bindings(members, {identity}), dict(behaviours=1, ownerless=1, scriptless=[], ownerless_scriptless=[], types=1, failures=[])
        )
        absent = C.prefab_script_bindings(members, {("Behaviour", "Package", "Other.dll")})
        self.assertEqual(
            [(row["path_id"], row["identity"], row["error"]) for row in absent["failures"]],
            [
                (2, identity, "type absent from Android player image"),
                (4, identity, "type absent from Android player image"),
            ],
        )
        layout["scripts"] = [(1, 4)]
        mismatched = C.prefab_script_bindings(members, {identity})
        self.assertEqual([row["error"] for row in mismatched["failures"]], ["serialized script table disagrees with m_Script"] * 2)

    def test_model_skin_slots_follow_actual_external_scripts_and_reject_nulls(self):
        def text(value):
            raw = struct.pack("<I", len(value)) + value.encode()
            return raw + bytes(-len(raw) % 4)

        controller = ("ModelSkinController", "RoR2", "RoR2.dll")
        skin = ("SkinDef", "RoR2", "RoR2.dll")

        def typ(identity, slots=False):
            fields = [
                ("MonoBehaviour", "Base", -1, 0),
                ("PPtr<GameObject>", "m_GameObject", 12, 1),
                ("int", "m_FileID", 4, 2),
                ("SInt64", "m_PathID", 8, 2),
                ("int", "m_Enabled", 4, 1),
                ("PPtr<MonoScript>", "m_Script", 12, 1),
                ("int", "m_FileID", 4, 2),
                ("SInt64", "m_PathID", 8, 2),
            ]
            if slots:
                fields += [
                    ("vector", "skins", -1, 1),
                    ("Array", "Array", -1, 2),
                    ("int", "size", 4, 3),
                    ("PPtr<SkinDef>", "data", 12, 3),
                    ("int", "m_FileID", 4, 4),
                    ("SInt64", "m_PathID", 8, 4),
                ]
            return dict(
                class_id=114,
                script_id=C.S.md4("".join(identity).encode()),
                tree=M.S._tree([dict(type=t, name=n, size=s, level=level, meta=0, flags=int(t == "Array"), version=1) for t, n, s, level in fields]),
            )

        def add(members, name, rows, externals=()):
            body, types, objects = b"", [], {}
            for path_id, native, raw in rows:
                objects[path_id] = dict(path_id=path_id, type_id=len(types), offset=len(body), bytes=len(raw))
                types.append(native)
                body += raw
            members.members[name] = (io.BytesIO(body), dict(data_offset=0, types=types, externals=[dict(path=x) for x in externals]), objects)

        for failure in (None, "null", "absent", "wrong-type", "wrong-script", "unregistered"):
            with self.subTest(failure=failure):
                members = C.ProducedMembers()
                pointer = (0, 0) if failure == "null" else (1, 999 if failure == "absent" else 20)
                body = bytes(16) + struct.pack("<iqIiq", 0, 7, 1, *pointer)
                script = lambda identity: text(identity[0]) + bytes(20) + b"".join(text(value) for value in identity)
                add(members, "CAB-body", [(10, typ(controller, slots=True), body), (7, dict(class_id=115), script(controller))], ["CAB-skins"])
                target_type = dict(class_id=1) if failure == "wrong-type" else typ(skin)
                binding = controller if failure == "wrong-script" else skin
                add(members, "CAB-skins", [(20, target_type, bytes(16) + struct.pack("<iq", 0, 8)), (8, dict(class_id=115), script(binding))])
                runtime = {controller} if failure == "unregistered" else {controller, skin}
                if failure:
                    with self.assertRaisesRegex(ValueError, "unresolved model skin slot.*CAB-body:10 skins.Array.0"):
                        C.validate_model_skins(members, runtime)
                else:
                    targets = {}
                    self.assertEqual(C.validate_model_skins(members, runtime, targets), dict(model_skin_controllers=1, model_skin_slots=1))
                    self.assertEqual(targets, {("CAB-body", 10): {"0": ("CAB-skins", 20)}})

    def test_deferred_references_preserve_subobjects_and_plain_preloads(self):
        guid = "1234567890abcdef1234567890abcdef"
        tree = {
            "skins": [
                {
                    "skinDefParamsAddress": {
                        "m_AssetGUID": guid,
                        "m_SubObjectName": "mesh",
                        "m_SubObjectType": "UnityEngine.Mesh, UnityEngine.CoreModule",
                        "m_SubObjectGUID": guid,
                    }
                }
            ],
            "preloadGUIDReferences": [guid],
            "effect": {"assetGUID": guid},
            "state": {"stringValue": guid + "[avatar]"},
            "m_Script": {"m_FileID": 0, "m_PathID": 123},
            "description": "text containing " + guid,
            "empty": {"m_AssetGUID": ""},
        }
        edges = list(C.deferred_references(tree))
        self.assertEqual([row["key"] for row in edges], [guid + "[mesh]", guid, guid, guid + "[avatar]"])
        self.assertEqual(edges[0]["field"], ["skins", 0, "skinDefParamsAddress"])
        self.assertEqual(edges[0]["kind"], "AssetReference")
        self.assertEqual(edges[0]["subobject_name"], "mesh")
        self.assertEqual(edges[0]["subobject_type"], "UnityEngine.Mesh, UnityEngine.CoreModule")
        self.assertEqual(edges[1]["field"], ["preloadGUIDReferences", 0])

    def test_deferred_subobject_type_filters_siblings_without_dropping_assembly(self):
        mesh = dict(id=1, type="UnityEngine.Mesh, UnityEngine.CoreModule, Version=0.0.0.0")
        other_assembly = dict(id=2, type="UnityEngine.Mesh, OtherAssembly")
        avatar = dict(id=3, type="UnityEngine.Avatar, UnityEngine.AnimationModule")
        candidates = [avatar, other_assembly, mesh]
        edge = dict(subobject_type="UnityEngine.Mesh, UnityEngine.CoreModule")
        self.assertEqual(C.deferred_reference_locations(edge, candidates), [mesh])
        self.assertEqual(C.deferred_reference_locations({}, candidates), candidates)
        self.assertEqual(C.deferred_reference_locations(dict(subobject_type="Absent, Assembly"), candidates), [])

    def test_sprite_ownership_uses_resolved_texture_not_preload_or_name(self):
        members = C.ProducedMembers()
        typ = dict(class_id=213, tree=b"schema")
        members.members = {"CAB": (None, dict(types=[typ, dict(class_id=28)]), {1: dict(type_id=0), 7: dict(type_id=1), 8: dict(type_id=1)})}
        body = struct.pack("<iq", 0, 7)
        route = ("m_RD", "texture")
        spans = {route: (0, 12), route + ("m_FileID",): (0, 4), route + ("m_PathID",): (4, 12)}
        records = SimpleNamespace(SCHEMA=SimpleNamespace(type_tree=lambda stream: None), fields=lambda body, root: (body, spans))
        with (
            patch.object(C, "module", return_value=records),
            patch.object(members, "resolve", side_effect=lambda member, ref: ("CAB", dict(path_id=ref[1], type_id=1))),
            patch.object(members, "record", return_value=("CAB", typ, body)),
        ):
            self.assertTrue(members.texture_has_sprites("CAB", (0, 7)))
            self.assertFalse(members.texture_has_sprites("CAB", (0, 8)))
            members.sprite_textures = None
            members.members["CAB"][1]["types"][1]["class_id"] = 1
            with self.assertRaisesRegex(ValueError, "ownership type differs"):
                members.texture_has_sprites("CAB", (0, 7))

    def test_sprite_texture_subasset_requires_explicit_render_data_pointer(self):
        members = C.ProducedMembers()
        body = struct.pack("<iq", 0, 7)
        route = ("m_RD", "texture")
        spans = {route: (0, 12), route + ("m_FileID",): (0, 4), route + ("m_PathID",): (4, 12)}
        records = SimpleNamespace(SCHEMA=SimpleNamespace(type_tree=lambda stream: None), fields=lambda body, root: (body, spans))
        with (
            patch.object(C, "module", return_value=records),
            patch.object(members, "resolve", return_value=("CAB", dict(path_id=7))),
            patch.object(members, "record", return_value=("CAB", dict(class_id=28), b"texture")),
        ):
            self.assertEqual(members.owned_subassets("CAB", dict(tree=b"schema"), body, 213), [28])

    def test_tmp_subassets_require_explicit_typed_ownership_fields(self):
        members = C.ProducedMembers()
        identity = ("TMP_FontAsset", "TMPro", "Unity.TextMeshPro.dll")
        body = struct.pack("<iqiq", 0, 7, 0, 8)
        spans = {("material",): (0, 12), ("material", "m_FileID"): (0, 4), ("material", "m_PathID"): (4, 12)}
        records = SimpleNamespace(SCHEMA=SimpleNamespace(type_tree=lambda stream: None), fields=lambda body, root: (body, spans))
        with (
            patch.object(C, "module", return_value=records),
            patch.object(members, "resolve", return_value=("CAB", dict(path_id=7))),
            patch.object(members, "record", return_value=("CAB", dict(class_id=21), b"material")) as record,
        ):
            self.assertEqual(members.owned_subassets("CAB", dict(tree=b"schema"), body, identity), [21])
            record.assert_called_once_with("CAB", (0, 7))
            record.return_value = ("CAB", dict(class_id=28), b"wrong")
            with self.assertRaisesRegex(ValueError, "ownership type differs"):
                members.owned_subassets("CAB", dict(tree=b"schema"), body, identity)

    def test_timeline_tracks_clips_and_parent_cycles_use_only_owned_fields(self):
        members = C.ProducedMembers()
        identities = [(name, "UnityEngine.Timeline", "Unity.Timeline.dll") for name in ("TimelineAsset", "AnimationTrack", "AnimationPlayableAsset")]
        bodies = [struct.pack("<iq", 0, index) for index in (2, 3, 1)]
        routes = [("m_Tracks", "Array", "0"), ("m_Clips", "Array", "0", "m_Asset"), ("m_Parent",)]
        spans = [{route: (0, 12), route + ("m_FileID",): (0, 4), route + ("m_PathID",): (4, 12)} for route in routes]
        records = SimpleNamespace(SCHEMA=SimpleNamespace(type_tree=lambda stream: None), fields=lambda body, root: (body, spans[bodies.index(body)]))
        typ = dict(class_id=114, tree=b"schema")
        with (
            patch.object(C, "module", return_value=records),
            patch.object(members, "resolve", side_effect=lambda member, ref: ("CAB", dict(path_id=ref[1]))),
            patch.object(members, "record", side_effect=lambda member, ref: ("CAB", typ, bodies[ref[1] - 1])),
            patch.object(members, "managed_identity", side_effect=lambda member, typ, body: identities[bodies.index(body)]),
        ):
            self.assertEqual(set(members.owned_subassets("CAB", typ, bodies[0], identities[0])), set(identities))
            with patch.object(members, "managed_identity", return_value=("Foreign", "Other", "Other.dll")):
                with self.assertRaisesRegex(ValueError, "not a Timeline subasset"):
                    members.owned_subassets("CAB", typ, bodies[0], identities[0])

    def test_controller_subassets_follow_explicit_behaviour_array(self):
        members = C.ProducedMembers()
        body = struct.pack("<Iiq", 1, 0, 7)
        records = SimpleNamespace(
            SCHEMA=SimpleNamespace(type_tree=lambda stream: None),
            fields=lambda body, root: (body, {("m_StateMachineBehaviours",): (0, len(body))}),
        )
        identity = ("ResetFootsteps", "RoR2.Mecanim", "RoR2.dll")
        with (
            patch.object(C, "module", return_value=records),
            patch.object(members, "record", return_value=("CAB", dict(class_id=114), b"behaviour")) as record,
            patch.object(members, "managed_identity", return_value=identity),
        ):
            self.assertEqual(members.controller_behaviours("CAB", dict(tree=b"schema"), body), [identity])
            record.assert_called_once_with("CAB", (0, 7))
            with self.assertRaisesRegex(ValueError, "array extent"):
                members.controller_behaviours("CAB", dict(tree=b"schema"), body + bytes(12))
            record.return_value = ("CAB", dict(class_id=1), b"wrong type")
            with self.assertRaisesRegex(ValueError, "not a MonoBehaviour"):
                members.controller_behaviours("CAB", dict(tree=b"schema"), body)

    def fixture(self, root, location_type="UnityEngine.Object, UnityEngine.CoreModule"):
        bundle = root / "bundle"
        bundle.write_bytes(M.build({"sample": dict(sha256="a" * 64, bytes=1, dependencies=[])}))
        registry = root / "globalgamemanagers.assets"
        registry.write_bytes(registry_bytes())
        metadata = root / "metadata.json"
        metadata.write_text(
            json.dumps(dict(input_id="source", attempt="startup", locations=[dict(id=1, path="assetbundlemanifest", type=location_type)], keys=[]))
        )
        profile = root / "profile.json"
        profile.write_text(json.dumps(dict(bundle=dict(name="generated-android-data", asset="assetbundlemanifest"))))
        request = dict(
            schema="owner-catalog-inputs-v1",
            metadata=pin(metadata),
            profiles=[pin(profile)],
            bundles={"generated-android-data": pin(bundle)},
            registry=pin(registry),
            input_id="source",
            attempt="startup",
        )
        path = root / "request.json"
        path.write_text(json.dumps(request))
        return path, request

    def test_pinned_production_validates_actual_container_and_graph(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request, _ = self.fixture(root)
            result = C.produce(request, root / "output")
            self.assertTrue(result["success"])
            self.assertEqual(result["checks"], dict(locations=1, container_paths=1, runtime_scripts=0, model_skin_controllers=0, model_skin_slots=0))
            emitted = json.loads((root / "output/whole-catalog.json").read_bytes())
            self.assertEqual(emitted["locations"][0]["bundle"], "generated-android-data")
            self.assertEqual(emitted["bundles"]["generated-android-data"]["sha256"], result["bundles"]["generated-android-data"]["sha256"])

    def test_managed_catalog_projects_keys_and_checks_actual_container(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, request = self.fixture(root)
            staged = json.loads(Path(request.pop("metadata")["path"]).read_text())["locations"][0]
            source = root / "original-catalog.json"
            row = dict(id=1, internalId="Assets/Authored.asset", type=staged["type"], primaryKey="authored")
            source.write_text(
                json.dumps(
                    dict(
                        input_id=request["input_id"],
                        source_catalog_sha256="catalog-hash",
                        locations=[row, dict(row, id=2, internalId="assetbundlemanifest", type="Unsupported"), dict(row, id=3, internalId="unowned")],
                        keys=[dict(key="alias", keyType="System.String", locations=[2, 1, 3]), dict(key="excluded", keyType="System.String", locations=[2])],
                        providers=[],
                    )
                )
            )
            policy = root / "policy.json"
            projection = dict(
                schema="owner-catalog-projection-v1",
                source_catalog_sha256="catalog-hash",
                remaps={"1": "AssetBundleManifest"},
                exclusions=[2],
                provider_roots=[1],
                runtime_roots=[],
                extra_roots=[],
                mesh_subobjects=[],
            )
            policy.write_text(json.dumps(projection))
            request["projection"] = dict(source=pin(source), policy=pin(policy))
            path.write_text(json.dumps(request))
            result = C.produce(path, root / "output")
            self.assertEqual(result["checks"]["locations"], 1)
            emitted = json.loads((root / "output/whole-catalog.json").read_bytes())
            self.assertEqual(
                emitted["locations"],
                [dict(staged, path="AssetBundleManifest", primaryKey="authored", root=True, bundle="generated-android-data")],
            )
            self.assertEqual(emitted["keys"], [dict(key="alias", keyType="System.String", locations=[1])])
            policy.write_text(json.dumps(dict(projection, source_catalog_sha256="other")))
            request["projection"]["policy"] = pin(policy)
            path.write_text(json.dumps(request))
            with self.assertRaisesRegex(ValueError, "catalog projection source identity differs"):
                C.produce(path, root / "other")

    def test_projection_appends_selected_aliases_in_source_order_and_preserves_root_keys(self):
        locations = [dict(id=i, internalId=f"Assets/Item{i}.asset", type="UnityEngine.GameObject", primaryKey=str(i)) for i in range(1, 6)]
        mesh_path = "Assets/WholeGame/SomeMesh.fbx"
        mesh_key = "SomeMesh.fbx[trunk]"
        source = dict(
            input_id="source",
            source_catalog_sha256="catalog-hash",
            locations=locations,
            keys=[dict(key="aliases", locations=[4, 1, 3, 2]), dict(key="roots", locations=[3, 1, 5, 2])],
            providers=[],
        )
        policy = dict(
            schema="owner-catalog-projection-v1",
            source_catalog_sha256="catalog-hash",
            remaps={},
            exclusions=[],
            provider_roots=[1],
            runtime_roots=[],
            extra_roots=[5],
            mesh_subobjects=[dict(path=mesh_path, key=mesh_key, type="UnityEngine.Mesh")],
            append_locations=[3, 4, 5],
        )
        builds = [dict(assetNames=[f"assets/wholegame/item{i}.asset" for i in range(1, 6)] + [mesh_path.casefold()])]
        with patch.object(sys, "path", [str(ROOT / "scripts/lab"), *sys.path]):
            result = C.project_source_catalog(source, policy, builds, input_id="source", attempt="startup")
            self.assertEqual([row["path"] for row in result["locations"]], [f"Assets/WholeGame/Item{i}.asset" for i in range(1, 6)] + [mesh_path])
            self.assertEqual(
                result["keys"], [dict(key="aliases", locations=[1, 2, 4, 3]), source["keys"][1], dict(key=mesh_key, keyType="System.String", locations=[6])]
            )
            self.assertEqual(result["roots"], [1, 5])
            for invalid in ([3, 3], [6]):
                with self.assertRaisesRegex(ValueError, "catalog projection append selection differs"):
                    C.project_source_catalog(source, dict(policy, append_locations=invalid), builds, input_id="source", attempt="startup")

    def test_player_resource_is_pinned_and_loaded_for_pointer_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, request = self.fixture(root)
            resource = root / "unity_builtin_extra"
            resource.write_bytes(registry_bytes())
            request["resources"] = {resource.name: pin(resource)}
            path.write_text(json.dumps(request))
            original = C.validate_locations

            def validate(metadata, members, registry):
                self.assertIn("unity_builtin_extra", members.members)
                return original(metadata, members, registry)

            with patch.object(C, "validate_locations", side_effect=validate):
                C.produce(path, root / "output")
            resource.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "catalog input differs"):
                C.produce(path, root / "other")

    def test_source_additions_restore_selected_typed_aliases_with_existing_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, request = self.fixture(root)
            metadata = Path(request["metadata"]["path"])
            staged = json.loads(metadata.read_text())
            staged.update(source_catalog_sha256="source-catalog", providers=["provider"])
            staged["keys"] = [dict(key="group", keyType="System.String", locations=[1])]
            metadata.write_text(json.dumps(staged))
            request["metadata"] = pin(metadata)
            original = staged["locations"][0]
            source = root / "source.json"
            source.write_text(
                json.dumps(
                    dict(
                        staged,
                        attempt="source-discovery",
                        locations=[dict(original, id=2, root=False), dict(original, id=3, root=False)],
                        keys=[
                            dict(key="group", keyType="System.String", locations=[2, 3, 1]),
                            dict(key="ghost-guid", keyType="System.String", locations=[2]),
                            dict(key="other-guid", keyType="System.String", locations=[3]),
                        ],
                    )
                )
            )
            request["source_additions"] = dict(metadata=pin(source), locations=[2])
            request["required_routes"] = [dict(key="ghost-guid", type=original["type"], location=2)]
            path.write_text(json.dumps(request))
            result = C.produce(path, root / "output")
            self.assertEqual(result["checks"]["locations"], 2)
            self.assertEqual(result["checks"]["required_routes"], 1)
            emitted = json.loads((root / "output/whole-catalog.json").read_bytes())
            self.assertEqual([(row["id"], row["bundle"]) for row in emitted["locations"]], [(1, "generated-android-data"), (2, "generated-android-data")])
            self.assertEqual([(row["key"], row["locations"]) for row in emitted["keys"]], [("group", [1, 2]), ("ghost-guid", [2])])
            request["source_additions"]["locations"] = [99]
            path.write_text(json.dumps(request))
            with self.assertRaisesRegex(ValueError, "location selection differs"):
                C.produce(path, root / "missing")

    def test_required_routes_reject_missing_wrong_and_ambiguous_typed_endpoints(self):
        shader = "UnityEngine.Shader, UnityEngine.CoreModule"
        metadata = dict(
            locations=[dict(id=1, type=shader), dict(id=2, type="UnityEngine.Material, UnityEngine.CoreModule"), dict(id=3, type=shader)],
            keys=[
                dict(key="camera", locations=[2, 1]),
                dict(key="number", keyType="System.Int32", locations=[1]),
                dict(key="ambiguous", keyType="System.String", locations=[1, 3]),
            ],
        )
        C.validate_required_routes(metadata, [dict(key="camera", type=shader, location=1)])
        for key, location, expected in (
            ("missing", 1, "found \\[\\]"),
            ("number", 1, "found \\[\\]"),
            ("camera", 2, "found \\[1\\]"),
            ("ambiguous", 1, "found \\[1, 3\\]"),
        ):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, expected):
                C.validate_required_routes(metadata, [dict(key=key, type=shader, location=location)])

    def test_source_root_additions_restore_catalog_membership_and_alias_order(self):
        identity = dict(input_id="fixture", source_catalog_sha256="source-catalog", providers=["provider"])
        staged = dict(
            identity,
            locations=[dict(id=1, root=True), dict(id=3, root=True), dict(id=9, root=False)],
            keys=[dict(key="family", locations=[3, 9, 1]), dict(key="other", locations=[3, 1])],
            roots=[1, 3],
            provider_roots=[1, 3],
            runtime_roots=[],
        )
        source = dict(
            identity,
            locations=[dict(id=1, root=True), dict(id=2, root=True), dict(id=3, root=True), dict(id=4, root=True), dict(id=5, root=False)],
            keys=[dict(key="family", locations=[2, 1, 3]), dict(key="other", locations=[5, 1, 3]), dict(key="runtime", locations=[4])],
            roots=[1, 2, 3, 4],
            provider_roots=[1, 2, 3],
            runtime_roots=[4],
        )
        result = C.include_source_locations(staged, source, [2, 4, 5])
        self.assertEqual(result["roots"], [1, 2, 3, 4])
        self.assertEqual(result["provider_roots"], [1, 2, 3])
        self.assertEqual(result["runtime_roots"], [4])
        self.assertEqual([(row["key"], row["locations"]) for row in result["keys"]], [("family", [2, 1, 3, 9]), ("other", [3, 1, 5]), ("runtime", [4])])

    def test_final_type_mismatch_refuses_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request, _ = self.fixture(root, "UnityEngine.GameObject, UnityEngine.CoreModule")
            with self.assertRaisesRegex(ValueError, "endpoint absent or type differs"):
                C.produce(request, root / "output")
            self.assertFalse((root / "output").exists())

    def test_changed_pin_and_startup_identity_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, request = self.fixture(root)
            request["attempt"] = "other-startup"
            path.write_text(json.dumps(request))
            with self.assertRaisesRegex(ValueError, "startup identity differs"):
                C.produce(path, root / "output")
            request["attempt"] = "startup"
            path.write_text(json.dumps(request))
            (root / "bundle").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "catalog input differs"):
                C.produce(path, root / "output")

    def test_duplicate_container_keys_preserve_each_root_and_preload_interval(self):
        fields = dict(
            m_Name="sample",
            m_PreloadTable=[dict(m_FileID=0, m_PathID=2), dict(m_FileID=0, m_PathID=3)],
            m_Container=[("same", dict(preloadIndex=index, preloadSize=1, asset=dict(m_FileID=0, m_PathID=index + 2))) for index in range(2)],
            m_MainAsset=dict(preloadIndex=0, preloadSize=0, asset=dict(m_FileID=0, m_PathID=0)),
            m_RuntimeCompatibility=1,
            m_AssetBundleName="sample",
            m_Dependencies=[],
            m_IsStreamedSceneAssetBundle=False,
            m_ExplicitDataLayout=0,
            m_PathFlags=7,
            m_SceneHashes=[],
        )
        body = C.W.write_shader_body(C.W.shader_node(M.schemas()[0]["tree"]), fields)
        rows, scene = C.containers(body)
        self.assertFalse(scene)
        self.assertEqual(rows, [("same", (0, 2), [(0, 2)]), ("same", (0, 3), [(0, 3)])])
        broken = bytearray(body)
        # Named string + two preload PPtrs + container count + first key.
        offset = 12 + 4 + 24 + 4 + 8
        struct.pack_into("<i", broken, offset, 9)
        with self.assertRaisesRegex(ValueError, "preload extent invalid"):
            C.containers(bytes(broken))

    def test_managed_root_checks_script_target_and_serialized_identity(self):
        def aligned(value):
            raw = struct.pack("<I", len(value)) + value.encode()
            return raw + bytes(-len(raw) % 4)

        identity = ("SkillDef", "RoR2.Skills", "RoR2.dll")
        script = aligned("SkillDef") + bytes(20) + b"".join(aligned(value) for value in identity)
        members = C.ProducedMembers()
        body = bytes(16) + struct.pack("<iq", 0, 7)
        with patch.object(members, "record", return_value=("CAB-script", dict(class_id=115), script)):
            typ = dict(script_id=C.S.md4("".join(identity).encode()))
            self.assertEqual(members.managed_identity("CAB-root", typ, body), identity)
            with self.assertRaisesRegex(ValueError, "binding differs"):
                members.managed_identity("CAB-root", dict(script_id=bytes(16)), body)
        with patch.object(members, "record", return_value=("CAB-script", dict(class_id=1), b"")):
            with self.assertRaisesRegex(ValueError, "not a MonoScript"):
                members.managed_identity("CAB-root", typ, body)

    def test_actual_managed_container_requires_current_runtime_registration(self):
        def aligned(value):
            raw = struct.pack("<I", len(value)) + value.encode()
            return raw + bytes(-len(raw) % 4)

        identity = ("SkillDef", "RoR2.Skills", "RoR2.dll")
        script = aligned("SkillDef") + bytes(20) + b"".join(aligned(value) for value in identity)
        behaviour = bytes(16) + struct.pack("<iq", 0, 3)
        container = aligned("bundle") + struct.pack("<Iiqiq", 2, 0, 2, 0, 3)
        container += struct.pack("<I", 1) + aligned("assets/skill.asset") + struct.pack("<iiiq", 0, 2, 0, 2)
        container += bytes(24) + aligned("bundle") + struct.pack("<I?", 0, False)

        def member(bodies):
            types, objects, offset = [], [], 0
            for index, (class_id, body) in enumerate(bodies):
                typ = dict(class_id=class_id, stripped=0, script_type=-1, hash=bytes(16))
                if class_id == 114:
                    typ["script_id"] = C.S.md4("".join(identity).encode())
                types.append(typ)
                offset = (offset + 7) // 8 * 8
                objects.append(dict(path_id=index + 1, type_id=index, offset=offset, bytes=len(body)))
                offset += len(body)
            stream = io.BytesIO()
            C.W.write_serialized(
                stream,
                dict(engine="2021.3.45f2", platform=13, trees=False, types=types, objects=objects, scripts=[], externals=[], ref_types=[], user=""),
                lambda row: io.BytesIO(bodies[row["path_id"] - 1][1]),
            )
            stream.size = len(stream.getbuffer())
            return stream

        members = C.ProducedMembers()
        members.add("CAB-main", member([(142, container), (114, behaviour), (115, script)]), "bundle")
        members.add("globalgamemanagers.assets", member([(115, script)]), "registry")
        metadata = dict(locations=[dict(id=1, bundle="bundle", path="Assets/Skill.asset", type="RoR2.Skills.SkillDef, RoR2")])
        self.assertEqual(C.validate_locations(metadata, members, "registry")["runtime_scripts"], 1)
        members.members["globalgamemanagers.assets"][2].clear()
        with self.assertRaisesRegex(ValueError, "absent from current runtime registry"):
            C.validate_locations(metadata, members, "registry")

    def test_external_pointer_must_resolve_actual_produced_object(self):
        members = C.ProducedMembers()
        members.members["a"] = (None, dict(externals=[dict(path="archive:/CAB-b/CAB-b")]), {})
        members.members["CAB-b"] = (None, dict(externals=[]), {})
        with self.assertRaisesRegex(ValueError, "missing produced PPtr target"):
            members.record("a", (1, 22))
        with self.assertRaisesRegex(ValueError, "invalid produced PPtr"):
            members.record("a", (2, 22))
        row = dict(path_id=22, offset=0, bytes=1000000)
        members.members["CAB-b"][2][22] = row
        # A preload validates the endpoint without reading its potentially large body.
        self.assertEqual(members.resolve("a", (1, 22)), ("CAB-b", row))


if __name__ == "__main__":
    unittest.main()
