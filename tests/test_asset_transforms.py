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
            self.assertEqual(transforms.check(self.work, self.root), {"total": 1, "identical": 1, "differences": []})
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()})
        target.write_bytes(b"changed")
        Path(str(target) + ".meta").unlink()
        result = transforms.check(self.work, self.root)
        self.assertEqual(result["identical"], 0)
        self.assertEqual(result["differences"], [self.asset["output"], self.asset["output"] + ".meta"])

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


if __name__ == "__main__":
    unittest.main()
