"""Synthetic contracts for migration-stage structural operations; no game payloads."""

import copy
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import asset_transforms as transforms

SOURCE = (
    "%YAML 1.1\n"
    "--- !u!1 &1\nGameObject:\n  m_Component:\n  - component: {fileID: 2}\n  - component: {fileID: 3}\n  m_Name: Root\n"
    "--- !u!4 &2\nTransform:\n  m_GameObject: {fileID: 1}\n  m_Father: {fileID: 0}\n"
    "--- !u!114 &3\nMonoBehaviour:\n  m_GameObject: {fileID: 1}\n"
    "  m_Script: {fileID: 1, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 3}\n"
    "  decal: {fileID: 4}  # retain\n"
    "  sounds:\n  - {fileID: 4}\n  - {fileID: 4}\n"
    "  action:\n    calls:\n    - target: {fileID: 4}\n      arguments:\n        object: {fileID: 4}\n    - target: {fileID: 4}\n"
)
OWNER = {"hierarchy_path": ["Root"], "class_id": 114, "script": {"fileID": 1, "guid": "a" * 32, "type": 3}, "occurrence": 0}


def null_operation(path=None):
    path = ["decal"] if path is None else path
    return {
        "op": "null_array_element" if any(type(key) is int for key in path) else "null_reference",
        "owner": copy.deepcopy(OWNER),
        "field_path": path,
        "expected_reference": {"fileID": 4},
        "expected_matches": 1,
    }


def addition(constructor="silent_projectile", position="first"):
    return {
        "op": "add_component",
        "constructor": constructor,
        "owner_file_id": 1,
        "id_seed_path": "Synthetic/Adapter.prefab",
        "script": {"fileID": 11500000, "guid": "642bd7a5ccd344f9d95e182b094fb1f6", "type": 3} if constructor == "silent_projectile" else None,
        "membership_position": position,
        "expected_matches": 1,
    }


