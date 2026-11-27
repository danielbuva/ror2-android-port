import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import pc_reference  # noqa: E402


class PcReferenceTest(unittest.TestCase):
    def test_checked_in_plan_validates_and_preserves_routes(self):
        plan = json.loads((ROOT / "tools/pc-reference/plans/gameplay.json").read_text())
        scenarios = {scenario["id"]: scenario for scenario in pc_reference.load_plan(plan)}
        self.assertTrue(scenarios["roost"]["naturalFirstStage"])
        self.assertFalse(scenarios["gold"].get("naturalFirstStage"))
        self.assertTrue(scenarios["huntress"]["captureAudio"])
        scenarios["roost"]["steps"][0]["id"] = "../escape"
        with self.assertRaisesRegex(ValueError, "path components"):
            pc_reference.load_plan(plan)

    def test_capture_manifest_requires_each_step_and_hashes_artifacts(self):
        scenario = {"steps": [{"id": "opening"}]}
        result = {"steps": [{"id": "opening", "timeline": [{"frame": "frame.png"}]}]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()
            (output / "opening").mkdir()
            for name in ("audio-events.jsonl", "opening/frame.png", "opening/state.json"):
                (output / name).write_text(name)
            self.assertEqual(pc_reference.capture_files(output, scenario, result)["opening/frame.png"], pc_reference.sha(output / "opening/frame.png"))
            (output / "opening/frame.png").unlink()
            with self.assertRaisesRegex(RuntimeError, "artifact is missing"):
                pc_reference.capture_files(output, scenario, result)

    def test_reference_clone_requires_its_ownership_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            drive = Path(directory) / "drive_c"
            source = drive / "steamapps/common/game"
            managed = source / pc_reference.MANAGED_DIR
            managed.mkdir(parents=True)
            (managed / "RoR2.dll").write_bytes(b"fixture")
            (source.parent.parent / "appmanifest_632360.acf").write_text('"buildid" "32"')
            clone = drive / pc_reference.CLONE_NAME
            clone.mkdir()
            with self.assertRaisesRegex(RuntimeError, "another installation"):
                pc_reference.prepare_clone(source, drive)

    def test_no_signed_in_account_from_empty_or_logged_out_registry(self):
        self.assertFalse(pc_reference.positive_steam_account(""))
        self.assertFalse(pc_reference.positive_steam_account("    ActiveUser    REG_DWORD    0x0"))
        self.assertTrue(pc_reference.positive_steam_account("    ActiveUser    REG_DWORD    0x12"))
