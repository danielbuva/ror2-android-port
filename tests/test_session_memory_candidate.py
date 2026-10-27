"""Synthetic bridge tests; no real build, Unity, APK, key or Android access."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/lab/session_memory_candidate.py"
COMMIT = "a" * 40
MEMBER_HASH = "b" * 64


class CandidateBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.work = self.root / "work"
        self.work.mkdir()
        self.receipt = "work/coordination/dots-memory/candidate.json"
        self.lane = self.root / ".local/build-lanes/test-memory"
        self.events = []
        self.payload = {"authored.dat": MEMBER_HASH, "authored.dat.manifest": "c" * 64}
        self.common = types.ModuleType("common")
        self.common.ROOT, self.common.WORK = self.root, self.work
        self.common.read = lambda p: json.loads(Path(p).read_text())
        self.common.write = self.write
        self.common.sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
        self.common.digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        adapter = types.ModuleType("session_memory_batch")
        adapter._receipt_path = self.receipt_path
        adapter._runner_context = lambda env: self.record("runner-lease", ("synthetic-device", self.root, "123"))
        self.lanes = types.ModuleType("build_lanes")
        self.lanes.create = self.create_lane
        self.lanes.dispatch = self.dispatch
        self.lanes.location = lambda name, root: self.lane
        selectors = types.ModuleType("device_context")
        self.selection = (None, None)
        selectors.command_selectors = lambda: self.selection
        selectors.set_command_selector = self.set_selection
        self.owner = types.ModuleType("alpha_stability_batch")
        self.runtime_root = "/storage/emulated/0/Android/data/dev.ror2lab.arm64/files"
        self.runtime_reads = 0
        self.hash_reads = 0
        self.device = types.SimpleNamespace(
            owned=lambda: {"apk": str(self.old_apk), "apk_sha256": self.old_hash},
            read_receipt=self.read_device_receipt,
            sh=self.device_shell,
        )
        self.owner._device = lambda serial: self.record("device", self.device)
        self.owner._idle_readback = lambda device, expected: self.record("initial", {"apk_sha256": expected})
        self.owner._terminal_readback = lambda serial, expected: self.record(("terminal", expected), {"apk_sha256": expected, "oled_asleep": True})
        patcher = mock.patch.dict(
            sys.modules,
            {
                "common": self.common,
                "session_memory_batch": adapter,
                "build_lanes": self.lanes,
                "device_context": selectors,
                "alpha_stability_batch": self.owner,
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        spec = importlib.util.spec_from_file_location("synthetic_session_memory_candidate", SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.child = mock.patch.object(self.module.subprocess, "run", side_effect=self.child_run)
        self.child.start()
        self.addCleanup(self.child.stop)
        self.old_apk = self.work / "build-cache/old/authored.bin"
        self.old_apk.parent.mkdir(parents=True)
        self.old_apk.write_bytes(b"authored old artifact fixture")
        self.old_hash = self.common.sha(self.old_apk)
        self.write(self.old_apk.parent / "result.json", {"apk_sha256": self.old_hash, "payload": self.payload})
        self.new_apk = self.work / "build-cache/lane-test-memory/authored.bin"
        self.new_apk.parent.mkdir(parents=True)
        self.new_apk.write_bytes(b"authored candidate artifact fixture")
        self.new_hash = self.common.sha(self.new_apk)
        self.artifact = {
            "success": True,
            "errors": 0,
            "source": {"commit": COMMIT},
            "apk": str(self.new_apk),
            "apk_sha256": self.new_hash,
            "payload": self.payload,
        }

    def record(self, event, result=None):
        self.events.append(event)
        return result

    def write(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def receipt_path(self, value, *, existing=False):
        path = self.root / value
        if path.exists() != existing:
            raise ValueError("wrong fixture receipt existence")
        return path

    def set_selection(self, cli, env):
        self.selection = (cli, env)

    def read_device_receipt(self, name):
        if name == "sync.json":
            return {"runtime_path": self.runtime_root, "files": [{"name": "authored.dat", "sha256": MEMBER_HASH}]}
        self.assertEqual(name, "runtime.json")
        self.runtime_reads += 1  # Actual Device owner validates grammar and backing.
        return {"persistentDataPath": self.runtime_root}

    def device_shell(self, *arguments, **kwargs):
        # Any scanner, write, transfer or payload repair fails this fixture.
        self.assertEqual(arguments, ("sha256sum", self.runtime_root + "/payload/authored.dat"))
        self.assertEqual(kwargs, {"check": False})
        self.record(arguments)
        self.hash_reads += 1
        return MEMBER_HASH + "  " + arguments[1]

    def create_lane(self, name, root):
        self.record("create")
        self.write(self.lane / "checkout/work/whole-catalog-code-base.json", {"payload": self.payload})
        return {"checkout": str(self.lane / "checkout"), "complete": True}

    def dispatch(self, name, arguments, root):
        self.record(tuple(arguments))
        os.write(1, b"PRIVATE native owner stdout\n")
        os.write(2, b"PRIVATE native owner stderr\n")
        if arguments[0] == "prototype":
            self.write(self.lane / "latest-build.json", self.artifact)
        return 0

    def child_run(self, arguments, **kwargs):
        if arguments[0] == "git":
            return subprocess.CompletedProcess(arguments, 0, COMMIT + "\n", "")
        self.record(tuple(arguments))
        self.assertEqual(arguments[1:3], ["install", "--device"])
        self.assertNotIn("reset", arguments)
        self.assertNotIn("sync-data", arguments)
        return subprocess.CompletedProcess(arguments, 0)

    def build(self):
        return self.module.run("build", lane="test-memory", expected_source_commit=COMMIT, receipt=self.receipt)

    def prepare_install(self):
        self.candidate_path = "work/coordination/dots-memory/build.json"
        self.write(
            self.root / self.candidate_path,
            dict(success=True, mode="build", source_commit=COMMIT, lane="test-memory", artifact=self.artifact, payload_sha256=self.common.digest(self.payload)),
        )
        return self.common.sha(self.root / self.candidate_path)

    def install(self, digest):
        return self.module.run(
            "install",
            lane="test-memory",
            expected_source_commit=COMMIT,
            receipt=self.receipt,
            candidate_receipt=self.candidate_path,
            expected_candidate_receipt_sha256=digest,
            expected_current_apk_sha256=self.old_hash,
        )

    def test_build_uses_only_normal_isolated_owner_operations(self):
        result = self.build()
        self.assertTrue(result["success"])
        self.assertEqual(
            self.events,
            ["create", ("editor", "--target", "lab", "--action", "open"), ("preflight", "--host-only"), ("prototype", "--action", "whole-catalog-code-build")],
        )
        self.assertEqual(result["apk_sha256"], self.new_hash)
        self.assertEqual(result["payload_file_count"], 2)
        self.assertTrue(self.lane.exists())  # Persistent lane, not temporary job worktree.
        self.assertNotIn("PRIVATE", json.dumps(result))
        log = (self.root / self.receipt).with_suffix(".log").read_text()
        self.assertIn("PRIVATE native owner stdout", log)
        self.assertIn("PRIVATE native owner stderr", log)

    def test_lane_space_refusal_has_no_fallback(self):
        self.lanes.create = mock.Mock(side_effect=RuntimeError("Less than 100 GiB free"))
        result = self.build()
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "lane-create")
        self.assertEqual(self.events, [])

    def test_iteration_artifact_is_refused(self):
        self.artifact["iteration"] = {"mode": "export-splice"}
        result = self.build()
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "published-artifact")

    def test_changed_frozen_payload_is_refused(self):
        self.artifact["payload"] = {"authored.dat": "d" * 64}
        result = self.build()
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "published-artifact")

    def test_source_drift_is_refused_before_lane_creation(self):
        with mock.patch.object(self.module, "require_source", side_effect=RuntimeError("different source")):
            result = self.build()
        self.assertFalse(result["success"])
        self.assertEqual(self.events, [])

    def test_build_failure_does_not_run_full_or_fast_fallback(self):
        self.lanes.dispatch = lambda *args, **kwargs: 1
        result = self.build()
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "lane-editor-open")
        self.assertEqual(self.events, ["create"])

    def test_install_preserves_cohort_and_uses_existing_install_cli(self):
        result = self.install(self.prepare_install())
        self.assertTrue(result["success"])
        self.assertEqual(result["apk_sha256"], self.new_hash)
        self.assertEqual(result["previous_apk_sha256"], self.old_hash)
        self.assertEqual(self.events[:3], ["runner-lease", "device", "initial"])
        self.assertEqual(self.events[3], ("sha256sum", self.runtime_root + "/payload/authored.dat"))
        self.assertEqual(self.events[4], (str(self.root / "dev"), "install", "--device", "synthetic-device", "--apk", str(self.new_apk)))
        self.assertEqual(self.events[5], self.events[3])
        self.assertEqual(self.events[6], ("terminal", self.new_hash))
        self.assertEqual(self.selection, (None, None))
        self.assertNotIn("synthetic-device", json.dumps(result))
        self.assertNotIn(self.runtime_root, json.dumps(result))
        self.assertNotIn("authored.dat", json.dumps(result))
        self.assertTrue(result["recorded_payload_cohort_matches"])
        self.assertTrue(result["actual_device_payload_verified"])
        self.assertTrue(result["payload_before_verified"])
        self.assertTrue(result["payload_after_verified"])
        self.assertEqual(result["runtime_payload_file_count"], 1)
        self.assertEqual(result["runtime_payload_sha256"], self.common.digest({"authored.dat": MEMBER_HASH}))
        self.assertEqual(self.runtime_reads, 2)
        self.assertEqual(self.hash_reads, 2)

    def test_candidate_receipt_hash_failure_precedes_device_access(self):
        self.prepare_install()
        result = self.install("f" * 64)
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "candidate-receipt")
        self.assertEqual(self.events, [])

    def test_payload_change_refuses_install_and_preserves_failure_phase(self):
        digest = self.prepare_install()
        self.write(self.old_apk.parent / "result.json", {"apk_sha256": self.old_hash, "payload": {"authored.dat": "d" * 64}})
        result = self.install(digest)
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "payload-cohort")
        self.assertEqual(self.events[-1], ("terminal", self.old_hash))
        self.assertEqual(len(self.events), 4)

    def test_live_mismatch_refuses_install_despite_matching_receipts(self):
        self.device.sh = mock.Mock(return_value="d" * 64 + "  " + self.runtime_root + "/payload/authored.dat")
        result = self.install(self.prepare_install())
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "payload-before-readback")
        self.assertTrue(result["recorded_payload_cohort_matches"])
        self.assertFalse(result["actual_device_payload_verified"])
        self.assertFalse(result["payload_before_verified"])
        self.assertEqual(self.events, ["runner-lease", "device", "initial", ("terminal", self.old_hash)])
        self.assertNotIn("d" * 64, json.dumps(result))
        self.assertIn("d" * 64, (self.root / self.receipt).read_text())

    def test_missing_live_hash_refuses_install(self):
        self.device.sh = mock.Mock(return_value="")
        result = self.install(self.prepare_install())
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "payload-before-readback")
        self.assertFalse(result["actual_device_payload_verified"])
        self.assertEqual(self.events[-1], ("terminal", self.old_hash))
        self.assertEqual(len(self.events), 4)

    def test_runtime_owner_validation_failure_refuses_install_before_hashing(self):
        ordinary = self.read_device_receipt

        def invalid(name):
            if name == "runtime.json":
                raise RuntimeError("Selected volume backing differs")
            return ordinary(name)

        self.device.read_receipt = invalid
        result = self.install(self.prepare_install())
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "payload-before-readback")
        self.assertFalse(result["actual_device_payload_verified"])
        self.assertEqual(self.hash_reads, 0)
        self.assertEqual(len(self.events), 4)

    def test_runtime_root_must_match_sync_receipt(self):
        ordinary = self.read_device_receipt

        def changed(name):
            result = ordinary(name)
            if name == "sync.json":
                result["runtime_path"] = "/unexpected/receipt/root"
            return result

        self.device.read_receipt = changed
        result = self.install(self.prepare_install())
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "payload-before-readback")
        self.assertEqual(self.hash_reads, 0)
        self.assertEqual(len(self.events), 4)

    def test_post_install_mismatch_is_not_verified_and_does_not_repair(self):
        ordinary = self.device_shell

        def changed(*arguments, **kwargs):
            value = ordinary(*arguments, **kwargs)
            return value if self.hash_reads == 1 else value.replace(MEMBER_HASH, "d" * 64)

        self.device.sh = changed
        result = self.install(self.prepare_install())
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "payload-after-readback")
        self.assertTrue(result["payload_before_verified"])
        self.assertFalse(result["payload_after_verified"])
        self.assertFalse(result["actual_device_payload_verified"])
        self.assertEqual(self.hash_reads, 2)
        self.assertEqual(result["apk_sha256"], self.new_hash)
        self.assertEqual(self.events[-1], ("terminal", self.new_hash))
        self.assertEqual(len([event for event in self.events if isinstance(event, tuple) and event[0] == str(self.root / "dev")]), 1)

    def test_install_refusal_does_not_reset_or_retry(self):
        digest = self.prepare_install()
        ordinary = self.child_run

        def fail(arguments, **kwargs):
            if arguments[0] == "git":
                return ordinary(arguments, **kwargs)
            self.record(tuple(arguments))
            return subprocess.CompletedProcess(arguments, 1)

        with mock.patch.object(self.module.subprocess, "run", side_effect=fail):
            result = self.install(digest)
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "owned-in-place-install")
        self.assertEqual(len([event for event in self.events if isinstance(event, tuple) and event[0] == str(self.root / "dev")]), 1)
        self.assertEqual(self.events[-1], ("terminal", self.old_hash))

    def test_terminal_failure_is_not_success(self):
        self.owner._terminal_readback = mock.Mock(side_effect=RuntimeError("private terminal failure"))
        result = self.install(self.prepare_install())
        self.assertFalse(result["success"])
        self.assertEqual(result["phase"], "terminal-readback")
        self.assertNotIn("private", json.dumps(result))

    def test_existing_receipt_is_never_overwritten(self):
        self.write(self.root / self.receipt, {"sentinel": True})
        result = self.build()
        self.assertFalse(result["success"])
        self.assertEqual(self.common.read(self.root / self.receipt), {"sentinel": True})
        self.assertEqual(self.events, [])

    def test_private_capture_includes_real_authored_child_output(self):
        path = self.root / "authored-child.log"
        with path.open("w") as log, self.module.private_output(log):
            child = subprocess.Popen([sys.executable, "-c", "import os; os.write(1, b'authored-child-stdout\\n'); os.write(2, b'authored-child-stderr\\n')"])
            self.assertEqual(child.wait(timeout=10), 0)
        self.assertEqual(path.read_text(), "authored-child-stdout\nauthored-child-stderr\n")


if __name__ == "__main__":
    unittest.main()
