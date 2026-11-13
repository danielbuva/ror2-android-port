"""Synthetic stage checkpoints, existing producer dispatch and thermal controls.

No game content, device, signing keys or generated Android artifacts are used.
"""

import copy
import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


F = load("tested_install_flow", "tools/phone-build/owner-apk/install_flow.py")
T = load("install_flow_thermal", "tools/phone-build/accepted-output/phone_runner.py")
U = load("install_flow_updates", "tools/phone-build/owner-apk/updates.py")
J = load("install_flow_jobs", "tools/phone-build/owner-apk/release_jobs.py")


def plan():
    return {"stages": [{"id": name, "title": name.title(), "jobs": [name + ".json"] if name in F.PRODUCTION else []} for name in F.STAGES]}


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.tick = 0.0
        self.options = dict(emit=lambda _: None, clock=lambda: self.tick)

    def create(self, release="signed-release-a"):
        return F.Pipeline(self.root, release, "accepted-input", plan(), **self.options)

    def test_stage_list_and_resume_after_process_death_excludes_reboot_downtime(self):
        flow = self.create()
        flow.perform("admission", lambda: None)
        flow.begin("textures")
        self.tick = 9
        flow.progress(0)
        self.tick = 10000  # A new process uses a different monotonic epoch.
        resumed = self.create()
        self.assertEqual(resumed.row("admission")["status"], "complete")
        self.assertEqual(resumed.row("textures")["status"], "interrupted")
        self.assertEqual(resumed.state["elapsed_seconds"], 9)
        resumed.begin("textures")
        self.tick += 4
        resumed.complete("textures")
        self.assertEqual(resumed.row("textures")["elapsed_seconds"], 13)
        self.assertEqual([row["id"] for row in resumed.state["stages"]], list(F.STAGES))

    def test_first_failure_and_retry_do_not_claim_downstream_success(self):
        flow = self.create()

        def fail():
            raise ValueError("synthetic producer refused")

        with self.assertRaisesRegex(ValueError, "synthetic"):
            flow.perform("textures", fail)
        self.assertEqual(flow.state["first_failure"], {"stage": "textures", "reason": "synthetic producer refused"})
        self.assertEqual(flow.row("native")["status"], "pending")
        resumed = self.create()
        resumed.perform("textures", lambda: None)
        self.assertIsNone(resumed.state["first_failure"])
        self.assertEqual(resumed.row("native")["status"], "pending")

    def test_signed_release_identity_change_discards_old_stage_success(self):
        self.create().perform("assembly", lambda: None)
        changed = self.create("signed-release-b")
        self.assertEqual(changed.row("assembly")["status"], "pending")

    def test_retry_reports_new_admission_failure_not_old_later_stage(self):
        flow = self.create()
        flow.begin("signing")
        flow.fail(ValueError("first attempt signing failure"))
        resumed = self.create()
        resumed.begin("admission")
        resumed.fail(ValueError("originals changed"))
        self.assertEqual(resumed.state["first_failure"], {"stage": "admission", "reason": "originals changed"})

    def test_artifact_receipt_rehashes_bytes_missing_and_symlink(self):
        flow = self.create()
        artifact = self.root / "synthetic-result.txt"
        artifact.write_text("authored synthetic output")
        flow.begin("apk")
        flow.artifacts("apk", [artifact])
        flow.complete("apk")
        self.assertTrue(self.create().reusable("apk"))
        artifact.write_text("corrupt")
        self.assertFalse(self.create().reusable("apk"))
        artifact.unlink()
        self.assertFalse(self.create().reusable("apk"))
        external = self.root / "other.txt"
        external.write_text("authored synthetic output")
        artifact.symlink_to(external)
        self.assertFalse(self.create().reusable("apk"))

    def test_ready_is_not_install_success_and_empty_stage_is_not_fake_work(self):
        selected = plan()
        selected["stages"][3]["jobs"] = []
        flow = F.Pipeline(self.root, "release", "input", selected)
        flow.perform("textures", lambda: None)
        self.assertEqual(flow.row("textures")["status"], "not_required")
        self.assertEqual(flow.row("textures")["completed"], 0)
        flow.await_install()
        self.assertEqual(flow.state["status"], "awaiting_install")
        self.assertEqual(flow.row("install")["status"], "awaiting_consent")

    def test_live_thermal_telemetry_is_read_without_changing_policy(self):
        F.write_json(self.root / "thermal-state.json", {"status": "paused", "cpu_celsius": 70, "battery_celsius": 34})
        flow = self.create()
        self.assertEqual(flow.snapshot()["telemetry"]["cpu_celsius"], 70)
        self.assertEqual(T.ThermalDutyCycle().high, 70)


