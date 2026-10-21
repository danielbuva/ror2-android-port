from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]
ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / ".git").exists())
R12 = ROOT / "work/experiments/original-game-audio/candidate-20261021T085802.632468Z"
CAMERA_RECEIPT = R12 / "NativeViewCameraStageReceipt.json"
AUDIO_RECEIPT = R12 / "OriginalGameAudioStageReceipt.json"
BUILD_RECEIPT = R12 / "build-receipt.json"
OLD_GENERATION = "2e3c7ddab09cc8f33c1dd911ec096b62efcbfee106c030b9fdd69ad8b6902510"
OLD_GENERATION_DIR = ROOT / "work/native-view-camera" / OLD_GENERATION
OLD_CAMERA_DLL = OLD_GENERATION_DIR / "RoR2.native-view-camera.dll"
PREIMAGE_DLL = OLD_GENERATION_DIR / "RoR2.preimage.dll"
API_1CED = ROOT / "work/lab-build/player-linker-inputs/20261021T065114.990266Z-89a9142c5ff0485e80728aa12294ece7/assemblies/AK.Wwise.Unity.API.dll"
API_D540 = (
    ROOT
    / "work/coordination/codex-original-audio-host-stage-root/r4/original-game-audio-owner/b653ba648a1624781279e0ce7422dd903a042c1fb4778c7e2118bb570ee9d3af/managed-chain/api-instrumented-composed.dll"
)
CURRENT_CAMERA_DLL = ROOT / "work/coordination/original-camera-update-next/r3/official-producer-final/RoR2.native-view-camera.dll"
EXPECTED = {
    "camera_old": "f6bc1a860e8abe2c82a397a83e55ec2050136e91763ade302ed0e181b320083c",
    "camera_current": "41b66d072085f70b6929dcd2a566fffff3f26b9c886d8781624e52ae8ab7e92f",
    "game": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
    "api_1ced": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
    "api_d540": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
    "audio_receipt": "3ee4a886d845e8b89421517c93cefb32d6004bf8653727f32ed100cb173c9287",
    "camera_receipt": "ee456b8f1a66d1ec2a3a59d982b509235238d2364b4e087a08961cefa3e27f0e",
    "build_receipt": "42be6cd338ae430e68e9fdcf6e2de4d18d15957258089cdc331e517aab83cc78",
    "apk": "fae79734107d07d7c9a8af838961ccf82b4e6fa530e4f1a6238b17eda3a44b1d",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_ready() -> bool:
    expected = {
        CAMERA_RECEIPT: EXPECTED["camera_receipt"],
        BUILD_RECEIPT: EXPECTED["build_receipt"],
        AUDIO_RECEIPT: EXPECTED["audio_receipt"],
        OLD_CAMERA_DLL: EXPECTED["camera_old"],
        PREIMAGE_DLL: EXPECTED["game"],
        API_1CED: EXPECTED["api_1ced"],
        API_D540: EXPECTED["api_d540"],
        CURRENT_CAMERA_DLL: EXPECTED["camera_current"],
    }
    return all(path.is_file() and (value is None or digest(path) == value) for path, value in expected.items())


class CameraRestorePredecessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scratch_parent = Path(os.environ.get("ORIGINAL_CAMERA_RESTORE_TEST_ROOT", tempfile.gettempdir()))
        cls.scratch_parent.mkdir(parents=True, exist_ok=True)
        if not evidence_ready():
            raise unittest.SkipTest("exact R12 camera/audio receipts and pinned source snapshots are not available locally")
        build = json.loads(BUILD_RECEIPT.read_text())
        if build.get("apk_sha256") != EXPECTED["apk"] or build.get("input_id") != "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88":
            raise unittest.SkipTest("R12 build receipt no longer binds the expected accepted input/APK")
        cls.module_source = CANDIDATE / "scripts/lab/native_view_camera_build_hook.py"

    def new_module_and_project(
        self,
        *,
        api_kind: str = "1ced",
        camera_kind: str = "old",
        mutation: str | None = None,
    ):
        temporary = tempfile.TemporaryDirectory(prefix="camera-restore-", dir=self.scratch_parent)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "repo"
        (root / ".git").mkdir(parents=True)
        (root / "recipe").mkdir()
        (root / "environment").mkdir()
        (root / "environment/toolchain.json").write_text("{}\n")
        lab = root / "scripts/lab"
        lab.mkdir(parents=True)
        module_path = lab / "native_view_camera_build_hook.py"
        shutil.copy2(self.module_source, module_path)
        module_spec = importlib.util.spec_from_file_location("camera_restore_subject", module_path)
        self.assertIsNotNone(module_spec)
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_spec.name] = module
        module_spec.loader.exec_module(module)

        work = root / "work"
        project = work / "project"
        stage_dir = project / "Assets/StreamingAssets/Lab"
        plugin_dir = project / "Assets/LabLoadingScene/Plugins"
        stage_dir.mkdir(parents=True)
        plugin_dir.mkdir(parents=True)
        snapshot = work / "native-view-camera" / OLD_GENERATION / "RoR2.preimage.dll"
        snapshot.parent.mkdir(parents=True)
        shutil.copy2(PREIMAGE_DLL, snapshot)
        shutil.copy2(
            OLD_CAMERA_DLL if camera_kind == "old" else CURRENT_CAMERA_DLL,
            plugin_dir / "RoR2.dll",
        )
        shutil.copy2(
            API_1CED if api_kind == "1ced" else API_D540,
            plugin_dir / "AK.Wwise.Unity.API.dll",
        )

        camera = json.loads(CAMERA_RECEIPT.read_text())
        audio_bytes = AUDIO_RECEIPT.read_bytes()
        audio = json.loads(audio_bytes)
        if api_kind == "d540":
            audio["lineage"]["composed_api_sha256"] = EXPECTED["api_d540"]
            audio_bytes = (json.dumps(audio, sort_keys=True, indent=2) + "\n").encode()
        camera["audio_stage_receipt_sha256"] = hashlib.sha256(audio_bytes).hexdigest()
        camera["api_sha256"] = EXPECTED["api_1ced"] if api_kind == "1ced" else EXPECTED["api_d540"]
        camera["preimage_snapshot"] = "native-view-camera/" + OLD_GENERATION + "/RoR2.preimage.dll"
        camera["output_sha256"] = EXPECTED["camera_old"] if camera_kind == "old" else EXPECTED["camera_current"]
        if camera_kind == "current":
            camera["producer_receipt_sha256"] = digest(
                ROOT / "work/coordination/original-camera-update-next/r3/official-producer-final/RoR2.native-view-camera.dll.producer-receipt.json"
            )
        if mutation == "receipt_sha":
            camera["audio_stage_receipt_sha256"] = "0" * 64
        elif mutation == "mode":
            camera["audio_requested"] = False
        elif mutation == "profile":
            camera["profile"] = "post-audio-r4-1034-api-d540"
        elif mutation == "api_identity":
            camera["api_sha256"] = "0" * 64
        elif mutation == "lineage":
            audio["lineage"]["composed_game_sha256"] = "0" * 64
            audio_bytes = (json.dumps(audio, sort_keys=True, indent=2) + "\n").encode()
            camera["audio_stage_receipt_sha256"] = hashlib.sha256(audio_bytes).hexdigest()
        elif mutation == "snapshot_path":
            camera["preimage_snapshot"] = "native-view-camera/missing/RoR2.preimage.dll"
        elif mutation == "output_identity":
            camera["output_sha256"] = "0" * 64
        elif mutation == "runtime_claim":
            camera["runtime_dispatch_ready"] = True

        if mutation == "api_bytes":
            api_path = plugin_dir / "AK.Wwise.Unity.API.dll"
            api_path.write_bytes(api_path.read_bytes() + b"tamper")
        elif mutation == "snapshot_bytes":
            snapshot.write_bytes(snapshot.read_bytes() + b"tamper")
        elif mutation == "output_bytes":
            game_path = plugin_dir / "RoR2.dll"
            game_path.write_bytes(game_path.read_bytes() + b"tamper")
        elif mutation == "audio_content":
            audio["lineage"]["composed_game_sha256"] = "0" * 64
            audio_bytes = (json.dumps(audio, sort_keys=True, indent=2) + "\n").encode()
            camera["audio_stage_receipt_sha256"] = hashlib.sha256(audio_bytes).hexdigest()

        (stage_dir / "OriginalGameAudioStageReceipt.json").write_bytes(audio_bytes)
        camera_path = stage_dir / "NativeViewCameraStageReceipt.json"
        camera_path.write_text(json.dumps(camera, sort_keys=True, indent=2) + "\n")
        return module, root, work, project, camera_path

    def test_actual_r12_predecessor_receipt_restores_only_its_exact_preimage(self):
        module, root, work, project, camera_path = self.new_module_and_project()
        before_stage = json.loads(camera_path.read_text())
        self.assertEqual(before_stage["profile"], "post-audio-r10-1ced-game-6f96")
        self.assertEqual(before_stage["api_sha256"], EXPECTED["api_1ced"])
        self.assertEqual(before_stage["input_sha256"], EXPECTED["game"])
        self.assertEqual(before_stage["audio_stage_receipt_sha256"], EXPECTED["audio_receipt"])
        self.assertIs(before_stage["accepted"], False)
        self.assertIs(before_stage["runtime_requested"], False)
        self.assertIs(before_stage["runtime_dispatch_ready"], False)
        before_game = digest(project / "Assets/LabLoadingScene/Plugins/RoR2.dll")
        self.assertEqual(before_stage["output_sha256"], EXPECTED["camera_old"])
        self.assertEqual(before_game, EXPECTED["camera_old"])
        result = module.restore_previous_camera(project, work)
        self.assertEqual(result["restored_sha256"], EXPECTED["game"])
        self.assertEqual(
            digest(project / "Assets/LabLoadingScene/Plugins/RoR2.dll"),
            EXPECTED["game"],
        )
        self.assertFalse(camera_path.exists())
        self.assertEqual(digest(OLD_CAMERA_DLL), EXPECTED["camera_old"])
        self.assertEqual(digest(PREIMAGE_DLL), EXPECTED["game"])
        # The already-staged exact audio receipt remains the input to the next
        # camera operation; selection must use the current output, not f6bc.
        audio = json.loads((project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json").read_text())
        profile, next_output = module._select_point_sound_profile(audio, EXPECTED["game"], EXPECTED["api_1ced"])
        self.assertEqual(profile, "post-audio-r10-1ced-game-6f96")
        self.assertEqual(next_output, EXPECTED["camera_current"])
        self.assertNotEqual(next_output, EXPECTED["camera_old"])

    def test_new_camera_output_still_restores_for_current_pair(self):
        module, root, work, project, camera_path = self.new_module_and_project(camera_kind="current")
        result = module.restore_previous_camera(project, work)
        self.assertEqual(result["restored_sha256"], EXPECTED["game"])
        self.assertEqual(
            digest(project / "Assets/LabLoadingScene/Plugins/RoR2.dll"),
            EXPECTED["game"],
        )
        self.assertFalse(camera_path.exists())

    def test_predecessor_restore_is_limited_to_declared_d540_and_1ced_profiles(self):
        module, *_ = self.new_module_and_project()
        source = json.loads(AUDIO_RECEIPT.read_text())
        source["passive_pcm_capture_requested"] = False
        source["outputs"] = [{"target": module.GAME_RELATIVE.as_posix(), "sha256": EXPECTED["game"]}]
        source["lineage"] = {
            "composed_game_sha256": EXPECTED["game"],
            "composed_api_sha256": EXPECTED["api_1ced"],
        }
        self.assertEqual(
            module._select_point_sound_profile(source, EXPECTED["game"], EXPECTED["api_1ced"]),
            ("post-audio-r10-1ced-game-6f96", EXPECTED["camera_current"]),
        )
        source["lineage"]["composed_api_sha256"] = EXPECTED["api_d540"]
        self.assertEqual(
            module._select_point_sound_profile(source, EXPECTED["game"], EXPECTED["api_d540"]),
            ("post-audio-point-sound-6f96-api-d540", EXPECTED["camera_current"]),
        )
        self.assertNotEqual(
            module.HASHES["camera_predecessor_f6bc_restore_only"],
            EXPECTED["camera_current"],
        )

    def test_receipt_profile_api_snapshot_and_bytes_mutants_refuse_without_changes(
        self,
    ):
        for mutation in (
            "receipt_sha",
            "mode",
            "profile",
            "api_identity",
            "lineage",
            "snapshot_path",
            "output_identity",
            "runtime_claim",
            "api_bytes",
            "snapshot_bytes",
            "output_bytes",
            "audio_content",
        ):
            with self.subTest(mutation=mutation):
                module, root, work, project, camera_path = self.new_module_and_project(mutation=mutation)
                game = project / "Assets/LabLoadingScene/Plugins/RoR2.dll"
                before_game = digest(game)
                before_receipt = camera_path.read_bytes()
                with self.assertRaises(ValueError):
                    module.restore_previous_camera(project, work)
                self.assertEqual(digest(game), before_game)
                self.assertEqual(camera_path.read_bytes(), before_receipt)


if __name__ == "__main__":
    unittest.main()
