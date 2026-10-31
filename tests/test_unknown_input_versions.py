"""Complete authored fingerprints, never filenames or unverified version hints."""

import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("version_importer", ROOT / "tools/phone-build/owner-apk/game_import.py")
IMPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORT)


def manifest(version, data, name="Data/game.txt"):
    return {"schema": 1, "game_version": version, "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}]}


class UnknownVersionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"schema": 2, "supported": [manifest("v2", b"new"), manifest("v1", b"old")], "recognized": [manifest("v0", b"ancient")]}

    def source(self, data, hint=None):
        return IMPORT.StreamSource({name: len(value) for name, value in data.items()}, lambda name: io.BytesIO(data[name]), game_version=hint)

    def test_all_supported_versions_selected_only_after_exact_fingerprints(self):
        for version, content in (("v1", b"old"), ("v2", b"new")):
            report = IMPORT.identify_version(self.source({"Data/game.txt": content}), self.catalog)
            self.assertEqual(report["status"], "supported")
            self.assertEqual(report["found_version"], version)
            self.assertEqual(report["manifest"]["game_version"], version)
            self.assertEqual(report["supported_versions"], ["v1", "v2"])

    def test_known_unsupported_is_identified_but_never_admitted(self):
        source = self.source({"Data/game.txt": b"ancient"})
        with self.assertRaises(IMPORT.VersionRefusal) as caught:
            IMPORT.select_version(source, self.catalog)
        self.assertEqual(caught.exception.report["status"], "unsupported")
        self.assertEqual(caught.exception.report["found_version"], "v0")
        self.assertIn("Supported versions: v1, v2", str(caught.exception))
        self.assertIn("maintainer", str(caught.exception))

    def test_unknown_missing_and_changed_same_name_report_unknown_not_guessed(self):
        for files in ({}, {"Data/game.txt": b"bad"}, {"Data/game.txt": b"old-modified"}):
            report = IMPORT.identify_version(self.source(files, hint="v1"), self.catalog)
            self.assertEqual(report["status"], "unknown")
            self.assertIsNone(report["manifest"])
            self.assertIsNone(report["found_version"])
            self.assertIn("unknown", report["message"])
            self.assertIn("complete, unmodified", report["message"])

    def test_extra_files_are_not_opened_and_labels_cannot_override_verified_bytes(self):
        opened = []
        source = IMPORT.StreamSource({"Data/game.txt": 3, "extra": 100}, lambda name: opened.append(name) or io.BytesIO(b"new"), game_version="v0")
        self.assertEqual(IMPORT.select_version(source, self.catalog)["game_version"], "v2")
        self.assertEqual(opened, ["Data/game.txt"])

    def test_unknown_size_reads_are_bounded_and_never_copy_or_modify_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            game = root / "Data/game.txt"
            game.parent.mkdir()
            game.write_bytes(b"unknown data")
            before = game.read_bytes()
            with self.assertRaises(IMPORT.VersionRefusal):
                IMPORT.select_version(IMPORT.FolderSource(root), self.catalog)
            self.assertEqual(game.read_bytes(), before)
            self.assertEqual(sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()), ["Data/game.txt"])
        stream = io.BytesIO(b"a" * 100)

        class RetainedStream(io.BytesIO):
            def close(self):
                pass

        stream = RetainedStream(b"a" * 100)
        report = IMPORT.identify_version(IMPORT.StreamSource({"Data/game.txt": None}, lambda name: stream), self.catalog)
        self.assertEqual(report["status"], "unknown")
        self.assertLessEqual(stream.tell(), 8)

    def test_duplicate_labels_and_indistinguishable_fingerprints_refused(self):
        for change in (lambda c: c["supported"].append(copy.deepcopy(c["supported"][0])), lambda c: c["recognized"].append(manifest("fake", b"new"))):
            catalog = copy.deepcopy(self.catalog)
            change(catalog)
            with self.assertRaises(ValueError):
                IMPORT.validate_catalog(catalog)

    def test_ambiguous_subset_match_refuses_without_guessing_most_specific(self):
        first = manifest("one", b"old")
        second = manifest("two", b"old")
        second["files"].append(manifest("unused", b"extra", "extra")["files"][0])
        report = IMPORT.identify_version(
            self.source({"Data/game.txt": b"old", "extra": b"extra"}), {"schema": 2, "supported": [first, second], "recognized": []}
        )
        self.assertEqual(report["status"], "ambiguous")
        self.assertIsNone(report["manifest"])

    def test_legacy_single_inventory_is_a_one_version_catalog(self):
        self.assertEqual(IMPORT.select_version(self.source({"Data/game.txt": b"old"}), manifest("legacy", b"old"))["game_version"], "legacy")

    def test_pause_cancel_and_unsafe_catalog_paths_are_refused_before_read(self):
        for action in ("pause", "cancel"):
            with self.assertRaises(IMPORT._Stopped):
                IMPORT.identify_version(self.source({"Data/game.txt": b"old"}), self.catalog, control=lambda: action)
        with self.assertRaises(ValueError):
            IMPORT.validate_catalog(manifest("invalid", b"data", "../escape"))
