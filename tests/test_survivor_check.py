import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import survivor_check as check


def report(**updates):
    value = {
        "phase": "integrated-world-playing",
        "selectedSurvivor": "Huntress",
        "developerSurvivorOverride": False,
        "world": {"seconds": 60},
        "stage": {"scene": "lakes"},
        "stageProgress": {"transitions": 0},
        "debugAcceleration": {"everAssisted": True},
        "profile": {"appliedRuns": 13},
        "survivorSkills": {
            "attached": True,
            "cleaned": False,
            "slots": [
                {
                    "slot": name,
                    "authorityActivations": 1,
                    "serverActivations": 1,
                    "suppressesActivationEvents": False,
                }
                for name in check.SLOTS
            ],
        },
    }
    value.update(updates)
    return value


class SurvivorSelectionTests(unittest.TestCase):
    def test_explicit_base_roster_and_native_names(self):
        self.assertEqual(len(check.targets("all")), 11)
        self.assertEqual(check.targets("Engi,Loader"), ("Engi", "Loader"))
        for value in ("lab", "Engineer", "Huntress,Huntress", "", "Railgunner", "Huntress,"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check.targets(value)

    def test_only_locked_base_survivors_use_diagnostic_override(self):
        for name in check.BASE_SURVIVORS:
            value = check.survivor_selection("owned-attempt", name)
            self.assertEqual(value["selectedSurvivor"], name)
            self.assertEqual(value["attempt"], "owned-attempt")
            self.assertEqual(value["developerSurvivorOverride"], name not in check.FREE_SURVIVORS)
            self.assertFalse(value["goldshoresRoute"])
            self.assertEqual([key for key in check.DEBUG_OPTIONS if value["debugOptions"][key]], ["invincibility"])
            self.assertIn("no permanent progression", value["debugOptions"]["purpose"])

    def test_lock_prevents_even_device_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "coordination").mkdir()
            (root / "coordination/claude-r9.lock").write_text("owned by parallel session")
            with patch.object(check, "WORK", root), patch.object(check.Device, "__init__") as discover:
                with self.assertRaisesRegex(RuntimeError, "coordination lock"):
                    check.SurvivorCheckDevice()
                discover.assert_not_called()

    def test_each_subsequent_device_command_rechecks_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = object.__new__(check.SurvivorCheckDevice)
            with patch.object(check, "WORK", root), patch.object(check.Device, "cmd", return_value="sent") as send:
                self.assertEqual(device.cmd("shell", "true"), "sent")
                (root / "coordination").mkdir()
                (root / "coordination/claude-r9.lock").touch()
                with self.assertRaisesRegex(RuntimeError, "coordination lock"):
                    device.cmd("shell", "true")
                self.assertEqual(send.call_count, 1)