class PlanTests(unittest.TestCase):
    def test_plan_covers_real_job_closure_and_rejects_missing_duplicate_or_backward_stage(self):
        selected = plan()
        jobs = {"assembly.json": {}, "textures.json": {"needs": ["assembly.json"]}, "native.json": {"needs": ["textures.json"]}}
        index = {"files": dict.fromkeys(jobs, "digest"), "entries": {"apk/synthetic.txt": {"job": "native.json"}}}
        self.assertEqual(F.validate_plan(selected, index, jobs.__getitem__)["textures.json"], "textures")
        for change in ("missing", "duplicate", "backward", "cycle", "extra"):
            bad, graph, bad_index = copy.deepcopy(selected), copy.deepcopy(jobs), copy.deepcopy(index)
            if change == "missing":
                bad["stages"][2]["jobs"] = []
            elif change == "duplicate":
                bad["stages"][3]["jobs"].append("assembly.json")
            elif change == "backward":
                bad["stages"][2]["jobs"], bad["stages"][4]["jobs"] = bad["stages"][4]["jobs"], bad["stages"][2]["jobs"]
            elif change == "cycle":
                graph["assembly.json"]["needs"] = ["native.json"]
            else:
                bad["stages"][2]["jobs"].append("extra.json")
                bad_index["files"]["extra.json"] = "digest"
            with self.subTest(change=change), self.assertRaises(ValueError):
                F.validate_plan(bad, bad_index, graph.__getitem__)


