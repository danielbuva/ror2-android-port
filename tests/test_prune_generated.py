import importlib.util
import json
import os
import shutil
import sys
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prune-generated.py"
sys.path.insert(0, str(SCRIPT.parent / "lab"))
spec = importlib.util.spec_from_file_location("prune_generated", SCRIPT)
prune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prune)

PROTECTED = "a" * 64
OLD = time.time() - 72 * 3600


def age(path):
    for base, dirs, files in os.walk(path):
        for name in dirs + files:
            os.utime(os.path.join(base, name), (OLD, OLD))
    os.utime(path, (OLD, OLD))


class PruneGeneratedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.work = self.root / "work"
        self.addCleanup(self.temporary.cleanup)
        prune.ROOT = self.root
        (self.root / "PORTING_STATE.md").write_text("Latest APK `" + PROTECTED + "`\n")

    def cache_entry(self, key, apk_hash):
        entry = self.work / "build-cache" / key
        (entry / "payload").mkdir(parents=True)
        (entry / "payload/whole-game-content").write_bytes(b"x" * (2 << 20))
        (entry / "lab-vulkan.apk").write_bytes(b"apk")
        (entry / "result.json").write_text(json.dumps({"apk_sha256": apk_hash}))
        age(entry)
        return entry

    def plan(self):
        hashes, paths = prune.protected_state(self.work, [])
        planner = prune.Planner(self.work, hashes, paths, 24)
        planner.build_cache()
        planner.lab_build()
        for name in prune.SCAN_ROOTS:
            planner.scan(name)
        return planner

    def test_protected_cache_entry_is_kept_and_superseded_one_is_retired_with_receipt(self):
        keep = self.cache_entry("k" * 64, PROTECTED)
        drop = self.cache_entry("d" * 64, "b" * 64)
        planner = self.plan()
        self.assertEqual([item["path"] for item in planner.items], [drop])
        prune.apply(planner.items, self.work, self.work / "cleanup-analysis/ledger.json")
        self.assertTrue((keep / "lab-vulkan.apk").is_file())
        self.assertFalse(drop.exists())
        self.assertTrue((self.work / "cleanup-analysis/pruned-build-cache" / drop.name / "result.json").is_file())

    def test_recent_outputs_are_never_planned(self):
        entry = self.cache_entry("r" * 64, "c" * 64)
        os.utime(entry / "lab-vulkan.apk", None)
        self.assertEqual(self.plan().items, [])

    def test_iteration_anchor_survives_a_different_current_build(self):
        entry = self.cache_entry("i" * 64, "e" * 64)
        (self.work / "config").mkdir()
        (self.work / "config/iteration-base.json").write_text(json.dumps({"apk": str(entry / "lab-vulkan.apk"), "apk_sha256": "e" * 64}))
        (self.work / "config/current-build.json").write_text(json.dumps({"apk_sha256": "f" * 64}))
        self.assertEqual(self.plan().items, [])

    def test_experiment_binary_is_replaced_by_marker_but_logs_stay(self):
        run = self.work / "experiments/audio/run1"
        run.mkdir(parents=True)
        (run / "candidate.apk").write_bytes(b"old apk")
        (run / "logcat.txt").write_text("evidence")
        age(run)
        planner = self.plan()
        prune.apply(planner.items, self.work, self.work / "cleanup-analysis/ledger.json")
        self.assertFalse((run / "candidate.apk").exists())
        self.assertTrue((run / "candidate.apk.retired.json").is_file())
        self.assertTrue((run / "logcat.txt").is_file())

    def test_apk_whose_hash_is_protected_keeps_its_payload(self):
        run = self.work / "experiments/audio/run2"
        (run / "payload").mkdir(parents=True)
        (run / "candidate.apk").write_bytes(b"protected bytes")
        age(run)
        digest = prune.sha256(run / "candidate.apk")
        (self.root / "PORTING_STATE.md").write_text("`" + digest + "`\n")
        self.assertEqual(self.plan().items, [])

    def test_payload_removed_during_deletion_does_not_abort_remaining_cleanup(self):
        run = self.work / "coordination/concurrent"
        payload = run / "payload"
        payload.mkdir(parents=True)
        binary = run / "candidate.apk"
        binary.write_bytes(b"old apk")
        age(run)
        planner = self.plan()
        planner.items.sort(key=lambda item: item["path"] != payload)
        remove_tree = shutil.rmtree

        def concurrent_remove(path):
            remove_tree(path)
            raise FileNotFoundError(path)

        ledger = self.work / "cleanup-analysis/ledger.json"
        with patch.object(prune.shutil, "rmtree", side_effect=concurrent_remove):
            prune.apply(planner.items, self.work, ledger)
        self.assertFalse(payload.exists())
        self.assertFalse(binary.exists())
        self.assertTrue(binary.with_name("candidate.apk.retired.json").is_file())
        self.assertEqual(json.loads(ledger.read_text())[0]["skipped"], "already removed by concurrent cleanup")

    def test_lane_pruning_retains_recent_live_and_busy_lanes(self):
        lanes = self.root / ".local/build-lanes"
        for name in ("stale", "recent", "live", "busy"):
            lane = lanes / name
            lane.mkdir(parents=True)
            (lane / "lane.json").write_text("{}")
            if name == "live":
                (lane / "server.json").write_text(json.dumps({"pid": os.getpid()}))
            age(lane)
        os.utime(lanes / "recent/lane.json", None)
        lock = lanes / ".locks/busy.lock"
        lock.parent.mkdir()
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import fcntl,sys; f=open(sys.argv[1],'w'); fcntl.flock(f,fcntl.LOCK_EX); print('held',flush=True); sys.stdin.read()",
                str(lock),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), "held")
            os.utime(lock, (OLD, OLD))
            planner = self.plan()
            planner.lanes()
        finally:
            child.communicate("")
        self.assertEqual([(item["kind"], item["name"]) for item in planner.items], [("build lane", "stale")])
        self.assertEqual(len(planner.kept), 3)

    def test_lane_apply_uses_owned_teardown_and_handles_new_activity(self):
        lane = self.root / ".local/build-lanes/stale"
        lane.mkdir(parents=True)
        plan = [{"path": lane, "kind": "build lane", "name": "stale"}]
        with patch("build_lanes.remove", side_effect=TimeoutError) as remove:
            prune.apply(plan, self.work, self.work / "ledger.json")
        remove.assert_called_once_with("stale", root=self.root)
        self.assertEqual(plan[0]["skipped"], "lane became active after planning")
        self.assertTrue(lane.exists())

    def test_prune_keep_marker_protects_a_directory_tree(self):
        run = self.work / "coordination/oracle/packet"
        (run / "payload").mkdir(parents=True)
        (run / "payload/whole-game-content").write_bytes(b"x")
        (self.work / "coordination/oracle/.prune-keep").write_text("costly private oracle\n")
        age(self.work / "coordination")
        self.assertEqual(self.plan().items, [])


if __name__ == "__main__":
    unittest.main()
