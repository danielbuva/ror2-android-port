import json
import importlib.util
import io
import re
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from whole_catalog import (
    CAMERA_SHADER_ROOTS,
    integration_metadata,
    integration_bundle_metadata,
    integration_catalog,
    produced_bundle_metadata,
    original_stage_contexts,
    analyze,
    catalog_roots,
    exported_mesh_signature,
    entity_state_gameobject_fields,
    entity_state_reference_closure,
    native_mesh_signature,
    native_candidates,
    preservation_descriptor,
    read_catalog,
    resolve_path,
    scene_guid_owners,
    runtime_key_roots,
    source_mesh_subobjects,
)
import build
from common import read, sha, write


class ProducedCatalogTests(unittest.TestCase):
    def test_native_cycle_closure_sorted_members_and_compact_utf8(self):
        metadata = dict(attempt="authored é\n", locations=[dict(bundle="b")], keys=[])
        bundles = {
            "b": dict(sha256="b-hash", bytes=2, dependencies=["a", "c", "a"]),
            "c": dict(sha256="c-hash", bytes=3, dependencies=[]),
            "a": dict(sha256="a-hash", bytes=1, dependencies=["b"]),
        }
        result = integration_catalog(metadata, bundles, bundle_names=["c", "b", "a"])
        self.assertEqual(
            result,
            (
                '{"attempt":"authored é\\n","locations":[{"bundle":"b"}],"keys":[],"bundles":{'
                '"a":{"sha256":"a-hash","bytes":1,"dependencies":["b","c"]},'
                '"b":{"sha256":"b-hash","bytes":2,"dependencies":["a","c"]},'
                '"c":{"sha256":"c-hash","bytes":3,"dependencies":[]}}}'
            ).encode(),
        )
        self.assertEqual(bundles["b"]["dependencies"], ["a", "c", "a"])
        self.assertNotIn("bundles", metadata)

    def test_missing_location_owner_or_graph_node_refuses_output(self):
        with self.assertRaisesRegex(ValueError, "Missing produced catalog bundles: absent"):
            integration_catalog(dict(locations=[dict(bundle="absent")]), {}, bundle_names=["absent"])
        with self.assertRaisesRegex(ValueError, "Missing produced catalog bundles: missing"):
            integration_catalog(dict(locations=[]), {"a": dict(sha256="hash", bytes=1, dependencies=["missing"])}, bundle_names=["a"])

    def test_declared_bundles_without_locations_are_required_and_unselected_files_omitted(self):
        with self.assertRaisesRegex(ValueError, "Missing produced catalog bundles: unlocated"):
            integration_catalog(dict(locations=[]), {}, bundle_names=["unlocated"])
        facts = {"unlocated": dict(sha256="hash", bytes=1, dependencies=[]), "unselected": {}}
        self.assertEqual(list(json.loads(integration_catalog(dict(locations=[]), facts, bundle_names=["unlocated"]))["bundles"]), ["unlocated"])
        facts["unlocated"]["dependencies"] = ["unselected"]
        with self.assertRaisesRegex(ValueError, "Catalog references undeclared bundles: unselected"):
            integration_catalog(dict(locations=[]), facts, bundle_names=["unlocated"])

    def test_produced_records_supply_dependencies_not_serialized_cab_links(self):
        spec = importlib.util.spec_from_file_location(
            "catalog_fixture_writer", Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/unity_write.py"
        )
        writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(writer)

        def text(value):
            data = value.encode()
            result = struct.pack("<I", len(data)) + data
            return result + bytes(-len(result) % 4)

        named_preload = text("") + struct.pack("<Iiq", 1, 2, 123)
        container = struct.pack("<I", 1) + text("assets/authored.asset") + bytes(20)
        asset_bundle = named_preload + container + bytes(24) + text("authored")
        asset_bundle += struct.pack("<I", 1) + text("bundle-a") + bytes(16)
        preload = named_preload + struct.pack("<I", 2) + text("bundle-b") + text("bundle-a") + bytes(1)
        serialized = []
        for class_id, body in [(142, asset_bundle), (150, preload)]:
            layout = dict(
                engine="2021.3.45f2",
                platform=13,
                trees=False,
                types=[dict(class_id=class_id, stripped=0, script_type=-1, hash=bytes(16))],
                objects=[dict(path_id=1, offset=0, bytes=len(body), type_id=0)],
                scripts=[],
                externals=[dict(empty="", guid=bytes(16), type=0, path="archive:/CAB-not-a-dependency")],
                ref_types=[],
                user="",
            )
            stream = io.BytesIO()
            writer.write_serialized(stream, layout, lambda row, body=body: io.BytesIO(body))
            serialized.append(stream.getvalue())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "authored"
            members = [("CAB-" + str(index), 4, len(data), lambda data=data: io.BytesIO(data)) for index, data in enumerate(serialized)]
            members.append(("CAB-0.resS", 0, 3, lambda: io.BytesIO(b"res")))
            with path.open("wb") as output:
                writer.write_bundle(output, members, lambda data, method: data, flags=0x40)
            facts = produced_bundle_metadata({"authored": path})
            self.assertEqual(facts, {"authored": dict(sha256=sha(path), bytes=path.stat().st_size, dependencies=["bundle-a", "bundle-b"])})


