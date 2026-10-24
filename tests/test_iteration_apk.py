"""Authored APK records exercise preservation, deletion and refusal contracts."""

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import iteration_apk as apk
from build_timing import PhaseTiming, bee_timing, trace_events
import common


class IterationApkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "base.apk"

    def base_apk(self):
        with zipfile.ZipFile(self.base, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"authored manifest")
            archive.writestr("assets/audio.wem", b"authored audio bytes" * 2000, compress_type=zipfile.ZIP_STORED)
            archive.writestr(apk.NATIVE, b"old native bytes", compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr(apk.METADATA, b"old metadata")
            archive.writestr("assets/removed", b"obsolete")
            archive.writestr("META-INF/CERT.SF", b"obsolete signature")
            archive.writestr("META-INF/MANIFEST.MF", b"obsolete manifest")

    def test_splice_preserves_members_compression_and_replaces_complete_data(self):
        self.base_apk()
        native = self.root / "fresh.so"
        native.write_bytes(b"fresh native bytes")
        meta = self.root / "fresh.dat"
        meta.write_bytes(b"fresh metadata")
        new = self.root / "new"
        new.write_bytes(b"fresh serialized Data")
        output = self.root / "splice.apk"
        # Unchanged data must never pass through ZipFile.open/read (and hence
        # decompression) in the splice path.
        with patch.object(zipfile.ZipFile, "read", side_effect=AssertionError("decompressed old member")):
            apk.splice(self.base, output, {apk.NATIVE: native, apk.METADATA: meta, "assets/new": new}, {"assets/removed"})
        with zipfile.ZipFile(self.base) as before, zipfile.ZipFile(output) as after:
            self.assertIsNone(after.testzip())
            self.assertEqual(after.read(apk.NATIVE), native.read_bytes())
            self.assertEqual(after.read(apk.METADATA), meta.read_bytes())
            self.assertEqual(after.read("assets/new"), new.read_bytes())
            self.assertEqual(before.read("assets/audio.wem"), after.read("assets/audio.wem"))
            self.assertEqual(after.getinfo(apk.NATIVE).compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(after.getinfo("assets/audio.wem").compress_type, zipfile.ZIP_STORED)
            self.assertFalse(any(apk.signature(name) for name in after.namelist()))
            self.assertNotIn("assets/removed", after.namelist())
        # Independent ZIP writer acts as a byte oracle, not the splice reader.
        oracle = self.root / "oracle.apk"
        with zipfile.ZipFile(oracle, "w") as z:
            for name, data in {
                "AndroidManifest.xml": b"authored manifest",
                "assets/audio.wem": b"authored audio bytes" * 2000,
                apk.NATIVE: native.read_bytes(),
                apk.METADATA: meta.read_bytes(),
                "assets/new": new.read_bytes(),
            }.items():
                z.writestr(name, data)
        self.assertTrue(apk.compare_members(output, oracle)["equal"])

    def test_refuses_overwrite_unsafe_names_and_duplicate_members(self):
        self.base_apk()
        with self.assertRaisesRegex(RuntimeError, "new"):
            apk.splice(self.base, self.base, {})
        for name in ("../escape", "/absolute", "x/../y", "x\\y", "META-INF/CERT.RSA"):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "Unsafe"):
                apk.splice(self.base, self.root / "new.apk", {name: self.base})
        with zipfile.ZipFile(self.base, "a") as z:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                z.writestr(apk.NATIVE, b"ambiguous")
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            apk.splice(self.base, self.root / "new.apk", {})

    def test_comparison_does_not_hide_build_metadata_or_missing_members(self):
        self.base_apk()
        candidate = self.root / "candidate.apk"
        changed = self.root / "changed"
        changed.write_bytes(b"different metadata")
        apk.splice(self.base, candidate, {apk.METADATA: changed})
        report = apk.compare_members(self.base, candidate)
        self.assertFalse(report["equal"])
        self.assertEqual(report["changed"], [apk.METADATA])

    def test_packaging_gate_observes_java_manifest_and_resource_drift(self):
        for module in ("launcher", "unityLibrary"):
            root = self.root / module / "src/main"
            root.mkdir(parents=True)
            (root / "AndroidManifest.xml").write_text("authored manifest")
        java = self.root / "unityLibrary/src/main/java/Owner.java"
        java.parent.mkdir()
        java.write_text("class Owner {}")
        first = apk.packaging_inputs(self.root)
        java.write_text("class Owner { int changed; }")
        self.assertNotEqual(apk.packaging_inputs(self.root), first)
        java.unlink()
        java.symlink_to(self.base)
        with self.assertRaisesRegex(RuntimeError, "symlinks"):
            apk.packaging_inputs(self.root)

    def test_export_requires_complete_fresh_arm64_and_metadata(self):
        for name in (apk.NATIVE, apk.METADATA, "assets/bin/Data/globalgamemanagers", "assets/bin/Data/boot.config"):
            relative = "jniLibs/" + name.removeprefix("lib/") if name.startswith("lib/") else name
            target = self.root / "unityLibrary/src/main" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"authored")
        with self.assertRaisesRegex(RuntimeError, "ARM64"):
            apk.export_members(self.root)
        native = self.root / "unityLibrary/src/main/jniLibs/arm64-v8a/libil2cpp.so"
        native.write_bytes(b"\x7fELF\x02\x01\x01" + bytes(9) + struct.pack("<HH", 3, 183))
        self.assertIn(apk.METADATA, apk.export_members(self.root))
        (self.root / "unityLibrary/src/main" / apk.METADATA).unlink()
        with self.assertRaisesRegex(RuntimeError, "complete"):
            apk.export_members(self.root)


class BuildTimingTests(unittest.TestCase):
    def test_phases_record_failures_without_double_counting_wall_time(self):
        ticks = iter([10, 11, 13, 15])
        timing = PhaseTiming(clock=lambda: next(ticks))
        with self.assertRaises(ValueError), timing.phase("failed"):
            raise ValueError("expected")
        self.assertEqual(timing.report(), {"wall_seconds": 5, "phases_seconds": {"failed": 2}})

    def test_bee_stream_parallel_union_and_old_request_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bee = root / "Library/Bee"
            bee.mkdir(parents=True)
            events = [
                {"ph": "X", "name": "C_Android_arm64", "ts": 100_000_000, "dur": 4_000_000},
                {"ph": "X", "name": "C_Android_arm64", "ts": 102_000_000, "dur": 4_000_000},
                {"ph": "X", "name": "UnityLinker", "ts": 90_000_000, "dur": 4_000_000},
            ]
            path = bee / "backend_profiler0.traceevents"
            path.write_text(",\n".join(json.dumps(v) for v in events) + ",")
            self.assertEqual(trace_events(path), events)
            report = bee_timing(root, 99, 110)["phases"]
            self.assertEqual(report["cpp_compile"], {"jobs": 2, "work_seconds": 8, "active_wall_seconds": 6})
            self.assertNotIn("unity_linker", report)

    def test_hash_session_reuses_only_unchanged_identity_and_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authored"
            path.write_bytes(b"first")
            expected = hashlib.sha256(b"other").hexdigest()
            with patch.object(common.hashlib, "sha256", wraps=hashlib.sha256) as hashing:
                with common.cached_hashes():
                    self.assertEqual(common.sha(path), common.sha(path))
                    self.assertEqual(hashing.call_count, 1)
                    path.write_bytes(b"other")
                    self.assertEqual(common.sha(path), expected)
                    self.assertEqual(hashing.call_count, 2)
                common.sha(path)
                self.assertEqual(hashing.call_count, 3)


if __name__ == "__main__":
    unittest.main()
