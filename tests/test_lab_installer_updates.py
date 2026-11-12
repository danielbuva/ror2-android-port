"""Host-only contracts: no keys, APKs, game inputs, tools, or device calls."""

from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
import os
import shlex
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lab_installer_updates", ROOT / "scripts/lab-installer-updates.py")
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)


class LabInstallerUpdatesTests(unittest.TestCase):
    def test_retain_declared_phone_artifact_streams_exact_bytes_before_cleanup(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        phone.installer_hash = "a" * 64
        directory = "b" * 16 + "-test/output"
        name = "emitted/Test Game.bundle"
        data = b"authored synthetic bundle witness\x00\xff\n" * 1000
        receipt = {"directory": directory, "files": {name: LAB.sha(data)}}
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "phone/files/owner-input/work/releases/jobs" / directory / name
            source.parent.mkdir(parents=True)
            source.write_bytes(data)
            target = root / "work/retained/content.bundle"

            def transfer(argv, **kwargs):
                self.assertEqual(argv[:4], [str(phone.adb), "-s", phone.serial, "exec-out"])
                remote = shlex.split(argv[4])
                self.assertEqual(remote[:4], ["run-as", LAB.PACKAGE, "sh", "-c"])
                self.assertTrue(hasattr(kwargs["stdout"], "fileno"))
                return real_run(["sh", "-c", remote[4]], cwd=root / "phone", **kwargs)

            with patch.object(LAB, "ROOT", root), patch.object(phone, "package_hash", return_value=phone.installer_hash):
                with patch.object(LAB.subprocess, "run", side_effect=transfer), patch.object(LAB, "DIAGNOSTICS", Mock()) as diagnostics:
                    self.assertEqual(phone.retain_build_artifact(receipt, name, target), {"bytes": len(data), "sha256": LAB.sha(data)})
                    diagnostics.record.assert_not_called()
                self.assertEqual(target.read_bytes(), data)
                shutil.rmtree(root / "phone")  # Owned device cleanup cannot remove retained output.
                self.assertEqual(target.read_bytes(), data)
                with self.assertRaisesRegex(LAB.Failure, "artifact-host-output-exists"):
                    phone.retain_build_artifact(receipt, name, target)
            self.assertEqual(list(target.parent.iterdir()), [target])

    def test_retain_artifact_refuses_unowned_undeclared_or_incomplete_results(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        phone.installer_hash = "a" * 64
        receipt = {"directory": "b" * 16 + "-test/output", "files": {"content.bundle": LAB.sha(b"complete")}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "work/retained/content.bundle"
            with patch.object(LAB, "ROOT", root), patch.object(phone, "package_hash", return_value=phone.installer_hash):
                for selected, name, output, reason in (
                    (receipt, "missing.bundle", target, "artifact-receipt-hash"),
                    ({**receipt, "directory": "../other/output"}, "content.bundle", target, "artifact-receipt-directory"),
                    ({**receipt, "files": {"../secret": "c" * 64}}, "../secret", target, "artifact-receipt-path"),
                    (receipt, "content.bundle", root / "tracked.bundle", "artifact-host-output-not-private"),
                ):
                    with self.subTest(reason=reason), patch.object(LAB.subprocess, "run") as transfer:
                        with self.assertRaisesRegex(LAB.Failure, reason):
                            phone.retain_build_artifact(selected, name, output)
                        transfer.assert_not_called()

                def partial(argv, **kwargs):
                    kwargs["stdout"].write(b"partial")
                    return subprocess.CompletedProcess(argv, 0, b"", b"")

                with patch.object(LAB.subprocess, "run", side_effect=partial):
                    with self.assertRaisesRegex(LAB.Failure, "artifact-transfer-hash-mismatch"):
                        phone.retain_build_artifact(receipt, "content.bundle", target)
                with patch.object(LAB.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 1)):
                    with self.assertRaisesRegex(LAB.Failure, "artifact-transfer-unavailable"):
                        phone.retain_build_artifact(receipt, "content.bundle", target)
                self.assertFalse(target.exists())
                self.assertEqual(list(target.parent.iterdir()), [])
            with patch.object(phone, "package_hash", return_value="d" * 64), patch.object(LAB.subprocess, "run") as transfer:
                with self.assertRaisesRegex(LAB.Failure, "artifact-installer-not-owned"):
                    phone.retain_build_artifact(receipt, "content.bundle", target)
                transfer.assert_not_called()

    def test_import_upload_preserves_space_containing_game_path_and_bytes(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        name = "import/files/pc/Test Game_Data/StreamingAssets/sample.bundle"
        data = b"authored synthetic bytes\x00\xff\n"
        with tempfile.TemporaryDirectory() as temporary:

            def shell(*args, stdin=None, **kwargs):
                self.assertEqual(args[0], "shell")
                command = " ".join(args[1:])
                prefix = "run-as " + LAB.PACKAGE + " "
                self.assertTrue(command.startswith(prefix))
                return subprocess.run(["sh", "-c", command.removeprefix(prefix)], input=stdin, cwd=temporary, check=True, capture_output=True).stdout

            with patch.object(phone, "command", side_effect=shell):
                phone.put(name, data)
            target = Path(temporary) / "files/owner-input" / name
            self.assertEqual(target.read_bytes(), data)
            self.assertEqual([path for path in Path(temporary).rglob("*") if path.is_file()], [target])

    @staticmethod
    def check_control(bounds="[1,2][30,40]", enabled="true"):
        return ET.fromstring(
            f'<hierarchy><node package="{LAB.PACKAGE}"><node package="{LAB.PACKAGE}" class="android.widget.Button" text="Check for updates" clickable="true" enabled="{enabled}" bounds="{bounds}"/></node></hierarchy>'
        )

    def test_check_acknowledgement_wait_is_short_read_only_and_bounded(self):
        phone, clock = LAB.Phone("synthetic-private", 1800), [0.0]
        phone.flow_metrics = Mock()
        with (
            patch.object(LAB.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(LAB.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
        ):
            with patch.object(phone, "read", return_value={"state": "TEST_WAIT"}) as read:
                self.assertIsNone(phone.check_acknowledgement())
                self.assertEqual(clock[0], 15)
                self.assertTrue(all(0 < call.kwargs["timeout"] <= 5 for call in read.call_args_list))
        phone.flow_metrics.sample.assert_not_called()
        for state, reason in (
            ("ERROR", "installer-update-error"),
            ("UP_TO_DATE", "release-check-state-unavailable"),
            (None, "release-check-state-unavailable"),
        ):
            with patch.object(phone, "read", return_value={"state": state}):
                with self.assertRaisesRegex(LAB.Failure, "^" + reason + "$"):
                    phone.check_acknowledgement()

    def test_check_acknowledged_action_never_retries_or_resets_state(self):
        phone = LAB.Phone("synthetic-private", 1)
        available = {"state": "UPDATE_AVAILABLE", "release": {"version_code": 2}}
        for state in (available, {"state": "CHECKING"}):
            with (
                patch.object(phone, "put") as put,
                patch.object(phone, "tap") as tap,
                patch.object(phone, "check_acknowledgement", return_value=state),
                patch.object(phone, "wait_state", return_value=available) as wait,
                patch.object(phone, "retry_unacknowledged_check", side_effect=AssertionError("no retry")),
            ):
                phone.check(2)
                put.assert_called_once_with("update-state.json", LAB.encoded({"state": "TEST_WAIT"}))
                tap.assert_called_once_with("Check for updates")
                self.assertEqual(wait.call_count, int(state["state"] == "CHECKING"))

    def test_check_retries_once_after_fresh_owned_control_and_unchanged_state(self):
        phone = LAB.Phone("synthetic-private", 1)
        available = {"state": "UPDATE_AVAILABLE", "release": {"version_code": 2}}
        with (
            patch.object(phone, "put") as put,
            patch.object(phone, "tap"),
            patch.object(phone, "check_acknowledgement", side_effect=[None, available]),
            patch.object(phone, "require_owned_installer") as owner,
            patch.object(phone, "shell"),
            patch.object(phone, "ui_windows", side_effect=[self.check_control(), self.check_control()]) as ui,
            patch.object(phone, "read", return_value={"state": "TEST_WAIT"}) as read,
            patch.object(phone, "tap_prompt_node") as retry,
        ):
            phone.check(2)
            self.assertEqual(put.call_count, 1)
            owner.assert_called_once()
            self.assertEqual(ui.call_count, 2)
            self.assertEqual(read.call_count, 2)
            self.assertTrue(all(call.kwargs == {"timeout": 5} for call in read.call_args_list))
            retry.assert_called_once()
        with (
            patch.object(phone, "put"),
            patch.object(phone, "tap"),
            patch.object(phone, "check_acknowledgement", return_value=None),
            patch.object(phone, "retry_unacknowledged_check", return_value=None) as retry,
        ):
            with self.assertRaisesRegex(LAB.Failure, "^check-action-not-acknowledged$"):
                phone.check(2)
            retry.assert_called_once()

    def test_check_late_acknowledgement_prohibits_the_second_tap(self):
        phone = LAB.Phone("synthetic-private", 1)
        for state in ("CHECKING", "UPDATE_AVAILABLE"):
            row = {"state": state, "release": {"version_code": 2}}
            for reads, ui_count in (([row], 0), ([{"state": "TEST_WAIT"}, row], 2)):
                with (
                    patch.object(phone, "require_owned_installer"),
                    patch.object(phone, "shell"),
                    patch.object(phone, "ui_windows", side_effect=[self.check_control(), self.check_control()]) as ui,
                    patch.object(phone, "read", side_effect=reads),
                    patch.object(phone, "tap_prompt_node", side_effect=AssertionError("late ack must not tap")),
                    patch.object(phone, "put", side_effect=AssertionError("must not reset")),
                ):
                    self.assertEqual(phone.retry_unacknowledged_check(), row)
                    self.assertEqual(ui.call_count, ui_count)

    def test_check_retry_refuses_changed_ambiguous_or_unowned_controls(self):
        phone = LAB.Phone("synthetic-private", 1)
        wrong = self.check_control()
        wrong.find("node").set("package", "synthetic-private")
        duplicate = self.check_control()
        duplicate.find("node").append(self.check_control().find("node/node"))
        for second in (
            wrong,
            duplicate,
            self.check_control(enabled="false"),
            self.check_control(bounds="[5,6][30,40]"),
            self.check_control(bounds="[0,0][0,0]"),
        ):
            with (
                patch.object(phone, "require_owned_installer"),
                patch.object(phone, "shell"),
                patch.object(phone, "ui_windows", side_effect=[self.check_control(), second]),
                patch.object(phone, "read", return_value={"state": "TEST_WAIT"}),
                patch.object(phone, "tap_prompt_node", side_effect=AssertionError("unqualified control must not tap")),
            ):
                with self.assertRaises(LAB.Failure):
                    phone.retry_unacknowledged_check()
        with (
            patch.object(phone, "require_owned_installer", side_effect=LAB.Failure("owned-hash-changed")),
            patch.object(phone, "ui_windows", side_effect=AssertionError("changed owner")),
        ):
            with self.assertRaisesRegex(LAB.Failure, "owned-hash-changed"):
                phone.retry_unacknowledged_check()

    def test_check_retry_refuses_unknown_state_and_never_changes_permissions(self):
        phone = LAB.Phone("synthetic-private", 1)
        for state in (None, {"state": "ERROR"}, {"state": "UP_TO_DATE"}):
            with (
                patch.object(phone, "require_owned_installer"),
                patch.object(phone, "shell"),
                patch.object(phone, "ui_windows", side_effect=[self.check_control(), self.check_control()]),
                patch.object(phone, "read", return_value=state),
                patch.object(phone, "tap_prompt_node", side_effect=AssertionError("unknown state")),
                patch.object(phone, "install", side_effect=AssertionError("no install")),
                patch.object(phone, "allow_visible_install_permission", side_effect=AssertionError("no permission")),
            ):
                with self.assertRaises(LAB.Failure):
                    phone.retry_unacknowledged_check()

    @staticmethod
    def timeout_records(root, states=("TEST_WAIT", "CHECKING"), name="run-first000", source="a" * 40):
        directory = root / "work/coordination/installer-update-acceptance" / name
        directory.mkdir(parents=True)

        def record(number, category, output, phase="baseline-N-check", code=0):
            path = directory / f"{number:05d}-{category}.json"
            path.write_bytes(LAB.encoded({"phase": phase, "category": category, "returncode": code, "outcome": "returned"}))
            path.with_suffix(".stdout.log").write_bytes(output)
            return path

        record(1, "resolve-source-commit", source.encode() + b"\n", "setup")
        for number, state in enumerate(states, 10):
            record(number, "device-state-read", LAB.encoded({"state": state, "message": "synthetic-private"}))
        ui = f'<hierarchy><node package="{LAB.PACKAGE}"><node package="{LAB.PACKAGE}" text="Check for updates" enabled="true" clickable="true" bounds="[1,2][3,4]"/><node package="{LAB.PACKAGE}" text="synthetic-private"/></node></hierarchy>'.encode()
        record(5, "device-ui-read", ui)
        return directory

    def timeout_inspection(self, root, *args):
        output = io.StringIO()
        phone_type = LAB.Phone
        with ExitStack() as stack:
            stack.enter_context(patch.object(LAB, "ROOT", root))
            stack.enter_context(patch.dict(os.environ, {}, clear=True))
            for name in ("read_context", "PrivateDiagnostics", "prepare_artifacts", "publisher_keys", "acceptance", "server"):
                stack.enter_context(patch.object(LAB, name, side_effect=AssertionError("inspection must not call " + name)))
            stack.enter_context(patch.object(LAB, "Phone", wraps=phone_type, side_effect=AssertionError("no device construction")))
            stack.enter_context(patch.object(LAB.subprocess, "run", side_effect=AssertionError("no commands")))
            stack.enter_context(redirect_stdout(output))
            code = LAB.main(["--inspect-check-timeout", *args])
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertNotIn(str(root), output.getvalue())
        self.assertNotIn("synthetic-private", output.getvalue())
        return code, json.loads(output.getvalue())

    def test_timeout_inspector_preserves_states_and_redacts_private_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.timeout_records(root, ("TEST_WAIT", "TEST_WAIT", "CHECKING", "UP_TO_DATE", "synthetic-private", {}, None))
            self.timeout_records(root, name="run-other000", source="b" * 40)
            before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            code, result = self.timeout_inspection(root, "a" * 40)
            self.assertEqual(code, 0)
            self.assertEqual(result["binding"], "unique-retained-source-not-run-id")
            self.assertEqual(result["state_counts"], {"TEST_WAIT": 2, "CHECKING": 1, "UP_TO_DATE": 1, "unknown": 3})
            self.assertEqual(result["first_transitions"], ["TEST_WAIT", "CHECKING", "UP_TO_DATE", "unknown"])
            self.assertEqual(
                result["last_retained_check_control"],
                {"status": "owned-root", "kind": "hierarchy", "count": 1, "enabled_count": 1, "clickable_count": 1, "bounds_valid_count": 1},
            )
            self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_timeout_inspector_refuses_ambiguous_or_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.timeout_records(root)
            for source in ("../synthetic-private", "b" * 40):
                self.assertEqual(self.timeout_inspection(root, source)[0], 1)
            self.timeout_records(root, name="run-second00")
            code, result = self.timeout_inspection(root, "a" * 40)
            self.assertEqual(code, 1)
            self.assertEqual(result["source_candidates"], 2)
            self.assertNotIn("state_counts", result)

    def test_timeout_inspector_rejects_other_modes_before_reading(self):
        with tempfile.TemporaryDirectory() as temporary:
            for flag in (
                "--host-only",
                "--inspect-state",
                "--inspect-ui-failure",
                "--inspect-update-failure",
                "--allow-test-installs",
                "--allow-test-notifications",
                "--qualify-phone-flow",
                "--qualify-install-prompts",
            ):
                with patch.object(LAB, "inspect_check_timeout", wraps=LAB.inspect_check_timeout):
                    # Prompt conflicts use the existing fixed FAIL output contract.
                    if flag.startswith("--qualify"):
                        with redirect_stdout(io.StringIO()):
                            self.assertEqual(LAB.main(["--inspect-check-timeout", "a" * 40, flag]), 1)
                    else:
                        self.assertEqual(self.timeout_inspection(Path(temporary), "a" * 40, flag)[0], 1)
            self.assertEqual(self.timeout_inspection(Path(temporary), "a" * 40, "--diagnostic-run", "newest")[0], 1)

    def test_timeout_inspector_does_not_follow_log_symlinks(self):
        for name in ("00010-device-state-read.stdout.log", "00005-device-ui-read.stdout.log", "00001-resolve-source-commit.stdout.log"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = self.timeout_records(root)
                path = directory / name
                path.unlink()
                path.symlink_to(root / "private-missing")
                code, result = self.timeout_inspection(root, "a" * 40)
                self.assertEqual(code, 1)
                self.assertEqual(result["errors"], ["log-inspection-record-unavailable"])

    def test_timeout_inspector_classifies_control_without_tap_or_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.timeout_records(root)
            path = directory / "00005-device-ui-read.stdout.log"
            original = path.read_text()
            path.write_text(original.replace("[1,2][3,4]", "[0,0][0,0]"))
            code, result = self.timeout_inspection(root, "a" * 40)
            self.assertEqual(code, 0)
            self.assertEqual(result["last_retained_check_control"]["bounds_valid_count"], 0)
            path.write_text(original.replace(LAB.PACKAGE, "synthetic-private"))
            code, result = self.timeout_inspection(root, "a" * 40)
            self.assertEqual(code, 0)
            self.assertEqual(result["last_retained_check_control"], {"status": "unclassified"})

    def test_timeout_inspector_bounds_transitions_and_distinguishes_absent_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.timeout_records(root, ("TEST_WAIT", "CHECKING") * 20)
            path = directory / "00049-device-state-read.stdout.log"
            path.write_text("null")
            code, result = self.timeout_inspection(root, "a" * 40)
            self.assertEqual(code, 0)
            self.assertEqual(len(result["first_transitions"]), 16)
            self.assertEqual(result["last_state"], "null")
            metadata_path = directory / "00049-device-state-read.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["returncode"] = 1
            metadata_path.write_bytes(LAB.encoded(metadata))
            self.assertEqual(self.timeout_inspection(root, "a" * 40)[1]["last_state"], "read-unavailable")

    def test_transport_reads_retry_signals_but_taps_do_not(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        killed = subprocess.CompletedProcess([], -9, b"", b"")
        success = subprocess.CompletedProcess([], 0, b"synthetic", b"")
        with patch.object(LAB.subprocess, "run", side_effect=[killed, success]) as run, patch.object(LAB.TRANSPORT.time, "sleep"):
            self.assertEqual(phone.shell("cat", "synthetic", label="read"), b"synthetic")
        self.assertEqual(run.call_count, 2)
        with patch.object(LAB.subprocess, "run", return_value=killed) as run:
            with self.assertRaisesRegex(LAB.Failure, "^tap$"):
                phone.shell("input", "tap", "1", "2", label="tap")
        self.assertEqual(run.call_count, 1)

    def test_install_ownership_requires_exact_readback_even_after_lost_adb(self):
        with tempfile.TemporaryDirectory() as temporary:
            apk = Path(temporary) / "synthetic-input"
            apk.write_bytes(b"authored synthetic text, not an APK")
            phone = LAB.Phone("synthetic-private-selector", 1)
            phone.install_volume = "synthetic-volume"
            with patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], -9, b"", b"")) as run:
                with patch.object(phone, "package_hash", return_value=LAB.sha(apk.read_bytes())):
                    phone.install(apk)
            self.assertTrue(phone.install_attempted)
            self.assertTrue(phone.owned_installer)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][3:7], ["install", "-r", "--force-uuid", "synthetic-volume"])

    def test_install_unknown_outcome_grants_no_cleanup_ownership(self):
        with tempfile.TemporaryDirectory() as temporary:
            apk = Path(temporary) / "synthetic-input"
            apk.write_bytes(b"synthetic text")
            phone = LAB.Phone("synthetic-private-selector", 1)
            phone.install_volume = "synthetic-volume"
            with patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], -9, b"", b"")) as run:
                with patch.object(phone, "package_hash", side_effect=LAB.Failure("unavailable")):
                    with self.assertRaisesRegex(LAB.Failure, "test-installer-install-unverified"):
                        phone.install(apk)
            self.assertTrue(phone.install_attempted)
            self.assertFalse(phone.owned_installer)
            self.assertEqual(run.call_count, 1)

    def test_detached_ui_preserves_final_dump_record_after_transport_cleanup(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        result = subprocess.CompletedProcess([], 0, b"synthetic dump", b"")
        with (
            patch.object(phone.transport, "start_detached", return_value=object()) as start,
            patch.object(phone.transport, "wait_detached", return_value=result) as wait,
        ):
            with patch.object(phone.transport, "cleanup_detached") as cleanup, patch.object(LAB, "adb_diagnostic") as record:
                self.assertIs(phone.detached(["uiautomator", "dump", phone.ui_path], label="device-ui-dump"), result)
        start.assert_called_once()
        wait.assert_called_once()
        cleanup.assert_called_once()
        record.assert_called_once_with("device-ui-dump", stdout=b"synthetic dump", stderr=b"", returncode=0)

    def test_detached_timeout_retains_private_handle_and_partial_logs_without_cleanup(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        job = LAB.TRANSPORT.DetachedJob("/data/local/tmp/ror2-adb-job-" + "a" * 32)

        def timeout(handle, logs, **kwargs):
            (logs / "stdout.log").write_bytes(b"synthetic partial")
            raise LAB.TRANSPORT.DetachedUncertain(handle)

        with tempfile.TemporaryDirectory() as temporary:
            diagnostics = LAB.PrivateDiagnostics(Path(temporary))
            with patch.object(LAB, "DIAGNOSTICS", diagnostics), patch.object(phone.transport, "start_detached", return_value=job):
                with patch.object(phone.transport, "wait_detached", side_effect=timeout), patch.object(phone.transport, "cleanup_detached") as cleanup:
                    with self.assertRaisesRegex(LAB.Failure, "^device-ui-dump$"):
                        phone.detached(["uiautomator", "dump", phone.ui_path], label="device-ui-dump")
            cleanup.assert_not_called()
            handle = json.loads((diagnostics.directory / (Path(job.directory).name + ".json")).read_text())
            self.assertEqual(handle["directory"], job.directory)
            self.assertEqual((diagnostics.directory / Path(job.directory).name / "stdout.log").read_bytes(), b"synthetic partial")
            final = json.loads((diagnostics.directory / "00001-device-ui-dump.json").read_text())
            self.assertEqual(final["outcome"], "TimeoutExpired")

    def run_install_poll(
        self, *, diagnostic, state=lambda _: "INSTALLING", receipt_at=None, timeout=120, require_pending_prompt=False, confirm_prompt=lambda: True
    ):
        phone = LAB.Phone("synthetic", timeout)
        clock = [0]
        receipt = {"release": {"version_code": 1}, "installed_readback_verified": True, "sha256": "a" * 64}

        def read(name):
            if name == "installed-release.json":
                return receipt if receipt_at is not None and clock[0] >= receipt_at else None
            self.assertEqual(name, "update-state.json")
            return {"state": state(clock[0])}

        def sleep(seconds):
            clock[0] += seconds

        with (
            patch.object(LAB.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(LAB.time, "sleep", side_effect=sleep),
            patch.object(phone, "read", side_effect=read),
            patch.object(phone, "capture_install_diagnostic", side_effect=lambda: diagnostic(clock[0])) as capture,
            patch.object(phone, "tap") as tap,
            patch.object(phone, "confirm_synthetic_install", side_effect=confirm_prompt),
            patch.object(phone, "package_hash", return_value=receipt["sha256"]),
            patch.object(phone, "storage"),
            patch.object(phone, "start"),
            patch.object(phone, "put") as put,
            patch.object(phone, "shell") as shell,
        ):
            try:
                result = phone.installed(1, require_pending_prompt=require_pending_prompt)
            except LAB.Failure as error:
                result = str(error)
            put.assert_not_called()
            shell.assert_not_called()
        return result, clock[0], capture.call_count, tap.call_count

    @staticmethod
    def settings_prompt(checked="false"):
        tree = ET.fromstring(
            '<hierarchy><node package="com.android.settings"><node text="Install unknown apps"/><node text="Owner game installer"/><node text="Allow from this source"/><node resource-id="android:id/switch_widget" checkable="true" enabled="true" bounds="[10,20][110,100]"/></node></hierarchy>'
        )
        tree.find("node")[-1].set("checked", checked)
        return tree

    @staticmethod
    def consent_prompt():
        return ET.fromstring(
            '<hierarchy><node package="com.android.packageinstaller"><node text="Synthetic update fixture"/><node resource-id="android:id/button1" text="Install" enabled="true" bounds="[10,20][110,100]"/></node></hierarchy>'
        )

    @staticmethod
    def owned_phone():
        phone = LAB.Phone("synthetic", 5)
        phone.owned_installer, phone.installer_hash = True, "a" * 64
        phone.settings_focus_key = "f" * 64
        phone.install_focus_key = "e" * 64
        return phone

    @staticmethod
    def settings_activity():
        return (
            "ACTIVITY MANAGER TOP-RESUMED (dumpsys activity top-resumed)\n"
            "packageName=com.android.settings processName=com.android.settings\n"
            "launchedFromUid=10007 launchedFromPackage=" + LAB.PACKAGE + " launchedFromFeature=null userId=7\n"
            "app=ProcessRecord{synthetic-private}\n"
            "Intent { act=android.settings.MANAGE_UNKNOWN_APP_SOURCES dat=package:"
            + LAB.PACKAGE
            + " cmp=com.android.settings/.Settings$ManageAppExternalSourcesActivity }\n"
            "rootOfTask=false task=Task{synthetic-private}\n"
            "taskAffinity=com.android.settings\n"
            "mActivityComponent=com.android.settings/.Settings$ManageAppExternalSourcesActivity\n"
            "state=RESUMED stopped=false delayedResume=false finishing=false\n"
            "occludesParent=true noDisplay=false immersive=false launchMode=0\n"
            "windows=[Window{abc123 u7 com.android.settings/com.android.settings.Settings$ManageAppExternalSourcesActivity}]\n"
            "mVisibleRequested=true mVisible=true mClientVisible=true reportedDrawn=true reportedVisible=true\n"
        ).encode()

    @staticmethod
    def settings_displays():
        return (
            "WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n"
            "  Display: mDisplayId=0 rootTasks=1\n"
            "  mCurrentFocus=Window{abc123 u7 com.android.settings/com.android.settings.Settings$ManageAppExternalSourcesActivity}\n"
            "  mFocusedApp=ActivityRecord{synthetic-private}\n"
        ).encode()

    def summarize_settings(self, data, user):
        return LAB.settings_activity_summary(data, user, self.settings_displays())

    def settings_verified(self):
        return self.summarize_settings(self.settings_activity(), b"7\n")

    def test_settings_snapshot_binds_single_primary_record_without_exporting_values(self):
        result = self.settings_verified()
        self.assertEqual(len(result), 8)
        self.assertTrue(all(value is True for value in result.values()))
        flagged = self.settings_activity().replace(b" cmp=", b" flg=0x10000000 cmp=")
        self.assertEqual(self.summarize_settings(flagged, b"7"), result)
        for forbidden in ("synthetic-private", "10007", LAB.PACKAGE, "ManageAppExternalSourcesActivity"):
            self.assertNotIn(forbidden, json.dumps(result))
        for data, user in (
            (b"", b"7"),
            (self.settings_activity() * 2, b"7"),
            (b"x" * 65537, b"7"),
            (b"\xff", b"7"),
            (self.settings_activity(), b"7" * 65),
            (self.settings_activity(), b"\xff"),
        ):
            self.assertFalse(all(self.summarize_settings(data, user).values()))

    def test_settings_snapshot_rejects_other_targets_users_state_aliases_and_nested_intents(self):
        original = self.settings_activity()
        edits = (
            (b"dat=package:" + LAB.PACKAGE.encode(), b"dat=package:" + LAB.PACKAGE.encode() + b".other"),
            (b"dat=package:" + LAB.PACKAGE.encode(), b"dat=package:another.app"),
            (b"act=android.settings.MANAGE_UNKNOWN_APP_SOURCES", b"act=android.settings.APPLICATION_DETAILS_SETTINGS"),
            (b"launchedFromPackage=" + LAB.PACKAGE.encode(), b"launchedFromPackage=another.app"),
            (b"mActivityComponent=com.android.settings/.Settings$ManageAppExternalSourcesActivity", b"mActivityComponent=com.android.settings/.OtherActivity"),
            (b"cmp=com.android.settings/.Settings$ManageAppExternalSourcesActivity", b"cmp=com.android.settings/.OtherActivity"),
            (b"userId=7", b"userId=8"),
            (b"state=RESUMED", b"state=PAUSING"),
            (b"stopped=false", b"stopped=true"),
            (b"finishing=false", b"finishing=true"),
            (b"delayedResume=false", b"delayedResume=true"),
            (b"noDisplay=false", b"noDisplay=true"),
            (b"noDisplay=false", b"noDisplay=false noDisplay=true"),
            (b"mVisible=true", b"mVisible=false"),
            (b"reportedDrawn=true", b"reportedDrawn=false"),
            (b" }\nrootOfTask", b" (has extras) }\nrootOfTask"),
            (b" }\nrootOfTask", b" sel={act=other} }\nrootOfTask"),
            (b"ACTIVITY MANAGER TOP-RESUMED (dumpsys activity top-resumed)", b"ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)"),
        )
        for before, after in edits:
            with self.subTest(after=after):
                result = self.summarize_settings(original.replace(before, after), b"7\n")
                self.assertFalse(all(result.values()))
                self.assertTrue(all(type(value) is bool for value in result.values()))
        for appended in (
            b"packageName=com.android.settings processName=com.android.settings\n",
            b"state=RESUMED stopped=false delayedResume=false finishing=false\n",
            b"  Pending Intent { dat=package:" + LAB.PACKAGE.encode() + b" }\n",
        ):
            self.assertFalse(all(self.summarize_settings(original + appended, b"7").values()))
        wrong_primary = original.replace(b"dat=package:" + LAB.PACKAGE.encode(), b"dat=package:another.app")
        self.assertFalse(all(self.summarize_settings(wrong_primary + b"  Intent { dat=package:" + LAB.PACKAGE.encode() + b" }\n", b"7").values()))

    def test_settings_window_binding_rejects_other_display_focus_and_ambiguous_records(self):
        activity, displays = self.settings_activity(), self.settings_displays()
        verified, key = LAB.settings_window_identity(activity, displays)
        self.assertTrue(verified)
        self.assertRegex(key, r"^[0-9a-f]{64}$")
        for changed_activity, changed_displays in (
            (activity, displays.replace(b"Window{abc123", b"Window{def456")),
            (activity, displays.replace(b"mDisplayId=0", b"mDisplayId=1")),
            (activity, displays + displays.split(b"\n", 1)[1]),
            (activity, displays + b"  mCurrentFocus=Window{abc123 u7 another}\n"),
            (
                activity,
                displays.replace(b"mCurrentFocus=Window{abc123", b"mCurrentFocus=Window{def456")
                + b"  Display: mDisplayId=1 rootTasks=1\n  mCurrentFocus=Window{abc123 u7 com.android.settings/com.android.settings.Settings$ManageAppExternalSourcesActivity}\n",
            ),
            (activity.replace(b"windows=[", b"unknown=["), displays),
            (activity + b"windows=[]\n", displays),
            (activity, b"x" * 131073),
            (activity, b"\xff"),
        ):
            with self.subTest(changed_displays=changed_displays[:80]):
                self.assertEqual(LAB.settings_window_identity(changed_activity, changed_displays), (False, None))
                self.assertFalse(all(LAB.settings_activity_summary(changed_activity, b"7", changed_displays).values()))
        # Another display may exist, but cannot supply the accepted focus.
        extra = displays + b"  Display: mDisplayId=1 rootTasks=1\n  mCurrentFocus=Window{def456 u7 another}\n"
        self.assertEqual(LAB.settings_window_identity(activity, extra), (True, key))

    def test_settings_snapshot_queries_are_read_only_bounded_and_retain_only_booleans(self):
        phone, diagnostics = self.owned_phone(), Mock()
        results = [
            subprocess.CompletedProcess([], 0, self.settings_activity(), b""),
            subprocess.CompletedProcess([], 0, b"7\n", b""),
            subprocess.CompletedProcess([], 0, self.settings_displays(), b""),
        ]
        with (
            patch.object(phone, "require_owned_installer") as owned,
            patch.object(LAB, "execute", side_effect=results) as execute,
            patch.object(LAB, "DIAGNOSTICS", diagnostics),
        ):
            self.assertEqual(phone.settings_identity(), self.settings_verified())
        owned.assert_called_once()
        self.assertEqual(
            [c.args[0][-1] for c in execute.call_args_list],
            ["'dumpsys activity top-resumed | head -c 65537'", "'am get-current-user | head -c 65'", "'dumpsys window displays | head -c 131073'"],
        )
        for call in execute.call_args_list:
            self.assertEqual(call.kwargs, {"label": "device-settings-identity-query", "timeout": 15, "record_output": False})
        self.assertEqual(json.loads(diagnostics.record.call_args.kwargs["stdout"]), self.settings_verified())
        self.assertNotIn("synthetic-private", str(diagnostics.record.call_args))
        for result in (
            subprocess.CompletedProcess([], 1, b"synthetic-private", b""),
            subprocess.CompletedProcess([], 0, self.settings_activity(), b"synthetic-private"),
        ):
            with patch.object(phone, "require_owned_installer"), patch.object(LAB, "execute", return_value=result), patch.object(LAB, "DIAGNOSTICS", None):
                self.assertFalse(all(phone.settings_identity().values()))
        with (
            patch.object(phone, "require_owned_installer", side_effect=LAB.Failure("install-prompt-installer-not-owned")),
            patch.object(LAB, "execute") as execute,
        ):
            with self.assertRaises(LAB.Failure):
                phone.settings_identity()
            execute.assert_not_called()

    def test_snapshot_raw_output_suppression_applies_to_success_and_timeout(self):
        diagnostics = Mock()
        with (
            patch.object(LAB, "DIAGNOSTICS", diagnostics),
            patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"synthetic-private", b"synthetic-private")),
        ):
            LAB.execute(["synthetic"], label="test", record_output=False)
        diagnostics.record.assert_not_called()
        with (
            patch.object(LAB, "DIAGNOSTICS", diagnostics),
            patch.object(
                LAB.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 1, output=b"synthetic-private", stderr=b"synthetic-private")
            ),
        ):
            with self.assertRaisesRegex(LAB.Failure, "^test$"):
                LAB.execute(["synthetic"], label="test", record_output=False)
        diagnostics.record.assert_not_called()

    def test_visible_permission_requires_fresh_owned_ungranted_package_without_writes(self):
        phone = self.owned_phone()
        for mode in ("No operations.", "REQUEST_INSTALL_PACKAGES: deny", "REQUEST_INSTALL_PACKAGES: ignore", "REQUEST_INSTALL_PACKAGES: default"):
            with patch.object(phone, "package_hash", return_value=phone.installer_hash), patch.object(phone, "shell", return_value=mode.encode()) as shell:
                phone.require_ungranted_install_permission()
                shell.assert_called_once_with("appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES", label="device-install-permission-query")
        for mode in ("REQUEST_INSTALL_PACKAGES: allow", "REQUEST_INSTALL_PACKAGES: foreground", "synthetic-private-output"):
            with patch.object(phone, "package_hash", return_value=phone.installer_hash), patch.object(phone, "shell", return_value=mode.encode()):
                with self.assertRaises(LAB.Failure) as error:
                    phone.require_ungranted_install_permission()
                self.assertNotIn("synthetic-private", str(error.exception))
        for owned, actual in ((False, "a" * 64), (True, "b" * 64)):
            phone.owned_installer = owned
            with patch.object(phone, "package_hash", return_value=actual), patch.object(phone, "shell") as shell:
                with self.assertRaisesRegex(LAB.Failure, "install-prompt-installer-not-owned"):
                    phone.require_ungranted_install_permission()
                shell.assert_not_called()

    def test_unset_permission_accepts_only_observed_default_mode_shape(self):
        phone = self.owned_phone()
        value = b"No operations.\nDefault mode: default\n"
        with patch.object(phone, "package_hash", return_value=phone.installer_hash), patch.object(phone, "shell", return_value=value) as shell:
            self.assertEqual(phone.install_permission_mode(), "default")
            phone.require_ungranted_install_permission()
            self.assertTrue(all(call.args == ("appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES") for call in shell.call_args_list))
        for value in (
            "No operations.\nDefault mode: allow",
            "No operations.\nDefault mode: foreground",
            "No operations.\nDefault mode: unknown",
            "No operations.\nDefault mode: deny",
            "No operations.\nDefault mode: default\nsynthetic-private",
            "synthetic-private\nNo operations.\nDefault mode: default",
            "No operations.\nDefault mode: default\nREQUEST_INSTALL_PACKAGES: deny",
            "No operations.\nDefault mode: default\nDefault mode: default",
            "No operations.\n\nDefault mode: default",
            "Default mode: default",
        ):
            with (
                self.subTest(value=value),
                patch.object(phone, "package_hash", return_value=phone.installer_hash),
                patch.object(phone, "shell", return_value=value.encode()),
            ):
                with self.assertRaisesRegex(LAB.Failure, "^device-install-permission-shape$"):
                    phone.require_ungranted_install_permission()
        phone.allow_test_installs = True
        with patch.object(phone, "package_hash", return_value=phone.installer_hash), patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "install-prompt-permission-already-granted"):
                phone.require_ungranted_install_permission()
            shell.assert_not_called()

    def test_settings_permission_is_app_opened_visibly_enabled_and_read_back(self):
        phone = self.owned_phone()
        app = ET.fromstring('<hierarchy><node package="' + LAB.PACKAGE + '"/></hierarchy>')
        with (
            patch.object(phone, "package_hash", return_value=phone.installer_hash),
            patch.object(phone, "tap") as tap,
            patch.object(phone, "settings_identity", return_value=self.settings_verified()),
            patch.object(phone, "shell", side_effect=[b"No operations.", b"", b"REQUEST_INSTALL_PACKAGES: allow", b""]) as shell,
            patch.object(phone, "ui_windows", side_effect=[self.settings_prompt(), self.settings_prompt("true")]),
            patch.object(phone, "ui_for", return_value=app),
        ):
            phone.allow_visible_install_permission()
        tap.assert_called_once_with("Install verified owner build")
        self.assertEqual(
            [c.args for c in shell.call_args_list],
            [
                ("appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES"),
                ("input", "tap", "60", "60"),
                ("appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES"),
                ("input", "keyevent", "KEYCODE_BACK"),
            ],
        )

    def test_settings_permission_rejects_foreign_ambiguous_or_already_enabled_prompt(self):
        for change in ("checked", "mixed", "duplicate", "disabled"):
            tree = self.settings_prompt()
            root = tree.find("node")
            if change == "checked":
                root[-1].set("checked", "true")
            elif change == "mixed":
                root[1].set("package", "another.app")
            elif change == "duplicate":
                ET.SubElement(root, "node", dict(root[-1].attrib))
            else:
                root[-1].set("enabled", "false")
            phone = self.owned_phone()
            with (
                self.subTest(change=change),
                patch.object(phone, "require_ungranted_install_permission"),
                patch.object(phone, "tap"),
                patch.object(phone, "settings_identity", return_value=self.settings_verified()),
                patch.object(phone, "ui_windows", return_value=tree),
                patch.object(phone, "shell") as shell,
            ):
                with self.assertRaises(LAB.Failure):
                    phone.allow_visible_install_permission()
                shell.assert_not_called()

    def test_settings_permission_requires_effective_grant_before_returning(self):
        phone, clock = self.owned_phone(), [0]

        def sleep(seconds):
            clock[0] += seconds

        with (
            patch.object(phone, "require_ungranted_install_permission"),
            patch.object(phone, "tap"),
            patch.object(phone, "settings_identity", return_value=self.settings_verified()),
            patch.object(phone, "ui_windows", side_effect=[self.settings_prompt()] + [self.settings_prompt("true")] * 15),
            patch.object(phone, "shell") as shell,
            patch.object(phone, "install_permission_mode", return_value="deny"),
            patch.object(LAB.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(LAB.time, "sleep", side_effect=sleep),
        ):
            with self.assertRaisesRegex(LAB.Failure, "install-settings-grant-not-observed"):
                phone.allow_visible_install_permission()
        shell.assert_called_once_with("input", "tap", "60", "60", label="device-install-permission-visible-enable")

    def test_settings_identity_change_or_missing_proof_never_taps_visible_switch(self):
        phone = self.owned_phone()
        verified = self.settings_verified()
        wrong = verified | {"target_verified": False}
        for identities, expected in (([verified, wrong], "install-settings-identity-changed"), ([wrong] * 30, "install-settings-identity-not-verified")):
            clock = [0]

            def sleep(seconds):
                clock[0] += seconds

            output = io.StringIO()
            with (
                patch.object(phone, "require_ungranted_install_permission"),
                patch.object(phone, "tap"),
                patch.object(phone, "settings_identity", side_effect=identities),
                patch.object(phone, "ui_windows", return_value=self.settings_prompt()),
                patch.object(phone, "shell") as shell,
                patch.object(LAB.time, "monotonic", side_effect=lambda: clock[0]),
                patch.object(LAB.time, "sleep", side_effect=sleep),
                redirect_stdout(output),
            ):
                with self.assertRaisesRegex(LAB.Failure, expected):
                    phone.allow_visible_install_permission()
            shell.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["observed"], wrong)

    def test_settings_window_change_after_ui_capture_refuses_tap(self):
        phone, count = self.owned_phone(), [0]

        def identity():
            count[0] += 1
            phone.settings_focus_key = ("a" if count[0] == 1 else "b") * 64
            return self.settings_verified()

        output = io.StringIO()
        with (
            patch.object(phone, "require_ungranted_install_permission"),
            patch.object(phone, "tap"),
            patch.object(phone, "settings_identity", side_effect=identity),
            patch.object(phone, "ui_windows", return_value=self.settings_prompt()),
            patch.object(phone, "shell") as shell,
            redirect_stdout(output),
        ):
            with self.assertRaisesRegex(LAB.Failure, "install-settings-identity-changed"):
                phone.allow_visible_install_permission()
        shell.assert_not_called()
        self.assertIs(json.loads(output.getvalue())["focus_unchanged"], False)

    def test_settings_verified_identity_still_requires_visible_switch_and_records_harness_actor(self):
        phone = self.owned_phone()
        tree = self.settings_prompt()
        # Missing/variant header text does not replace OS identity or switch proof.
        for node in tree.iter("node"):
            node.set("text", "")
        checked = ET.fromstring(ET.tostring(tree))
        checked.find("node")[-1].set("checked", "true")
        app = ET.fromstring('<hierarchy><node package="' + LAB.PACKAGE + '"/></hierarchy>')
        output = io.StringIO()
        with (
            patch.object(phone, "require_ungranted_install_permission"),
            patch.object(phone, "tap"),
            patch.object(phone, "settings_identity", return_value=self.settings_verified()),
            patch.object(phone, "ui_windows", side_effect=[tree, checked]) as ui,
            patch.object(phone, "ui_for", return_value=app),
            patch.object(phone, "shell"),
            patch.object(phone, "install_permission_mode", return_value="allow"),
            redirect_stdout(output),
        ):
            phone.allow_visible_install_permission()
        self.assertIn("INFO install-permission-switch actor=harness", output.getvalue())
        self.assertTrue(all(call.kwargs == {"recovery": False} for call in ui.call_args_list))

    def test_consent_summary_exports_only_fixed_classes_and_counts(self):
        nodes = [
            {"resource-id": "android:id/alertTitle", "text": "PRIVATE APP", "content-desc": "PRIVATE DESCRIPTION"},
            {"resource-id": "android:id/button1", "text": "PRIVATE ACTION", "enabled": "false"},
            {"resource-id": "android:id/message", "text": "PRIVATE ERROR"},
            {"resource-id": "PRIVATE RESOURCE", "text": "PRIVATE CONTENT"},
        ]
        summary = LAB.install_consent_summary(nodes)
        self.assertEqual(
            summary,
            {
                "expected_label_location": "neither",
                "title_class": "other",
                "button1_count": 1,
                "button1_enabled_count": 0,
                "button1_caption_class": "other",
                "layout_class": "message-dialog",
            },
        )
        self.assertNotIn("PRIVATE", json.dumps(summary))
        self.assertEqual(LAB.install_consent_summary([])["title_class"], "missing")
        nodes.append(dict(nodes[0]))
        nodes.append(dict(nodes[1]))
        self.assertEqual(LAB.install_consent_summary(nodes)["title_class"], "multiple")
        self.assertEqual(LAB.install_consent_summary(nodes)["button1_caption_class"], "multiple")

    def test_consent_summary_classifies_known_labels_without_broadening_tap_gate(self):
        for title, classification in (
            ("Synthetic update fixture", "synthetic-fixture"),
            (LAB.GAME, "fixture-package"),
            ("Owner game installer", "installer-host"),
        ):
            nodes = [
                {"resource-id": "android:id/alertTitle", "text": title},
                {"resource-id": "com.android.packageinstaller:id/install_confirm_question"},
                {"resource-id": "android:id/button1", "text": "Update", "enabled": "true"},
            ]
            result = LAB.install_consent_summary(nodes)
            self.assertEqual(result["title_class"], classification)
            self.assertEqual(result["layout_class"], "confirmation-control")
            self.assertEqual(result["button1_caption_class"], "update")
            self.assertEqual(result["button1_enabled_count"], 1)
        nodes.append({"content-desc": "Synthetic update fixture"})
        self.assertEqual(LAB.install_consent_summary(nodes)["expected_label_location"], "content-desc")
        nodes.append({"text": "Synthetic update fixture"})
        self.assertEqual(LAB.install_consent_summary(nodes)["expected_label_location"], "both")

    def test_refused_consent_emits_fixed_observation_without_a_tap(self):
        phone = self.owned_phone()
        tree = self.consent_prompt()
        tree.find("node")[0].set("text", "PRIVATE APP")
        tree.find("node")[0].set("content-desc", "Synthetic update fixture")
        with (
            patch.object(phone, "require_owned_installer"),
            patch.object(phone, "install_identity", return_value=self.install_verified()),
            patch.object(phone, "ui_windows", return_value=tree),
            patch.object(phone, "shell") as shell,
            redirect_stdout(io.StringIO()) as output,
        ):
            with self.assertRaisesRegex(LAB.Failure, "^install-consent-fixture-not-identified$"):
                phone.confirm_synthetic_install()
        result = json.loads(output.getvalue())
        self.assertEqual(result["mode"], "install-consent-fixture")
        self.assertTrue(result["identity_verified"])
        self.assertEqual(result["observed"]["expected_label_location"], "content-desc")
        self.assertNotIn("PRIVATE", output.getvalue())
        self.assertFalse(any(call.args[:2] == ("input", "tap") for call in shell.call_args_list))

    def test_synthetic_install_consent_requires_owned_fixture_and_identified_button(self):
        phone = self.owned_phone()
        with (
            patch.object(phone, "package_hash", return_value=phone.installer_hash),
            patch.object(phone, "install_identity", return_value=self.install_verified()),
            patch.object(phone, "ui_windows", return_value=self.consent_prompt()),
            patch.object(phone, "shell") as shell,
        ):
            self.assertTrue(phone.confirm_synthetic_install())
        self.assertEqual(shell.call_args.args, ("input", "tap", "60", "60"))
        self.assertEqual(shell.call_args.kwargs, {"label": "device-synthetic-install-consent"})
        for change in ("app", "button", "foreign", "duplicate"):
            tree = self.consent_prompt()
            root = tree.find("node")
            if change == "app":
                root[0].set("text", "Another app")
            elif change == "button":
                root[1].set("text", "Delete")
            elif change == "foreign":
                root.set("package", "another.app")
            else:
                ET.SubElement(root, "node", dict(root[1].attrib))
            with (
                self.subTest(change=change),
                patch.object(phone, "require_owned_installer"),
                patch.object(phone, "install_identity", return_value=self.install_verified()),
                patch.object(phone, "ui_windows", return_value=tree),
                patch.object(phone, "shell") as shell,
            ):
                with self.assertRaises(LAB.Failure):
                    phone.confirm_synthetic_install()
                self.assertFalse(any(c.args[:2] == ("input", "tap") for c in shell.call_args_list))

    @classmethod
    def install_activity(cls):
        return (
            cls.settings_activity()
            .replace(b"com.android.settings/.Settings$ManageAppExternalSourcesActivity", b"com.android.packageinstaller/.PackageInstallerActivity")
            .replace(
                b"com.android.settings/com.android.settings.Settings$ManageAppExternalSourcesActivity",
                b"com.android.packageinstaller/com.android.packageinstaller.PackageInstallerActivity",
            )
            .replace(b"com.android.settings", b"com.android.packageinstaller")
            .replace(b"launchedFromPackage=" + LAB.PACKAGE.encode(), b"launchedFromPackage=com.android.packageinstaller")
            .replace(
                b"act=android.settings.MANAGE_UNKNOWN_APP_SOURCES dat=package:" + LAB.PACKAGE.encode(),
                b"act=android.content.pm.action.CONFIRM_INSTALL flg=0x2000001 pkg=com.android.packageinstaller",
            )
            .replace(b".PackageInstallerActivity }", b".PackageInstallerActivity (has extras) }")
        )

    @classmethod
    def install_displays(cls):
        return cls.settings_displays().replace(
            b"com.android.settings/com.android.settings.Settings$ManageAppExternalSourcesActivity",
            b"com.android.packageinstaller/com.android.packageinstaller.PackageInstallerActivity",
        )

    def install_verified(self):
        return LAB.install_activity_summary(self.install_activity(), b"7", self.install_displays())

    def test_install_snapshot_binds_confirmation_activity_user_forwarder_and_focus(self):
        result = self.install_verified()
        self.assertTrue(all(result.values()))
        self.assertEqual(len(result), 8)
        for value in ("10007", "u7", "synthetic-private", "PackageInstallerActivity"):
            self.assertNotIn(value, json.dumps(result))
        for before, after in (
            (b".PackageInstallerActivity", b".InstallStart"),
            (b"CONFIRM_INSTALL", b"INSTALL_PACKAGE"),
            (b"launchedFromPackage=com.android.packageinstaller", b"launchedFromPackage=another.app"),
            (b"userId=7", b"userId=8"),
            (b"state=RESUMED", b"state=PAUSING"),
            (b"mVisible=true", b"mVisible=false"),
            (b"finishing=false", b"finishing=true"),
            (b" (has extras)", b""),
        ):
            with self.subTest(after=after):
                self.assertFalse(all(LAB.install_activity_summary(self.install_activity().replace(before, after), b"7", self.install_displays()).values()))
        for data in (self.settings_activity(), self.install_activity() * 2):
            self.assertFalse(all(LAB.install_activity_summary(data, b"7", self.install_displays()).values()))
        self.assertFalse(all(LAB.install_activity_summary(self.install_activity(), b"7", self.settings_displays()).values()))

    def test_install_snapshot_binds_explicit_system_package_to_component(self):
        activity = self.install_activity()
        self.assertTrue(all(self.install_verified().values()))
        without_package = activity.replace(b"pkg=com.android.packageinstaller ", b"")
        self.assertTrue(all(LAB.install_activity_summary(without_package, b"7", self.install_displays()).values()))
        for replacement in (
            b"pkg=another.app",
            b"pkg=com.android.packageinstaller.other",
            b"pkg=com.android.packageinstaller pkg=com.android.packageinstaller",
        ):
            with self.subTest(replacement=replacement):
                changed = activity.replace(b"pkg=com.android.packageinstaller", replacement)
                summary = LAB.install_activity_summary(changed, b"7", self.install_displays())
                self.assertIs(summary["target_verified"], False)
                self.assertIs(summary["component_verified"], True)

    def test_install_identity_query_keeps_raw_records_private(self):
        phone = self.owned_phone()
        outputs = (self.install_activity(), b"7", self.install_displays())
        with (
            patch.object(phone, "require_owned_installer"),
            patch.object(LAB, "execute", side_effect=[subprocess.CompletedProcess([], 0, value, b"") for value in outputs]) as execute,
            patch.object(LAB, "DIAGNOSTICS", Mock()) as diagnostics,
        ):
            self.assertTrue(all(phone.install_identity().values()))
        self.assertIsNotNone(phone.install_focus_key)
        self.assertTrue(all(call.kwargs["record_output"] is False for call in execute.call_args_list))
        self.assertEqual(json.loads(diagnostics.record.call_args.kwargs["stdout"]), self.install_verified())
        self.assertEqual(diagnostics.record.call_args.args, ("device-install-identity",))

    def test_install_consent_uses_focused_window_not_covered_app_root(self):
        phone = self.owned_phone()
        for caption in ("Install", "Update"):
            tree = self.consent_prompt()
            tree.find("node")[1].set("text", caption)
            with (
                self.subTest(caption=caption),
                patch.object(phone, "require_owned_installer"),
                patch.object(phone, "install_identity", return_value=self.install_verified()),
                patch.object(phone, "ui_for", side_effect=AssertionError("active root must not be used")),
                patch.object(phone, "ui_windows", return_value=tree) as ui,
                patch.object(phone, "shell") as shell,
                redirect_stdout(io.StringIO()) as output,
            ):
                self.assertTrue(phone.confirm_synthetic_install())
            ui.assert_called_once_with(("com.android.packageinstaller", "com.google.android.packageinstaller"), recovery=False)
            self.assertEqual(sum(call.args[:2] == ("input", "tap") for call in shell.call_args_list), 1)
            self.assertIn("android-install-consent actor=harness", output.getvalue())

    def test_install_consent_waits_without_tapping_an_unverified_activity(self):
        phone = self.owned_phone()
        with (
            patch.object(phone, "require_owned_installer"),
            patch.object(phone, "install_identity", return_value=self.install_verified() | {"component_verified": False}),
            patch.object(phone, "ui_windows") as ui,
            patch.object(phone, "shell") as shell,
            redirect_stdout(io.StringIO()),
        ):
            self.assertFalse(phone.confirm_synthetic_install())
        ui.assert_not_called()
        self.assertFalse(any(call.args[:2] == ("input", "tap") for call in shell.call_args_list))

    def test_install_consent_stops_on_focused_confirmation_with_wrong_target(self):
        phone = self.owned_phone()
        with (
            patch.object(phone, "require_owned_installer"),
            patch.object(phone, "install_identity", return_value=self.install_verified() | {"target_verified": False}),
            patch.object(phone, "ui_windows") as ui,
            patch.object(phone, "shell") as shell,
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(LAB.Failure, "^install-consent-target-not-verified$"):
                phone.confirm_synthetic_install()
        ui.assert_not_called()
        self.assertFalse(any(call.args[:2] == ("input", "tap") for call in shell.call_args_list))

    def test_install_consent_rechecks_activity_and_window_before_tapping(self):
        for changed_window in (False, True):
            phone, count = self.owned_phone(), [0]

            def identity():
                count[0] += 1
                if count[0] == 2:
                    if changed_window:
                        phone.install_focus_key = "b" * 64
                    else:
                        return self.install_verified() | {"caller_verified": False}
                return self.install_verified()

            with (
                self.subTest(changed_window=changed_window),
                patch.object(phone, "require_owned_installer"),
                patch.object(phone, "install_identity", side_effect=identity),
                patch.object(phone, "ui_windows", return_value=self.consent_prompt()),
                patch.object(phone, "shell") as shell,
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaisesRegex(LAB.Failure, "^install-consent-identity-changed$"):
                    phone.confirm_synthetic_install()
            self.assertFalse(any(call.args[:2] == ("input", "tap") for call in shell.call_args_list))

    def test_pending_prompt_requires_matching_callback_state_visible_consent_and_receipt(self):
        pending = {"status": "observed", "stage": "commit-returned", "callback": "pending-user-action", "session_match": True, "callback_entry": "entered"}
        confirm = Mock(return_value=True)
        result, _, captures, taps = self.run_install_poll(
            diagnostic=lambda now: pending if now >= 1 else pending | {"callback": "none", "session_match": None},
            state=lambda now: "AWAITING_CONFIRMATION" if now >= 1 else "INSTALLING",
            receipt_at=2,
            require_pending_prompt=True,
            confirm_prompt=confirm,
        )
        self.assertEqual(result["release"]["version_code"], 1)
        self.assertEqual((captures, taps, confirm.call_count), (2, 0, 1))
        for state, diagnostic, visible in (
            ("INSTALLING", pending, True),
            ("AWAITING_CONFIRMATION", pending | {"session_match": False}, True),
            ("AWAITING_CONFIRMATION", {"status": "unavailable"}, True),
            ("AWAITING_CONFIRMATION", pending, False),
        ):
            with self.subTest(state=state, diagnostic=diagnostic, visible=visible):
                result, _, _, taps = self.run_install_poll(
                    diagnostic=lambda _: diagnostic, state=lambda _: state, receipt_at=2, require_pending_prompt=True, confirm_prompt=lambda: visible
                )
                self.assertEqual(result, "install-pending-prompt-not-observed")
                self.assertEqual(taps, 0)

    def test_prompt_mode_refuses_pregrant_host_and_inspection_modes_without_setup(self):
        for flag in ("--allow-test-installs", "--host-only", "--inspect-state", "--inspect-ui-failure", "--inspect-update-failure"):
            with self.subTest(flag=flag), patch.object(LAB, "read_context") as setup, patch.object(LAB, "Phone") as phone, redirect_stdout(io.StringIO()):
                self.assertEqual(LAB.main(["--qualify-install-prompts", flag]), 1)
                setup.assert_not_called()
                phone.assert_not_called()

    def test_prompt_mode_reports_unrun_cases_and_preserves_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            phone = Mock()
            phone.cleanup.return_value = "verified-absent"
            output = io.StringIO()
            with (
                patch.object(LAB, "ROOT", Path(temporary)),
                patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "synthetic"}),
                patch.object(LAB, "read_context", return_value={}),
                patch.object(LAB, "Phone", return_value=phone),
                patch.object(LAB, "acceptance", side_effect=LAB.Failure("install-settings-prompt-not-identified")) as acceptance,
                redirect_stdout(output),
            ):
                self.assertEqual(LAB.main(["--qualify-install-prompts", "--allow-test-notifications"]), 1)
            self.assertEqual(acceptance.call_args.kwargs, {"qualify_install_prompts": True})
            for case in (*LAB.PROMPT_CASES, *LAB.CASES):
                self.assertIn("FAIL " + case, output.getvalue())
            self.assertIn("PASS cleanup packages=verified-absent", output.getvalue())
            phone.cleanup.assert_called_once()

    def test_first_callback_bound_starts_only_after_observed_commit_return(self):
        none = {"status": "observed", "stage": "commit-returned", "callback": "none", "session_match": None}
        result, elapsed, _, taps = self.run_install_poll(diagnostic=lambda now: none if now >= 70 else none | {"stage": "fsync-start"}, timeout=180)
        self.assertEqual((result, elapsed, taps), ("install-first-callback-timeout", 130, 130))

    def test_first_callback_bound_requires_installing_state_and_available_evidence(self):
        none = {"status": "observed", "stage": "commit-returned", "callback": "none", "session_match": None}
        result, elapsed, captures, _ = self.run_install_poll(diagnostic=lambda _: none, state=lambda _: "READY", timeout=65)
        self.assertEqual((result, elapsed, captures), ("install-readback-timeout", 65, 0))
        for interrupted in ({"status": "unavailable", "reason": "missing"}, none | {"stage": "prepare"}):
            with self.subTest(interrupted=interrupted):
                result, elapsed, _, _ = self.run_install_poll(diagnostic=lambda now: interrupted if now == 59 else none, timeout=125)
                self.assertEqual((result, elapsed), ("install-first-callback-timeout", 120))

        def unavailable(_):
            raise OSError("synthetic-private")

        result, elapsed, _, _ = self.run_install_poll(diagnostic=unavailable, timeout=65)
        self.assertEqual((result, elapsed), ("install-readback-timeout", 65))

    def test_any_observed_callback_disables_only_the_first_callback_bound(self):
        none = {"status": "observed", "stage": "commit-returned", "callback": "none", "session_match": None}
        for callback in ("pending-user-action", "success", "failure", "unknown"):
            for matched in (True, False):
                with self.subTest(callback=callback, matched=matched):
                    observed = none | {"callback": callback, "session_match": matched}
                    result, elapsed, captures, taps = self.run_install_poll(diagnostic=lambda now: observed if now == 59 else none)
                    self.assertEqual((result, elapsed, captures, taps), ("install-readback-timeout", 120, 60, 120))

    def test_callback_bound_never_overrides_success_error_or_original_deadline(self):
        none = {"status": "observed", "stage": "commit-returned", "callback": "none", "session_match": None}
        result, elapsed, _, _ = self.run_install_poll(diagnostic=lambda _: none, receipt_at=60)
        self.assertEqual(result["release"]["version_code"], 1)
        self.assertEqual(elapsed, 60)
        result, elapsed, _, _ = self.run_install_poll(diagnostic=lambda _: none, state=lambda now: "ERROR" if now == 60 else "INSTALLING")
        self.assertEqual((result, elapsed), ("installer-build-error", 60))
        result, elapsed, _, _ = self.run_install_poll(diagnostic=lambda _: none, timeout=30)
        self.assertEqual((result, elapsed), ("install-readback-timeout", 30))

    def test_schema_two_callback_entry_prevents_false_absence_timeout(self):
        raw = {"schema": 2, "stage": "commit-returned", "callback": "none", "session_match": None, "receiver_registration": "private", "callback_entry": "none"}
        none = LAB.install_diagnostic_summary(LAB.encoded(raw))
        result, elapsed, _, _ = self.run_install_poll(diagnostic=lambda _: none)
        self.assertEqual((result, elapsed), ("install-first-callback-timeout", 60))
        entered = LAB.install_diagnostic_summary(LAB.encoded(raw | {"callback_entry": "entered"}))
        result, elapsed, captures, _ = self.run_install_poll(diagnostic=lambda now: entered if now == 59 else none)
        self.assertEqual((result, elapsed, captures), ("install-readback-timeout", 120, 60))
        unknown = LAB.install_diagnostic_summary(LAB.encoded(raw | {"callback_entry": "unknown"}))
        result, elapsed, _, _ = self.run_install_poll(diagnostic=lambda _: unknown)
        self.assertEqual((result, elapsed), ("install-readback-timeout", 120))

    def test_install_diagnostic_schema_two_strict_fixed_receiver_and_entry_values(self):
        base = {
            "schema": 2,
            "stage": "commit-returned",
            "callback": "none",
            "session_match": None,
            "receiver_registration": "private",
            "callback_entry": "none",
        }
        for registration in ("private", "exported", "disabled", "missing", "unavailable"):
            for entry in ("none", "entered", "unknown"):
                row = base | {"receiver_registration": registration, "callback_entry": entry}
                self.assertEqual(
                    LAB.install_diagnostic_summary(LAB.encoded(row)), {"status": "observed"} | {key: value for key, value in row.items() if key != "schema"}
                )
        for row in (
            base | {"schema": 1},
            base | {"schema": 3},
            base | {"schema": True},
            base | {"receiver_registration": "private-secret"},
            base | {"receiver_registration": []},
            base | {"callback_entry": "private-secret"},
            base | {"callback_entry": False},
            base | {"extra": "private-secret"},
            {key: value for key, value in base.items() if key != "callback_entry"},
        ):
            result = LAB.install_diagnostic_summary(LAB.encoded(row))
            self.assertEqual(result, {"status": "unavailable", "reason": "invalid-schema"})
            self.assertNotIn("private-secret", json.dumps(result))

    def test_install_diagnostic_contract_is_strict_and_never_exports_unknown_values(self):
        base = {"schema": 1, "stage": "commit-returned", "callback": "none", "session_match": None}
        self.assertEqual(
            LAB.install_diagnostic_summary(LAB.encoded(base)), {"status": "observed", "stage": "commit-returned", "callback": "none", "session_match": None}
        )
        for stage in (
            "prepare",
            "session-create",
            "session-open",
            "write-start",
            "write-complete",
            "fsync-start",
            "fsync-complete",
            "commit-start",
            "commit-returned",
            "unknown",
        ):
            self.assertEqual(LAB.install_diagnostic_summary(LAB.encoded(base | {"stage": stage}))["stage"], stage)
        for callback in ("pending-user-action", "success", "failure", "unknown"):
            for matched in (True, False):
                row = base | {"callback": callback, "session_match": matched}
                self.assertEqual(LAB.install_diagnostic_summary(LAB.encoded(row))["session_match"], matched)
        for row in (
            base | {"schema": True},
            base | {"stage": "private-secret"},
            base | {"callback": "private-secret"},
            base | {"session_match": False},
            base | {"callback": "success", "session_match": 1},
            base | {"extra": "private-secret"},
            ["private-secret"],
        ):
            result = LAB.install_diagnostic_summary(LAB.encoded(row))
            self.assertEqual(result, {"status": "unavailable", "reason": "invalid-schema"})
            self.assertNotIn("private-secret", json.dumps(result))
        for data in (b"{", b"\xff", b'"private-secret"'):
            self.assertEqual(LAB.install_diagnostic_summary(data)["status"], "unavailable")
        self.assertEqual(LAB.install_diagnostic_summary(b"null")["reason"], "missing")
        self.assertEqual(LAB.install_diagnostic_summary(b"x" * 4097)["reason"], "size-limit")

    def test_install_diagnostic_capture_is_bounded_owned_and_read_only(self):
        phone = LAB.Phone("synthetic", 1)
        row = {"schema": 1, "stage": "fsync-start", "callback": "none", "session_match": None}
        with patch.object(phone, "shell") as shell, patch.object(phone, "package_hash") as hash_read:
            self.assertEqual(phone.capture_install_diagnostic()["reason"], "ownership-unverified")
            shell.assert_not_called()
            hash_read.assert_not_called()
        phone.owned_installer, phone.installer_hash = True, "a" * 64
        with patch.object(phone, "shell") as shell, patch.object(phone, "package_hash", return_value="b" * 64):
            self.assertEqual(phone.capture_install_diagnostic()["reason"], "ownership-unverified")
            shell.assert_not_called()
        with (
            patch.object(phone, "shell", return_value=LAB.encoded(row)) as shell,
            patch.object(phone, "package_hash", return_value=phone.installer_hash) as hash_read,
        ):
            self.assertEqual(phone.capture_install_diagnostic()["stage"], "fsync-start")
        hash_read.assert_called_once_with(LAB.PACKAGE)
        self.assertEqual(shell.call_args.args[:4], ("run-as", LAB.PACKAGE, "sh", "-c"))
        self.assertIn("head -c 4097 files/owner-input/install-diagnostic.json", shell.call_args.args[4])
        self.assertIn('[ ! -L "$p" ] || exit 1', shell.call_args.args[4])
        self.assertEqual(shell.call_args.kwargs, {"label": "device-install-diagnostic-read", "timeout": 15})

    def test_install_failure_capture_precedes_cleanup_and_keeps_original_error(self):
        for fail_capture, reason in (
            (False, "install-readback-timeout"),
            (True, "install-readback-timeout"),
            (False, "install-first-callback-timeout"),
            (True, "install-first-callback-timeout"),
        ):
            with self.subTest(fail_capture=fail_capture, reason=reason), tempfile.TemporaryDirectory() as tmp:
                output, events = io.StringIO(), []
                phone = Mock()

                def fail(*args):
                    LAB.set_phase("baseline-N-install")
                    raise LAB.Failure(reason)

                def capture():
                    events.append("capture")
                    if fail_capture:
                        raise ValueError("private-secret")
                    return {"status": "observed", "stage": "commit-returned", "callback": "none", "session_match": None}

                phone.capture_install_diagnostic.side_effect = capture
                phone.cleanup.side_effect = lambda: events.append("cleanup") or "verified-absent"
                with (
                    patch.object(LAB, "ROOT", Path(tmp)),
                    patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "synthetic"}),
                    patch.object(LAB, "read_context", return_value={}),
                    patch.object(LAB, "Phone", return_value=phone),
                    patch.object(LAB, "acceptance", side_effect=fail),
                    redirect_stdout(output),
                ):
                    self.assertEqual(LAB.main([]), 1)
                self.assertEqual(events, ["capture", "cleanup"])
                self.assertIn("reason=" + reason, output.getvalue())
                self.assertIn("PASS cleanup packages=verified-absent", output.getvalue())
                self.assertNotIn("private-secret", output.getvalue())
                diagnostic = json.loads(output.getvalue().splitlines()[0])
                self.assertEqual(diagnostic["mode"], "install-diagnostic")
                if fail_capture:
                    self.assertEqual(diagnostic["observed"], {"status": "unavailable", "reason": "capture-failed"})

    def test_install_diagnostic_output_failure_cannot_skip_cleanup_or_replace_failure(self):
        for mode in ("write", "flush"):
            for fail_capture in (False, True):
                with self.subTest(mode=mode, fail_capture=fail_capture), tempfile.TemporaryDirectory() as tmp:
                    events = []

                    class BrokenDiagnosticOutput(io.StringIO):
                        pending = False

                        def write(self, value):
                            if '"mode":"install-diagnostic"' in value:
                                events.append("diagnostic-output")
                                if mode == "write":
                                    raise BrokenPipeError("private-output-error")
                                self.pending = True
                            return super().write(value)

                        def flush(self):
                            if self.pending:
                                self.pending = False
                                raise BrokenPipeError("private-output-error")
                            return super().flush()

                    output, phone = BrokenDiagnosticOutput(), Mock()

                    def fail(*args):
                        LAB.set_phase("baseline-N-install")
                        raise LAB.Failure("install-readback-timeout")

                    def capture():
                        events.append("capture")
                        if fail_capture:
                            raise ValueError("private-capture-error")
                        return {"status": "observed", "stage": "commit-returned", "callback": "none", "session_match": None}

                    phone.capture_install_diagnostic.side_effect = capture
                    phone.cleanup.side_effect = lambda: events.append("cleanup") or "verified-absent"
                    with (
                        patch.object(LAB, "ROOT", Path(tmp)),
                        patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "synthetic"}),
                        patch.object(LAB, "read_context", return_value={}),
                        patch.object(LAB, "Phone", return_value=phone),
                        patch.object(LAB, "acceptance", side_effect=fail),
                        redirect_stdout(output),
                    ):
                        self.assertEqual(LAB.main([]), 1)
                    self.assertEqual(events, ["capture", "diagnostic-output", "cleanup"])
                    phone.cleanup.assert_called_once_with()
                    self.assertIsNone(LAB.DIAGNOSTICS)
                    self.assertIn("reason=install-readback-timeout", output.getvalue())
                    self.assertIn("PASS cleanup packages=verified-absent", output.getvalue())
                    self.assertNotIn("private-output-error", output.getvalue())
                    self.assertNotIn("private-capture-error", output.getvalue())

    def toolhost_inspection(self, root, args):
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"LAB_TOOLHOST_ROOT": str(root / "toolhost")}, clear=True))
            for name in ("read_context", "Phone", "PrivateDiagnostics", "prepare_artifacts", "publisher_keys", "acceptance", "server"):
                stack.enter_context(patch.object(LAB, name, side_effect=AssertionError("toolhost inspection must not call " + name)))
            stack.enter_context(patch.object(LAB.subprocess, "run", side_effect=AssertionError("toolhost inspection must not execute commands")))
            stack.enter_context(redirect_stdout(output))
            code = LAB.main(["--inspect-toolhost-failure", *args])
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertNotIn(str(root), output.getvalue())
        self.assertNotIn("synthetic-private", output.getvalue())
        return code, json.loads(output.getvalue())

    @staticmethod
    def toolhost_logs(root):
        build = root / "toolhost" / ("a" * 40)
        build.mkdir(parents=True)
        (build / "result.json").write_bytes(
            LAB.encoded({"source_commit": "a" * 40, "package": LAB.PACKAGE, "success": False, "failure": "javac exit 1", "private": "synthetic-private"})
        )
        run = root / "123456"
        run.mkdir()
        (run / "output.log").write_text(
            "$ python /synthetic-private/build.py --source " + "a" * 40 + " --out /synthetic-private\n"
            "/synthetic-private/ToolHostActivity.java:365: error: cannot find symbol\n"
            "symbol: synthetic-private-symbol\n"
        )
        return build, run

    def test_toolhost_inspector_reads_only_bound_receipt_and_run_log_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.toolhost_logs(root)
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            code, result = self.toolhost_inspection(root, ["a" * 40, "--diagnostic-run", "123456"])
            self.assertEqual(code, 0)
            self.assertFalse(result["build_success"])
            self.assertTrue(result["receipt_source_present"])
            self.assertTrue(result["receipt_failure_present"])
            self.assertEqual(result["receipt_failure"], {"category": "build-command-failed", "stage": "javac"})
            self.assertEqual(result["log_error"], {"category": "java-symbol-not-found", "source": "ToolHostActivity.java", "line": 365})
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})
            self.assertNotIn("a" * 40, json.dumps(result))

    def test_toolhost_inspector_refuses_unbound_selection_and_mutating_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.toolhost_logs(root)
            for args in (
                ["a" * 40],
                ["../synthetic-private", "--diagnostic-run", "123456"],
                ["a" * 40, "--diagnostic-run", "../synthetic-private"],
                *[
                    ["a" * 40, "--diagnostic-run", "123456", flag]
                    for flag in ("--host-only", "--allow-test-installs", "--allow-test-notifications", "--inspect-state", "--inspect-ui-failure")
                ],
            ):
                with self.subTest(args=args):
                    code, result = self.toolhost_inspection(root, args)
                    self.assertEqual(code, 1)
                    self.assertNotIn("log_error", result)

    def test_toolhost_inspector_refuses_log_source_drift_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build, run = self.toolhost_logs(root)
            log = run / "output.log"
            log.write_text("$ build --source " + "b" * 40 + "\n")
            code, result = self.toolhost_inspection(root, ["a" * 40, "--diagnostic-run", "123456"])
            self.assertEqual(code, 1)
            self.assertEqual(result["errors"], ["toolhost-inspection-log-source-mismatch"])
            log.unlink()
            log.symlink_to(root / "unrelated-not-read")
            code, result = self.toolhost_inspection(root, ["a" * 40, "--diagnostic-run", "123456"])
            self.assertEqual(code, 1)
            self.assertEqual(result["errors"], ["toolhost-inspection-record-unavailable"])

    def test_toolhost_error_classifier_never_exports_unknown_names_or_error_text(self):
        self.assertEqual(LAB.toolhost_error_summary("synthetic-private-error"), {"category": "unclassified"})
        self.assertEqual(
            LAB.toolhost_error_summary("Traceback (most recent call last):\nOSError: synthetic-private: No space left on device"),
            {"category": "storage-exhausted"},
        )
        self.assertEqual(LAB.toolhost_error_summary("TIMEOUT after 1200 s synthetic-private"), {"category": "timeout"})
        self.assertEqual(LAB.toolhost_error_summary("/synthetic-private/Unknown.java:99: error: cannot find symbol"), {"category": "java-symbol-not-found"})
        self.assertEqual(
            LAB.toolhost_error_summary("/synthetic-private/OwnerUpdateState.java:9: error: synthetic-private-syntax"),
            {"category": "java-compiler-error", "source": "OwnerUpdateState.java", "line": 9},
        )

    @staticmethod
    def private_ui_logs(root, run_name, dump=b"ERROR: could not get idle state.\n", read_error=b"cat: /synthetic/private/ui.xml: No such file or directory\n"):
        directory = root / "work/coordination/installer-update-acceptance" / run_name
        directory.mkdir(parents=True)
        for sequence, category, code, stdout, stderr in ((1, "device-ui-dump", 0, dump, b""), (2, "device-ui-read", 1, b"", read_error)):
            prefix = f"{sequence:05d}-{category}"
            (directory / (prefix + ".json")).write_bytes(
                LAB.encoded({"phase": "baseline-N-check", "category": category, "returncode": code, "outcome": "returned"})
            )
            (directory / (prefix + ".stdout.log")).write_bytes(stdout)
            (directory / (prefix + ".stderr.log")).write_bytes(stderr)
        return directory

    def log_inspection(self, root, args, mode="--inspect-ui-failure"):
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(LAB, "ROOT", root))
            stack.enter_context(patch.dict(os.environ, {}, clear=True))
            for name in ("read_context", "Phone", "PrivateDiagnostics", "prepare_artifacts", "publisher_keys", "acceptance", "server"):
                stack.enter_context(patch.object(LAB, name, side_effect=AssertionError("log inspection must not call " + name)))
            run = stack.enter_context(patch.object(LAB.subprocess, "run", side_effect=AssertionError("log inspection must not execute a command")))
            stack.enter_context(redirect_stdout(output))
            code = LAB.main([mode, *args])
        run.assert_not_called()
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertNotIn(str(root), output.getvalue())
        return code, json.loads(output.getvalue())

    def test_update_error_inspection_selects_first_retained_error_and_emits_only_public_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = root / "tools/phone-build/owner-apk/updates.py"
            public.parent.mkdir(parents=True)
            public.write_text('raise ValueError("public contract failure: " + private)\n')
            directory = root / "work/coordination/installer-update-acceptance/run-newest00"
            directory.mkdir(parents=True)
            for index, state in enumerate(
                (
                    {"state": "CHECKING", "message": "synthetic-private"},
                    {"state": "ERROR", "message": "ValueError: public contract failure: synthetic-private-input"},
                    {"state": "ERROR", "message": "RuntimeError: synthetic-private-later"},
                ),
                1,
            ):
                prefix = f"{index:05d}-device-state-read"
                (directory / (prefix + ".json")).write_bytes(
                    LAB.encoded({"phase": "baseline-N-check", "category": "device-state-read", "returncode": 0, "outcome": "returned"})
                )
                (directory / (prefix + ".stdout.log")).write_bytes(LAB.encoded(state))
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"], mode="--inspect-update-failure")
            self.assertEqual(code, 0)
            self.assertEqual(result["backend_error"]["exception_classes"], ["ValueError"])
            self.assertEqual(
                result["backend_error"]["public_templates"],
                [
                    {
                        "source": "tools/phone-build/owner-apk/updates.py",
                        "line": 1,
                        "public_message": "public contract failure: ",
                        "dynamic_suffix_omitted": True,
                    }
                ],
            )
            self.assertNotIn("synthetic-private", json.dumps(result))
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})
            for flag in ("--allow-test-notifications", "--allow-test-installs", "--host-only", "--inspect-ui-failure", "--inspect-state"):
                code, result = self.log_inspection(root, ["--diagnostic-run", "newest", flag], mode="--inspect-update-failure")
                self.assertEqual(code, 1)
                self.assertNotIn("backend_error", result)
            record = directory / "00002-device-state-read.stdout.log"
            record.unlink()
            record.symlink_to(root / "unrelated-not-read")
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"], mode="--inspect-update-failure")
            self.assertEqual(code, 1)
            self.assertEqual(result["errors"], ["log-inspection-record-unavailable"])

    def test_update_error_inspection_includes_baseline_install_but_not_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = root / "tools/phone-build/owner-apk/updates.py"
            public.parent.mkdir(parents=True)
            public.write_text('raise ValueError("public build failure")\n')
            directory = root / "work/coordination/installer-update-acceptance/run-newest00"
            directory.mkdir(parents=True)
            rows = (
                ("cleanup", {"state": "ERROR", "message": "synthetic-private-cleanup"}),
                ("baseline-N-check", {"state": "UPDATE_AVAILABLE"}),
                ("baseline-N-install", None),
                ("baseline-N-install", {"state": "ERROR", "message": "ValueError: public build failure"}),
                ("baseline-N-install", {"state": "ERROR", "message": "synthetic-private-later"}),
            )
            for index, (phase, state) in enumerate(rows, 1):
                prefix = f"{index:05d}-device-state-read"
                (directory / (prefix + ".json")).write_bytes(
                    LAB.encoded({"phase": phase, "category": "device-state-read", "returncode": 0, "outcome": "returned"})
                )
                (directory / (prefix + ".stdout.log")).write_bytes(LAB.encoded(state))
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"], mode="--inspect-update-failure")
            self.assertEqual(code, 0)
            self.assertEqual(result["phase"], "baseline-N-install")
            self.assertEqual(result["backend_error"]["public_templates"][0]["public_message"], "public build failure")
            self.assertNotIn("synthetic-private", json.dumps(result))
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})

    def test_update_error_inspection_preserves_pipeline_first_failure_without_private_suffixes(self):
        for stage, reason, expected in (
            ("apk", "[Errno 2] No such file or directory: '/synthetic-private/input'", {"os_error": "missing-file"}),
            ("signing", "PermissionError: [Errno 13] Permission denied: '/synthetic-private/key'", {"os_error": "permission-denied"}),
            ("apk", "[Errno 28] No space left on device: '/synthetic-private/output'", {"os_error": "no-space"}),
            ("assembly", "Source producer exited with code -9; private producer log retained.", {"producer_exit": -9}),
            ("apk", "public assembly refusal", {"public_message": "public assembly refusal"}),
            ("synthetic-private-stage", "[Errno 999] synthetic-private", {}),
            ("apk", {"synthetic-private": True}, {"status": "unavailable"}),
        ):
            with self.subTest(stage=stage, expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "tools/phone-build/owner-apk/build_owner_apk.py"
                source.parent.mkdir(parents=True)
                source.write_text('raise ValueError("public assembly refusal")\n')
                directory = root / "work/coordination/installer-update-acceptance/run-newest00"
                directory.mkdir(parents=True)
                prefix = directory / "00001-device-state-read"
                prefix.with_suffix(".json").write_bytes(
                    LAB.encoded({"phase": "baseline-N-install", "category": "device-state-read", "returncode": 0, "outcome": "returned"})
                )
                prefix.with_suffix(".stdout.log").write_bytes(
                    LAB.encoded(
                        {
                            "state": "ERROR",
                            "message": "synthetic-private-wrapper",
                            "pipeline": {
                                "current_stage": "install",
                                "first_failure": {"stage": stage, "reason": reason},
                                "stages": [{"id": "synthetic-private", "work": "/synthetic-private"}],
                            },
                        }
                    )
                )
                before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                code, result = self.log_inspection(root, ["--diagnostic-run", "newest"], mode="--inspect-update-failure")
                self.assertEqual(code, 0)
                first = result["pipeline_first_failure"]
                self.assertEqual(first["stage"], "unknown" if stage == "synthetic-private-stage" else stage)
                for key, value in expected.items():
                    actual = first["reason"]["public_templates"][0] if key == "public_message" else first["reason"]
                    self.assertEqual(actual[key], value)
                if not expected:
                    self.assertEqual(first["reason"], {"exception_classes": [], "public_templates": [], "public_traceback_frames": []})
                self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})
                self.assertNotIn("synthetic-private", json.dumps(result))

    def test_update_error_inspection_classifies_captured_apk_logs_without_raw_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "work/coordination/installer-update-acceptance/run-newest00"
            directory.mkdir(parents=True)
            for sequence, category, output in (
                (1, "device-state-read", LAB.encoded({"state": "ERROR", "message": "synthetic-private"})),
                (4, "device-apk-javac-log", b"ROR2_APK_LOG_BEGIN\n/synthetic-private/ProfileStore.java:42: error: cannot find symbol\nprivate-symbol\n"),
                (5, "device-apk-dex-log", b""),
                (6, "device-apk-javac-log", b"unrelated-later-log"),
            ):
                prefix = directory / f"{sequence:05d}-{category}"
                prefix.with_suffix(".json").write_bytes(
                    LAB.encoded({"phase": "baseline-N-install", "category": category, "returncode": 0, "outcome": "returned"})
                )
                prefix.with_suffix(".stdout.log").write_bytes(output)
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"], mode="--inspect-update-failure")
            self.assertEqual(code, 0)
            self.assertEqual(len(result["apk_logs"]), 2)
            self.assertEqual(result["apk_logs"][0]["status"], "captured")
            self.assertEqual(result["apk_logs"][0]["error"], {"category": "java-symbol-not-found", "source": "ProfileStore.java", "line": 42})
            self.assertEqual(result["apk_logs"][1], {"tool": "dex", "status": "not-found"})
            self.assertNotIn("private-symbol", json.dumps(result))
            self.assertNotIn("unrelated-later-log", json.dumps(result))

    def test_backend_error_summary_preserves_only_public_literals_and_traceback_locations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = "tools/phone-build/owner-apk/updates.py"
            path = root / source
            path.parent.mkdir(parents=True)
            path.write_text('raise ValueError("exact public failure")\nraise ValueError("public prefix: " + value)\n')
            java = root / "tools/phone-build/managed-host/ToolHostActivity.java"
            java.parent.mkdir(parents=True)
            java.write_text('throw new IOException("public native failure " + name);\n')
            with patch.object(LAB, "ROOT", root):
                result = LAB.backend_error_summary(
                    'java.io.IOException: owner-backend exit 1 Traceback:\n  File "/synthetic-private/repo/'
                    + source
                    + '", line 17, in private_function\nValueError: public prefix: synthetic-private'
                )
                self.assertEqual(result["owner_backend_exit"], 1)
                self.assertEqual(result["public_traceback_frames"], [{"source": source, "line": 17}])
                self.assertEqual(result["public_templates"][0]["public_message"], "public prefix: ")
                self.assertNotIn("synthetic-private", json.dumps(result))
                self.assertNotIn("private_function", json.dumps(result))
                result = LAB.backend_error_summary("java.io.IOException: public native failure synthetic-private")
                self.assertEqual(result["public_templates"][0]["public_message"], "public native failure ")
                for value in ("exact public failure synthetic-private", "synthetic-private", "SecretException: synthetic-private"):
                    self.assertEqual(LAB.backend_error_summary(value), {"exception_classes": [], "public_templates": [], "public_traceback_frames": []})

    def test_private_ui_log_summary_selects_one_run_and_only_fixed_classifications(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.private_ui_logs(root, "run-first000", dump=b"ERROR: null root node returned by UiTestAutomationBridge.\n")
            newest = self.private_ui_logs(root, "run-newest00")
            os.utime(first, ns=(1, 1))
            os.utime(newest, ns=(2, 2))
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 0)
            self.assertEqual(result["selection"], "newest")
            self.assertEqual([row["category"] for row in result["records"]], ["device-ui-dump", "device-ui-read"])
            self.assertEqual(result["records"][0]["stdout"], "idle-timeout")
            self.assertEqual(result["records"][0]["returncode"], "zero")
            self.assertEqual(result["records"][1]["stderr"], "missing-file")
            self.assertEqual(result["records"][1]["returncode"], "nonzero")
            code, explicit = self.log_inspection(root, ["--diagnostic-run", "run-first000"])
            self.assertEqual(code, 0)
            self.assertEqual(explicit["selection"], "explicit")
            self.assertEqual(explicit["records"][0]["stdout"], "null-root")
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})
            for private in ("synthetic", "ui.xml", "run-newest00", "run-first000", "UiTestAutomationBridge"):
                self.assertNotIn(private, json.dumps([result, explicit]))

    def test_private_ui_log_summary_observes_failed_dump_without_inventing_a_read(self):
        for category, code, outcome, stderr, classification, termination in (
            ("device-ui-dump", 1, "returned", b"ERROR: null root node synthetic-private", "null-root", "exit-nonzero"),
            ("device-ui-windows-dump", 1, "returned", b"Permission denied: synthetic-private", "permission-denied", "exit-nonzero"),
            ("device-ui-dump", None, "TimeoutExpired", b"synthetic-private", "other-output", "unavailable"),
            ("device-ui-dump", None, "OSError", b"", "empty", "unavailable"),
            ("device-ui-dump", -9, "returned", b"", "empty", "signal-SIGKILL"),
            ("device-ui-windows-dump", -15, "returned", b"", "empty", "signal-SIGTERM"),
            ("device-ui-dump", -999, "returned", b"", "empty", "signal-other"),
            ("device-ui-dump", 137, "returned", b"", "empty", "exit-nonzero"),
            ("device-ui-dump", "synthetic-private", "returned", b"", "empty", "unavailable"),
        ):
            with self.subTest(category=category, outcome=outcome), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = root / "work/coordination/installer-update-acceptance/run-newest00"
                directory.mkdir(parents=True)
                prefix = "00001-" + category
                (directory / (prefix + ".json")).write_bytes(
                    LAB.encoded({"phase": "baseline-N-check", "category": category, "returncode": code, "outcome": outcome})
                )
                (directory / (prefix + ".stdout.log")).write_bytes(b"")
                (directory / (prefix + ".stderr.log")).write_bytes(stderr)
                before = {path: path.read_bytes() for path in directory.iterdir()}
                status, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
                self.assertEqual(status, 0)
                self.assertEqual(len(result["records"]), 1)
                self.assertEqual(result["records"][0]["category"], category)
                self.assertEqual(result["records"][0]["outcome"], outcome)
                self.assertEqual(result["records"][0]["returncode"], "nonzero" if type(code) is int else "unavailable")
                self.assertEqual(result["records"][0]["termination"], termination)
                self.assertEqual(result["records"][0]["stderr"], classification)
                self.assertEqual(before, {path: path.read_bytes() for path in directory.iterdir()})
                self.assertNotIn("synthetic-private", json.dumps(result))

    def test_private_ui_log_summary_pairs_failed_read_with_actual_windows_dump(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.private_ui_logs(root, "run-newest00")
            for suffix in (".json", ".stdout.log", ".stderr.log"):
                (directory / ("00001-device-ui-dump" + suffix)).rename(directory / ("00001-device-ui-windows-dump" + suffix))
            metadata = directory / "00001-device-ui-windows-dump.json"
            row = json.loads(metadata.read_bytes())
            row["category"] = "device-ui-windows-dump"
            metadata.write_bytes(LAB.encoded(row))
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 0)
            self.assertEqual([record["category"] for record in result["records"]], ["device-ui-windows-dump", "device-ui-read"])
            self.assertEqual(result["foreground"], {"status": "unknown", "reason": "ui-window-read-unavailable"})

    def test_private_ui_log_classification_never_echoes_unknown_output(self):
        for data, expected in (
            (b"synthetic-private-error", "other-output"),
            (b" ", "empty"),
            (b"cat: /synthetic/private: Permission denied", "permission-denied"),
            (b"UI hierchary dumped to: /synthetic/private", "dump-reported-written"),
            (b"UI hierarchy dumped to: /synthetic/private", "dump-reported-written"),
            (b"ERROR: Error while dumping window hierarchy: synthetic-private", "hierarchy-write-error"),
            (b'<?xml version="1.0"?><hierarchy>synthetic-private</hierarchy>', "hierarchy-present"),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(LAB.ui_output_classification(data), expected)

    def test_private_ui_log_summary_rejects_unconstrained_selection_and_other_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.private_ui_logs(root, "run-newest00")
            for args in (
                [],
                ["--diagnostic-run", "../synthetic-private"],
                ["--diagnostic-run", str(root)],
                ["--diagnostic-run", "newest", "--inspect-state"],
                ["--diagnostic-run", "newest", "--allow-test-installs"],
                ["--diagnostic-run", "newest", "--allow-test-notifications"],
            ):
                with self.subTest(args=args):
                    code, result = self.log_inspection(root, args)
                    self.assertEqual(code, 1)
                    self.assertEqual(result["records"], [])
                    self.assertNotIn("synthetic-private", json.dumps(result))

    def test_private_ui_log_summary_refuses_symlinks_and_does_not_search_other_namespaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "work/coordination/installer-update-acceptance"
            other = root / "unrelated"
            other.mkdir()
            parent.mkdir(parents=True)
            (parent / "run-symlink0").symlink_to(other, target_is_directory=True)
            for selection in ("newest", "run-symlink0"):
                code, result = self.log_inspection(root, ["--diagnostic-run", selection])
                self.assertEqual(code, 1)
                self.assertEqual(result["records"], [])
            directory = self.private_ui_logs(root, "run-newest00")
            record = directory / "00002-device-ui-read.stderr.log"
            record.unlink()
            record.symlink_to(other / "not-read")
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 1)
            self.assertEqual(result["errors"], ["log-inspection-record-unavailable"])

    def inspection(self, results, extra_args=(), environment=None):
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(os.environ, environment if environment is not None else {"LAB_DEVICE_SERIAL": "synthetic-private-selector"}, clear=True)
            )
            for name in ("read_context", "PrivateDiagnostics", "prepare_artifacts", "publisher_keys", "acceptance", "server"):
                stack.enter_context(patch.object(LAB, name, side_effect=AssertionError("inspection must not call " + name)))
            for name in ("cleanup", "ui", "start", "put", "read", "storage", "await_install_permission"):
                stack.enter_context(patch.object(LAB.Phone, name, side_effect=AssertionError("inspection must not call " + name)))
            run = stack.enter_context(patch.object(LAB.subprocess, "run", side_effect=results))
            stack.enter_context(redirect_stdout(output))
            code = LAB.main(["--inspect-state", *extra_args])
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        return code, json.loads(output.getvalue()), run.call_args_list

    def test_inspection_only_queries_fixed_packages_and_normalizes_permission(self):
        path = subprocess.CompletedProcess([], 0, b"package:/synthetic/private/base.apk\n", b"")
        digest = subprocess.CompletedProcess([], 0, b"a" * 64 + b"  /synthetic/private/base.apk\n", b"")
        for mode in ("allow", "ignore", "deny", "default", "foreground", "unset"):
            with self.subTest(mode=mode):
                permission = b"No operations.\n" if mode == "unset" else ("REQUEST_INSTALL_PACKAGES: " + mode + "; time=synthetic-private\n").encode()
                code, result, calls = self.inspection(
                    [path, path, digest, path, path, digest, subprocess.CompletedProcess([], 0, permission, b"")],
                    ["--expected-installer-sha256", "a" * 64],
                )
                self.assertEqual(code, 0)
                self.assertEqual(result["status"], "observed")
                self.assertEqual(result["installer"], {"presence": "present", "hash": "match", "install_permission": mode})
                self.assertEqual(result["alpha"], {"presence": "present", "hash": "read"})
                self.assertEqual(
                    [call.args[0][3:] for call in calls],
                    [
                        ["shell", "pm", "path", LAB.PACKAGE],
                        ["shell", "pm", "path", LAB.PACKAGE],
                        ["shell", "sha256sum", "/synthetic/private/base.apk"],
                        ["shell", "pm", "path", LAB.GAME],
                        ["shell", "pm", "path", LAB.GAME],
                        ["shell", "sha256sum", "/synthetic/private/base.apk"],
                        ["shell", "appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES"],
                    ],
                )
                for private in ("synthetic", "a" * 64, "/", "PASS"):
                    self.assertNotIn(private, json.dumps(result))

    def test_inspection_absence_and_hash_mismatch_do_not_adopt_or_mutate(self):
        absent = subprocess.CompletedProcess([], 1, b"", b"")
        code, result, calls = self.inspection([absent, absent], ["--expected-installer-sha256", "a" * 64])
        self.assertEqual(code, 0)
        self.assertEqual(result["installer"], {"presence": "absent", "hash": "absent", "install_permission": "not-installed"})
        self.assertEqual(result["alpha"], {"presence": "absent", "hash": "absent"})
        self.assertEqual(len(calls), 2)
        path = subprocess.CompletedProcess([], 0, b"package:/synthetic/private/base.apk\n", b"")
        code, result, calls = self.inspection(
            [
                path,
                path,
                subprocess.CompletedProcess([], 0, b"b" * 64 + b"  /synthetic/private/base.apk", b""),
                absent,
                subprocess.CompletedProcess([], 0, b"No operations.", b""),
            ],
            ["--expected-installer-sha256", "a" * 64],
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["installer"]["hash"], "mismatch")
        self.assertEqual(result["status"], "observed")
        self.assertEqual(calls[-1].args[0][-4:], ["appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES"])

    def test_inspection_requires_explicit_device_and_expected_hash_before_queries(self):
        for args, environment in (
            ([], None),
            (["--expected-installer-sha256", "synthetic-private-invalid"], None),
            (["--expected-installer-sha256", "a" * 64], {}),
            (["--expected-installer-sha256", "a" * 64, "--allow-test-installs"], None),
            (["--expected-installer-sha256", "a" * 64, "--allow-test-notifications"], None),
            (["--expected-installer-sha256", "a" * 64, "--host-only"], None),
        ):
            with self.subTest(args=args, environment=environment):
                code, result, calls = self.inspection([], args, environment)
                self.assertEqual(code, 1)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["installer"]["presence"], "unknown")
                self.assertEqual(calls, [])
                self.assertNotIn("synthetic-private", json.dumps(result))

    def test_inspection_query_failure_is_unknown_not_absent_and_redacts_output(self):
        code, result, calls = self.inspection(
            [subprocess.CompletedProcess([], 1, b"synthetic-private-output", b"synthetic-private-error"), subprocess.CompletedProcess([], 1, b"", b"")],
            ["--expected-installer-sha256", "a" * 64],
        )
        self.assertEqual(code, 1)
        self.assertEqual(result["installer"]["presence"], "unknown")
        self.assertEqual(result["alpha"]["presence"], "absent")
        self.assertEqual(result["errors"], ["device-package-path-query"])
        self.assertEqual(len(calls), 2)
        self.assertNotIn("synthetic-private", json.dumps(result))

    def test_missing_explicit_device_emits_all_failures_without_setup(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch.object(LAB, "read_context") as config, redirect_stdout(output):
            self.assertEqual(LAB.main([]), 1)
        config.assert_not_called()
        self.assertEqual(len(output.getvalue().splitlines()), len(LAB.CASES))
        for case in LAB.CASES:
            self.assertIn("FAIL " + case, output.getvalue())
        self.assertNotIn(str(ROOT), output.getvalue())

    def test_missing_toolhost_context_refuses_without_scanning_or_device(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LAB.Failure, "LAB_TOOLHOST_ROOT-required"):
                LAB.read_context()

    def test_acceptance_checks_witness_before_marking_update_and_rollback_pass(self):
        phone = Mock()
        phone.occupied.return_value = False
        phone.ui.return_value = ET.fromstring('<hierarchy><node text="TEST RELEASE SOURCE"/></hierarchy>')
        phone.installed.side_effect = [{"sha256": "first"}, {"sha256": "second"}, {"sha256": "rolled"}]
        phone.read.return_value = {"sha256": "rolled"}
        phone.package_hash.side_effect = lambda package: LAB.sha(b"synthetic test input") if package == LAB.PACKAGE else "rolled"
        phone.wait_state.return_value = {"message": "signature refused"}
        phone.attach_mock(Mock(), "passed")
        releases = {n: {"release.json": LAB.encoded({"version": "synthetic"})} for n in (1, 2)}
        apk = Mock()
        apk.read_bytes.return_value = b"synthetic test input"
        with patch.object(LAB, "prepare_artifacts", return_value=(apk, {}, b"key", releases, releases[2])):
            LAB.acceptance(phone, {}, Path("unused"), phone.passed)
        calls = [(call[0], call.args) for call in phone.mock_calls if call[0] in ("installed", "retention_witness", "passed")]
        self.assertEqual(
            calls[:10],
            [
                ("installed", (1,)),
                ("retention_witness", ("seed",)),
                ("passed", ("check-for-updates",)),
                ("retention_witness", ("verify",)),
                ("installed", (2, {"sha256": "first"})),
                ("retention_witness", ("verify", {"sha256": "second"})),
                ("passed", ("update-N-to-N+1",)),
                ("installed", (1, {"sha256": "second"})),
                ("retention_witness", ("verify", {"sha256": "rolled"})),
                ("passed", ("same-key-rollback",)),
            ],
        )

    def test_prompt_acceptance_requires_settings_and_pending_evidence_before_update_cases(self):
        phone = Mock()
        phone.occupied.return_value = False
        phone.ui.return_value = ET.fromstring('<hierarchy><node text="TEST RELEASE SOURCE"/></hierarchy>')
        phone.installed.side_effect = [{"sha256": "first"}, {"sha256": "second"}, {"sha256": "rolled"}]
        phone.read.return_value = {"sha256": "rolled"}
        phone.package_hash.side_effect = lambda package: LAB.sha(b"synthetic test input") if package == LAB.PACKAGE else "rolled"
        phone.wait_state.return_value = {"message": "signature refused"}
        phone.attach_mock(Mock(), "passed")
        releases = {n: {"release.json": LAB.encoded({"version": "synthetic"})} for n in (1, 2)}
        apk = Mock()
        apk.read_bytes.return_value = b"synthetic test input"
        with patch.object(LAB, "prepare_artifacts", return_value=(apk, {}, b"key", releases, releases[2])):
            LAB.acceptance(phone, {}, Path("unused"), phone.passed, qualify_install_prompts=True)
        phone.await_install_permission.assert_not_called()
        phone.require_ungranted_install_permission.assert_called_once()
        phone.allow_visible_install_permission.assert_called_once()
        first_install = phone.installed.call_args_list[0]
        self.assertEqual(first_install.args, (1,))
        self.assertEqual(first_install.kwargs, {"require_pending_prompt": True})
        events = [(c[0], c.args) for c in phone.mock_calls if c[0] in ("wait_state", "allow_visible_install_permission", "passed", "installed")]
        self.assertEqual(
            events[:5],
            [
                ("wait_state", ({"READY"},)),
                ("allow_visible_install_permission", ()),
                ("passed", ("install-unknown-apps-visible",)),
                ("installed", (1,)),
                ("passed", ("pending-user-action-visible",)),
            ],
        )
        self.assertEqual([c.args[0] for c in phone.passed.call_args_list], [*LAB.PROMPT_CASES, *LAB.CASES])

    def test_generated_witness_java_behavior_with_android_doubles(self):
        # Compile the exact generator output, not a Python reimplementation.
        # These doubles test file behavior, not Android lifecycle/API support.
        java = shutil.which("java")
        if not java:
            self.skipTest("JDK compiler/runtime unavailable")
        compiler = subprocess.run([java, "com.sun.tools.javac.Main", "-version"], capture_output=True, text=True)
        if compiler.returncode:
            self.skipTest("JDK compiler module unavailable")
        files = {"dev/ror2lab/synthetic/RetentionWitness.java": LAB.witness_source()}
        files["android/os/Bundle.java"] = r"""package android.os; public class Bundle {}"""
        files["android/content/Intent.java"] = (
            r"""package android.content; public class Intent { public String mode,nonce; public String getStringExtra(String key) { return key.equals("mode")?mode:nonce; } }"""
        )
        files["android/app/Activity.java"] = (
            r"""package android.app; import java.io.File; public class Activity { public static File external,internal; public static android.content.Intent intent=new android.content.Intent(); public void onCreate(android.os.Bundle b){} public void finish(){} public android.content.Intent getIntent(){return intent;} public File getExternalFilesDir(String kind){return external;} public File getFilesDir(){return internal;} }"""
        )
        files["org/json/JSONObject.java"] = (
            r"""package org.json; public class JSONObject { StringBuilder s=new StringBuilder(); public JSONObject put(String key,Object value){s.append(key).append("=").append(value).append(";");return this;} public String toString(){return s.toString();} }"""
        )
        files["Review.java"] = r"""import java.nio.file.*; import java.io.*; import android.app.Activity; import dev.ror2lab.synthetic.RetentionWitness;
public class Review {
 static Path base; static int cases;
 static void setup(String name)throws Exception { Path p=base.resolve(name);Files.createDirectories(p);Activity.external=p.resolve("external").toFile();Activity.internal=p.resolve("internal").toFile();Activity.external.mkdirs();Activity.internal.mkdirs(); }
 static String run(String mode)throws Exception { Activity.intent.mode=mode;Activity.intent.nonce=String.format("%032x",++cases);new RetentionWitness().onCreate(null);Path r=Activity.internal.toPath().resolve("synthetic-retention-witness.json");return Files.exists(r)?Files.readString(r):""; }
 static void check(boolean ok,String name) { if(!ok)throw new AssertionError(name);System.out.println("PASS "+name); }
 static Path profile(){return Activity.external.toPath().resolve("android-profile-v1/profile.json");}
 public static void main(String[] args)throws Exception {
 base=Paths.get(args[0]);
 setup("ordinary");check(run("seed").contains("verified=true;files=2;"),"seed");byte[] expected=Files.readAllBytes(profile());
 check(run("verify").contains("verified=true;files=2;"),"verify-after-seed");
 check(run("seed").contains("verified=false;files=0;"),"repeated-seed-refused");check(java.util.Arrays.equals(expected,Files.readAllBytes(profile())),"repeated-seed-preserves-bytes");
 byte[] changed=expected.clone();changed[0]^=1;Files.write(profile(),changed);check(run("verify").contains("verified=false;files=0;"),"same-size-changed-data-refused");check(java.util.Arrays.equals(changed,Files.readAllBytes(profile())),"verify-never-reseeds");
 Files.delete(profile());check(run("verify").contains("verified=false;files=0;"),"missing-data-refused");check(!Files.exists(profile()),"missing-data-not-recreated");
 setup("symlink");Path outside=base.resolve("outside");Files.createDirectories(outside);Files.createSymbolicLink(Activity.external.toPath().resolve("android-profile-v1"),outside.toAbsolutePath());check(run("seed").contains("verified=false;files=0;"),"symlink-parent-refused");check(!Files.exists(outside.resolve("profile.json")),"symlink-target-untouched");
 setup("null-root");Activity.external=null;check(run("seed").contains("verified=false;files=0;"),"unavailable-external-root-refused");
 setup("receipt-error");Files.createDirectory(Activity.internal.toPath().resolve("synthetic-retention-witness.tmp"));check(run("seed").isEmpty(),"receipt-write-failure-no-success");
 setup("invalid-mode");check(run("unknown").isEmpty(),"invalid-mode-no-receipt");
 }
}"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, source in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            result = subprocess.run(
                [java, "com.sun.tools.javac.Main", "-source", "8", "-target", "8", "-d", str(root / "classes"), *[str(root / name) for name in files]],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path in (root / "classes").rglob("*.class"):
                self.assertEqual(int.from_bytes(path.read_bytes()[6:8], "big"), 52)
            result = subprocess.run([java, "-cp", str(root / "classes"), "Review", str(root / "data")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(result.stdout.splitlines()), 13)
            self.assertTrue(all(line.startswith("PASS ") for line in result.stdout.splitlines()))

    def test_retention_witness_requires_owned_exact_alpha(self):
        phone = LAB.Phone("synthetic", 1)
        with patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "retention-witness-ownership"):
                phone.retention_witness("seed")
        shell.assert_not_called()

    def test_retention_witness_nonce_matching_and_failure_are_fail_closed(self):
        for verified, count in ((True, 2), (False, 0), (True, 0)):
            with self.subTest(verified=verified, count=count):
                phone = LAB.Phone("synthetic", 1)
                phone.owned_installer, phone.alpha_hash = True, "a" * 64
                rows = iter([None, {"nonce": "old", "verified": True}, {"nonce": "b" * 32, "mode": "verify", "verified": verified, "files": count}])
                events = []

                def shell(*args, label, **kwargs):
                    events.append((args, label))
                    return LAB.encoded(next(rows)) if label == "retention-witness-result" else b""

                with (
                    patch.object(phone, "package_hash", return_value=phone.alpha_hash),
                    patch.object(LAB.secrets, "token_hex", return_value="b" * 32),
                    patch.object(phone, "shell", side_effect=shell),
                    patch.object(phone, "start") as start,
                    patch.object(LAB.time, "sleep"),
                ):
                    if verified and count == 2:
                        phone.retention_witness(
                            "verify",
                            {
                                "profile_retention_verified": True,
                                "retention_backup": {"snapshot": "c" * 64, "data_schema": 1, "bytes": sum(map(len, LAB.WITNESS_FILES.values()))},
                            },
                        )
                        start.assert_called_once()
                    else:
                        with self.assertRaisesRegex(LAB.Failure, "retention-witness-mismatch"):
                            phone.retention_witness("verify")
                        start.assert_not_called()
                self.assertEqual(events[-1], (("am", "force-stop", LAB.GAME), "retention-witness-stop"))
                launches = [args for args, label in events if label == "retention-witness-launch"]
                self.assertEqual(len(launches), 1)
                self.assertIn(LAB.GAME + "/" + LAB.WITNESS_CLASS, launches[0])

    def test_retention_witness_rejects_empty_or_unverified_provider_receipt(self):
        phone = LAB.Phone("synthetic", 1)
        phone.owned_installer, phone.alpha_hash = True, "a" * 64
        for receipt in ({}, {"profile_retention_verified": True, "retention_backup": {"data_schema": 1, "bytes": 0, "snapshot": "c" * 64}}):
            with patch.object(phone, "package_hash", return_value=phone.alpha_hash), patch.object(phone, "shell") as shell:
                with self.assertRaisesRegex(LAB.Failure, "retention-witness-provider-unverified"):
                    phone.retention_witness("verify", receipt)
            shell.assert_not_called()

    def test_witness_fixture_uses_real_retention_roots_and_no_verify_reseed(self):
        source = LAB.witness_source()
        self.assertEqual(set(LAB.WITNESS_FILES), {"android-profile-v1/profile.json", "offline-settings-v1/preferences.json"})
        self.assertIn("getExternalFilesDir(null)", source)
        self.assertIn('if ("seed".equals(mode) && files[i].exists()) throw new IOException()', source)
        self.assertIn('if ("seed".equals(mode)) {', source)
        self.assertIn("if (!files[i].createNewFile()) throw new IOException()", source)
        self.assertIn("if (!Arrays.equals(actual, expected)) throw new IOException()", source)
        self.assertNotIn("com.unity3d", source)
        self.assertNotIn("listFiles", source)

    def test_synthetic_manifest_uses_aapt1_required_basename(self):
        # Only source XML is created: no toolchain invocation, APK or key.
        with tempfile.TemporaryDirectory() as temporary:
            manifest = LAB.synthetic_manifest(Path(temporary))
            self.assertEqual(manifest.name, "AndroidManifest.xml")
            root = ET.parse(manifest).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        self.assertEqual(root.get("package"), LAB.GAME)
        self.assertEqual(root.find("application").get(android + "debuggable"), "true")
        self.assertEqual(root.find("application/activity").get(android + "name"), "com.unity3d.player.UnityPlayerActivity")

    def test_http_assets_metadata_and_request_observation(self):
        files = {"release.json": b'{"version":"synthetic"}', "release.sig": b"authored signature substitute", "public-tools.zip": b"not an APK"}
        with LAB.server() as service:
            base = LAB.publish(service, files, 2)
            with urllib.request.urlopen(base + "latest.json") as response:
                metadata = json.load(response)
            self.assertEqual(metadata["tag_name"], "owner-v2")
            self.assertEqual({row["name"] for row in metadata["assets"]}, set(files))
            self.assertNotIn("/public-tools.zip", service.requests)
            for row in metadata["assets"]:
                self.assertEqual(row["browser_download_url"], base + row["name"])
                self.assertEqual(row["size"], len(files[row["name"]]))
            LAB.publish(service, files, 1)
            self.assertEqual(service.requests, [])

    def test_pm_path_empty_success_or_exit_one_is_absence(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        for code in (0, 1):
            with self.subTest(code=code), patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], code, b"", b"")) as run:
                self.assertFalse(phone.occupied(LAB.GAME))
                self.assertEqual(run.call_args.args[0][-4:], ["shell", "pm", "path", LAB.GAME])
                with patch.object(phone, "shell") as shell:
                    with self.assertRaisesRegex(LAB.Failure, "installed-package-shape"):
                        phone.package_hash(LAB.GAME)
                shell.assert_not_called()

    def test_pm_path_present_package_still_requires_exact_hash_readback(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        result = subprocess.CompletedProcess([], 0, b"package:/synthetic/app/base.apk\n", b"")
        with (
            patch.object(LAB.subprocess, "run", return_value=result),
            patch.object(phone, "shell", return_value=b"a" * 64 + b"  /synthetic/app/base.apk\n") as shell,
        ):
            self.assertTrue(phone.occupied(LAB.GAME))
            self.assertEqual(phone.package_hash(LAB.GAME), "a" * 64)
        shell.assert_called_once_with("sha256sum", "/synthetic/app/base.apk", label="device-package-hash")

    def test_pm_path_other_errors_never_count_as_absence_or_print_raw_error(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        for code, stdout, stderr in (
            (1, b"", b"synthetic-private-error"),
            (1, b"synthetic-private-error", b""),
            (1, b"package:/synthetic/app/base.apk\n", b""),
            (0, b"", b"synthetic-private-error"),
            (2, b"", b""),
            (0, b"synthetic-private-error", b""),
        ):
            with (
                self.subTest(code=code, stdout=stdout, stderr=stderr),
                patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], code, stdout, stderr)),
            ):
                with self.assertRaises(LAB.Failure) as failure:
                    phone.occupied(LAB.GAME)
                self.assertIn(str(failure.exception), {"device-package-path-query", "device-package-path-shape"})
                self.assertNotIn("synthetic-private-error", str(failure.exception))

    def test_no_permission_setting_without_explicit_flag_and_fresh_ownership(self):
        for authorized, owned in ((False, True), (True, False), (False, False)):
            phone = LAB.Phone("synthetic-private-selector", 1, authorized)
            phone.owned_installer = owned
            with patch.object(phone, "shell", return_value=b"No operations.") as shell:
                with self.assertRaisesRegex(LAB.Failure, "owner-authorization-required"):
                    phone.await_install_permission()
                shell.assert_called_once_with("appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES", label="device-install-permission-query")

    def test_permission_flag_is_scoped_to_fresh_test_package(self):
        phone = LAB.Phone("synthetic-private-selector", 1, True)
        phone.owned_installer = True
        with patch.object(phone, "shell", return_value=b"No operations.") as shell:
            phone.await_install_permission()
        self.assertEqual(shell.call_args.args, ("appops", "set", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES", "allow"))

    @staticmethod
    def notification_dialog(message="Allow Owner game installer to send you notifications?", button="permission_deny_button"):
        tree = ET.Element("hierarchy")
        controller = "com.android.permissioncontroller"
        ET.SubElement(tree, "node", {"package": controller, "resource-id": controller + ":id/permission_message", "text": message})
        ET.SubElement(
            tree,
            "node",
            {"package": controller, "resource-id": controller + ":id/" + button, "text": "Don’t allow", "enabled": "true", "bounds": "[20,40][100,80]"},
        )
        return tree

    def test_null_root_dump_retries_before_reading_and_cleans_successful_dump(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        xml = b'<?xml version="1.0"?><hierarchy><node text="synthetic"/></hierarchy>'
        success = subprocess.CompletedProcess([], 0, b"UI hierchary dumped to: /synthetic/private/ui.xml", b"")
        for stdout, stderr in ((b"", b"ERROR: null root node returned by UiTestAutomationBridge."), (b"ERROR: null root node", b"")):
            with self.subTest(stdout=stdout, stderr=stderr):
                events = []

                def execute(*args, **kwargs):
                    events.append("dump")
                    return subprocess.CompletedProcess([], 0, stdout, stderr) if events.count("dump") == 1 else success

                def shell(*args, **kwargs):
                    events.append(args[0])
                    return xml if args[0] == "cat" else b""

                with (
                    patch.object(phone, "detached", side_effect=execute) as dump,
                    patch.object(phone, "shell", side_effect=shell) as command,
                    patch.object(LAB.time, "sleep", side_effect=lambda seconds: events.append("wait")),
                ):
                    self.assertEqual(phone.ui().tag, "hierarchy")
                self.assertEqual(events, ["dump", "wait", "dump", "cat", "rm"])
                self.assertEqual(dump.call_count, 2)
                self.assertEqual(command.call_args_list[-1].args, ("rm", "-f", phone.ui_path))
                self.assertTrue(all(call.kwargs == {"label": "device-ui-dump", "timeout": 30} for call in dump.call_args_list))

    def test_null_root_dump_retry_limit_never_reads_nonexistent_file(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        result = subprocess.CompletedProcess([], 0, b"", b"ERROR: null root node synthetic-private-detail")
        with (
            patch.object(phone, "detached", return_value=result) as dump,
            patch.object(phone, "shell") as shell,
            patch.object(LAB.time, "sleep") as sleep,
            patch.object(phone, "ui_windows", side_effect=LAB.Failure("device-ui-null-root-retry-exhausted")) as fallback,
        ):
            with self.assertRaisesRegex(LAB.Failure, "^device-ui-null-root-retry-exhausted$"):
                phone.ui()
        self.assertEqual(dump.call_count, 3)
        self.assertEqual([call.args for call in sleep.call_args_list], [(1,), (1,)])
        shell.assert_not_called()
        fallback.assert_called_once_with((LAB.PACKAGE,))

    def test_idle_timeout_never_reads_or_retries_a_missing_dump(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        for stdout, stderr in ((b"", b"ERROR: could not get idle state."), (b"ERROR: could not get idle state.", b"")):
            with (
                self.subTest(stdout=stdout),
                patch.object(phone, "detached", return_value=subprocess.CompletedProcess([], 0, stdout, stderr)) as dump,
                patch.object(phone, "shell") as shell,
                patch.object(phone, "ui_windows") as fallback,
                patch.object(LAB.time, "sleep") as sleep,
            ):
                with self.assertRaisesRegex(LAB.Failure, "^device-ui-idle-timeout$"):
                    phone.ui()
            dump.assert_called_once()
            shell.assert_not_called()
            fallback.assert_not_called()
            sleep.assert_not_called()

    def test_ui_dump_retry_does_not_retry_nonzero_or_unrelated_read_failure(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        result = subprocess.CompletedProcess([], 1, b"", b"ERROR: null root node synthetic-private-detail")
        with patch.object(phone, "detached", return_value=result) as dump, patch.object(phone, "shell") as shell, patch.object(LAB.time, "sleep") as sleep:
            with self.assertRaisesRegex(LAB.Failure, "^device-ui-dump$"):
                phone.ui()
        dump.assert_called_once()
        shell.assert_not_called()
        sleep.assert_not_called()
        with (
            patch.object(phone, "detached", return_value=subprocess.CompletedProcess([], 0, b"UI hierarchy dumped to: /synthetic/private", b"")) as dump,
            patch.object(phone, "shell", side_effect=[LAB.Failure("device-ui-read"), b""]) as shell,
            patch.object(LAB.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(LAB.Failure, "^device-ui-read$"):
                phone.ui()
        dump.assert_called_once()
        self.assertEqual([call.args[0] for call in shell.call_args_list], ["cat", "rm"])
        sleep.assert_not_called()

    def test_notification_dialog_denied_by_scoped_resource_id_not_button_text(self):
        manifest = ET.parse(ROOT / "tools/phone-build/managed-host/AndroidManifest.xml").getroot()
        self.assertEqual(manifest.find("application").get("{http://schemas.android.com/apk/res/android}label"), "Owner game installer")
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        with patch.object(phone, "ui_for", side_effect=[self.notification_dialog(), ET.Element("hierarchy")]), patch.object(phone, "shell") as shell:
            self.assertTrue(phone.dismiss_notification_permission())
        shell.assert_called_once_with("input", "tap", "60", "60", label="device-notification-deny")
        with patch.object(phone, "shell") as shell, patch.object(LAB.time, "sleep"), patch.object(phone, "dismiss_notification_permission") as dismiss:
            phone.start()
            phone.start()
        self.assertEqual(dismiss.call_count, 2)
        self.assertEqual(shell.call_args_list[0].args, ("input", "keyevent", "KEYCODE_WAKEUP"))
        self.assertEqual(shell.call_args_list[2].args, ("am", "start", "-W", "-n", LAB.ACTIVITY))

    @staticmethod
    def window_document(package=None):
        document = ET.Element("displays")
        display = ET.SubElement(document, "display", {"id": "0"})
        window = ET.SubElement(display, "window", {"active": "true", "focused": "true", "title": "synthetic-private-title"})
        hierarchy = ET.SubElement(window, "hierarchy", {"rotation": "0"})
        ET.SubElement(hierarchy, "node", {"package": package or LAB.PACKAGE, "text": "synthetic-private-text"})
        return document

    def test_window_fallback_recovers_only_unique_foreground_direct_hierarchy(self):
        document = self.window_document()
        other = ET.SubElement(document, "display", {"id": "2"})
        ET.SubElement(other, "window", {"active": "true", "focused": "true"})
        background = ET.SubElement(document.find("display"), "window", {"active": "false", "focused": "false"})
        ET.SubElement(ET.SubElement(background, "hierarchy"), "node", {"package": "synthetic.other"})
        selected = LAB.focused_ui_hierarchy(document, (LAB.PACKAGE,))
        self.assertIs(selected, document.find("display/window/hierarchy"))
        self.assertEqual(len(list(selected.iter("node"))), 1)

    def test_retained_window_summary_exports_only_fixed_categories_and_mixed_package_fact(self):
        for package, category in (
            (LAB.PACKAGE, "test-installer"),
            ("com.android.permissioncontroller", "permission-controller"),
            ("com.android.systemui", "system-ui"),
            ("android", "android-system"),
            ("com.android.packageinstaller", "package-installer"),
            ("com.google.android.packageinstaller", "package-installer"),
            ("synthetic.private.foreground", "other"),
        ):
            with self.subTest(category=category):
                document = self.window_document(package)
                result = LAB.ui_window_summary(ET.tostring(document, xml_declaration=True))
                self.assertEqual(result, {"status": "observed", "package_category": category, "mixed_node_packages": False})
                ET.SubElement(document.find("display/window/hierarchy/node"), "node", {"package": "synthetic.private.child"})
                result = LAB.ui_window_summary(ET.tostring(document, xml_declaration=True))
                self.assertTrue(result["mixed_node_packages"])
                self.assertNotIn("synthetic", json.dumps(result))
                # Classification never authorizes a foreign or mixed tap root.
                with self.assertRaises(LAB.Failure):
                    LAB.focused_ui_hierarchy(document, (LAB.PACKAGE, "com.android.permissioncontroller"))

    def test_retained_window_summary_keeps_ambiguous_or_malformed_focus_unknown(self):
        document = self.window_document()
        ET.SubElement(document.find("display"), "window", {"active": "true", "focused": "false"})
        result = LAB.ui_window_summary(ET.tostring(document, xml_declaration=True))
        self.assertEqual(result, {"status": "unknown", "reason": "ui-window-focus-ambiguous"})
        for data in (b"synthetic-private", b"<?xml invalid?></displays>", b"<?xml version='1.0'?><hierarchy></hierarchy>"):
            self.assertEqual(LAB.ui_window_summary(data), {"status": "unknown", "reason": "ui-window-schema"})

    def test_private_ui_log_summary_classifies_successfully_read_rejected_window_without_device_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "work/coordination/installer-update-acceptance/run-newest00"
            directory.mkdir(parents=True)
            document = self.window_document("com.android.systemui")
            for sequence, category, stdout in (
                (1, "device-ui-dump", b"ERROR: null root node returned\n"),
                (2, "device-ui-windows-dump", b"UI hierarchy dumped to: /synthetic/private/ui.xml\n"),
                (3, "device-ui-read", ET.tostring(document, xml_declaration=True)),
                (4, "device-ui-remove", b""),
                (5, "device-ui-diagnostic-power", b"synthetic-private-output-not-exported"),
            ):
                prefix = f"{sequence:05d}-{category}"
                (directory / (prefix + ".json")).write_bytes(
                    LAB.encoded({"phase": "baseline-N-check", "category": category, "returncode": 0, "outcome": "returned"})
                )
                (directory / (prefix + ".stdout.log")).write_bytes(stdout)
                (directory / (prefix + ".stderr.log")).write_bytes(b"")
            marker = directory / "00005-device-ui-diagnostic-power.json"
            marker_bytes = marker.read_bytes()
            marker.unlink()
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 1)
            self.assertNotIn("foreground", result)
            marker.write_bytes(marker_bytes)
            before = {path: path.read_bytes() for path in directory.iterdir()}
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 0)
            self.assertEqual([record["category"] for record in result["records"]], ["device-ui-windows-dump", "device-ui-read"])
            self.assertEqual(result["foreground"], {"status": "observed", "package_category": "system-ui", "mixed_node_packages": False})
            self.assertEqual(before, {path: path.read_bytes() for path in directory.iterdir()})
            for private in ("synthetic", "ui.xml", "run-newest00", "com.android.systemui"):
                self.assertNotIn(private, json.dumps(result))
            record = directory / "00003-device-ui-read.stdout.log"
            record.unlink()
            record.symlink_to(root / "unrelated-not-read")
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 1)
            self.assertEqual(result["errors"], ["log-inspection-record-unavailable"])
            self.assertNotIn("foreground", result)

    def test_window_fallback_refuses_missing_ambiguous_background_or_foreign_roots(self):
        cases = []
        wrong_schema = ET.Element("hierarchy")
        cases.append(wrong_schema)
        for attribute in ("active", "focused"):
            document = self.window_document()
            document.find("display/window").set(attribute, "false")
            cases.append(document)
        document = self.window_document()
        ET.SubElement(document.find("display"), "window", {"active": "true", "focused": "false"})
        cases.append(document)
        document = self.window_document()
        document.find("display").set("id", "2")
        cases.append(document)
        document = self.window_document()
        window = document.find("display/window")
        hierarchy = window.find("hierarchy")
        window.remove(hierarchy)
        ET.SubElement(window, "window", {"active": "false", "focused": "false"}).append(hierarchy)
        cases.append(document)
        cases.append(self.window_document("synthetic.other"))
        document = self.window_document()
        ET.SubElement(document.find("display/window/hierarchy/node"), "node", {"package": "synthetic.other"})
        cases.append(document)
        for document in cases:
            with self.subTest(xml=ET.tostring(document)):
                with self.assertRaises(LAB.Failure):
                    LAB.focused_ui_hierarchy(document, (LAB.PACKAGE,))

    def test_window_dump_runs_once_only_after_null_root_and_removes_local_xml(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        null = subprocess.CompletedProcess([], 0, b"", b"ERROR: null root node")
        success = subprocess.CompletedProcess([], 0, b"UI hierchary dumped to: synthetic-private", b"")
        xml = ET.tostring(self.window_document(), encoding="utf-8", xml_declaration=True)
        output = io.StringIO()
        with (
            patch.object(phone, "detached", side_effect=[null, null, null, success]) as dump,
            patch.object(phone, "shell", side_effect=[xml, b""]) as shell,
            patch.object(LAB.time, "sleep"),
            patch.object(phone, "ui_diagnostics") as diagnostics,
            redirect_stdout(output),
        ):
            self.assertEqual(phone.ui().tag, "hierarchy")
        self.assertEqual(dump.call_count, 4)
        self.assertEqual(dump.call_args.args[0][-4:], ["uiautomator", "dump", "--windows", phone.ui_path])
        self.assertEqual([call.args[0] for call in shell.call_args_list], ["cat", "rm"])
        diagnostics.assert_not_called()
        self.assertEqual(output.getvalue(), "INFO ui-null-root-recovered source=focused-window\n")

    def test_window_dump_missing_file_or_unsupported_schema_never_means_success(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        for result, document, reason in (
            (subprocess.CompletedProcess([], 0, b"", b"ERROR: null root node"), None, "ui-window-dump-unavailable"),
            (subprocess.CompletedProcess([], 0, b"UI hierarchy dumped to: synthetic-private", b""), LAB.Failure("device-ui-read"), "device-ui-read"),
            (subprocess.CompletedProcess([], 0, b"UI hierarchy dumped to: synthetic-private", b""), ET.Element("hierarchy"), "ui-window-schema"),
        ):
            with (
                self.subTest(reason=reason),
                patch.object(phone, "detached", return_value=result) as dump,
                patch.object(phone, "read_ui_dump", side_effect=document if isinstance(document, Exception) else None, return_value=document) as read,
                patch.object(phone, "ui_diagnostics") as diagnostics,
            ):
                with self.assertRaisesRegex(LAB.Failure, "^device-ui-null-root-retry-exhausted$"):
                    phone.ui_windows((LAB.PACKAGE,))
            dump.assert_called_once()
            diagnostics.assert_called_once_with(reason)
            if document is None:
                read.assert_not_called()

    def test_ui_interaction_wakes_before_read_without_relaunching_consent(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        events = []
        tree = ET.fromstring('<hierarchy><node text="Install" enabled="true" bounds="[0,0][20,20]" /></hierarchy>')
        with (
            patch.object(phone, "shell", side_effect=lambda *args, **kwargs: events.append(args)),
            patch.object(phone, "ui_for", side_effect=lambda packages: events.append(("read", packages)) or tree),
        ):
            for _ in range(2):
                self.assertTrue(phone.tap_visible("Install"))
        self.assertEqual(
            events,
            [
                ("input", "keyevent", "KEYCODE_WAKEUP"),
                ("read", (LAB.PACKAGE, "com.android.packageinstaller", "com.google.android.packageinstaller")),
                ("input", "tap", "10", "10"),
            ]
            * 2,
        )

    def test_wake_failure_does_not_read_or_tap_ui(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        with patch.object(phone, "shell", side_effect=LAB.Failure("device-display-wake")) as shell, patch.object(phone, "ui_for") as read:
            with self.assertRaisesRegex(LAB.Failure, "^device-display-wake$"):
                phone.tap_visible("Install")
        shell.assert_called_once_with("input", "keyevent", "KEYCODE_WAKEUP", label="device-display-wake")
        read.assert_not_called()

    def test_install_consent_window_packages_are_scoped_to_install_action(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        with patch.object(phone, "shell") as shell, patch.object(phone, "ui_for", return_value=ET.Element("hierarchy")) as read:
            self.assertFalse(phone.tap_visible("Install"))
            self.assertEqual(read.call_args.args, ((LAB.PACKAGE, "com.android.packageinstaller", "com.google.android.packageinstaller"),))
            self.assertFalse(phone.tap_visible("Check for updates"))
            self.assertEqual(read.call_args.args, ((LAB.PACKAGE,),))
            self.assertEqual([call.args for call in shell.call_args_list], [("input", "keyevent", "KEYCODE_WAKEUP")] * 2)
        for package in ("com.android.permissioncontroller", "com.android.packageinstaller", "com.google.android.packageinstaller"):
            with self.subTest(package=package):
                with self.assertRaises(LAB.Failure):
                    LAB.focused_ui_hierarchy(self.window_document(package), (LAB.PACKAGE,))
                self.assertEqual(LAB.focused_ui_hierarchy(self.window_document(package), (LAB.PACKAGE, package)).find("node").get("package"), package)

    def test_null_root_environment_diagnostics_are_read_only_fixed_boolean_or_unknown(self):
        outputs = {
            "power": "mWakefulness=Awake\nsynthetic-private",
            "window": "mCurrentFocus=Window{private u17 com.android.permissioncontroller/.permission.ui.GrantPermissionsActivity}\nKeyguardServiceDelegate\n  showing=true\n  showingAndNotOccluded=false\n  inputRestricted=true\n  Window #1 Window{private u17 "
            + LAB.ACTIVITY
            + "}\n    isOnScreen=true\n",
            "activity": "ACTIVITY MANAGER ACTIVITIES\nActivityRecord{private u17 "
            + LAB.ACTIVITY
            + " t123}\nResumedActivity: ActivityRecord{private u17 com.android.permissioncontroller/.permission.ui.GrantPermissionsActivity}\n",
            "accessibility": "ACCESSIBILITY MANAGER\ncurrentUserId=17\nsynthetic-private",
            "instrumentation": "ACTIVITY MANAGER RUNNING PROCESSES\nsynthetic-private",
            "user": "17\n",
        }
        result = LAB.ui_environment_summary(outputs)
        for key in (
            "display_awake",
            "keyguard_showing",
            "keyguard_input_restricted",
            "test_activity_present",
            "test_window_on_screen",
            "permission_window_focused",
            "test_activity_current_user",
            "accessibility_current_user",
        ):
            self.assertTrue(result[key], key)
        for key in (
            "keyguard_showing_not_occluded",
            "test_activity_resumed",
            "test_window_focused",
            "ui_automation_registered_after_dump",
            "instrumentation_running_after_dump",
        ):
            self.assertFalse(result[key], key)
        self.assertTrue(all(value is None or type(value) is bool for value in result.values()))
        phone = LAB.Phone("synthetic-private-selector", 1)
        output = io.StringIO()
        with patch.object(phone, "shell", side_effect=[value.encode() for value in outputs.values()]) as shell, redirect_stdout(output):
            phone.ui_diagnostics("ui-window-dump-unavailable")
        self.assertEqual(
            [call.args for call in shell.call_args_list],
            [
                ("dumpsys", "power"),
                ("dumpsys", "window"),
                ("dumpsys", "activity", "activities"),
                ("dumpsys", "accessibility"),
                ("dumpsys", "activity", "processes"),
                ("am", "get-current-user"),
            ],
        )
        self.assertEqual(json.loads(output.getvalue())["observed"], result)
        for private in ("synthetic-private", "17", LAB.PACKAGE, "GrantPermissionsActivity", "t123"):
            self.assertNotIn(private, output.getvalue())
        with patch.object(phone, "shell", side_effect=LAB.Failure("device-ui-diagnostic-power")), redirect_stdout(io.StringIO()):
            phone.ui_diagnostics("ui-window-dump-unavailable")
        unknown = LAB.ui_environment_summary({})
        self.assertTrue(all(value is False if key.endswith("_query_ok") else value is None for key, value in unknown.items()))

    def test_notification_opt_in_selects_allow_resource_id_not_button_text(self):
        phone = LAB.Phone("synthetic-private-selector", 1, allow_test_notifications=True)
        phone.owned_installer = True
        dialog = self.notification_dialog(button="permission_allow_button")
        deny = self.notification_dialog().findall("node")[-1]
        deny.set("bounds", "[200,400][300,480]")
        dialog.append(deny)
        with patch.object(phone, "ui_for", side_effect=[dialog, ET.Element("hierarchy")]) as ui, patch.object(phone, "shell") as shell:
            self.assertTrue(phone.dismiss_notification_permission())
        shell.assert_called_once_with("input", "tap", "60", "60", label="device-notification-allow")
        self.assertEqual([call.args for call in ui.call_args_list], [((LAB.PACKAGE, "com.android.permissioncontroller"),)] * 2)

    def test_notification_opt_in_rejects_unidentified_or_unavailable_allow_button(self):
        phone = LAB.Phone("synthetic-private-selector", 1, allow_test_notifications=True)
        phone.owned_installer = True
        for message, changes, duplicate, reason in (
            ("Allow another app to send you notifications?", {}, False, "notification-dialog-not-identified"),
            ("Allow Owner game installer to access your camera?", {}, False, "notification-dialog-not-identified"),
            (None, {"enabled": "false"}, False, "notification-allow-unavailable"),
            (None, {"package": "another.app"}, False, "notification-allow-unavailable"),
            (None, {"resource-id": "com.android.permissioncontroller:id/permission_deny_button"}, False, "notification-allow-unavailable"),
            (None, {}, True, "notification-allow-unavailable"),
            (None, {"bounds": "invalid"}, False, "ui-button-bounds"),
        ):
            dialog = self.notification_dialog(button="permission_allow_button")
            if message is not None:
                dialog.findall("node")[0].set("text", message)
            button = dialog.findall("node")[-1]
            button.attrib.update(changes)
            if duplicate:
                dialog.append(ET.fromstring(ET.tostring(button)))
            with self.subTest(reason=reason, changes=changes), patch.object(phone, "ui_for", return_value=dialog), patch.object(phone, "shell") as shell:
                with self.assertRaisesRegex(LAB.Failure, reason):
                    phone.dismiss_notification_permission()
                shell.assert_not_called()

    def test_notification_opt_in_cli_reaches_phone_without_enabling_installs(self):
        with (
            patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "synthetic-private-selector"}),
            patch.object(LAB, "PrivateDiagnostics"),
            patch.object(LAB, "read_context", return_value={}),
            patch.object(LAB, "Phone") as phone,
            patch.object(LAB, "acceptance"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(LAB.main(["--allow-test-notifications"]), 0)
        phone.assert_called_once_with("synthetic-private-selector", 1200, False, True)

    def test_notification_dialog_does_not_act_without_prompt_or_fresh_ownership(self):
        for allow in (False, True):
            phone = LAB.Phone("synthetic-private-selector", 1, allow_test_notifications=allow)
            with self.subTest(allow=allow), patch.object(phone, "ui_for") as ui, patch.object(phone, "shell") as shell:
                with self.assertRaisesRegex(LAB.Failure, "notification-dialog-installer-not-owned"):
                    phone.dismiss_notification_permission()
                ui.assert_not_called()
                shell.assert_not_called()
            phone.owned_installer = True
            with patch.object(phone, "ui_for", return_value=ET.Element("hierarchy")), patch.object(phone, "shell") as shell:
                self.assertFalse(phone.dismiss_notification_permission())
                shell.assert_not_called()

    def test_notification_dialog_rejects_other_apps_permissions_and_allow_button(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        for dialog, reason in (
            (self.notification_dialog("Allow another app to send you notifications?"), "notification-dialog-not-identified"),
            (self.notification_dialog("Allow Owner game installer to access your camera?"), "notification-dialog-not-identified"),
            (self.notification_dialog(button="permission_allow_button"), "notification-denial-unavailable"),
        ):
            with self.subTest(reason=reason), patch.object(phone, "ui_for", return_value=dialog), patch.object(phone, "shell") as shell:
                with self.assertRaisesRegex(LAB.Failure, reason):
                    phone.dismiss_notification_permission()
                shell.assert_not_called()

    def test_notification_dialog_requires_observed_dismissal(self):
        for allow in (False, True):
            phone = LAB.Phone("synthetic-private-selector", 1, allow_test_notifications=allow)
            phone.owned_installer = True
            dialog = self.notification_dialog(button="permission_allow_button" if allow else "permission_deny_button")
            with self.subTest(allow=allow), patch.object(phone, "ui_for", return_value=dialog), patch.object(phone, "shell") as shell:
                with self.assertRaisesRegex(LAB.Failure, "notification-dialog-not-dismissed"):
                    phone.dismiss_notification_permission()
            self.assertEqual(shell.call_count, 1)

    @classmethod
    def focused_notification_dialog(cls, **kwargs):
        tree = ET.Element("hierarchy")
        root = ET.SubElement(tree, "node", {"package": "com.android.permissioncontroller"})
        for node in cls.notification_dialog(**kwargs):
            root.append(node)
        root[-1].set("clickable", "true")
        return tree

    def test_repeat_notification_denial_is_explicit_user_fixed_after_observed_first_denial(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer, phone.installer_hash = True, "a" * 64
        dialog = self.focused_notification_dialog(button="permission_deny_and_dont_ask_again_button")
        app = ET.Element("hierarchy")
        ET.SubElement(app, "node", {"package": LAB.PACKAGE})
        output = io.StringIO()
        with (
            patch.object(phone, "package_hash", return_value=phone.installer_hash) as owned,
            patch.object(phone, "ui_for", side_effect=[self.notification_dialog(), ET.Element("hierarchy")]) as ordinary,
            patch.object(phone, "ui_windows", side_effect=[dialog, dialog, app]) as focused,
            patch.object(phone, "shell") as shell,
            redirect_stdout(output),
        ):
            self.assertTrue(phone.dismiss_notification_permission())
            self.assertTrue(phone.notification_denied)
            self.assertTrue(phone.dismiss_notification_permission(repeat_denial=True))
        self.assertEqual([c.kwargs["label"] for c in shell.call_args_list], ["device-notification-deny", "device-notification-deny-and-dont-ask-again"])
        self.assertEqual(ordinary.call_count, 2)
        self.assertEqual(owned.call_count, 2)
        self.assertEqual(
            [c.args for c in focused.call_args_list],
            [
                ((LAB.PACKAGE, "com.android.permissioncontroller"),),
                (("com.android.permissioncontroller",),),
                ((LAB.PACKAGE, "com.android.permissioncontroller"),),
            ],
        )
        self.assertTrue(all(c.kwargs == {"recovery": False} for c in focused.call_args_list))
        self.assertIn("effect=user-fixed scope=owned-disposable-installer", output.getvalue())

    def test_repeat_notification_control_is_not_an_ordinary_denial_or_grant_alias(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer, phone.notification_denied = True, True
        dialog = self.notification_dialog(button="permission_deny_and_dont_ask_again_button")
        with patch.object(phone, "ui_for", return_value=dialog), patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "notification-denial-unavailable"):
                phone.dismiss_notification_permission()
            shell.assert_not_called()
        phone.allow_test_notifications = True
        with patch.object(phone, "ui_windows") as ui, patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "notification-repeat-denial-conflicting-policy"):
                phone.dismiss_notification_permission(repeat_denial=True)
            ui.assert_not_called()
            shell.assert_not_called()

    def test_repeat_notification_denial_rejects_changed_ambiguous_or_unowned_prompt_without_tap(self):
        for mode in (
            "no-prior-denial",
            "disabled",
            "not-clickable",
            "duplicate",
            "both-negative",
            "misspelled",
            "wrong-purpose",
            "foreign",
            "zero-bounds",
            "changed-focus",
            "changed-apk",
        ):
            phone = LAB.Phone("synthetic-private-selector", 1)
            phone.owned_installer, phone.installer_hash, phone.notification_denied = True, "a" * 64, mode != "no-prior-denial"
            dialog = self.focused_notification_dialog(button="permission_deny_and_dont_ask_again_button")
            button = dialog.find("node")[-1]
            if mode == "disabled":
                button.set("enabled", "false")
            if mode == "not-clickable":
                button.set("clickable", "false")
            if mode in ("duplicate", "both-negative"):
                other = ET.fromstring(ET.tostring(button))
                if mode == "both-negative":
                    other.set("resource-id", "com.android.permissioncontroller:id/permission_deny_button")
                dialog.find("node").append(other)
            if mode == "misspelled":
                button.set("resource-id", "com.android.permissioncontroller:id/permission_deny_dont_ask_again_button")
            if mode == "wrong-purpose":
                dialog.find("node")[0].set("text", "Allow Owner game installer to access camera?")
            if mode == "foreign":
                button.set("package", "foreign")
            if mode == "zero-bounds":
                button.set("bounds", "[10,10][10,10]")
            confirm = ET.fromstring(ET.tostring(dialog))
            if mode == "changed-focus":
                confirm.find("node")[-1].set("bounds", "[50,60][100,120]")
            with (
                self.subTest(mode=mode),
                patch.object(phone, "package_hash", return_value="b" * 64 if mode == "changed-apk" else phone.installer_hash),
                patch.object(phone, "ui_windows", side_effect=[dialog, confirm]),
                patch.object(phone, "shell") as shell,
                self.assertRaises(LAB.Failure),
            ):
                try:
                    phone.dismiss_notification_permission(repeat_denial=True)
                finally:
                    shell.assert_not_called()

    def test_repeat_notification_denial_requires_observed_dismissal(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer, phone.installer_hash, phone.notification_denied = True, "a" * 64, True
        dialog = self.focused_notification_dialog(button="permission_deny_and_dont_ask_again_button")
        with (
            patch.object(phone, "package_hash", return_value=phone.installer_hash),
            patch.object(phone, "ui_windows", return_value=dialog),
            patch.object(phone, "shell") as shell,
        ):
            with self.assertRaisesRegex(LAB.Failure, "notification-dialog-not-dismissed"):
                phone.dismiss_notification_permission(repeat_denial=True)
            self.assertEqual(shell.call_count, 1)

    def test_occupied_alpha_refuses_before_build_and_key_creation(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        with (
            patch.object(LAB, "HostTools"),
            patch.object(phone, "occupied", return_value=True),
            patch.object(LAB, "prepare_artifacts") as build,
            patch.object(LAB, "publisher_keys") as keys,
        ):
            with self.assertRaisesRegex(LAB.Failure, "occupied-package"):
                LAB.acceptance(phone, {}, Path("/unused"), lambda case: None)
        build.assert_not_called()
        keys.assert_not_called()

    def test_apk_log_capture_is_owned_bounded_and_rejects_symlinks(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.installer_hash = "a" * 64
        with patch.object(phone, "package_hash", return_value="b" * 64), patch.object(phone, "shell") as shell:
            for owned in (False, True):
                phone.owned_installer = owned
                with self.assertRaisesRegex(LAB.Failure, "apk-log-installer-not-owned"):
                    phone.capture_apk_logs()
            shell.assert_not_called()
        with patch.object(phone, "package_hash", return_value=phone.installer_hash), patch.object(phone, "shell") as shell:
            phone.capture_apk_logs()
        self.assertEqual([call.kwargs["label"] for call in shell.call_args_list], ["device-apk-javac-log", "device-apk-dex-log"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            releases = root / "files/owner-input/work/releases"
            for index in range(6):
                assembly = releases / f"build-{index}" / "assembly"
                assembly.mkdir(parents=True)
                (assembly / "javac.log").write_bytes(b"x" * 70000)
                (assembly / "dex.log").symlink_to(root / "private-log")
            (root / "private-log").write_text("synthetic-private")
            for call in shell.call_args_list:
                self.assertEqual(call.args[:4], ("run-as", LAB.PACKAGE, "sh", "-c"))
                self.assertEqual(call.kwargs["timeout"], 15)
                script = call.args[4][1:-1]
                output = subprocess.run(["sh", "-c", script], cwd=root, capture_output=True, check=True).stdout
                if call.kwargs["label"] == "device-apk-javac-log":
                    self.assertEqual(output, (b"ROR2_APK_LOG_BEGIN\n" + b"x" * 65536 + b"\n") * 4)
                else:
                    self.assertEqual(output, b"")
                self.assertNotIn(b"synthetic-private", output)

    def test_apk_log_capture_failure_keeps_original_install_failure(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        state = {"state": "ERROR", "pipeline": {"first_failure": {"stage": "apk"}}}
        with (
            patch.object(LAB, "CURRENT_PHASE", "baseline-N-install"),
            patch.object(phone, "read", side_effect=[None, state]),
            patch.object(phone, "capture_apk_logs", side_effect=OSError("synthetic-private")) as capture,
        ):
            with self.assertRaisesRegex(LAB.Failure, "^installer-build-error$"):
                phone.installed(1)
            capture.assert_called_once_with()

    def test_unowned_cleanup_never_uninstalls_or_reads_app_data(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        with patch.object(phone, "command") as command, patch.object(phone, "shell") as shell, patch.object(phone, "read") as read:
            phone.cleanup()
        command.assert_not_called()
        read.assert_not_called()
        shell.assert_called_once_with("input", "keyevent", "KEYCODE_SLEEP", label="device-display-sleep")

    def test_changed_alpha_blocks_uninstall_and_keeps_installer_receipts(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        phone.installer_hash = "a" * 64
        with (
            patch.object(phone, "occupied", return_value=True),
            patch.object(phone, "package_hash", return_value="b" * 64),
            patch.object(phone, "read", return_value={"application_id": LAB.GAME, "sha256": "c" * 64}),
            patch.object(phone, "command") as command,
            patch.object(phone, "shell") as shell,
        ):
            with self.assertRaisesRegex(LAB.Failure, "ownership-not-established"):
                phone.cleanup()
        command.assert_not_called()
        self.assertEqual(shell.call_args.args, ("input", "keyevent", "KEYCODE_SLEEP"))

    def test_unknown_install_outcome_cannot_claim_cleanup_or_delete(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.install_attempted = True
        with patch.object(phone, "occupied", return_value=True) as occupied, patch.object(phone, "command") as command, patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "cleanup-package-ownership-unverified"):
                phone.cleanup()
        occupied.assert_called_once_with(LAB.PACKAGE)
        command.assert_not_called()
        shell.assert_called_once_with("input", "keyevent", "KEYCODE_SLEEP", label="device-display-sleep")

    def test_unknown_install_outcome_only_claims_absence_after_readback(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.install_attempted = True
        with patch.object(phone, "occupied", return_value=False) as occupied, patch.object(phone, "command") as command, patch.object(phone, "shell"):
            self.assertEqual(phone.cleanup(), "verified-absent")
        self.assertEqual([call.args[0] for call in occupied.call_args_list], [LAB.PACKAGE, LAB.GAME])
        command.assert_not_called()

    def test_private_diagnostics_persist_and_operation_and_cleanup_failures_stay_separate(self):
        output = io.StringIO()
        temporary_artifacts = []

        def fail_operation(phone, config, temporary, passed):
            temporary_artifacts.append(temporary)
            LAB.set_phase("pre-install-storage")
            LAB.run(["not-executed", "synthetic-argv-secret"], stdin=b"synthetic-stdin-secret", label="device-storage-volume-free")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(LAB, "ROOT", root),
                patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "synthetic-selector-not-for-publication"}),
                patch.object(LAB, "read_context", return_value={}),
                patch.object(LAB, "Phone") as phone,
                patch.object(LAB, "acceptance", side_effect=fail_operation),
                patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"synthetic-private-stdout", b"synthetic-private-stderr")),
                redirect_stdout(output),
            ):
                phone.return_value.cleanup.side_effect = LAB.Failure("device-display-sleep")
                self.assertEqual(LAB.main([]), 1)
            self.assertFalse(temporary_artifacts[0].exists())
            logs = list((root / "work/coordination/installer-update-acceptance").glob("run-*"))
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].stat().st_mode & 0o777, 0o700)
            files = list(logs[0].iterdir())
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in files))
            self.assertEqual(next(logs[0].glob("*.stderr.log")).read_bytes(), b"synthetic-private-stderr")
            metadata = json.loads(next(logs[0].glob("*.json")).read_text())
            self.assertEqual(metadata, {"phase": "pre-install-storage", "category": "device-storage-volume-free", "returncode": 1, "outcome": "returned"})
            retained = b"".join(path.read_bytes() for path in files)
            self.assertNotIn(b"synthetic-argv-secret", retained)
            self.assertNotIn(b"synthetic-stdin-secret", retained)
        result = output.getvalue()
        self.assertIn("FAIL check-for-updates phase=pre-install-storage reason=device-storage-volume-free", result)
        self.assertIn("FAIL cleanup phase=cleanup reason=device-display-sleep", result)
        self.assertNotIn("PASS cleanup", result)
        for private in ("synthetic-private", "synthetic-argv-secret", "synthetic-stdin-secret", "synthetic-selector-not-for-publication", directory):
            self.assertNotIn(private, result)

    def test_subprocess_error_does_not_publish_argv_stderr_or_identifiers(self):
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "not-for-publication"}),
            patch.object(LAB, "read_context", side_effect=RuntimeError("private-path-not-for-publication")),
            patch.object(LAB, "PrivateDiagnostics"),
            redirect_stdout(output),
        ):
            self.assertEqual(LAB.main([]), 1)
        self.assertNotIn("not-for-publication", output.getvalue())
        self.assertIn("unexpected-local-error", output.getvalue())


if __name__ == "__main__":
    unittest.main()
