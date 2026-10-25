"""Source-stage binding and truthful destination MainOutput qualification."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import baseline


def first():
    return {
        "phase": "integrated-world-playing",
        "stage": {"scene": "lakes"},
        "stageProgress": {"transitions": 0},
        "profile": {"appliedRuns": 0},
        "passivePcmGameplayArmRequested": False,
    }


def captured():
    return {
        "phase": "integrated-world-playing",
        "stage": {"scene": "fixture-next"},
        "stageProgress": {"transitions": 1, "enteredAt": 100},
        "world": {"seconds": 112},
        "profile": {"appliedRuns": 0},
        "debugAcceleration": {"everAssisted": True},
        "passivePcmCaptureInDestinationRequested": True,
        "passivePcmCaptureInDestinationObserved": True,
        "passivePcmCaptureAfterAuthoritySkillRequested": True,
        "passivePcmAuthoritySkillObserved": True,
        "passivePcmGameplayArmRequested": True,
        "passivePcmArmStageScene": "fixture-next",
        "passivePcmArmStageTransitions": 1,
        "passivePcmArmWorldSeconds": 101,
        "originalAudio": {
            "passivePcmState": "captured",
            "passivePcmCaptureSelectorMode": "main",
            "passivePcmNonzeroFiniteSamples": 12,
            "passivePcmNonfiniteSamples": 0,
            "passivePcmFailure": "",
        },
    }


def member(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 0
    for i in range(opening, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return text[start : i + 1]
    raise AssertionError(signature)


class DestinationPcmTests(unittest.TestCase):
    def assess(self, value, initial=None):
        return baseline.assess("stage-exit-10s", initial or first(), value, stage_exit=True, capture_in_destination=True)

    def test_explicit_selection_and_invalid_mode_refuse_before_device(self):
        self.assertNotIn("passivePcmCaptureInDestinationRequested", baseline.selection("fixture"))
        self.assertIs(baseline.selection("fixture", True, True)["passivePcmCaptureInDestinationRequested"], True)
        with self.assertRaises(ValueError):
            baseline.selection("fixture", capture_in_destination=True)
        with self.assertRaises(ValueError):
            baseline.check_baseline(capture_in_destination=True)

    def test_destination_capture_is_bounded_without_accepting_partial_window(self):
        r = captured()
        self.assertEqual(baseline.stage_exit_stop(r, True), "stage-exit-10s")
        r["originalAudio"]["passivePcmState"] = "capturing"
        self.assertIsNone(baseline.stage_exit_stop(r, True))
        self.assertEqual(baseline.stage_exit_stop(r), "stage-exit-10s")
        r["world"]["seconds"] = 130
        self.assertEqual(baseline.stage_exit_stop(r, True), "destination-pcm-deadline")
        r["stageProgress"]["requested"] = "third-stage"
        self.assertEqual(baseline.stage_exit_stop(r, True), "second-stage-exit")

    def test_only_destination_finite_nonzero_capture_passes(self):
        self.assertEqual(self.assess(captured()), [])
        changes = [
            ("passivePcmCaptureInDestinationObserved", False),
            ("passivePcmCaptureInDestinationRequested", False),
            ("passivePcmCaptureAfterAuthoritySkillRequested", False),
            ("passivePcmAuthoritySkillObserved", False),
            ("passivePcmGameplayArmRequested", False),
            ("passivePcmArmStageScene", "lakes"),
            ("passivePcmArmStageTransitions", True),
            ("passivePcmArmWorldSeconds", 99),
            ("passivePcmArmWorldSeconds", float("nan")),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                r = captured()
                r[key] = value
                self.assertTrue(self.assess(r))
        for key, value in [
            ("passivePcmState", "capturing"),
            ("passivePcmCaptureSelectorMode", "specific"),
            ("passivePcmNonzeroFiniteSamples", 0),
            ("passivePcmNonzeroFiniteSamples", True),
            ("passivePcmNonfiniteSamples", 1),
            ("passivePcmFailure", "fixture refusal"),
        ]:
            with self.subTest(key=key, value=value):
                r = captured()
                r["originalAudio"][key] = value
                self.assertTrue(self.assess(r))
        initial = first()
        initial["passivePcmGameplayArmRequested"] = True
        self.assertTrue(self.assess(captured(), initial))

    def test_exact_nan_is_still_a_runtime_failure(self):
        from nova_bridge import current_errors

        line = "10-24 16:00:00.000 123 123 E Unity: Infinity or NaN floating point numbers appear when calculating the transform matrix for a Collider. Scene hierarchy path LightningStake(Clone)"
        self.assertEqual(current_errors(line, "123"), [line])

    def test_runtime_nan_stops_and_cleans_up_before_destination(self):
        line = "10-24 16:00:00.000 123 123 E Unity: Infinity or NaN floating point numbers appear when calculating the transform matrix for a Collider. Scene hierarchy path LightningStake(Clone)"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config/current-build.json").write_text('{"apk_sha256":"fixture"}')
            device = SimpleNamespace(
                settings={"storage_mode": "internal"},
                owned=Mock(return_value={"storage": {"mode": "internal"}, "package_path": "package:/data/app/fixture/base.apk", "apk_sha256": "fixture"}),
                storage=Mock(return_value={"mode": "internal"}),
                read_receipt=Mock(return_value={"persistentDataPath": "/fixture/runtime"}),
                sh=Mock(return_value=""),
                cmd=Mock(side_effect=lambda *args: line if args[0] == "logcat" else ""),
                launch=Mock(return_value={"pid": "123"}),
            )

            def collect(kind, path):
                if kind == "logs":
                    path.mkdir(parents=True, exist_ok=True)
                    (path / "unity.log").write_text("")  # Earliest failure must survive later ring turnover.

            device.collect = collect
            value = first()
            value.update(pid="123", world={"seconds": 1})
            with (
                patch.object(baseline, "WORK", root),
                patch.object(baseline, "Device", return_value=device),
                patch.object(baseline, "attempt_from_installed", return_value="fixture"),
                patch.object(baseline, "runtime_files", return_value=set()),
                patch.object(baseline, "process_pid", return_value="123"),
                patch.object(baseline, "current_report", return_value=value),
                patch.object(baseline, "cleanup", return_value={"process_absent": True, "selector_absent": True, "display_asleep": True}) as cleanup,
            ):
                result = baseline.check_baseline(stage_exit=True, capture_in_destination=True)
            self.assertFalse(result["success"])
            self.assertEqual(result["stop"], "first-runtime-error")
            self.assertEqual(result["destination_pcm_log_errors"], [line])
            cleanup.assert_called_once()

    def test_real_session_methods_with_original_activity_policy(self):
        editor = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
        mono = editor / "bin/mono"
        csc = editor / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("exact editor Mono/Roslyn unavailable")
        source = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text()
        methods = "\n".join(
            member(source, text)
            for text in [
                "GameAudioOriginalPassivePcmActivityArmPolicy GetPassivePcmActivityArmPolicy()",
                "bool PassivePcmDestinationReady()",
                "void RequestPassivePcmGameplayArm()",
                "internal void ClosePassivePcmActivityArmPolicy()",
                "internal void OnRecognizedAuthoritySkillForPassivePcm()",
            ]
        )
        fixture = r"""
