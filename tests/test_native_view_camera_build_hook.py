from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import contextlib
import io
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

CANDIDATE = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load copied tracked module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrackedCameraSourcesTests(unittest.TestCase):
    def test_checked_in_source_pins_are_fresh(self):
        hook = load("camera_hook_checked_in_pins", CANDIDATE / "scripts/lab/native_view_camera_build_hook.py")
        result = hook.build_hook_pins()
        pins = json.loads(hook.CAMERA_PINS.read_text())
        self.assertTrue(result["success"])
        self.assertEqual(result["source_count"], len(pins["source_paths"]))
        self.assertEqual(result["updated_roles"], [])

    def test_no_private_preview_source_root_is_selected(self):
        build_hook = (CANDIDATE / "scripts/lab/native_view_camera_build_hook.py").read_text()
        transform = (CANDIDATE / "scripts/lab/native_view_camera_transform.py").read_text()
        self.assertIn("CAMERA_SOURCE_ROOT = ROOT", build_hook)
        self.assertIn("SOURCE_ROOT = ROOT", transform)
        self.assertNotIn("work/coordination/native-visual-camera-contract", build_hook + transform)
        self.assertNotIn("IN_PREVIEW", build_hook + transform)

    def test_point_sound_and_previous_audio_profiles_have_distinct_exact_outputs(self):
        hook = load("camera_hook_profile_contract", CANDIDATE / "scripts/lab/native_view_camera_build_hook.py")
        pins = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        r4 = "post-audio-r4-1034-api-d540"
        point = "post-audio-point-sound-6f96-api-d540"
        self.assertEqual(hook.HASHES["composed_game"], pins["profiles"][r4]["input_sha256"])
        self.assertEqual(hook.HASHES["camera_after_audio"], pins["profiles"][r4]["output_sha256"])
        self.assertEqual(hook.HASHES["point_sound_composed_game"], pins["profiles"][point]["input_sha256"])
        self.assertEqual(hook.HASHES["camera_after_point_sound"], pins["profiles"][point]["output_sha256"])
        self.assertEqual(hook.HASHES["composed_api"], pins["resolver_profiles"][point]["api_sha256"])
        self.assertNotEqual(pins["profiles"][r4]["input_sha256"], pins["profiles"][point]["input_sha256"])
        transform = (CANDIDATE / "tools/assembly-transforms/NativeViewCameraCecilTransform.cs").read_text()
        self.assertIn(pins["profiles"][point]["input_sha256"], transform)
        self.assertIn(pins["profiles"][r4]["input_sha256"], transform)

    def test_r10_1ced_point_sound_profile_accepts_both_explicit_pcm_states(self):
        hook = load("camera_hook_pcm_profile_contract", CANDIDATE / "scripts/lab/native_view_camera_build_hook.py")
        pins = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        profile = "post-audio-r10-1ced-game-6f96"
        game_hash = "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc"
        api_hash = "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b"
        receipt = {
            "requested": True,
            "passive_pcm_capture_requested": True,
            "stage_receipt_sha256": hook.HASHES["stage_receipt_sha256"],
            "lineage": {"composed_game_sha256": game_hash, "composed_api_sha256": api_hash},
            "outputs": [{"target": hook.GAME_RELATIVE.as_posix(), "sha256": game_hash}],
        }
        self.assertEqual(hook._select_point_sound_profile(receipt, game_hash, api_hash)[0], profile)
        self.assertEqual(pins["profiles"][profile]["input_sha256"], game_hash)
        self.assertEqual(pins["resolver_profiles"][profile]["api_sha256"], api_hash)

        pcm_off = json.loads(json.dumps(receipt))
        pcm_off["passive_pcm_capture_requested"] = False
        self.assertEqual(hook._select_point_sound_profile(pcm_off, game_hash, api_hash)[0], profile)
        for invalid_state in (None, 0, "false"):
            invalid = json.loads(json.dumps(receipt))
            invalid["passive_pcm_capture_requested"] = invalid_state
            with self.subTest(pcm_state=invalid_state), self.assertRaises(ValueError):
                hook._select_point_sound_profile(invalid, game_hash, api_hash)

        for mutate in (
            lambda value: value.update(requested=False),
            lambda value: value.update(stage_receipt_sha256="0" * 64),
            lambda value: value["lineage"].update(composed_api_sha256=hook.HASHES["composed_api"]),
            lambda value: value["lineage"].update(composed_game_sha256=hook.HASHES["composed_game"]),
            lambda value: value["outputs"].clear(),
            lambda value: value["outputs"].append(dict(value["outputs"][0])),
        ):
            mutant = json.loads(json.dumps(receipt))
            mutate(mutant)
            with self.subTest(mutant=mutant), self.assertRaises(ValueError):
                hook._select_point_sound_profile(mutant, game_hash, api_hash)

        for bad_game, bad_api in (
            (hook.HASHES["composed_game"], api_hash),
            (game_hash, hook.HASHES["composed_api"]),
            (game_hash, hook.HASHES["previous_composed_api_restore_only"]),
        ):
            with self.subTest(game=bad_game, api=bad_api), self.assertRaises(ValueError):
                hook._select_point_sound_profile(receipt, bad_game, bad_api)

        d540 = json.loads(json.dumps(receipt))
        d540["passive_pcm_capture_requested"] = False
        d540["lineage"]["composed_api_sha256"] = hook.HASHES["composed_api"]
        self.assertEqual(hook._select_point_sound_profile(d540, game_hash, hook.HASHES["composed_api"])[0], "post-audio-point-sound-6f96-api-d540")


