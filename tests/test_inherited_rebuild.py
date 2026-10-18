"""Synthetic per-file regeneration, inherited hash gates and read-only real placement."""

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from common import read, sha, write
from composition_io import StageIO
import composition_migration
import inherited_rebuild as replay
import inherited_state
import rebuild


def digest(data):
    return hashlib.sha256(data).hexdigest()


class InheritedReplayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / "inputs"
        self.dest = self.root / "destination"
        self.recipe = self.root / "recipe"
        self.input_id = "a" * 64
        self.asset = dict(path="Assets/LabLoadingScene/Test.shader", project_path="Assets/LabLoadingScene/Test.shader", guid="b" * 32, status="inherited")
        self.body = b"synthetic shader"
        self.meta = replay.importer(self.asset)
        self.asset.update(sha256=digest(self.body), meta_sha256=digest(self.meta))
        self.ledger = dict(input_id=self.input_id, assets=[self.asset])
        self.rows = [dict(old=self.asset["path"], target=self.asset["project_path"], guid=self.asset["guid"])]
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        self.store = inherited_state.store_root(self.work, self.ledger)
        self.put(self.store / self.asset["path"], self.body)
        self.put(self.store / (self.asset["path"] + ".meta"), self.meta)
        self.config = dict(schema=1, input_id=self.input_id, texture_importers={})
        self.save()
        write(self.recipe / "inherited-rebuild-package.json", dict(assets=[]))
        for patcher in (patch.object(replay, "RECIPE", self.recipe), patch("unity_package_additions.generate_pairs", return_value={})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.io = StageIO(self.work, self.dest)

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save(self):
        write(self.recipe / "inherited-rebuild.json", self.config)

    def candidates(self):
        return replay.replacements(self.io, self.ledger)

    def prepare(self, generated):
        return inherited_state.prepare(self.rows, self.work, self.ledger, generated, {})

    def test_regenerated_importer_does_not_read_missing_store_file_and_preserves_remaining_hash_gate(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}
        generated = self.candidates()
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()})
        (self.store / (self.asset["path"] + ".meta")).unlink()
        pairs = self.prepare(generated)
        self.assertEqual(pairs[self.asset["path"]], (self.body, self.meta))
        self.put(self.store / self.asset["path"], b"drift")
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            self.prepare(generated)
        self.put(self.store / self.asset["path"], self.body)
        with self.assertRaises(FileNotFoundError):
            inherited_state.read_pair(self.store, self.asset)

    def test_replacement_hash_and_guid_remain_mandatory(self):
        path = self.asset["path"] + ".meta"
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            self.prepare({path: b"invalid"})
        self.asset["guid"] = "c" * 32
        self.rows[0]["guid"] = "c" * 32
        with self.assertRaisesRegex(RuntimeError, "GUID mismatch"):
            self.prepare({path: self.meta})

    def test_mismatching_candidate_keeps_verified_store_bytes(self):
        self.meta += b"user-defined historical field\n"
        self.asset["meta_sha256"] = digest(self.meta)
        self.put(self.store / (self.asset["path"] + ".meta"), self.meta)
        self.assertEqual(self.candidates(), {})
        self.assertEqual(self.prepare({})[self.asset["path"]][1], self.meta)

    def test_real_stage_addition_write_locations_and_rebuild_origin_counts(self):
        generated = self.candidates()
        origins = {}
        pairs = inherited_state.prepare(self.rows, self.work, self.ledger, generated, origins)
        live = StageIO(self.work)
        composition_migration.stage_addition(self.rows[0], pairs, None, live.project, {}, {"rows": []}, live)
        self.assertEqual((live.project / self.asset["path"]).read_bytes(), self.body)
        self.assertEqual((live.project / (self.asset["path"] + ".meta")).read_bytes(), self.meta)
        self.io.inherited_origins = origins
        paths = {self.asset["path"] + suffix for suffix in ("", ".meta")}
        provenance = {p: dict(producer="inherited-store") for p in paths}
        with patch("inherited_state.load_ledger", return_value=self.ledger):
            result = replay.report(self.io, paths, provenance)
        self.assertEqual(result["counts"], dict(regenerated=1, still_inherited=1))
        self.assertFalse(result["j558_satisfied"])

    def test_texture_importer_reuses_hash_pinned_export_without_reading_body(self):
        path = "Assets/LabLoadingScene/Resources/AndroidNativeEliteRamp.png"
        original = b"fileFormatVersion: 2\nguid: " + b"c" * 32 + b"\ntimeCreated: 1\nTextureImporter: {}\n"
        self.asset.update(path=path, project_path=path)
        source = "Assets/texture.png.meta"
        self.put(self.work / "export" / source, original)
        self.config["texture_importers"] = {path + ".meta": dict(source=source, source_sha256=digest(original), guid=self.asset["guid"], time_created=2)}
        self.save()
        write(self.work / "config/reconstruction.json", dict(input_id=self.input_id, projects=["work/export"]))
        target = original.replace(b"c" * 32, b"b" * 32).replace(b"timeCreated: 1", b"timeCreated: 2")
        self.asset["meta_sha256"] = digest(target)
        self.assertEqual(self.candidates(), {path + ".meta": target})
        self.put(self.work / "export" / source, b"drift")
        with self.assertRaisesRegex(RuntimeError, "source drift"):
            self.candidates()

    def test_input_and_package_identity_drift_fail_closed(self):
        self.config["input_id"] = "f" * 64
        self.save()
        with self.assertRaisesRegex(RuntimeError, "accepted input"):
            self.candidates()
        self.config["input_id"] = self.input_id
        self.save()
        write(self.recipe / "inherited-rebuild-package.json", dict(assets=[dict(output="Assets/Absent.cginc")]))
        with self.assertRaisesRegex(RuntimeError, "membership drift"):
            self.candidates()

    def test_package_candidates_are_independently_hash_gated_per_file(self):
        path = self.asset["path"]
        write(self.recipe / "inherited-rebuild-package.json", dict(assets=[dict(output=path)]))
        with patch("unity_package_additions.generate_pairs", return_value={path: (b"different body", self.meta)}) as generate:
            result = self.candidates()
        self.assertNotIn(path, result)
        self.assertEqual(result[path + ".meta"], self.meta)
        self.assertEqual(self.prepare(result)[path], (self.body, self.meta))
        self.assertFalse(generate.call_args.kwargs["verify"])

    def test_r9_coverage_classifies_known_editor_outputs_separately(self):
        public = read(Path(__file__).resolve().parents[1] / "recipe/rebuild-r9-obligations.json")
        provenance = {p: dict(producer="unknown") for p in public["files"]}
        provenance["Assets/Unknown.asset"] = dict(producer="unknown")
        result = rebuild.provenance_coverage(provenance)
        self.assertEqual(set(result["r9_obligations"]), set(public["files"]))
        self.assertEqual(set(result["uncovered"]), {"Assets/Unknown.asset"})


if __name__ == "__main__":
    unittest.main()
