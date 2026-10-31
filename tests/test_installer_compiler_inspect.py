"""Synthetic retained-log fixtures; no Android or game input."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("compiler_inspect", Path(__file__).resolve().parents[1] / "scripts/lab-installer-compiler-inspect.py")
INSPECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECT)
SOURCE = "a" * 40
RUN = "123456"
SECRET = "/synthetic-private-root/secret-device-id"


class CompilerInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordination = Path(self.temp.name) / "coordination"
        self.root = self.coordination / "lab-runner/toolhost"
        self.root.mkdir(parents=True)
        self.run = self.root.parent / RUN
        self.run.mkdir()
        self.log = self.run / "output.log"
        self.log.write_text(
            f"$ git -C {SECRET} fetch -q origin {SOURCE}\n"
            f"$ {SECRET}/.local/worktrees/lab-run-{RUN}/.local/lab-venv/bin/python scripts/lab-installer-updates.py --allow-test-installs --allow-test-notifications\n"
            "FAIL check-for-updates phase=baseline-N-install reason=installer-build-error\n"
        )
        self.capture = self.coordination / "installer-update-acceptance/run-abcdefgh"
        self.capture.mkdir(parents=True)
        self.record(1, "resolve-source-commit", SOURCE + "\n", phase="setup")
        self.record(10, "device-state-read", json.dumps({"state": "ERROR", "message": SECRET}))
        self.record(12, "device-apk-javac-log", INSPECT.PREFIX + "warning: source value 8 is obsolete\n" + SECRET)
        self.record(
            13,
            "device-apk-dex-log",
            INSPECT.PREFIX
            + f'Error in {SECRET}/bootstrap.jar:dev/ror2owner/bootstrap/PayloadBootstrapActivity$LocalAssetClient.class: java.lang.NullPointerException: Cannot invoke "String.length()" because "<parameter1>" is null\nCompilationFailedException\n',
        )

    def record(self, sequence, category, output, phase=INSPECT.PHASE):
        stem = self.capture / f"{sequence:05d}-{category}"
        stem.with_suffix(".json").write_text(json.dumps({"category": category, "phase": phase, "returncode": 0, "outcome": "returned"}))
        stem.with_suffix(".stdout.log").write_text(output)

    def invoke(self):
        return INSPECT.inspect(self.root, SOURCE, RUN)

    def test_classifies_named_d8_error_without_leaking_content(self):
        result = self.invoke()
        self.assertFalse(result["direct_run_id_binding"])
        self.assertEqual(result["binding"], "unique-source-plus-run-log")
        dex = result["logs"][1]
        self.assertEqual(dex["categories"], ["null-pointer", "d8-compilation-failed", "null-string-length"])
        self.assertEqual(dex["authored_classes"], ["PayloadBootstrapActivity$LocalAssetClient"])
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn("parameter1", json.dumps(result))

    def test_unknown_classes_and_messages_are_not_echoed(self):
        result = INSPECT.classify(SECRET + "/Proprietary$Secret.class: unknown " + SECRET)
        self.assertEqual(result["authored_classes"], [])
        self.assertEqual(result["categories"], ["unclassified"])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_anonymous_class_and_javac_categories(self):
        result = INSPECT.classify(
            "bootstrap.jar:dev/ror2owner/bootstrap/PayloadBootstrapActivity$1.class: java.lang.NullPointerException\n"
            + SECRET
            + ":7: error: cannot find symbol"
        )
        self.assertEqual(result["authored_classes"], ["PayloadBootstrapActivity$1"])
        self.assertIn("java-symbol-not-found", result["categories"])

    def test_retention_anonymous_classes_are_public_allowlist_only(self):
        for name in ("ProfileRetentionProvider$1", "ProfileRetentionProvider$2", "ProfileStore$Manifest", "PayloadStore$Source"):
            result = INSPECT.classify(SECRET + "/bootstrap.jar:dev/ror2owner/bootstrap/" + name + ".class: java.lang.NullPointerException")
            self.assertEqual(result["authored_classes"], [name])
        self.assertEqual(INSPECT.classify("/ProfileRetentionProvider$Private.class: failure")["authored_classes"], [])

    def test_same_source_multiple_captures_refuse(self):
        other = self.capture.with_name("run-ijklmnop")
        other.mkdir()
        for p in self.capture.glob("00001-*"):
            (other / p.name).write_bytes(p.read_bytes())
        with self.assertRaisesRegex(INSPECT.Refused, "ambiguous"):
            self.invoke()

    def test_wrong_source_and_wrong_run_refuse(self):
        self.log.write_text(self.log.read_text().replace(SOURCE, "b" * 40))
        with self.assertRaisesRegex(INSPECT.Refused, "mismatch"):
            self.invoke()

    def test_wrong_acceptance_arguments_refuse(self):
        self.log.write_text(self.log.read_text().replace("--allow-test-installs", "--host-only"))
        with self.assertRaisesRegex(INSPECT.Refused, "mismatch"):
            self.invoke()

    def test_path_traversal_refuses(self):
        for source, run in ((SOURCE, "../" + RUN), ("../" + SOURCE, RUN)):
            with self.assertRaisesRegex(INSPECT.Refused, "invalid"):
                INSPECT.inspect(self.root, source, run)

    def test_capture_log_symlink_refuses(self):
        target = self.capture / "00013-device-apk-dex-log.stdout.log"
        target.unlink()
        target.symlink_to(self.log)
        with self.assertRaisesRegex(INSPECT.Refused, "unavailable"):
            self.invoke()

    def test_run_directory_symlink_refuses(self):
        alias = self.root.parent / "999"
        alias.symlink_to(self.run, target_is_directory=True)
        with self.assertRaisesRegex(INSPECT.Refused, "unavailable"):
            INSPECT.inspect(self.root, SOURCE, "999")

    def test_oversized_log_refuses(self):
        target = self.capture / "00013-device-apk-dex-log.stdout.log"
        target.write_bytes(b"x" * (INSPECT.LIMIT + 1))
        with self.assertRaisesRegex(INSPECT.Refused, "unavailable"):
            self.invoke()

    def test_wrong_phase_failed_command_and_capture_marker_refuse(self):
        path = self.capture / "00013-device-apk-dex-log.json"
        original = json.loads(path.read_text())
        for key, value in (("phase", "setup"), ("returncode", -9), ("category", "other")):
            path.write_text(json.dumps({**original, key: value}))
            with self.assertRaises(INSPECT.Refused):
                self.invoke()
        path.write_text(json.dumps(original))
        path.with_suffix(".stdout.log").write_text(SECRET)
        with self.assertRaisesRegex(INSPECT.Refused, "capture-missing"):
            self.invoke()

    def test_malformed_json_cli_never_prints_exception_or_private_text(self):
        path = self.capture / "00013-device-apk-dex-log.json"
        path.write_text(SECRET)
        output = io.StringIO()
        with patch.dict(os.environ, {"LAB_TOOLHOST_ROOT": str(self.root)}), redirect_stdout(output):
            self.assertEqual(INSPECT.main(["--source", SOURCE, "--run", RUN]), 1)
        self.assertEqual(json.loads(output.getvalue()), {"status": "refused", "reason": "malformed-or-unavailable-record"})

    def test_no_root_cli_refuses(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            self.assertEqual(INSPECT.main(["--source", SOURCE, "--run", RUN]), 1)
        self.assertEqual(json.loads(output.getvalue())["reason"], "lab-root-required")


if __name__ == "__main__":
    unittest.main()