class IntegrationMetadataTests(unittest.TestCase):
    def test_bundle_owners_preserve_rows_and_override_scene_fallback_without_io(self):
        rows = [
            dict(id=1, path="Assets/Explicit.UNITY", root=True),
            dict(id=2, path="assets/explicit.unity", root=False),
            dict(id=3, path="Assets/Ordinary.asset"),
            dict(id=4, path="Assets/Scene.UNITY"),
            dict(id=5, path="assets/scene.unity"),
            dict(id=6, path="Assets/Recovered/geometry.obj"),
        ]
        metadata = dict(locations=rows, keys=[dict(key="alias", locations=[1, 2])], roots=[1])
        builds = [
            dict(assetBundleName="source-scene", assetNames=["Assets/Explicit.unity"]),
            dict(assetBundleName="labgeometry", assetNames=["Assets/Recovered/geometry.obj"]),
        ]
        with patch("builtins.open", side_effect=AssertionError("ownership must not access files")):
            result = integration_bundle_metadata(metadata, builds)
        names = ["source-scene", "source-scene", "whole-game-content", "whole-scene-scene", "whole-scene-scene", "labgeometry"]
        self.assertEqual(result, dict(metadata, locations=[dict(row, bundle=name) for row, name in zip(rows, names)]))
        self.assertNotIn("bundle", rows[0])

    def test_bundle_owners_refuse_observed_explicit_and_scene_collisions(self):
        with self.assertRaisesRegex(RuntimeError, "Duplicate explicit bundle ownership"):
            integration_bundle_metadata(
                dict(locations=[]),
                [dict(assetBundleName="a", assetNames=["Assets/a", "assets/A"])],
            )
        with self.assertRaisesRegex(RuntimeError, "Scene bundle name collision"):
            integration_bundle_metadata(dict(locations=[dict(path="Assets/A/Scene.unity"), dict(path="Assets/B/Scene.unity")]), [])

    def setUp(self):
        self.camera = sorted(CAMERA_SHADER_ROOTS)
        ids = self.camera + [900001, 900003, 900002]
        self.metadata = dict(
            locations=[dict(id=i, type="Fixture.Type", primaryKey="key-" + str(i)) for i in ids],
            keys=[dict(key="alias", keyType="System.String", locations=[900001])],
            providers=["Fixture.Provider"],
        )
        self.closure = dict(
            input_id="fixture-input",
            source_catalog_sha256="fixture-source-hash",
            roots=[900001],
            runtime_roots=[900003],
            converted={str(i): dict(source="Assets/" + str(i)) for i in ids},
        )
        self.mapped = {"Assets/" + str(i): "Assets/WholeGame/" + str(i) for i in ids if i != 900002}

    def test_preserves_catalog_order_alias_numbering_and_root_roles_without_io(self):
        mesh = [dict(source="Assets/900001", type="UnityEngine.Mesh", key="mesh-alias")]
        with patch("builtins.open", side_effect=AssertionError("metadata must not access files")):
            result = integration_metadata(self.metadata, self.closure, self.mapped, mesh, attempt="integration-fixture")
        expected = [dict(row, path=self.mapped["Assets/" + str(row["id"])], root=True) for row in self.metadata["locations"] if row["id"] != 900002]
        alias_id = max(row["id"] for row in self.metadata["locations"]) + 1
        expected.append(dict(id=alias_id, path=self.mapped["Assets/900001"], type="UnityEngine.Mesh", primaryKey="mesh-alias", root=False))
        self.assertEqual(
            result,
            dict(
                input_id="fixture-input",
                attempt="integration-fixture",
                locations=expected,
                keys=self.metadata["keys"] + [dict(key="mesh-alias", keyType="System.String", locations=[alias_id])],
                providers=self.metadata["providers"],
                source_catalog_sha256="fixture-source-hash",
                roots=sorted(self.camera + [900001, 900003]),
                provider_roots=[900001],
                runtime_roots=[900003],
                quarantine=[],
            ),
        )

    def test_missing_runtime_root_refuses(self):
        del self.mapped["Assets/900003"]
        with self.assertRaisesRegex(RuntimeError, "Provider roots lost"):
            integration_metadata(self.metadata, self.closure, self.mapped, [], attempt="integration-fixture")

    def test_pre_camera_build_uses_its_source_selection_and_root_policy(self):
        # J850 predates the camera extension: one shader remains a non-root
        # dependency, while shaders outside the historical closure are absent.
        mapped = {key: value for key, value in self.mapped.items() if key not in {"Assets/" + str(i) for i in self.camera[1:]}}
        result = integration_metadata(self.metadata, self.closure, mapped, [], attempt="accepted-fixture", camera_roots=())
        self.assertEqual(result["roots"], [900001, 900003])
        self.assertEqual([row["id"] for row in result["locations"]], [self.camera[0], 900001, 900003])
        self.assertFalse(result["locations"][0]["root"])
        self.assertEqual(result["keys"], self.metadata["keys"])
        owned = integration_metadata(self.metadata, self.closure, mapped, [], attempt="accepted-fixture", camera_roots=(), bundle_builds=[])
        self.assertEqual(owned, integration_bundle_metadata(result, []))

    def test_recipe_mapping_supplies_metadata_and_mesh_aliases_without_project_scan(self):
        from composition_rebuild import integration_declarations, integration_mapping

        sources = ["Assets/" + str(row["id"]) for row in self.metadata["locations"]]
        index = {"guid-" + source: source for source in sources}
        with patch("builtins.open", side_effect=AssertionError("mapping and metadata must not access files")):
            declarations = integration_declarations(
                index,
                [],
                [],
                [],
                [dict(source="Assets/900001", output="Assets/Relocated.asset")],
                [],
                dict(runtime_source_guids={"runtime/input/NovaInputBridge.cs": "bridge"}),
            )
            mapped = integration_mapping(index, sources, declarations)
            result = integration_metadata(
                self.metadata, self.closure, mapped, [dict(source="Assets/900001", type="UnityEngine.Mesh", key="mesh-alias")], attempt="fixture"
            )
        self.assertEqual(result["locations"][-1]["path"], "Assets/Relocated.asset")
        self.assertEqual(next(row for row in result["locations"] if row["id"] == 900001)["path"], "Assets/Relocated.asset")
        self.assertEqual(result["roots"], sorted(self.camera + [900001, 900003]))

    def test_missing_mesh_owner_refuses(self):
        with self.assertRaisesRegex(RuntimeError, "Exact original mesh subobject was not staged"):
            integration_metadata(self.metadata, self.closure, self.mapped, [dict(source="missing", key="mesh-alias")], attempt="integration-fixture")


class WholePayloadReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.project = self.work / "lab-project"
        self.allowed = sorted(build.WHOLE_PLAYER_INPUTS)
        for name in self.allowed + ["Assets/Content.prefab"]:
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")
        payload = self.work / "generated-android-data/content"
        payload.parent.mkdir()
        payload.write_text("content fixture")
        write(
            self.work / "whole-catalog-code-base.json",
            dict(allowed=self.allowed, files={"Assets/Content.prefab": sha(self.project / "Assets/Content.prefab")}, payload={"content": sha(payload)}),
        )
        self.patcher = patch.object(build, "WORK", self.work)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_code_only_fix_cannot_reuse_changed_game_content(self):
        (self.project / "Assets/LabDiagnostics.cs").write_text("updated harness method")
        build.validate_whole_payload_reuse(self.project)
        (self.project / "Assets/Content.prefab").write_text("changed game content")
        with self.assertRaisesRegex(RuntimeError, "Content inputs changed"):
            build.validate_whole_payload_reuse(self.project)

    def test_authored_bootstrap_migrates_old_receipt_without_changing_payload(self):
        receipt = self.work / "whole-catalog-code-base.json"
        frozen = read(receipt)
        bootstrap = next(iter(build.WHOLE_APK_ASSEMBLIES))
        frozen["allowed"].remove(bootstrap)
        frozen["files"][bootstrap] = "previous authored bootstrap hash"
        write(receipt, frozen)
        (self.project / bootstrap).write_text("current authored owner contract")
        build.validate_whole_payload_reuse(self.project)
        updated = read(receipt)
        self.assertEqual(updated["payload"], frozen["payload"])
        self.assertNotIn(bootstrap, updated["files"])
        self.assertIn(bootstrap, updated["allowed"])
        (self.work / "generated-android-data/content").write_text("changed payload")
        with self.assertRaisesRegex(RuntimeError, "payload identity changed"):
            build.validate_whole_payload_reuse(self.project)

    def test_bootstrap_importer_and_game_assemblies_remain_frozen(self):
        for relative in (
            "Assets/LabLoadingScene/Plugins/GameAudioOriginalBootstrap.dll.meta",
            "Assets/LabLoadingScene/Plugins/RoR2.dll",
            "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll",
        ):
            with self.subTest(relative=relative):
                path = self.project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("frozen")
                build.freeze_whole_payload(self.project, {"payload": {}, "key": "fixture"})
                path.write_text("changed")
                with self.assertRaisesRegex(RuntimeError, "Content inputs changed"):
                    build.validate_whole_payload_reuse(self.project)
                path.unlink()

    def test_uncompressed_reuse_is_separate_and_requires_exact_content_and_payload(self):
        normal = self.work / "whole-catalog-code-base.json"
        original = normal.read_bytes()
        self.assertFalse(build.reuse_uncompressed_payload(self.project))
        receipt = self.work / "whole-catalog-uncompressed-base.json"
        payload = self.work / "generated-android-data/content"
        build.freeze_whole_payload(self.project, {"payload": {"content": sha(payload)}, "key": "authored"}, receipt)
        self.assertTrue(build.reuse_uncompressed_payload(self.project))
        (self.project / "Assets/LabDiagnostics.cs").write_text("changed player-only code")
        self.assertTrue(build.reuse_uncompressed_payload(self.project))
        payload.write_text("changed generated payload")
        self.assertFalse(build.reuse_uncompressed_payload(self.project))
        payload.write_text("content fixture")
        (self.project / "Assets/Content.prefab").write_text("changed content")
        self.assertFalse(build.reuse_uncompressed_payload(self.project))
        self.assertEqual(normal.read_bytes(), original)

    def test_uncompressed_build_refuses_canonical_and_code_only_paths_before_editor_work(self):
        with patch.object(build, "lane_config", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "isolated full iteration"):
                build.build(bundle_compression="uncompressed")
        with patch.object(build, "lane_config", return_value={"name": "fixture"}):
            with self.assertRaisesRegex(RuntimeError, "isolated full iteration"):
                build.build(bundle_compression="uncompressed", reuse_payload=True)

    def test_reuse_rejects_corrupted_or_added_payload(self):
        (self.work / "generated-android-data/content").write_text("corrupted")
        with self.assertRaisesRegex(RuntimeError, "payload identity changed"):
            build.validate_whole_payload_reuse(self.project)


