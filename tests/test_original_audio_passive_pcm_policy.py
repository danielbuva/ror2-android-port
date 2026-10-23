from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "canonical" and (parent / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").is_file():
            return parent
        if (parent / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").is_file():
            return parent
    raise RuntimeError("repository root not found")


REPO = find_repo_root()
HOST_REPO = next((parent for parent in Path(__file__).resolve().parents if (parent / "AGENTS.md").is_file()), REPO)


def source(relative: str) -> Path:
    candidate = REPO / relative
    return candidate if candidate.is_file() else HOST_REPO / relative


UNITY_MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
MONO = UNITY_MONO / "bin/mono"
CSC = UNITY_MONO / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class PassivePcmActivityArmPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn is unavailable")

    def test_activity_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-activity-arm-") as temp:
            exe = Path(temp) / "policy.exe"
            built = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-target:exe",
                    "-out:" + str(exe),
                    str(REPO / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs"),
                    str(source("tests/fixtures/original_audio/PassivePcmActivityArmPolicyHarness.cs")),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(MONO), str(exe)], capture_output=True, text=True, check=False)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS integrated PCM activity policy", ran.stdout)

    def test_integration_hook_is_existing_authority_skill_callback_and_main_output_arm(self) -> None:
        observer = (REPO / "tools/unity/runtime/world/SurvivorSkillObserver.cs").read_text()
        boundary = (REPO / "tools/unity/runtime/world/IntegratedWorldBoundary.cs").read_text()
        audio_owner = (REPO / "tools/unity/runtime/session/PortSessionOriginalAudioOwner.cs").read_text()
        self.assertIn("body.onSkillActivatedAuthority += AuthorityActivated", observer)
        self.assertIn("body.onSkillActivatedServer += ServerActivated", observer)
        self.assertIn("int index = locator ? (int)locator.FindSkillSlot(skill) : -1", observer)
        self.assertIn("var component = FindComponent(skill)", observer)
        self.assertIn("survivorSkills = new SurvivorSkillObserver(player,", boundary)
        self.assertIn("coordinator.OnRecognizedAuthoritySkillForPassivePcm", boundary)
        self.assertIn("GameAudioOriginalPassivePcmCaptureSelection.MainOutput()", audio_owner)
        self.assertIn("return GameAudioOriginalOwner.ArmPassiveCaptureAtGameplayBoundary(", audio_owner)
        # Existing PCM arm is managed policy state; the callback path does not
        # call an AK API or create a second capture/native callback owner.
        capture_owner = source("tools/unity/support/audio/bootstrap/PassivePcmCaptureWindow.cs").read_text()
        arm = capture_owner.split("internal bool RequestGameplayArm(GameAudioOriginalPassivePcmCaptureSelection selection)", 1)[1]
        arm = arm.split("// Called from the persistent PortSession owner's Update", 1)[0]
        self.assertNotIn("AkSoundEngine", arm)
        # Cleanup has recovery branches that intentionally retain the observer.
        # The policy must close before any such return so retained callbacks
        # cannot arm after teardown starts.
        cleanup = boundary.split("public void CleanupIntegratedWorld()", 1)[1]
        self.assertLess(
            cleanup.index("coordinator.ClosePassivePcmActivityArmPolicy();"),
            cleanup.index("CancelPendingOriginalAudioCameraContextCreationForCleanup();"),
        )
        self.assertLess(
            cleanup.index("coordinator.ClosePassivePcmActivityArmPolicy();"),
            cleanup.index("if (coordinator.r.sourceStageLifecycleRecoveryRequired)"),
        )


if __name__ == "__main__":
    unittest.main()
