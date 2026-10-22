"""Host contracts for the exact R3 music-result to camera continuation."""

from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace


TEST_ROOT = Path(__file__).resolve().parents[1]
R4 = TEST_ROOT.parent if TEST_ROOT.name == "apply" else TEST_ROOT
if (R4 / "source/scripts/lab/native_view_camera_build_hook.py").is_file():
    MODULE_ROOT = R4 / "source"
elif (TEST_ROOT / "scripts/lab/native_view_camera_build_hook.py").is_file():
    MODULE_ROOT = TEST_ROOT
else:
    MODULE_ROOT = R4


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


music = load_module(
    "r4_music_observer_hook",
    "scripts/lab/original_music_output_observer_build_hook.py",
)
camera = load_module("r4_camera_hook", "scripts/lab/native_view_camera_build_hook.py")


class LightningR3MusicCameraPipelineTests(unittest.TestCase):
    def test_uncached_music_resolver_profile_materializes_without_camera_output_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "RoR2.dll"
            source.write_bytes(b"synthetic audio-owned module")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            profile = "post-audio-r10-1ced-game-lightning-r3"
            api_hash = "a" * 64
            pins = {
                "profiles": {},
                "music_observer_resolver_profiles": {profile: {"input_sha256": source_hash}},
            }
            resolver_set = {"profile": "synthetic-resolver"}
            materialize = Mock()
            module = SimpleNamespace(source_rows=Mock(return_value=[]), materialize=materialize)
            with patch.object(camera, "_resolver_module", return_value=module):
                result = camera._ensure_resolver_set(root / "resolvers", resolver_set, root, source, api_hash, profile, pins, root / "editor")
            materialize.assert_called_once()
            args = materialize.call_args.args
            self.assertEqual(args[:4], (profile, root, source, root / "editor"))
            self.assertEqual(args[-2:], (source_hash, api_hash))
            self.assertEqual(result, args[4] / "assemblies")
            materialize.reset_mock()
            source.write_bytes(b"drifted audio-owned module")
            with patch.object(camera, "_resolver_module", return_value=module):
                with self.assertRaisesRegex(ValueError, "exact source input"):
                    camera._ensure_resolver_set(root / "resolvers", resolver_set, root, source, api_hash, profile, pins, root / "editor")
            materialize.assert_not_called()

    def test_observer_profile_requires_exact_r3_game_api_and_core(self):
        self.assertEqual(
            music._observer_output_profile(music.R3_POINT_SOUND_GAME, music.R10_API, music.R3_CORE_OBSERVER),
            (music.R3_PROFILE, music.R3_NATIVE_RESULT_OBSERVED_GAME),
        )
        self.assertEqual(
            music._observer_output_profile(music.RAW_GAME, music.R10_API, "legacy-core"),
            ("post-audio-r10-1ced-game-6f96", music.NATIVE_RESULT_OBSERVED_GAME),
        )
        with self.assertRaises(ValueError):
            music._observer_output_profile(music.R3_POINT_SOUND_GAME, music.R10_API, "0" * 64)
        with self.assertRaises(ValueError):
            music._observer_output_profile(music.R3_POINT_SOUND_GAME, music.R10_API, music.R3_CORE_PREDECESSOR_RESTORE_ONLY)
        with self.assertRaises(ValueError):
            music._observer_output_profile(music.R3_POINT_SOUND_GAME, "0" * 64, music.R3_CORE_OBSERVER)
        with self.assertRaises(ValueError):
            music._observer_output_profile("0" * 64, music.R10_API, music.R3_CORE_OBSERVER)

    def test_camera_selects_r3_from_exact_audio_lineage(self):
        audio = {
            "requested": True,
            "stage_receipt_sha256": camera.HASHES["stage_receipt_sha256"],
            "lineage": {
                "composed_game_sha256": camera.HASHES["lightning_r3_point_sound_composed_game"],
                "composed_api_sha256": camera.HASHES["pcm_composed_api"],
            },
            "outputs": [
                {
                    "target": camera.GAME_RELATIVE.as_posix(),
                    "sha256": camera.HASHES["lightning_r3_point_sound_composed_game"],
                }
            ],
        }
        self.assertEqual(
            camera._select_point_sound_profile(
                audio,
                camera.HASHES["lightning_r3_point_sound_composed_game"],
                camera.HASHES["pcm_composed_api"],
            ),
            (
                "post-audio-r10-1ced-game-lightning-r3",
                camera.HASHES["lightning_r3_native_result_observed_game"],
            ),
        )
        pins = json.loads(camera.CAMERA_PINS.read_text(encoding="utf-8"))
        final_profile = pins["profiles"]["post-audio-native-music-results-lightning-r3-1ced"]
        resolver_profile = pins["resolver_profiles"]["post-audio-native-music-results-lightning-r3-1ced"]
        self.assertEqual(final_profile["input_sha256"], music.R3_NATIVE_RESULT_OBSERVED_GAME)
        self.assertEqual(final_profile["output_sha256"], "15a92aa6f513e2271ce7240c33a205b0376fff37200089987f0cb54944c3382c")
        self.assertEqual(resolver_profile["api_sha256"], music.R10_API)
        for bad in (
            {**audio, "stage_receipt_sha256": "0" * 64},
            {
                **audio,
                "lineage": {**audio["lineage"], "composed_api_sha256": "0" * 64},
            },
            {**audio, "outputs": []},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                camera._select_point_sound_profile(
                    bad,
                    camera.HASHES["lightning_r3_point_sound_composed_game"],
                    camera.HASHES["pcm_composed_api"],
                )

    def test_music_receipt_joins_exact_r3_input_and_camera_result(self):
        with tempfile.TemporaryDirectory(dir=R4) as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            (root / "work").mkdir()
            old_root = camera.ROOT
            old_hashes = camera.HASHES
            camera.ROOT = root
            input_bytes = b"synthetic exact PointSound preimage"
            output_bytes = b"synthetic exact native-result observer output"
            input_hash = hashlib.sha256(input_bytes).hexdigest()
            output_hash = hashlib.sha256(output_bytes).hexdigest()
            api_hash = "1" * 64
            camera.HASHES = {
                **old_hashes,
                "lightning_r3_point_sound_composed_game": input_hash,
                "lightning_r3_native_result_observed_game": output_hash,
                "lightning_r3_native_result_camera_output": "2" * 64,
                "pcm_composed_api": api_hash,
            }
            project = root / "project"
            game_path = project / camera.GAME_RELATIVE
            game_path.parent.mkdir(parents=True)
            game_path.write_bytes(output_bytes)
            snapshot = root / "work/r3-point-sound-snapshot.dll"
            snapshot.write_bytes(input_bytes)
            snapshot_rel = snapshot.relative_to(root / "work").as_posix()
            audio_sha = "a" * 64
            receipt = {
                "schema": "original-music-output-observer-stage-r1",
                "accepted": False,
                "runtime_dispatch_ready": False,
                "audio_stage_receipt_sha256": audio_sha,
                "input_sha256": input_hash,
                "output_sha256": output_hash,
                "profile": music.R3_PROFILE,
                "api_sha256": api_hash,
                "preimage_snapshot": snapshot_rel,
            }
            receipt["lineage"] = {
                "composed_game_sha256": input_hash,
                "composed_api_sha256": api_hash,
            }
            receipt_path = project / camera.AUDIO_STAGE_RELATIVE
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(json.dumps({"unused": True}), encoding="utf-8")
            observer_path = project / "Assets/StreamingAssets/Lab/OriginalMusicOutputObserverStageReceipt.json"
            observer_path.write_text(json.dumps(receipt), encoding="utf-8")
            try:
                audio = {"lineage": receipt["lineage"]}
                result = camera._music_observer_receipt(project, audio_sha, audio)
                self.assertEqual(result["output_sha256"], output_hash)

                receipt["profile"] = "post-audio-r10-1ced-game-6f96"
                observer_path.write_text(json.dumps(receipt), encoding="utf-8")
                with self.assertRaises(ValueError):
                    camera._music_observer_receipt(project, audio_sha, audio)
            finally:
                camera.ROOT = old_root
                camera.HASHES = old_hashes


if __name__ == "__main__":
    unittest.main()
