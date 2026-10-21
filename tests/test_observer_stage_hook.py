from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from _music_observer_test_support import cecil, digest, dotnet, required_directory, required_file


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / ".git").exists():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_root()
RAW_GAME = "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc"
OBSERVED_GAME = "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef"
API_PROFILES = {
    "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
    "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
}
CORE_TARGET = "Assets/LabLoadingScene/Plugins/OriginalOwnerProbeObserver.dll"
AUDIO_RECEIPT = "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"


class MusicObserverStageHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_project = required_directory("MUSIC_OBSERVER_STAGE_PROJECT")
        source_game = required_file("MUSIC_OBSERVER_GAME_DLL", RAW_GAME)
        if digest(cls.source_project / "Assets/LabLoadingScene/Plugins/RoR2.dll") != RAW_GAME:
            raise AssertionError("MUSIC_OBSERVER_STAGE_PROJECT does not contain the pinned raw game module")
        receipt_path = cls.source_project / AUDIO_RECEIPT
        if not receipt_path.is_file():
            raise AssertionError("MUSIC_OBSERVER_STAGE_PROJECT lacks an original-audio stage receipt")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        lineage = receipt.get("lineage", {})
        api_hash = lineage.get("composed_api_sha256")
        if api_hash not in API_PROFILES or digest(cls.source_project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll") != api_hash:
            raise AssertionError("stage project does not contain an exact pinned d540/1ced game/API pair")
        if digest(source_game) != RAW_GAME:
            raise AssertionError("MUSIC_OBSERVER_GAME_DLL has drifted")
        cls.dotnet = dotnet()
        cls.cecil = cecil()
        editor_value = os.environ.get("UNITY_EDITOR")
        if not editor_value:
            raise unittest.SkipTest("UNITY_EDITOR is required for optional stage lifecycle host tests")
        editor = Path(editor_value).expanduser().resolve()
        if not editor.is_file():
            raise AssertionError("UNITY_EDITOR was supplied but the pinned Unity host binary is missing")

        cls.temp = tempfile.TemporaryDirectory(prefix="music-observer-stage-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name).resolve()
        cls.work = cls.root / "work"
        cls.project = cls.work / "project"
        cls.project.mkdir(parents=True)
        for rel in (
            "environment/toolchain.json",
            "recipe/assembly-transforms.json",
            "recipe/native-view-camera-transform.json",
            "scripts/lab/original_music_output_observer_build_hook.py",
            "scripts/lab/native_view_camera_transform.py",
            "scripts/lab/native_view_camera_resolver.py",
            "tools/assembly-transforms/MusicOutputObserverCecilTransform.cs",
            "tools/assembly-transforms/MusicOutputObserverCecilTransform.csproj",
        ):
            target = cls.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        for rel in ("Assets/LabLoadingScene/Plugins", "Assets/Plugins"):
            source = cls.source_project / rel
            if source.is_dir():
                shutil.copytree(source, cls.project / rel)
        shutil.copytree(cls.source_project / "Assets/StreamingAssets/Lab", cls.project / "Assets/StreamingAssets/Lab")
        cls.original_audio_receipt = cls.project / AUDIO_RECEIPT

        cls.core_dir = cls.work / "fixture-core"
        core_project = ROOT / "tests/observer-fixtures/OriginalOwnerProbeObserver.Fixture.csproj"
        result = __import__("subprocess").run(
            [str(cls.dotnet), "build", str(core_project), "-o", str(cls.core_dir)],
            cwd=ROOT,
            text=True,
            stdout=__import__("subprocess").PIPE,
            stderr=__import__("subprocess").STDOUT,
        )
        if result.returncode:
            raise AssertionError("fixture observer compile failed:\n" + result.stdout)
        cls.fixture_core = cls.core_dir / "OriginalOwnerProbeObserver.dll"
        core_hash = digest(cls.fixture_core)
        audio = json.loads(cls.original_audio_receipt.read_text(encoding="utf-8"))
        rows = [row for row in audio.get("outputs", []) if row.get("target") == CORE_TARGET]
        if len(rows) != 1:
            raise unittest.SkipTest("audio fixture receipt has no unique observer output row")
        # This receipt is a copied shape fixture, not accepted producer evidence.
        # Only the private temp project row is rebound to the test-compiled observer.
        rows[0]["sha256"] = core_hash
        cls.original_audio_receipt.write_text(json.dumps(audio, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.copyfile(cls.fixture_core, cls.project / CORE_TARGET)

        hook_path = cls.root / "scripts/lab/original_music_output_observer_build_hook.py"
        spec = importlib.util.spec_from_file_location("portable_observer_stage_hook", hook_path)
        cls.hook = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.hook)
        resolver_path = cls.root / "scripts/lab/native_view_camera_resolver.py"
        resolver_spec = importlib.util.spec_from_file_location("portable_observer_resolver", resolver_path)
        cls.resolver_module = importlib.util.module_from_spec(resolver_spec)
        assert resolver_spec.loader is not None
        resolver_spec.loader.exec_module(cls.resolver_module)
        editor_contents = editor.parent.parent
        profile = "post-audio-r10-1ced-game-6f96" if api_hash.startswith("1ced") else "post-audio-point-sound-6f96-api-d540"
        resolver_output = cls.work / "generated/native-view-camera/resolver-sets" / profile
        cls.resolver_module.materialize(
            profile,
            cls.project,
            cls.project / "Assets/LabLoadingScene/Plugins/RoR2.dll",
            editor_contents,
            resolver_output,
            RAW_GAME,
            api_hash,
        )
        cls.references = (resolver_output / "assemblies").resolve()
        cls.old_unity_editor = os.environ.get("UNITY_EDITOR")
        cls.old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(cls.dotnet.parent) + os.pathsep + cls.old_path
        os.environ["UNITY_EDITOR"] = str(editor)

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "old_unity_editor", None) is not None:
            os.environ["UNITY_EDITOR"] = cls.old_unity_editor
        else:
            os.environ.pop("UNITY_EDITOR", None)
        if getattr(cls, "old_path", None) is not None:
            os.environ["PATH"] = cls.old_path

    def test_stage_then_camera_then_observer_restore_order(self) -> None:
        game = self.project / "Assets/LabLoadingScene/Plugins/RoR2.dll"
        result = self.hook.stage(self.project, self.work, self.references, self._profile())
        self.assertEqual(result["receipt"]["output_sha256"], OBSERVED_GAME)
        self.assertEqual(digest(game), OBSERVED_GAME)
        camera_receipt = self.project / "Assets/StreamingAssets/Lab/NativeViewCameraStageReceipt.json"
        camera_receipt.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "camera stage must be restored"):
            self.hook.restore(self.project, self.work)
        self.assertEqual(digest(game), OBSERVED_GAME)
        camera_receipt.unlink()
        restored = self.hook.restore(self.project, self.work)
        self.assertEqual(restored["restored_sha256"], RAW_GAME)
        self.assertEqual(digest(game), RAW_GAME)

    def test_wrong_resolver_api_refuses_before_project_write(self) -> None:
        game = self.project / "Assets/LabLoadingScene/Plugins/RoR2.dll"
        bad_root = self.work / "wrong-api-resolver"
        shutil.copytree(self.references.parent, bad_root)
        bad_assemblies = bad_root / "assemblies"
        api = bad_assemblies / "AK.Wwise.Unity.API.dll"
        data = bytearray(api.read_bytes())
        data[len(data) // 2] ^= 1
        api.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError, "resolver set DLL drift"):
            self.hook.stage(self.project, self.work, bad_assemblies.resolve(), self._profile())
        self.assertEqual(digest(game), RAW_GAME)

    def test_historical_owner_core_refuses_new_observer_transform(self) -> None:
        stale_core = required_file(
            "MUSIC_OBSERVER_STALE_CORE_DLL",
            "7e5fa4afa8e4d7bb9d083f489c289b2e3ad0f28904c330d137f8008705f745d0",
        )
        stale_project = self.work / "historical-owner-fixture"
        shutil.copytree(self.project, stale_project)
        shutil.copyfile(stale_core, stale_project / CORE_TARGET)
        receipt_path = stale_project / AUDIO_RECEIPT
        audio = json.loads(receipt_path.read_text(encoding="utf-8"))
        rows = [row for row in audio.get("outputs", []) if row.get("target") == CORE_TARGET]
        self.assertEqual(len(rows), 1)
        rows[0]["sha256"] = digest(stale_core)
        receipt_path.write_text(json.dumps(audio, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        game = stale_project / "Assets/LabLoadingScene/Plugins/RoR2.dll"
        with self.assertRaisesRegex(RuntimeError, "Sequence contains no matching element"):
            self.hook.stage(stale_project, self.work, self.references, self._profile())
        self.assertEqual(digest(game), RAW_GAME)
        self.assertFalse((stale_project / "Assets/StreamingAssets/Lab/OriginalMusicOutputObserverStageReceipt.json").exists())

    def _profile(self) -> str:
        audio = json.loads(self.original_audio_receipt.read_text(encoding="utf-8"))
        api = audio["lineage"]["composed_api_sha256"]
        return "post-audio-r10-1ced-game-6f96" if api.startswith("1ced") else "post-audio-point-sound-6f96-api-d540"


if __name__ == "__main__":
    unittest.main()