class SurvivorAssessmentTests(unittest.TestCase):
    def test_passing_activation_evidence(self):
        self.assertEqual(check.assess("Huntress", "four-slots-activated", report(), report(), []), [])

    def test_both_authority_and_server_callbacks_are_required_per_slot(self):
        for index in range(4):
            for key in ("authorityActivations", "serverActivations"):
                for count in (0, -1, None, True, "1"):
                    with self.subTest(slot=index, key=key, count=count):
                        value = report()
                        value["survivorSkills"]["slots"][index][key] = count
                        self.assertEqual(check.missing_activations(value), [check.SLOTS[index]])
                        self.assertTrue(check.assess("Huntress", "four-slots-activated", report(), value, []))

    def test_missing_duplicate_or_detached_slots_never_pass(self):
        observations = [None, {}, {"attached": True, "slots": []}, report()["survivorSkills"]]
        observations[-1]["slots"][3]["slot"] = "primary"
        observations += [dict(report()["survivorSkills"], attached=False), dict(report()["survivorSkills"], cleaned=True)]
        for observation in observations:
            with self.subTest(observation=observation):
                self.assertEqual(check.missing_activations(report(survivorSkills=observation)), list(check.SLOTS))

    def test_waits_for_broad_world_play_and_reports_unobserved_skills(self):
        self.assertIsNone(check.stop_reason(report(world={"seconds": 59.9})))
        self.assertEqual(check.stop_reason(report()), "four-slots-activated")
        self.assertEqual(check.stop_reason(report(world={"seconds": 180}, survivorSkills=None)), "unobserved-skills")
        for value in (None, -1, True, "60", float("nan"), float("inf")):
            self.assertIsNone(check.stop_reason(report(world={"seconds": value})))

    def test_suppressed_callbacks_are_classified_with_callback_context_and_never_pass(self):
        value = report()
        slot = value["survivorSkills"]["slots"][1]
        slot["authorityActivations"] = 0
        slot["serverActivations"] = 0
        slot["suppressesActivationEvents"] = True
        context = [{"slot": "secondary", "callbacks": ["authorityActivations", "serverActivations"]}]
        self.assertEqual(check.suppressed_missing_callbacks(value), context)
        self.assertEqual(check.stop_reason(value), "suppressed-activation-events")
        failures = check.assess("Huntress", "suppressed-activation-events", report(), value, [])
        self.assertTrue(any("suppressed activation callbacks: secondary(authorityActivations, serverActivations)" in item for item in failures))
        self.assertTrue(failures)

    def test_only_the_missing_suppressed_callback_is_reported(self):
        value = report()
        slot = value["survivorSkills"]["slots"][2]
        slot["authorityActivations"] = 0
        slot["suppressesActivationEvents"] = True
        self.assertEqual(
            check.suppressed_missing_callbacks(value),
            [{"slot": "utility", "callbacks": ["authorityActivations"]}],
        )
        self.assertEqual(check.stop_reason(value), "suppressed-activation-events")

    def test_unsuppressed_missing_callback_remains_unobserved(self):
        value = report()
        value["survivorSkills"]["slots"][0]["authorityActivations"] = 0
        self.assertEqual(check.suppressed_missing_callbacks(value), [])
        self.assertIsNone(check.stop_reason(value))
        self.assertEqual(check.stop_reason(report(world={"seconds": 180}, survivorSkills=value["survivorSkills"])), "unobserved-skills")

    def test_errors_result_and_transport_take_precedence_over_activations(self):
        for updates, expected in (
            ({"error": "runtime error"}, "first-failure"),
            ({"firstFailure": "runtime error"}, "first-failure"),
            ({"phase": "commando-defeated"}, "ordinary-result"),
            ({"stage": {"scene": "goolake"}}, "left-first-stage"),
            ({"stageProgress": {"transitions": 1}}, "left-first-stage"),
            ({"stageProgress": {"transporting": True}}, "left-first-stage"),
        ):
            with self.subTest(updates=updates):
                self.assertEqual(check.stop_reason(report(**updates)), expected)

    def test_profile_assistance_identity_and_process_errors_are_all_acceptance_gates(self):
        for updates, errors, reason in (
            ({"selectedSurvivor": "Commando"}, [], "survivor selection"),
            ({"developerSurvivorOverride": True}, [], "survivor selection"),
            ({"profile": {"appliedRuns": 14}}, [], "profile run count"),
            ({"profile": {}}, [], "profile run count"),
            ({"debugAcceleration": {}}, [], "not marked assisted"),
            ({}, ["current process error"], "current-process"),
        ):
            with self.subTest(updates=updates, errors=errors):
                failures = check.assess("Huntress", "four-slots-activated", report(), report(**updates), errors)
                self.assertTrue(any(reason in failure for failure in failures), failures)
        self.assertTrue(check.assess("Huntress", "process-exited", None, None, []))
        untouched = report()
        self.assertEqual(check.assess("Huntress", "four-slots-activated", None, copy.deepcopy(untouched), []), ["profile run count changed or missing"])


class SurvivorRunnerTests(unittest.TestCase):
    def run_case(self, *, stale=False, errors=False, capture_error=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        reports = [
            report(pid="old", attempt="fixture", id=check.SPINE_ID),
            report(pid="42", attempt="wrong-attempt", id=check.SPINE_ID),
            report(pid="42", attempt="fixture", id="other-session"),
            report(pid="42", attempt="fixture", id=check.SPINE_ID),
        ]
        replies = iter(reports if stale else reports[-1:])
        device = Mock()

        def shell(*args, **kwargs):
            if args[0] == "pidof":
                return "42"
            if args[0] == "cat":
                return json.dumps(next(replies))
            return ""

        device.sh.side_effect = shell
        device.launch.return_value = {"pid": "42"}
        device.cmd.return_value = "10-19 01:02:03.004 42 43 E Unity : failure" if errors else ""
        if capture_error:
            device.collect.side_effect = RuntimeError("capture transfer failed")
        with patch.object(check, "WORK", root), patch.object(check.time, "sleep"):
            try:
                result = check.check_one(device, "Huntress", "fixture", "/owned/runtime", root / "case", {"apk_sha256": "a" * 64})
            except RuntimeError:
                if not capture_error:
                    raise
                result = None
        return result, device, root

    def test_current_pid_attempt_and_session_are_required_and_stop_precedes_collection(self):
        result, device, root = self.run_case(stale=True)
        self.assertTrue(result["success"], result)
        calls = device.mock_calls
        stop = calls.index(unittest.mock.call.sh("am", "force-stop", check.PACKAGE, check=False))
        logs = next(i for i, call in enumerate(calls) if call[0] == "cmd" and call.args[0] == "logcat")
        self.assertLess(stop, logs)
        self.assertEqual(sum(call[0] == "collect" and call.args[0] == "screenshot" for call in calls), 1)
        self.assertTrue((root / "case/final-report.json").exists())
        device.display.assert_called_with(False)

    def test_current_process_errors_fail_despite_four_activations(self):
        result, device, root = self.run_case(errors=True)
        self.assertFalse(result["success"])
        self.assertIn("unexpected current-process Unity/Android errors", result["failures"])

    def test_capture_failure_still_removes_selection_stops_app_and_sleeps_display(self):
        result, device, root = self.run_case(capture_error=True)
        self.assertIsNone(result)
        device.sh.assert_any_call("rm", "-f", "/owned/runtime/movement-batch-selection.json", check=False)
        device.sh.assert_any_call("am", "force-stop", check.PACKAGE, check=False)
        device.display.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
