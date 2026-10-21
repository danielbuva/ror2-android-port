import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys

import phone_wrapper_oracle as oracle


class WrapperOracleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        for name in oracle.SOURCES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// authored staging control\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "test: fixture"], cwd=self.root, check=True)
        self.work = self.root / "work"
        self.project = self.work / "rebuild/phone-wrapper-oracle/attempt/project"
        oracle.stage(self.project, self.root)

    def test_stage_refuses_overwrite_and_project_drift(self):
        oracle.validate_project(self.project, self.root, self.work)
        with self.assertRaises(FileExistsError):
            oracle.stage(self.project, self.root)
        staged = self.project / "Assets/Editor/WrapperMetadataOracle.cs"
        staged.write_text("different source")
        with self.assertRaisesRegex(ValueError, "Staged oracle source"):
            oracle.validate_project(self.project, self.root, self.work)
        staged.write_bytes((self.root / oracle.READER).read_bytes())
        (self.project / "Assets/foreign.dll").write_bytes(b"foreign")
        with self.assertRaisesRegex(ValueError, "Foreign oracle asset"):
            oracle.validate_project(self.project, self.root, self.work)

    def test_stage_refuses_symlinked_ancestors_before_outside_writes(self):
        for depth in range(4):
            with self.subTest(depth=depth):
                work = self.root / ("redirected-work-" + str(depth))
                outside = self.root / ("outside-" + str(depth))
                outside.mkdir()
                chain = [work, work / "rebuild", work / "rebuild/phone-wrapper-oracle", work / "rebuild/phone-wrapper-oracle/attempt"]
                target = chain[depth]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "without links"):
                    oracle.stage(chain[-1] / "project", self.root, work)
                self.assertEqual(list(outside.iterdir()), [])

    def test_stage_rechecks_created_parent_before_writing_each_file(self):
        project = self.work / "rebuild/phone-wrapper-oracle/replaced-parent/project"
        outside = self.root / "outside-replaced-parent"
        outside.mkdir()
        original = oracle.write_owned

        def replace_then_write(path, data, work):
            parent = project / "Assets/Editor"
            parent.rmdir()
            parent.symlink_to(outside, target_is_directory=True)
            original(path, data, work)

        with patch.object(oracle, "write_owned", replace_then_write), self.assertRaisesRegex(ValueError, "without links"):
            oracle.stage(project, self.root, self.work)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_drift_and_project_escape_refuse(self):
        (self.root / oracle.SOURCES[0]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "source drift"):
            oracle.validate_project(self.project, self.root, self.work)
        alias = self.root / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "owned isolated"):
            oracle.validate_project(alias, self.root, self.work)

    def test_live_mutex_contention_refuses_without_starting_an_editor(self):
        lock = self.work / "coordination/unity-build.lock"
        lock.parent.mkdir(parents=True)
        editor = self.root / "Contents/MacOS/AuthoredEditor"
        editor.parent.mkdir(parents=True)
        editor.write_bytes(b"authored binary pin control; must never execute")
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import fcntl,sys; f=open(sys.argv[1],'a+'); fcntl.flock(f,fcntl.LOCK_EX); print('held',flush=True); sys.stdin.readline()",
                str(lock),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "held")
            with patch.dict("os.environ", UNITY_EDITOR=str(editor)), patch.object(oracle, "BINARY_SHA256", oracle.sha(editor)):
                with self.assertRaisesRegex(RuntimeError, "retained attempt"):
                    oracle.run_editor(self.project, self.root, self.work)
            self.assertIsNone(holder.poll())
            receipt = json.loads(next(self.project.parent.glob("editor-check-*/receipt.json")).read_text())
            self.assertFalse(receipt["success"])
            self.assertIsNone(receipt["exit_code"])
            self.assertIn("Timed out waiting", receipt["error"])
            self.assertIsNone(receipt["oracle_sha256"])
        finally:
            holder.stdin.close()
            holder.wait(timeout=5)
            holder.stdout.close()

    def test_report_requires_supported_query_coverage_and_preserves_unknowns(self):
        root = dict(
            persistentTypeID=10,
            name="Object",
            nativeNamespace="",
            qualifiedName="Object",
            hasParent=False,
            parentID=0,
            flags=0,
            wrapperQueried=False,
            wrapperReturnedNull=False,
            wrapperName="",
            skipReason="native-object-root",
        )
        child = dict(
            root,
            persistentTypeID=11,
            name="Authored",
            qualifiedName="Authored",
            hasParent=True,
            parentID=10,
            wrapperQueried=True,
            wrapperReturnedNull=True,
            skipReason="",
        )
        report = dict(
            schema=1,
            unity=oracle.VERSION,
            source_commit="c",
            queryProfile="concrete-object-descendants-v1",
            root_generation_qualified=False,
            game_inputs=False,
            records=[root, child],
        )
        oracle.validate_report(report, "c")
        for mutation in ({"wrapperQueried": False}, {"skipReason": "abstract"}, {"parentID": 11}):
            invalid = json.loads(json.dumps(report))
            invalid["records"][1].update(mutation)
            with self.assertRaises(ValueError):
                oracle.validate_report(invalid, "c")


class WrapperOracleApiTests(unittest.TestCase):
    def test_actual_collector_with_independent_api_and_unsafe_query_controls(self):
        contents = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
        mono, compiler = contents / "bin/mono", contents / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("Optional exact-editor Mono/Roslyn absent")
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "oracle.exe"
            built = subprocess.run(
                [
                    str(mono),
                    str(compiler),
                    "-nologo",
                    "-out:" + str(output),
                    str(repo / oracle.READER),
                    str(repo / "tests/fixtures/WrapperMetadataOracleHost.cs"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(mono), str(output)], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: scope", run.stdout)
