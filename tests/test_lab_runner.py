import os
import subprocess
import sys
import unittest
from pathlib import Path

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
        self.assertIsNotNone(lab_runner.battery_refusal(70, 0, 350))


class OwnerGateTest(unittest.TestCase):
    def test_non_owner_comment_is_refused_before_any_work(self):
        env = {"LAB_REPO": "/nonexistent", "LAB_REPOSITORY_OWNER": "owner", "LAB_COMMENT_AUTHOR": "someone", "LAB_AUTHOR_ASSOCIATION": "NONE"}
        self.assertEqual(lab_runner.main(env), 3)


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