class NullReferenceTests(unittest.TestCase):
    def test_scalar_null_preserves_comments_bytes_and_line_endings(self):
        for source in (SOURCE, SOURCE.replace("\n", "\r\n")):
            expected = source.replace("decal: {fileID: 4}", "decal: {fileID: 0}")
            self.assertEqual(transforms.apply_null_operation(source, null_operation()), expected)

    def test_null_array_index_retains_duplicate_reference_and_membership(self):
        expected = SOURCE.replace("  - {fileID: 4}\n  - {fileID: 4}", "  - {fileID: 4}\n  - {fileID: 0}")
        self.assertEqual(transforms.apply_null_operation(SOURCE, null_operation(["sounds", 1])), expected)

    def test_nested_array_mapping_first_key_and_nested_argument(self):
        for path, old in (
            (["action", "calls", 1, "target"], "    - target: {fileID: 4}\n---"),
            (["action", "calls", 0, "arguments", "object"], "        object: {fileID: 4}"),
        ):
            source = SOURCE + "--- !u!114 &5\nMonoBehaviour:\n"
            expected = source.replace(old, old.replace("{fileID: 4}", "{fileID: 0}"))
            self.assertNotEqual(source, expected)
            self.assertEqual(transforms.apply_null_operation(source, null_operation(path)), expected)

    def test_indented_sequence_and_crlf(self):
        source = SOURCE.replace("  - {fileID: 4}", "    - {fileID: 4}").replace("\n", "\r\n")
        expected = source.replace("    - {fileID: 4}", "    - {fileID: 0}", 1)
        self.assertEqual(transforms.apply_null_operation(source, null_operation(["sounds", 0])), expected)

    def test_component_occurrence_selects_only_second_record(self):
        second = SOURCE[SOURCE.index("--- !u!114") :].replace("&3", "&5")
        operation = null_operation()
        operation["owner"]["occurrence"] = 1
        self.assertEqual(transforms.apply_null_operation(SOURCE + second, operation), SOURCE + second.replace("decal: {fileID: 4}", "decal: {fileID: 0}"))

    def test_duplicate_hierarchy_requires_explicit_occurrence(self):
        second = SOURCE.replace("&1\n", "&11\n").replace("&2\n", "&12\n").replace("&3\n", "&13\n")
        second = second.replace("m_GameObject: {fileID: 1}", "m_GameObject: {fileID: 11}")
        second = second.replace("component: {fileID: 2}", "component: {fileID: 12}").replace("component: {fileID: 3}", "component: {fileID: 13}")
        second = second[second.index("--- !u!1") :]
        source = SOURCE + second
        with self.assertRaisesRegex(RuntimeError, "owner must match exactly once"):
            transforms.apply_null_operation(source, null_operation())
        operation = null_operation()
        operation["owner"]["hierarchy_occurrence"] = 1
        self.assertEqual(transforms.apply_null_operation(source, operation), SOURCE + second.replace("decal: {fileID: 4}", "decal: {fileID: 0}"))
        for occurrence in (-1, True, 2):
            operation["owner"]["hierarchy_occurrence"] = occurrence
            with self.subTest(occurrence=occurrence), self.assertRaises(RuntimeError):
                transforms.apply_null_operation(source, operation)
        field = {
            "op": "set_field",
            "owner": dict(OWNER, hierarchy_occurrence=1),
            "field_path": ["decal"],
            "value": {"type": "reference", "value": {"fileID": 0}},
            "expected_matches": 1,
        }
        self.assertEqual(transforms.apply_field_operation(source, field), SOURCE + second.replace("decal: {fileID: 4}", "decal: {fileID: 0}"))

    def test_precondition_and_external_references_are_rejected(self):
        for old in ("{fileID: 0}", "{fileID: 5}", "{fileID: 4, guid: " + "b" * 32 + ", type: 3}"):
            source = SOURCE.replace("decal: {fileID: 4}", "decal: " + old)
            with self.subTest(old=old), self.assertRaisesRegex(RuntimeError, "precondition"):
                transforms.apply_null_operation(source, null_operation())

    def test_schema_indices_counts_and_null_precondition_are_strict(self):
        changes = [
            {"op": "null_array_element"},
            {"field_path": ["sounds", -1]},
            {"field_path": ["sounds", True]},
            {"field_path": ["bad\nfield"]},
            {"expected_matches": 2},
            {"expected_matches": True},
            {"expected_reference": {"fileID": 0}},
            {"expected_reference": {"fileID": 4, "guid": "a" * 32, "type": 3}},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                transforms.apply_null_operation(SOURCE, dict(null_operation(), **change))

    def test_missing_duplicate_and_wrong_shape_paths_fail(self):
        for source, path in (
            (SOURCE, ["missing"]),
            (SOURCE.replace("  decal: {fileID: 4}", "  decal: {fileID: 4}\n  decal: {fileID: 4}"), ["decal"]),
            (SOURCE, ["sounds", 2]),
            (SOURCE, ["decal", "child"]),
            (SOURCE, ["action", 0]),
            (SOURCE, ["sounds"]),
        ):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                transforms.apply_null_operation(source, null_operation(path))

    def test_explicit_null_then_remove_has_no_dangling_local_reference(self):
        source = SOURCE.replace("  - component: {fileID: 3}\n", "  - component: {fileID: 3}\n  - component: {fileID: 4}\n")
        source += "--- !u!114 &4\nMonoBehaviour:\n  m_GameObject: {fileID: 1}\n"
        for path in (
            ["decal"],
            ["sounds", 0],
            ["sounds", 1],
            ["action", "calls", 0, "target"],
            ["action", "calls", 0, "arguments", "object"],
            ["action", "calls", 1, "target"],
        ):
            source = transforms.apply_null_operation(source, null_operation(path))
        result = transforms.apply_removal_operation(source, {"op": "remove_components", "file_ids": [4], "expected_matches": 1})
        self.assertNotIn("{fileID: 4}", result)
        self.assertNotIn("&4", result)


class ComponentAdditionTests(unittest.TestCase):
    def test_both_constructors_use_sanitizer_hash_ids_and_typed_bodies(self):
        for constructor, base, token, class_id, typename in (
            ("silent_projectile", 8000000000000000, "|silent|", 114, "MonoBehaviour"),
            ("empty_mesh_renderer", 7000000000000000, "|", 23, "MeshRenderer"),
        ):
            op = addition(constructor)
            fid = base + int(hashlib.sha256((op["id_seed_path"] + token + "1").encode()).hexdigest()[:12], 16)
            result = transforms.apply_addition_operation(SOURCE, op)
            self.assertIn(f"--- !u!{class_id} &{fid}\n{typename}:\n", result)
            self.assertIn(f"  m_Component:\n  - component: {{fileID: {fid}}}\n  - component: {{fileID: 2}}", result)
            self.assertIn("  m_GameObject: {fileID: 1}\n", result)
            if class_id == 23:
                self.assertTrue(result.endswith("  m_Enabled: 0\n  m_CastShadows: 0\n  m_ReceiveShadows: 0\n  m_Materials: []\n"))
            else:
                self.assertTrue(result.endswith("  m_Name:\n  m_EditorClassIdentifier:\n"))
                self.assertIn("  m_Script: {fileID: 11500000, guid: 642bd7a5ccd344f9d95e182b094fb1f6, type: 3}", result)
            # Aside from the single inserted membership, source bytes are untouched.
            self.assertEqual(result[: result.rindex(f"--- !u!{class_id} &{fid}")].replace(f"  - component: {{fileID: {fid}}}\n", ""), SOURCE)

    def test_append_membership_and_crlf(self):
        source = SOURCE.replace("\n", "\r\n")
        result = transforms.apply_addition_operation(source, addition(position="last"))
        self.assertRegex(result, r"component: \{fileID: 3\}\r\n  - component: \{fileID: 8\d+\}\r\n  m_Name")
        self.assertNotIn("\n", result.replace("\r\n", ""))

    def test_collision_increments_over_every_existing_record(self):
        initial = transforms.apply_addition_operation(SOURCE, addition())
        fid = int(re.findall(r"^--- !u!114 &(\d+)", initial, re.M)[-1])
        source = SOURCE + f"--- !u!29 &{fid}\nOcclusionCullingSettings:\n--- !u!29 &{fid + 1}\nOcclusionCullingSettings:\n"
        result = transforms.apply_addition_operation(source, addition())
        self.assertIn(f"--- !u!114 &{fid + 2}\n", result)

    def test_deterministic_and_recipe_immutable(self):
        op = addition()
        before = copy.deepcopy(op)
        self.assertEqual(transforms.apply_addition_operation(SOURCE, op), transforms.apply_addition_operation(SOURCE, op))
        self.assertEqual(before, op)

    def test_duplicate_component_and_duplicate_record_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "already present"):
            transforms.apply_addition_operation(transforms.apply_addition_operation(SOURCE, addition()), addition())
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            transforms.apply_addition_operation(SOURCE + "--- !u!1 &1\nGameObject:\n", addition())

    def test_bad_constructor_owner_seed_script_and_position_rejected(self):
        for change in (
            {"constructor": "arbitrary"},
            {"owner_file_id": 0},
            {"owner_file_id": True},
            {"owner_file_id": 2},
            {"owner_file_id": 99},
            {"id_seed_path": "../outside.prefab"},
            {"id_seed_path": "/outside.prefab"},
            {"id_seed_path": "a//b.prefab"},
            {"script": {"fileID": 1, "guid": "a" * 32, "type": 3}},
            {"membership_position": "middle"},
            {"expected_matches": 0},
        ):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                transforms.apply_addition_operation(SOURCE, dict(addition(), **change))

    def test_missing_membership_and_unterminated_record_rejected(self):
        for source in (SOURCE.replace("  m_Component:\n", ""), SOURCE.rstrip()):
            with self.assertRaises(RuntimeError):
                transforms.apply_addition_operation(source, addition())