class BuildHookPinCommandTests(unittest.TestCase):
    def setUp(self):
        self.hook = load("camera_hook_pin_command", CANDIDATE / "scripts/lab/native_view_camera_build_hook.py")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.hook.CAMERA_SOURCE_ROOT = self.root
        self.hook.CAMERA_PINS = self.root / "pins.json"
        self.pins = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        for role, relative in self.pins["source_paths"].items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("authored synthetic source: " + role)
            self.pins["source_sha256"][role] = self.hook.sha256(path)
        self.hook.CAMERA_PINS.write_text(json.dumps(self.pins, indent=2, sort_keys=True) + "\n")
        self.changed_roles = ["build_hook", "music_observer_stage"]
        for role in self.changed_roles:
            (self.root / self.pins["source_paths"][role]).write_text("reviewed synthetic change: " + role)

    def test_check_reports_all_changed_sources_without_writing(self):
        before = self.hook.CAMERA_PINS.read_bytes()
        with self.assertRaises(ValueError) as failure:
            self.hook.build_hook_pins()
        for role in self.changed_roles:
            self.assertIn(self.pins["source_paths"][role], str(failure.exception))
        self.assertIn("./dev build-hook-pins --action refresh", str(failure.exception))
        self.assertEqual(self.hook.CAMERA_PINS.read_bytes(), before)

    def test_refresh_updates_every_changed_source_preserving_other_values(self):
        result = self.hook.build_hook_pins("refresh")
        self.assertEqual(result["updated_roles"], self.changed_roles)
        after = json.loads(self.hook.CAMERA_PINS.read_text())
        for key, value in self.pins.items():
            if key != "source_sha256":
                self.assertEqual(after[key], value, key)
        for role, relative in self.pins["source_paths"].items():
            self.assertEqual(after["source_sha256"][role], self.hook.sha256(self.root / relative), role)
        self.assertTrue(self.hook.build_hook_pins()["success"])
        unchanged = self.hook.CAMERA_PINS.read_bytes()
        self.assertEqual(self.hook.build_hook_pins("refresh")["updated_roles"], [])
        self.assertEqual(self.hook.CAMERA_PINS.read_bytes(), unchanged)

    def test_preflight_refuses_stale_sources_before_local_configuration(self):
        with patch.object(sys, "path", [str(CANDIDATE / "scripts/lab"), *sys.path]):
            import build
        with (
            patch.dict(sys.modules, {"native_view_camera_build_hook": self.hook}),
            patch.object(build, "config", side_effect=AssertionError("configuration read too early")) as config,
        ):
            with self.assertRaisesRegex(ValueError, "reviewed camera source drift"):
                build.preflight_host()
            config.assert_not_called()
            self.hook.build_hook_pins("refresh")
            with self.assertRaisesRegex(AssertionError, "configuration read too early"):
                build.preflight_host()
            config.assert_called_once_with()

    def test_cli_defaults_to_check_and_explicit_refresh_uses_same_owner(self):
        with patch.object(sys, "path", [str(CANDIDATE / "scripts/lab"), *sys.path]):
            from device import Device
        for arguments, action in (([], "check"), (["--action", "refresh"], "refresh")):
            with (
                self.subTest(action=action),
                patch.dict(os.environ, {"LAB_LANE": ""}),
                patch.object(sys, "argv", ["dev", "build-hook-pins", *arguments]),
                patch.dict(sys.modules, {"native_view_camera_build_hook": self.hook}),
                patch.object(self.hook, "build_hook_pins", return_value={"success": True}) as command,
                patch.object(Device, "sleep_awakened", return_value=[]),
                patch.object(sys, "path", [str(CANDIDATE / "scripts/lab"), *sys.path]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                runpy.run_path(str(CANDIDATE / "scripts/lab/main.py"), run_name="__main__")
                command.assert_called_once_with(action)


class RestoreOnly793ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.hook_path = CANDIDATE / "scripts/lab/native_view_camera_build_hook.py"
        self.hook = load("camera_hook_restore_793", self.hook_path)
        self.root = Path(tempfile.mkdtemp(prefix="camera-restore-793-", dir=CANDIDATE))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.hook.ROOT = self.root
        self.work = self.root / "work"
        self.project = self.work / "project"
        self.plugins = self.project / "Assets/LabLoadingScene/Plugins"
        self.streaming = self.project / "Assets/StreamingAssets/Lab"
        self.plugins.mkdir(parents=True)
        self.streaming.mkdir(parents=True)
        self.input_bytes = b"synthetic exact-profile preimage bytes"
        self.api_793_bytes = b"synthetic previous API 793 identity bytes"
        self.api_d540_bytes = b"synthetic current API d540 identity bytes"
        self.output_bytes = b"synthetic camera-owned e16 image bytes"
        self.hook.HASHES["composed_game"] = hashlib.sha256(self.input_bytes).hexdigest()
        self.hook.HASHES["previous_composed_api_restore_only"] = hashlib.sha256(self.api_793_bytes).hexdigest()
        self.hook.HASHES["composed_api"] = hashlib.sha256(self.api_d540_bytes).hexdigest()
        self.hook.HASHES["camera_after_audio"] = hashlib.sha256(self.output_bytes).hexdigest()
        self.snapshot = self.work / "coordination/camera-restore-test/RoR2.preimage.dll"
        self.snapshot.parent.mkdir(parents=True)
        self.snapshot.write_bytes(self.input_bytes)
        (self.plugins / "RoR2.dll").write_bytes(self.output_bytes)
        (self.plugins / "AK.Wwise.Unity.API.dll").write_bytes(self.api_793_bytes)

    def write_receipts(self, profile="post-audio-r4-1034"):
        audio = {
            "schema": self.hook.AUDIO_SCHEMA,
            "requested": True,
            "lineage": {
                "composed_game_sha256": self.hook.HASHES["composed_game"],
                "composed_api_sha256": self.hook.HASHES["previous_composed_api_restore_only"],
            },
        }
        audio_raw = json.dumps(audio, sort_keys=True, separators=(",", ":")).encode()
        (self.streaming / "OriginalGameAudioStageReceipt.json").write_bytes(audio_raw)
        receipt = {
            "schema": self.hook.STAGE_SCHEMA,
            "accepted": False,
            "runtime_requested": False,
            "runtime_dispatch_ready": False,
            "input_sha256": self.hook.HASHES["composed_game"],
            "output_sha256": self.hook.HASHES["camera_after_audio"],
            "api_sha256": self.hook.HASHES["previous_composed_api_restore_only"],
            "audio_stage_receipt_sha256": hashlib.sha256(audio_raw).hexdigest(),
            "audio_requested": True,
            "profile": profile,
            "preimage_snapshot": self.snapshot.relative_to(self.work).as_posix(),
        }
        (self.streaming / "NativeViewCameraStageReceipt.json").write_text(json.dumps(receipt))

    def test_exact_1034_793_receipt_restores_preimage(self):
        self.write_receipts()
        result = self.hook.restore_previous_camera(self.project, self.work)
        self.assertEqual(result["restored_sha256"], self.hook.HASHES["composed_game"])
        self.assertEqual((self.plugins / "RoR2.dll").read_bytes(), self.input_bytes)
        self.assertFalse((self.streaming / "NativeViewCameraStageReceipt.json").exists())

    def test_793_receipt_with_d540_bytes_refuses_without_writes(self):
        self.write_receipts()
        (self.plugins / "AK.Wwise.Unity.API.dll").write_bytes(self.api_d540_bytes)
        game_before = (self.plugins / "RoR2.dll").read_bytes()
        receipt_path = self.streaming / "NativeViewCameraStageReceipt.json"
        receipt_before = receipt_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "API pair"):
            self.hook.restore_previous_camera(self.project, self.work)
        self.assertEqual((self.plugins / "RoR2.dll").read_bytes(), game_before)
        self.assertEqual(receipt_path.read_bytes(), receipt_before)

    def test_793_receipt_with_wrong_profile_refuses_without_writes(self):
        self.write_receipts(profile="post-audio-r4-1034-api-d540")
        game_before = (self.plugins / "RoR2.dll").read_bytes()
        receipt_path = self.streaming / "NativeViewCameraStageReceipt.json"
        receipt_before = receipt_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "profile"):
            self.hook.restore_previous_camera(self.project, self.work)
        self.assertEqual((self.plugins / "RoR2.dll").read_bytes(), game_before)
        self.assertEqual(receipt_path.read_bytes(), receipt_before)

    def test_supported_restore_receipt_fails_against_omitted_tuple_mutant(self):
        source = self.hook_path.read_text()
        block = """        (HASHES["composed_game"], HASHES["previous_composed_api_restore_only"]): (
            "post-audio-r4-1034",
            HASHES["camera_after_audio"],
        ),
"""
        self.assertEqual(source.count(block), 1, "restore-only map tuple source changed unexpectedly")
        mutant_path = self.root / "restore_793_tuple_omitted.py"
        mutant_path.parent.mkdir(parents=True, exist_ok=True)
        mutant_path.write_text(source.replace(block, "", 1))
        mutant = load("camera_hook_omitted_793_tuple", mutant_path)
        mutant.ROOT = self.root
        mutant.HASHES.update(self.hook.HASHES)
        self.write_receipts()
        game_before = (self.plugins / "RoR2.dll").read_bytes()
        receipt_path = self.streaming / "NativeViewCameraStageReceipt.json"
        receipt_before = receipt_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "outside the exact owned camera profiles"):
            mutant.restore_previous_camera(self.project, self.work)
        self.assertEqual((self.plugins / "RoR2.dll").read_bytes(), game_before)
        self.assertEqual(receipt_path.read_bytes(), receipt_before)


if __name__ == "__main__":
    unittest.main()
