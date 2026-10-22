from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


REPO = find_repo_root()
SOURCE = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").is_file()),
    REPO,
)
TESTS = next(
    (parent / "tests" for parent in Path(__file__).resolve().parents if (parent / "tests/BootstrapPreservationDependencyFixture.cs").is_file()),
    REPO / "tests",
)
UNITY = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = UNITY / "MonoBleedingEdge/bin/mono"
CSC = UNITY / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class OriginalMusicTargetCaptureCompileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned host Mono/Roslyn is unavailable")

    def compile_and_run_bootstrap_preservation_fixture(self, temp: Path) -> None:
        core = SOURCE / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs"
        owner = SOURCE / "tools/unity/support/audio/bootstrap/OriginalGameAudioPassivePcmOwner.cs"
        fixture = TESTS / "BootstrapPreservationDependencyFixture.cs"
        harness = TESTS / "PreservedBootstrapReflectionHarness.cs"
        executable = temp / "bootstrap-preservation.exe"
        compiled = subprocess.run(
            [str(MONO), str(CSC), "-nologo", "-target:exe", f"-out:{executable}", str(core), str(owner), str(fixture), str(harness)],
            cwd=temp,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        ran = subprocess.run([str(MONO), str(executable), str(executable)], cwd=temp, capture_output=True, text=True, check=False)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertIn("PASS: exact reflection-bound bootstrap members", ran.stdout)

    def test_bootstrap_preservation_compiles_against_shared_selection_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="music-target-bootstrap-") as name:
            self.compile_and_run_bootstrap_preservation_fixture(Path(name))

    def test_full_audio_and_music_session_sources_compile_against_shared_contract(self) -> None:
        core = SOURCE / "tools/unity/support/audio/core"
        session = SOURCE / "tools/unity/runtime/session"
        fixture = TESTS / "fixtures/target_capture_session_compile_stubs.cs"
        sources = [
            core / "GameAudioOriginalPassivePcmContract.cs",
            core / "GameAudioOriginalReadiness.cs",
            core / "GameAudioOriginalOwner.cs",
            core / "PointSoundDiagnosticObserver.cs",
            core / "OriginalOwnerProbeObserver.cs",
            SOURCE / "tools/unity/support/audio/bootstrap/GameAudioOriginalPreparation.cs",
            session / "OriginalMusicControllerContract.cs",
            session / "PortSessionOriginalMusicControllerOwner.cs",
            session / "MusicPcmJoinObserver.cs",
            session / "AkMusicPcmJoinQueryAdapter.cs",
            session / "PortSessionOriginalAudioOwner.cs",
            REPO / "tests/fixtures/point_sound/PointSoundBuildPin.cs",
            fixture,
        ]
        with tempfile.TemporaryDirectory(prefix="music-target-session-") as name:
            output = Path(name) / "session-contract.dll"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:latest", "-target:library", f"-out:{output}", *(str(source) for source in sources)],
                cwd=name,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            self.assertTrue(output.is_file())

    def test_bootstrap_and_callback_owner_compile_with_real_selector_contract(self) -> None:
        core = SOURCE / "tools/unity/support/audio/core"
        bootstrap = SOURCE / "tools/unity/support/audio/bootstrap"
        sources = [
            core / "GameAudioOriginalPassivePcmContract.cs",
            core / "GameAudioOriginalReadiness.cs",
            core / "GameAudioOriginalOwner.cs",
            core / "PointSoundDiagnosticObserver.cs",
            core / "OriginalOwnerProbeObserver.cs",
            bootstrap / "GameAudioOriginalPreparation.cs",
            bootstrap / "NativeWwiseMonitorLease.cs",
            bootstrap / "PassivePcmCaptureWindow.cs",
            bootstrap / "PcmWaveformReadbackV1.cs",
            bootstrap / "GameAudioOriginalAndroidNativeBootstrap.cs",
            bootstrap / "OriginalGameAudioPassivePcmOwner.cs",
            REPO / "tests/fixtures/point_sound/PointSoundBuildPin.cs",
            TESTS / "fixtures/target_capture_session_compile_stubs.cs",
        ]
        with tempfile.TemporaryDirectory(prefix="music-target-bootstrap-owner-") as name:
            output = Path(name) / "bootstrap-contract.dll"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:latest", "-target:library", f"-out:{output}", *(str(source) for source in sources)],
                cwd=name,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
