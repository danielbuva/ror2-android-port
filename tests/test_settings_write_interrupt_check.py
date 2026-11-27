"""Interruption evidence must distinguish an uncommitted store from a completed save."""

from contextlib import ExitStack
import hashlib
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import settings_write_interrupt_check as check  # noqa: E402


class InterruptedWriteEvidenceTests(unittest.TestCase):
    witness = dict(success=True, createObserved=True, writerExited=True, pendingPresentBeforeStop=True, pendingPresentAfterStop=True)

    def test_profile_interruption_recovers_only_the_new_native_loss(self):
        self.check_profile_recovery(injected=False)

    def test_profile_enospc_retains_live_writer_and_recovers_only_the_new_native_loss(self):
        self.check_profile_recovery(injected=True)

    def check_profile_recovery(self, *, injected):
        root = "/owned-lab"
        primary = root + "/android-profile-v1/profile.json"
        settings = root + "/offline-settings-v1/preferences.json"
        result_root = root + "/offline-run-results-v1/"
        ledger = result_root + "profile.json"
        applied, new_id, nonce = "1" * 32, "2" * 32, "3" * 32
        run_file = "run-" + new_id + ".xml"
        loss = dict(file=run_file, ending="StandardLoss", win=False, debugAssisted=False)
        old_generation = dict(version=2, appliedRuns=[applied], baselineRuns=[])
        old_hashes = {primary: "original", primary + ".backup": "older", settings: "unchanged"}
        stopped_hashes = dict(old_hashes, **{ledger: "ledger", result_root + run_file: "xml"})
        if not injected:
            stopped_hashes[primary + ".pending"] = "partial"
        recovered_hashes = dict(stopped_hashes, **{primary: "updated", primary + ".backup": "original"})
        recovered_hashes.pop(primary + ".pending", None)
        device = Mock()
        device.read_receipt.return_value = {"persistentDataPath": root}
        thermal = Mock(error=None)
        witness = dict(nonce=nonce, pid=101, uid=10001, observerPid=102, pendingName="profile.json.pending")
        request_file = root + ("/movement-batch-selection.json" if injected else "/profile-write-observer.request")
        witness_file = root + "/ror2lab-write-" + nonce + ".result"
        witness_raw = json.dumps(dict(witness, **self.witness)).encode()
        pushed = {}

        def shell(*args, **kwargs):
            if args[0] == "sha256sum":
                return hashlib.sha256(witness_raw).hexdigest()
            if args[0] == "sh" and "stat -c" in args[2]:
                return str(len(witness_raw) if args[-2] == witness_file else len(pushed[request_file]))
            if args[0] == "pidof":
                return "101"
            return ""

        device.sh.side_effect = shell

        def command(op, source, dest):
            if op == "pull":
                Path(dest).write_bytes(witness_raw)
            if op == "push":
                pushed[dest] = Path(source).read_text()

        device.cmd.side_effect = command

        paths = {primary: "file", settings: "file"}
        ledger_states = iter(["absent", "file"])

        def path_state(device, path):
            if path == ledger:
                return next(ledger_states)
            return paths.get(path, "absent")

        def start(device, owner, pid, output, *, report_id):
            self.assertEqual(report_id, "body-state-spawn-state-auto-player")
            if pid == "101" and not injected:
                paths.update({witness_file: "file", primary + ".pending": "file"})
            else:
                paths.pop(primary + ".pending", None)
            return dict(profile=dict(ready=True, recovery="validated-primary", reconciledRuns=int(pid == "103")))

        def read_json(device, path):
            if path == primary:
                return next(generations)
            if path == ledger:
                return dict(version=1, runs=[loss])
            if injected:
                return dict(
                    pid=101,
                    attempt="fixture-attempt",
                    id="body-state-spawn-state-auto-player",
                    firstFailure="System.IO.IOException: ENOSPC: injected profile write failure\nstack trace",
                    results=dict(reportReloaded=True, persisted=False, reportFile=run_file),
                    profile=dict(resultApplied=False),
                )
            if path.endswith(".ready"):
                return witness
            return dict(witness, **self.witness)

        generations = iter([old_generation, dict(old_generation, appliedRuns=[applied, new_id])])
        start_device = Mock(side_effect=[dict(pid=101), dict(pid=103), dict(pid=104)])
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            stack.enter_context(patch.object(check, "bind_installed_apk"))
            stack.enter_context(patch.object(check, "attempt_from_installed", return_value="fixture-attempt"))
            stack.enter_context(patch.object(check, "observer_uid", return_value=10001))
            stack.enter_context(patch.object(check.uuid, "uuid4", return_value=Mock(hex=nonce)))
            stack.enter_context(patch.object(check, "_remote_path_state", side_effect=path_state))
            stack.enter_context(patch.object(check, "_read_json", side_effect=read_json))
            reads = iter([True, True, False])
            stack.enter_context(patch.object(check, "_read_raw", side_effect=lambda device, path: pushed[path] if next(reads) else ""))
            stack.enter_context(patch.object(check, "persistence_hashes", side_effect=[old_hashes, stopped_hashes, recovered_hashes, recovered_hashes]))
            stop = stack.enter_context(patch.object(check, "stop_after_observed_exit", return_value=dict(writer_absent=True)))
            stack.enter_context(patch.object(thermal, "between_sessions", return_value={}))
            cleanup = dict(bytes_removed=0, files=[])
            mode = "profile-save-failure" if injected else "profile-write-interrupt"
            receipt = check.check_profile_recovery(
                device, thermal, dict(mode=mode, apk_sha256="a" * 64, duration_seconds=2), Path(temporary), start_device, start, cleanup
            )
            if injected:
                stop.assert_not_called()
                self.assertEqual(receipt["writer_survived_pid"], "101")
                self.assertTrue(json.loads(pushed[request_file])["debugOptions"]["profileSaveFailure"])
                self.assertTrue((Path(temporary) / "profile-save-failed.json").is_file())
            else:
                stop.assert_called_once()
                self.assertEqual((Path(temporary) / Path(witness_file).name).read_bytes(), witness_raw)
                device.sh.assert_any_call("rm", "--", witness_file)
        self.assertTrue(receipt["success"])
        self.assertEqual(receipt["run_id"], new_id)
        self.assertEqual(start_device.call_count, 3)
        device.sh.assert_any_call("rm", "--", request_file)
        self.assertEqual(cleanup["bytes_removed"], len(pushed[request_file]) + (0 if injected else len(witness_raw)))
        self.assertFalse(any(primary + ".pending" in call.args for call in device.sh.call_args_list if call.args[0] == "rm"))

    def test_result_ledger_cannot_substitute_an_assisted_or_reordered_loss(self):
        old = dict(file="run-" + "1" * 32 + ".xml")
        new = dict(file="run-" + "2" * 32 + ".xml", ending="StandardLoss", win=False, debugAssisted=False)
        self.assertEqual(check.new_native_loss([old], [old, new]), ("2" * 32, new["file"]))
        for changed in ([new], [new, old], [old, dict(new, debugAssisted=True)], [old, dict(new, win=True)]):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                check.new_native_loss([old], changed)

    def test_injected_failure_checks_retained_generations_visible_retry_and_cold_load(self):
        device = Mock()
        device.read_receipt.return_value = {"persistentDataPath": "/synthetic"}
        live_pid = None
        launches = []
        selectors = []
        device.sh.side_effect = lambda *args, **kwargs: live_pid if args[0] == "pidof" else ""

        def push(*args):
            if args[0] == "push":
                selectors.append(json.loads(Path(args[1]).read_text()))

        device.cmd.side_effect = push

        def launch(current):
            nonlocal live_pid
            self.assertIs(current, device)
            live_pid = str(7 + len(launches))
            launches.append(selectors[-1])
            return {"pid": live_pid}

        cancelled = Mock()
        cancelled.is_set.return_value = False

        def report(**settings):
            return dict(phase="offline-start-menu", settings=dict(ready=True, buttonX=10, buttonY=20, screenWidth=1920, screenHeight=1080, **settings))

        reports = []
        for pid, stage in ((7, "write"), (8, "rename")):
            reports.extend(
                [
                    report(),
                    report(visible=True),
                    report(visible=True, persisted=False, injectedSaveFailure=stage, error="Storage retry"),
                    report(visible=False, persisted=True),
                ]
            )
            for value in reports[-4:]:
                value.update(pid=pid, attempt="fixture-attempt", id=check.SPINE_ID)
        reports.append(dict(report(recovery="validated-primary"), pid=9, attempt="fixture-attempt", id=check.SPINE_ID))
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            stack.enter_context(patch.object(check, "bind_installed_apk"))
            stack.enter_context(patch.object(check, "attempt_from_installed", return_value="fixture-attempt"))
            stack.enter_context(patch.object(check, "_read_json", side_effect=reports))
            stack.enter_context(patch.object(check, "_read_raw", return_value='{"version":1}'))
            stack.enter_context(patch.object(check, "_remote_path_state", side_effect=lambda d, p: "absent" if p.endswith(".pending") else "file"))
            stack.enter_context(patch.object(check, "protected_hashes", return_value={"profile": "retained"}))
            stack.enter_context(patch.object(check, "current_errors", return_value=[]))
            gestures = stack.enter_context(patch.object(check, "gesture"))
            result = check.check_settings_save_failure(device, Path(temporary), "a" * 64, launch, cancelled)
            self.assertTrue(result["success"])
            self.assertEqual([s["stage"] for s in result["stages"]], ["write", "rename"])
            self.assertEqual(gestures.call_count, 6)
            self.assertEqual([s["debugOptions"].get("settingsSaveFailure") for s in launches], ["write", "rename", None])
            self.assertEqual(launches[-1]["id"], check.SPINE_ID)
            self.assertEqual(launches[-1]["attempt"], "fixture-attempt")
            self.assertTrue(all(not value for key, value in launches[-1]["debugOptions"].items() if key != "purpose"))
            self.assertTrue((Path(temporary) / "settings-save-failure.json").is_file())

    def test_android_restarted_activity_is_stopped_without_reclassifying_writer_exit(self):
        device = Mock()
        device.sh.side_effect = ["456", "", ""]
        with patch.object(check, "_remote_path_state", return_value="absent"), patch.object(check, "bind_installed_apk") as binding:
            result = check.stop_after_observed_exit(device, dict(self.witness, pid=123), "a" * 64)
        self.assertEqual(result, dict(writer_pid=123, writer_absent=True, package_pids_before_stop="456"))
        device.sh.assert_any_call("am", "force-stop", check.PACKAGE)
        binding.assert_called_once_with(device.owned(), expected_sha256="a" * 64)

    def test_still_live_bound_writer_is_not_hidden_by_force_stop(self):
        device = Mock()
        with patch.object(check, "_remote_path_state", return_value="directory"), self.assertRaisesRegex(RuntimeError, "writer PID remains"):
            check.stop_after_observed_exit(device, dict(self.witness, pid=123), "a" * 64)
        device.sh.assert_not_called()

    def test_service_binding_requires_nonce_writer_uid_and_distinct_process(self):
        ready = dict(nonce="a" * 32, pid=123, uid=10001, observerPid=124)
        check.validate_observer_binding(ready, "a" * 32, "123", 10001)
        for changed in (dict(nonce="b" * 32), dict(pid=125), dict(uid=10002), dict(observerPid=123), dict(observerPid=True)):
            with self.subTest(changed=changed), self.assertRaisesRegex(RuntimeError, "binding differs"):
                check.validate_observer_binding(dict(ready, **changed), "a" * 32, "123", 10001)

    def test_a_completed_save_is_not_interruption_evidence(self):
        with self.assertRaisesRegex(RuntimeError, "Missed pre-commit"):
            check.interrupted_transaction("old valid JSON", "new valid JSON", dict(state="absent"), self.witness)

    def test_unchanged_primary_without_a_retained_pending_file_is_not_enough(self):
        with self.assertRaisesRegex(RuntimeError, "Missed pre-commit"):
            check.interrupted_transaction("old valid JSON", "old valid JSON", dict(state="absent"), self.witness)

    def test_real_old_primary_and_partial_pending_can_satisfy_the_observed_contract(self):
        with tempfile.TemporaryDirectory() as root:
            primary = Path(root) / "preferences.json"
            pending = Path(root) / "preferences.json.pending"
            primary.write_text('{"version":1,"invertY":false}')
            before = primary.read_text()
            pending.write_text('{"version":')
            check.interrupted_transaction(before, primary.read_text(), dict(state="file"), self.witness)
            self.assertEqual(primary.read_text(), before)
            self.assertEqual(pending.read_text(), '{"version":')

    def test_synthetic_or_failed_observer_reports_cannot_qualify_real_interruption(self):
        for witness in (
            None,
            {},
            dict(self.witness, success=False),
            dict(self.witness, createObserved=1),
            dict(self.witness, pendingPresentAfterStop=False),
            dict(self.witness, writerExited=False),
            dict(self.witness, writerExited=1),
            dict(self.witness, pendingPresentBeforeStop=False),
        ):
            with self.subTest(witness=witness), self.assertRaisesRegex(RuntimeError, "No successful native"):
                check.interrupted_transaction("old", "old", dict(state="file"), witness)

    def test_missing_artifact_identity_refuses_before_device_access(self):
        with patch.object(check, "Device", side_effect=AssertionError("unexpected device access")):
            with self.assertRaisesRegex(ValueError, "requires --expected-apk-sha256"):
                check.check_settings_write_interrupt()

    def failed_menu(self, root, report, *, capture_report=None, logs="actual PID logs", log_error=None):
        out = Path(root) / "evidence"
        device = Mock()
        device.read_receipt.return_value = {"persistentDataPath": "/runtime"}
        device.evidence_directory.return_value = out
        device.launch.return_value = {"pid": "123"}
        pids = iter(["", "123", ""])

        def sh(*args, **kwargs):
            if args[0] == "pidof":
                return "" if args[1].endswith(":settings_write_observer") else next(pids)
            if args[0] == "sha256sum":
                return "a" * 64
            if args[0] == "logcat":
                self.assertIn("--pid=123", args)
                if log_error:
                    raise log_error
                return logs
            return ""

        device.sh.side_effect = sh
        device.cmd.side_effect = lambda *args: Path(args[2]).write_text("{}") if args[0] == "pull" else None
        original = RuntimeError("transition interrupted")
        with ExitStack() as stack:
            for name, value in (
                ("Device", device),
                ("bind_installed_apk", None),
                ("attempt_from_installed", "attempt"),
                ("sha", "a" * 64),
                ("selection", {"debugOptions": {}}),
                ("_read_raw", "{}"),
                ("selector_action", "remove-owned"),
                ("matches_run", True),
            ):
                stack.enter_context(patch.object(check, name, return_value=value))
            stack.enter_context(patch.object(check, "_remote_path_state", side_effect=lambda d, p: "file" if p.endswith("preferences.json") else "absent"))
            stack.enter_context(patch.object(check, "_read_json", side_effect=[report, capture_report if capture_report is not None else report]))
            stack.enter_context(patch.object(check.time, "sleep", side_effect=original))
            with self.assertRaises(RuntimeError) as raised:
                check.check_settings_write_interrupt("a" * 64)
        return original, raised.exception, out, json.loads((out / "result.json").read_text())

    def test_failure_before_menu_ready_saves_current_report_and_actual_pid_logs(self):
        report = {"phase": "bootstrap"}
        with tempfile.TemporaryDirectory() as root:
            original, error, out, result = self.failed_menu(root, report)
            self.assertIs(error, original)
            self.assertEqual(json.loads((out / "failure-current-report.json").read_text()), report)
            self.assertEqual((out / "failure-process.log").read_text(), "actual PID logs")
            self.assertEqual(result["error"], str(original))

    def test_latest_native_failure_overrides_interrupted_transition(self):
        with tempfile.TemporaryDirectory() as root:
            original, error, out, result = self.failed_menu(
                root, {"phase": "bootstrap"}, capture_report={"firstFailure": "native broke"}, log_error=RuntimeError("log unavailable")
            )
            self.assertIn("Native first failure: native broke", str(error))
            self.assertIs(error.__cause__, original)
            self.assertEqual(result["original_error"], str(original))
            self.assertEqual(result["capture_errors"], ["log unavailable"])

    def test_runtime_log_error_overrides_transition_even_if_report_capture_fails(self):
        with tempfile.TemporaryDirectory() as root, patch.object(check, "current_errors", return_value=["runtime broke"]):
            original, error, out, result = self.failed_menu(root, {"phase": "bootstrap"}, capture_report=RuntimeError("report unavailable"))
            self.assertIn("Actual-PID runtime error", str(error))
            self.assertEqual(result["capture_errors"], ["report unavailable"])
            self.assertEqual(result["runtime_errors"], ["runtime broke"])
            self.assertEqual(json.loads((out / "failure-current-report.json").read_text()), {"phase": "bootstrap"})

    def test_capture_failures_preserve_original_transition_error(self):
        with tempfile.TemporaryDirectory() as root:
            original, error, out, result = self.failed_menu(
                root, {"phase": "bootstrap"}, capture_report=RuntimeError("report unavailable"), log_error=RuntimeError("log unavailable")
            )
            self.assertIs(error, original)
            self.assertEqual(result["capture_errors"], ["report unavailable", "log unavailable"])
