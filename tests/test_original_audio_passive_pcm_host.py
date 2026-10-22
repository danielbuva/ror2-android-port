from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def find_repo_root() -> Path:
    marker = Path("tools/unity/support/audio/bootstrap/PassivePcmCaptureWindow.cs")
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    raise RuntimeError("repository root not found from test path")


ROOT = find_repo_root()
AUDIO = ROOT / "tools/unity/support/audio/bootstrap"
FIXTURE = Path(__file__).resolve().parent / "fixtures/original_audio/PassivePcmCaptureWindowHarness.cs"
UNITY_EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
UNITY_MONO = UNITY_EDITOR / "MonoBleedingEdge"
MONO = UNITY_MONO / "bin/mono"
CSC = UNITY_MONO / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class OriginalAudioPassivePcmHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler unavailable")

    def test_capture_window_uses_actual_monitor_lease_and_term_guard_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="original-audio-pcm-") as temp_name:
            executable = Path(temp_name) / "pcm.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-target:exe",
                    "-out:" + str(executable),
                    str(AUDIO / "NativeWwiseMonitorLease.cs"),
                    str(AUDIO / "PassivePcmCaptureWindow.cs"),
                    str(AUDIO / "PcmWaveformReadbackV1.cs"),
                    str(ROOT / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs"),
                    str(FIXTURE),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True, check=False)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("PASS", executed.stdout)

    def test_playable_boundary_arms_and_session_end_reports_without_delaying_gameplay(self):
        session = (Path(__file__).resolve().parents[1] / "tools/unity/runtime/session/PortSession.cs").read_text()
        owner = (Path(__file__).resolve().parents[1] / "tools/unity/runtime/session/PortSessionOriginalAudioOwner.cs").read_text()
        window = (Path(__file__).resolve().parents[1] / "tools/unity/support/audio/bootstrap/PassivePcmCaptureWindow.cs").read_text()
        self.assertNotIn('r.phase = "integrated-world-playing"', session)
        self.assertNotIn("playableWorldStarted", session)
        save_body = session.split("    void Save()", 1)[1].split("    private void RetirePointSoundDiagnostic", 1)[0]
        self.assertIn("GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(", save_body)
        self.assertIn("passivePcmGameplayArmBoundaryAttempted, r.integratedWorld, r.phase, r.world.seconds", save_body)
        self.assertNotIn("r.integratedResults", save_body)
        self.assertIn(
            "!float.IsNaN(worldSeconds) && !float.IsInfinity(worldSeconds)",
            (Path(__file__).resolve().parents[1] / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").read_text(),
        )
        self.assertIn("ArmPassivePcmCaptureAtGameplayBoundary(true)", save_body)
        self.assertIn("r.passivePcmCaptureRequested = PortSessionOriginalAudioOwner.PassivePcmCaptureRequested", save_body)
        self.assertIn("r.passivePcmGameplayArmRequested = PortSessionOriginalAudioOwner.PassivePcmGameplayArmRequested", save_body)
        run = session.split("IEnumerator RunSelectedProbe", 1)[1]
        self.assertIn("PassivePcmGameplayArmRequested", run)
        self.assertIn("FinishPassivePcmCaptureGameplayWindow()", run)
        on_destroy = session.split("    private void OnDestroy()", 1)[1].split("    // MovementBatchProbe", 1)[0]
        self.assertIn("if (!r.pointSoundDiagnosticRequested && !pcmArmed) return", on_destroy)
        self.assertIn("PassivePcmGameplayArmRequested", on_destroy)
        self.assertIn("RecordPrimarySessionFailure(r, new InvalidOperationException(", save_body)
        self.assertIn("Passive PCM capture reported:", save_body)
        self.assertIn("FinishPassivePcmCaptureGameplayWindow()", owner)
        self.assertIn("playable_session_completed", window)
        self.assertNotIn("while (r.passivePcmCaptureRequested", session)

    def test_gameplay_gate_accepts_actual_world_when_results_profile_is_false(self):
        core = Path(__file__).resolve().parents[1] / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs"
        fixture = Path(__file__).resolve().parent / "fixtures/original_audio/PassivePcmGameplayGateHarness.cs"
        with tempfile.TemporaryDirectory(prefix="original-audio-pcm-gate-") as temp_name:
            executable = Path(temp_name) / "gameplay-gate.exe"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-target:exe", "-out:" + str(executable), str(core), str(fixture)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True, check=False)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("false-results report", executed.stdout)


if __name__ == "__main__":
    unittest.main()
