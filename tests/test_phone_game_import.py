"""Synthetic local-only owner-input import contracts; no game data or devices."""

import copy
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tested_game_import", ROOT / "tools/phone-build/owner-apk/game_import.py")
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def manifest(contents):
    return {
        "schema": 1,
        "game_version": "authored-fixture-v1",
        "files": [{"path": name, "bytes": len(value), "sha256": sha(value)} for name, value in contents.items()],
    }


def zipped(entries):
    value = io.BytesIO()
    with zipfile.ZipFile(value, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    value.seek(0)
    return value


class GameImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.private = self.root / "private"
        self.contents = {"authored/header.txt": b"synthetic header\n", "authored/content.bin": b"authored bytes only\n" * 80, "empty": b""}
        self.manifest = manifest(self.contents)
        self.opened = []

    def tearDown(self):
        self.temp.cleanup()

    def importer(self, **kwargs):
        return G.Importer(self.manifest, self.private, reserve_bytes=17, free_bytes=lambda: 100 * 1024**3, **kwargs)

    def source(self, contents=None, *, unknown=False, **kwargs):
        contents = self.contents if contents is None else contents

        def opener(name):
            self.opened.append(name)
            return io.BytesIO(contents[name])

        return G.StreamSource({name: None if unknown else len(value) for name, value in contents.items()}, opener, **kwargs)

    def folder(self, contents=None):
        contents = self.contents if contents is None else contents
        folder = self.root / "source"
        folder.mkdir(exist_ok=True)
        for name, data in contents.items():
            path = folder / name
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(data)
        return folder

    def test_stream_import_only_required_files_with_progress_and_durable_receipt(self):
        extra = {**self.contents, "unrelated/save.txt": b"leave me alone"}
        progress = []
        with patch.object(G.os, "fsync", wraps=os.fsync) as sync:
            report = self.importer().run(self.source(extra), progress=progress.append)
        self.assertEqual("complete", report["status"])
        self.assertEqual(["unrelated/save.txt"], report["extra"])
        self.assertNotIn("unrelated/save.txt", self.opened)
        self.assertGreaterEqual(sync.call_count, len(self.contents) * 2)
        self.assertTrue(any(row["current_bytes"] for row in progress))
        for name, data in self.contents.items():
            path = self.private / "files" / name
            self.assertEqual(data, path.read_bytes())
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        receipt = json.loads((self.private / "checkpoint.json").read_bytes())
        self.assertEqual(set(self.contents), set(receipt["completed"]))
        self.assertEqual(report["manifest_sha256"], receipt["manifest_sha256"])
        self.assertEqual(sum(map(len, self.contents.values())), report["completed_bytes"])
        self.assertFalse((self.private / "files/unrelated").exists())

    def test_folder_import_never_changes_source(self):
        folder = self.folder()
        before = {name: (folder / name).read_bytes() for name in self.contents}
        self.assertEqual("complete", self.importer().run(G.FolderSource(folder))["status"])
        self.assertEqual(before, {name: (folder / name).read_bytes() for name in self.contents})

    def test_zip_import_streams_and_never_extracts_extras(self):
        with G.ZipSource(zipped([("authored/", b""), *self.contents.items(), ("unrelated.bin", b"extra")])) as source:
            with patch.object(zipfile.ZipFile, "extractall", side_effect=AssertionError("not streaming")):
                report = self.importer().run(source)
        self.assertEqual("complete", report["status"])
        self.assertEqual(["unrelated.bin"], report["extra"])

    def test_unknown_saf_sizes_are_verified_in_bounded_chunks(self):
        data = b"authored-" * (G.CHUNK // 2)
        self.manifest = manifest({"stream": data})
        reads = []

        class Tracking(io.BytesIO):
            def read(self, count=-1):
                reads.append(count)
                return super().read(count)

        source = G.StreamSource({"stream": None}, lambda _: Tracking(data))
        self.assertEqual("complete", self.importer().run(source)["status"])
        self.assertGreater(len(reads), 2)
        self.assertTrue(all(0 < value <= G.CHUNK for value in reads))

    def test_missing_and_extra_are_reported_without_opening_sources(self):
        contents = {"authored/header.txt": self.contents["authored/header.txt"], "extra": b"synthetic"}
        result = self.importer().run(self.source(contents))
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["authored/content.bin", "empty"], result["missing"])
        self.assertEqual(["extra"], result["extra"])
        self.assertFalse(self.opened)

    def test_advertised_size_mismatch_reports_version_mismatch(self):
        contents = {**self.contents, "empty": b"new version"}
        result = self.importer().run(self.source(contents))
        self.assertEqual("blocked", result["status"])
        self.assertTrue(result["version_mismatch"])
        self.assertEqual("size", result["mismatched"][0]["reason"])
        self.assertFalse(self.opened)

    def test_explicit_source_version_mismatch_is_blocked(self):
        result = self.importer().run(self.source(game_version="other-authored-version"))
        self.assertEqual("blocked", result["status"])
        self.assertTrue(result["version_mismatch"])
        self.assertEqual("other-authored-version", result["source_game_version"])
        self.assertFalse(self.opened)

    def test_hash_mismatch_never_becomes_final_or_completed(self):
        contents = {**self.contents, "authored/header.txt": b"x" * len(self.contents["authored/header.txt"])}
        result = self.importer().run(self.source(contents))
        self.assertEqual("blocked", result["status"])
        self.assertEqual("sha256", result["mismatched"][0]["reason"])
        self.assertTrue(result["version_mismatch"])
        self.assertFalse((self.private / "files/authored/header.txt").exists())
        self.assertEqual(2, result["completed_files"])
        self.assertEqual([], list((self.private / "staging").iterdir()))

    def test_stream_size_lies_are_bounded_and_reported(self):
        for data in (b"", b"x" * G.CHUNK):
            with self.subTest(length=len(data)):
                self.manifest = manifest({"small": b"abc"})
                source = G.StreamSource({"small": 3}, lambda _: io.BytesIO(data))
                result = self.importer().run(source)
                self.assertEqual("blocked", result["status"])
                self.assertEqual("size", result["mismatched"][0]["reason"])
                self.assertLessEqual(result["mismatched"][0]["actual"], 4)
                self.assertFalse((self.private / "files/small").exists())

    def test_space_estimate_includes_separate_reconstruction_and_margin(self):
        importer = self.importer(reconstruction_bytes=500, margin_ratio=0.10)
        estimate = importer.estimate(100)
        self.assertEqual(627, estimate["required_free_bytes"])
        self.assertEqual(500, estimate["reconstruction_bytes"])
        self.assertEqual(27, estimate["margin_bytes"])
        importer.free_bytes = lambda: 626
        self.manifest = manifest({"small": b"x" * 100})
        importer = G.Importer(self.manifest, self.private, reconstruction_bytes=500, reserve_bytes=17, margin_ratio=0.10, free_bytes=lambda: 626)
        result = importer.run(self.source({"small": b"x" * 100}))
        self.assertEqual("insufficient-space", result["status"])
        self.assertFalse(self.opened)

    def test_capacity_is_refreshed_before_each_copy(self):
        importer = self.importer()
        values = iter([100 * 1024**3, 0])
        importer.free_bytes = lambda: next(values)
        self.assertEqual("insufficient-space", importer.run(self.source())["status"])
        self.assertFalse(self.opened)

    def test_pause_between_files_retains_checkpoint_and_resume_skips_source(self):
        paused = False

        def progress(value):
            nonlocal paused
            paused = value["completed_files"] >= 1

        report = self.importer().run(self.source(), progress=progress, control=lambda: "pause" if paused else None)
        self.assertEqual("paused", report["status"])
        self.assertEqual(1, report["completed_files"])
        completed = self.opened[:]
        self.opened.clear()
        result = self.importer().run(self.source())
        self.assertEqual("complete", result["status"])
        self.assertTrue(set(completed).isdisjoint(self.opened))

    def test_pause_and_cancel_mid_file_delete_partial_and_restart(self):
        self.manifest = manifest({"large": b"synthetic" * G.CHUNK})
        contents = {"large": b"synthetic" * G.CHUNK}
        for action, expected in (("pause", "paused"), ("cancel", "cancelled")):
            with self.subTest(action=action):
                stop = False

                def progress(value):
                    nonlocal stop
                    stop = value["current_bytes"] > 0

                result = self.importer().run(self.source(contents), progress=progress, control=lambda: action if stop else None)
                self.assertEqual(expected, result["status"])
                self.assertEqual(0, result["completed_files"])
                self.assertFalse((self.private / "files/large").exists())
                self.assertEqual([], list((self.private / "staging").iterdir()))
        self.assertEqual("complete", self.importer().run(self.source(contents))["status"])

    def test_completed_file_mutation_is_rehashed_and_repaired(self):
        self.importer().run(self.source())
        damaged = self.private / "files/authored/header.txt"
        damaged.write_bytes(b"x" * len(self.contents["authored/header.txt"]))
        self.opened.clear()
        result = self.importer().run(self.source())
        self.assertEqual("complete", result["status"])
        self.assertEqual(["authored/header.txt"], self.opened)
        self.assertEqual(self.contents["authored/header.txt"], damaged.read_bytes())

    def test_forged_receipt_does_not_skip_missing_bytes(self):
        importer = self.importer()
        (self.private / "checkpoint.json").write_text(
            json.dumps(
                {"schema": 1, "manifest_sha256": importer.identity, "status": "complete", "completed": {name: row for name, row in importer.rows.items()}}
            )
        )
        result = importer.run(self.source())
        self.assertEqual("complete", result["status"])
        self.assertEqual(set(self.contents), set(self.opened))

    def test_torn_checkpoint_and_partial_are_recovered(self):
        importer = self.importer()
        (self.private / "checkpoint.json").write_bytes(b'{"schema":')
        stage = self.private / "staging" / (sha(b"authored/header.txt") + ".part")
        stage.write_bytes(b"untrusted partial")
        result = importer.run(self.source())
        self.assertEqual("complete", result["status"])
        self.assertFalse(stage.exists())

    def test_different_manifest_refuses_without_overwriting_prior_receipt(self):
        self.importer().run(self.source())
        receipt = (self.private / "checkpoint.json").read_bytes()
        changed = copy.deepcopy(self.manifest)
        changed["game_version"] = "authored-v2"
        with self.assertRaisesRegex(ValueError, "different input manifest"):
            G.Importer(changed, self.private).run(self.source())
        self.assertEqual(receipt, (self.private / "checkpoint.json").read_bytes())

    def test_direct_native_files_are_adopted_without_double_copy(self):
        importer = self.importer()
        for name, value in self.contents.items():
            path = self.private / "files" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        with patch.object(G.os, "replace", wraps=os.replace) as replace:
            result = importer.verify()
        self.assertEqual("complete", result["status"])
        self.assertTrue(all(str(call.args[1]).endswith("checkpoint.json") for call in replace.call_args_list))
        self.assertEqual([], list((self.private / "staging").iterdir()))

    def test_verify_reports_missing_and_hash_mismatch_without_copy(self):
        importer = self.importer()
        path = self.private / "files/authored/header.txt"
        path.parent.mkdir()
        path.write_bytes(b"x" * len(self.contents["authored/header.txt"]))
        result = importer.verify()
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["authored/content.bin", "empty"], result["missing"])
        self.assertEqual("sha256", result["mismatched"][0]["reason"])
        self.assertEqual([], list((self.private / "staging").iterdir()))

    def test_resume_rehash_has_chunk_progress_and_can_pause(self):
        self.importer().run(self.source())
        stop, progress = False, []

        def observed(row):
            nonlocal stop
            progress.append(row)
            stop = row["status"] == "validating" and row["current_bytes"] > 0

        self.opened.clear()
        result = self.importer().run(self.source(), progress=observed, control=lambda: "pause" if stop else None)
        self.assertEqual("paused", result["status"])
        self.assertFalse(self.opened)
        self.assertTrue(any(row["status"] == "validating" and row["current_bytes"] > 0 for row in progress))

    def test_source_read_error_keeps_prior_completed_files(self):
        source = self.source()
        original = source.opener

        def opener(name):
            if name == "authored/header.txt":
                raise OSError("synthetic permission revocation")
            return original(name)

        source.opener = opener
        with self.assertRaisesRegex(OSError, "permission revocation"):
            self.importer().run(source)
        receipt = json.loads((self.private / "checkpoint.json").read_bytes())
        self.assertEqual("failed", receipt["status"])
        self.assertEqual(["authored/content.bin"], list(receipt["completed"]))
        self.assertEqual([], list((self.private / "staging").iterdir()))
        self.assertEqual("complete", self.importer().run(self.source())["status"])

    def test_duplicate_worker_refuses_under_lock(self):
        importer = self.importer()
        with (self.private / "import.lock").open("wb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "another import"):
                importer.run(self.source())
        self.assertFalse(self.opened)

    def test_unsafe_manifest_paths_and_aliases_refuse(self):
        for name in ("../escape", "/absolute", "a//b", "a/./b", "a/../b", "C:/file", "a\\b", "a\x00b", "a\nb", "e\u0301/file", "trailing/"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                G.validate_manifest(manifest({name: b"authored"}))
        for names in (("a", "a/b"), ("A", "a"), ("A/f", "a/g")):
            with self.subTest(names=names), self.assertRaises(ValueError):
                G.validate_manifest(manifest(dict.fromkeys(names, b"authored")))

    def test_manifest_strict_types_and_hashes(self):
        for field, value in (("bytes", True), ("bytes", -1), ("bytes", 1.0), ("sha256", "A" * 64), ("sha256", "0" * 63)):
            bad = copy.deepcopy(self.manifest)
            bad["files"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                G.validate_manifest(bad)
        for change in ({"schema": True}, {"schema": 2}, {"game_version": " "}, {"files": []}, {"unknown": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                G.validate_manifest({**self.manifest, **change})
        bad = copy.deepcopy(self.manifest)
        bad["files"].append(bad["files"][0])
        with self.assertRaises(ValueError):
            G.validate_manifest(bad)
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            G.load_manifest(b'{"schema":1,"schema":1}')

    def test_canonical_manifest_identity_does_not_depend_on_row_order(self):
        first = self.importer().identity
        self.manifest["files"].reverse()
        self.assertEqual(first, self.importer().identity)

    def test_unicode_manifest_identity_matches_release_canonical_json(self):
        self.manifest = manifest({"authored/é.txt": b"synthetic accented filename"})
        normalized = G.validate_manifest(self.manifest)
        expected = sha(json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())
        self.assertEqual(expected, self.importer().identity)
        self.assertEqual("complete", self.importer().run(self.source({"authored/é.txt": b"synthetic accented filename"}))["status"])

    def test_process_death_retains_only_revalidated_whole_files(self):
        # The subprocess kills only itself, after one fsynced checkpoint and
        # during the next synthetic file. A new importer must recover safely.
        folder = self.folder()
        script = """
import importlib.util,json,os,signal,sys
spec=importlib.util.spec_from_file_location('killed_import',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def progress(row):
    if row['completed_files'] == 1 and row['current_path'] == 'authored/header.txt' and row['current_bytes']:
        os.kill(os.getpid(), signal.SIGKILL)
module.Importer(json.loads(sys.argv[2]),sys.argv[3],reserve_bytes=0).run(module.FolderSource(sys.argv[4]),progress=progress)
"""
        child = subprocess.run(
            [sys.executable, "-c", script, str(ROOT / "tools/phone-build/owner-apk/game_import.py"), json.dumps(self.manifest), str(self.private), str(folder)],
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(-9, child.returncode, child.stderr.decode())
        receipt = json.loads((self.private / "checkpoint.json").read_bytes())
        self.assertEqual(["authored/content.bin"], list(receipt["completed"]))
        self.assertEqual(1, len(list((self.private / "staging").iterdir())))
        result = self.importer().run(self.source())
        self.assertEqual("complete", result["status"])
        self.assertNotIn("authored/content.bin", self.opened)
        self.assertEqual([], list((self.private / "staging").iterdir()))

    def test_folder_symlink_special_file_and_path_swap_refuse(self):
        folder = self.folder()
        (folder / "link").symlink_to(folder / "empty")
        with self.assertRaises(ValueError):
            G.FolderSource(folder)
        (folder / "link").unlink()
        os.mkfifo(folder / "pipe")
        with self.assertRaises(ValueError):
            G.FolderSource(folder)
        (folder / "pipe").unlink()
        source = G.FolderSource(folder)
        original = folder / "authored/content.bin"
        original.unlink()
        original.symlink_to(folder / "authored/header.txt")
        with self.assertRaises(OSError):
            self.importer().run(source)
        self.assertFalse((self.private / "files/authored/content.bin").exists())

    def test_private_symlink_parents_and_checkpoints_refuse(self):
        importer = self.importer()
        outside = self.root / "outside"
        outside.mkdir()
        (self.private / "files/authored").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            importer.run(self.source())
        self.assertEqual([], list(outside.iterdir()))
        (self.private / "files/authored").unlink()
        (self.private / "checkpoint.json").unlink()
        victim = outside / "untouched"
        victim.write_bytes(b"keep")
        (self.private / "checkpoint.json").symlink_to(victim)
        with self.assertRaises(ValueError):
            importer.run(self.source())
        self.assertEqual(b"keep", victim.read_bytes())

    def test_overlapping_source_and_destination_refuse(self):
        folder = self.folder()
        importer = G.Importer(self.manifest, folder / "private")
        with self.assertRaisesRegex(ValueError, "disjoint"):
            importer.run(G.FolderSource(folder))

    def test_zip_traversal_duplicates_and_file_directory_collisions_refuse(self):
        cases = [
            [("../outside", b"authored")],
            [("/absolute", b"authored")],
            [("a\\b", b"authored")],
            [("a", b"one"), ("a", b"two")],
            [("a", b"one"), ("A", b"two")],
            [("a", b"one"), ("a/b", b"two")],
            [("a", b"one"), ("a/", b"")],
            [("a", b"one"), ("a/b/", b"")],
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for entries in cases:
                with self.subTest(entries=entries), self.assertRaises(ValueError):
                    G.ZipSource(zipped(entries))

    def test_zip_symlinks_refuse(self):
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError):
            G.ZipSource(zipped([(link, b"../target")]))

    def test_zip_crc_failure_is_not_checkpointed(self):
        value = io.BytesIO()
        payload = b"authored CRC fixture"
        with zipfile.ZipFile(value, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("input", payload)
        value = io.BytesIO(value.getvalue().replace(payload, b"X" + payload[1:]))
        self.manifest = manifest({"input": payload})
        with G.ZipSource(value) as source, self.assertRaises(zipfile.BadZipFile):
            self.importer().run(source)
        self.assertFalse((self.private / "files/input").exists())
        self.assertEqual({}, json.loads((self.private / "checkpoint.json").read_bytes())["completed"])


if __name__ == "__main__":
    unittest.main()
