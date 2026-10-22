"""Synthetic host contracts for current and historical observer generations."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "environment/toolchain.json").is_file())
SOURCE = ROOT
OBSERVER_PATH = SOURCE / "scripts/lab/original_music_output_observer_build_hook.py"
CAMERA_PATH = SOURCE / "scripts/lab/native_view_camera_build_hook.py"
PINS_PATH = SOURCE / "recipe/native-view-camera-transform.json"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ProfileWiringTests(unittest.TestCase):
    def test_only_qualified_1ced_path_stages_native_result_observer(self):
        camera = load(CAMERA_PATH, "camera_observer_dispatch_test")
        project, work = Path("fixture-project"), Path("fixture-work")
        for profile, expected_calls in (
            ("post-audio-point-sound-6f96-api-d540", 0),
            ("post-audio-r10-1ced-game-6f96", 1),
            ("default-game-3124", 0),
        ):
            with self.subTest(profile=profile):
                observer = Mock()
                selection = {"profile": profile, "resolver_set_directory": "fixture-resolver"}
                with (
                    patch.object(camera, "_canonical_project", return_value=(project, work)),
                    patch.object(camera, "select_profile", return_value=selection),
                    patch.object(camera, "_verify_tracked_sources", side_effect=RuntimeError("stop before camera staging")),
                    patch.dict(sys.modules, {"original_music_output_observer_build_hook": SimpleNamespace(stage=observer)}),
                ):
                    with self.assertRaisesRegex(RuntimeError, "stop before camera staging"):
                        camera.stage_after_audio(project, work, {})
                self.assertEqual(observer.call_count, expected_calls)
                if expected_calls:
                    observer.assert_called_once_with(project, work, camera.ROOT / "work/fixture-resolver", profile)

    def test_new_profile_binds_measured_chain_and_legacy_is_not_selected(self):
        pins = json.loads(PINS_PATH.read_text(encoding="utf-8"))
        name = "post-audio-native-music-results-r23-1ced"
        self.assertEqual(
            pins["profiles"][name],
            {
                "input_relative_path": "Assets/LabLoadingScene/Plugins/RoR2.dll",
                "input_sha256": "a6385e3166d3950944da8a08f145d7e9be602571a6a75b4afb18279801f44311",
                "output_sha256": "64628a52d443786d7920fc8d6b65215f32886cb3489bf5439c3efaed17e43ccf",
            },
        )
        self.assertEqual(
            pins["resolver_profiles"][name]["api_sha256"],
            "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
        )
        camera = load(CAMERA_PATH, "r23_camera_hook_profile_test")
        self.assertEqual(camera.HASHES["native_result_observed_game"], pins["profiles"][name]["input_sha256"])
        self.assertEqual(camera.HASHES["native_result_camera_output"], pins["profiles"][name]["output_sha256"])
        self.assertEqual(camera.HASHES["music_observed_game"], "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef")

    def test_observer_restore_accepts_exact_historical_r10_and_lightning_r3_pairs_only(self):
        observer = load(OBSERVER_PATH, "r23_observer_restore_test")
        old_api = "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23"
        r10_api = observer.R10_API
        raw = b"synthetic raw PointSound preimage"
        raw_hash = digest(raw)
        outputs = {
            "legacy-observer": b"synthetic legacy observer output",
            "native-result": b"synthetic measured native-result output",
            "unknown": b"synthetic unknown output",
        }
        output_hashes = {name: digest(value) for name, value in outputs.items()}
        original = {
            name: getattr(observer, name)
            for name in (
                "ROOT",
                "RAW_GAME",
                "R3_POINT_SOUND_GAME",
                "R3_NATIVE_RESULT_OBSERVED_GAME",
                "R3_CORE_OBSERVER",
                "ACCEPTED_GAME",
                "GUARDED_GAME",
                "ACCEPTED_INPUT_ID",
                "LEGACY_OBSERVED_GAME",
                "NATIVE_RESULT_OBSERVED_GAME",
                "sha",
            )
        }
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
                temp_root = Path(temporary)
                work = temp_root / "work"
                project = work / "project"
                (project / "Assets/StreamingAssets/Lab").mkdir(parents=True)
                (project / "Assets/LabLoadingScene/Plugins").mkdir(parents=True)
                (work / "snapshots").mkdir()
                observer.ROOT = temp_root
                observer.RAW_GAME = raw_hash
                observer.ACCEPTED_GAME = "a" * 64
                observer.GUARDED_GAME = "b" * 64
                observer.ACCEPTED_INPUT_ID = "c" * 64
                observer.LEGACY_OBSERVED_GAME = output_hashes["legacy-observer"]
                observer.NATIVE_RESULT_OBSERVED_GAME = output_hashes["native-result"]

                def run_case(api_hash: str, output_name: str, should_restore: bool, profile: str | None = None):
                    game = project / observer.GAME
                    game.parent.mkdir(parents=True, exist_ok=True)
                    game.write_bytes(outputs[output_name])
                    snapshot = work / "snapshots/raw.dll"
                    snapshot.write_bytes(raw)
                    api_path = project / observer.API
                    api_path.write_bytes(b"synthetic API bytes")
                    core_path = project / observer.CORE
                    core_path.write_bytes(b"synthetic core")
                    audio = {
                        "schema": "original-game-audio-project-stage-r1",
                        "requested": True,
                        "accepted_input_id": observer.ACCEPTED_INPUT_ID,
                        "lineage": {
                            "accepted_input_id": observer.ACCEPTED_INPUT_ID,
                            "accepted_game_sha256": observer.ACCEPTED_GAME,
                            "guarded_game_input_sha256": observer.GUARDED_GAME,
                            "composed_game_sha256": raw_hash,
                            "composed_api_sha256": api_hash,
                        },
                    }
                    audio_path = project / observer.AUDIO_RECEIPT
                    audio_path.parent.mkdir(parents=True, exist_ok=True)
                    audio_path.write_text(json.dumps(audio), encoding="utf-8")
                    audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
                    stage_path = project / observer.STAGE
                    receipt = {
                        "schema": observer.SCHEMA,
                        "audio_stage_receipt_sha256": audio_hash,
                        "api_sha256": api_hash,
                        "core_observer_sha256": digest(core_path.read_bytes()),
                        "input_sha256": raw_hash,
                        "audio_stage_input_game_sha256": raw_hash,
                        "output_sha256": output_hashes[output_name],
                        "preimage_snapshot": "snapshots/raw.dll",
                    }
                    if profile is not None:
                        receipt["profile"] = profile
                    stage_path.write_text(json.dumps(receipt), encoding="utf-8")
                    real_sha = observer.sha

                    def mapped_sha(path: Path) -> str:
                        if Path(path) == api_path:
                            return api_hash
                        return real_sha(path)

                    observer.sha = mapped_sha
                    before = game.read_bytes()
                    if should_restore:
                        result = observer.restore(project, work)
                        self.assertEqual(result["restored_sha256"], raw_hash)
                        self.assertEqual(game.read_bytes(), raw)
                        self.assertFalse(stage_path.exists())
                    else:
                        with self.assertRaisesRegex(ValueError, "unknown exact input/API/output pair"):
                            observer.restore(project, work)
                        self.assertEqual(game.read_bytes(), before)
                        self.assertTrue(stage_path.exists())
                    observer.sha = real_sha
                    stage_path.unlink(missing_ok=True)

                run_case(r10_api, "legacy-observer", True)
                run_case(r10_api, "native-result", True)
                run_case(old_api, "legacy-observer", True)
                run_case(old_api, "native-result", False)
                run_case(r10_api, "unknown", False)

                # Exercise the Lightning R3 branch independently of the legacy 6f96 profile.
                observer.RAW_GAME = "e" * 64
                observer.R3_POINT_SOUND_GAME = raw_hash
                observer.R3_NATIVE_RESULT_OBSERVED_GAME = output_hashes["native-result"]
                observer.R3_CORE_OBSERVER = digest(b"synthetic core")
                run_case(r10_api, "native-result", True, observer.R3_PROFILE)
        finally:
            for name, value in original.items():
                setattr(observer, name, value)

    def test_camera_unwind_rejects_cross_generation_receipt_before_write(self):
        camera = load(CAMERA_PATH, "r23_camera_unwind_crosschain_test")
        raw_bytes = b"synthetic 6f96 preimage"
        old_observer_bytes = b"synthetic legacy observer"
        new_observer_bytes = b"synthetic new observer"
        old_camera_bytes = b"synthetic legacy camera output"
        api_bytes = b"synthetic 1ced API"
        raw_hash = digest(raw_bytes)
        old_observer_hash = digest(old_observer_bytes)
        new_observer_hash = digest(new_observer_bytes)
        old_camera_hash = digest(old_camera_bytes)
        api_hash = camera.HASHES["pcm_composed_api"]
        saved_hashes = camera.HASHES.copy()
        original_root = camera.ROOT
        original_sha = camera.sha256
        camera.HASHES.update(
            {
                "point_sound_composed_game": raw_hash,
                "music_observed_game": old_observer_hash,
                "native_result_observed_game": new_observer_hash,
                "music_camera_output": old_camera_hash,
                "native_result_camera_output": digest(b"synthetic new camera"),
            }
        )
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
                temp_root = Path(temporary)
                camera.ROOT = temp_root
                work = temp_root / "work"
                project = work / "project"
                (project / "Assets/LabLoadingScene/Plugins").mkdir(parents=True)
                (project / "Assets/StreamingAssets/Lab").mkdir(parents=True)
                (work / "snapshots").mkdir(parents=True)
                game = project / camera.GAME_RELATIVE
                game.write_bytes(old_camera_bytes)
                api = project / camera.API_RELATIVE
                api.write_bytes(api_bytes)
                observer_snapshot = work / "snapshots/point-sound.dll"
                observer_snapshot.write_bytes(raw_bytes)
                camera_snapshot = work / "snapshots/legacy-observer.dll"
                camera_snapshot.write_bytes(old_observer_bytes)
                audio = {
                    "schema": camera.AUDIO_SCHEMA,
                    "requested": True,
                    "lineage": {
                        "composed_game_sha256": raw_hash,
                        "composed_api_sha256": api_hash,
                    },
                }
                audio_path = project / camera.AUDIO_STAGE_RELATIVE
                audio_path.write_text(json.dumps(audio), encoding="utf-8")
                audio_sha = hashlib.sha256(audio_path.read_bytes()).hexdigest()
                observer_stage = project / "Assets/StreamingAssets/Lab/OriginalMusicOutputObserverStageReceipt.json"
                observer_stage.write_text(
                    json.dumps(
                        {
                            "schema": "original-music-output-observer-stage-r1",
                            "accepted": False,
                            "runtime_dispatch_ready": False,
                            "audio_stage_receipt_sha256": audio_sha,
                            "input_sha256": raw_hash,
                            "output_sha256": new_observer_hash,
                            "api_sha256": api_hash,
                            "preimage_snapshot": observer_snapshot.relative_to(work).as_posix(),
                        }
                    ),
                    encoding="utf-8",
                )
                camera_receipt_path = project / camera.CAMERA_STAGE_RELATIVE
                camera_receipt_path.write_text(
                    json.dumps(
                        {
                            "schema": camera.STAGE_SCHEMA,
                            "profile": "post-audio-music-observer-r10-1ced",
                            "input_sha256": old_observer_hash,
                            "output_sha256": old_camera_hash,
                            "audio_stage_receipt_sha256": audio_sha,
                            "audio_requested": True,
                            "api_sha256": api_hash,
                            "preimage_snapshot": camera_snapshot.relative_to(work).as_posix(),
                            "accepted": False,
                            "runtime_requested": False,
                            "runtime_dispatch_ready": False,
                        }
                    ),
                    encoding="utf-8",
                )

                def mapped_sha(path: Path) -> str:
                    if Path(path) == api:
                        return api_hash
                    return original_sha(path)

                camera.sha256 = mapped_sha
                before = game.read_bytes()
                with self.assertRaisesRegex(ValueError, "exact observer/API camera lineage"):
                    camera.restore_previous_camera(project, work)
                self.assertEqual(game.read_bytes(), before)
                self.assertTrue(camera_receipt_path.exists())
        finally:
            camera.HASHES.clear()
            camera.HASHES.update(saved_hashes)
            camera.ROOT = original_root
            camera.sha256 = original_sha

    def test_camera_receipt_game_hash_is_scoped_to_observer_generation(self):
        camera = load(CAMERA_PATH, "r23_camera_receipt_test")
        old_observer = b"old observer"
        new_observer = b"new observer"
        old_camera = b"old camera output"
        old_delegate = b"old delegate output"
        new_camera = b"new camera output"
        raw = b"raw preimage"
        old_api = "1" * 64
        new_api = "2" * 64
        hashes = camera.HASHES.copy()
        camera.HASHES.update(
            {
                "point_sound_composed_game": digest(raw),
                "composed_api": old_api,
                "pcm_composed_api": new_api,
                "music_observed_game": digest(old_observer),
                "native_result_observed_game": digest(new_observer),
                "music_camera_output": digest(old_camera),
                "camera_music_observer_delegate_previous_restore_only": digest(old_delegate),
                "native_result_camera_output": digest(new_camera),
            }
        )
        original_root = camera.ROOT
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
                temp_root = Path(temporary)
                camera.ROOT = temp_root
                work = temp_root / "work"
                project = work / "project"
                (project / "Assets/LabLoadingScene/Plugins").mkdir(parents=True)
                (project / "Assets/StreamingAssets/Lab").mkdir(parents=True)
                snapshot = work / "snapshots/raw.dll"
                snapshot.parent.mkdir(parents=True)
                snapshot.write_bytes(raw)
                snapshot_rel = snapshot.relative_to(work).as_posix()

                def check(api_hash: str, observer_hash: str, game_bytes: bytes, allowed: bool):
                    game = project / camera.GAME_RELATIVE
                    game.write_bytes(game_bytes)
                    before = game.read_bytes()
                    receipt = {
                        "schema": "original-music-output-observer-stage-r1",
                        "accepted": False,
                        "runtime_dispatch_ready": False,
                        "audio_stage_receipt_sha256": "e" * 64,
                        "input_sha256": digest(raw),
                        "output_sha256": observer_hash,
                        "api_sha256": api_hash,
                        "preimage_snapshot": snapshot_rel,
                    }
                    stage = project / "Assets/StreamingAssets/Lab/OriginalMusicOutputObserverStageReceipt.json"
                    stage.write_text(json.dumps(receipt), encoding="utf-8")
                    audio = {"lineage": {"composed_game_sha256": digest(raw), "composed_api_sha256": api_hash}}
                    if allowed:
                        camera._music_observer_receipt(project, "e" * 64, audio)
                    else:
                        with self.assertRaisesRegex(ValueError, "exact observer/API camera lineage"):
                            camera._music_observer_receipt(project, "e" * 64, audio)
                        self.assertEqual(game.read_bytes(), before)

                check(new_api, digest(new_observer), new_observer, True)
                check(new_api, digest(new_observer), new_camera, True)
                check(old_api, digest(old_observer), old_delegate, True)
                check(new_api, digest(new_observer), old_camera, False)
                check(old_api, digest(old_observer), new_camera, False)
        finally:
            camera.HASHES.clear()
            camera.HASHES.update(hashes)
            camera.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
