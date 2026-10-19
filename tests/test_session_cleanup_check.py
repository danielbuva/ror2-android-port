import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))

from session_cleanup_check import (
    SPINE_ID,
    cleanup_contract,
    matches_run,
    menu_start_coordinates,
    parse_display_size,
    parse_window_rotation,
    report_errors,
    restart_contract,
    runtime_stop,
    restart_coordinates,
    selector_action,
)
import session_cleanup_check as runner


def live_report(**changes):
    report = {
        "pid": 314,
        "attempt": "attempt-1",
        "id": SPINE_ID,
        "session": 1,
        "phase": "integrated-world-playing",
        "integratedWorld": True,
        "teleporterLoop": True,
        "stage": {"scene": "lakes"},
        "stageProgress": {"current": "lakes", "transitions": 0, "transporting": False},
        "debugOptions": {
            "invincibility": False,
            "highDamage": False,
            "fastCharge": False,
            "movementBoost": False,
            "jumpBoost": False,
        },
        "debugAcceleration": {
            "everAssisted": True,
            "normalGameAcceptanceEligible": False,
            "active": {
                "invincibility": False,
                "highDamage": False,
                "fastCharge": False,
                "movementBoost": False,
                "jumpBoost": False,
            },
            "events": [{"toggle": "diagnosticInput", "enabled": True}],
        },
        "world": {"seconds": 10.0, "ready": True, "health": 100.0, "diagnosticInputEver": True},
        "profile": {
            "ready": True,
            "appliedRuns": 13,
            "earnedUnlocks": 2,
            "availableEarnedUnlocks": 2,
        },
        "moonMission": False,
    }
    report.update(changes)
    return report


def completed_report(**overrides):
    report = live_report(
        phase="complete",
        success=True,
        cleanup=True,
        world={"cleaned": True, "diagnosticInputEver": True},
        objective={
            "cleaned": True,
            "nativeHostTeardownObserved": True,
            "nativeHostTeardownServerActive": True,
            "nativeHostTeardownSynchronous": True,
            "nativeHostTeardownPreAwake": False,
            "nativeHostCombatSquads": 1,
            "nativeHostDeathListenersBefore": 1,
            "nativeHostDeathListenersAfter": 0,
            "nativeHostSummonListenersBefore": 1,
            "nativeHostSummonListenersAfter": 0,
        },
        playerDefeat={"deathEvents": 1, "deathEntered": True, "bodyDestroyed": True},
        results={"persisted": True, "clientEnding": True},
        profile={
            "ready": True,
            "assistedExcluded": True,
            "resultApplied": False,
            "appliedRuns": 13,
            "earnedUnlocks": 2,
            "availableEarnedUnlocks": 2,
        },
    )
    report.update(overrides)
    return report


SYNTHETIC_SERIAL = "synthetic-device"


