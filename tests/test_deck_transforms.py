"""Synthetic DCCS contracts: export selections, sparse legacy fields and stage ownership."""

import copy
import contextlib
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
from composition_migration import stage_addition


def card(guid, weight=1):
    return (
        "    - spawnCardReference:\n        m_AssetGUID:\n        m_SubObjectName:\n        m_SubObjectType:\n"
        "      spawnCard: {fileID: 11400000, guid: " + guid + ", type: 2}\n"
        "      selectionWeight: " + str(weight) + "\n      spawnDistance: 2\n      preventOverhead: 1\n"
        "      minimumStageCompletions: 3\n      requiredUnlockable: SyntheticRequirement\n      forbiddenUnlockable:\n"
        "      requiredUnlockableDef: {fileID: 0}\n      forbiddenUnlockableDef: {fileID: 0}\n"
        "      isExclusivelyElite: 0\n      eliteDef: {fileID: 0}\n"
    )


SOURCE = (
    "%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!114 &11400000\nMonoBehaviour:\n"
    "  m_Script: {fileID: -1, guid: " + "d" * 32 + ", type: 3}\n"
    "  m_Name: SyntheticDeck\n  expansionsInEffect: []\n  categories:\n  - name: SyntheticFirst\n    cards:\n"
    + card("a" * 32)
    + card("b" * 32, 7)
    + "    selectionWeight: 2.5\n"
    "  - name: SyntheticSecond\n    cards:\n" + card("c" * 32) + "    selectionWeight: 4\n"
).encode()


class DeckTransformsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / "work"
        self.export = self.work / "export"
        self.asset = {
            "source": "Assets/SyntheticDeck.asset",
            "source_sha256": hashlib.sha256(SOURCE).hexdigest(),
            "output": "Assets/LabLoadingScene/Director-Synthetic.asset",
            "guid": "e" * 32,
            "constructor": "deck",
            "categories": [{"name": "SyntheticFirst", "cards": [{"spawn_card": "b" * 32, "omit_fields": []}], "omit_weight": False}],
        }
        self.recipe = {"schema_version": 1, "input_id": "synthetic", "assets": [self.asset]}
        self.recipe_dir = self.root / "recipe"
        self.recipe_path = self.recipe_dir / "deck-transforms.json"
        write(self.recipe_path, self.recipe)
        patcher = patch.object(transforms, "RECIPE", self.recipe_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        source = self.export / self.asset["source"]
        source.parent.mkdir(parents=True)
        source.write_bytes(SOURCE)
        self.row = {"old": self.asset["output"], "target": "Assets/Relocated.asset", "guid": self.asset["guid"]}

    def test_selection_keeps_card_restrictions_weights_and_source_unchanged(self):
        original = copy.deepcopy(self.asset)
        data = transforms.generate_deck(SOURCE, self.asset).decode()
        expected = SOURCE.decode().split("  categories:\n")[0].replace("m_Name: ", "m_Name: Android supported ")
        expected += "  categories:\n  - name: SyntheticFirst\n    cards:\n"
        expected += card("b" * 32, 7).replace("      isExclusivelyElite: 0\n", "").replace("      eliteDef: {fileID: 0}\n", "")
        expected += "    selectionWeight: 2.5\n"
        self.assertEqual(data, expected)
        self.assertEqual(self.asset, original)
        self.assertEqual((self.export / self.asset["source"]).read_bytes(), SOURCE)

    def test_sparse_legacy_card_and_category_weight_are_explicit(self):
        selection = self.asset["categories"][0]
        selection["omit_weight"] = True
        selection["cards"][0]["omit_fields"] = sorted(transforms.DECK_OMIT_FIELDS)
        data = transforms.generate_deck(SOURCE, self.asset).decode()
        self.assertTrue(data.endswith("      selectionWeight: 7\n"))
        self.assertNotIn("minimumStageCompletions", data)
        self.assertNotIn("    selectionWeight: 2.5", data)

    def test_hash_nondefault_elite_and_ambiguous_source_fail(self):
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            transforms.generate_deck(SOURCE + b"drift", self.asset)
        for data in (
            SOURCE.replace(b"isExclusivelyElite: 0", b"isExclusivelyElite: 1"),
            SOURCE.replace(b"eliteDef: {fileID: 0}", b"eliteDef: {fileID: 42}"),
            SOURCE.replace(card("a" * 32).encode(), card("b" * 32).encode()),
            SOURCE.replace(b"&11400000", b"&42"),
        ):
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                transforms.generate_deck(data, dict(self.asset, source_sha256=hashlib.sha256(data).hexdigest()))

    def test_missing_category_or_card_fails(self):
        for key, value in (("name", "Absent"), ("spawn_card", "f" * 32)):
            asset = copy.deepcopy(self.asset)
            target = asset["categories"][0] if key == "name" else asset["categories"][0]["cards"][0]
            target[key] = value
            with self.assertRaisesRegex(RuntimeError, "missing"):
                transforms.generate_deck(SOURCE, asset)

    def test_recipe_rejects_input_duplicates_payloads_paths_and_unknown_fields(self):
        with self.assertRaisesRegex(RuntimeError, "different accepted input"):
            transforms.load_deck_recipe("other")
        cases = []
        for key, value in (("constructor", "payload"), ("output", "Assets/../Escape.asset"), ("guid", "bad")):
            cases.append(dict(self.asset, **{key: value}))
        for omitted in (["spawnCard"], ["minimumStageCompletions"] * 2, ["payload\ncontent"]):
            asset = copy.deepcopy(self.asset)
            asset["categories"][0]["cards"][0]["omit_fields"] = omitted
            cases.append(asset)
        for asset in cases:
            write(self.recipe_path, dict(self.recipe, assets=[asset]))
            with self.subTest(asset=asset), self.assertRaises(RuntimeError):
                transforms.load_deck_recipe("synthetic")
        write(self.recipe_path, dict(self.recipe, assets=[self.asset, self.asset]))
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            transforms.load_deck_recipe("synthetic")

    def test_prepare_and_stage_need_neither_history_nor_export_importer(self):
        prepared = transforms.prepare_decks([self.row], self.export, "synthetic")
        data, meta = prepared[self.row["old"]]
        self.assertIn(b"NativeFormatImporter:\n", meta)
        self.assertIn(b"guid: " + self.asset["guid"].encode(), meta)
        self.assertNotIn(b"timeCreated", meta)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("historical read")):
            stage_addition(self.row, prepared, self.root / "absent-history", self.root / "project", {}, {"rows": []})
        self.assertEqual((self.root / "project" / self.row["target"]).read_bytes(), data)
        self.assertEqual((self.root / "project" / (self.row["target"] + ".meta")).read_bytes(), meta)

    def test_prepare_refuses_incomplete_or_ambiguous_cohort(self):
        for rows in ([], [self.row, self.row], [dict(self.row, guid="f" * 32)]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                transforms.prepare_decks(rows, self.export, "synthetic")

    def setup_check(self):
        write(self.work / "config/accepted-input.json", {"input_id": "synthetic"})
        write(self.work / "config/composition-migration.json", {"input_id": "synthetic", "previous_project": "work/previous", "evidence": "work/evidence"})
        write(self.work / "config/reconstruction.json", {"input_id": "synthetic", "projects": ["work/export"]})
        write(self.work / "evidence/rebase-analysis.json", {"guidmap": {"f" * 32: "d" * 32}})
        write(self.recipe_dir / "hud-ui-remaps.json", {"input_id": "synthetic", "rows": []})
        data, meta = transforms.generate_deck_asset(self.export, self.asset)
        for folder in ("previous", "lab-project"):
            dest = self.work / folder / self.asset["output"]
            dest.parent.mkdir(parents=True)
            dest.write_bytes(data.replace(b"d" * 32, b"f" * 32) if folder == "previous" else data)
            Path(str(dest) + ".meta").write_bytes(meta)
        return self.work / "previous" / self.asset["output"]

    def test_check_is_read_only_normalizes_oracle_and_compares_both_bytes(self):
        previous = self.setup_check()
        with patch.object(Path, "write_bytes", side_effect=AssertionError("write")), patch.object(Path, "write_text", side_effect=AssertionError("write")):
            self.assertEqual(transforms.check_decks(self.work, self.root), {"total": 1, "identical": 1, "differences": [], "changed_later_in_project": []})
        previous.write_bytes(b"drift")
        Path(str(previous) + ".meta").write_bytes(b"drift")
        result = transforms.check_decks(self.work, self.root)
        self.assertEqual(result["identical"], 0)
        self.assertEqual(result["differences"], [self.asset["output"], self.asset["output"] + ".meta"])

    def test_check_reports_current_drift_separately_and_rejects_input_drift(self):
        self.setup_check()
        (self.work / "lab-project" / self.asset["output"]).write_bytes(b"later")
        result = transforms.check_decks(self.work, self.root)
        self.assertEqual(result["identical"], 1)
        self.assertEqual(result["changed_later_in_project"], [self.asset["output"]])
        for path in (self.work / "config/reconstruction.json", self.work / "config/composition-migration.json", self.recipe_dir / "hud-ui-remaps.json"):
            prior = path.read_bytes()
            write(path, {"input_id": "other"})
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, "different accepted input"):
                transforms.check_decks(self.work, self.root)
            path.write_bytes(prior)

    def test_missing_current_metadata_is_reported_as_later_drift(self):
        self.setup_check()
        Path(str(self.work / "lab-project" / self.asset["output"]) + ".meta").unlink()
        self.assertEqual(transforms.check_decks(self.work, self.root)["changed_later_in_project"], [self.asset["output"]])

    def test_action_fails_when_only_deck_cohort_differs(self):
        with (
            patch.object(transforms, "check", return_value={"total": 0, "identical": 0, "differences": []}),
            patch.object(transforms, "check_decks", return_value={"total": 1, "identical": 0, "differences": ["Synthetic.asset.meta"]}),
            contextlib.redirect_stdout(io.StringIO()) as output,
            self.assertRaises(SystemExit) as failure,
        ):
            transforms.check_action()
        self.assertEqual(failure.exception.code, 1)
        self.assertEqual(json.loads(output.getvalue())["deck_cohort"]["identical"], 0)

    def test_public_recipe_covers_exactly_the_inherited_director_decks(self):
        root = Path(__file__).resolve().parents[1]
        inherited = json.loads((root / "recipe/inherited-state.json").read_text())
        recipe = transforms.load_deck_recipe(inherited["input_id"], root / "recipe/deck-transforms.json")
        expected = {row["path"]: row["guid"] for row in inherited["assets"] if Path(row["path"]).name.startswith("Director-")}
        self.assertEqual(len(expected), 14)
        self.assertEqual({row["output"]: row["guid"] for row in recipe["assets"]}, expected)
