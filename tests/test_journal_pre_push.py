"""Exercise the real pre-push hook against a disposable Git remote."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = Path("docs/PORTING_JOURNAL.md")
INDEX = Path("docs/JOURNAL_INDEX.md")


class JournalPrePushTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "topic"
        self.root.mkdir()
        self.remote = Path(temporary.name) / "remote.git"
        self.env = dict(os.environ)
        for name in subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True).splitlines():
            self.env.pop(name, None)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Synthetic fixture")
        self.git("config", "user.email", "fixture.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("init", "-q", "--bare", str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        for name in (
            "journal-index.py",
            "journal-renumber.py",
            "journal-pre-push.py",
            "lab/source_pins.py",
            "git-hooks/pre-push",
        ):
            target = self.root / "scripts" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts" / name, target)
        # CI is already tested separately; this stub witnesses the exact SHA.
        ci = self.root / "scripts/ci-local.sh"
        ci.write_text('#!/bin/sh\necho "checked $1"\n')
        ci.chmod(0o755)
        (self.root / ".gitattributes").write_text(f"{JOURNAL} merge=union\n{INDEX} merge=union\n")
        (self.root / JOURNAL.parent).mkdir()
        (self.root / JOURNAL).write_text("# Journal\n\n## J1 — Base\n\nBase evidence.\n")
        (self.root / INDEX).write_text("Synthetic generated index placeholder.\n")
        (self.root / "unrelated.txt").write_text("original\n")
        self.commit("base")
        self.git("push", "-q", "origin", "main")
        self.git("switch", "-q", "-c", "dani/fixture")
        self.append(2, "Topic")
        self.commit("topic", date="2020-01-04T02:00:00+0000")
        self.git("switch", "-q", "main")
        self.append(2, "Main")
        self.commit("advance main", date="2020-01-06T01:00:00+0000")
        self.git("push", "-q", "origin", "main")
        self.git("switch", "-q", "dani/fixture")
        self.git("merge", "--no-edit", "origin/main")
        self.git("config", "core.hooksPath", "scripts/git-hooks")

    def git(self, *args, ok=True, date=None):
        env = self.env if date is None else self.env | {"GIT_AUTHOR_DATE": date}
        result = subprocess.run(["git", *args], cwd=self.root, env=env, capture_output=True, text=True, timeout=30)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def commit(self, message, date=None):
        self.git("add", ".")
        self.git("commit", "-qm", message, date=date)

    def append(self, number, name):
        with (self.root / JOURNAL).open("a", encoding="utf-8") as stream:
            stream.write(f"\n## J{number} — {name}\n\n{name} evidence.\n")

    def push(self, *, ok=True):
        return self.git("push", "origin", "dani/fixture", ok=ok, date="2020-01-08T23:00:00-0800")

    def test_first_push_repairs_then_retry_sends_exact_new_commit(self):
        original = self.git("rev-parse", "HEAD").stdout.strip()
        before = self.push(ok=False)
        self.assertNotEqual(before.returncode, 0)
        self.assertIn("Run git push again", before.stderr)
        self.assertNotIn("checked ", before.stdout)
        self.assertEqual(self.git("ls-remote", "--heads", "origin", "dani/fixture").stdout, "")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.git("rev-parse", "HEAD^").stdout.strip(), original)
        self.assertEqual(set(self.git("diff", "--name-only", original, tip).stdout.splitlines()), {str(JOURNAL), str(INDEX)})
        self.assertIn("## J2 — Main", (self.root / JOURNAL).read_text())
        self.assertIn("## J3 — Topic", (self.root / JOURNAL).read_text())
        index = (self.root / INDEX).read_text()
        self.assertIn("| [J2](PORTING_JOURNAL.md#j2--main) | 2020-01-06 |", index)
        self.assertIn("| [J3](PORTING_JOURNAL.md#j3--topic) | 2020-01-08 |", index)
        self.assertEqual(self.git("status", "--porcelain").stdout, "")
        check = subprocess.run([sys.executable, "scripts/journal-index.py", "--check"], cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("checked " + tip, self.push().stdout)
        self.assertTrue(self.git("ls-remote", "--heads", "origin", "dani/fixture").stdout.startswith(tip))

    def test_dirty_topic_is_preserved_and_refused(self):
        unrelated = self.root / "unrelated.txt"
        unrelated.write_text("keep this staged edit\n")
        self.git("add", "unrelated.txt")
        before = self.git("status", "--porcelain").stdout
        original = self.git("rev-parse", "HEAD").stdout
        journal = (self.root / JOURNAL).read_bytes()
        result = self.push(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit or stash tracked changes", result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, original)
        self.assertEqual(self.git("status", "--porcelain").stdout, before)
        self.assertEqual((self.root / JOURNAL).read_bytes(), journal)

    def test_ambiguous_journal_is_not_repaired(self):
        original = (self.root / JOURNAL).read_text()
        (self.root / JOURNAL).write_text(original.replace("Main evidence.", "Edited upstream evidence."))
        self.commit("edit upstream evidence")
        tip = self.git("rev-parse", "HEAD").stdout
        result = self.push(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preserve it unchanged", result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, tip)
        self.assertIn("Edited upstream evidence.", (self.root / JOURNAL).read_text())

    def test_rejected_repair_commit_restores_original_files(self):
        hook = self.root / "scripts/git-hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho synthetic refusal >&2\nexit 1\n")
        hook.chmod(0o755)
        original = self.git("rev-parse", "HEAD").stdout
        files = [(self.root / path).read_bytes() for path in (JOURNAL, INDEX)]
        result = self.push(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("synthetic refusal", result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, original)
        self.assertEqual([(self.root / path).read_bytes() for path in (JOURNAL, INDEX)], files)
        self.assertEqual(self.git("diff", "--name-only").stdout, "")
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")

    def test_nonchecked_out_ref_never_rewrites_current_branch(self):
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("switch", "-q", "main")
        head = self.git("rev-parse", "HEAD").stdout
        self.assertIn("checked " + tip, self.push().stdout)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, head)
        self.assertEqual(self.git("rev-parse", "dani/fixture").stdout.strip(), tip)
