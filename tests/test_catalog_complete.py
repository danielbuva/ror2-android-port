"""Final produced-container checks are independent of profile declarations."""

import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
            self.assertEqual(result["checks"], dict(locations=1, container_paths=1, runtime_scripts=0))
            emitted = json.loads((root / "output/whole-catalog.json").read_bytes())
            self.assertEqual(emitted["locations"][0]["bundle"], "generated-android-data")
            self.assertEqual(emitted["bundles"]["generated-android-data"]["sha256"], result["bundles"]["generated-android-data"]["sha256"])

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
