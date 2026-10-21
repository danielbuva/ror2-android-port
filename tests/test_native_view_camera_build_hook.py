from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load copied tracked module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrackedCameraSourcesTests(unittest.TestCase):
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
