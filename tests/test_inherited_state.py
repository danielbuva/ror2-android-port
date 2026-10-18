"""Ledger integrity contracts using authored temporary assets; no editor or device."""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import actions
import inherited_state as state
from common import ROOT, write


class InheritedStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name) / "work"
        self.previous = self.work / "previous"
        self.asset = copy.deepcopy(state.load_ledger()["assets"][0])
        self.asset.update(path="Assets/LabLoadingScene/Test.shader", project_path="Assets/LabLoadingScene/Test.shader", status="inherited")
        source = self.previous / self.asset["path"]
        source.parent.mkdir(parents=True)
        source.write_bytes(b"authored synthetic fixture\n")
        meta = Path(str(source) + ".meta")
        meta.write_text("guid: " + self.asset["guid"] + "\n")
        self.asset["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.asset["meta_sha256"] = hashlib.sha256(meta.read_bytes()).hexdigest()
        self.ledger = dict(state.load_ledger(), assets=[self.asset])
        self.recipe = self.work.parent / "ledger.json"
        write(self.recipe, self.ledger)
        write(self.work / "config/composition-migration.json", {"input_id": self.ledger["input_id"], "previous_project": "work/previous"})
        write(self.work / "config/accepted-input.json", {"input_id": self.ledger["input_id"]})

    def test_read_only_pair_check_and_counts(self):
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}
        result = state.check(self.work, self.ledger)
        self.assertEqual(result["checked_inherited_pairs"], 1)
        self.assertEqual(result["differences"], [])
        self.assertEqual(result["by_status"], {"inherited": 1, "reproducible": 0, "retired": 0})
        self.assertEqual(result["by_usage"][self.asset["usage"]], 1)
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()})

    def test_asset_and_meta_drift_and_missing_fail_independently(self):
        source = self.previous / self.asset["path"]
        source.write_bytes(b"drift")
        Path(str(source) + ".meta").unlink()
        self.assertEqual(
            state.check(self.work, self.ledger)["differences"],
            [{"path": self.asset["path"], "reason": "sha256"}, {"path": self.asset["path"] + ".meta", "reason": "missing"}],
        )

    def test_guid_is_checked_even_if_meta_hash_was_recorded_incorrectly(self):
        self.asset["guid"] = "0" * 32
        self.assertEqual(state.check(self.work, self.ledger)["differences"][0]["reason"], "guid")

    def test_reproducible_and_retired_are_counted_without_requiring_history(self):
        for status in ("reproducible", "retired"):
            asset = dict(self.asset, status=status, path="Assets/LabLoadingScene/Absent.shader", usage="unclear")
            result = state.check(self.work, dict(self.ledger, assets=[asset]))
            self.assertEqual(result["checked_inherited_pairs"], 0)
            self.assertEqual(result["by_status_and_usage"][status], {"unclear": 1})
            self.assertFalse(result["differences"])

    def test_input_gates_and_source_escape(self):
        for changes in ({"input_id": "0" * 64}, {"previous_project": "work/../escape"}, {"previous_project": "work/lab-project"}):
            selection = {"input_id": self.ledger["input_id"], "previous_project": "work/previous", **changes}
            write(self.work / "config/composition-migration.json", selection)
            with self.assertRaises(RuntimeError):
                state.check(self.work, self.ledger)

    def test_symlink_escape_is_rejected(self):
        source = self.previous / self.asset["path"]
        source.unlink()
        source.symlink_to(self.work.parent / "outside")
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            state.check(self.work, self.ledger)

    def test_schema_duplicate_paths_guids_and_traversal_are_rejected(self):
        for asset in (dict(self.asset, path="Assets/LabLoadingScene/../escape"), dict(self.asset, status="unknown"), dict(self.asset, sha256="bad")):
            write(self.recipe, dict(self.ledger, assets=[asset]))
            with self.assertRaises(RuntimeError):
                state.load_ledger(self.recipe)
        write(self.recipe, dict(self.ledger, assets=[self.asset, self.asset]))
        with self.assertRaises(RuntimeError):
            state.load_ledger(self.recipe)

    def test_action_exit_and_work_root_dispatch(self):
        with patch.object(state, "check", return_value={"differences": ["fixture"]}), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ended:
                state.check_action()
        self.assertEqual(ended.exception.code, 1)
        function = unittest.mock.Mock()
        actions._inherited_check(function, {}, SimpleNamespace(work_dir="selected-work"))
        function.assert_called_once_with(work="selected-work")
        self.assertEqual(actions.ACTIONS["inherited-state-check"].status, "current")

    def test_tracked_ledger_cohorts_provenance_and_public_safety(self):
        assets = state.load_ledger()["assets"]
        self.assertEqual(len(assets), 229)
        self.assertEqual(sum(a["kind"] == "shader" for a in assets), 192)
        native = [
            a
            for a in assets
            if a["kind"] == "shader" and a["comparison"]["basis"] in ("selected_receipted_output", "selected_output_absent", "generated_shader_pair")
        ]
        self.assertEqual(len(native), 177)
        self.assertEqual(sum(a["comparison"]["asset_matches"] for a in native), 9)
        self.assertEqual(sum(a["status"] == "reproducible" for a in assets), 40)  # 15 authored + 9 shaders + 14 decks + 2 non-shaders
        self.assertEqual(sum(a["status"] == "inherited" for a in assets), 189)
        self.assertEqual(sum(a["status"] == "inherited" for a in native), 168)
        self.assertFalse(any(a["status"] == "retired" for a in assets))
        # Evidence contains only identifiers, hashes and authored classification, never asset programs.
        for asset in assets:
            for evidence in asset["usage_evidence"]:
                self.assertIn(
                    evidence["kind"],
                    {
                        "runtime_shader",
                        "runtime_manifest_shader",
                        "runtime_resource",
                        "bundle_root",
                        "serialized_reference",
                        "shader_include",
                        "no_reference_in_scope",
                    },
                )
            if asset["generator"] and "function" in asset["generator"]:
                self.assertTrue((ROOT / asset["generator"]["function"].split(":")[0]).is_file())
        serialized = json.dumps(assets)
        self.assertNotIn("HLSLPROGRAM", serialized)
        self.assertNotIn("CGPROGRAM", serialized)
        self.assertNotIn("/Users/", serialized)
