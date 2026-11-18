from contextlib import redirect_stdout, redirect_stderr
import io
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
        planner.snapshots()
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

    def test_retains_frozen_keys_and_payloads_of_live_apks_only(self):
        pinned = self.cache_entry("pinned", PROTECTED)
        recent = self.cache_entry("recent", "a" * 64)
        expired = self.cache_entry("expired", "b" * 64)
        pinned_payload = self.cache_entry("pinned-payload", "c" * 64)
        recent_payload = self.cache_entry("recent-payload", "d" * 64)
        expired_payload = self.cache_entry("expired-payload", "e" * 64)
        for apk, payload in ((pinned, pinned_payload), (recent, recent_payload), (expired, expired_payload)):
            receipt = apk / "result.json"
            result = json.loads(receipt.read_text())
            receipt.write_text(json.dumps(dict(result, payload_directory=str(payload / "payload"))))
            if apk != recent:
                age(apk)
        for mode, apk_hash in (("code", "1" * 64), ("uncompressed", "2" * 64)):
            owner = self.cache_entry(mode, apk_hash)
            (self.work / ("whole-catalog-" + mode + "-base.json")).write_text(json.dumps({"build_key": owner.name}))
        self.assertEqual({item["path"] for item in self.plan().items}, {expired, expired_payload})

    def test_cache_protection_uses_live_references_not_nested_hashes_or_sync_history(self):
        current = self.cache_entry("current", "c" * 64)
        base = self.cache_entry("base", "e" * 64)
        latest = self.cache_entry("installed", "f" * 64)
        stale = self.cache_entry("stale", "b" * 64)
        history = self.cache_entry("history", "d" * 64)
        marked = self.cache_entry("marked", "1" * 64)
        (marked / ".prune-keep").touch()
        age(marked)
        (self.work / "config").mkdir()
        (self.work / "config/current-build.json").write_text(
            json.dumps({"apk": str(current / "lab-vulkan.apk"), "members": ["b" * 64, str(stale / "payload")]})
        )
        (self.work / "config/iteration-base.json").write_text(json.dumps({"apk": str(base / "lab-vulkan.apk"), "members": ["b" * 64]}))
        device = self.work / "device/fixture"
        device.mkdir(parents=True)
        (device / "installed.json").write_text(json.dumps({"apk_sha256": "f" * 64}))
        (device / "sync.json").write_text(json.dumps({"files": ["b" * 64, str(stale / "payload")]}))
        (device / "install-attempt.json").write_text(json.dumps({"apk_sha256": "b" * 64, "success": False}))
        (self.root / "docs").mkdir()
        (self.root / "docs/history-retention.md").write_text("d" * 64)
        planner = self.plan()
        self.assertEqual({item["path"] for item in planner.items}, {stale, history, marked})
        reasons = {Path(item["path"]).name: item["reason"] for item in planner.kept}
        self.assertEqual(reasons[current.name], "current-build cache entry")
        self.assertEqual(reasons[base.name], "iteration-base cache entry")
        self.assertIn("latest installed APK", reasons[latest.name])

    def test_only_newest_build_referenced_by_each_worker_handoff_survives(self):
        old = self.cache_entry("worker-old", "b" * 64)
        latest = self.cache_entry("worker-new", "c" * 64)
        (old / ".prune-keep").touch()
        age(old)
        os.utime(latest / "result.json", (OLD + 3600, OLD + 3600))
        handoffs = self.root / ".local/orchestrator/handoff"
        handoffs.mkdir(parents=True)
        (handoffs / "fixture-worker.md").write_text("old " + "b" * 64 + "\ncurrent " + "c" * 64)
        self.assertEqual([item["path"] for item in self.plan().items], [old])

    def test_three_hour_cache_guard_does_not_lower_other_output_age_guard(self):
        stale = self.cache_entry("stale", "b" * 64)
        recent = self.cache_entry("recent", "c" * 64)
        for path in (stale, recent):
            timestamp = time.time() - (4 if path == stale else 2) * 3600
            for child in [*path.rglob("*"), path]:
                os.utime(child, (timestamp, timestamp))
        planner = prune.Planner(self.work, set(), set(), 24, cache_min_age_hours=3)
        planner.build_cache()
        self.assertEqual([item["path"] for item in planner.items], [stale])
        self.assertTrue(planner.old(stale) is False)

    def test_cache_uses_authoritative_install_receipt_per_device_and_explicit_keep(self):
        stale = self.cache_entry("stale", "b" * 64)
        live = self.cache_entry("live", "c" * 64)
        explicit = self.cache_entry("explicit", "d" * 64)
        device = self.work / "device/fixture"
        device.mkdir(parents=True)
        old = self.work / "device/installed.json"
        old.write_text(json.dumps({"serial": "AUTHORIZED_SERIAL", "apk_sha256": "b" * 64}))
        os.utime(old, (OLD, OLD))
        (device / "installed.json").write_text(json.dumps({"serial": "AUTHORIZED_SERIAL", "apk_sha256": "c" * 64}))
        (device / ".device-context-active.json").write_text("{}")
        hashes, paths = prune.protected_state(self.work, ["d" * 64])
        planner = prune.Planner(self.work, hashes, paths, 24, prune.cache_protected_state(self.work, ["d" * 64]))
        planner.build_cache()
        self.assertEqual([item["path"] for item in planner.items], [stale])
        self.assertEqual({Path(item["path"]).name for item in planner.kept}, {live.name, explicit.name})
        (device / ".device-context-active.json").unlink()
        planner = prune.Planner(self.work, hashes, paths, 24, prune.cache_protected_state(self.work, ["d" * 64]))
        planner.build_cache()
        self.assertEqual([item["path"] for item in planner.items], [live])

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

    def snapshot_run(self, name="analyzed", analyzed=True):
        run = self.work / "device/test-device/experiments/session-memory" / name
        run.mkdir(parents=True)
        heap = run / ("session-2-" + name + ".snap")
        heap.write_bytes(b"heap")
        snapshot = {"file": heap.name, "sha256": prune.sha256(heap), "bytes": heap.stat().st_size}
        (run / "result.json").write_text(json.dumps({"success": False}))
        (run / "memory-snapshots.json").write_text(json.dumps({"2": snapshot}))
        (run / "logcat.txt").write_text("retained evidence")
        if analyzed:
            receipt = self.work / "coordination" / name / "analysis.done.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({"success": True, "exports": [{"snapshot": snapshot, "returncode": 0}], "compare_returncode": 0}))
        age(run)
        return run, heap

    def test_analyzed_snapshot_deleted_but_capture_and_analysis_receipts_stay(self):
        run, heap = self.snapshot_run()
        planner = self.plan()
        self.assertEqual([item["path"] for item in planner.items], [heap])
        prune.apply(planner.items, self.work, self.work / "cleanup-analysis/ledger.json")
        self.assertFalse(heap.exists())
        for name in ("result.json", "memory-snapshots.json", "logcat.txt", heap.name + ".retired.json"):
            self.assertTrue((run / name).is_file())
        self.assertTrue((self.work / "coordination/analyzed/analysis.done.json").is_file())

    def test_snapshot_retention_requires_finished_old_run_and_matching_successful_analysis(self):
        for condition in ("unfinished", "recent", "unanalysed", "failed", "compare-failed", "hash", "bytes", "keep", "protected", "unanalysed-extra"):
            with self.subTest(condition=condition):
                run, heap = self.snapshot_run(condition, analyzed=condition != "unanalysed")
                receipt = self.work / "coordination" / condition / "analysis.done.json"
                if condition == "unfinished":
                    (run / "result.json").unlink()
                elif condition == "recent":
                    os.utime(heap, None)
                elif condition in ("failed", "compare-failed", "hash", "bytes"):
                    result = json.loads(receipt.read_text())
                    if condition == "failed":
                        result["success"] = False
                    elif condition == "compare-failed":
                        result["compare_returncode"] = 1
                    else:
                        result["exports"][0]["snapshot"]["sha256" if condition == "hash" else "bytes"] = "mismatch"
                    receipt.write_text(json.dumps(result))
                elif condition == "keep":
                    (run / ".prune-keep").touch()
                    age(run)
                elif condition == "protected":
                    (self.work / "config").mkdir(exist_ok=True)
                    (self.work / "config/current-build.json").write_text(json.dumps({"evidence": str(heap)}))
                elif condition == "unanalysed-extra":
                    (run / "other.snap").write_bytes(b"unanalysed")
                    age(run)
                planner = self.plan()
                self.assertNotIn(heap, [item["path"] for item in planner.items])
                heap.unlink()

    def test_single_snapshot_analysis_receipt(self):
        _, heap = self.snapshot_run()
        receipt = self.work / "coordination/analyzed/analysis.done.json"
        snapshot = json.loads(receipt.read_text())["exports"][0]["snapshot"]
        receipt.write_text(json.dumps({"success": True, "snapshot": snapshot, "returncode": 0}))
        self.assertEqual([item["path"] for item in self.plan().items], [heap])

    def test_cold_run_unlinks_only_link_and_honors_target_keep_and_receipt(self):
        run, heap = self.snapshot_run()
        cold = self.root / "cold-storage"
        run.rename(cold)
        run.symlink_to(cold, target_is_directory=True)
        os.utime(run, (OLD, OLD), follow_symlinks=False)
        (cold / ".prune-keep").touch()
        age(cold)
        self.assertEqual(self.plan().items, [])
        (cold / ".prune-keep").unlink()
        age(cold)
        (self.work / "config").mkdir()
        protection = self.work / "config/current-build.json"
        protection.write_text(json.dumps({"evidence": str(run / heap.name)}))
        self.assertEqual(self.plan().items, [])
        protection.unlink()
        planner = self.plan()
        self.assertEqual([item["path"] for item in planner.items], [run])
        prune.apply(planner.items, self.work, self.work / "ledger.json")
        self.assertFalse(run.is_symlink())
        self.assertEqual((cold / heap.name).read_bytes(), b"heap")
        self.assertTrue((cold / "result.json").exists())

    def removed_lane(self, name="finished"):
        lane = self.root / ".local/build-lanes" / name
        (lane / "checkout/work/Library").mkdir(parents=True)
        (lane / "checkout/work/Library/binary").write_bytes(b"cache")
        receipt = self.work / "coordination/build-lanes" / (name + "-old") / "removed.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({"removed": True, "name": name, "checkout": str(lane / "checkout")}))
        age(lane)
        return lane, receipt

    def test_finished_lane_leftovers_removed_with_evidence_preserved(self):
        lane, receipt = self.removed_lane()
        planner = self.plan()
        planner.lanes()
        self.assertEqual([item["path"] for item in planner.items], [lane])
        prune.apply(planner.items, self.work, self.work / "ledger.json")
        self.assertFalse(lane.exists())
        self.assertTrue(receipt.exists())

    def test_finished_lane_requires_old_matching_evidence_and_honors_protection(self):
        for condition in ("recent", "missing", "failed", "checkout", "recreated", "keep", "protected"):
            with self.subTest(condition=condition):
                lane, receipt = self.removed_lane(condition)
                if condition == "recent":
                    os.utime(lane, None)
                elif condition == "missing":
                    receipt.unlink()
                elif condition in ("failed", "checkout"):
                    facts = json.loads(receipt.read_text())
                    facts["removed" if condition == "failed" else "checkout"] = False
                    receipt.write_text(json.dumps(facts))
                elif condition == "recreated":
                    (lane / "lane.json").write_text(json.dumps({"seed_commit": "new"}))
                    age(lane)
                elif condition == "keep":
                    (lane / "checkout/.prune-keep").touch()
                    age(lane)
                elif condition == "protected":
                    (self.work / "device").mkdir(exist_ok=True)
                    (self.work / "device/installed.json").write_text(json.dumps({"apk": str(lane / "checkout/work/build.apk")}))
                planner = self.plan()
                # A recreated managed lane must still go through normal owned teardown.
                if condition == "recreated":
                    with patch("build_lanes.remove") as remove:
                        planner.lanes()
                        prune.apply(planner.items, self.work, self.work / "ledger.json")
                    remove.assert_called_once_with(condition, root=self.root)
                else:
                    planner.lanes()
                    self.assertNotIn(lane, [item["path"] for item in planner.items])

    def test_finished_lane_symlink_unlinked_without_modifying_target(self):
        lane, receipt = self.removed_lane()
        cold = self.root / "cold-lane"
        lane.rename(cold)
        lane.symlink_to(cold, target_is_directory=True)
        os.utime(lane, (OLD, OLD), follow_symlinks=False)
        planner = self.plan()
        planner.lanes()
        self.assertEqual([item["path"] for item in planner.items], [lane])
        prune.apply(planner.items, self.work, self.work / "ledger.json")
        self.assertFalse(lane.is_symlink())
        self.assertTrue((cold / "checkout/work/Library/binary").is_file())
        self.assertTrue(receipt.is_file())

    def superseded_pair(self):
        old = self.work / "coordination/fixture/v1"
        new = self.work / "coordination/fixture/v2"
        (old / "payload").mkdir(parents=True)
        (old / "payload/data").write_bytes(b"generated")
        (old / "candidate.apk").write_bytes(b"old candidate")
        (old / "result.json").write_text('{"success": true}')
        (old / "logcat.txt").write_text("retained evidence")
        new.mkdir()
        (new / "terminal.done.json").write_text('{"success": true}')
        age(old)
        prune.supersede(old, new, self.work)
        return old, new

    def test_superseded_marker_waits_24_hours_then_overrides_old_manifest_only(self):
        old, new = self.superseded_pair()
        config = self.work / "config/current-build.json"
        config.parent.mkdir()
        config.write_text(json.dumps({"apk": str(old / "candidate.apk"), "apk_sha256": prune.sha256(old / "candidate.apk")}))
        self.assertEqual(self.plan().items, [])
        age(old)
        planner = self.plan()
        self.assertEqual({item["path"] for item in planner.items}, {old / "candidate.apk", old / "payload"})
        prune.apply(planner.items, self.work, self.work / "cleanup-analysis/ledger.json")
        self.assertFalse((old / "candidate.apk").exists())
        self.assertFalse((old / "payload").exists())
        for name in ("result.json", "logcat.txt", ".superseded-by", "candidate.apk.retired.json", "payload.retired.json"):
            self.assertTrue((old / name).is_file())
        self.assertTrue((new / "terminal.done.json").is_file())

    def test_superseded_protections_survive_historical_override(self):
        for protection in ("state-hash", "baseline-path", "device-hash", "device-path", "keep", "nested-keep", "ancestor-keep", "explicit"):
            with self.subTest(protection=protection):
                old, new = self.superseded_pair()
                digest = prune.sha256(old / "candidate.apk")
                if protection == "state-hash":
                    (self.root / "PORTING_STATE.md").write_text(digest)
                elif protection == "baseline-path":
                    (self.root / "docs").mkdir(exist_ok=True)
                    (self.root / "docs/BASELINE.md").write_text("`work/coordination/fixture/v1`")
                elif protection.startswith("device"):
                    path = self.work / "device/fixture/installed.json"
                    path.parent.mkdir(parents=True)
                    path.write_text(json.dumps({"apk": str(old / "candidate.apk")} if protection.endswith("path") else {"apk_sha256": digest}))
                elif protection != "explicit":
                    target = old.parent if protection == "ancestor-keep" else old / "payload" if protection == "nested-keep" else old
                    (target / ".prune-keep").touch()
                age(old)
                hashes, paths = prune.protected_state(self.work, [])
                planner = prune.Planner(
                    self.work,
                    hashes,
                    paths,
                    24,
                    superseded_protection=prune.protected_state(self.work, [digest] if protection == "explicit" else [], authoritative=True),
                )
                planner.scan("coordination")
                self.assertEqual(planner.items, [])
                shutil.rmtree(self.work)
                (self.root / "PORTING_STATE.md").write_text("")
                if (self.root / "docs/BASELINE.md").exists():
                    (self.root / "docs/BASELINE.md").unlink()

    def test_superseded_invalid_receipt_marker_and_new_activity_fail_closed(self):
        for condition in (
            "receipt-change",
            "receipt-failure",
            "receipt-missing",
            "newer-failure",
            "marker-invalid",
            "marker-symlink",
            "receipt-symlink",
            "recent-output",
            "nested-link",
        ):
            with self.subTest(condition=condition):
                old, new = self.superseded_pair()
                age(old)
                receipt = new / "terminal.done.json"
                if condition == "receipt-change":
                    receipt.write_text('{"success":true,"changed":true}')
                elif condition == "receipt-failure":
                    receipt.write_text('{"success":false}')
                elif condition == "receipt-missing":
                    receipt.unlink()
                elif condition == "newer-failure":
                    (new / "result.json").write_text('{"success":false}')
                elif condition == "marker-invalid":
                    (old / ".superseded-by").write_text("not json")
                    age(old)
                elif condition in ("marker-symlink", "receipt-symlink"):
                    path = old / ".superseded-by" if condition == "marker-symlink" else receipt
                    target = self.root / "unrelated"
                    target.write_bytes(path.read_bytes())
                    path.unlink()
                    path.symlink_to(target)
                elif condition == "recent-output":
                    (old / "payload/new-data").write_bytes(b"new")
                else:
                    (old / "linked").symlink_to(new, target_is_directory=True)
                self.assertEqual(self.plan().items, [])
                shutil.rmtree(self.work)

    def test_supersede_requires_disjoint_physical_runs_and_latest_passing_receipt(self):
        old, new = self.superseded_pair()
        marker = old / ".superseded-by"
        with self.assertRaises(FileExistsError):
            prune.supersede(old, new, self.work)
        marker.unlink()
        for target in (old, old.parent, old / "payload", self.root, self.work / "coordination"):
            with self.assertRaises(ValueError):
                prune.supersede(old, target, self.work)
        (new / "terminal.done.json").write_text('{"success":1}')
        with self.assertRaises(ValueError):
            prune.supersede(old, new, self.work)
        self.assertFalse(marker.exists())

    def test_supersede_cli_marks_only_and_rejects_apply_combination(self):
        old, new = self.superseded_pair()
        (old / ".superseded-by").unlink()
        with (
            patch.object(prune.subprocess, "check_output", return_value=str(self.root / ".git")),
            patch.object(sys, "argv", [str(SCRIPT), "--supersede", str(old), "--by", str(new)]),
            redirect_stdout(io.StringIO()),
        ):
            prune.main()
        self.assertTrue((old / ".superseded-by").is_file())
        self.assertTrue((old / "candidate.apk").is_file())
        with (
            patch.object(prune.subprocess, "check_output", return_value=str(self.root / ".git")),
            patch.object(sys, "argv", [str(SCRIPT), "--supersede", str(old), "--by", str(new), "--apply"]),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            prune.main()
        self.assertTrue((old / "candidate.apk").is_file())

    def test_supersession_planning_checks_each_run_once_and_apply_rechecks(self):
        old, _ = self.superseded_pair()
        for number in range(100):
            (old / f"subdirectory-{number}").mkdir()
        age(old)
        with patch.object(prune, "superseded_ready", wraps=prune.superseded_ready) as eligibility, patch.object(prune, "sha256", wraps=prune.sha256) as digest:
            planner = self.plan()
            self.assertEqual(eligibility.call_count, 1)
            self.assertEqual(sum(call.args[0] == old / "candidate.apk" for call in digest.call_args_list), 2)
            self.assertEqual({item["path"] for item in planner.items}, {old / "candidate.apk", old / "payload"})
            # Cached planning must not weaken the independent apply-time veto.
            (old / ".prune-keep").touch()
            prune.apply(planner.items, self.work, self.work / "cleanup-analysis/ledger.json")
            self.assertEqual(eligibility.call_count, 2)
            self.assertTrue(all("skipped" in item for item in planner.items))
        self.assertTrue((old / "candidate.apk").is_file())
        self.assertTrue((old / "payload").is_dir())

    def test_superseded_apply_rechecks_protection_added_after_plan(self):
        old, _ = self.superseded_pair()
        age(old)
        planner = self.plan()
        (old / ".prune-keep").touch()
        prune.apply(planner.items, self.work, self.work / "cleanup-analysis/ledger.json")
        self.assertTrue((old / "candidate.apk").exists())
        self.assertTrue((old / "payload").is_dir())
        self.assertTrue(all("skipped" in item for item in planner.items))

    def test_prune_keep_marker_protects_a_directory_tree(self):
        run = self.work / "coordination/oracle/packet"
        (run / "payload").mkdir(parents=True)
        (run / "payload/whole-game-content").write_bytes(b"x")
        (self.work / "coordination/oracle/.prune-keep").write_text("costly private oracle\n")
        age(self.work / "coordination")
        self.assertEqual(self.plan().items, [])


if __name__ == "__main__":
    unittest.main()
