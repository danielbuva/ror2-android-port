from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]
REPO = next((parent for parent in (CANDIDATE, *CANDIDATE.parents) if (parent / "AGENTS.md").is_file()), CANDIDATE)
R8 = REPO / "work/coordination/codex-original-audio-host-stage-root/r8"
RESOLVER = REPO / "work/generated/native-view-camera/resolver-sets/current-project-3124-api107-unity-2021.3.45f2-7de1415edc442a6e"
EXPECTED_GAME = "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30"
EXPECTED_OLD_CAMERA = "236fab2c616b1a017971c316437ec1a9fa9f6b3999563263d4a8ab689a1e59b6"
EXPECTED_API = "107295e478a58ef295a83228111f375c536861bc9081f482d638c59899bf495c"
EXPECTED_AUDIO = "920017966a1e890232d6a47c57d6e4c85f5dabee84a9f2ce09599e2787e61e2e"
EXPECTED_CAMERA_RECEIPT = "8c85eb19c35dba27c6d58d5680522388aec1edfa83e0400374f33bb400db6fe5"
SNAPSHOT_REL = (
    "coordination/codex-original-audio-host-stage-root/r8/native-view-camera/9b764d4bd180e7047c0dc193dc41c4ed6de5f8007c9d97bb964891af07eea9ab/RoR2.preimage.dll"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_ready() -> bool:
    paths = (
        R8 / "project/Assets/LabLoadingScene/Plugins/RoR2.dll",
        R8 / "project/Assets/StreamingAssets/Lab/NativeViewCameraStageReceipt.json",
        R8 / "project/Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json",
        RESOLVER / "assemblies/AK.Wwise.Unity.API.dll",
        R8 / "native-view-camera/9b764d4bd180e7047c0dc193dc41c4ed6de5f8007c9d97bb964891af07eea9ab/RoR2.preimage.dll",
    )
    expected = {
        paths[0]: EXPECTED_OLD_CAMERA,
        paths[1]: EXPECTED_CAMERA_RECEIPT,
        paths[2]: EXPECTED_AUDIO,
        paths[3]: EXPECTED_API,
        paths[4]: EXPECTED_GAME,
    }
    return all(path.is_file() and not path.is_symlink() and digest(path) == expected[path] for path in paths)


class DefaultReceiptRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not source_ready():
            raise unittest.SkipTest("exact Root R8 default-off camera/audio receipt fixture is absent")
        cls.scratch_parent = REPO / "work/coordination/original-camera-update-next/r6/test-scratch"
        cls.scratch_parent.mkdir(parents=True, exist_ok=True)

    def make_subject(self, mutation: str | None = None):
        temp = tempfile.TemporaryDirectory(prefix="default-restore-", dir=self.scratch_parent)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "repo"
        (root / ".git").mkdir(parents=True)
        (root / "environment").mkdir()
        shutil.copy2(REPO / "environment/toolchain.json", root / "environment/toolchain.json")
        shutil.copytree(CANDIDATE / "recipe", root / "recipe")
        hook_dir = root / "scripts/lab"
        hook_dir.mkdir(parents=True)
        shutil.copy2(CANDIDATE / "scripts/lab/native_view_camera_build_hook.py", hook_dir)
        spec = importlib.util.spec_from_file_location("r6_camera_restore_subject", hook_dir / "native_view_camera_build_hook.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        project = root / "work/project"
        plugin = project / "Assets/LabLoadingScene/Plugins"
        staged = project / "Assets/StreamingAssets/Lab"
        plugin.mkdir(parents=True)
        staged.mkdir(parents=True)
        shutil.copy2(R8 / "project/Assets/LabLoadingScene/Plugins/RoR2.dll", plugin / "RoR2.dll")
        shutil.copy2(
            RESOLVER / "assemblies/AK.Wwise.Unity.API.dll",
            plugin / "AK.Wwise.Unity.API.dll",
        )
        camera_path = staged / "NativeViewCameraStageReceipt.json"
        audio_path = staged / "OriginalGameAudioStageReceipt.json"
        shutil.copy2(
            R8 / "project/Assets/StreamingAssets/Lab/NativeViewCameraStageReceipt.json",
            camera_path,
        )
        shutil.copy2(
            R8 / "project/Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json",
            audio_path,
        )
        snapshot = root / "work" / SNAPSHOT_REL
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            R8 / "native-view-camera/9b764d4bd180e7047c0dc193dc41c4ed6de5f8007c9d97bb964891af07eea9ab/RoR2.preimage.dll",
            snapshot,
        )
        if mutation:
            camera = json.loads(camera_path.read_text())
            if mutation == "receipt-output":
                camera["output_sha256"] = "e237af4fea2b04dfecb54593e39d98862078a66de4a08272b75531303fe4b33d"
            elif mutation == "profile":
                camera["profile"] = "post-audio-r4-1034-api-d540"
            elif mutation == "api-pin":
                camera["api_sha256"] = "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23"
            elif mutation == "audio-receipt-sha":
                camera["audio_stage_receipt_sha256"] = "0" * 64
            elif mutation == "snapshot-path":
                camera["preimage_snapshot"] = "coordination/missing/RoR2.preimage.dll"
            elif mutation == "runtime-claim":
                camera["runtime_requested"] = True
            camera_path.write_text(json.dumps(camera, sort_keys=True, indent=2) + "\n")
            if mutation == "api-bytes":
                api = plugin / "AK.Wwise.Unity.API.dll"
                api.write_bytes(api.read_bytes() + b"tamper")
            elif mutation == "snapshot-bytes":
                snapshot.write_bytes(snapshot.read_bytes() + b"tamper")
        return module, root, project, plugin / "RoR2.dll", camera_path

    def test_exact_default_off_r8_receipt_restores_original_3124_input(self):
        module, root, project, game, camera = self.make_subject()
        receipt = json.loads(camera.read_text())
        self.assertEqual(receipt["profile"], "default-game-3124")
        self.assertEqual(receipt["input_sha256"], EXPECTED_GAME)
        self.assertEqual(receipt["output_sha256"], EXPECTED_OLD_CAMERA)
        self.assertEqual(receipt["api_sha256"], EXPECTED_API)
        self.assertEqual(receipt["audio_stage_receipt_sha256"], EXPECTED_AUDIO)
        self.assertIs(receipt["audio_requested"], False)
        self.assertEqual(digest(game), EXPECTED_OLD_CAMERA)
        self.assertEqual(digest(root / "work" / SNAPSHOT_REL), EXPECTED_GAME)
        result = module.restore_previous_camera(project, root / "work")
        self.assertEqual(result["restored_sha256"], EXPECTED_GAME)
        self.assertEqual(digest(game), EXPECTED_GAME)
        self.assertFalse(camera.exists())

    def test_default_predecessor_receipt_mutants_refuse_without_writing(self):
        for mutation in (
            "receipt-output",
            "profile",
            "api-pin",
            "audio-receipt-sha",
            "snapshot-path",
            "runtime-claim",
            "api-bytes",
            "snapshot-bytes",
        ):
            with self.subTest(mutation=mutation):
                module, root, project, game, camera = self.make_subject(mutation)
                before_game = digest(game)
                before_receipt = camera.read_bytes()
                with self.assertRaises(ValueError):
                    module.restore_previous_camera(project, root / "work")
                self.assertEqual(digest(game), before_game)
                self.assertEqual(camera.read_bytes(), before_receipt)


if __name__ == "__main__":
    unittest.main()