using System;
public static class GameAudioOriginalRequestBootstrap {public static bool IsConfigured=true,PassivePcmCaptureMusicOutputRequested;}
public static class PortSessionOriginalAudioOwner {
 public static bool PassivePcmCaptureRequested=true,PassivePcmCaptureAfterAuthoritySkillRequested=true,Accept=true;
 public static bool PassivePcmGameplayArmRequested;
 public static int Arms;public static bool ArmPassivePcmCaptureAtGameplayBoundary(bool request){Arms++;if(Accept)PassivePcmGameplayArmRequested=true;return Accept;}
}
public class World {public float seconds=101;}
public class Stage {public string scene="fixture-next";}
public class Progress {public int transitions=1;public bool transporting,activeSceneVerified=true;public string current="fixture-next";public float enteredAt=100;}
public class Report {
 public bool passivePcmCaptureInDestinationRequested=true,passivePcmCaptureInDestinationObserved;
 public bool passivePcmPlayableWorldObserved,passivePcmAuthoritySkillObserved,integratedWorld=true;
 public string phase="integrated-world-playing",passivePcmArmStageScene;public int passivePcmArmStageTransitions;
 public float passivePcmArmWorldSeconds;public World world=new World();public Stage stage=new Stage();public Progress stageProgress=new Progress();
}
public class Harness {
 Report r=new Report();bool passivePcmGameplayArmBoundaryAttempted;
 GameAudioOriginalPassivePcmActivityArmPolicy passivePcmActivityArmPolicy;
 static int failures;static void RecordPrimarySessionFailure(Report report,Exception error){failures++;}
 METHODS
 static void Assert(bool value,string message){if(!value)throw new Exception(message);}
 static void Blocked(Action<Report> change) {var h=new Harness();change(h.r);int before=PortSessionOriginalAudioOwner.Arms;h.OnRecognizedAuthoritySkillForPassivePcm();Assert(PortSessionOriginalAudioOwner.Arms==before&&!h.r.passivePcmCaptureInDestinationObserved,"invalid transition must not consume capture");}
 public static void Main(){
  Blocked(r=>r.stageProgress.transitions=0);Blocked(r=>r.stageProgress.transitions=2);
  Blocked(r=>r.stageProgress.transporting=true);Blocked(r=>r.stageProgress.activeSceneVerified=false);
  Blocked(r=>r.stage.scene="old-stage");Blocked(r=>r.stage.scene="");Blocked(r=>r.stageProgress.enteredAt=float.NaN);
  Blocked(r=>r.stageProgress.enteredAt=-1);Blocked(r=>r.world.seconds=100);Blocked(r=>r.world.seconds=float.NaN);
  Blocked(r=>r.phase="offline-start-menu");Blocked(r=>r.integratedWorld=false);
  var h=new Harness();h.r.stageProgress.transitions=0;h.r.stageProgress.enteredAt=0;h.OnRecognizedAuthoritySkillForPassivePcm();
  Assert(!h.passivePcmActivityArmPolicy.ArmAttempted,"first-stage callbacks cannot claim one-shot arm");
  h.r.stageProgress.transitions=1;h.r.stageProgress.enteredAt=100;h.OnRecognizedAuthoritySkillForPassivePcm();h.OnRecognizedAuthoritySkillForPassivePcm();
  Assert(PortSessionOriginalAudioOwner.Arms==1&&h.r.passivePcmCaptureInDestinationObserved&&h.r.passivePcmAuthoritySkillObserved,"one accepted destination skill");
  Assert(h.r.passivePcmArmStageScene=="fixture-next"&&h.r.passivePcmArmStageTransitions==1&&h.r.passivePcmArmWorldSeconds==101,"arm-time source witnesses");
  var reused=new Harness();reused.OnRecognizedAuthoritySkillForPassivePcm();Assert(failures==1&&PortSessionOriginalAudioOwner.Arms==1&&!reused.r.passivePcmCaptureInDestinationObserved,"earlier process window must never become new-stage evidence");
  var ordinary=new Harness();ordinary.r.passivePcmCaptureInDestinationRequested=false;ordinary.r.stageProgress.transitions=0;ordinary.OnRecognizedAuthoritySkillForPassivePcm();
  Assert(PortSessionOriginalAudioOwner.Arms==2&&!ordinary.r.passivePcmCaptureInDestinationObserved,"default first-stage path unchanged");
  var closed=new Harness();closed.GetPassivePcmActivityArmPolicy();closed.ClosePassivePcmActivityArmPolicy();closed.OnRecognizedAuthoritySkillForPassivePcm();Assert(PortSessionOriginalAudioOwner.Arms==2,"closed policy cannot arm later");
  GameAudioOriginalRequestBootstrap.PassivePcmCaptureMusicOutputRequested=true;bool refused=false;try{new Harness().GetPassivePcmActivityArmPolicy();}catch(InvalidOperationException){refused=true;}Assert(refused,"specific-output request refused");GameAudioOriginalRequestBootstrap.PassivePcmCaptureMusicOutputRequested=false;
  PortSessionOriginalAudioOwner.Accept=false;PortSessionOriginalAudioOwner.PassivePcmGameplayArmRequested=false;var refusedArm=new Harness();refusedArm.OnRecognizedAuthoritySkillForPassivePcm();Assert(failures==2&&!refusedArm.r.passivePcmCaptureInDestinationObserved,"refused native arm cannot produce destination evidence");
  Console.WriteLine("PASS original destination activity boundary");
 }
}
""".replace("METHODS", methods)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / "Fixture.cs"
            path.write_text(fixture)
            exe = folder / "Fixture.exe"
            built = subprocess.run(
                [
                    str(mono),
                    str(csc),
                    "/nologo",
                    "/out:" + str(exe),
                    str(ROOT / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs"),
                    str(path),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(mono), str(exe)], text=True, capture_output=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS original destination activity boundary", ran.stdout)


if __name__ == "__main__":
    unittest.main()
