"""The parallel runner must retain unittest semantics, not just a green exit."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/host-tests.py"
SPEC = importlib.util.spec_from_file_location("host_test_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class HostTestRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "tests").mkdir()

    def module(self, name, source):
        (self.root / "tests" / (name + ".py")).write_text(textwrap.dedent(source))

    def run_suite(self, workers=2, *, compare=None, timeout=10):
        report = self.root / f"report-{workers}.json"
        command = [sys.executable, str(SCRIPT), "--root", str(self.root), "--workers", str(workers), "--timeout", str(timeout), "--report", str(report)]
        if compare:
            command += ["--compare", str(compare)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertTrue(report.is_file(), process.stdout + process.stderr)
        return process, json.loads(report.read_text()), report

    def test_serial_parallel_equal_with_all_outcomes_and_subtests(self):
        self.module(
            "test_outcomes",
            """
            import unittest
            class Outcomes(unittest.TestCase):
                def test_pass(self): pass
                def test_failure(self): self.fail('authored failure')
                def test_error(self): raise ValueError('authored error')
                @unittest.skip('authored skip')
                def test_skip(self): pass
                @unittest.expectedFailure
                def test_expected(self): self.fail('expected')
                @unittest.expectedFailure
                def test_unexpected(self): pass
                def test_subtests(self):
                    for case in ('pass', 'fail', 'error', 'skip'):
                        with self.subTest(case=case):
                            if case == 'fail': self.fail('subtest failure')
                            if case == 'error': raise ValueError('subtest error')
                            if case == 'skip': self.skipTest('subtest skip')
            """,
        )
        self.module("test_import_skip", "import unittest\nraise unittest.SkipTest('import skip')\n")
        first, serial, path = self.run_suite(1)
        second, parallel, _ = self.run_suite(3, compare=path)
        self.assertEqual((first.returncode, second.returncode), (1, 1))
        self.assertIn("Comparison passed", second.stdout)
        self.assertEqual(serial["discovered_ids"], parallel["discovered_ids"])
        events = [event for module in parallel["modules"] for event in module["events"]]
        self.assertEqual({event["outcome"] for event in events}, {"pass", "failure", "error", "skip", "expectedFailure", "unexpectedSuccess"})
        subtests = [event for event in events if "subtest_index" in event]
        self.assertEqual([event["subtest_index"] for event in subtests], [1, 2, 3, 4])
        self.assertEqual([event["outcome"] for event in subtests], ["pass", "failure", "error", "skip"])
        self.assertIn("(case='pass')", subtests[0]["id"])
        self.assertTrue(all(test["seconds"] >= 0 for module in parallel["modules"] for test in module["tests"]))
        self.assertIn("Slowest modules (including fixtures)", second.stdout)

    def test_module_and_class_fixtures_and_cleanup_run_once_in_order(self):
        for name in ("test_first", "test_second"):
            self.module(
                name,
                f"""
                from pathlib import Path
                import unittest
                log = Path({str(self.root / (name + ".log"))!r})
                def record(value):
                    with log.open('a') as stream: stream.write(value + '\\n')
                def setUpModule():
                    record('module setup')
                    unittest.addModuleCleanup(record, 'module cleanup')
                def tearDownModule(): record('module teardown')
                class Fixture(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls):
                        record('class setup')
                        cls.addClassCleanup(record, 'class cleanup')
                    @classmethod
                    def tearDownClass(cls): record('class teardown')
                    def test_a(self): record('a')
                    def test_b(self): record('b')
                """,
            )
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 0, process.stderr)
        for name in ("test_first", "test_second"):
            self.assertEqual(
                (self.root / (name + ".log")).read_text().splitlines(),
                ["module setup", "class setup", "a", "b", "class teardown", "class cleanup", "module teardown", "module cleanup"],
            )
        self.assertEqual(sum(module["tests_run"] for module in report["modules"]), 4)

    def test_fixture_errors_and_skips_are_reported_not_dropped(self):
        for name, statement in (("test_error", "raise RuntimeError('setup failed')"), ("test_skip", "raise unittest.SkipTest('class skipped')")):
            self.module(
                name,
                f"""
                import unittest
                class Fixture(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls): {statement}
                    def test_not_started(self): raise AssertionError('unreachable')
                """,
            )
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(len(report["discovered_ids"]), 2)
        self.assertEqual(sum(module["tests_run"] for module in report["modules"]), 0)
        self.assertEqual({event["outcome"] for module in report["modules"] for event in module["events"]}, {"error", "skip"})

    def test_custom_load_tests_suite_is_preserved(self):
        self.module(
            "test_custom",
            """
            import unittest
            ready = False
            class Fixture(unittest.TestCase):
                def test_loaded(self): self.assertTrue(ready)
            class CustomSuite(unittest.TestSuite):
                def run(self, result, debug=False):
                    global ready
                    ready = True
                    return super().run(result, debug)
            def load_tests(loader, tests, pattern):
                return CustomSuite([Fixture('test_loaded')])
            """,
        )
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report["discovered_ids"], ["test_custom.Fixture.test_loaded"])

    def test_fixture_may_shadow_id_without_losing_unittest_identity(self):
        self.module(
            "test_shadow",
            """
            import unittest
            class Fixture(unittest.TestCase):
                def setUp(self): self.id = 42
                def test_shadow(self):
                    with self.subTest(value=self.id): self.assertEqual(self.id, 42)
            """,
        )
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 0, process.stderr)
        events = report["modules"][0]["events"]
        self.assertEqual(events[0]["id"], "test_shadow.Fixture.test_shadow (value=42)")
        self.assertEqual(events[1]["id"], "test_shadow.Fixture.test_shadow")

    def test_fixture_holder_cannot_reuse_a_completed_test_identity(self):
        self.module(
            "test_fixture_ids",
            """
            import unittest
            class A(unittest.TestCase):
                def test_pass(self): pass
            class B(unittest.TestCase):
                @classmethod
                def setUpClass(cls): raise unittest.SkipTest('authored class skip')
                def test_not_started(self): pass
            """,
        )
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual([event["id"] for event in report["modules"][0]["events"]], ["test_fixture_ids.A.test_pass", "setUpClass (test_fixture_ids.B)"])

    def test_worker_temporary_directories_are_unique_and_removed(self):
        for name in ("test_first", "test_second"):
            self.module(
                name,
                f"""
                import os, tempfile, unittest
                from pathlib import Path
                class Fixture(unittest.TestCase):
                    def test_isolation(self):
                        root = Path(tempfile.gettempdir())
                        self.assertEqual(str(root), os.environ['TMPDIR'])
                        marker = root / 'same-filename'
                        self.assertFalse(marker.exists())
                        marker.write_text('authored')
                        Path({str(self.root / (name + ".tmp"))!r}).write_text(str(root))
                """,
            )
        process, _, _ = self.run_suite()
        self.assertEqual(process.returncode, 0, process.stderr)
        paths = [Path((self.root / (name + ".tmp")).read_text()) for name in ("test_first", "test_second")]
        self.assertNotEqual(*paths)
        self.assertTrue(all(not path.exists() for path in paths))

    def test_shared_source_build_modules_do_not_overlap(self):
        for name in ("test_music_output_observer", "test_observer_stage_hook"):
            self.module(
                name,
                f"""
                import os, time, unittest
                from pathlib import Path
                class Fixture(unittest.TestCase):
                    def test_lock(self):
                        lock = Path({str(self.root / "shared-build")!r})
                        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        try: time.sleep(0.05)
                        finally:
                            os.close(descriptor)
                            lock.unlink()
                """,
            )
        process, report, _ = self.run_suite(4)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(report["modules"]), 2)

    def test_import_failure_is_nonzero_and_has_failed_test_identity(self):
        self.module("test_broken", "raise RuntimeError('authored import failure')\n")
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 1)
        self.assertIn("test_broken", report["discovered_ids"][0])
        self.assertIn("authored import failure", process.stderr)

    def test_crashed_worker_is_nonzero_without_hanging(self):
        self.module("test_crash", "import os, unittest\nclass Fixture(unittest.TestCase):\n    def test_crash(self): os._exit(17)\n")
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 1)
        self.assertIn("worker exited 17", process.stderr)
        self.assertTrue(report["infrastructure_errors"])

    def test_timeout_is_nonzero_and_terminates_worker(self):
        self.module("test_timeout", "import time, unittest\nclass Fixture(unittest.TestCase):\n    def test_wait(self): time.sleep(20)\n")
        process, report, _ = self.run_suite(timeout=0.1)
        self.assertEqual(process.returncode, 1)
        self.assertIn("exceeded 0.1 seconds", process.stderr)
        self.assertTrue(report["infrastructure_errors"])

    def test_comparison_fails_when_tests_or_outcomes_change(self):
        source = "import unittest\nclass Fixture(unittest.TestCase):\n    def test_control(self): {}\n"
        self.module("test_control", source.format("pass"))
        first, _, path = self.run_suite(1)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.module("test_control", source.format("self.skipTest('changed')"))
        changed, report, _ = self.run_suite(2, compare=path)
        self.assertEqual(changed.returncode, 1)
        self.assertTrue(report["comparison_errors"])
        self.module("test_added", source.format("pass"))
        added, report, _ = self.run_suite(2, compare=path)
        self.assertEqual(added.returncode, 1)
        self.assertIn("discovered test IDs differ", report["comparison_errors"])

    def test_empty_discovery_is_not_a_green_fast_path(self):
        process, report, _ = self.run_suite()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report["discovered_ids"], [])

    def test_nonfinite_timeout_cannot_disable_worker_deadline(self):
        for value in ("nan", "inf", "-inf", "0", "-1"):
            with self.subTest(value=value):
                process = subprocess.run(
                    [sys.executable, str(SCRIPT), "--root", str(self.root), f"--timeout={value}"], capture_output=True, text=True, timeout=5
                )
                self.assertEqual(process.returncode, 2)
                self.assertIn("positive and finite", process.stderr)
