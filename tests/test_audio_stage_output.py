"""Audio staging retains ignored-work admission across shared-work checkouts."""

import importlib.util
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
