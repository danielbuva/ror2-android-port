import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import asset_transforms as transforms
from common import write

SOURCE = (
    "%YAML 1.1\n--- !u!114 &11400000\nMonoBehaviour:\n"
    "  m_Name: SyntheticSurface\n"
    "  impactEffectPrefab: {fileID: 1, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 2}\n"
    "  footstepEffectPrefab: {fileID: 2}\n"
    "  isSlippery: 0\n"
    "  impactSoundString: SyntheticImpact\n"
    "  materialSwitchString: SyntheticMaterial\n"
).encode()
META = b"fileFormatVersion: 2\nguid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nSyntheticImporter:\n  fixture: 1\n"


def entry(source=SOURCE):
    return {
        "source": "Assets/SyntheticSurface.asset",
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "output": "Assets/WholeGame/SyntheticSurface.asset",
        "operations": copy.deepcopy(list(transforms.SURFACE_OPERATIONS)),
    }


class AssetTransformsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / "work"
        self.export = self.work / "export"
        self.project = self.work / "lab-project"
        self.asset = entry()
        self.recipe = self.root / "recipe"
        write(self.recipe / "asset-transforms.json", {"schema_version": 1, "input_id": "synthetic-input", "assets": [self.asset]})
        patcher = patch.object(transforms, "RECIPE", self.recipe)
        patcher.start()
        self.addCleanup(patcher.stop)
        source = transforms.asset_path(self.export, self.asset["source"])
        source.parent.mkdir(parents=True)
        source.write_bytes(SOURCE)
        Path(str(source) + ".meta").write_bytes(META)

    def test_operations_clear_only_selected_fields_and_preserve_other_bytes(self):
        result = transforms.generate(SOURCE, self.asset)
        self.assertEqual(
            result,
            "%YAML 1.1\n--- !u!114 &11400000\nMonoBehaviour:\n"
            "  m_Name: SyntheticSurface\n  impactEffectPrefab: {fileID: 0}\n"
            "  footstepEffectPrefab: {fileID: 0}\n  isSlippery: 0\n"
            "  impactSoundString:\n  materialSwitchString:\n",
        )

    def test_source_hash_mismatch_fails(self):
        with self.assertRaisesRegex(RuntimeError, "source hash mismatch"):
            transforms.generate(SOURCE + b"\n", self.asset)

    def test_unknown_field_or_value_or_operation_fails(self):
        for update in ({"field": "unreviewed"}, {"value": "payload"}, {"op": "unknown"}):
            asset = copy.deepcopy(self.asset)
            asset["operations"][0].update(update)
            with self.subTest(update=update), self.assertRaisesRegex(RuntimeError, "Unknown field"):
                transforms.generate(SOURCE, asset)

    def test_missing_or_duplicate_field_fails(self):
        for source in (SOURCE.replace(b"  materialSwitchString: SyntheticMaterial\n", b""), SOURCE + b"  impactSoundString: duplicate\n"):
            with self.subTest(source=source), self.assertRaisesRegex(RuntimeError, "exactly once"):
                transforms.generate(source, entry(source))

    def test_multiple_records_or_missing_marker_fail(self):
        for source in (SOURCE + b"--- !u!114 &2\nMonoBehaviour:\n", SOURCE.replace(b"  isSlippery: 0\n", b"")):
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                transforms.generate(source, entry(source))

    def test_deterministic_without_mutating_recipe_or_source(self):
        before = copy.deepcopy(self.asset)
        results = [transforms.generate_asset(self.export, self.asset) for _ in range(3)]
        self.assertEqual(results, [results[0]] * 3)
        self.assertEqual(self.asset, before)
        self.assertEqual((self.export / self.asset["source"]).read_bytes(), SOURCE)
        self.assertEqual(results[0][1], META)

    def test_metadata_uses_export_and_changes_only_guid_when_requested(self):
        _, meta = transforms.generate_asset(self.export, self.asset, "c" * 32)
        self.assertEqual(meta, META.replace(b"b" * 32, b"c" * 32))
        Path(str(self.export / self.asset["source"]) + ".meta").write_bytes(b"no guid\n")
        with self.assertRaisesRegex(RuntimeError, "GUID missing"):
            transforms.generate_asset(self.export, self.asset)

    def test_recipe_rejects_input_schema_duplicates_paths_and_operations(self):
        path = self.recipe / "asset-transforms.json"
        valid = json.loads(path.read_text())
        invalid = [dict(valid, input_id="other"), dict(valid, schema_version=2), dict(valid, assets=[self.asset, self.asset])]
        for field, value in (("source", "../escape.asset"), ("output", "/outside.asset"), ("operations", []), ("source_sha256", "bad")):
            asset = dict(self.asset, **{field: value})
            invalid.append(dict(valid, assets=[asset]))
        for recipe in invalid:
            write(path, recipe)
            with self.subTest(recipe=recipe), self.assertRaises(RuntimeError):
                transforms.load_recipe("synthetic-input")

    def prepare_check(self):
        write(self.work / "config/accepted-input.json", {"input_id": "synthetic-input"})
        write(self.work / "config/reconstruction.json", {"input_id": "synthetic-input", "projects": ["work/export"]})
        write(self.project / ".port-input.json", {"input_id": "synthetic-input"})
        target = transforms.asset_path(self.project, self.asset["output"])
        target.parent.mkdir(parents=True)
        target.write_bytes(transforms.generate(SOURCE, self.asset).encode())
        Path(str(target) + ".meta").write_bytes(META)
        return target

    def test_check_is_read_only_and_reports_asset_and_meta_differences(self):
        target = self.prepare_check()
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with (
            patch.object(Path, "write_bytes", side_effect=AssertionError("must not write")),
            patch.object(Path, "write_text", side_effect=AssertionError("must not write")),
        ):
            self.assertEqual(transforms.check(self.work, self.root), {"total": 1, "identical": 1, "differences": [], "changed_later_in_project": []})
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()})
        target.write_bytes(b"changed")
        Path(str(target) + ".meta").unlink()
        result = transforms.check(self.work, self.root)
        self.assertEqual(result["identical"], 0)
        self.assertEqual(result["differences"], [self.asset["output"], self.asset["output"] + ".meta"])

    def test_check_uses_the_migration_preview_as_oracle(self):
        # Later current steps change some assets in the project; the stage output must still match.
        target = self.prepare_check()
        preview = self.work / "evidence/preview" / self.asset["output"]
        preview.parent.mkdir(parents=True)
        preview.write_bytes(target.read_bytes())
        write(self.work / "config/composition-migration.json", {"evidence": "work/evidence"})
        target.write_bytes(b"changed later by the dependency sanitizer")
        result = transforms.check(self.work, self.root)
        self.assertEqual((result["identical"], result["differences"]), (1, []))
        self.assertEqual(result["changed_later_in_project"], [self.asset["output"]])
        preview.write_bytes(b"different stage output")
        self.assertEqual(transforms.check(self.work, self.root)["differences"], [self.asset["output"]])

    def test_check_covers_surface_identity_and_general_field_assets(self):
        self.prepare_check()
        assets = [
            self.asset,
            prefab_entry(),
            dict(prefab_entry(operations=[{"op": "identity"}]), source="Assets/Synthetic.renderTexture", output="Assets/WholeGame/Synthetic.renderTexture"),
        ]
        for asset in assets[1:]:
            source = transforms.asset_path(self.export, asset["source"])
            source.write_bytes(PREFAB)
            Path(str(source) + ".meta").write_bytes(META)
            target = transforms.asset_path(self.project, asset["output"])
            target.write_bytes(transforms.generate(PREFAB, asset).encode())
            Path(str(target) + ".meta").write_bytes(META)
        write(self.recipe / "asset-transforms.json", {"schema_version": 1, "input_id": "synthetic-input", "assets": assets})
        self.assertEqual(transforms.check(self.work, self.root), {"total": 3, "identical": 3, "differences": [], "changed_later_in_project": []})
        for asset in assets:
            transforms.asset_path(self.project, asset["output"]).write_bytes(b"drift")
        self.assertEqual(
            transforms.check(self.work, self.root),
            {"total": 3, "identical": 0, "differences": [asset["output"] for asset in assets], "changed_later_in_project": []},
        )

    def test_check_rejects_export_or_project_input_drift(self):
        self.prepare_check()
        for relative in ("config/reconstruction.json", "lab-project/.port-input.json"):
            path = self.work / relative
            original = json.loads(path.read_text())
            write(path, dict(original, input_id="other"))
            with self.subTest(path=relative), self.assertRaisesRegex(RuntimeError, "different accepted input"):
                transforms.check(self.work, self.root)
            write(path, original)

    def test_current_action_reports_and_returns_nonzero_on_differences(self):
        import actions

        action = next(action for action in actions._ENTRIES if action.name == "asset-transforms-check")
        self.assertEqual(action.status, "current")
        for differences in ([], ["Assets/SyntheticSurface.asset"]):
            result = {"total": 1, "identical": int(not differences), "differences": differences}
            with patch.object(transforms, "check", return_value=result), contextlib.redirect_stdout(io.StringIO()) as output:
                if differences:
                    with self.assertRaises(SystemExit) as failure:
                        transforms.check_action()
                    self.assertEqual(failure.exception.code, 1)
                else:
                    transforms.check_action()
            self.assertEqual(json.loads(output.getvalue()), result)


