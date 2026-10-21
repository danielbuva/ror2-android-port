from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from _music_observer_test_support import cecil, digest, required_directory, required_file


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / ".git").exists():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_root()
OBSERVER_HASH = "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef"
CAMERA_HASH = "a2054dcfc5d14d2fdfba0fd0e61851e4a153b842be6bb6f1c0e1df8ef634762e"
API_HASHES = {
    "d540": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
    "1ced": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
}


def run(command: list[str], *, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if ok and result.returncode:
        raise AssertionError(f"exit {result.returncode}: {' '.join(command)}\n{result.stdout}")
    return result


class CameraAfterMusicObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.input = required_file("MUSIC_OBSERVER_OUTPUT_DLL", OBSERVER_HASH)
        cls.resolvers = {profile: required_directory(f"MUSIC_OBSERVER_RESOLVER_{profile.upper()}") for profile in API_HASHES}
        for profile, resolver in cls.resolvers.items():
            api = resolver / "AK.Wwise.Unity.API.dll"
            if not api.is_file() or digest(api) != API_HASHES[profile]:
                raise AssertionError(f"profile {profile} resolver lacks its pinned audio API")
        editor_value = os.environ.get("UNITY_EDITOR")
        if not editor_value:
            raise unittest.SkipTest("UNITY_EDITOR is required for optional pinned host composition tests")
        editor = Path(editor_value).expanduser().resolve()
        contents = editor.parent.parent
        cls.mono = contents / "MonoBleedingEdge/bin/mono"
        cls.mcs = contents / "MonoBleedingEdge/bin/mcs"
        cls.cecil = cecil()
        for tool in (cls.mono, cls.mcs):
            if not tool.is_file():
                raise AssertionError(f"pinned Unity host tool is missing: {tool}")
        cls.work_context = tempfile.TemporaryDirectory(prefix="camera-observer-composition-")
        cls.addClassCleanup(cls.work_context.cleanup)
        cls.work = Path(cls.work_context.name)
        cls.transformer = cls.work / "NativeViewCameraTransform.exe"
        cls.verifier = cls.work / "VerifyNativeViewCameraTransform.exe"
        cls.helper = cls.work / "NativeViewCameraMarker.Helper.dll"
        helper_source = ROOT / "tools/unity/runtime/input/AndroidNativeSourceViewOnlyRigMarker.cs"
        compile_args = [str(cls.mcs), "-sdk:4.7.2", "-target:library", "-out:" + str(cls.helper), "-r:" + str(cls.input)]
        for relative in (
            "Managed/UnityEngine/UnityEngine.CoreModule.dll",
            "MonoBleedingEdge/lib/mono/4.7.2-api/Facades/netstandard.dll",
        ):
            compile_args.extend(("-r:" + str(contents / relative),))
        run(compile_args + [str(helper_source)])
        for target, source in (
            (cls.transformer, ROOT / "tools/assembly-transforms/NativeViewCameraCecilTransform.cs"),
            (cls.verifier, ROOT / "tools/assembly-transforms/VerifyNativeViewCameraTransform.cs"),
        ):
            run([str(cls.mcs), "-sdk:4.7.2", "-out:" + str(target), "-r:" + str(cls.cecil), str(source)])

    def test_exact_observer_output_is_camera_input_and_verifies(self) -> None:
        self.assertEqual(digest(self.input), OBSERVER_HASH)
        for profile, resolver in self.resolvers.items():
            with self.subTest(profile=profile):
                output = self.work / f"verified-camera-output-{profile}.dll"
                run([str(self.mono), str(self.transformer), str(self.input), str(output), str(self.helper), "-", str(resolver)])
                self.assertEqual(digest(output), CAMERA_HASH)
                verification = run([str(self.mono), str(self.verifier), str(self.input), str(output), str(self.helper)])
                self.assertIn("unrelated_bodies_unchanged=true", verification.stdout)

    def test_wrong_observer_preimage_is_rejected_before_output(self) -> None:
        wrong = self.work / "wrong-preimage.dll"
        raw = bytearray(self.input.read_bytes())
        raw[len(raw) // 2] ^= 1
        wrong.write_bytes(raw)
        output = self.work / "must-not-exist.dll"
        result = run([str(self.mono), str(self.transformer), str(wrong), str(output), str(self.helper), "-", str(self.resolvers["1ced"])], ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact pinned preimage", result.stdout)
        self.assertFalse(output.exists())

    def test_api_profile_mutant_is_rejected(self) -> None:
        mutant_dir = self.work / "wrong-api-resolver"
        shutil.copytree(self.resolvers["1ced"], mutant_dir)
        api = mutant_dir / "AK.Wwise.Unity.API.dll"
        raw = bytearray(api.read_bytes())
        raw[len(raw) // 2] ^= 1
        api.write_bytes(raw)
        output = self.work / "wrong-api-output.dll"
        result = run([str(self.mono), str(self.transformer), str(self.input), str(output), str(self.helper), "-", str(mutant_dir)], ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("resolver source set does not match exact camera game/API profile", result.stdout)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
