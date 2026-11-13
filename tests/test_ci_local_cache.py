"""Reusable CI inputs never reuse a worktree or a previous check result."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_local_cache", ROOT / "scripts/ci-local-cache.py")
CACHE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CACHE)


class CiLocalCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ci-cache-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        self.env = os.environ.copy()
        for name in subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True).splitlines():
            self.env.pop(name, None)
        self.env.update(GIT_AUTHOR_NAME="CI fixture", GIT_COMMITTER_NAME="CI fixture", GIT_AUTHOR_EMAIL="ci-fixture", GIT_COMMITTER_EMAIL="ci-fixture")
        self.git("init", "-q")
        (self.repo / ".gitignore").write_text("work/\n.local/\n")
        (self.repo / "tracked.txt").write_text("first committed value")
        (self.repo / "tools").mkdir()
        (self.repo / "tools/lab-requirements.txt").write_text("")
        self.first = self.commit()
        self.git("update-ref", "refs/remotes/origin/main", self.first)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], env=self.env, stderr=subprocess.STDOUT, text=True).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_warm_checkout_has_exact_target_and_no_source_or_previous_run_state(self):
        (self.repo / "tracked.txt").write_text("second committed value")
        second = self.commit()
        (self.repo / "tracked.txt").write_text("uncommitted change")
        (self.repo / "untracked.txt").write_text("untracked fixture")
        (self.repo / "work").mkdir()
        (self.repo / "work/local.json").write_text("ignored fixture")
        self.git("config", "ci.fixture", "source-only")
        one, two = self.root / "one", self.root / "two"
        CACHE.checkout(self.repo, one, second, self.first)
        (one / "tracked.txt").write_text("previous-run mutation")
        (one / "stale-result.txt").write_text("not reusable")
        CACHE.checkout(self.repo, two, self.first, self.first)
        self.assertEqual((two / "tracked.txt").read_text(), "first committed value")
        for name in ("work", "untracked.txt", "stale-result.txt"):
            self.assertFalse((two / name).exists())
        self.assertEqual(CACHE.git(two, "rev-parse", "HEAD"), self.first)
        self.assertEqual(CACHE.git(two, "status", "--porcelain", "--ignored"), "")
        self.assertNotIn("source-only", CACHE.git(two, "config", "--local", "--list"))
        self.assertEqual(CACHE.git(two, "rev-parse", "origin/main"), self.first)
        self.assertEqual((self.repo / "tracked.txt").read_text(), "uncommitted change")

    def test_ten_simultaneous_checkouts_share_objects_but_not_worktrees(self):
        destinations = [self.root / f"run-{index}" for index in range(10)]
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(lambda path: CACHE.checkout(self.repo, path, self.first, self.first), destinations))
        alternates = []
        for path in destinations:
            self.assertEqual(CACHE.git(path, "rev-parse", "HEAD"), self.first)
            self.assertEqual(CACHE.git(path, "status", "--porcelain", "--ignored"), "")
            alternates.append((path / ".git/objects/info/alternates").read_text())
        self.assertEqual(len(set(alternates)), 1)
        self.assertFalse((CACHE.cache_root(self.repo) / "source.git/tracked.txt").exists())

    def test_empty_tree_base_is_available_for_initial_push(self):
        empty = CACHE.git(self.repo, "hash-object", "-t", "tree", "--stdin", input="")
        destination = self.root / "initial"
        CACHE.checkout(self.repo, destination, self.first, empty)
        self.assertIn("tracked.txt", CACHE.git(destination, "diff", "--name-only", empty, self.first))

    def test_key_tracks_requirements_and_interpreter_abi_platform(self):
        identity = CACHE.interpreter_identity()
        initial = CACHE.requirements_key(b"package==1\n", identity)
        self.assertEqual(initial, CACHE.requirements_key(b"package==1\n", identity))
        self.assertNotEqual(initial, CACHE.requirements_key(b"package==2\n", identity))
        for field in ("executable", "version", "abi", "platform", "machine", "cache_tag"):
            self.assertNotEqual(initial, CACHE.requirements_key(b"package==1\n", identity | {field: "different"}))
        for unkeyed in ("-r other.txt", "-e .", "package @ file:///fixture", "package>=1"):
            with self.assertRaises(RuntimeError):
                CACHE.pinned_requirements(unkeyed)

    def fake_install(self, path, requirements, pins):
        (path / "bin").mkdir()
        (path / "bin/python").symlink_to(sys.executable)
        time.sleep(0.02)

    def cleanup_environments(self):
        environments = CACHE.cache_root(self.repo) / "venvs"
        for path in environments.iterdir():
            if path.is_dir():
                CACHE.remove_environment(path)

    def test_simultaneous_environment_build_publishes_once_and_reuses_pins(self):
        self.addCleanup(self.cleanup_environments)
        with patch.object(CACHE, "install_environment", side_effect=self.fake_install) as install, patch.object(CACHE, "dependency_inventory", return_value={}):
            with ThreadPoolExecutor(max_workers=10) as executor:
                pythons = list(executor.map(lambda _: CACHE.environment(self.repo, self.repo), range(10)))
            self.assertEqual(install.call_count, 1)
            self.assertEqual(len(set(pythons)), 1)
            (self.repo / "tools/lab-requirements.txt").write_text("# tracked input changed\n")
            changed = CACHE.environment(self.repo, self.repo)
            self.assertNotEqual(pythons[0], changed)
            self.assertEqual(install.call_count, 2)

    def test_incomplete_environment_is_rebuilt_and_changed_installs_are_rejected(self):
        self.addCleanup(self.cleanup_environments)
        root = CACHE.private_directory(CACHE.cache_root(self.repo) / "venvs")
        key = CACHE.requirements_key(b"", CACHE.interpreter_identity())
        incomplete = CACHE.private_directory(root / key)
        (incomplete / "stale").write_text("interrupted build")
        with patch.object(CACHE, "install_environment", side_effect=self.fake_install) as install, patch.object(CACHE, "dependency_inventory", return_value={}):
            python = CACHE.environment(self.repo, self.repo)
            self.assertEqual(install.call_count, 1)
            self.assertFalse((incomplete / "stale").exists())
            self.assertTrue((python.parent.parent / "complete.json").is_file())
        with patch.object(CACHE, "dependency_inventory", return_value={"unexpected": "1"}):
            with self.assertRaisesRegex(RuntimeError, "installed metadata changed"):
                CACHE.environment(self.repo, self.repo)

    def test_symlink_cache_and_lock_are_rejected_without_touching_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        cache = self.repo / ".git/ci-cache"
        cache.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            CACHE.cache_root(self.repo)
        self.assertEqual(list(outside.iterdir()), [])
        cache.unlink()
        CACHE.cache_root(self.repo)
        lock_target = outside / "sentinel"
        lock_target.write_text("untouched")
        (cache / "source.lock").symlink_to(lock_target)
        with self.assertRaises(OSError):
            CACHE.checkout(self.repo, self.root / "unsafe", self.first, self.first)
        self.assertEqual(lock_target.read_text(), "untouched")

    def test_nested_source_symlink_and_changed_git_config_are_rejected(self):
        CACHE.checkout(self.repo, self.root / "first", self.first, self.first)
        store = CACHE.cache_root(self.repo) / "source.git"
        outside = self.root / "outside"
        outside.mkdir()
        (store / "objects/unsafe").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "unsafe CI source store"):
            CACHE.checkout(self.repo, self.root / "unsafe", self.first, self.first)
        (store / "objects/unsafe").unlink()
        CACHE.git(store, "config", "alias.fixture", "!false")
        with self.assertRaisesRegex(RuntimeError, "unexpected local Git configuration"):
            CACHE.checkout(self.repo, self.root / "unsafe", self.first, self.first)
        self.assertEqual(list(outside.iterdir()), [])

    def test_environment_directory_links_may_not_escape_the_cache(self):
        environment = self.root / "environment"
        environment.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (environment / "lib").mkdir()
        (environment / "lib64").symlink_to(environment / "lib", target_is_directory=True)
        CACHE.validate_environment_paths(environment)
        (environment / "lib/python").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "unsafe CI environment directory"):
            CACHE.validate_environment_paths(environment)

    def test_symlink_environment_is_rejected(self):
        environments = CACHE.private_directory(CACHE.cache_root(self.repo) / "venvs")
        key = CACHE.requirements_key(b"", CACHE.interpreter_identity())
        target = self.root / "outside"
        target.mkdir()
        (environments / key).symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "unsafe CI environment"):
            CACHE.environment(self.repo, self.repo)
        self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
