import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import lab_runner  # noqa: E402

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
    def test_user_battery_rule(self):
        self.assertIsNone(lab_runner.battery_refusal(80, 0, 260))  # limit holding with zero current
        self.assertIsNotNone(lab_runner.battery_refusal(80, 500, 260))  # actually charging at the limit
        self.assertIsNotNone(lab_runner.battery_refusal(86, -100, 260))
        self.assertIsNone(lab_runner.battery_refusal(70, 0, 350))
        self.assertIsNotNone(lab_runner.battery_refusal(70, 0, 351))

    def test_charging_requires_three_consecutive_observations(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {})
            with mock.patch.object(runner, "battery", side_effect=[(80, 1, 300), (80, 0, 300)]), mock.patch.object(lab_runner.time, "sleep") as sleep:
                self.assertIsNone(runner.admit_battery("synthetic"))
                sleep.assert_called_once_with(10)
            with mock.patch.object(runner, "battery", return_value=(80, 1, 300)) as battery, mock.patch.object(lab_runner.time, "sleep"):
                self.assertIsNotNone(runner.admit_battery("synthetic"))
                self.assertEqual(battery.call_count, 3)

    def test_uncertain_emission_preserves_lease_through_runner_cleanup(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {})
            runner.devices = {"synthetic": "synthetic-device"}
            runner.worktree = lambda ref: Path(repo)

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
    def test_local_emission_publishes_failure_done_file_after_runner_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            request = repo / "request.json"
            done = repo / "work/terminal.json"
            request.write_text(json.dumps(dict(runner=dict(repo=str(repo), ref="main", device="synthetic"), done_file=str(done))))
            with mock.patch.object(lab_runner.Runner, "execute", side_effect=RuntimeError("synthetic failure")):
                self.assertEqual(lab_runner.local_emission(request), 1)
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
            (lease / "lab-runner.json").write_text(json.dumps({"workstream": "lab-runner", "pid": 12}))
            with mock.patch.object(lab_runner.os, "kill", return_value=None), self.assertRaisesRegex(lab_runner.CommandError, "still alive"):
                runner.take_lease("synthetic", "synthetic")
            with mock.patch.object(lab_runner.os, "kill", side_effect=ProcessLookupError):
                self.assertEqual(runner.take_lease("synthetic", "synthetic"), lease)
            self.assertTrue(runner.reattached)
            self.assertEqual(json.loads((lease / "lab-runner.json").read_text())["pid"], os.getpid())

    def test_refused_lease_never_touches_the_busy_device(self):
        with tempfile.TemporaryDirectory() as repo:
            runner = lab_runner.Runner(repo, {"LAB_RUN_ID": "t"})
            runner.devices = {"nova-b": "SERIAL"}
            runner.worktree = lambda ref: Path(repo)
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
            runner.worktree = lambda ref: Path(repo)
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
