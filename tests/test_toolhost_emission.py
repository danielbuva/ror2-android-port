"""Shared emission lifecycle with authored files and fake device boundaries."""

from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

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

    def signed_request(self):
        self.request.pop("expected_records")
        self.request.update(operation="signed-code", expected_managed_providers=332)
        manifest = Path(self.request["manifest"]["path"])
        files = {}
        for name, value in (
            ("request.json", {"source_inputs": {}, "audio_members": ["Init.bnk"], "output": "conversion"}),
            ("input-hashes.json", {}),
            ("work/inventory/files.json", {}),
        ):
            source = self.root / (Path(name).stem + "-signed.json")
            source.write_text(json.dumps(value))
            files[name] = dict(source=str(source), bytes=source.stat().st_size, sha256=EMISSION.digest(source))
        manifest.write_text(json.dumps(dict(files=files)))
        self.request["manifest"]["sha256"] = EMISSION.digest(manifest)
        self.path.write_text(json.dumps(self.request))
        self.collected = dict(
            code=dict(
                success=True,
                phase="converted-native-planned",
                upstream_managed_generation_qualified=True,
                managed_providers=332,
                backend=dict(stripped_assemblies=93, native=dict(success=True)),
            ),
            converter=dict(inputs_unchanged=True, input_assemblies=93, files={"data/Metadata/global-metadata.dat": {}}),
            measurements={},
            thermal={},
        )

    def test_signed_code_uses_installed_clr_and_removes_only_owned_toolhost(self):
        self.signed_request()
        result = self.run_request()
        self.assertTrue(result["success"])
        self.assertTrue(result["owned_app_removed"])
        self.assertFalse(result["device_accepted"])
        self.phone.remove_owned_installer.assert_called_once()
        self.phone.cleanup.assert_not_called()
        command = self.phone.transport.start_detached.call_args.args[0]
        self.assertTrue(any(part.endswith("/owner-code/run_android.py") for part in command))
        self.assertTrue(any(part.startswith("ROR2LAB_BUILD_HOSTFXR=") and part.endswith("/libhostfxr10.so") for part in command))
        self.assertTrue(any(part.startswith("ROR2LAB_BUILD_DOTNET_ROOT=") and part.endswith("/runtime/dotnet") for part in command))
        self.assertEqual(self.run_request(resume=True)["error"], "signed-code-resume-requires-active-handle")

    def test_signed_code_keeps_unknown_handle_for_exact_reattachment(self):
        self.signed_request()
        self.phone.transport.wait_detached.side_effect = INSTALLER.TRANSPORT.DetachedUncertain(self.job)
        self.assertTrue(self.run_request()["lease_retained"])
        self.phone.remove_owned_installer.assert_not_called()
        self.phone.transport.wait_detached.side_effect = None
        final = self.run_request(resume=True)
        self.assertTrue(final["success"])
        self.assertTrue(final["reattached_without_launch"])
        self.phone.transport.start_detached.assert_called_once()
        self.phone.remove_owned_installer.assert_called_once()

    def test_signed_code_runtime_stream_keeps_framework_libraries_in_installed_apk(self):
        apk = self.root / "runtime.apk"
        dotnet8 = "dotnet/shared/Microsoft.NETCore.App/8.0.32/"
        dotnet10 = "dotnet/shared/Microsoft.NETCore.App/10.0.13/"
        native = "/data/app/synthetic/lib/arm64"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("assets/native-hashes.json", json.dumps(dict.fromkeys((*EMISSION.NET8_LIBRARIES, "libcoreclr10.so", "libcrypto.so", "libssl.so"))))
            archive.writestr("assets/python-links.json", json.dumps({dotnet10 + "libcoreclr.so": "libcoreclr10.so"}))
            for name in ("python/lib/python3.14/abc.py", dotnet8 + "CoreLib.dll", dotnet10 + "CoreLib.dll", "clang/21/include/stddef.h"):
                archive.writestr("assets/" + name, "authored fixture")
        streamed = self.root / "stream.tar"
        with streamed.open("wb") as pipe, patch.object(EMISSION.subprocess, "Popen") as launch:
            process = launch.return_value
            process.stdin = pipe
            process.wait.return_value = process.poll.return_value = 0
            EMISSION.transfer(self.phone, apk, {}, "/remote", native, signed_code=True)
        with tarfile.open(streamed) as archive:
            self.assertEqual(archive.getmember("runtime/" + dotnet8 + "libcoreclr.so").linkname, native + "/libcoreclr.so")
            self.assertEqual(archive.getmember("runtime/" + dotnet10 + "libcoreclr.so").linkname, native + "/libcoreclr10.so")
            self.assertEqual(archive.getmember("runtime/native-links/libssl.so.3").linkname, native + "/libssl.so")
            self.assertEqual(archive.getmember("runtime/repo").linkname, "../repo")
            self.assertTrue(archive.getmember("runtime/clang/21/include/stddef.h").isfile())

    def test_signed_code_upgrades_exact_retained_tool_and_cleans_only_new_scratch(self):
        self.signed_request()
        self.request["retained_tool_sha256"] = "c" * 64
        self.path.write_text(json.dumps(self.request))
        self.phone.occupied.return_value = True
        self.phone.package_hash.side_effect = ["c" * 64, self.request["tool_apk"]["sha256"]]
        with patch("device.validate_apk_identity") as identity:
            result = self.run_request()
        self.assertTrue(result["success"])
        self.assertTrue(result["retained_tool_preserved"])
        identity.assert_called_once()
        self.phone.transport.install.assert_called_once()
        self.phone.install.assert_not_called()
        self.phone.remove_owned_installer.assert_not_called()
        state = json.loads((self.output / "device-state.json").read_bytes())
        self.assertTrue(state["retained_tool"])
        self.phone.shell.assert_any_call("run-as", INSTALLER.PACKAGE, "rm", "-rf", state["remote"], label="emission-retained-scratch-cleanup")

    def test_signed_code_refuses_a_retained_tool_pin_mismatch(self):
        self.signed_request()
        self.request["retained_tool_sha256"] = "c" * 64
        self.path.write_text(json.dumps(self.request))
        self.phone.occupied.return_value = True
        self.assertEqual(self.run_request()["error"], "emission-preexisting-package")
        self.phone.transport.install.assert_not_called()
        self.phone.remove_owned_installer.assert_not_called()

    def test_android_invocation_uses_serial_records_without_multiprocessing_extension(self):
        result = self.run_request()
        self.assertTrue(result["success"])
        self.assertEqual(result["record_workers"], 1)
        command = self.phone.transport.start_detached.call_args.args[0]
        producer = command[command.index("--") + 1 :]
        self.assertEqual(producer[producer.index("--workers") + 1], "1")

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