class SettingsAndRetainedMembershipTests(unittest.TestCase):
    def test_retained_slot_is_explicit_and_keeps_membership_order(self):
        op = {"op": "remove_components", "file_ids": [3], "expected_matches": 1, "retain_null_slots": [3]}
        result = transforms.apply_removal_operation(SOURCE, op)
        expected = SOURCE[: SOURCE.index("--- !u!114")].replace("component: {fileID: 3}", "component: {fileID: 0}")
        self.assertEqual(result, expected)
        for retained in ([4], [3, 3], [True], "3"):
            with self.subTest(retained=retained), self.assertRaises(RuntimeError):
                transforms.apply_removal_operation(SOURCE, dict(op, retain_null_slots=retained))

    def test_retained_slot_still_requires_the_correct_unique_membership(self):
        source = SOURCE.replace("  - component: {fileID: 3}\n", "")
        with self.assertRaisesRegex(RuntimeError, "exactly once"):
            transforms.apply_removal_operation(source, {"op": "remove_components", "file_ids": [3], "expected_matches": 1, "retain_null_slots": [3]})

    def test_scene_settings_removal_preserves_all_other_bytes(self):
        op = {"op": "remove_scene_settings", "records": [{"file_id": 4, "class_id": 29}, {"file_id": 5, "class_id": 196}], "expected_matches": 2}
        source = SOURCE + "--- !u!29 &4\nOcclusionCullingSettings:\n  keep: 37\n--- !u!196 &5\nNavMeshSettings:\n"
        # Remove source references first, as required by the independent operation.
        source = source.replace("{fileID: 4}", "{fileID: 0}")
        self.assertEqual(transforms.apply_scene_settings_operation(source, op), SOURCE.replace("{fileID: 4}", "{fileID: 0}"))

    def test_settings_reject_wrong_class_owned_records_and_dangling_reference(self):
        op = {"op": "remove_scene_settings", "records": [{"file_id": 4, "class_id": 29}], "expected_matches": 1}
        for block in (
            "--- !u!104 &4\nRenderSettings:\n",
            "--- !u!29 &4\nOcclusionCullingSettings:\n  m_GameObject: {fileID: 1}\n",
            "--- !u!29 &4\nOcclusionCullingSettings:\n",
        ):
            with self.subTest(block=block), self.assertRaises(RuntimeError):
                transforms.apply_scene_settings_operation(SOURCE + block, op)

    def test_settings_schema_refuses_hierarchy_and_invalid_counts(self):
        op = {"op": "remove_scene_settings", "records": [{"file_id": 4, "class_id": 29}], "expected_matches": 1}
        for change in (
            {"expected_matches": 0},
            {"expected_matches": True},
            {"records": [{"file_id": 4, "class_id": 1}]},
            {"records": [{"file_id": 0, "class_id": 29}]},
        ):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                transforms.apply_scene_settings_operation(SOURCE, dict(op, **change))

    def test_generate_dispatches_new_operations(self):
        source = SOURCE.encode()
        operations = [null_operation(), null_operation(["sounds", 0]), addition()]
        asset = {"source": "Assets/Synthetic.prefab", "source_sha256": hashlib.sha256(source).hexdigest(), "operations": operations}
        result = transforms.generate(source, asset)
        self.assertIn("decal: {fileID: 0}", result)
        self.assertIn("sounds:\n  - {fileID: 0}", result)
        self.assertIn("guid: 642bd7a5ccd344f9d95e182b094fb1f6", result)


