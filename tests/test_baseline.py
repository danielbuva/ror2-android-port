import contextlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import baseline


def report(**overrides):
    value = {
        "error": "",
        "firstFailure": "",
        "phase": "integrated-world-playing",
        "world": {"seconds": 35.2},
        "stage": {"scene": "lakes"},
        "stageProgress": {"transitions": 0, "enteredAt": 0},
        "debugAcceleration": {"everAssisted": True},
        "profile": {"appliedRuns": 13},
    }
    value.update(overrides)
    return value


def next_stage_report(**overrides):
    return report(
        **dict(
            {
                "world": {"seconds": 210},
                "stage": {"scene": "fixture-next-stage"},
                "stageProgress": {"transitions": 1, "enteredAt": 200},
            },
            **overrides,
        )
    )


class BaselineAssessmentTests(unittest.TestCase):
    def test_passing_run(self):
        self.assertEqual(baseline.assess("world-35s", report(), report()), [])

    def test_each_criterion_fails_alone(self):
        cases = {
            "stopped: first-failure": ("first-failure", report(), report()),
            "report error": ("world-35s", report(), report(firstFailure="MissingMethodException")),
            "world play under": ("world-35s", report(), report(world={"seconds": 20})),
            "not on Lakes": ("world-35s", report(), report(stage={"scene": "foggyswamp"})),
            "run not marked assisted": ("world-35s", report(), report(debugAcceleration={})),
            "profile run count": ("world-35s", report(), report(profile={"appliedRuns": 14})),
        }
        for expected, args in cases.items():
            with self.subTest(expected=expected):
                failures = baseline.assess(*args)
                self.assertEqual(len(failures), 1, failures)
                self.assertTrue(failures[0].startswith(expected), failures)

    def test_missing_report_fails(self):
        self.assertIn("no final report", baseline.assess("process-exited", None, None))

    def test_selection_is_assisted_ordinary_commando(self):
        value = baseline.selection("attempt-x")
        self.assertEqual((value["attempt"], value["selectedSurvivor"], value["developerSurvivorOverride"]), ("attempt-x", "Commando", False))
        enabled = [key for key in baseline.DEBUG_OPTIONS if value["debugOptions"][key]]
        self.assertEqual(enabled, ["invincibility"])
        self.assertFalse(value["goldshoresRoute"])


class BaselinePlacementTests(unittest.TestCase):
    def test_both_modes_accept_selected_internal_or_adopted_placement_before_run(self):
        class StopBeforeRun(Exception):
            pass

        for stage_exit in (False, True):
            for mode, path, uuid in (
                ("internal", "package:/data/app/fixture/base.apk", None),
                ("adopted", "package:/mnt/expand/live-volume/app/base.apk", "live-volume"),
            ):
                with self.subTest(mode=mode, stage_exit=stage_exit):
                    d = SimpleNamespace(
                        settings={"storage_mode": mode},
                        owned=Mock(return_value={"storage": {"mode": mode}, "package_path": path}),
                        storage=Mock(return_value={"mode": mode, "uuid": uuid}),
                    )
                    with patch.object(baseline, "Device", return_value=d), patch.object(baseline, "attempt_from_installed", side_effect=StopBeforeRun):
                        with self.assertRaises(StopBeforeRun):
                            baseline.check_baseline(stage_exit=stage_exit)
                    d.owned.assert_called_once_with()
                    d.storage.assert_called_once_with()

    def test_policy_or_live_volume_drift_refuses_before_runtime_writes(self):
        for installed_mode, path in (("internal", "package:/data/app/fixture/base.apk"), ("adopted", "package:/mnt/expand/previous-volume/app/base.apk")):
            d = SimpleNamespace(
                settings={"storage_mode": "adopted"},
                owned=lambda: {"storage": {"mode": installed_mode}, "package_path": path},
                storage=lambda: {"mode": "adopted", "uuid": "current-volume"},
            )
            with self.subTest(installed_mode=installed_mode), patch.object(baseline, "Device", return_value=d), patch.object(baseline, "write") as write:
                with self.assertRaisesRegex(RuntimeError, "differs from selected"):
                    baseline.check_baseline()
                write.assert_not_called()


