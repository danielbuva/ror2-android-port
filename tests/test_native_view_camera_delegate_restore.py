from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts/lab/native_view_camera_build_hook.py"
PREVIOUS_OUTPUTS = {
    "default": "d5fc522e83cb6f6f6845b2a8b7e5de28011031fe2f3b54c0716c52db9679c65c",
    "audio1034": "e4aeeb5acb7b81922a0a6603d01c1d407c57e9b00852b5e15ef70838e1961e5b",
    "pointsound": "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384",
    "musicobserver": "a2054dcfc5d14d2fdfba0fd0e61851e4a153b842be6bb6f1c0e1df8ef634762e",
}
CASES = (
    ("default", "ordinary_game", "ordinary_api", "default-game-3124", "camera_default_delegate_previous_restore_only", False),
    ("audio1034", "composed_game", "composed_api", "post-audio-r4-1034-api-d540", "camera_after_audio_delegate_previous_restore_only", True),
    (
        "pointsound",
        "point_sound_composed_game",
        "composed_api",
        "post-audio-point-sound-6f96-api-d540",
        "camera_after_point_sound_delegate_previous_restore_only",
        True,
    ),
    (
        "pointsound",
        "point_sound_composed_game",
        "pcm_composed_api",
        "post-audio-r10-1ced-game-6f96",
        "camera_after_point_sound_delegate_previous_restore_only",
        True,
    ),
    (
        "musicobserver",
        "music_observed_game",
        "composed_api",
        "post-audio-music-observer-6f96-api-d540",
        "camera_music_observer_delegate_previous_restore_only",
        True,
    ),
    (
        "musicobserver",
        "music_observed_game",
        "pcm_composed_api",
        "post-audio-music-observer-r10-1ced",
        "camera_music_observer_delegate_previous_restore_only",
        True,
    ),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_hook(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import copied camera hook")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PreDelegateRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pre-delegate-camera-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "repo"
        (self.root / ".git").mkdir(parents=True)
        (self.root / "recipe").mkdir()
        (self.root / "environment").mkdir()
        (self.root / "scripts/lab").mkdir(parents=True)
        (self.root / "environment/toolchain.json").write_text("{}\n")
        shutil.copy2(HOOK, self.root / "scripts/lab/native_view_camera_build_hook.py")
        shutil.copy2(REPO / "recipe/native-view-camera-transform.json", self.root / "recipe/native-view-camera-transform.json")

    def fixture(self, case, mutation=None):
        module = load_hook("private_camera_hook", self.root / "scripts/lab/native_view_camera_build_hook.py")
        module.ROOT = self.root
        module.CAMERA_SOURCE_ROOT = self.root
        name, input_key, api_key, profile, previous_key, requested = case
        hashes = module.HASHES
        input_bytes = ("input:" + name).encode()
        api_bytes = ("api:" + api_key).encode()
        old_output_bytes = ("prior-camera-output:" + name + ":" + api_key).encode()
        input_hash, api_hash, old_output_hash = map(digest, (input_bytes, api_bytes, old_output_bytes))
        current_output_hash = digest(("new-camera-output:" + name + ":" + api_key).encode())
        hashes[input_key] = input_hash
        hashes[api_key] = api_hash
        hashes[previous_key] = old_output_hash
        if name == "default":
            hashes["camera_default"] = current_output_hash
        elif name == "audio1034":
            hashes["camera_after_audio"] = current_output_hash
        elif name == "pointsound":
            if api_key == "composed_api":
                hashes["camera_after_point_sound"] = current_output_hash
            else:
                hashes["camera_after_r10_1ced"] = current_output_hash
        else:
            hashes["music_camera_output"] = current_output_hash

        work = self.root / "work"
        project = work / "project"
        stage = project / "Assets/StreamingAssets/Lab"
        plugins = project / "Assets/LabLoadingScene/Plugins"
        stage.mkdir(parents=True, exist_ok=True)
        plugins.mkdir(parents=True, exist_ok=True)
        snapshot = work / "coordination/input.dll"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(input_bytes)
        (plugins / "RoR2.dll").write_bytes(old_output_bytes)
        (plugins / "AK.Wwise.Unity.API.dll").write_bytes(api_bytes)

        lineage = {}
        if name == "audio1034":
            lineage = {"composed_game_sha256": input_hash, "composed_api_sha256": api_hash}
        elif name == "pointsound":
            lineage = {"composed_game_sha256": input_hash, "composed_api_sha256": api_hash}
        elif name == "musicobserver":
            point_sound_bytes = b"point-sound-preimage"
            point_sound_hash = digest(point_sound_bytes)
            hashes["point_sound_composed_game"] = point_sound_hash
            observer_bytes = input_bytes
            audio_bytes = b"accepted-audio-receipt"
            lineage = {"composed_game_sha256": point_sound_hash, "composed_api_sha256": api_hash}
            (work / "coordination/point-sound.dll").write_bytes(point_sound_bytes)
            observer = {
                "schema": "original-music-output-observer-stage-r1",
                "accepted": False,
                "runtime_dispatch_ready": False,
                "audio_stage_receipt_sha256": digest(audio_bytes),
                "input_sha256": point_sound_hash,
                "output_sha256": input_hash,
                "api_sha256": api_hash,
                "preimage_snapshot": "coordination/point-sound.dll",
            }
            (stage / "OriginalMusicOutputObserverStageReceipt.json").write_text(json.dumps(observer))
        else:
            audio_bytes = b'{"schema":"original-game-audio-project-stage-r1","requested":false,"lineage":{}}'
        if name != "musicobserver":
            audio = {"schema": module.AUDIO_SCHEMA, "requested": requested, "lineage": lineage}
            audio_bytes = json.dumps(audio, sort_keys=True).encode()
        else:
            audio = {"schema": module.AUDIO_SCHEMA, "requested": True, "lineage": lineage}
            audio_bytes = json.dumps(audio, sort_keys=True).encode()
            observer_path = stage / "OriginalMusicOutputObserverStageReceipt.json"
            observer = json.loads(observer_path.read_text())
            observer["audio_stage_receipt_sha256"] = digest(audio_bytes)
            observer_path.write_text(json.dumps(observer))
        (stage / "OriginalGameAudioStageReceipt.json").write_bytes(audio_bytes)

        receipt = {
            "schema": module.STAGE_SCHEMA,
            "accepted": False,
            "runtime_requested": False,
            "runtime_dispatch_ready": False,
            "input_sha256": input_hash,
            "output_sha256": old_output_hash,
            "api_sha256": api_hash,
            "audio_stage_receipt_sha256": digest(audio_bytes),
            "audio_requested": requested,
            "profile": profile,
            "preimage_snapshot": "coordination/input.dll",
        }
        if mutation == "output":
            receipt["output_sha256"] = digest(b"wrong-output")
            (plugins / "RoR2.dll").write_bytes(b"wrong-output")
        elif mutation == "profile":
            receipt["profile"] = "post-audio-r4-1034-api-d540" if profile != "post-audio-r4-1034-api-d540" else "default-game-3124"
        elif mutation == "api":
            (plugins / "AK.Wwise.Unity.API.dll").write_bytes(api_bytes + b"tamper")
        elif mutation == "snapshot":
            snapshot.write_bytes(input_bytes + b"tamper")
        elif mutation == "audio-receipt":
            receipt["audio_stage_receipt_sha256"] = "0" * 64
        receipt_path = stage / "NativeViewCameraStageReceipt.json"
        receipt_path.write_text(json.dumps(receipt, sort_keys=True))
        return module, work, project, receipt_path, plugins / "RoR2.dll", old_output_hash, input_hash

    def test_four_exact_prior_images_are_restore_only_for_owned_tuples(self):
        module = load_hook("constant_check", self.root / "scripts/lab/native_view_camera_build_hook.py")
        for key, expected in (
            ("camera_default_delegate_previous_restore_only", PREVIOUS_OUTPUTS["default"]),
            ("camera_after_audio_delegate_previous_restore_only", PREVIOUS_OUTPUTS["audio1034"]),
            ("camera_after_point_sound_delegate_previous_restore_only", PREVIOUS_OUTPUTS["pointsound"]),
            ("camera_music_observer_delegate_previous_restore_only", PREVIOUS_OUTPUTS["musicobserver"]),
        ):
            self.assertEqual(module.HASHES[key], expected)

    def test_all_exact_old_output_receipts_restore_and_remove_only_camera_receipt(self):
        for case in CASES:
            with self.subTest(profile=case[3], api=case[2]):
                module, work, project, receipt, game, old_hash, input_hash = self.fixture(case)
                result = module.restore_previous_camera(project, work)
                self.assertEqual(result["restored_sha256"], input_hash)
                self.assertEqual(digest(game.read_bytes()), input_hash)
                self.assertFalse(receipt.exists())
                self.assertTrue((project / module.AUDIO_STAGE_RELATIVE).is_file())

    def test_mismatched_tuple_receipt_or_preimage_refuses_before_writes(self):
        for case in CASES:
            for mutation in ("output", "profile", "api", "snapshot", "audio-receipt"):
                with self.subTest(profile=case[3], api=case[2], mutation=mutation):
                    module, work, project, receipt, game, _, _ = self.fixture(case, mutation)
                    before_game = game.read_bytes()
                    before_receipt = receipt.read_bytes()
                    with self.assertRaises(ValueError):
                        module.restore_previous_camera(project, work)
                    self.assertEqual(game.read_bytes(), before_game)
                    self.assertEqual(receipt.read_bytes(), before_receipt)


if __name__ == "__main__":
    unittest.main()