class StructuralIntegrationTests(unittest.TestCase):
    def test_cached_field_edits_match_sequential_execution(self):
        operations = [null_operation(), null_operation(["sounds", 1]), null_operation(["action", "calls", 0, "target"])]
        asset = {"source": "Assets/Synthetic.prefab", "source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(), "operations": operations}
        expected = SOURCE
        for operation in operations:
            expected = transforms.apply_null_operation(expected, operation)
        self.assertEqual(transforms.generate(SOURCE.encode(), asset), expected)

    def test_owner_rename_flushes_the_selector_index(self):
        operations = [
            null_operation(),
            {
                "op": "set_field",
                "owner": {"hierarchy_path": ["Root"], "class_id": 1, "script": None, "occurrence": 0},
                "field_path": ["m_Name"],
                "value": {"type": "string", "value": "Renamed"},
                "expected_matches": 1,
            },
            dict(null_operation(["sounds", 0]), owner=dict(OWNER, hierarchy_path=['"Renamed"'])),
        ]
        asset = {"source": "Assets/Synthetic.prefab", "source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(), "operations": operations}
        result = transforms.generate(SOURCE.encode(), asset)
        self.assertIn('m_Name: "Renamed"', result)
        self.assertIn("sounds:\n  - {fileID: 0}", result)

    def test_scene_stage_generates_new_operations_without_history_or_writes(self):
        import composition_migration

        source = SOURCE + "--- !u!196 &5\nNavMeshSettings:\n"
        operations = [
            null_operation(),
            null_operation(["sounds", 1]),
            {"op": "remove_scene_settings", "records": [{"file_id": 5, "class_id": 196}], "expected_matches": 1},
            addition(),
        ]
        asset = {
            "source": "Assets/Synthetic.unity",
            "output": "Assets/WholeGame/Synthetic.unity",
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "operations": operations,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = root / "export"
            path = export / asset["source"]
            path.parent.mkdir(parents=True)
            path.write_text(source)
            meta = b"fileFormatVersion: 2\nguid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
            Path(str(path) + ".meta").write_bytes(meta)
            data, generated_meta = transforms.generate_asset(export, asset)
            row = {
                "source": asset["source"],
                "target": asset["output"],
                "current_source_sha256": asset["source_sha256"],
                "output_sha": hashlib.sha256(data).hexdigest(),
            }
            with (
                patch.object(Path, "write_bytes", side_effect=AssertionError("read only")),
                patch.object(Path, "write_text", side_effect=AssertionError("read only")),
            ):
                result = composition_migration.prepare_asset_transforms(
                    {"rows": [row]},
                    {asset["output"]: asset},
                    export,
                    root / "missing-previous",
                    root / "missing-preview",
                    root / "project",
                    {asset["source"]: "b" * 32},
                )
            self.assertEqual(result, {asset["output"]: (data, meta)})
            self.assertNotIn(b"NavMeshSettings", data)
            self.assertEqual(transforms.structural_kind(asset), "scene_settings_and_references")
