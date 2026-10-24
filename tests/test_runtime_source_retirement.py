"""Full builds retire only byte/GUID-verified authored predecessor staging."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build
from common import write


class RuntimeSourceRetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.work = self.root / "work"
        self.project = self.work / "lab-project"
        self.stage = self.project / "Assets/LabLoadingScene"
        self.stage.mkdir(parents=True)
        self.name = "runtime/input/PreviousOwner.cs"
        self.code = b"public sealed class PreviousOwner {}\n"
        self.guid = "a" * 32
        source = self.root / "tools/unity" / self.name
        source.parent.mkdir(parents=True)
        source.write_bytes(self.code)
        write(self.root / "recipe/runtime-sources.json", [self.name])
        write(self.root / "recipe/project-layout.json", {"runtime_source_guids": {self.name: self.guid}})
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture.invalid")
        self.git("add", "tools", "recipe")
        self.git("commit", "-qm", "fixture predecessor")
        self.commit = self.git("rev-parse", "HEAD").strip()
        write(self.work / "config/current-build.json", {"success": True, "source": {"commit": self.commit}})
        self.staged = self.stage / "PreviousOwner.cs"
        self.staged.write_bytes(self.code)
        self.meta = Path(str(self.staged) + ".meta")
        self.meta.write_text("fileFormatVersion: 2\nguid: " + self.guid + "\n")
        for name, value in (("ROOT", self.root), ("WORK", self.work)):
            context = patch.object(build, name, value)
            context.start()
            self.addCleanup(context.stop)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def test_verified_source_is_removed_with_reproducible_commit_and_guid_receipt(self):
        build.retire_staged_runtime_sources(self.project, [self.staged.name])
        self.assertFalse(self.staged.exists())
        self.assertFalse(self.meta.exists())
        self.assertEqual((self.root / "tools/unity" / self.name).read_bytes(), self.code)
        receipt = json.loads(next((self.work / "coordination/staging-retirements").glob("*.json")).read_text())
        self.assertEqual(receipt["previous_source_commit"], self.commit)
        self.assertEqual(receipt["removed"], [self.staged.name])
        self.assertEqual(receipt["sources"][0]["guid"], self.guid)

    def test_edited_source_or_guid_refuses_without_removing_files(self):
        for mutate in ("source", "guid"):
            with self.subTest(mutate=mutate):
                self.staged.write_bytes(self.code + (b"// local edit" if mutate == "source" else b""))
                self.meta.write_text("guid: " + ("b" * 32 if mutate == "guid" else self.guid) + "\n")
                with self.assertRaises(RuntimeError):
                    build.retire_staged_runtime_sources(self.project, [self.staged.name])
                self.assertTrue(self.staged.exists())
                self.assertTrue(self.meta.exists())

    def test_unknown_source_refuses_before_any_verified_source_is_removed(self):
        foreign = self.stage / "Foreign.cs"
        foreign.write_bytes(b"authored foreign bytes")
        with self.assertRaises(RuntimeError):
            build.retire_staged_runtime_sources(self.project, [self.staged.name, foreign.name])
        self.assertTrue(self.staged.exists())
        self.assertTrue(self.meta.exists())
        self.assertTrue(foreign.exists())

    def test_code_only_membership_still_refuses_unknown_sources(self):
        with patch.object(build, "runtime_sources", return_value=[]), self.assertRaisesRegex(RuntimeError, "Unlisted"):
            build.validate_runtime_source_membership(self.project)
        self.assertTrue(self.staged.exists())


if __name__ == "__main__":
    unittest.main()
