"""Compare the batched public audit with an independent staged-content oracle."""

import contextlib
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_index_audit", ROOT / "scripts/audit-public.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class PublicAuditIndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "--quiet")
        self.git("config", "user.name", "Audit fixture")
        self.git("config", "user.email", "fixture" + "@users.noreply.github.com")
        self.root_patch = patch.object(AUDIT, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def git(self, *args, data=None):
        return subprocess.check_output(["git", *args], cwd=self.root, input=data, stderr=subprocess.PIPE)

    def stage(self, path, data, mode="100644"):
        object_id = self.git("hash-object", "-w", "--stdin", data=data).strip()
        self.git("update-index", "--add", "--cacheinfo", mode, object_id, os.fsencode(path))
        return object_id

    def legacy_blobs(self, explicit_stage=False):
        prefix = b":0:" if explicit_stage else b":"
        return [(os.fsdecode(path), self.git("show", prefix + path)) for path in self.git("ls-files", "-z").split(b"\0") if path]

    def assert_same_findings(self, explicit_stage=False):
        expected = self.legacy_blobs(explicit_stage)
        # Comparing every byte, not just pass/fail, also detects any omitted file.
        self.assertEqual(list(AUDIT.index_blobs()), expected)
        findings = [f"{path}: {label}" for path, data in expected for label in AUDIT.violations(path, data)]
        expected_output = "\n".join(findings) if findings else "Public index audit passed (pattern checks; not a complete IP/secret review)."
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = AUDIT.main()
        self.assertEqual(result, bool(findings))
        self.assertEqual(output.getvalue().encode("utf-8", "surrogateescape"), (expected_output + "\n").encode("utf-8", "surrogateescape"))
        return findings

    def test_staged_changes_deletions_renames_and_missing_worktree(self):
        sensitive = b"-----BEGIN " + b"PRIVATE KEY-----"
        self.stage("removed.txt", sensitive)
        self.stage("renamed.txt", sensitive)
        self.stage("modified.txt", b"clean HEAD")
        self.git("commit", "--quiet", "-m", "Synthetic index baseline")
        self.git("update-index", "--force-remove", "removed.txt", "renamed.txt")
        self.stage("docs/new-name.txt", sensitive)
        self.stage("modified.txt", sensitive)
        self.stage("missing-worktree.txt", sensitive)
        (self.root / "modified.txt").write_bytes(b"clean unstaged replacement")
        (self.root / "removed.txt").write_bytes(sensitive)
        (self.root / "untracked.txt").write_bytes(sensitive)
        findings = self.assert_same_findings()
        self.assertEqual(findings, ["docs/new-name.txt: private key", "missing-worktree.txt: private key", "modified.txt: private key"])

    def test_symlinks_empty_executables_duplicate_blobs_and_binary_bytes(self):
        sensitive = b"/" + b"home/audit-fixture/private"
        self.stage("link", sensitive, mode="120000")
        self.stage("executable", b"#!/bin/sh\n", mode="100755")
        self.stage("empty", b"")
        self.stage("binary", bytes(range(256)) + sensitive)
        self.stage("second-link", sensitive, mode="120000")
        # A symlink must be scanned as its staged target text, never followed.
        (self.root / "link").symlink_to(self.root / "nonexistent")
        self.assert_same_findings()

    def test_filename_bytes_tabs_newlines_colons_and_double_prefixes(self):
        names = ("space name", "tab\tname", "line\nname", "-option", ":colon", ":0:double", "éclair")
        for index, path in enumerate(names):
            self.stage(path, str(index).encode() + b"\0" + b"-----BEGIN " + b"PRIVATE KEY-----")
        self.assert_same_findings()

    def test_stage_ambiguous_filename_is_rejected_not_misread(self):
        for stage in range(4):
            path = f"{stage}:other.txt"
            self.stage(path, b"authored")
            with self.assertRaisesRegex(RuntimeError, "stage-ambiguous"):
                list(AUDIT.index_blobs())
            self.git("update-index", "--force-remove", path)

    def test_non_utf8_filename_retains_fail_closed_behavior(self):
        self.stage(os.fsdecode(b"invalid-\xff"), b"authored")
        with self.assertRaises(UnicodeDecodeError):
            self.git("ls-files", "-z").decode()
        with self.assertRaises(UnicodeDecodeError):
            list(AUDIT.index_blobs())

    def test_every_existing_violation_and_compressed_recipe_is_unchanged(self):
        uuid = b"-".join((b"12345678", b"1234", b"1234", b"1234", b"123456789abc"))
        sensitive = b"\n".join(
            (
                b"/" + b"Users/audit-fixture/private",
                b"/mnt/expand/" + uuid,
                b"-----BEGIN " + b"PRIVATE KEY-----",
                b"audit-fixture" + b"@example.invalid",
                b'{"device_serial":' + b'"synthetic-fixture"}',
            )
        )
        self.stage("work/capture.log", sensitive)
        self.stage("environment/unreviewed.txt", sensitive)
        header = json.dumps({"input_id": "synthetic"}).encode() + b"\n"
        row = json.dumps({"path": "original.bundle", "sha256": "synthetic", "members": []}).encode() + b"\n"
        self.stage("recipe/authored.jsonl.gz", gzip.compress(header + row, mtime=0))
        self.stage("recipe/malformed.jsonl.gz", b"not compressed")
        self.stage("docs/assets/branding/ror2-android-icon.png", b"not the reviewed image")
        findings = self.assert_same_findings()
        for label in AUDIT.PATTERNS:
            self.assertTrue(any(item.endswith(": " + label) for item in findings), label)
        self.assertIn("recipe/malformed.jsonl.gz: invalid compressed recipe", findings)

    def test_empty_and_intent_to_add_indexes(self):
        self.assert_same_findings()
        (self.root / "intent.txt").write_bytes(b"not staged")
        self.git("add", "--intent-to-add", "intent.txt")
        self.assert_same_findings()
        self.assertEqual(list(AUDIT.index_blobs()), [("intent.txt", b"")])

    def test_unmerged_index_is_rejected_instead_of_choosing_a_stage(self):
        object_id = self.stage("conflict.txt", b"base")
        self.git("update-index", "--force-remove", "conflict.txt")
        for stage in (1, 2, 3):
            self.git("update-index", "--index-info", data=b"100644 " + object_id + b" " + str(stage).encode() + b"\tconflict.txt\n")
        with self.assertRaises(subprocess.CalledProcessError):
            self.legacy_blobs()
        with self.assertRaisesRegex(RuntimeError, "unresolved merge"):
            list(AUDIT.index_blobs())

    def test_unavailable_blob_is_rejected_not_skipped(self):
        self.git("update-index", "--add", "--cacheinfo", "100644", "1" * 40, "missing.txt")
        with self.assertRaises(subprocess.CalledProcessError):
            self.legacy_blobs()
        with self.assertRaisesRegex(RuntimeError, "staged blob"):
            list(AUDIT.index_blobs())

    def test_gitlink_retains_git_show_behavior(self):
        self.stage("ordinary.txt", b"authored text")
        self.git("commit", "--quiet", "-m", "Synthetic submodule commit")
        commit = self.git("rev-parse", "HEAD").strip()
        self.git("update-index", "--add", "--cacheinfo", "160000", commit, "submodule")
        self.assert_same_findings()

    def test_blob_scan_uses_one_reader_process_not_one_per_path(self):
        for index in range(12):
            self.stage(f"file-{index}.txt", str(index).encode())
        with patch.object(AUDIT.subprocess, "Popen", wraps=subprocess.Popen) as popen:
            self.assertEqual(len(list(AUDIT.index_blobs())), 12)
        self.assertEqual([call.args[0] for call in popen.call_args_list], [["git", "ls-files", "--stage", "-z"], ["git", "cat-file", "--batch"]])


class PublicAuditPrefilterTests(unittest.TestCase):
    @staticmethod
    def original_patterns(path, data):
        # Independent pre-optimization oracle: unconditional substitution and
        # every original regex, with no use of the new necessary-byte filters.
        if path.startswith("recipe/"):
            data = AUDIT.WWISE_ASSET_NAME.sub(b"Wwise/ScriptableObjects/WWISE-ASSET.asset", data)
        return [label for label, pattern in AUDIT.PATTERNS.items() if re.search(pattern, data)]

    def test_prefilters_preserve_all_patterns_at_every_position(self):
        uuid = b"-".join((b"12345678", b"1234", b"abcd", b"ABCD", b"123456789abc"))
        markers = (
            b"/" + b"Users/synthetic-fixture/private",
            b"/" + b"home/synthetic-fixture/private",
            b"/MnT/ExPaNd/" + uuid,
            uuid,
            b"-----BEGIN " + b"PRIVATE KEY-----",
            b"-----BEGIN " + b"RSA PRIVATE KEY-----",
            b"synthetic-fixture" + b"@example.invalid",
            b'{"DeViCe_SeRiAl":' + b'"synthetic-fixture"}',
        )
        padding = b"encoded" * 10000
        samples = [b"", padding, bytes(range(256))]
        rng = random.Random(0)
        samples.extend(rng.randbytes(2048) for _ in range(64))
        for marker in markers:
            samples.extend((marker + padding, padding + marker, padding + marker + padding, b"\0" + marker + b"\0"))
        for path in ("docs/authored.txt", "recipe/authored.json"):
            for index, data in enumerate(samples):
                with self.subTest(path=path, sample=index):
                    self.assertEqual(AUDIT.violations(path, data), self.original_patterns(path, data))

    def test_wwise_prefix_gate_preserves_ascii_case_folding_and_other_uuids(self):
        uuid = b"-".join((b"12345678", b"1234", b"abcd", b"ABCD", b"123456789abc"))
        prefix = b"wwise/scriptableobjects/"
        prefixes = [prefix, prefix.upper()]
        prefixes.extend(prefix[:index] + prefix[index : index + 1].upper() + prefix[index + 1 :] for index in range(len(prefix)))
        for variant in prefixes:
            for tail in (b"", b" " + uuid):
                data = variant + b"Event/" + uuid + b".asset" + tail
                for path in ("recipe/authored.json", "docs/authored.txt"):
                    with self.subTest(prefix=variant, extra_uuid=bool(tail), path=path):
                        self.assertEqual(AUDIT.violations(path, data), self.original_patterns(path, data))

    def test_compressed_recipe_checks_every_row_with_unchanged_findings(self):
        rows = [json.dumps({"input_id": "synthetic"}).encode() + b"\n"]
        for marker in ("synthetic" + "@example.invalid", "/" + "home/synthetic-fixture/private", "-----BEGIN " + "PRIVATE KEY-----"):
            rows.append(json.dumps({"path": marker, "sha256": "synthetic", "members": []}).encode() + b"\n")
        expected = sorted({label for row in rows for label in self.original_patterns("recipe/authored.jsonl", row)})
        data = gzip.compress(b"".join(rows), mtime=0)
        self.assertEqual(AUDIT.violations("recipe/authored.jsonl.gz", data), expected)


if __name__ == "__main__":
    unittest.main()
