from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "PORTING_STATE.md").is_file())
PATCH = HERE.parent if (HERE.parent / "tools/unity").is_dir() else ROOT
FIXTURES = HERE / "fixtures/point_sound"
UNITY = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = UNITY / "MonoBleedingEdge/bin/mono"
CSC = UNITY / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CECIL = UNITY / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
UNITY_CORE = UNITY / "Managed/UnityEngine/UnityEngine.CoreModule.dll"
CORE = PATCH / "tools/unity/support/audio/core"
COMPOSED = PATCH / "tools/unity/support/audio/managed-producer/tools/composed/ComposedGameCecilTransform.cs"


def run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True, env=env)


class PointSoundDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not all(path.is_file() for path in (MONO, CSC, CECIL, UNITY_CORE)):
            raise unittest.SkipTest("pinned Unity Mono/Roslyn/Cecil/CoreModule unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="point-sound-contract-")
        cls.work = Path(cls.temp.name)
        cls.env = dict(os.environ)
        cls.env["MONO_PATH"] = str(CECIL.parent)
        cls.core_observer = cls.work / "OriginalOwnerProbeObserver.dll"
        cls.core = cls.work / "GameAudioOriginalCore.dll"
        cls.core_default = cls.work / "GameAudioOriginalCore-default.dll"
        cls.transform = cls.work / "ComposedGameCecilTransform.exe"
        cls.fixture = cls.work / "PointSoundObserverFixture.exe"
        cls.mutator = cls.work / "BypassPointSoundMarker.exe"
        cls.default_fixture = cls.work / "PointSoundBuildPinDefaultFixture.exe"
        cls.candidate = cls.work / "RoR2-point-sound-diagnostic.dll"
        cls.mutated = cls.work / "RoR2-point-sound-bypass-mutant.dll"
        cls.compile(cls.core_observer, [CORE / "OriginalOwnerProbeObserver.cs"])
        common = [
            CORE / "GameAudioOriginalReadiness.cs",
            CORE / "GameAudioOriginalOwner.cs",
            CORE / "PointSoundDiagnosticObserver.cs",
        ]
        cls.compile(cls.core, common + [FIXTURES / "PointSoundBuildPin.cs"], [UNITY_CORE, cls.core_observer])
        cls.compile(cls.core_default, common + [FIXTURES / "PointSoundBuildPinDefault.cs"], [UNITY_CORE, cls.core_observer])
        cls.env["MONO_PATH"] = str(cls.work) + os.pathsep + str(CECIL.parent)
        cls.compile(cls.transform, [COMPOSED], [CECIL], target="exe")
        cls.compile(cls.fixture, [FIXTURES / "PointSoundObserverFixture.cs"], [cls.core], target="exe")
        cls.compile(cls.mutator, [FIXTURES / "BypassPointSoundMarker.cs"], [CECIL], target="exe")
        cls.compile(cls.default_fixture, [FIXTURES / "PointSoundBuildPinDefaultFixture.cs"], [cls.core_default], target="exe")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    @classmethod
    def compile(cls, output: Path, sources: list[Path], references: list[Path] | None = None, target: str = "library") -> None:
        command = [str(MONO), str(CSC), "-nologo", "-deterministic+", "-target:" + target, "-out:" + str(output)]
        command.extend("-r:" + str(reference) for reference in (references or []))
        command.extend(str(source) for source in sources)
        result = run(command, cls.env)
        if result.returncode:
            raise AssertionError("C# compile failed: " + result.stdout + result.stderr)

    def test_runtime_core_and_dotted_legacy_stack_teardown_contract(self) -> None:
        result = run([str(MONO), str(self.fixture)], self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("teardown passed", result.stdout)

    def test_transform_has_exact_input_gate_and_mutation_rejection_contract(self) -> None:
        source = COMPOSED.read_text(encoding="utf-8")
        self.assertIn("point-sound diagnostic requires exact composed game 1034 input", source)
        self.assertIn("RequireNoIncomingControlEdge", source)
        self.assertIn("ShortBranchCount(resultRequest) == requestShortBranchCount", source)
        self.assertIn("ShortBranchCount(resultEmit) == emitShortBranchCount", source)
        self.assertIn("original PostEvent callsites retained", source)

    def test_default_off_pin_and_save_scoped_selection(self) -> None:
        result = run([str(MONO), str(self.default_fixture)], self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        session = (PATCH / "tools/unity/runtime/session/PortSession.cs").read_text(encoding="utf-8")
        self.assertIn("public bool pointSoundDiagnosticRequested;", session)
        self.assertIn("PortSessionOriginalAudioOwner.ConfigurePointSoundDiagnostic(true);", session)
        self.assertIn("GameAudioOriginalOwner.PointSoundDiagnosticBuildRefusal(true)", session)
        self.assertIn("r.pointSoundDiagnostic = PortSessionOriginalAudioOwner.CapturePointSoundDiagnosticSnapshot();", session)
        self.assertIn("r.originalAudio = PortSessionOriginalAudioOwner.CaptureSnapshot();", session)
        self.assertIn("private void OnDestroy()", session)
        self.assertIn("sourceStageLifecycleRecoveryRequired", session)
        self.assertIn("PortSessionOriginalAudioOwner.DisablePointSoundDiagnostic();", session)

    def test_requested_producer_and_exact_predecessor_are_pinned(self) -> None:
        producer = (PATCH / "tools/unity/support/audio/managed-producer/produce.py").read_text(encoding="utf-8")
        adapter = (PATCH / "scripts/lab/original_game_audio_produce.py").read_text(encoding="utf-8")
        self.assertIn('"point_sound_composed_game": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc"', producer)
        self.assertIn('"point_sound_composed_game": LINEAGE["composed_game_sha256"]', adapter)
        self.assertIn('Path(key).name == "game-original-owner-point-sound-composed.dll"', adapter)
        self.assertIn("pair == (current_api, PREVIOUS_COMPOSED_GAME_SHA256)", adapter)
        self.assertIn("pair == (PREVIOUS_COMPOSED_API_SHA256, PREVIOUS_COMPOSED_GAME_SHA256)", adapter)
        self.assertIn("pair == (LEGACY_RESTORE_API_SHA256, PREVIOUS_COMPOSED_GAME_SHA256)", adapter)


if __name__ == "__main__":
    unittest.main()