class StageExitAssessmentTests(unittest.TestCase):
    def assess(self, final, first=None, stop="stage-exit-10s"):
        return baseline.assess(stop, first or report(), final, stage_exit=True)

    def test_passes_at_exactly_ten_next_stage_seconds(self):
        self.assertEqual(self.assess(next_stage_report()), [])

    def test_each_criterion_fails_alone(self):
        cases = {
            "report error": next_stage_report(error="fixture error"),
            "report error: first": next_stage_report(firstFailure="first fixture failure"),
            "stage transition count": next_stage_report(stageProgress={"transitions": 0, "enteredAt": 200}),
            "not on a non-first-stage": next_stage_report(stage={"scene": "lakes"}),
            "next stage is not in live": next_stage_report(phase="complete"),
            "next-stage world play under": next_stage_report(world={"seconds": 209.9}),
            "run not marked assisted": next_stage_report(debugAcceleration={"everAssisted": False}),
            "profile run count": next_stage_report(profile={"appliedRuns": 14}),
            "second stage exit requested": next_stage_report(stageProgress={"transitions": 1, "enteredAt": 200, "requested": "fixture-third-stage"}),
        }
        for expected, final in cases.items():
            with self.subTest(expected=expected):
                failures = self.assess(final)
                self.assertEqual(len(failures), 1, failures)
                self.assertTrue(failures[0].startswith(expected), failures)

    def test_all_unsuccessful_stops_fail_even_with_a_good_final_report(self):
        for stop in ("deadline", "process-exited", "first-failure", "ordinary-result", "unexpected-first-stage", "second-stage-exit", "world-35s"):
            with self.subTest(stop=stop):
                self.assertEqual(self.assess(next_stage_report(), stop=stop), ["stopped: " + stop])

    def test_missing_or_extra_transitions_fail(self):
        for transitions in (None, 0, 2, 4, True, "1"):
            with self.subTest(transitions=transitions):
                final = next_stage_report(stageProgress={"transitions": transitions, "enteredAt": 200})
                self.assertIn("stage transition count is not 1", self.assess(final))

    def test_missing_or_first_stage_scene_fails(self):
        for scene in (None, "", "lakes"):
            with self.subTest(scene=scene):
                self.assertIn("not on a non-first-stage scene", self.assess(next_stage_report(stage={"scene": scene})))

    def test_missing_invalid_or_total_run_timing_cannot_pass(self):
        for progress, world in (
            ({"transitions": 1}, {"seconds": 500}),
            ({"transitions": 1, "enteredAt": 200}, {}),
            ({"transitions": 1, "enteredAt": -1}, {"seconds": 210}),
            ({"transitions": 1, "enteredAt": 220}, {"seconds": 210}),
            ({"transitions": 1, "enteredAt": 200}, {"seconds": float("nan")}),
            ({"transitions": 1, "enteredAt": 200}, {"seconds": float("inf")}),
            ({"transitions": 1, "enteredAt": "200"}, {"seconds": 210}),
            ({"transitions": 1, "enteredAt": 200}, {"seconds": 209.9}),
        ):
            with self.subTest(progress=progress, world=world):
                final = next_stage_report(stageProgress=progress, world=world)
                self.assertTrue(any(failure.startswith("next-stage world play under") for failure in self.assess(final)))

    def test_first_live_stage_and_both_profile_counts_are_required(self):
        for first in (None, report(phase="offline-start-menu"), report(stage={"scene": "fixture-next-stage"}), report(stageProgress={"transitions": 1})):
            with self.subTest(first=first):
                self.assertIn("no first-stage live report", baseline.assess("stage-exit-10s", first, next_stage_report(), stage_exit=True))
        for first, final in ((report(profile={}), next_stage_report()), (report(), next_stage_report(profile={}))):
            with self.subTest(first=first, final=final):
                self.assertIn("profile run count changed or missing", self.assess(final, first=first))

    def test_missing_final_report_fails(self):
        self.assertIn("no final report", self.assess(None))

    def test_transporting_is_not_live_world_play(self):
        final = next_stage_report(stageProgress={"transitions": 1, "enteredAt": 200, "transporting": True})
        self.assertIn("next stage is not in live world play", self.assess(final))