class OrchestrationTests(unittest.TestCase):
    def test_signed_plan_real_dispatch_failure_then_reboot_retry_reuses_verified_jobs(self):
        self.exercise(0)

    def test_existing_install_retains_previously_provisioned_signing_directory(self):
        self.exercise(1)

    def exercise(self, installed_version):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            inputs, runtime, native, repo = [root / name for name in ("inputs", "runtime", "native", "repo")]
            for directory in (inputs, runtime, native, repo):
                directory.mkdir()
            script = "tools/phone-build/accepted-output/record_produce.py"
            jobs = ("recipe/assembly.json", "recipe/textures.json")
            descriptors = {
                jobs[0]: {
                    "schema": 1,
                    "script": script,
                    "arguments": ["${output}", "${inputs}/attempt-count.txt"],
                    "outputs": {},
                    "artifacts": {"intermediate": "result"},
                },
                jobs[1]: {
                    "schema": 1,
                    "script": script,
                    "arguments": ["${output}", "${inputs}/attempt-count.txt"],
                    "outputs": {"payload/synthetic.txt": "result"},
                    "needs": [jobs[0]],
                },
            }
            manifest = {
                "schema": 1,
                "game_version": "synthetic-version",
                "files": [{"path": "original.txt", "bytes": 8, "sha256": __import__("hashlib").sha256(b"authored").hexdigest()}],
            }
            contents = {name: json.dumps(value).encode() for name, value in descriptors.items()}
            contents["recipe/inputs.json"] = json.dumps(manifest).encode()
            contents[script] = (
                b"import pathlib,sys\np=pathlib.Path(sys.argv[1]);p.mkdir();(p/'result').write_text('synthetic result');f=pathlib.Path(sys.argv[2]);f.write_text((f.read_text() if f.exists() else '')+'attempt\\n')\n"
            )
            for name, value in contents.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
            selected = {
                "schema": 1,
                "required_inputs": "recipe/inputs.json",
                "workspace_bytes": 0,
                "configuration": {"bindings": {"originals": "."}},
                "stages": [],
            }
            for stage in F.STAGES:
                selected["stages"].append(
                    {"id": stage, "title": stage.title(), "jobs": [jobs[0]] if stage == "assembly" else [jobs[1]] if stage == "textures" else []}
                )
            index = {
                "schema": 1,
                "files": {name: F.digest(repo / name) for name in contents},
                "entries": {"payload/synthetic.txt": {"job": jobs[1], "recipe_files": list(jobs), "producer_files": [script]}},
                "install_plan": selected,
            }
            release = {
                "version": "synthetic-1",
                "version_code": 2,
                "application_id": "dev.ror2lab.alpha",
                "data_schema": {"writes": 1, "reads": [1]},
                "minimum_installer_version": 3,
                "bundle_sha256": "a" * 64,
                "entries": {"payload/synthetic.txt": U.public().entry_dependencies(index, "payload/synthetic.txt")},
            }
            candidate = {"release": release, "envelope": {}, "bundle": {"url": "https://github.com/example/synthetic/releases/download/one/public-tools.zip"}}
            request = inputs / "update-request.json"
            U.write_json(
                request,
                {
                    "action": "install-prepare",
                    "application_id": release["application_id"],
                    "installed_version": installed_version,
                    "installed_release_version": installed_version,
                    "installer_version": 3,
                    "installer_package": "dev.ror2lab.phonebuildhostfixture",
                    "installer_signer_sha256": "c" * 64,
                },
            )
            U.write_json(
                runtime / "release-trust.json",
                {"repository": "example/synthetic", "application_id": release["application_id"], "keys": {"synthetic": "mocked signature boundary"}},
            )
            module = U.module

            def dispatch(*args, **kwargs):
                return J.Dispatcher(*args, **kwargs, python=[sys.executable])

            def modules(name, path):
                return SimpleNamespace(Dispatcher=dispatch) if name == "owner_update_jobs" else module(name, path)

            if installed_version:
                U.ALPHA.reserve(
                    inputs / "work/releases",
                    installed_version=0,
                    binding={
                        "source_sha256": "a" * 64,
                        "input_sha256": "b" * 64,
                        "toolchain_sha256": "c" * 64,
                        "publisher_version_code": 1,
                        "purpose": "update",
                    },
                )
            attempts = []
            is_file = Path.is_file

            def simulated_key_presence(path):
                # No keys are created or obtained; only the signer's custody
                # boundary is simulated, just like the signer below.
                return True if installed_version and path in {inputs / "retained-owner/owner.p12", inputs / "retained-owner/password"} else is_file(path)

            def assemble(release, outputs, *args, flow, **kwargs):
                # Real producer output reaches the pre-existing packaging boundary;
                # signing itself is deliberately not performed in a host fixture.
                self.assertEqual(Path(outputs["payload/synthetic.txt"]).read_text(), "synthetic result")
                flow.perform("apk", lambda: None)

                def signing():
                    attempts.append(1)
                    if len(attempts) == 1:
                        raise ValueError("synthetic signing boundary failure")
                    return {"synthetic": True}

                return flow.perform("signing", signing)

            with (
                patch.object(U, "latest", return_value=candidate),
                patch.object(U, "acquire", return_value=(repo, index)),
                patch.object(U.public(), "verify_envelope", return_value=release),
                patch.object(U, "module", side_effect=modules),
                patch.object(U, "assemble_sign", side_effect=assemble),
                patch.object(U, "toolchain_identity", return_value="d" * 64),
                patch.object(U.shutil, "disk_usage", return_value=SimpleNamespace(free=10 * 1024**3)),
                patch.object(Path, "is_file", simulated_key_presence),
            ):
                U.run(request, runtime, native, transport=Mock())
                self.assertEqual(json.loads((inputs / "update-state.json").read_text())["state"], "INPUTS_REQUIRED")
                self.assertFalse((inputs / "attempt-count.txt").exists())
                original = inputs / "import/files/original.txt"
                original.parent.mkdir(parents=True)
                original.write_bytes(b"authored")
                # Old per-install bookkeeping must not preempt signed admission.
                U.write_json(
                    inputs / "update-config.json",
                    {"input_hashes": "missing-stale-inventory.json", "manifest": "unused.json", "key_directory": "retained-owner"},
                )
                U.write_json(
                    request,
                    {
                        "action": "release-build",
                        "application_id": release["application_id"],
                        "installed_version": installed_version,
                        "installed_release_version": installed_version,
                        "installer_version": 3,
                        "installer_package": "dev.ror2lab.phonebuildhostfixture",
                        "installer_signer_sha256": "c" * 64,
                    },
                )
                with self.assertRaisesRegex(ValueError, "signing boundary"):
                    U.run(request, runtime, native, transport=Mock())
                failed = json.loads((inputs / "install-checkpoint.json").read_text())
                self.assertEqual(failed["first_failure"]["stage"], "signing")
                self.assertEqual(json.loads((inputs / "update-config.json").read_text())["key_directory"], "retained-owner")
                self.assertFalse((inputs / "owner-apk-ready.json").exists())
                U.run(request, runtime, native, transport=Mock())
                ready = json.loads((inputs / "update-state.json").read_text())
                self.assertEqual(ready["state"], "READY")
                self.assertEqual(ready["pipeline"]["status"], "awaiting_install")
                self.assertEqual((inputs / "attempt-count.txt").read_text().splitlines(), ["attempt", "attempt"])
                self.assertFalse((inputs / "installed-release.json").exists())
                U.write_json(
                    inputs / "update-config.json", {"input_hashes": "missing-stale-inventory.json", "manifest": "unused.json", "key_directory": "signing/owner"}
                )
                U.write_json(
                    request,
                    {
                        "action": "release-check",
                        "application_id": release["application_id"],
                        "installed_version": installed_version,
                        "installed_release_version": installed_version,
                        "installer_version": 3,
                        "installer_package": "dev.ror2lab.phonebuildhostfixture",
                        "installer_signer_sha256": "c" * 64,
                    },
                )
                U.run(request, runtime, native, transport=Mock())
                self.assertEqual(json.loads((inputs / "update-state.json").read_text())["state"], "UPDATE_AVAILABLE")


