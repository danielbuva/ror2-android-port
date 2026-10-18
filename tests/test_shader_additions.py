"""Synthetic contracts for generator-owned shader pairs; no game, editor or device."""

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import inherited_state
import shader_additions as additions
import shader_deferred
from authored_additions import shader_importer
from common import sha, write
from composition_migration import stage_addition


class ShaderAdditionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / "work"
        self.asset = copy.deepcopy(next(a for a in inherited_state.load_ledger()["assets"] if a["comparison"]["basis"] == "generated_shader_pair"))
        self.data = b'Shader "Synthetic" {}\n'
        self.meta = shader_importer(self.asset["guid"])
        self.asset.update(sha256=hashlib.sha256(self.data).hexdigest(), meta_sha256=hashlib.sha256(self.meta).hexdigest())
        self.ledger = dict(inherited_state.load_ledger(), assets=[self.asset])
        self.row = {"old": self.asset["path"], "target": self.asset["project_path"], "guid": self.asset["guid"]}
        self.selection = {"input_id": self.ledger["input_id"], "previous_project": "work/previous", "shader_sources": ["work/pipeline/sources"]}
        write(self.work / "config/composition-migration.json", self.selection)
        write(self.work / "config/accepted-input.json", {"input_id": self.ledger["input_id"]})
        generator = self.asset["generator"]
        input_path = additions.private_input(self.work, generator["inputs"][0]["path"])
        write(input_path, {"synthetic": True})
        generator["inputs"][0]["sha256"] = sha(input_path)
        self.receipt = self.work / "pipeline/receipt.json"
        write(self.receipt, {"success": True, "source_sha256_by_file": {Path(self.asset["path"]).name: self.asset["sha256"]}})
        generator["output"]["receipt_sha256"] = sha(self.receipt)
        generator["output"]["sha256"] = self.asset["sha256"]
        self.calls = []
        patcher = patch.object(shader_deferred, "generate", side_effect=self.generate)
        patcher.start()
        self.addCleanup(patcher.stop)

    def generate(self, output, resources, work, root, independent):
        self.assertNotIn(self.work, output.resolve().parents)
        self.assertEqual(work, self.work)
        self.assertEqual(root, self.root)
        self.assertEqual(independent, self.receipt.parent)
        self.assertEqual(resources, {Path(self.asset["path"]).stem})
        self.calls.append(output)
        target = output / "sources" / Path(self.asset["path"]).name
        target.parent.mkdir()
        target.write_bytes(self.data)

    def test_prepare_stage_and_cleanup_without_history_or_work_writes(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}
        pairs = additions.prepare([self.row], self.work, self.ledger)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("history read")):
            stage_addition(self.row, pairs, self.work / "absent-history", self.root / "project", {}, {"rows": []})
        target = self.root / "project" / self.row["target"]
        self.assertEqual(target.read_bytes(), self.data)
        self.assertEqual(Path(str(target) + ".meta").read_bytes(), self.meta)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()})
        self.assertTrue(self.calls)
        self.assertTrue(all(not path.exists() for path in self.calls))

    def test_preparation_rejects_missing_duplicate_guid_target_and_input(self):
        for rows in ([], [self.row, self.row], [dict(self.row, guid="0" * 32)], [dict(self.row, target="Assets/Other.shader")]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                additions.prepare(rows, self.work, self.ledger)
        write(self.work / "config/accepted-input.json", {"input_id": "0" * 64})
        with self.assertRaisesRegex(RuntimeError, "different accepted input"):
            additions.prepare([self.row], self.work, self.ledger)
        self.assertFalse(self.calls)

    def test_input_receipt_and_generated_body_or_importer_drift_fail(self):
        for mutate in (
            lambda a: a["generator"]["inputs"][0].update(sha256="0" * 64),
            lambda a: a["generator"]["output"].update(receipt_sha256="0" * 64),
            lambda a: a.update(sha256="0" * 64),
            lambda a: a.update(meta_sha256="0" * 64),
            lambda a: a["generator"]["output"].update(filename="../Other.shader"),
        ):
            asset = copy.deepcopy(self.asset)
            mutate(asset)
            with self.subTest(asset=asset), self.assertRaises(RuntimeError):
                additions.generate_pairs([asset], self.work)

    def test_check_proves_both_bytes_against_previous_and_ledger(self):
        target = self.work / "previous" / self.asset["path"]
        target.parent.mkdir(parents=True)
        target.write_bytes(self.data)
        meta = Path(str(target) + ".meta")
        meta.write_bytes(self.meta)
        result = inherited_state.check(self.work, self.ledger)
        self.assertEqual(result["checked_generated_pairs"], 1)
        self.assertEqual(result["checked_inherited_pairs"], 0)
        self.assertEqual(result["differences"], [])
        target.write_bytes(b"drift")
        meta.write_bytes(b"drift")
        self.assertEqual(
            inherited_state.check(self.work, self.ledger)["differences"],
            [{"path": self.asset["path"], "reason": "generated_pair"}, {"path": self.asset["path"] + ".meta", "reason": "generated_pair"}],
        )
        target.write_bytes(self.data)
        meta.write_bytes(self.meta)
        ledger = copy.deepcopy(self.ledger)
        ledger["assets"][0]["meta_sha256"] = "0" * 64
        self.assertEqual(inherited_state.check(self.work, ledger)["differences"], [{"path": self.asset["path"] + ".meta", "reason": "generated_pair"}])

    def test_shader_inputs_and_previous_symlinks_cannot_escape(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid inherited-state path"):
            additions.private_input(self.work, "work/../other")
        link = self.work / "escape"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            additions.private_input(self.work, "work/escape/other")
        target = self.work / "previous" / self.asset["path"]
        target.parent.mkdir(parents=True)
        target.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            inherited_state.check(self.work, self.ledger)

    def test_only_proven_pairs_are_generator_owned(self):
        assets = additions.cohort(inherited_state.load_ledger())
        self.assertEqual(len(assets), 9)
        self.assertTrue(all(a["comparison"]["asset_matches"] and a["comparison"]["meta_matches"] for a in assets))
        self.assertFalse(additions.cohort(dict(self.ledger, assets=[dict(self.asset, status="inherited")])))
