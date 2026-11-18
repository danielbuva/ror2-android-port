"""Audio staging retains ignored-work admission across shared-work checkouts."""

import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "tools/unity/support/audio/generators/stage_original_game_banks.py"
SPEC = importlib.util.spec_from_file_location("audio_stage_output", PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)


class AudioStageOutputTests(unittest.TestCase):
    def test_explicit_owner_index_requires_matching_full_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work, game = root / "owner/work", root / "owner/import/files"
            (work / "config").mkdir(parents=True)
            (work / "inventory").mkdir()
            game.mkdir(parents=True)
            files = [{"path": "bank.bnk", "sha256": "a" * 64}]
            identity = hashlib.sha256(json.dumps([["bank.bnk", "a" * 64]], separators=(",", ":")).encode()).hexdigest()
            inventory = work / "inventory/files.json"
            inventory.write_text(json.dumps(dict(input_id=identity, hash_mode="full", files=files)))
            (work / "config/local.json").write_text(json.dumps(dict(game_path=str(game))))
            (work / "config/accepted-input.json").write_text(json.dumps(dict(input_id=identity)))
            prefab = work / "prefab"
            prefab.write_bytes(b"prefab")
            index = work / "index.json"
            index.write_text(json.dumps(dict(input_id=identity, decoder_sample=None)))
            with patch.multiple(STAGE, ACCEPTED_ID=identity, PREFAB_SHA=STAGE.sha_file(prefab), OWNER_BANK_INDEX_SHA=STAGE.sha_file(index), WORK=work):
                self.assertEqual(STAGE.bank_context(prefab, index, work)[0], game)
                with self.assertRaisesRegex(ValueError, "bank-index receipt mismatch"):
                    STAGE.bank_context(prefab, index, None)
                files[0]["sha256"] = "b" * 64
                inventory.write_text(json.dumps(dict(input_id=identity, hash_mode="full", files=files)))
                with self.assertRaisesRegex(ValueError, "inventory content does not match"):
                    STAGE.bank_context(prefab, index, work)

    def test_git_admission_covers_only_ignored_canonical_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            checkout, shared = root / "checkout", root / "shared"
            checkout.mkdir()
            shared.mkdir()
            subprocess.run(["git", "init", "--quiet", str(checkout)], check=True)
            work = checkout / "work"
            work.symlink_to(shared, target_is_directory=True)
            with patch.object(STAGE, "ROOT", checkout), patch.object(STAGE, "WORK", work):
                output = shared / "new-stage"
                self.assertFalse(STAGE.subprocess_check_ignore(output))
                (checkout / ".gitignore").write_text("/work\n")
                self.assertTrue(STAGE.subprocess_check_ignore(output))
                self.assertFalse(STAGE.subprocess_check_ignore(root / "outside"))
                work.unlink()
                work.mkdir()
                self.assertTrue(STAGE.subprocess_check_ignore(work / "new-stage"))
                self.assertFalse(STAGE.subprocess_check_ignore(checkout / "tracked"))
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