class StageExitControlTests(unittest.TestCase):
    def test_selection_adds_only_damage_and_charge_assists(self):
        ordinary = baseline.selection("fixture-attempt")
        value = baseline.selection("fixture-attempt", stage_exit=True)
        enabled = [key for key in baseline.DEBUG_OPTIONS if value["debugOptions"][key]]
        self.assertEqual(enabled, ["invincibility", "highDamage", "fastCharge"])
        self.assertEqual(
            {key: item for key, item in value.items() if key != "debugOptions"},
            {key: item for key, item in ordinary.items() if key != "debugOptions"},
        )
        self.assertEqual(value["id"], baseline.SPINE_ID)
        self.assertFalse(value["developerSurvivorOverride"])
        self.assertFalse(value["goldshoresRoute"])
        self.assertIn("no permanent progression", value["debugOptions"]["purpose"])
        self.assertEqual(baseline.selection("fixture-attempt"), ordinary)

    def test_keeps_playing_first_stage_and_waits_for_ten_next_stage_seconds(self):
        for value in (
            report(),
            report(world={"seconds": 300}),
            next_stage_report(world={"seconds": 209.9}),
            report(phase="integrated-stage-transition", stageProgress={"transitions": 0, "transporting": True}),
        ):
            with self.subTest(value=value):
                self.assertIsNone(baseline.stage_exit_stop(value))
        self.assertEqual(baseline.stage_exit_stop(next_stage_report()), "stage-exit-10s")

    def test_unexpected_scene_fails_before_the_first_transition_in_any_phase(self):
        for phase in ("offline-start-menu", "integrated-world-playing", "integrated-stage-transition"):
            with self.subTest(phase=phase):
                value = report(phase=phase, stage={"scene": "fixture-unexpected-stage"})
                self.assertEqual(baseline.stage_exit_stop(value), "unexpected-first-stage")

    def test_startup_without_a_scene_does_not_fail(self):
        self.assertIsNone(baseline.stage_exit_stop(report(phase="started", stage={})))

    def test_errors_and_extra_transitions_stop_before_success(self):
        for value, expected in (
            (next_stage_report(error="fixture error"), "first-failure"),
            (next_stage_report(firstFailure="fixture failure"), "first-failure"),
            (next_stage_report(stageProgress={"transitions": 2, "enteredAt": 100}), "extra-stage-transition"),
            (next_stage_report(stageProgress={"transitions": 1, "enteredAt": 200, "requested": "fixture-third-stage"}), "second-stage-exit"),
            (next_stage_report(stageProgress={"transitions": 1, "enteredAt": 200, "transporting": True}), "second-stage-exit"),
            (next_stage_report(phase="integrated-stage-transition"), "second-stage-exit"),
            (next_stage_report(stageProgress={"transitions": None}), "invalid-stage-progress"),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(baseline.stage_exit_stop(value), expected)

    def test_completed_first_exit_request_does_not_look_like_a_second_exit(self):
        value = next_stage_report(stageProgress={"transitions": 1, "enteredAt": 200, "requested": "fixture-next-stage", "transporting": False})
        self.assertEqual(baseline.stage_exit_stop(value), "stage-exit-10s")


class BaselineCliTests(unittest.TestCase):
    def cli(self, *arguments):
        with (
            patch.object(sys, "argv", ["dev", *arguments]),
            patch.object(baseline, "check_baseline", return_value={"success": True}) as check,
            patch.object(baseline.Device, "sleep_awakened", return_value=[]),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = 0
            try:
                runpy.run_path(str(Path(baseline.__file__).with_name("main.py")), run_name="__main__")
            except SystemExit as ended:
                code = ended.code
            return code, check.call_args_list

    def test_flag_reaches_check_and_plain_check_stays_default(self):
        for arguments, enabled in ((["check-baseline"], False), (["check-baseline", "--stage-exit"], True)):
            with self.subTest(arguments=arguments):
                code, calls = self.cli(*arguments)
                self.assertEqual(code, 0)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].kwargs, {"stage_exit": enabled, "capture_in_destination": False})

    def test_destination_capture_requires_and_reaches_one_exit_mode(self):
        code, calls = self.cli("check-baseline", "--stage-exit", "--capture-in-destination")
        self.assertEqual(code, 0)
        self.assertEqual(calls[0].kwargs, {"stage_exit": True, "capture_in_destination": True})
        for arguments in (["check-baseline"], ["test", "--stage-exit"]):
            code, calls = self.cli(*arguments, "--capture-in-destination")
            self.assertEqual(code, 2)
            self.assertEqual(calls, [])

    def test_stage_flag_is_rejected_for_other_commands(self):
        code, calls = self.cli("test", "--stage-exit")
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])


class StageExitTransportTests(unittest.TestCase):
    def test_mid_transport_report_is_not_an_unexpected_first_stage(self):
        # Observed on device (J526): destination scene reported before the count increments.
        report = {
            "phase": "stage-geometry-load",
            "stage": {"scene": "goolake"},
            "stageProgress": {"transitions": 0, "requested": "goolake", "transporting": True, "current": "lakes"},
        }
        self.assertIsNone(baseline.stage_exit_stop(report))

    def test_unexpected_scene_without_transport_still_fails(self):
        report = {"phase": "integrated-world-playing", "stage": {"scene": "goolake"}, "stageProgress": {"transitions": 0}}
        self.assertEqual(baseline.stage_exit_stop(report), "unexpected-first-stage")


if __name__ == "__main__":
    unittest.main()
