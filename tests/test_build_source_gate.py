"""Whole-catalog builds stage only committed sources and record their commit (J738)."""

import subprocess
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import build
import whole_catalog


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


class BuildSourceGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "gate")
        git(self.root, "config", "user.name", "gate")
        for path in ("tools/unity/runtime/A.cs", "tools/catalog/Host.cs", "android/Assets/Editor/LabBuild.cs", "docs/notes.md"):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text("authored\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "synthetic")
        patcher = patch.object(build, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_clean_tree_records_the_commit(self):
        identity = build.build_source_identity()
        self.assertEqual(identity["commit"], git(self.root, "rev-parse", "HEAD").strip())
        self.assertEqual(identity["clean_paths"], list(build.BUILD_SOURCE_PATHS))

    def test_modified_or_untracked_build_sources_refuse(self):
        for path, content in (("tools/unity/runtime/A.cs", "draft\n"), ("tools/catalog/New.cs", "new\n"), ("android/Assets/Editor/LabBuild.cs", "draft\n")):
            with self.subTest(path=path):
                original = (self.root / path).read_text() if (self.root / path).exists() else None
                (self.root / path).write_text(content)
                with self.assertRaisesRegex(RuntimeError, "Uncommitted build sources.*" + Path(path).name):
                    build.build_source_identity()
                if original is None:
                    (self.root / path).unlink()
                else:
                    (self.root / path).write_text(original)

    def test_changes_outside_build_sources_are_allowed(self):
        (self.root / "docs/notes.md").write_text("edited\n")
        (self.root / "scratch.txt").write_text("untracked\n")
        self.assertIn("commit", build.build_source_identity())

    def test_build_integration_refuses_before_staging_and_when_head_moves(self):
        locks = dict(assert_build_unblocked=lambda: None, host_build_lock=lambda *a, **k: nullcontext())
        with patch.multiple("build_lock", **locks), patch.object(whole_catalog, "_build_integration") as staged:
            (self.root / "tools/catalog/Host.cs").write_text("draft\n")
            with self.assertRaisesRegex(RuntimeError, "Uncommitted build sources"):
                whole_catalog.build_integration(code_only=True)
            staged.assert_not_called()
            git(self.root, "checkout", "-q", "--", "tools/catalog/Host.cs")

            def moves_head(**kwargs):
                self.assertEqual(kwargs["source_identity"]["commit"], git(self.root, "rev-parse", "HEAD").strip())
                (self.root / "docs/notes.md").write_text("later\n")
                git(self.root, "commit", "-q", "-am", "later")
                return {}

            staged.side_effect = moves_head
            with self.assertRaisesRegex(RuntimeError, "changed during the build"):
                whole_catalog.build_integration(code_only=True)


if __name__ == "__main__":
    unittest.main()