PREFAB = (
    "%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Name: SyntheticRoot\n  m_IsActive: 1\n"
    "--- !u!4 &2\nTransform:\n  m_GameObject: {fileID: 1}\n  m_Father: {fileID: 0}\n"
    "--- !u!114 &3\nMonoBehaviour:\n  m_GameObject: {fileID: 1}\n"
    "  m_Script: {fileID: 11500000, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 3}\n"
    "  settings:\n    enabled: 1\n    keep: 37\n  keep: untouched\n"
).encode()


def field_operation():
    return {
        "op": "set_field",
        "owner": {"hierarchy_path": ["SyntheticRoot"], "class_id": 1, "script": None, "occurrence": 0},
        "field_path": ["m_IsActive"],
        "value": {"type": "int", "value": 0},
        "expected_matches": 1,
    }


def prefab_entry(source=PREFAB, operations=None):
    return dict(
        entry(source),
        source="Assets/Synthetic.prefab",
        output="Assets/WholeGame/Synthetic.prefab",
        operations=[field_operation()] if operations is None else operations,
    )


class GeneralAssetOperationTests(unittest.TestCase):
    def test_field_match_preserves_every_other_byte_including_crlf(self):
        for data in (PREFAB, PREFAB.replace(b"\n", b"\r\n")):
            with self.subTest(crlf=b"\r" in data):
                self.assertEqual(transforms.generate(data, prefab_entry(data)).encode(), data.replace(b"m_IsActive: 1", b"m_IsActive: 0"))

    def test_comments_and_trailing_spaces_are_untouched(self):
        for value in (b"1   # keep this comment", b"1   ", b'"quoted # value"  # keep this comment', b"'single # value'  # keep this comment"):
            data = PREFAB.replace(b"m_IsActive: 1", b"m_IsActive: " + value)
            end = transforms.scalar_end(value.decode())
            self.assertEqual(transforms.generate(data, prefab_entry(data)).encode(), data.replace(b"m_IsActive: " + value, b"m_IsActive: 0" + value[end:]))

    def test_zero_and_multiple_field_matches_fail(self):
        for data in (PREFAB.replace(b"  m_IsActive: 1\n", b""), PREFAB.replace(b"  m_IsActive: 1\n", b"  m_IsActive: 1\n  m_IsActive: 1\n")):
            with self.subTest(data=data), self.assertRaisesRegex(RuntimeError, "exactly once"):
                transforms.generate(data, prefab_entry(data))

    def test_missing_and_duplicate_hierarchy_owner_fail(self):
        operation = field_operation()
        operation["owner"]["hierarchy_path"] = ["Missing"]
        with self.assertRaisesRegex(RuntimeError, "owner must match exactly once"):
            transforms.generate(PREFAB, prefab_entry(operations=[operation]))
        data = PREFAB + b"--- !u!1 &4\nGameObject:\n  m_Name: SyntheticRoot\n  m_IsActive: 1\n"
        with self.assertRaisesRegex(RuntimeError, "owner must match exactly once"):
            transforms.generate(data, prefab_entry(data))

    def test_script_identity_occurrence_and_nested_path(self):
        operation = field_operation()
        operation["owner"].update(class_id=114, script={"fileID": 11500000, "guid": "a" * 32, "type": 3}, occurrence=1)
        operation["field_path"] = ["settings", "enabled"]
        operation["value"] = {"type": "bool", "value": False}
        duplicate = PREFAB[PREFAB.index(b"--- !u!114") :].replace(b"&3", b"&4")
        data = PREFAB + duplicate
        expected = PREFAB + duplicate.replace(b"enabled: 1", b"enabled: 0")
        self.assertEqual(transforms.generate(data, prefab_entry(data, [operation])).encode(), expected)
        for change in ({"occurrence": 2}, {"script": {"fileID": 11500000, "guid": "b" * 32, "type": 3}}):
            bad = copy.deepcopy(operation)
            bad["owner"].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, "component must match exactly once"):
                transforms.generate(data, prefab_entry(data, [bad]))

    def test_hierarchy_path_selects_child_and_leaves_root(self):
        data = PREFAB + (
            b"--- !u!1 &4\nGameObject:\n  m_Name: Child\n  m_IsActive: 1\n--- !u!4 &5\nTransform:\n  m_GameObject: {fileID: 4}\n  m_Father: {fileID: 2}\n"
        )
        operation = field_operation()
        operation["owner"]["hierarchy_path"].append("Child")
        result = transforms.generate(data, prefab_entry(data, [operation])).encode()
        self.assertEqual(result, data[: len(PREFAB)] + data[len(PREFAB) :].replace(b"m_IsActive: 1", b"m_IsActive: 0"))

    def test_typed_values_and_empty_field_spacing(self):
        for value, rendered in (
            ({"type": "float", "value": 0.5}, "0.5"),
            ({"type": "string", "value": "quoted:\nvalue"}, '"quoted:\\nvalue"'),
            ({"type": "reference", "value": {"fileID": 0}}, "{fileID: 0}"),
        ):
            operation = field_operation()
            operation["value"] = value
            data = PREFAB.replace(b"m_IsActive: 1", b"m_IsActive:")
            with self.subTest(value=value):
                self.assertEqual(
                    transforms.generate(data, prefab_entry(data, [operation])).encode(), data.replace(b"m_IsActive:", ("m_IsActive: " + rendered).encode())
                )

    def test_invalid_contract_and_value_types_fail(self):
        changes = [
            {"expected_matches": 0},
            {"expected_matches": 2},
            {"expected_matches": True},
            {"field_path": []},
            {"field_path": ["bad\nkey"]},
            {"value": {"type": "int", "value": True}},
            {"value": {"type": "float", "value": float("inf")}},
            {"value": {"type": "yaml", "value": "payload"}},
        ]
        for change in changes:
            operation = dict(field_operation(), **change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                transforms.generate(PREFAB, prefab_entry(operations=[operation]))

    def test_nested_zero_multiple_and_non_scalar_fail(self):
        operation = field_operation()
        operation["owner"].update(class_id=114, script={"fileID": 11500000, "guid": "a" * 32, "type": 3})
        operation["field_path"] = ["settings", "enabled"]
        for data in (PREFAB.replace(b"    enabled: 1\n", b""), PREFAB.replace(b"    enabled: 1\n", b"    enabled: 1\n    enabled: 1\n")):
            with self.subTest(data=data), self.assertRaisesRegex(RuntimeError, "exactly once"):
                transforms.generate(data, prefab_entry(data, [operation]))
        operation["field_path"] = ["settings"]
        with self.assertRaisesRegex(RuntimeError, "scalar"):
            transforms.generate(PREFAB, prefab_entry(operations=[operation]))

    def test_identity_copies_binary_source_and_meta_and_gates_hash(self):
        data = b"\xff\x00\r\nsynthetic binary"
        asset = prefab_entry(data, [{"op": "identity"}])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / asset["source"]
            source.parent.mkdir(parents=True)
            source.write_bytes(data)
            Path(str(source) + ".meta").write_bytes(META)
            self.assertEqual(transforms.generate_asset(directory, asset), (data, META))
            source.write_bytes(data + b"drift")
            with self.assertRaisesRegex(RuntimeError, "source hash mismatch"):
                transforms.generate_asset(directory, asset)

    def test_identity_is_exclusive_and_recipe_accepts_new_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipe.json"
            for extension in ("prefab", "renderTexture"):
                asset = prefab_entry(operations=[{"op": "identity"}])
                asset["source"] = "Assets/Synthetic." + extension
                asset["output"] = "Assets/WholeGame/Synthetic." + extension
                write(path, {"schema_version": 1, "input_id": "synthetic-input", "assets": [asset]})
                self.assertEqual(transforms.load_recipe("synthetic-input", path)["assets"], [asset])
            asset["operations"].append(field_operation())
            write(path, {"schema_version": 1, "input_id": "synthetic-input", "assets": [asset]})
            with self.assertRaises(RuntimeError):
                transforms.load_recipe("synthetic-input", path)

    def test_remapping_is_explicit_pinned_and_input_gated(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(transforms, "RECIPE", Path(directory)):
            path = Path(directory) / "hud-ui-remaps.json"
            write(path, {"input_id": "synthetic-input", "rows": [{"from": "untouched", "to": "normalized"}]})
            operation = {"op": "remap_references", "recipe": path.name, "recipe_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            asset = prefab_entry(operations=[operation, field_operation()])
            self.assertEqual(
                transforms.generate(PREFAB, asset).encode(), PREFAB.replace(b"untouched", b"normalized").replace(b"m_IsActive: 1", b"m_IsActive: 0")
            )
            transforms.validate_operations(asset["operations"], "synthetic-input")
            with self.assertRaisesRegex(RuntimeError, "different accepted input"):
                transforms.validate_operations(asset["operations"], "other")
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(RuntimeError, "recipe hash mismatch"):
                transforms.generate(PREFAB, asset)


REMOVAL_SOURCE = PREFAB.replace(
    b"  m_Name: SyntheticRoot\n", b"  m_Component:\n  - component: {fileID: 2}\n  - component: {fileID: 3}\n  m_Name: SyntheticRoot\n"
)


def removal_operation(*ids):
    return {"op": "remove_components", "file_ids": list(ids or (3,)), "expected_matches": len(ids or (3,))}


class ComponentRemovalTests(unittest.TestCase):
    def test_removes_only_records_and_memberships_preserving_line_endings(self):
        for source in (REMOVAL_SOURCE, REMOVAL_SOURCE.replace(b"\n", b"\r\n")):
            newline = b"\r\n" if b"\r" in source else b"\n"
            asset = prefab_entry(source, [removal_operation()])
            expected = source[: source.index(b"--- !u!114")].replace(b"  - component: {fileID: 3}" + newline, b"")
            before = copy.deepcopy(asset)
            self.assertEqual(transforms.generate(source, asset).encode(), expected)
            self.assertEqual(transforms.generate(source, asset).encode(), expected)
            self.assertEqual(asset, before)

    def test_rejects_invalid_identifiers_counts_and_payloads(self):
        for update in (
            {"file_ids": []},
            {"file_ids": [3, 3], "expected_matches": 2},
            {"file_ids": [True]},
            {"file_ids": [0]},
            {"file_ids": [2**63]},
            {"file_ids": ["3"]},
            {"expected_matches": 0},
            {"expected_matches": True},
            {"yaml": "unreviewed"},
        ):
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                transforms.generate(REMOVAL_SOURCE, prefab_entry(REMOVAL_SOURCE, [dict(removal_operation(), **update)]))

    def test_rejects_absent_records_hierarchy_objects_and_scene_settings(self):
        for fid in (99, 1, 2, 4):
            source = REMOVAL_SOURCE + b"--- !u!29 &4\nOcclusionCullingSettings:\n  serializedVersion: 2\n"
            with self.subTest(fid=fid), self.assertRaises(RuntimeError):
                transforms.generate(source, prefab_entry(source, [removal_operation(fid)]))

    def test_requires_one_membership_with_correct_owner(self):
        member = b"  - component: {fileID: 3}\n"
        for source in (
            REMOVAL_SOURCE.replace(member, b""),
            REMOVAL_SOURCE.replace(member, member * 2),
            REMOVAL_SOURCE.replace(b"  m_GameObject: {fileID: 1}\n  m_Script", b"  m_GameObject: {fileID: 99}\n  m_Script"),
            REMOVAL_SOURCE + b"--- !u!1 &4\nGameObject:\n  m_Component:\n" + member,
        ):
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                transforms.generate(source, prefab_entry(source, [removal_operation()]))

    def test_dangling_local_references_fail_but_external_file_ids_are_untouched(self):
        for reference in (b"{fileID: 3}", b"{fileID: 3, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 3}"):
            source = REMOVAL_SOURCE.replace(b"  m_IsActive: 1", b"  reference: " + reference + b"\n  m_IsActive: 1")
            asset = prefab_entry(source, [removal_operation()])
            if b"guid:" in reference:
                self.assertIn(reference, transforms.generate(source, asset).encode())
            else:
                with self.assertRaisesRegex(RuntimeError, "surviving local reference"):
                    transforms.generate(source, asset)

    def test_removed_components_may_reference_each_other(self):
        source = REMOVAL_SOURCE.replace(b"  - component: {fileID: 3}\n", b"  - component: {fileID: 3}\n  - component: {fileID: 4}\n")
        duplicate = source[source.index(b"--- !u!114") :].replace(b"&3", b"&4") + b"  peer: {fileID: 3}\n"
        source += duplicate
        asset = prefab_entry(source, [removal_operation(3, 4)])
        result = transforms.generate(source, asset)
        self.assertNotIn("MonoBehaviour:", result)
        self.assertIn("  - component: {fileID: 2}\n", result)

    def test_check_reports_removal_cohort_and_stage_preparation_needs_no_history(self):
        import composition_migration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, export, project = root / "work", root / "work/export", root / "work/lab-project"
            recipe = root / "recipe"
            asset = prefab_entry(REMOVAL_SOURCE, [removal_operation()])
            source = transforms.asset_path(export, asset["source"])
            source.parent.mkdir(parents=True)
            source.write_bytes(REMOVAL_SOURCE)
            Path(str(source) + ".meta").write_bytes(META)
            data, meta = transforms.generate_asset(export, asset)
            row = dict(
                source=asset["source"],
                target=asset["output"],
                current_source_sha256=asset["source_sha256"],
                output_sha=hashlib.sha256(data).hexdigest(),
                target_before_sha256=asset["source_sha256"],
            )
            args = ({"rows": [row]}, {asset["output"]: asset}, export, root / "absent-previous", root / "absent-preview", project, {asset["source"]: "b" * 32})
            with patch.object(Path, "write_bytes", side_effect=AssertionError("must not write")):
                self.assertEqual(composition_migration.prepare_asset_transforms(*args), {asset["output"]: (data, meta)})
            for update in (
                {"output_sha": "a" * 64},
                {"current_source_sha256": "a" * 64},
                {"source": "Assets/Missing.prefab"},
            ):
                bad_args = ({"rows": [dict(row, **update)]}, *args[1:])
                with self.subTest(update=update), self.assertRaises((RuntimeError, FileNotFoundError)):
                    composition_migration.prepare_asset_transforms(*bad_args)
            with self.assertRaisesRegex(RuntimeError, "omits recipe"):
                composition_migration.prepare_asset_transforms({"rows": []}, *args[1:])
            with self.assertRaisesRegex(RuntimeError, "Duplicate transformed"):
                composition_migration.prepare_asset_transforms({"rows": [row, row]}, *args[1:])
            target = transforms.asset_path(project, asset["output"])
            target.parent.mkdir(parents=True)
            target.write_bytes(data)
            Path(str(target) + ".meta").write_bytes(meta)
            write(work / "config/accepted-input.json", {"input_id": "synthetic-input"})
            write(work / "config/reconstruction.json", {"input_id": "synthetic-input", "projects": ["work/export"]})
            write(project / ".port-input.json", {"input_id": "synthetic-input"})
            write(recipe / "asset-transforms.json", {"schema_version": 1, "input_id": "synthetic-input", "assets": [asset]})
            with patch.object(transforms, "RECIPE", recipe):
                self.assertEqual(transforms.check(work, root)["component_removal_cohort"], {"total": 1, "identical": 1, "components": 1})
                target.write_bytes(b"drift")
                self.assertEqual(transforms.check(work, root)["component_removal_cohort"]["identical"], 0)

    def test_unconverted_stage_rows_still_require_both_historical_assets(self):
        import composition_migration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Assets/Synthetic.prefab"
            source.parent.mkdir()
            source.write_bytes(REMOVAL_SOURCE)
            row = dict(
                source="Assets/Synthetic.prefab",
                target="Assets/WholeGame/Synthetic.prefab",
                old="Assets/Previous.prefab",
                current_source_sha256=hashlib.sha256(REMOVAL_SOURCE).hexdigest(),
                output_sha="a" * 64,
                previous_adapted_sha256="b" * 64,
            )
            args = ({"rows": [row]}, {}, root, root / "previous", root / "evidence", root / "project", {})
            with self.assertRaises(FileNotFoundError):
                composition_migration.prepare_asset_transforms(*args)
            preview = root / "evidence/preview" / row["target"]
            preview.parent.mkdir(parents=True)
            preview.write_bytes(b"wrong output")
            with self.assertRaisesRegex(RuntimeError, "provenance drift"):
                composition_migration.prepare_asset_transforms(*args)
            row["output_sha"] = hashlib.sha256(preview.read_bytes()).hexdigest()
            with self.assertRaises(FileNotFoundError):
                composition_migration.prepare_asset_transforms(*args)


if __name__ == "__main__":
    unittest.main()