class SupervisedControlTests(unittest.TestCase):
    def supervise(self, temperatures, actions, finish=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        control, status, receipt = [root / name for name in ("control.json", "status.json", "receipt.json")]
        tick = [0.0]
        child, family = Mock(returncode=None), Mock()
        child.poll.side_effect = lambda: 0 if finish is not None and tick[0] >= finish else None

        def wait(seconds):
            tick[0] += seconds
            if tick[0] in actions:
                F.write_json(control, {"id": tick[0], "action": actions[tick[0]]})

        def sample():
            cpu, battery = temperatures(tick[0])
            return {"cpu": ("cpu", cpu), "battery": ("battery", battery)}

        with (
            patch.object(T, "efficiency_cpus", return_value={0, 1}),
            patch.object(T.subprocess, "Popen", return_value=child),
            patch.object(T, "Family", return_value=family),
        ):
            result = T.run(["synthetic-producer"], receipt, sensor=sample, clock=lambda: tick[0], wait=wait, control=control, status=status)
        return (
            result,
            [call.args[0] for call in family.send.call_args_list],
            json.loads(status.read_text()),
            json.loads(Path(str(receipt) + ".pause.json").read_text()),
        )

    def test_manual_pause_uses_same_family_and_pause_clock(self):
        result, signals, status, pause = self.supervise(lambda tick: (45, 34), {0.25: "pause", 0.75: "resume"}, finish=1)
        self.assertTrue(result["success"])
        self.assertEqual(signals, [signal.SIGSTOP, signal.SIGSTOP, signal.SIGCONT, signal.SIGKILL])
        self.assertEqual(pause, {"paused_seconds": 0.5, "paused_at": None})
        self.assertEqual(status["cpu_celsius"], 45)

    def test_manual_resume_cannot_override_thermal_hysteresis(self):
        result, signals, status, pause = self.supervise(lambda tick: (45 if tick in (0, 1) else 70, 34), {0.25: "pause", 0.5: "resume"}, finish=1)
        self.assertTrue(result["success"])
        self.assertEqual(signals[:-1], [signal.SIGSTOP, signal.SIGSTOP, signal.SIGSTOP, signal.SIGCONT])
        self.assertEqual(pause["paused_seconds"], 0.75)

    def test_cancel_while_paused_kills_without_resuming_and_reports_terminal_state(self):
        result, signals, status, pause = self.supervise(lambda tick: (45, 34), {0.25: "pause", 0.5: "cancel"})
        self.assertFalse(result["success"])
        self.assertEqual(signals, [signal.SIGSTOP, signal.SIGKILL])
        self.assertEqual(status["status"], "cancelled")

    def test_manual_pause_still_enforces_original_battery_cutoff(self):
        result, signals, status, pause = self.supervise(lambda tick: (45, 43 if tick >= 0.5 else 34), {0.25: "pause"})
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "battery at or above 43 C")
        self.assertEqual(signals, [signal.SIGSTOP, signal.SIGKILL])
        self.assertEqual(status["status"], "failed")


if __name__ == "__main__":
    unittest.main()
