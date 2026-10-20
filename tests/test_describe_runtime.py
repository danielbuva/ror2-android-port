from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("ROR2LAB_TEST_ROOT", Path(__file__).resolve().parents[1]))
EDITOR_BIN = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin")
MCS = EDITOR_BIN / "mcs"
MONO = EDITOR_BIN / "mono"
HARNESS = None


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if "TMPDIR" in os.environ:
        env["TMPDIR"] = os.environ["TMPDIR"]
    return subprocess.run([str(MONO), str(HARNESS), *args], capture_output=True, text=True, env=env)


class ActualDescribeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        global HARNESS
        if not MCS.is_file() or not MONO.is_file():
            raise unittest.SkipTest("pinned Unity Mono compiler/runtime is unavailable")
        temp_root = Path(os.environ.get("TMPDIR", tempfile.gettempdir()))
        cls.build_temp = tempfile.TemporaryDirectory(dir=temp_root)
        HARNESS = Path(cls.build_temp.name) / "DescribeHarness.exe"
        sources = [
            ROOT / "tests" / "UnityStubs.cs",
            ROOT / "android" / "Assets" / "Editor" / "PlayerLinkerInputCapture.cs",
            ROOT / "tests" / "DescribeHarness.cs",
        ]
        subprocess.run(
            [str(MCS), "-out:" + str(HARNESS), *(str(path) for path in sources)],
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "build_temp"):
            cls.build_temp.cleanup()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", tempfile.gettempdir()))
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.input_dir = self.project / "Library" / "Bee" / "link-input"
        self.input_dir.mkdir(parents=True)
        self.work = self.root / "work"
        self.work.mkdir()
        self.source = self.input_dir / "Game.dll"
        self.source.write_bytes(b"real temporary assembly bytes")
        self.request = "runtime-test-001"
        self.snapshot_root = self.work / "lab-build" / "player-linker-inputs" / self.request / "assemblies"
        self.snapshot = self.snapshot_root / "Game.dll"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def describe(self) -> subprocess.CompletedProcess[str]:
        return invoke(
            "describe",
            str(self.input_dir),
            str(self.source),
            str(self.snapshot_root),
            str(self.work),
            self.request,
        )

    def prepare_output(self, work: Path | None = None) -> subprocess.CompletedProcess[str]:
        return invoke("prepare-output", str(work or self.work))

    def test_output_preparation_is_fresh_and_idempotent(self) -> None:
        first = self.prepare_output()
        self.assertEqual(first.returncode, 0, first.stderr)
        marker = self.work / "lab-build" / "player-linker-inputs" / "empty-linker.xml"
        expected = b'<?xml version="1.0" encoding="utf-8"?>\n<linker />\n'
        self.assertEqual(marker.read_bytes(), expected)
        second = self.prepare_output()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(marker.read_bytes(), expected)

    def test_output_symlink_is_refused_before_external_write(self) -> None:
        external = self.root / "external-output"
        external.mkdir()
        (self.work / "lab-build").mkdir()
        (self.work / "lab-build" / "player-linker-inputs").symlink_to(external, target_is_directory=True)
        result = self.prepare_output()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(external.iterdir()), [])

    def test_output_ancestor_symlink_is_refused_before_external_write(self) -> None:
        external = self.root / "external-ancestor"
        external.mkdir()
        (self.work / "lab-build").symlink_to(external, target_is_directory=True)
        result = self.prepare_output()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(external.iterdir()), [])

    def test_empty_marker_symlink_is_refused_without_modifying_target(self) -> None:
        output = self.work / "lab-build" / "player-linker-inputs"
        output.mkdir(parents=True)
        external = self.root / "external-marker"
        external.write_bytes(b"keep-existing-bytes")
        (output / "empty-linker.xml").symlink_to(external)
        result = self.prepare_output()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(external.read_bytes(), b"keep-existing-bytes")

    def test_fresh_snapshot_and_identical_reentry_execute_actual_describe(self) -> None:
        expected = hashlib.sha256(self.source.read_bytes()).hexdigest()
        first = self.describe()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout.strip(), f"{expected} {self.source.stat().st_size}")
        self.assertEqual(self.snapshot.read_bytes(), self.source.read_bytes())
        second = self.describe()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, first.stdout)

    def test_changed_existing_snapshot_is_refused(self) -> None:
        self.assertEqual(self.describe().returncode, 0)
        self.snapshot.write_bytes(b"tampered")
        changed = self.describe()
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("snapshot", changed.stderr.lower())

    def test_snapshot_symlink_is_refused(self) -> None:
        self.snapshot_root.mkdir(parents=True)
        external = self.root / "external.dll"
        external.write_bytes(self.source.read_bytes())
        self.snapshot.symlink_to(external)
        result = self.describe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symbolic link", result.stderr.lower())

    def test_existing_snapshot_symlink_ancestor_is_refused_before_outside_write(self) -> None:
        external = self.root / "external-work"
        external.mkdir()
        (self.work / "lab-build").symlink_to(external, target_is_directory=True)
        result = self.describe()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(external.iterdir()), [])

    def test_input_directory_and_root_reparse_points_are_refused(self) -> None:
        alias = self.project / "linked-input"
        alias.symlink_to(self.input_dir, target_is_directory=True)
        linked = invoke("ancestors", str(self.project), str(alias))
        self.assertNotEqual(linked.returncode, 0)
        project_alias = self.root / "project-alias"
        project_alias.symlink_to(self.project, target_is_directory=True)
        root_link = invoke("ancestors", str(project_alias), str(project_alias / "Library"))
        self.assertNotEqual(root_link.returncode, 0)


if __name__ == "__main__":
    unittest.main()