class FakeDevice:
    serial = SYNTHETIC_SERIAL

    def __init__(self, work, reports, log_error=False, foreign_selector=False):
        self.runtime = "/storage/emulated/0/Android/data/dev.ror2lab.arm64/files"
        self.remote = {}
        self.reports = list(reports)
        self.log_error = log_error
        self.foreign_selector = foreign_selector
        self.pid = "314"
        self.alive = False
        self.taps = []
        self.display_states = []
        self.completed_path = self.runtime + "/movement-completed-session-1.json"
        self.report_path = self.runtime + "/movement-batch-" + SPINE_ID + ".json"
        self.selector_path = self.runtime + "/movement-batch-selection.json"
        self.evidence_root = work / "receipts" / self.serial

    @property
    def settings(self):
        return {"storage_mode": "internal"}

    def owned(self):
        return {
            "storage": {"mode": "internal"},
            "package_path": "/data/app/dev.ror2lab.arm64/base.apk",
            "apk_sha256": self.apk_hash,
        }

    def storage(self):
        return {"mode": "internal"}

    def read_receipt(self, _name):
        return {"persistentDataPath": self.runtime}

    def evidence_directory(self, *components):
        return self.evidence_root.joinpath(*components)

    def cmd(self, *args, **_kwargs):
        if args[0] == "push":
            self.remote[args[2]] = Path(args[1]).read_text()

    def launch(self):
        self.alive = True
        return {"pid": self.pid}

    def display(self, awake):
        self.display_states.append(awake)
        return True

    def sh(self, *args, **_kwargs):
        if args[:2] == ("sh", "-c"):
            path = args[2].split("[ -L ", 1)[1].split(" ];", 1)[0]
            return "file" if path in self.remote else "absent"
        if args[0] == "cat":
            path = args[1]
            if path == self.report_path and self.alive and self.reports:
                report = self.reports.pop(0)
                if self.foreign_selector and report.get("session") == 2:
                    self.remote[self.selector_path] = json.dumps({"id": "foreign", "attempt": "foreign"})
                return json.dumps(report)
            return self.remote.get(path, "")
        if args[:2] == ("rm", "-f"):
            self.remote.pop(args[2], None)
            return ""
        if args[0] == "pidof":
            return self.pid if self.alive else ""
        if args[0] == "am" and args[1] == "force-stop":
            self.alive = False
            return ""
        if args[0] == "input" and args[1] == "tap":
            self.taps.append((int(args[2]), int(args[3])))
            if len(self.taps) == 2:
                self.remote[self.completed_path] = json.dumps(completed_report())
            return ""
        if args[:2] == ("wm", "size"):
            return "Physical size: 1280x800\n"
        if args[:3] == ("dumpsys", "window", "displays"):
            return "mDisplayRotation=ROTATION_0\n"
        if args[0] == "logcat":
            return "FINAL" if self.log_error else ""
        return ""


def run_fake_check(reports, *, log_error=False, foreign_selector=False, host_deadline_seconds=600):
    temp = tempfile.TemporaryDirectory()
    base = Path(temp.name)
    work = base / "work"
    apk = base / "current.apk"
    apk.write_bytes(b"synthetic apk artifact")
    apk_hash = hashlib.sha256(apk.read_bytes()).hexdigest()
    (work / "config").mkdir(parents=True)
    config = work / "lab-project/Assets/LabLoadingScene/Resources"
    config.mkdir(parents=True)
    (work / "config/current-build.json").write_text(
        json.dumps(
            {
                "success": True,
                "apk": str(apk),
                "apk_sha256": apk_hash,
            }
        )
    )
    (config / "MovementBatchProbe.json").write_text(json.dumps({"attempt": "attempt-1"}))
    device = FakeDevice(work, reports, log_error=log_error, foreign_selector=foreign_selector)
    device.apk_hash = apk_hash
    device.remote[device.report_path] = json.dumps({"attempt": "stale", "session": 1})
    device.remote[device.completed_path] = json.dumps({"attempt": "stale", "session": 1})
    ticks = iter(index / 10 for index in range(10000))
    patches = (
        mock.patch.object(runner, "ROOT", base),
        mock.patch.object(runner, "WORK", work),
        mock.patch.object(runner, "SessionCleanupDevice", return_value=device),
        mock.patch.object(runner, "now", return_value="synthetic-run"),
        mock.patch.object(runner.time, "monotonic", side_effect=lambda: next(ticks)),
        mock.patch.object(runner.time, "sleep", return_value=None),
        mock.patch.object(runner, "current_errors", side_effect=lambda logs, _pid: ["late log failure"] if logs == "FINAL" else []),
        mock.patch.object(runner, "HOST_DEADLINE_SECONDS", host_deadline_seconds),
    )
    with ExitStack() as stack:
        for patcher in patches:
            stack.enter_context(patcher)
        try:
            result = runner.check_session_cleanup()
            error = None
        except RuntimeError as exc:
            result = None
            error = exc
    evidence = work / "receipts" / device.serial / "experiments/session-cleanup/synthetic-run"
    return temp, device, result, error, evidence