class WholeCatalogTests(unittest.TestCase):
    def test_ambiguous_mesh_export_requires_matching_native_buffers(self):
        native = dict(
            m_VertexData=dict(m_VertexCount=3, m_DataSize=b"\x01\x02\x03"),
            m_IndexBuffer=[0, 1, 2],
            m_SubMeshes=[dict(firstByte=0, indexCount=3, topology=0, baseVertex=0, firstVertex=0, vertexCount=3)],
        )
        source = "%YAML 1.1\n--- !u!43 &4300000\nMesh:\n  m_SubMeshes:\n  - serializedVersion: 2\n    firstByte: 0\n    indexCount: 3\n    topology: 0\n    baseVertex: 0\n    firstVertex: 0\n    vertexCount: 3\n  m_Shapes:\n    vertices: []\n  m_IndexBuffer: 000102\n  m_VertexData:\n    m_VertexCount: 3\n    _typelessdata: 010203\n"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "same-name.asset"
            path.write_text(source)
            self.assertEqual(exported_mesh_signature(path), native_mesh_signature(native))
            path.write_text(source.replace("010203", "010204"))
            self.assertNotEqual(exported_mesh_signature(path), native_mesh_signature(native))

    def test_mesh_subobjects_require_exact_guid_name_type_and_native_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Assets").mkdir()
            (root / "Assets/skin.asset").write_text(
                "%YAML\nmeshAddress:\n  m_AssetGUID: "
                + "a" * 32
                + "\n  m_SubObjectName: VultureMesh\n  m_SubObjectType: UnityEngine.Mesh, UnityEngine.CoreModule\n"
                "otherMeshAddress:\n  m_AssetGUID: "
                + "b" * 32
                + "\n  m_SubObjectName: VultureMesh\n  m_SubObjectType: UnityEngine.Mesh, UnityEngine.CoreModule\n"
            )
            (root / "Assets/VultureMesh.asset").write_text("%YAML\n")
            metadata = dict(
                keys=[dict(key=g * 32, keyType="System.String", locations=[i]) for i, g in enumerate("ab", 1)],
                locations=[dict(id=i, type="UnityEngine.Mesh, UnityEngine.CoreModule") for i in (1, 2)],
            )
            native = dict(
                issues=[
                    dict(location=i, objects=[dict(name=name, type="Mesh", source="Assets/VultureMesh.asset", native_path_id=i)])
                    for i, name in ((1, "VultureMesh"), (2, "OtherMesh"))
                ]
            )
            resolved, unresolved = source_mesh_subobjects(root, dict(files=["Assets/skin.asset"], converted={}), metadata, native)
            self.assertEqual([row["key"] for row in resolved], ["a" * 32 + "[VultureMesh]"])
            self.assertEqual(resolved[0]["native_path_id"], 1)
            self.assertEqual([row["key"] for row in unresolved], ["b" * 32 + "[VultureMesh]"])

    def test_runtime_keys_use_exact_original_identity_and_keep_consumers(self):
        data = dict(
            keys=[
                dict(key="baked-key", locations=[1]),
                dict(key="missing-conversion", locations=[2]),
                dict(key="bundle", locations=[3]),
                dict(key="typed", keyType="System.Type", locations=[1]),
            ],
            locations=[
                dict(id=1, internalId="Assets/baked.asset", primaryKey="baked-key"),
                dict(id=2, internalId="Assets/missing.asset", primaryKey="missing-conversion"),
                dict(id=3, internalId="library:/bundle"),
            ],
        )
        candidates = [dict(key=key, methods=["Original.Method"]) for key in ["baked-key", "missing-conversion", "bundle", "typed", "Baked-key"]]
        roots, edges = runtime_key_roots(data, candidates)
        self.assertEqual(roots, {1, 2})
        self.assertEqual([row["key"] for row in edges], ["baked-key", "missing-conversion"])
        self.assertEqual(edges[0]["methods"], ["Original.Method"])
        data["keys"].append(dict(key="stage-name", locations=[1, 2]))
        self.assertEqual(runtime_key_roots(data, [dict(key="stage-name", methods=["Original.CompareStage"])]), (set(), []))
        alias = "Legacy/OriginalAsset"
        guid = "b" * 32
        data["keys"].append(dict(key=guid, locations=[2]))
        roots, edges = runtime_key_roots(data, [dict(key=alias, methods=["Original.LoadLegacy"])], {alias: guid})
        self.assertEqual(roots, {2})
        self.assertEqual(edges, [dict(key=guid, source_key=alias, locations=[2], methods=["Original.LoadLegacy"])])
        self.assertEqual(runtime_key_roots(data, [dict(key=alias, methods=["Original.LoadLegacy"])]), (set(), []))

    def test_scene_collision_keeps_original_guid_target_and_both_addresses(self):
        guid = "a" * 32
        paths = ["Assets/stage.unity", "Assets/stageTest.unity"]
        data = dict(
            keys=[dict(key=guid, locations=[1])],
            locations=[
                dict(id=i + 1, internalId=p, type="UnityEngine.ResourceManagement.ResourceProviders.SceneInstance, Unity.ResourceManager")
                for i, p in enumerate(paths)
            ],
        )
        index, repairs = scene_guid_owners({guid: paths}, data, "input")
        self.assertEqual(index[guid], paths[0])
        self.assertEqual(set(index.values()), set(paths))
        self.assertEqual(repairs[0]["source"], paths[1])
        self.assertEqual(scene_guid_owners({guid: paths}, data, "input"), (index, repairs))
        data["keys"][0]["locations"] = [1, 2]
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            scene_guid_owners({guid: paths}, data, "input")

    def test_non_scene_guid_collision_still_requires_attribution(self):
        data = dict(keys=[dict(key="a", locations=[1])], locations=[dict(id=1, internalId="Assets/body.prefab", type="UnityEngine.GameObject")])
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            scene_guid_owners({"a": ["Assets/body.prefab", "Assets/bodyOther.prefab"]}, data, "input")

    def test_unverified_content_is_still_a_root(self):
        data = dict(
            keys=[dict(key="ContentPack:base", locations=[1, 2]), dict(key="Items", locations=[1, 2, 3])],
            providers=[dict(identifier="base")],
            labels=[dict(name="items", key="Items")],
        )
        packs, roots = catalog_roots(data, ["items"])
        self.assertEqual(roots, {1, 2})
        self.assertEqual(packs[0]["categories"]["items"], [1, 2])

    def test_missing_provider_label_fails_instead_of_empty_success(self):
        data = dict(keys=[], providers=[dict(identifier="base")], labels=[])
        with self.assertRaisesRegex(RuntimeError, "provider label absent"):
            catalog_roots(data, [])

    def test_unresolved_imported_model_is_not_guessed(self):
        self.assertEqual(resolve_path("Assets/Model.fbx", {"Assets/Model.asset", "Assets/Model.prefab"}), (None, "unresolved-conversion"))

    def test_case_collision_is_not_silently_selected(self):
        self.assertEqual(resolve_path("Assets/NAME.asset", {"Assets/Name.asset", "Assets/name.asset"}), (None, "unresolved-conversion"))
        self.assertEqual(resolve_path("Assets/NAME.asset", {"Assets/Name.asset"}), ("Assets/Name.asset", "exported-filename-case"))

    def test_native_object_mapping_requires_type_name_and_owner(self):
        record = dict(address="Assets/Actors/model.fbx", type="Mesh", name="Body", path_id=123, serialized_file="source-file")
        exports = {("Assets/Actors", "Mesh", "Body"): ["Assets/Actors/Body.asset"], ("Assets/Actors", "GameObject", "Body"): ["Assets/Actors/Body.prefab"]}
        objects, issues = native_candidates([record], exports)
        self.assertEqual(objects[0]["source"], "Assets/Actors/Body.asset")
        self.assertEqual(objects[0]["native_path_id"], 123)
        self.assertFalse(issues)
        exports[("Assets/Actors", "Mesh", "Body")].append("Assets/Actors/Body_0.asset")
        objects, issues = native_candidates([record], exports)
        self.assertFalse(objects)
        self.assertEqual(issues[0]["category"], "ambiguous-exported-object")

    def test_compact_graph_retains_all_dependencies_without_duplicate_arrays(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.json"
            path.write_text(json.dumps(dict(schemaVersion=2, dependencySets=[[4, 5]], locations=[dict(id=i, dependencySet=0) for i in [1, 2]])))
            data = read_catalog(path)
            self.assertEqual(data["locations"][0]["dependencies"], [4, 5])
            self.assertIs(data["locations"][0]["dependencies"], data["locations"][1]["dependencies"])

    def test_runtime_reference_edges_expand_beyond_provider_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            guid = "a" * 32
            (root / "Assets").mkdir()
            (root / "Assets/root.asset").write_text("%YAML\nm_AssetGUID: " + guid + "\nassetGUID: " + guid + "\n")
            (root / "Assets/dependency.asset").write_text("%YAML\nm_Name: dependency\n")
            categories = ["category" + str(i) for i in range(29)]
            helper = "\n".join("FindLocationsThenAddLoadOperation(AddressablesLabels." + name + ")" for name in categories)
            data = dict(
                keys=[dict(key="ContentPack:base", locations=[1]), dict(key=categories[0], locations=[1]), dict(key=guid, locations=[2])],
                providers=[dict(identifier="base")],
                labels=[dict(name=name, key=name) for name in categories],
                locations=[
                    dict(id=i, internalId="Assets/" + name + ".asset", dependencies=[], type="Example.Asset, Example")
                    for i, name in [(1, "root"), (2, "dependency")]
                ],
            )
            source = root / "catalog.json"
            source.write_text(json.dumps(data))
            result = analyze(source, root, {"b" * 32: "Assets/root.asset", "c" * 32: "Assets/dependency.asset"}, helper)
            self.assertEqual(result["files"], ["Assets/dependency.asset", "Assets/root.asset"])
            self.assertEqual(result["summary"]["catalog_roots"], 1)
            self.assertEqual(result["summary"]["soft_reference_edges"], 1)
            self.assertEqual(result["summary"]["quarantine"], [])

    def test_original_stage_policy_requires_unique_complete_source_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = "golemplains"
            scene = root / "Assets/RoR2/Base/Scenes" / stage / (stage + ".unity")
            scene.parent.mkdir(parents=True)
            record = (
                "--- !u!114 &1\n  monsterDccsPool: {fileID: 11400000, guid: "
                + ("a" * 32)
                + ", type: 2}\n  interactableDccsPool: {fileID: 11400000, guid: "
                + ("b" * 32)
                + ", type: 2}\n"
            )
            for name, value in [
                ("ignoreArtifactsThatRebuildCards", 0),
                ("contentSourceMixLimitOverride", 1),
                ("contentSourceMixLimitOverrideValue", 3),
                ("contentInteractableOnlySourceMixLimitOverride", 0),
                ("contentInteractableOnlySourceMixLimitOverrideValue", 2),
                ("sceneDirectorInteractibleCredits", 220),
                ("sceneDirectorMonsterCredits", 100),
            ]:
                record += "  " + name + ": " + str(value) + "\n"
            record += "  bonusInteractibleCreditObjects: []\n--- !u!114 &2\n  usePlacedSpawnPoints: 0\n  expRewardCoefficient: 0.06666667\n  eliteBias: 2\n  spawnDistanceMultiplier: 6\n  monsterSpawnTargetOverride: {fileID: 0}\n"
            scene.write_text(record)
            result = original_stage_contexts(root, [stage], "accepted", {"a" * 32: "Original/Monsters", "b" * 32: "Original/Interactables"})
            self.assertEqual(result["stages"][stage]["director_fields"]["spawnDistanceMultiplier"], 6)
            self.assertEqual(result["stages"][stage]["bonus_credits"], [])
            self.assertEqual(result["stages"][stage]["monsterDccsPool"], "Original/Monsters")
            self.assertEqual(result["stages"][stage]["fields"]["contentSourceMixLimitOverrideValue"], 3)
            self.assertIs(result["stages"][stage]["fields"]["contentSourceMixLimitOverride"], True)
            scene.write_text(
                record.replace(
                    "bonusInteractibleCreditObjects: []", "bonusInteractibleCreditObjects:\n  - objectThatGrantsPointsIfEnabled: {fileID: 5}\n    points: 160"
                )
                + "--- !u!1 &5\n  m_Name: Variant\n--- !u!4 &6\n  m_GameObject: {fileID: 5}\n  m_Father: {fileID: 8}\n--- !u!1 &7\n  m_Name: Environment\n--- !u!4 &8\n  m_GameObject: {fileID: 7}\n  m_Father: {fileID: 0}\n"
            )
            result = original_stage_contexts(root, [stage], "accepted", {"a" * 32: "Original/Monsters", "b" * 32: "Original/Interactables"})
            self.assertEqual(result["stages"][stage]["bonus_credits"], [{"path": "Environment/Variant", "points": 160}])
            scene.write_text(scene.read_text().replace("points: 160", "points: unknown"))
            with self.assertRaisesRegex(RuntimeError, "bonus credit entry"):
                original_stage_contexts(root, [stage], "accepted", {"a" * 32: "Original/Monsters", "b" * 32: "Original/Interactables"})
            scene.write_text(record + record)
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                original_stage_contexts(root, [stage], "accepted", {"a" * 32: "Original/Monsters", "b" * 32: "Original/Interactables"})
            scene.write_text(record.replace("  sceneDirectorMonsterCredits: 100\n", ""))
            with self.assertRaisesRegex(RuntimeError, "policy missing"):
                original_stage_contexts(root, [stage], "accepted", {"a" * 32: "Original/Monsters", "b" * 32: "Original/Interactables"})

    def test_state_preload_strings_extend_runtime_closure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Assets").mkdir()
            guid = "a" * 32
            (root / "Assets/root.asset").write_text("%YAML\n  preloadGUIDReferences:\n  - " + guid + "\n  - \n")
            (root / "Assets/preloaded.prefab").write_text("%YAML\n  m_Name: preloaded\n")
            categories = ["category" + str(i) for i in range(29)]
            helper = "\n".join("FindLocationsThenAddLoadOperation(AddressablesLabels." + name + ")" for name in categories)
            data = dict(
                keys=[dict(key="ContentPack:base", locations=[1]), dict(key=categories[0], locations=[1]), dict(key=guid, locations=[2])],
                providers=[dict(identifier="base")],
                labels=[dict(name=name, key=name) for name in categories],
                locations=[
                    dict(id=1, internalId="Assets/root.asset", dependencies=[], type="Example.Config, Example"),
                    dict(id=2, internalId="Assets/preloaded.prefab", dependencies=[], type="UnityEngine.GameObject, Example"),
                ],
            )
            source = root / "catalog.json"
            source.write_text(json.dumps(data))
            result = analyze(source, root, {"b" * 32: "Assets/root.asset", "c" * 32: "Assets/preloaded.prefab"}, helper)
            self.assertEqual(result["files"], ["Assets/preloaded.prefab", "Assets/root.asset"])
            self.assertEqual(result["runtime_roots"], [2])
            self.assertEqual(result["runtime_key_edges"][0]["field"], "preloadGUIDReferences")
            self.assertEqual(result["summary"]["issues"]["invalid-preload-key"], 1)
            self.assertEqual(result["summary"]["quarantine"], [])

    def test_broken_original_dependency_graph_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = ["category" + str(i) for i in range(29)]
            data = dict(
                keys=[dict(key="ContentPack:base", locations=[1])],
                providers=[dict(identifier="base")],
                labels=[dict(name=n, key=n) for n in names],
                locations=[dict(id=1, internalId="Assets/root.asset", dependencies=[99])],
            )
            source = root / "catalog.json"
            source.write_text(json.dumps(data))
            helper = "\n".join("FindLocationsThenAddLoadOperation(AddressablesLabels." + n + ")" for n in names)
            with self.assertRaisesRegex(RuntimeError, "Broken original catalog dependency"):
                analyze(source, root, {}, helper)


class EntityStateGameObjectClosureTests(unittest.TestCase):
    def write_state_sources(self, root):
        root.mkdir(parents=True, exist_ok=True)
        (root / "States.cs").write_text("""
namespace Fixture.States {
    public class BaseState {
        public EntityStateGameObject inheritedCharge;
        public string ordinaryText;
        public EntityStateGameObject wrongType;
        public EntityStateGameObject ambiguous;
        public EntityStateGameObject missing;
        public EntityStateGameObject unconverted;
        public EntityStateGameObject orphaned;
        public class NestedState {
            public EntityStateGameObject nestedOnly;
        }
    }
    public class DerivedState : BaseState {
        public EntityStateGameObject beam;
        public string ordinaryDerivedText;
    }
    public class SiblingState : BaseState { }
    public class HiddenState : BaseState {
        public new string inheritedCharge;
    }
}
""")
        return root

    @staticmethod
    def state_config(state_type, fields):
        rows = [
            "%YAML 1.1",
            "--- !u!114 &1",
            "MonoBehaviour:",
            "  targetType:",
            "    assemblyQualifiedName: " + state_type + ", RoR2, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null",
            "  serializedFieldsCollection:",
            "    serializedFields:",
        ]
        for name, representation, value in fields:
            rows.extend(["    - fieldName: " + name, "      fieldValue:"])
            if representation == "stringValue":
                rows.append("        stringValue: " + value)
            else:
                rows.append("        objectValue: " + value)
        return "\n".join(rows) + "\n"

    def test_fields_are_scoped_inherited_nested_and_shadowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            fields = entity_state_gameobject_fields(self.write_state_sources(Path(temporary)))
        self.assertEqual(fields["Fixture.States.BaseState"], {"inheritedCharge", "wrongType", "ambiguous", "missing", "unconverted", "orphaned"})
        self.assertEqual(fields["Fixture.States.DerivedState"], {"inheritedCharge", "wrongType", "ambiguous", "missing", "unconverted", "orphaned", "beam"})
        self.assertEqual(fields["Fixture.States.BaseState+NestedState"], {"nestedOnly"})
        self.assertEqual(fields["Fixture.States.SiblingState"], {"inheritedCharge", "wrongType", "ambiguous", "missing", "unconverted", "orphaned"})
        self.assertNotIn("beam", fields["Fixture.States.BaseState"])
        self.assertNotIn("inheritedCharge", fields["Fixture.States.HiddenState"])

    def test_only_typed_guid_string_values_become_asset_edges(self):
        with tempfile.TemporaryDirectory() as temporary:
            fields = entity_state_gameobject_fields(self.write_state_sources(Path(temporary)))
        guid = "a" * 32
        config = self.state_config(
            "Fixture.States.DerivedState",
            [
                ("inheritedCharge", "stringValue", guid),
                ("beam", "stringValue", "not-a-guid"),
                ("wrongType", "objectValue", "{fileID: 0}"),
                ("ordinaryText", "stringValue", guid),
                ("ordinaryDerivedText", "stringValue", guid),
            ],
        )
        catalog_keys = {guid: [1]}
        converted = {1: {"source": "Charge.prefab"}}
        locations = {
            1: {
                "type": "UnityEngine.GameObject, UnityEngine.CoreModule",
                "provider": "fixture-provider",
                "internalId": "Assets/Charge.prefab",
                "primaryKey": "Fixture/Charge.prefab",
            }
        }
        edges, pending, issues = entity_state_reference_closure(config, "Assets/State.asset", fields, catalog_keys, converted, locations)
        self.assertEqual([edge["field"] for edge in edges], ["inheritedCharge"])
        self.assertEqual(pending, ["Charge.prefab"])
        self.assertEqual(issues, [])

    def test_nested_base_identity_precedes_unrelated_namespace_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Nested.cs").write_text("""
namespace Fixture {
    public class Outer {
        public class ChargedState {
            public EntityStateGameObject localEffect;
        }
        public class DerivedState : ChargedState { }
    }
}
namespace Other {
    public class ChargedState {
        public EntityStateGameObject foreignEffect;
    }
}
""")
            fields = entity_state_gameobject_fields(root)
        self.assertEqual(fields["Fixture.Outer+DerivedState"], {"localEffect"})

    def test_exact_gameobject_identity_and_every_refusal_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            fields = entity_state_gameobject_fields(self.write_state_sources(Path(temporary)))
        good, wrong, ambiguous, missing, unconverted, orphaned = ("a" * 32, "b" * 32, "c" * 32, "d" * 32, "e" * 32, "f" * 32)
        config = self.state_config(
            "Fixture.States.BaseState",
            [
                ("inheritedCharge", "stringValue", good),
                ("wrongType", "stringValue", wrong),
                ("ambiguous", "stringValue", ambiguous),
                ("missing", "stringValue", missing),
                ("unconverted", "stringValue", unconverted),
                ("orphaned", "stringValue", orphaned),
            ],
        )
        keys = {good: [10, 11], wrong: [20], ambiguous: [30, 31], missing: [], unconverted: [40], orphaned: [50]}
        locations = {
            10: {"type": "UnityEngine.Mesh, UnityEngine.CoreModule", "provider": "wrong-provider", "internalId": "Assets/Wrong.asset"},
            11: {
                "type": "UnityEngine.GameObject, UnityEngine.CoreModule",
                "provider": "fixture-provider",
                "internalId": "Assets/Good.prefab",
                "primaryKey": "Fixture/Good.prefab",
            },
            20: {"type": "UnityEngine.Mesh, UnityEngine.CoreModule", "provider": "fixture-provider", "internalId": "Assets/Mesh.asset"},
            30: {"type": "UnityEngine.GameObject, UnityEngine.CoreModule", "provider": "fixture-provider", "internalId": "Assets/A.prefab"},
            31: {"type": "UnityEngine.GameObject, UnityEngine.CoreModule", "provider": "fixture-provider", "internalId": "Assets/B.prefab"},
            40: {"type": "UnityEngine.GameObject, UnityEngine.CoreModule", "provider": "fixture-provider", "internalId": "Assets/Unconverted.prefab"},
        }
        converted = {
            10: {"source": "Wrong.asset"},
            11: {"source": "Good.prefab"},
            20: {"source": "Mesh.asset"},
            30: {"source": "A.prefab"},
            31: {"source": "B.prefab"},
        }
        edges, pending, issues = entity_state_reference_closure(config, "Assets/State.asset", fields, keys, converted, locations)
        by_field = {edge["field"]: edge for edge in edges}
        self.assertEqual(by_field["inheritedCharge"]["locations"], [10, 11])
        self.assertEqual(by_field["inheritedCharge"]["matchingLocations"], [11])
        self.assertEqual(by_field["inheritedCharge"]["locationIdentity"][0]["provider"], "wrong-provider")
        self.assertEqual(pending, ["Good.prefab"])
        self.assertEqual(
            {issue["field"]: issue["category"] for issue in issues},
            {
                "wrongType": "asset-reference-requested-type-missing",
                "ambiguous": "asset-reference-requested-type-ambiguous",
                "missing": "asset-reference-key-missing",
                "unconverted": "asset-reference-conversion-unresolved",
                "orphaned": "asset-reference-requested-type-missing",
            },
        )

    def test_analyze_stages_typed_dependency_as_nonroot_manifest_location(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = root / "export"
            export.mkdir()
            source_root = self.write_state_sources(root / "native-source")
            guid = "f" * 32
            state_type = "Fixture.States.DerivedState"
            state_yaml = self.state_config(state_type, [("beam", "stringValue", guid)])
            for relative, contents in {
                "Assets/State.asset": state_yaml,
                "Assets/Beam.prefab": "%YAML 1.1\n--- !u!1 &1\nGameObject: {m_Name: Beam}\n",
            }.items():
                target = export / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents)
            categories = ["category" + str(index) for index in range(29)]
            helper = "\n".join("FindLocationsThenAddLoadOperation(AddressablesLabels." + name + ")" for name in categories)
            catalog = {
                "providers": [{"identifier": "fixture"}],
                "labels": [{"name": name, "key": name} for name in categories],
                "keys": [
                    {"key": "ContentPack:fixture", "keyType": "System.String", "locations": [1]},
                    {"key": categories[0], "keyType": "System.String", "locations": [1]},
                    {"key": guid, "keyType": "System.String", "locations": [2]},
                ],
                "locations": [
                    {
                        "id": 1,
                        "internalId": "Assets/State.asset",
                        "type": "RoR2.EntityStateConfiguration, RoR2",
                        "dependencies": [],
                        "provider": "state-provider",
                    },
                    {
                        "id": 2,
                        "internalId": "Assets/Beam.prefab",
                        "primaryKey": "Fixture/Beam.prefab",
                        "type": "UnityEngine.GameObject, UnityEngine.CoreModule",
                        "dependencies": [],
                        "provider": "gameobject-provider",
                    },
                ],
            }
            catalog_path = root / "catalog.json"
            catalog_path.write_text(json.dumps(catalog))
            result = analyze(
                catalog_path,
                export,
                {"state-guid": "Assets/State.asset", "beam-guid": "Assets/Beam.prefab"},
                helper,
                state_source_root=source_root,
            )
            staged = set(result["files"])
            selected = {int(identity): conversion["source"] for identity, conversion in result["converted"].items() if conversion["source"] in staged}
            self.assertIn("Assets/Beam.prefab", staged)
            self.assertEqual(selected[2], "Assets/Beam.prefab")
            self.assertNotIn(2, result["roots"])
            self.assertNotIn(2, result["runtime_roots"])
            edge = next(row for row in result["soft_edges"] if row.get("kind") == "EntityStateGameObject")
            self.assertEqual(edge["requestedType"], "UnityEngine.GameObject")
            self.assertEqual(edge["locationIdentity"][0]["provider"], "gameobject-provider")


class PreservationDescriptorTests(unittest.TestCase):
    def test_bundle_rooted_assemblies_survive_a_fresh_editor(self):
        import xml.etree.ElementTree as ET

        linker = ET.fromstring(preservation_descriptor({"RoR2": {"RoR2.ItemDef", "RoR2.Achievements.*"}, "Unity.ResourceManager": {"Outer+Inner"}}))
        assemblies = {node.get("fullname"): node for node in linker.findall("assembly")}
        # J33 measured ProviderOperation`1, GroupOperation, ChainOperation`2 and
        # ResourceManager/CompletedOperation`1; whole-assembly preservation covers them.
        self.assertEqual(assemblies["Unity.ResourceManager"].get("preserve"), "all")
        self.assertEqual([n.get("fullname") for n in assemblies["Unity.ResourceManager"]], ["Outer/Inner"])
        # J583: full builds also root Unity.Timeline; code-only builds must match them.
        for name in ["KinematicCharacterController", "Rewired_Core", "Unity.Timeline", "com.unity.multiplayer-hlapi.Runtime"]:
            self.assertEqual(assemblies[name].get("preserve"), "all")
        self.assertIsNone(assemblies["RoR2"].get("preserve"))
        self.assertEqual(sorted(n.get("fullname") for n in assemblies["RoR2"]), ["RoR2.Achievements.*", "RoR2.ItemDef"])
        self.assertEqual(list(assemblies), sorted(assemblies))


class AuthoredIntegrationHookTests(unittest.TestCase):
    """The build copies these sources unchanged, so the hooks must be authored in them."""

    UNITY = Path(__file__).resolve().parents[1] / "tools/unity"

    def compact(self, name):
        return "".join((self.UNITY / name).read_text().split())

    def test_start_yields_to_the_catalog_scan_before_the_session_wait(self):
        text = self.compact("runtime/session/PortSession.cs")
        start = text[text.index("IEnumeratorStart(){") :]
        self.assertTrue(
            start.startswith(
                'IEnumeratorStart(){if(File.Exists(System.IO.Path.Combine(Application.persistentDataPath,"whole-catalog-selection.json")))yieldbreak;'
            )
        )
        self.assertLess(start.index("yieldbreak;"), start.index("WaitForSeconds(8)"))

    def test_body_catalog_prepares_and_releases_the_composed_catalog(self):
        text = self.compact("runtime/catalog/BodyCatalogBoundary.cs")
        register = text[text.index("IEnumeratorRegisterBodyCatalog(){") :]
        self.assertIn(
            'if(Resources.Load<TextAsset>("WholeCatalogBootstrap")){varshared=WholeCatalogComposed.Prepare();'
            "while(shared.MoveNext())yieldreturnshared.Current;}",
            re.split(r"(?:void|IEnumerator|bool)[A-Z]\w*\(", register[1:], maxsplit=1)[0],
        )
        self.assertIn(
            'ReleaseObjectiveBundlePreload();CleanupRecoveredText();if(Resources.Load<TextAsset>("WholeCatalogBootstrap"))WholeCatalogComposed.Release();', text
        )

    def test_hooked_sources_are_compared_before_a_code_only_build(self):
        self.assertIn("Assets/LabLoadingScene/BodyCatalogBoundary.cs", build.WHOLE_PLAYER_INPUTS)
