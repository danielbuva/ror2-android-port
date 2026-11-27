"""Tracked-source pins refresh transitively and pre-push repairs the outgoing commit."""

import contextlib
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import source_pins


class SourcePinsTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.git("init", "-b", "topic")
        self.git("config", "user.email", "fixture")
        self.git("config", "user.name", "Fixture")
        self.source = "tools/producer.py"
        self.provider = "recipe/owner-provider.json"
        self.consumer = "recipe/owner-consumer.json"
        self.external = sha256(b"original bytes").hexdigest()
        self.put(self.source, "original bytes")
        self.source_hash = self.digest(self.source)
        self.put(
            self.provider,
            f'{{ "input": {{"path":"{self.source}","bytes":14,"sha256":"{self.source_hash}"}}, '
            f'"original": {{ "path":"work/game.bin", "sha256":"{self.external}" }}, '
            f'"compiled": {{ "source":"{self.source}","sha256":"{self.external}","bytes":14 }} }}\n',
        )
        self.provider_hash = self.digest(self.provider)
        self.put(
            self.consumer,
            f'{{"objects":[{{"record":"{self.provider_hash}","sha256":"{self.provider_hash}"}}]}}\n',
        )
        self.put("recipe/owner-j850-code.json", json.dumps({"source_files": {self.source: self.source_hash}}))
        self.put("work/game.bin", "replacement private fixture")
        self.git("add", "recipe", "tools")
        self.git("commit", "-m", "Baseline")
        self.baseline = self.git("rev-parse", "HEAD")
        self.put(self.source, "changed public producer")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True, stderr=subprocess.PIPE).strip()

    def put(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)

    def digest(self, name):
        return sha256((self.root / name).read_bytes()).hexdigest()

    def run_pins(self, *args):
        output = StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = source_pins.main(args, root=self.root)
        return code, output.getvalue()

    def hook(self, sha, ref="refs/heads/topic"):
        return subprocess.run(
            ["sh", str(ROOT / "scripts/git-hooks/pre-push")],
            input=f"{ref} {sha} {ref} {self.baseline}\n",
            cwd=self.root,
            text=True,
            capture_output=True,
        )

    def install_hook_fixture(self):
        for name in ("lab/source_pins.py", "journal-index.py", "journal-renumber.py", "journal-pre-push.py"):
            source = Path("scripts") / name
            path = self.root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, path)
        self.put("scripts/ci-local.sh", "#!/bin/sh\ntouch ci-ran\n")
        (self.root / "scripts/ci-local.sh").chmod(0o755)

    def assert_refreshed(self):
        provider = json.loads((self.root / self.provider).read_text())
        self.assertEqual(provider["input"], {"path": self.source, "sha256": self.digest(self.source), "bytes": 23})
        self.assertEqual(provider["original"]["sha256"], self.external)
        self.assertEqual(provider["compiled"], {"source": self.source, "sha256": self.external, "bytes": 14})
        historical = json.loads((self.root / "recipe/owner-j850-code.json").read_text())
        self.assertEqual(historical["source_files"][self.source], self.source_hash)
        row = json.loads((self.root / self.consumer).read_text())["objects"][0]
        self.assertEqual(row, {"record": self.digest(self.provider), "sha256": self.provider_hash})

    def test_check_is_read_only_and_refresh_is_transitive_and_idempotent(self):
        code, output = self.run_pins("check", "--show-external")
        self.assertEqual(code, 1, output)
        self.assertIn(f"{self.provider} <- {self.source}", output)
        self.assertIn(f"{self.consumer} <- {self.provider}", output)
        self.assertIn("input or output witness", output)
        self.assertEqual(self.digest(self.provider), self.provider_hash)
        self.assertEqual(self.run_pins("refresh")[0], 0)
        self.assert_refreshed()
        self.assertTrue((self.root / self.provider).read_text().startswith('{ "input": '))
        self.assertEqual(self.run_pins("check")[0], 0)
        self.assertNotIn("Refreshed", self.run_pins("refresh")[1])

    def test_base_resolves_stale_legacy_digest_after_provider_edit(self):
        old = json.loads((self.root / self.provider).read_text())
        old["unrelated_profile_setting"] = 1
        self.put(self.provider, json.dumps(old))
        self.assertEqual(self.run_pins("refresh")[0], 0)
        self.assert_refreshed()

    def test_identical_providers_refresh_to_one_digest(self):
        alias = "recipe/owner-provider-alias.json"
        self.put(alias, (self.root / self.provider).read_text())
        self.git("add", alias)
        code, output = self.run_pins("refresh")
        self.assertEqual(code, 0, output)
        self.assert_refreshed()
        self.assertEqual(self.digest(alias), self.digest(self.provider))

    def test_hook_repairs_head_stops_push_and_leaves_index_untouched(self):
        self.install_hook_fixture()
        self.git("commit", "-am", "Change producer")
        head = self.git("rev-parse", "HEAD")
        result = self.hook(head)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Commit the refreshed files", result.stderr)
        self.assertFalse((self.root / "ci-ran").exists())
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assert_refreshed()
        self.git("commit", "-am", "Refresh source pins")
        result = self.hook(self.git("rev-parse", "HEAD"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "ci-ran").is_file())

    def test_hook_preserves_overlapping_edits_and_different_outgoing_ref(self):
        self.install_hook_fixture()
        self.git("commit", "-am", "Change producer")
        head = self.git("rev-parse", "HEAD")
        result = self.hook(head, "refs/heads/other")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Check out the outgoing branch", result.stderr)
        previous = (self.root / self.provider).read_text()
        self.put(self.provider, previous + "\n")
        result = self.hook(head)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Preserving local edits", result.stderr)
        self.assertEqual((self.root / self.provider).read_text(), previous + "\n")
        self.assertNotIn("Refreshed", result.stdout)


if __name__ == "__main__":
    unittest.main()