def ordinary_start_report():
    report = live_report(
        session=1,
        phase="offline-start-menu",
        integratedWorld=False,
        teleporterLoop=False,
        hud={"menuStartX": 100, "menuStartY": 200, "screenWidth": 1280, "screenHeight": 800},
    )
    report.pop("profile")
    return report


def session_one_defeat_report():
    return live_report(
        session=1,
        phase="commando-defeated",
        results={"persisted": True, "clientEnding": True},
        hud={"screenWidth": 1280, "screenHeight": 800},
    )


class SessionCleanupCheckTests(unittest.TestCase):
    def test_report_identity_requires_process_attempt_and_owner(self):
        report = live_report()
        self.assertTrue(matches_run(report, 314, "attempt-1", 1))
        self.assertFalse(matches_run(report, 315, "attempt-1", 1))
        self.assertFalse(matches_run(report, 314, "other-attempt", 1))
        self.assertFalse(matches_run({**report, "id": "other"}, 314, "attempt-1", 1))

    def test_first_stage_exit_and_runtime_error_stop_immediately(self):
        report = live_report(stage={"scene": "goolake"})
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "outside-first-stage-contract")
        report = live_report(stage={"scene": None})
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "outside-first-stage-contract")
        report = live_report(firstFailure="native callback failed")
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "first-failure")
        self.assertEqual(runtime_stop(live_report(moonMission=True), 314, "attempt-1"), "outside-first-stage-contract")
        self.assertIsNone(runtime_stop(live_report(pid=999), 314, "attempt-1"))

    def test_nested_current_report_errors_fail_closed(self):
        report = live_report(results={"ledgerRecoveryError": "ledger write failed"})
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "first-failure")
        self.assertIn("results.ledgerRecoveryError: ledger write failed", report_errors(report))
        report = live_report(
            stageProgress={
                "current": "lakes",
                "transitions": 0,
                "transporting": False,
                "sirenEncounters": [{"error": "encounter cleanup failed"}],
            }
        )
        self.assertIn(
            "stageProgress.sirenEncounters[0].error: encounter cleanup failed",
            report_errors(report),
        )

    def test_missing_integrated_teleporter_contract_is_not_counted_as_a_run(self):
        report = live_report(teleporterLoop=False)
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "outside-first-stage-contract")
        menu = live_report(phase="offline-start-menu", integratedWorld=False, teleporterLoop=False)
        self.assertIsNone(runtime_stop(menu, 314, "attempt-1"))

    def test_completed_session_requires_active_native_listener_retirement_and_real_loss(self):
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        self.assertEqual(cleanup_contract(completed_report(), 314, "attempt-1", counts), [])
        report = completed_report()
        report["objective"]["nativeHostSummonListenersAfter"] = 1
        self.assertIn("native summon listener counts did not retire from 1 to 0", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["objective"]["nativeHostTeardownPreAwake"] = True
        self.assertIn("native teleporter never reached its active lifecycle", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["playerDefeat"]["deathEvents"] = 0
        self.assertIn("session did not finish one original player death", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["results"]["error"] = "late save failure"
        self.assertIn("results.error: late save failure", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report(firstFailure="primary failure")
        self.assertIn("firstFailure: primary failure", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["profile"]["assistedExcluded"] = False
        self.assertIn("assisted loss was not excluded from profile result application", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["profile"]["earnedUnlocks"] += 1
        self.assertIn("applied-run or earned-unlock counts changed/missing", cleanup_contract(report, 314, "attempt-1", counts))

    def test_restart_requires_same_process_second_session_on_lakes(self):
        report = live_report(session=2)
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        self.assertEqual(restart_contract(report, 314, "attempt-1", counts), [])
        self.assertIn("stage geometry identity is not Lakes", restart_contract({**report, "stage": {"scene": "goolake"}}, 314, "attempt-1", counts))

    def test_restart_requires_a_ready_observed_integrated_tick(self):
        report = live_report(
            session=2,
            world={
                "seconds": 0.0,
                "ready": False,
                "health": 0.0,
                "diagnosticInputEver": False,
            },
        )
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        self.assertFalse(runner.session2_ready(report))
        failures = restart_contract(report, 314, "attempt-1", counts)
        self.assertIn("second session did not reach a ready observed integrated tick", failures)

    def test_restart_tap_requires_reported_display_grid_to_match_android(self):
        report = live_report(hud={"screenWidth": 1280, "screenHeight": 800})
        self.assertEqual(parse_display_size("Physical size: 1280x800\n"), (1280, 800))
        self.assertEqual(parse_window_rotation("mDisplayRotation=ROTATION_0\n"), 0)
        displays = "mDisplayRotation=ROTATION_0\n"
        self.assertEqual(restart_coordinates(report, "Physical size: 1280x800\n", displays), (207, 420))
        self.assertIsNone(restart_coordinates(report, "Physical size: 800x1280\n", displays))
        self.assertIsNone(restart_coordinates(report, "Physical size: 1280x800\n", ""))
        self.assertIsNone(restart_coordinates(report, "Physical size: 1280x800\n", "mDisplayRotation=ROTATION_1\n"))
        self.assertIsNone(restart_coordinates(live_report(), "Physical size: 1280x800\n", displays))

    def test_restart_tap_maps_rotated_physical_portrait_to_logical_landscape(self):
        report = live_report(hud={"screenWidth": 1280, "screenHeight": 960})
        raw_rotation = "mDisplayRotation=ROTATION_90\nmDisplayRotation=ROTATION_90\n"
        mapping = runner.restart_mapping(report, "Physical size: 960x1280\n", raw_rotation)
        self.assertEqual(mapping["rotation_degrees"], 90)
        self.assertEqual(mapping["physical_size"], (960, 1280))
        self.assertEqual(mapping["logical_size"], (1280, 960))
        self.assertEqual(mapping["coordinates"], (207, 420))
        self.assertIsNone(
            runner.restart_mapping(
                report,
                "Physical size: 960x1280\n",
                "mDisplayRotation=ROTATION_90\nmDisplayRotation=ROTATION_0\n",
            )["coordinates"]
        )

    def test_menu_start_uses_only_finite_in_bounds_report_coordinates(self):
        report = live_report(hud={"menuStartX": 100.4, "menuStartY": 200.6, "screenWidth": 1280, "screenHeight": 800})
        self.assertEqual(menu_start_coordinates(report), (100, 201))
        self.assertIsNone(menu_start_coordinates(live_report(hud={"menuStartX": -1, "menuStartY": 2, "screenWidth": 1280, "screenHeight": 800})))

    def test_selector_cleanup_preserves_malformed_or_foreign_data(self):
        owned = json.dumps({"attempt": "attempt-1", "id": SPINE_ID})
        foreign = json.dumps({"attempt": "other", "id": SPINE_ID})
        self.assertEqual(selector_action("absent", "", "attempt-1"), "none")
        self.assertEqual(selector_action("file", owned, "attempt-1"), "remove-owned")
        self.assertEqual(selector_action("file", "{", "attempt-1"), "preserve-malformed")
        self.assertEqual(selector_action("file", foreign, "attempt-1"), "preserve-foreign")
        self.assertEqual(selector_action("symlink", "", "attempt-1"), "preserve-invalid-path")
        self.assertEqual(selector_action("other", "", "attempt-1"), "preserve-invalid-path")

    def test_mocked_runner_observes_stale_clear_death_restart_and_same_process(self):
        reports = [
            ordinary_start_report(),
            live_report(session=1),
            session_one_defeat_report(),
            live_report(
                session=2,
                world={
                    "seconds": 0.0,
                    "ready": False,
                    "health": 0.0,
                    "diagnosticInputEver": False,
                },
            ),
            live_report(session=2),
        ]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(error)
            self.assertTrue(result["success"])
            self.assertEqual(result["stop"], "same-process-restart")
            self.assertEqual(
                result["profile_snapshots"]["first_live_session"],
                {
                    "appliedRuns": 13,
                    "earnedUnlocks": 2,
                    "availableEarnedUnlocks": 2,
                },
            )
            self.assertEqual(len(device.taps), 2)
            self.assertFalse(device.alive)
            self.assertEqual(device.display_states, [True, False])
            self.assertNotIn(device.selector_path, device.remote)
            self.assertEqual(json.loads((evidence / "prior-completed-session-1.json").read_text())["attempt"], "stale")
            self.assertEqual(json.loads((evidence / "restart-display-mapping.json").read_text())["coordinates"], [207, 420])
            self.assertEqual(json.loads((evidence / "first-live-session.json").read_text())["phase"], "integrated-world-playing")
            self.assertEqual(json.loads((evidence / "result.json").read_text())["restarted_session"]["world"]["seconds"], 10.0)
            self.assertTrue(json.loads((evidence / "result.json").read_text())["success"])
        finally:
            temp.cleanup()

    def test_mocked_runner_final_log_only_error_fails_and_preserves_first_failure(self):
        reports = [
            ordinary_start_report(),
            live_report(session=1),
            session_one_defeat_report(),
            live_report(session=2),
        ]
        temp, _device, result, error, evidence = run_fake_check(reports, log_error=True)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertFalse(saved["success"])
            self.assertEqual(saved["first_failure"], "late log failure")
            self.assertTrue(any("current-process runtime errors" in failure for failure in saved["failures"]))
            self.assertIn("late log failure", str(error))
        finally:
            temp.cleanup()

    def test_mocked_runner_missing_observed_restart_never_passes(self):
        reports = [ordinary_start_report(), live_report(session=2)]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [(100, 200)])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertFalse(saved["success"])
            self.assertIn("session-1 defeat was not observed", saved["failures"])
            self.assertIn("restart input was not sent", saved["failures"])
        finally:
            temp.cleanup()

    def test_mocked_runner_requires_profile_counts_from_first_live_session(self):
        missing_counts = live_report(session=1, profile={"ready": False})
        reports = [ordinary_start_report(), missing_counts, session_one_defeat_report(), live_report(session=2)]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [(100, 200)])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "first-live-profile-baseline-unavailable")
            self.assertIsNone(saved["profile_baseline"])
        finally:
            temp.cleanup()

    def test_mocked_runner_stops_on_unexpected_session_index(self):
        reports = [ordinary_start_report(), live_report(session=3)]
        temp, _device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "unexpected-session-index")
            self.assertFalse(saved["success"])
        finally:
            temp.cleanup()

    def test_mocked_runner_does_not_accept_transient_restart_at_deadline(self):
        transient = live_report(
            session=2,
            world={
                "seconds": 0.0,
                "ready": False,
                "health": 0.0,
                "diagnosticInputEver": False,
            },
        )
        reports = [ordinary_start_report(), live_report(session=1), session_one_defeat_report(), transient]
        temp, _device, result, error, evidence = run_fake_check(
            reports,
            host_deadline_seconds=1.5,
        )
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "deadline")
            self.assertFalse(saved["success"])
            self.assertTrue(any("ready observed integrated tick" in failure for failure in saved["failures"]))
        finally:
            temp.cleanup()

    def test_mocked_runner_preserves_foreign_selector_during_cleanup(self):
        reports = [
            ordinary_start_report(),
            live_report(session=1),
            session_one_defeat_report(),
            live_report(session=2),
        ]
        temp, device, result, error, evidence = run_fake_check(reports, foreign_selector=True)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertIn(device.selector_path, device.remote)
            self.assertEqual(json.loads(device.remote[device.selector_path])["id"], "foreign")
            saved = json.loads((evidence / "result.json").read_text())
            self.assertFalse(saved["success"])
            self.assertTrue(any("preserved it" in failure for failure in saved["failures"]))
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
