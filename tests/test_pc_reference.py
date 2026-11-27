import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_grapple_plan_and_manifest_require_hold_trace_and_clip(self):
        plan = json.loads((ROOT / "tools/pc-reference/plans/loader-roost.json").read_text())
        scenario = pc_reference.load_plan(plan)[0]
        step = scenario["steps"][0]
        folder = step["id"]
        result = {"steps": [{"id": folder, "timeline": [{"frame": "frame.png"}]}]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()
            (output / folder).mkdir()
            for name in ("audio-events.jsonl", f"{folder}/frame.png", f"{folder}/state.json", f"{folder}/grapple-ticks.jsonl"):
                (output / name).write_text(name)
            with self.assertRaisesRegex(RuntimeError, "grapple.mp4"):
                pc_reference.capture_files(output, scenario, result)
            clip = output / folder / "grapple.mp4"
            clip.write_text("encoded fixture")
            self.assertEqual(pc_reference.capture_files(output, scenario, result)[f"{folder}/grapple.mp4"], pc_reference.sha(clip))
        step["holdSeconds"] = step["recordSeconds"]
        with self.assertRaisesRegex(ValueError, "longer than the positive hold"):
            pc_reference.load_plan(plan)

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

    def test_cross_over_uses_the_clone_executable_as_a_positional_path(self):
        plan = json.loads((ROOT / "tools/pc-reference/plans/gameplay.json").read_text())
        scenario = pc_reference.load_plan(plan)[0]
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            clone = local / "New Bottle/drive_c/ror2-reference"
            with (
                patch.object(pc_reference, "LOCAL", local),
                patch.object(pc_reference, "check_capture_host"),
                patch.object(pc_reference.subprocess, "run") as launch,
            ):
                launch.return_value.returncode = 2
                with self.assertRaisesRegex(RuntimeError, "never produced a result"):
                    pc_reference.run_plan(pc_reference.argparse.Namespace(timeout=1), clone, {}, ["wine"], plan, [scenario])
            command = launch.call_args.args[0]
            self.assertEqual(command[:7], ["wine", "--dll", "winhttp=n,b", "--workdir", clone, clone / pc_reference.GAME_EXE, "-force-d3d11"])
