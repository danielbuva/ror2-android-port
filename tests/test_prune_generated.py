import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prune-generated.py"
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


if __name__ == "__main__":
    unittest.main()
