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
import authored_additions as additions
from common import write
from composition_migration import stage_addition


class AuthoredAdditionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.recipe_path = self.root / "recipe/authored-additions.json"
        self.data = b'Shader "Synthetic" {}\n'
        self.asset = {
            "source": "tools/unity/runtime/shaders/Synthetic.shader",
            "source_sha256": hashlib.sha256(self.data).hexdigest(),
            "output": "Assets/LabLoadingScene/Resources/Synthetic.shader",
            "guid": "a" * 32,
        }
        self.recipe = {"schema_version": 1, "assets": [self.asset]}
        source = self.root / self.asset["source"]
        source.parent.mkdir(parents=True)
        source.write_bytes(self.data)
        write(self.recipe_path, self.recipe)
        patcher = patch.object(additions, "RECIPE", self.recipe_path.parent)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.row = {"old": self.asset["output"], "guid": self.asset["guid"], "target": "Assets/Relocated.shader"}

    def test_shader_and_include_importer_bytes(self):
        data, meta = additions.generate_asset(self.asset, self.root)
        self.assertEqual(data, self.data)
        self.assertEqual(
            meta,
            (
                "fileFormatVersion: 2\nguid: " + "a" * 32 + "\nShaderImporter:\n  externalObjects: {}\n"
                "  defaultTextures: []\n  nonModifiableTextures: []\n  preprocessorOverride: 0\n"
                "  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
            ).encode(),
        )
        asset = dict(self.asset, source=self.asset["source"].replace(".shader", ".cginc"))
        (self.root / asset["source"]).write_bytes(self.data)
        _, include = additions.generate_asset(asset, self.root)
        self.assertIn(b"ShaderIncludeImporter:\n", include)
        self.assertNotIn(b"defaultTextures", include)
        self.assertTrue(include.endswith(b"  assetBundleVariant: \n"))

    def test_source_drift_and_symlink_escape_fail(self):
        source = self.root / self.asset["source"]
        source.write_bytes(b"drift")
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            additions.generate_asset(self.asset, self.root)
        source.unlink()
        source.symlink_to(self.root.parent / "outside.shader")
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            additions.generate_asset(self.asset, self.root)

    def test_recipe_rejects_invalid_paths_identity_and_duplicates(self):
        invalid = [dict(self.recipe, schema_version=2), dict(self.recipe, assets=[]), dict(self.recipe, assets=[self.asset, self.asset])]
        for key, value in (
            ("source", "tools/unity/runtime/shaders/../../secret.shader"),
            ("source", "/outside.shader"),
            ("output", "Assets/LabLoadingScene/Resources/../Other.shader"),
            ("output", "Assets/LabLoadingScene/Resources/Different.shader"),
            ("guid", "bad"),
            ("source_sha256", "bad"),
        ):
            invalid.append(dict(self.recipe, assets=[dict(self.asset, **{key: value})]))
        for recipe in invalid:
            write(self.recipe_path, recipe)
            with self.subTest(recipe=recipe), self.assertRaises(RuntimeError):
                additions.load_recipe()

    def test_prepare_and_stage_never_read_history_and_allow_relocation(self):
        before = copy.deepcopy(self.recipe)
        prepared = additions.prepare([self.row], additions.load_recipe(), self.root)
        previous = self.root / "nonexistent-history"
        with patch.object(Path, "read_bytes", side_effect=AssertionError("history read")):
            stage_addition(self.row, prepared, previous, self.root / "project", {}, {"rows": []})
        target = self.root / "project" / self.row["target"]
        self.assertEqual(target.read_bytes(), self.data)
        self.assertEqual(Path(str(target) + ".meta").read_bytes(), prepared[self.row["old"]][1])
        self.assertFalse(previous.exists())
        self.assertEqual(self.recipe, before)

    def test_prepare_fails_on_missing_duplicate_or_wrong_identity(self):
        for rows in ([], [self.row, self.row], [dict(self.row, guid="b" * 32)]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                additions.prepare(rows, self.recipe, self.root)

    def prepare_check(self):
        work = self.root / "work"
        write(work / "config/accepted-input.json", {"input_id": "synthetic"})
        write(work / "config/composition-migration.json", {"input_id": "synthetic", "previous_project": "work/previous", "evidence": "work/evidence"})
        write(work / "evidence/rebase-analysis.json", {"guidmap": {}})
        write(self.recipe_path.parent / "hud-ui-remaps.json", {"input_id": "synthetic", "rows": []})
        source = work / "previous" / self.asset["output"]
        source.parent.mkdir(parents=True)
        data, meta = additions.generate_asset(self.asset, self.root)
        source.write_bytes(data)
        Path(str(source) + ".meta").write_bytes(meta)
        return work, source

    def test_check_is_read_only_and_requires_both_asset_and_meta(self):
        work, source = self.prepare_check()
        with patch.object(Path, "write_bytes", side_effect=AssertionError("write")), patch.object(Path, "write_text", side_effect=AssertionError("write")):
            self.assertEqual(additions.check(work, self.root), {"total": 1, "identical": 1, "differences": []})
        source.write_bytes(b"drift")
        Path(str(source) + ".meta").write_bytes(b"drift")
        result = additions.check(work, self.root)
        self.assertEqual(result, {"total": 1, "identical": 0, "differences": [self.asset["output"], self.asset["output"] + ".meta"]})

    def test_check_rejects_wrong_input_and_remaps(self):
        work, _ = self.prepare_check()
        for path in (work / "config/accepted-input.json", self.recipe_path.parent / "hud-ui-remaps.json"):
            prior = path.read_text()
            write(path, {"input_id": "other"})
            with self.assertRaisesRegex(RuntimeError, "different.*input"):
                additions.check(work, self.root)
            path.write_text(prior)

    def test_unconverted_addition_preserves_normalization_and_original_meta(self):
        source = self.root / "previous/Synthetic.asset"
        source.parent.mkdir()
        source.write_bytes(b"%YAML 1.1\n  ref: {guid: " + b"a" * 32 + b"}\n  ui: before\n")
        Path(str(source) + ".meta").write_bytes(b"original-meta")
        row = {"old": source.name, "target": "Assets/Synthetic.asset"}
        project = self.root / "project"
        stage_addition(row, {}, source.parent, project, {"a" * 32: "b" * 32}, {"rows": [{"from": "before", "to": "after"}]})
        self.assertEqual((project / row["target"]).read_bytes(), b"%YAML 1.1\n  ref: {guid: " + b"b" * 32 + b"}\n  ui: after\n")
        self.assertEqual(Path(str(project / row["target"]) + ".meta").read_bytes(), b"original-meta")

    def test_action_fails_on_differences(self):
        import actions

        self.assertEqual(next(action for action in actions._ENTRIES if action.name == "authored-additions-check").status, "current")
        for differences in ([], ["Synthetic.shader.meta"]):
            result = {"total": 1, "identical": int(not differences), "differences": differences}
            with patch.object(additions, "check", return_value=result), contextlib.redirect_stdout(io.StringIO()) as output:
                if differences:
                    with self.assertRaises(SystemExit) as failure:
                        additions.check_action()
                    self.assertEqual(failure.exception.code, 1)
                else:
                    additions.check_action()
            self.assertEqual(json.loads(output.getvalue()), result)
