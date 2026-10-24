"""Historical source is byte-bound and cannot bypass full owner admission."""

import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/legacy_init.py"
SPEC = importlib.util.spec_from_file_location("owner_code_legacy_init", PATH)
LEGACY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEGACY)


class OwnerCodeLegacyInitTests(unittest.TestCase):
    def test_archived_authored_source_is_exact_and_readable(self):
        self.assertEqual(LEGACY.native.sha(LEGACY.TEMPLATE), LEGACY.TEMPLATE_SHA)
        tree = ast.parse(LEGACY.TEMPLATE.read_text())
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertTrue({"transform_file", "rewrite_bank", "validate_output_paths"}.issubset(names))

    def test_wrong_accepted_inventory_refuses_before_creating_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work = root / "work"
            work.mkdir()
            with patch.object(LEGACY, "ROOT", root), patch.object(LEGACY.native, "input_state", return_value=("unknown", root / "game", {})):
                with self.assertRaisesRegex(ValueError, "accepted inventory"):
                    LEGACY.run(work, work / "output")
            self.assertEqual(list(work.iterdir()), [])

    def test_wrong_bank_hash_refuses_even_after_inventory_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work, game = root / "work", root / "game"
            work.mkdir()
            bank = game / LEGACY.BANK
            bank.parent.mkdir(parents=True)
            bank.write_bytes(b"independently authored wrong-bank witness")
            with patch.object(LEGACY, "ROOT", root), patch.object(LEGACY.native, "input_state", return_value=(LEGACY.INPUT_ID, game, {})):
                with self.assertRaisesRegex(ValueError, "source/template drift"):
                    LEGACY.run(work, work / "output")
            self.assertEqual(list(work.iterdir()), [])

    def test_tool_failure_retains_exact_materialization_and_terminal_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work, game = root / "work", root / "game"
            work.mkdir()
            bank = game / LEGACY.BANK
            bank.parent.mkdir(parents=True)
            data = b"independently authored source witness"
            bank.write_bytes(data)
            state = (LEGACY.INPUT_ID, game, {})
            with (
                patch.object(LEGACY, "ROOT", root),
                patch.object(LEGACY, "BANK_SHA", LEGACY.native.sha(bank)),
                patch.object(LEGACY.native, "input_state", return_value=state),
                patch.object(LEGACY.native, "invoke", side_effect=RuntimeError("child failure")),
            ):
                with self.assertRaisesRegex(RuntimeError, "child failure"):
                    LEGACY.run(work, work / "output")
            result = json.loads((work / "output/result.json").read_text())
            self.assertFalse(result["success"])
            source = Path(result["materialized_source"])
            self.assertEqual(LEGACY.native.sha(source), LEGACY.TEMPLATE_SHA)
            self.assertEqual(source.parents[3], root)
            self.assertEqual(bank.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
