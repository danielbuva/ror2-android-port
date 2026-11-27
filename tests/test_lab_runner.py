import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tarfile import open as open_tar
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import lab_runner  # noqa: E402
import toolhost_build  # noqa: E402

GUARD = ROOT / "scripts/lab/lab-runner-guard.sh"
REPO = "danielbuva/ror2-android-port"


class ParseCommandTest(unittest.TestCase):
    def test_parses_job_ref_device_and_args(self):
        request = lab_runner.parse_command("/lab dev ref=dani/dots-x device=nova-b -- run --target Siren\nnotes")
        self.assertEqual(request, {"job": "dev", "ref": "dani/dots-x", "device": "nova-b", "args": ["run", "--target", "Siren"]})

    def test_defaults_to_main_without_device(self):
        self.assertEqual(lab_runner.parse_command("/lab host-tests")["ref"], "main")
        self.assertIsNone(lab_runner.parse_command("/lab status")["device"])

    def test_refuses_what_the_menu_does_not_allow(self):
        for body in (
            "/lab shell rm -rf /",
            "/lab dev reset",
            "/lab dev run --device abc",
            "/lab script /etc/passwd.py",
            "/lab script ../escape.py",
            "/lab script docs/notes.py",
            "/lab script scripts/run.sh",
            "/lab host-tests ref=../main",
            "/lab host-tests ref=-x",
            "/lab status device=Nova;rm",
            "please /lab status",
        ):
            with self.subTest(body=body), self.assertRaises(lab_runner.CommandError):
                lab_runner.parse_command(body)

    def test_toolhost_takes_only_a_ref(self):
        self.assertEqual(lab_runner.parse_command("/lab toolhost ref=dani/dots-x")["job"], "toolhost")
        for body in ("/lab toolhost device=thor", "/lab toolhost -- --out /tmp"):
            with self.subTest(body=body), self.assertRaises(lab_runner.CommandError):
                lab_runner.parse_command(body)

    def test_script_paths_inside_allowed_roots(self):
        self.assertEqual(lab_runner.parse_command("/lab script tools/catalog/check.py --json")["args"], ["tools/catalog/check.py", "--json"])


class SanitizeTest(unittest.TestCase):
    def test_removes_private_identifiers(self):
        uuid = "-".join(("1" * 8, "a" * 4, "b" * 4, "c" * 4, "d" * 12))  # built so the public audit sees no literal
        email = "me" + "@" + "example.invalid"
        text = "/" + "Users/someone/repo" + f" serial ABC123 on /mnt/expand/{uuid} {email} 10.0.0.2 ghp_abcdefghijklmnopqrstuvwxyz"
        clean = lab_runner.sanitize(text, ["ABC123"])
        for private in ("someone", "ABC123", uuid, email, "10.0.0.2", "ghp_"):
            self.assertNotIn(private, clean)


