"""Shared emission lifecycle with authored files and fake device boundaries."""

from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import toolhost_emission as EMISSION  # noqa: E402

SPEC = importlib.util.spec_from_file_location("emission_installer_fixture", ROOT / "scripts/lab-installer-updates.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class EmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.output = self.root / "work/result"
        self.output.mkdir(parents=True)
        apk = self.root / "authored.apk"
        apk.write_bytes(b"authored APK stand-in, never installed")
        source = self.root / "input.json"
        source.write_text('{"authored":true}\n')
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"files": {"request.json": {"source": str(source), "bytes": source.stat().st_size, "sha256": EMISSION.digest(source)}}}))
        self.request = dict(
            runner=dict(repo=str(self.root), ref="main", device="synthetic"),
            tool_apk=dict(path=str(apk), sha256=EMISSION.digest(apk)),
            manifest=dict(path=str(manifest), sha256=EMISSION.digest(manifest)),
            request="request.json",
            done_file=str(self.output / "terminal.json"),
            expected_records=3,
            estimated_output_bytes=1024,
            profile="thor",
            timeout_seconds=10,
        )
        self.path = self.root / "request.json"
        self.path.write_text(json.dumps(self.request))
        self.lease = self.root / ".local/orchestrator/leases/synthetic-device"
        self.lease.mkdir(parents=True)
        (self.lease / "lab-runner.json").write_text(json.dumps(dict(pid=os.getppid())))
        self.device = Mock()
        self.device.storage.return_value = dict(mode="internal", internal=dict(free_bytes=1024**4))
        self.device.display.return_value = True
        self.phone = Mock()
        self.phone.owned_installer = False
        self.phone.occupied.return_value = False
        self.phone.package_hash.return_value = self.request["tool_apk"]["sha256"]
        self.phone.execute.return_value = subprocess.CompletedProcess([], 0, b"", b"")
        self.phone.shell.side_effect = lambda *args, **kwargs: (
            b"/data/user/0/dev.ror2lab.installertest\n" if kwargs["label"] == "emission-home" else b" nativeLibraryDir=/data/app/synthetic/lib/arm64\n"
        )
        self.phone.install.side_effect = lambda apk: setattr(self.phone, "owned_installer", True)
        self.job = INSTALLER.TRANSPORT.DetachedJob("/data/user/0/dev.ror2lab.installertest/files/ror2-adb-job-" + "a" * 32, ("run-as", INSTALLER.PACKAGE))

        def launch(*args, **kwargs):
            kwargs["persist"](self.job.as_dict())
            self.assertTrue((self.output / "device-state.json").exists())
            self.assertEqual(json.loads((self.lease / "retain.json").read_text())["job"], self.job.as_dict())
            return self.job

        self.phone.transport.start_detached.side_effect = launch
        self.phone.transport.wait_detached.return_value = subprocess.CompletedProcess([], 0, b"", b"")
        self.collected = dict(emission=dict(bundle="retained-on-device", sha256="b" * 64, emission=dict(records=3, structural_accepted=True)))

    def run_request(self, *, resume=False, restage=False):
        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(os.environ, dict(LAB_CANONICAL_ROOT=str(self.root), LAB_RUNNER_LEASE=str(self.lease), LAB_DEVICE_SERIAL="synthetic-device"))
            )
            stack.enter_context(patch("device.Device", return_value=self.device))
            thermal = stack.enter_context(patch("alpha_stability_batch._GameThermalOwner"))
            thermal.return_value.admission_battery = dict(level=80, current_now=0, temperature=300)
            stack.enter_context(patch.object(INSTALLER, "Phone", return_value=self.phone))
            stack.enter_context(patch.object(EMISSION, "transfer"))
            stack.enter_context(patch.object(EMISSION, "collect", return_value=self.collected))
            return EMISSION.execute(self.path, INSTALLER, resume=resume, restage=restage)

    def test_explicit_restage_replaces_only_confirmed_terminal_owned_inputs(self):
        self.phone.transport.wait_detached.return_value = subprocess.CompletedProcess([], 1, b"", b"")
        self.run_request()
        previous = json.loads((self.output / "device-state.json").read_bytes())["remote"]
        manifest = Path(self.request["manifest"]["path"])
        manifest.write_text(manifest.read_text() + "\n")
        self.request["manifest"]["sha256"] = EMISSION.digest(manifest)
        self.path.write_text(json.dumps(self.request))
        ordinary = self.run_request(resume=True)
        self.assertEqual(ordinary["error"], "emission-resume-identity")
        self.phone.transport.wait_detached.return_value = subprocess.CompletedProcess([], 0, b"", b"")
        result = self.run_request(resume=True, restage=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["restaged_after_terminal"])
        current = json.loads((self.output / "device-state.json").read_bytes())
        self.assertNotEqual(previous, current["remote"])
        self.assertEqual(current["manifest_sha256"], self.request["manifest"]["sha256"])
        self.phone.shell.assert_any_call("run-as", INSTALLER.PACKAGE, "rm", "-rf", previous, label="emission-retire-staging")
        self.phone.install.assert_called_once()

    def test_restage_refuses_an_unknown_remote_outcome(self):
        self.phone.transport.wait_detached.side_effect = INSTALLER.TRANSPORT.DetachedUncertain(self.job)
        self.run_request()
        result = self.run_request(resume=True, restage=True)
        self.assertEqual(result["error"], "emission-restage-confirmed-terminal-required")
        self.phone.transport.start_detached.assert_called_once()
        self.assertNotIn("emission-retire-staging", [call.kwargs.get("label") for call in self.phone.shell.call_args_list])

    def test_terminal_failure_retains_cache_and_retry_uses_new_output_same_cache(self):
        self.phone.transport.wait_detached.return_value = subprocess.CompletedProcess([], 1, b"", b"")
        first = self.run_request()
        self.assertFalse(first["success"])
        self.assertTrue(first["owned_app_and_cache_retained"])
        first_command = self.phone.transport.start_detached.call_args.args[0]
        self.phone.transport.wait_detached.return_value = subprocess.CompletedProcess([], 0, b"", b"")
        second = self.run_request(resume=True)
        second_command = self.phone.transport.start_detached.call_args.args[0]
        self.assertTrue(second["success"])
        self.assertNotEqual(first_command[first_command.index("--output") + 1], second_command[second_command.index("--output") + 1])
        self.assertEqual(first_command[first_command.index("--cache") + 1], second_command[second_command.index("--cache") + 1])
        self.phone.install.assert_called_once()
        self.phone.cleanup.assert_not_called()

    def test_exact_cli_dry_run_validates_pins_without_device_or_terminal(self):
        observed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/lab/lab_runner.py"), "--emission-request", str(self.path), "--dry-run"], capture_output=True, text=True
        )
        self.assertEqual(observed.returncode, 0, observed.stderr)
        self.assertTrue(json.loads(observed.stdout)["dry_run"])
        self.assertFalse(Path(self.request["done_file"]).exists())

    def test_installer_entry_imports_lab_helpers_without_ambient_pythonpath(self):
        (self.lease / "lab-runner.json").write_text(json.dumps(dict(pid=os.getpid())))
        script = """
import runpy
import sys
import types

device = types.ModuleType("device")
def boundary(*args, **kwargs):
    raise RuntimeError("fixture-device-boundary-reached")
device.Device = boundary
sys.modules["device"] = device
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
        observed = subprocess.run(
            [sys.executable, "-I", "-c", script, str(ROOT / "scripts/lab-installer-updates.py"), "--emission-request", str(self.path)],
            env=dict(os.environ, LAB_CANONICAL_ROOT=str(self.root), LAB_RUNNER_LEASE=str(self.lease), LAB_DEVICE_SERIAL="synthetic-device"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(observed.returncode, 1, observed.stderr)
        result = json.loads(Path(self.request["done_file"]).with_suffix(".operation.json").read_bytes())
        self.assertEqual(result["error"], "fixture-device-boundary-reached")
        self.assertFalse((self.output / "device-state.json").exists())

    def producer_checkout(self):
        checkout = self.root / "producer"
        checkout.mkdir()
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)
        source = checkout / "producer.py"
        source.write_text("print('authored new producer')\n")
        subprocess.run(["git", "-C", str(checkout), "add", "producer.py"], check=True)
        subprocess.run(
            ["git", "-C", str(checkout), "-c", "user.name=Fixture", "-c", "user.email=fixture@invalid", "commit", "-qm", "fixture"],
            check=True,
        )
        manifest = Path(self.request["manifest"]["path"])
        value = json.loads(manifest.read_bytes())
        value["files"]["repo/producer.py"] = dict(value["files"]["request.json"])
        value["files"]["repo/producer.py"]["bytes"] += 1  # Stale producer pin is the reason to refresh.
        value["original_input"] = {"sha256": "a" * 64}
        manifest.write_text(json.dumps(value))
        self.request["manifest"]["sha256"] = EMISSION.digest(manifest)
        self.path.write_text(json.dumps(self.request))
        return checkout, value

    def test_cli_refresh_repins_only_repo_files_without_device_access(self):
        checkout, original = self.producer_checkout()
        observed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/lab/lab_runner.py"), "--emission-request", str(self.path), "--refresh-emission-manifest", str(checkout)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(observed.returncode, 0, observed.stderr)
        result = json.loads(observed.stdout)
        self.assertEqual(result["refreshed_repo_files"], 1)
        request, files = EMISSION.load_request(self.path)
        manifest = json.loads(Path(request["manifest"]["path"]).read_bytes())
        self.assertEqual(files["request.json"], original["files"]["request.json"])
        self.assertEqual(manifest["original_input"], original["original_input"])
        self.assertEqual(files["repo/producer.py"]["source"], str(checkout / "producer.py"))
        self.assertEqual(manifest["bytes"], sum(pin["bytes"] for pin in files.values()))
        self.assertEqual(manifest["source_commit"], request["runner"]["ref"])
        self.assertEqual(manifest["source_checkout"], str(checkout))
        self.assertFalse(Path(request["done_file"]).exists())
        self.device.storage.assert_not_called()

    def test_refresh_refuses_invalid_outer_pin_before_git_or_device(self):
        self.request["manifest"]["sha256"] = "0" * 64
        self.path.write_text(json.dumps(self.request))
        before = self.path.read_bytes()
        with patch.object(EMISSION.subprocess, "check_output") as git:
            with self.assertRaisesRegex(ValueError, "emission-input-pin"):
                EMISSION.refresh_manifest(self.path, self.root)
        git.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)
        self.device.storage.assert_not_called()

    def test_refresh_refuses_uncommitted_producer(self):
        checkout, _ = self.producer_checkout()
        (checkout / "producer.py").write_text("print('uncommitted')\n")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "emission-clean-producer-checkout-required"):
            EMISSION.refresh_manifest(self.path, checkout)
        self.assertEqual(self.path.read_bytes(), before)

    def test_refresh_refuses_changed_nonrepo_input(self):
        checkout, _ = self.producer_checkout()
        (self.root / "input.json").write_text('{"changed":true}\n')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "emission-staged-input-pin"):
            EMISSION.refresh_manifest(self.path, checkout)
        self.assertEqual(self.path.read_bytes(), before)

    def test_uncertain_remote_job_retains_lease_and_resume_never_relaunches(self):
        self.phone.transport.wait_detached.side_effect = INSTALLER.TRANSPORT.DetachedUncertain(self.job)
        first = self.run_request()
        self.assertFalse(first["success"])
        self.assertTrue(first["lease_retained"])
        self.assertTrue((self.lease / "retain.json").exists())
        self.phone.transport.wait_detached.side_effect = None
        second = self.run_request(resume=True)
        self.assertTrue(second["success"])
        self.phone.transport.start_detached.assert_called_once()
        self.assertEqual(self.phone.transport.wait_detached.call_args.args[0].as_dict(), self.job.as_dict())
        self.assertFalse((self.lease / "retain.json").exists())

    def test_changed_input_refused_before_device_access_and_still_records_failure(self):
        self.request["tool_apk"]["sha256"] = "0" * 64
        self.path.write_text(json.dumps(self.request))
        result = self.run_request()
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "emission-input-pin")
        self.device.storage.assert_not_called()
        self.assertFalse(json.loads((self.output / "terminal.operation.json").read_bytes())["success"])

    def test_adopted_staging_refuses_internal_fallback(self):
        self.device.storage.return_value = dict(mode="adopted")
        result = self.run_request()
        self.assertEqual(result["error"], "emission-adopted-external-runtime-staging-unavailable")
        self.phone.install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
