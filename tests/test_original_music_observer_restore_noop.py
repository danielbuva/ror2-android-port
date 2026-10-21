from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "environment/toolchain.json").is_file())
HOOK = ROOT / "scripts/lab/original_music_output_observer_build_hook.py"


class OriginalMusicObserverRestoreNoopTests(unittest.TestCase):
    def test_absent_receipt_is_inert_for_destination_without_canonical_work(self) -> None:
        spec = importlib.util.spec_from_file_location("observer_restore_noop", HOOK)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(prefix="observer-restore-noop-", dir=ROOT) as temp_name:
            root = Path(temp_name)
            project = root / "destination-project"
            project.mkdir()
            work = root / "not-created-work-root"
            self.assertIsNone(module.restore(project, work))
            self.assertFalse(work.exists())
            self.assertFalse((project / module.STAGE).exists())


if __name__ == "__main__":
    unittest.main()