class BatteryRuleTest(unittest.TestCase):
    def test_strict_battery_applies_to_runner_and_child(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            config = repo / "work/config/lab-runner.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"battery_charge_override": True}))
            runner = lab_runner.Runner(repo, {}, strict_battery=True)
            with mock.patch.object(runner, "battery", return_value=(86, 0, 300)):
                self.assertIn("> 85 %", runner.admit_battery("synthetic"))
            with mock.patch.dict(os.environ, {"LAB_BATTERY_CHARGE_OVERRIDE": "1"}), mock.patch.object(lab_runner.subprocess, "run") as child:
                runner.run(["probe"], repo)
                self.assertNotIn("LAB_BATTERY_CHARGE_OVERRIDE", child.call_args.kwargs["env"])

    def test_explicit_toolhost_cooldown_honors_owner_override(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            config = repo / "work/config/lab-runner.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"battery_charge_override": True}))
            runner = lab_runner.Runner(repo, {})
            device = mock.Mock()
            device.storage.return_value = {"mode": "internal", "internal": {"free_bytes": 22 * 1024**3}}
            device.cmd.return_value = "cpu-0 45000 /thermal_zone0/temp\nbattery 34000 /thermal_zone1/temp\n"
            device.sh.side_effect = ["temperature: 360\nlevel: 90\nstatus: 2", "500", "temperature: 340\nlevel: 90\nstatus: 2", "500"]
            out = repo / "output"
            with (
                mock.patch("device.Device", return_value=device),
                mock.patch("alpha_stability_batch.time.sleep") as sleep,
                mock.patch.object(toolhost_build, "stage_archive", side_effect=RuntimeError("fixture admitted")),
                self.assertRaisesRegex(RuntimeError, "fixture admitted"),
            ):
                toolhost_build.execute(
                    {"tool_root": "/data/local/tmp/synthetic"},
                    (None, None, None, None, None, None),
                    out,
                    runner=runner,
                    serial="synthetic",
                    lease=repo,
                    transport_module=mock.Mock(),
                    package=lab_runner.TEST_PACKAGE,
                )
            sleep.assert_called_once()
            device.display.assert_called_once_with(False)

    def test_user_battery_rule(self):
        self.assertIsNone(lab_runner.battery_refusal(80, 0, 260))  # limit holding with zero current
        self.assertIsNotNone(lab_runner.battery_refusal(80, 500, 260))  # actually charging at the limit
        self.assertIsNotNone(lab_runner.battery_refusal(86, -100, 260))
        self.assertIsNone(lab_runner.battery_refusal(70, 0, 350))
        self.assertIsNotNone(lab_runner.battery_refusal(70, 0, 351))
        # the owner charge override admits a full, charging battery but never a warm one
        self.assertIsNone(lab_runner.battery_refusal(95, 500, 260, charge_override=True))
        self.assertIsNotNone(lab_runner.battery_refusal(95, 500, 351, charge_override=True))

    def test_charging_requires_three_consecutive_observations(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {})
            with mock.patch.object(runner, "battery", side_effect=[(80, 1, 300), (80, 0, 300)]), mock.patch.object(lab_runner.time, "sleep") as sleep:
                self.assertIsNone(runner.admit_battery("synthetic"))
                sleep.assert_called_once_with(10)
            with mock.patch.object(runner, "battery", return_value=(80, 1, 300)) as battery, mock.patch.object(lab_runner.time, "sleep"):
                self.assertIsNotNone(runner.admit_battery("synthetic"))
                self.assertEqual(battery.call_count, 3)

    def test_phone_producer_battery_floor(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {})
            with mock.patch.object(runner, "battery", return_value=(29, 0, 260)):
                self.assertIn("< 30 %", runner.admit_battery("synthetic", heavy=True))
                self.assertIsNone(runner.admit_battery("synthetic"))
            with mock.patch.object(runner, "battery", return_value=(30, 0, 260)):
                self.assertIsNone(runner.admit_battery("synthetic", heavy=True))

    def test_charge_override_admits_phone_producers_at_any_charge(self):
        with tempfile.TemporaryDirectory() as repo:
            config = Path(repo) / "work/config/lab-runner.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"battery_charge_override": True}))
            runner = lab_runner.Runner(repo, {})
            with mock.patch.object(runner, "battery", return_value=(29, 0, 260)):
                self.assertIsNone(runner.admit_battery("synthetic", heavy=True))
            with mock.patch.object(runner, "battery", return_value=(29, 0, 351)):
                self.assertIsNotNone(runner.admit_battery("synthetic", heavy=True))

    def test_uncertain_emission_preserves_lease_through_runner_cleanup(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {})
            runner.devices = {"synthetic": "synthetic-device"}
            runner.worktree = lambda ref, *, local_ref=False: Path(repo)

            def run(*args, **kwargs):
                if kwargs.get("extra_env"):
                    lease = Path(kwargs["extra_env"]["LAB_RUNNER_LEASE"])
                    (lease / "retain.json").write_text("{}")
                return 1

            with mock.patch.object(runner, "battery", return_value=(70, 0, 300)), mock.patch.object(runner, "run", side_effect=run):
                with mock.patch.object(lab_runner._TRANSPORT.AdbTransport, "run", return_value=b""):
                    runner.execute(lab_runner.parse_command("/lab script device=synthetic -- scripts/synthetic.py"))
            self.assertTrue((runner.leases / "synthetic-device/retain.json").exists())


class OwnerGateTest(unittest.TestCase):
    def test_non_owner_comment_is_refused_before_any_work(self):
        env = {"LAB_REPO": "/nonexistent", "LAB_REPOSITORY_OWNER": "owner", "LAB_COMMENT_AUTHOR": "someone", "LAB_AUTHOR_ASSOCIATION": "NONE"}
        self.assertEqual(lab_runner.main(env), 3)


class RefusedLeaseTest(unittest.TestCase):
    def test_local_packaging_refuses_without_a_grant_and_preserves_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            checkout = repo / ".local/worktrees/fixture"
            checkout.mkdir(parents=True)
            runner = lab_runner.Runner(repo, {})
            runner.devices = {"nova-b": "fixture"}
            command = lab_runner.parse_command("/lab script device=nova-b -- scripts/lab-alpha-packaging.py --package-only")
            with mock.patch.object(runner, "run", return_value=0) as run, mock.patch.object(runner, "battery") as battery:
                with self.assertRaisesRegex(lab_runner.CommandError, "grant required"):
                    runner.execute(command, local_checkout=checkout, workstream="fixture-worker")
            battery.assert_not_called()
            run.assert_called_once_with([lab_runner.sys.executable, "scripts/prune-generated.py", "--apply", "--aggressive"], checkout, timeout=1800)
            self.assertTrue(checkout.is_dir())

    def test_local_packaging_publishes_terminal_after_shared_runner_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            config = repo / "work/config/lab-runner.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"devices": {"nova-b": "fixture"}}))
            request = repo / "request.json"
            done = repo / "work/terminal.json"
            source_commit = "a" * 40
            request.write_text(
                json.dumps(
                    dict(
                        repo=str(repo),
                        checkout=str(repo),
                        workstream="fixture-worker",
                        device="nova-b",
                        done_file=str(done),
                        toolhost_source_commit=source_commit,
                    )
                )
            )
            with (
                mock.patch.object(lab_runner.subprocess, "check_output", return_value=str(repo / ".git")),
                mock.patch.object(lab_runner.Runner, "execute", side_effect=lab_runner.CommandError("fixture failure")) as execute,
            ):
                self.assertEqual(lab_runner.local_packaging(request), 1)
            self.assertEqual(execute.call_args.kwargs, dict(local_checkout=repo, workstream="fixture-worker"))
            self.assertEqual(execute.call_args.args[0]["args"][-2:], ["--toolhost-source-commit", source_commit])
            self.assertEqual(json.loads(done.read_bytes())["error"], "fixture failure")

    def test_signed_packaging_budgets_import_and_each_native_build(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            request_path = repo / "request.json"
            config = repo / "work/config/lab-runner.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"devices": {"thor": "fixture-thor", "nova-b": "fixture-nova"}}))
            for operation, device, tools, budget in (
                ("staged-update", "thor", False, 3 * 14400 + 1800),
                ("staged-update", "thor", True, 4 * 14400 + 1800),
                ("nightly", "nova-b", False, 2 * 14400 + 3000),
                ("nightly", "nova-b", True, 3 * 14400 + 3000),
            ):
                with self.subTest(operation=operation, acquire_on_phone=tools):
                    request_path.write_text(
                        json.dumps(
                            dict(
                                repo=str(repo),
                                checkout=str(repo),
                                workstream="fixture-worker",
                                device=device,
                                done_file=str(repo / f"work/{operation}-{tools}.json"),
                                operation=operation,
                                acquire_on_phone=tools,
                            )
                        )
                    )
                    with (
                        mock.patch.object(lab_runner.subprocess, "check_output", return_value=str(repo / ".git")),
                        mock.patch.object(lab_runner.Runner, "execute", return_value=(0, None)) as execute,
                    ):
                        self.assertEqual(lab_runner.local_packaging(request_path), 0)
                    command = execute.call_args.args[0]
                    self.assertEqual(command["args"][-4:], [f"--{operation}-request", str(request_path), "--timeout", "14400"])
                    self.assertEqual(command["timeout_seconds"], budget)

    def test_explicit_toolhost_plan_is_validated_and_cached_by_input_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            stage = repo / "work/stage"
            stage.mkdir(parents=True)
            config = repo / "work/config/lab-runner.json"
            config.parent.mkdir()
            config.write_text(json.dumps({"devices": {"thor": "fixture"}}))
            provider = repo / "_socket.so"
            provider.write_bytes(b"synthetic-provider")
            apk_data = b"synthetic-apk"
            tools = {"natives": {"libpyext__socket.so": {"path": str(provider), "sha256": toolhost_build.digest(provider)}}}
            for name, value in {
                "backend-tools.json": json.dumps(tools),
                "python-native-plan.json": "{}",
                "build_fixture.py": "# synthetic",
                "apksigner.jar": "fixture",
                "release-trust.json": "{}",
                "repo/synthetic.py": "# pinned checkout",
            }.items():
                file = stage / name
                file.parent.mkdir(exist_ok=True)
                file.write_text(value)
            (repo / "synthetic.py").write_text("# pinned checkout")
            files = {path.relative_to(stage).as_posix(): toolhost_build.digest(path) for path in stage.rglob("*") if path.is_file()}
            receipt = stage / "stage-receipt.json"
            request = repo / "request.json"
            root = "/data/local/tmp/synthetic-tools"
            outputs = []

            def run(command, **kwargs):
                inputs, plan, out = command["local_toolhost"]
                self.assertEqual(inputs["tool_root"], root)
                self.assertEqual(kwargs, {"local_checkout": repo, "workstream": "fixture-worker"})
                out.mkdir(parents=True)
                remote = root + "/synthetic-run"
                tar = out / "stage.tar"
                toolhost_build.stage_archive(tar, *plan[:4], remote, lab_runner.TEST_PACKAGE)
                with open_tar(tar) as archive:
                    backend = json.load(archive.extractfile("stage/backend-tools.json"))
                    path = "providers/libpyext__socket.so/_socket.so"
                    self.assertEqual(backend["natives"]["libpyext__socket.so"]["path"], remote + "/" + path)
                    self.assertEqual(archive.extractfile(path).read(), provider.read_bytes())
                self.assertEqual(backend["package"], lab_runner.TEST_PACKAGE)
                apk = out / "signed.apk"
                apk.write_bytes(apk_data)
                (out / "build-receipt.json").write_text(json.dumps({"apk_sha256": toolhost_build.digest(apk)}))
                outputs.append(out)
                return 0, {"success": True, "apk_sha256": toolhost_build.digest(apk)}

            def command(*args, **kwargs):
                return str(repo / ".git") if "--git-common-dir" in args[0] else "synthetic-commit"

            with (
                mock.patch.object(lab_runner.subprocess, "check_output", side_effect=command),
                mock.patch.object(lab_runner.Runner, "execute", side_effect=run),
                mock.patch.object(toolhost_build, "verify_apk") as verify,
            ):
                for attempt, source in enumerate(("first", "first", "second")):
                    receipt.write_text(json.dumps(dict(success=True, game_inputs=False, files=files, source_hint=source)))
                    done = repo / "work" / f"done-{attempt}.json"
                    inputs = dict(stage_receipt=dict(path=str(receipt), sha256=toolhost_build.digest(receipt)), tool_root=root, signer_sha256="a" * 64)
                    request.write_text(
                        json.dumps(
                            dict(
                                repo=str(repo),
                                checkout=str(repo),
                                workstream="fixture-worker",
                                device="thor",
                                operation="toolhost",
                                toolhost_inputs=inputs,
                                done_file=str(done),
                            )
                        )
                    )
                    self.assertEqual(lab_runner.local_packaging(request), 0)
                    self.assertEqual(json.loads(done.read_bytes()).get("cached", False), attempt == 1)
                    result = outputs[-1] / "result.json"
                    cached = json.loads(result.read_bytes())
                    self.assertEqual(cached["source_commit"], "synthetic-commit")
                    self.assertEqual(cached["cache_key"], outputs[-1].name)
                    self.assertEqual(cached["package"], lab_runner.TEST_PACKAGE)
                    self.assertEqual(cached["signer_sha256"], inputs["signer_sha256"])
                    if attempt == 0:
                        result.write_text(json.dumps({"success": True, "apk_sha256": cached["apk_sha256"], "cache_key": cached["cache_key"]}))
                self.assertEqual(len(set(outputs)), 2)
                verify.assert_called_once()
                self.assertEqual(verify.call_args.args[-1], lab_runner.TEST_PACKAGE)
                provider.write_bytes(b"changed")
                inputs = json.loads(request.read_bytes())["toolhost_inputs"]
                with self.assertRaisesRegex(ValueError, "input pin mismatch"):
                    toolhost_build.read_plan(inputs, repo)

    def test_local_packaging_can_back_up_a_cached_thor_signer_without_building(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            commit = "a" * 40
            config = repo / "work/config/lab-runner.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"devices": {"thor": "fixture"}}))
            output = repo / "work/coordination/lab-runner/toolhost" / commit
            output.mkdir(parents=True)
            command = output / "command.json"
            command.write_text(json.dumps(dict(source_commit=commit, retained_tool_key="/data/local/tmp/synthetic/owner-tool-key")))
            (output / "result.json").write_text(json.dumps(dict(success=True, package=lab_runner.TEST_PACKAGE, source_commit=commit, signer_sha256="b" * 64)))
            done = repo / "work/terminal.json"
            request = repo / "request.json"
            request.write_text(
                json.dumps(
                    dict(
                        repo=str(repo),
                        checkout=str(repo),
                        device="thor",
                        workstream="fixture-worker",
                        done_file=str(done),
                        operation="toolhost",
                        backup_installer_key=True,
                        toolhost_source_commit=commit,
                    )
                )
            )
            with (
                mock.patch.object(lab_runner.subprocess, "check_output", return_value=str(repo / ".git")),
                mock.patch.object(lab_runner, "retain_installer_signer") as backup,
                mock.patch.object(lab_runner.Runner, "toolhost") as build,
            ):
                self.assertEqual(lab_runner.local_packaging(request, dry_run=True), 0)
                backup.assert_not_called()
                self.assertEqual(lab_runner.local_packaging(request), 0)
                self.assertEqual(backup.call_args.args[1:], ("thor", "fixture-worker", output))
                build.assert_not_called()
            self.assertTrue(json.loads(done.read_bytes())["signing_key_backed_up"])

    def test_explicit_restage_uses_the_shared_installer_resume_path(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            request = repo / "request.json"
            request.write_text(json.dumps(dict(runner=dict(repo=str(repo), ref="main", device="synthetic"), done_file=str(repo / "work/terminal.json"))))
            with mock.patch.object(lab_runner.Runner, "execute", return_value=(1, None)) as execute:
                self.assertEqual(lab_runner.local_emission(request, restage=True), 1)
            self.assertEqual(execute.call_args.args[0]["args"][-2:], ["--resume-emission", "--restage-emission"])

    def test_local_emission_publishes_failure_done_file_after_runner_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            request = repo / "request.json"
            done = repo / "work/terminal.json"
            request.write_text(json.dumps(dict(runner=dict(repo=str(repo), ref="c" * 40, local_ref=True, device="synthetic"), done_file=str(done))))
            with mock.patch.object(lab_runner.Runner, "execute", side_effect=RuntimeError("synthetic failure")) as execute:
                self.assertEqual(lab_runner.local_emission(request, workstream="fixture-worker"), 1)
            self.assertEqual(execute.call_args.kwargs["workstream"], "fixture-worker")
            self.assertTrue(execute.call_args.kwargs["local_ref"])
            self.assertEqual(json.loads(done.read_text())["error"], "synthetic failure")

    def test_resume_claims_only_its_retained_lease_after_previous_runner_exits(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {})
            lease = runner.leases / "synthetic"
            lease.mkdir(parents=True)
            runner.resume_state = Path(repo) / "state.json"
            job = {"directory": "synthetic-job"}
            runner.resume_state.write_text(json.dumps({"job": job}))
            (lease / "retain.json").write_text(json.dumps({"job": job, "state": str(runner.resume_state)}))
            (lease / "lab-runner.json").write_text(json.dumps({"workstream": "fixture-worker", "pid": 12}))
            with self.assertRaisesRegex(lab_runner.CommandError, "identity mismatch"):
                runner.take_lease("synthetic", "synthetic")
            with mock.patch.object(lab_runner.os, "kill", return_value=None), self.assertRaisesRegex(lab_runner.CommandError, "still alive"):
                runner.take_lease("synthetic", "synthetic", workstream="fixture-worker")
            with mock.patch.object(lab_runner.os, "kill", side_effect=ProcessLookupError):
                self.assertEqual(runner.take_lease("synthetic", "synthetic", workstream="fixture-worker"), lease)
            self.assertTrue(runner.reattached)
            self.assertEqual(json.loads((lease / "lab-runner.json").read_text())["pid"], os.getpid())

    def test_refused_lease_never_touches_the_busy_device(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {"LAB_RUN_ID": "t"})
            runner.devices = {"nova-b": "SERIAL"}
            runner.worktree = lambda ref, *, local_ref=False: Path(repo)
            runner.run = lambda *a, **k: 0
            (Path(repo) / ".local/orchestrator/leases/SERIAL").mkdir(parents=True)
            with mock.patch.object(lab_runner.subprocess, "run") as run:
                with self.assertRaises(lab_runner.CommandError):
                    runner.execute(lab_runner.parse_command("/lab script device=nova-b -- scripts/x.py"))
            self.assertFalse(any("KEYCODE_SLEEP" in call.args[0] for call in run.call_args_list if call.args))


class TransportIntegrationTest(unittest.TestCase):
    def test_battery_read_retries_signal_and_refuses_nonzero_or_incomplete_observation(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {"LAB_RUN_ID": "synthetic"})
            killed = subprocess.CompletedProcess([], -9, b"", b"")
            battery = subprocess.CompletedProcess([], 0, b"level: 70\ntemperature: 260\n", b"")
            current = subprocess.CompletedProcess([], 0, b"0\n", b"")
            with (
                mock.patch.object(lab_runner.subprocess, "run", side_effect=[killed, battery, current]) as run,
                mock.patch.object(lab_runner._TRANSPORT.time, "sleep"),
            ):
                self.assertEqual(runner.battery("synthetic-target"), (70, 0, 260))
            self.assertEqual(run.call_count, 3)
            for output in (subprocess.CompletedProcess([], 1, b"", b""), subprocess.CompletedProcess([], 0, b"", b"")):
                with mock.patch.object(lab_runner.subprocess, "run", return_value=output), self.assertRaises(lab_runner.CommandError):
                    runner.battery("synthetic-target")

    def test_cleanup_releases_lease_after_failed_sleep_without_replaying_job(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {"LAB_RUN_ID": "synthetic"})
            runner.devices = {"synthetic-alias": "synthetic-target"}
            runner.worktree = lambda ref, *, local_ref=False: Path(repo)
            with mock.patch.object(runner, "battery", return_value=(70, 0, 260)), mock.patch.object(runner, "run", return_value=0) as job:
                with mock.patch.object(lab_runner.subprocess, "run", return_value=subprocess.CompletedProcess([], -9, b"", b"")) as adb:
                    with mock.patch.object(lab_runner._TRANSPORT.time, "sleep"):
                        self.assertEqual(runner.execute(lab_runner.parse_command("/lab script device=synthetic-alias -- scripts/synthetic.py")), (0, None))
            self.assertFalse((runner.leases / "synthetic-target").exists())
            self.assertEqual(adb.call_count, 3)
            self.assertEqual(job.call_count, 3)  # job, worktree cleanup, prune; never replay the job
            self.assertIn("display sleep unverified", runner.log.read_text())

    def test_isolated_bootstrap_loads_only_both_pinned_main_files(self):
        workflow = (ROOT / ".github/workflows/lab-runner.yml").read_text()
        self.assertIn('trusted_main=$(git -C "$LAB_REPO" rev-parse origin/main)', workflow)
        for name in ("lab_runner.py", "adb_transport.py"):
            self.assertIn('show "$trusted_main:scripts/lab/' + name + '"', workflow)
        self.assertIn('python3 -I "$bootstrap/lab_runner.py"', workflow)
        with tempfile.TemporaryDirectory() as directory:
            for name in ("lab_runner.py", "adb_transport.py"):
                (Path(directory) / name).write_bytes((ROOT / "scripts/lab" / name).read_bytes())
            env = {"PATH": os.environ["PATH"], "LAB_COMMENT_AUTHOR": "not-owner", "LAB_REPOSITORY_OWNER": "owner", "LAB_REPO": "/synthetic-unused"}
            result = subprocess.run([sys.executable, "-I", str(Path(directory) / "lab_runner.py")], env=env, capture_output=True)
        self.assertEqual(result.returncode, 3)
        self.assertNotIn(b"Traceback", result.stderr)


class GuardHookTest(unittest.TestCase):
    def guard(self, **overrides):
        env = {
            "PATH": os.environ["PATH"],
            "GITHUB_REPOSITORY": REPO,
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_WORKFLOW_REF": f"{REPO}/.github/workflows/lab-runner.yml@refs/heads/main",
            "GITHUB_ACTOR": "danielbuva",
            **overrides,
        }
        return subprocess.run(["bash", str(GUARD)], env=env, capture_output=True).returncode

    def test_admits_only_mains_comment_workflow(self):
        self.assertEqual(self.guard(), 0)
        self.assertNotEqual(self.guard(GITHUB_EVENT_NAME="push"), 0)
        self.assertNotEqual(self.guard(GITHUB_EVENT_NAME="pull_request"), 0)
        self.assertNotEqual(self.guard(GITHUB_WORKFLOW_REF=f"{REPO}/.github/workflows/evil.yml@refs/heads/dani/dots-x"), 0)
        self.assertNotEqual(self.guard(GITHUB_WORKFLOW_REF=f"{REPO}/.github/workflows/lab-runner.yml@refs/heads/dani/dots-x"), 0)
        self.assertNotEqual(self.guard(GITHUB_REPOSITORY="someone/fork"), 0)
        self.assertNotEqual(self.guard(GITHUB_ACTOR="someone"), 0)


if __name__ == "__main__":
    unittest.main()
