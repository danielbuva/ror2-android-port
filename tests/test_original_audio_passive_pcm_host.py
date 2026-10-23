from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def find_repo_root() -> Path:
    marker = Path("tools/unity/support/audio/bootstrap/PassivePcmCaptureWindow.cs")
    for parent in Path(__file__).resolve().parents:
        if parent.name == "canonical" and (parent / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").is_file():
            return parent
        if (parent / marker).is_file():
            return parent
    raise RuntimeError("repository root not found from test path")


ROOT = find_repo_root()


def find_host_repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    return ROOT


HOST_REPO = find_host_repository_root()


def source(relative: str) -> Path:
    candidate = ROOT / relative
    if candidate.is_file():
        return candidate
    return HOST_REPO / relative


AUDIO = ROOT / "tools/unity/support/audio/bootstrap"
FIXTURE = source("tests/fixtures/original_audio/PassivePcmCaptureWindowHarness.cs")
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
                    str(source("tools/unity/support/audio/bootstrap/NativeWwiseMonitorLease.cs")),
                    str(source("tools/unity/support/audio/bootstrap/PassivePcmCaptureWindow.cs")),
                    str(source("tools/unity/support/audio/bootstrap/PcmWaveformReadbackV1.cs")),
                    str(source("tools/unity/runtime/session/MusicPcmJoinObserver.cs")),
                    str(source("tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs")),
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
        session = source("tools/unity/runtime/session/PortSession.cs").read_text()
        owner = source("tools/unity/runtime/session/PortSessionOriginalAudioOwner.cs").read_text()
        window = source("tools/unity/support/audio/bootstrap/PassivePcmCaptureWindow.cs").read_text()
        self.assertNotIn('r.phase = "integrated-world-playing"', session)
        self.assertNotIn("playableWorldStarted", session)
        save_body = session.split("    void Save()", 1)[1].split("    private void RetirePointSoundDiagnostic", 1)[0]
        self.assertIn("GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(", save_body)
        self.assertIn("passivePcmGameplayArmBoundaryAttempted, r.integratedWorld, r.phase, r.world.seconds", save_body)
        self.assertNotIn("r.integratedResults", save_body)
        self.assertIn(
            "!float.IsNaN(worldSeconds) && !float.IsInfinity(worldSeconds)",
            source("tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").read_text(),
        )
        self.assertIn("activityPolicy.ObservePlayableWorld(true)", save_body)
        self.assertIn("RequestPassivePcmGameplayArm();", save_body)
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

    def test_deferred_mode_uses_recognized_authority_skill_and_closes_before_recovery(self):
        session = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text()
        boundary = (ROOT / "tools/unity/runtime/world/IntegratedWorldBoundary.cs").read_text()
        observer = (ROOT / "tools/unity/runtime/world/SurvivorSkillObserver.cs").read_text()
        request = (ROOT / "tools/unity/support/audio/generators/generate_accepted_request_pin.py").read_text()
        self.assertIn("PassivePcmCaptureAfterAuthoritySkillRequested", session)
        self.assertIn("onRecognizedAuthoritySkill?.Invoke()", observer)
        self.assertIn("body.networkIdentity.hasAuthority", observer)
        self.assertIn("FindSkillSlot(skill)", observer)
        self.assertIn("new SurvivorSkillObserver(player, skillActivity)", boundary)
        self.assertIn("coordinator.OnRecognizedAuthoritySkillForPassivePcm", boundary)
        self.assertIn("waitForAuthoritySkill", ROOT.joinpath("tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").read_text())
        self.assertIn("ObserveAuthoritySkill(true, validWorld)", session)
        self.assertIn(
            "if (waitForSkill && (!captureRequested || musicOutputRequested))",
            source("tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").read_text(),
        )
        self.assertIn("PassivePcmCaptureAfterAuthoritySkillRequested", request)
        # In recovery paths the skill observer can outlive the current stage;
        # closure must happen before teardown can return early.
        cleanup = boundary.split("public void CleanupIntegratedWorld()", 1)[1]
        close = cleanup.index("coordinator.ClosePassivePcmActivityArmPolicy();")
        self.assertLess(close, cleanup.index("if (coordinator.r.sourceStageLifecycleRecoveryRequired)"))

    def test_gameplay_gate_accepts_actual_world_when_results_profile_is_false(self):
        core = source("tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs")
        fixture = source("tests/fixtures/original_audio/PassivePcmGameplayGateHarness.cs")
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

    def test_activity_policy_fixture_runs_against_candidate_contract(self):
        core = source("tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs")
        fixture = source("tests/fixtures/original_audio/PassivePcmActivityArmPolicyHarness.cs")
        with tempfile.TemporaryDirectory(prefix="original-audio-pcm-arm-policy-") as temp_name:
            executable = Path(temp_name) / "activity-arm-policy.exe"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-target:exe", "-out:" + str(executable), str(core), str(fixture)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True, check=False)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("PASS integrated PCM activity policy", executed.stdout)


if __name__ == "__main__":
    unittest.main()
