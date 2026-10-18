"""Synthetic complete-pair contracts; no third-party/game bodies, editor or device."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import export_additions as exports
import inherited_state
import unity_package_additions as packages
from authored_additions import shader_importer
from common import write
from composition_migration import stage_addition


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive_bytes(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, data in entries:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return stream.getvalue()


class NonshaderAdditionsTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.work = self.root / "work"
        self.recipe = self.root / "recipe"
        self.recipe.mkdir()
        self.ledger = copy.deepcopy(inherited_state.load_ledger())
        self.assets = exports.cohort(self.ledger) + packages.cohort(self.ledger)
        self.ledger["assets"] = self.assets
        write(self.work / "config/accepted-input.json", {"input_id": self.ledger["input_id"]})
        write(self.work / "config/reconstruction.json", {"input_id": self.ledger["input_id"], "projects": ["work/export"]})
        write(self.work / "config/composition-migration.json", {"input_id": self.ledger["input_id"], "previous_project": "work/previous"})
        self.export_recipe = copy.deepcopy(exports.load_recipe(self.ledger["input_id"]))
        self.package_recipe = copy.deepcopy(packages.load_recipe())
        self.texture, self.include = self.assets
        self.texture_data = b"synthetic PNG fixture\x00\r\n"
        self.texture_source = self.work / "export" / self.export_recipe["assets"][0]["source"]
        self.texture_source.parent.mkdir(parents=True)
        self.texture_source.write_bytes(self.texture_data)
        self.source_meta = Path(str(self.texture_source) + ".meta")
        self.source_meta.write_bytes(b"fileFormatVersion: 2\r\nguid: " + b"a" * 32 + b"\r\ntimeCreated: 10\r\nTextureImporter:\r\n  synthetic: 1\r\n")
        source = self.export_recipe["assets"][0]
        source.update(source_sha256=digest(self.texture_data), source_meta_sha256=digest(self.source_meta.read_bytes()), importer_time_created=20)
        self.texture_meta = self.source_meta.read_bytes().replace(b"a" * 32, self.texture["guid"].encode()).replace(b"timeCreated: 10", b"timeCreated: 20")
        self.texture.update(sha256=digest(self.texture_data), meta_sha256=digest(self.texture_meta))
        self.include_data = b"// authored synthetic include fixture\r\n"
        self.include_meta = shader_importer(self.include["guid"], shader=False)
        self.include.update(sha256=digest(self.include_data), meta_sha256=digest(self.include_meta))
        self.package_recipe["assets"][0]["source_sha256"] = digest(self.include_data)
        self.resource = archive_bytes([("fixture/pathname", self.package_recipe["assets"][0]["source"].encode()), ("fixture/asset", self.include_data)])
        self.install_package(self.resource)
        self.save_recipes()
        for module in (exports, packages):
            patcher = patch.object(module, "RECIPE", self.recipe)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, {"UNITY_EDITOR": str(self.root / "Unity.app/Contents/MacOS/Unity")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.rows = [{"old": a["path"], "target": a["project_path"], "guid": a["guid"]} for a in self.assets]

    def install_package(self, resource):
        self.archive = self.root / "Unity.app/Contents/Resources/PackageManager/Editor/com.unity.textmeshpro-3.0.6.tgz"
        self.archive.parent.mkdir(parents=True, exist_ok=True)
        raw = archive_bytes([(self.package_recipe["package"]["resource"], resource)])
        self.archive.write_bytes(raw)
        self.package_recipe["package"].update(sha256=digest(raw), resource_sha256=digest(resource))

    def save_recipes(self):
        write(self.recipe / "export-additions.json", self.export_recipe)
        write(self.recipe / "unity-package-additions.json", self.package_recipe)

    def snapshot(self):
        return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}

    def test_complete_pairs_and_stage_without_history_or_input_writes(self):
        before = self.snapshot()
        pairs = exports.prepare(self.rows, self.work, self.ledger)
        pairs.update(packages.prepare(self.rows, self.work, self.ledger))
        self.assertEqual(pairs[self.texture["path"]], (self.texture_data, self.texture_meta))
        self.assertEqual(pairs[self.include["path"]], (self.include_data, self.include_meta))
        self.assertEqual(self.snapshot(), before)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected history read")):
            for row in self.rows:
                stage_addition(row, pairs, self.work / "absent-history", self.root / "project", {}, {"rows": []})
        for row in self.rows:
            target = self.root / "project" / row["target"]
            self.assertEqual((target.read_bytes(), Path(str(target) + ".meta").read_bytes()), pairs[row["old"]])

    def test_identity_source_and_importer_drift_fail_independently(self):
        for target in (self.texture_source, self.source_meta):
            original = target.read_bytes()
            target.write_bytes(b"drift")
            with self.subTest(target=target.name), self.assertRaisesRegex(RuntimeError, "drift|hash mismatch"):
                exports.generate_pairs([self.texture], self.work)
            target.write_bytes(original)

    def test_final_body_and_importer_hashes_are_both_required(self):
        for module, asset in ((exports, self.texture), (packages, self.include)):
            for key in ("sha256", "meta_sha256"):
                changed = dict(asset, **{key: "0" * 64})
                kwargs = {"work": self.work} if module is exports else {}
                with self.subTest(module=module.__name__, key=key), self.assertRaisesRegex(RuntimeError, "differs from ledger"):
                    module.generate_pairs([changed], **kwargs)

    def test_selection_requires_all_members_and_exact_guid_and_target(self):
        for module in (exports, packages):
            selected = self.rows[0 if module is exports else 1]
            for rows in ([], [selected, selected], [dict(selected, guid="0" * 32)], [dict(selected, target="Assets/Other.asset")]):
                with self.subTest(module=module.__name__, rows=rows), self.assertRaises(RuntimeError):
                    module.prepare(rows, self.work, self.ledger)

    def test_accepted_input_and_reconstruction_gates(self):
        write(self.work / "config/accepted-input.json", {"input_id": "0" * 64})
        for module in (exports, packages):
            with self.subTest(module=module.__name__), self.assertRaisesRegex(RuntimeError, "different accepted input"):
                module.prepare(self.rows, self.work, self.ledger)
        with self.assertRaisesRegex(RuntimeError, "different accepted input"):
            exports.generate_pairs([self.texture], self.work)

    def test_source_symlink_escape_is_rejected(self):
        original = self.texture_source.read_bytes()
        outside = self.root / "outside.png"
        outside.write_bytes(original)
        self.texture_source.unlink()
        self.texture_source.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            exports.generate_pairs([self.texture], self.work)

    def test_archive_resource_source_and_importer_hashes_are_gated(self):
        for mutate in (
            lambda r: r["package"].update(sha256="0" * 64),
            lambda r: r["package"].update(resource_sha256="0" * 64),
            lambda r: r["assets"][0].update(source_sha256="0" * 64),
        ):
            recipe = copy.deepcopy(self.package_recipe)
            mutate(recipe)
            write(self.recipe / "unity-package-additions.json", recipe)
            with self.assertRaisesRegex(RuntimeError, "drift"):
                packages.generate_pairs([self.include])
        self.save_recipes()

    def test_ambiguous_or_nonregular_archive_members_fail_without_extraction(self):
        name = self.package_recipe["assets"][0]["source"].encode()
        for resource in (
            archive_bytes([("a/pathname", name), ("b/pathname", name)]),
            archive_bytes([("a/pathname", name), ("a/asset", self.include_data), ("a/asset", self.include_data)]),
        ):
            self.install_package(resource)
            self.save_recipes()
            with self.assertRaisesRegex(RuntimeError, "[Aa]mbiguous"):
                packages.generate_pairs([self.include])
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            link = tarfile.TarInfo("link")
            link.type, link.linkname = tarfile.SYMTYPE, "/outside"
            archive.addfile(link)
        with tarfile.open(fileobj=io.BytesIO(stream.getvalue())) as archive, self.assertRaisesRegex(RuntimeError, "invalid"):
            packages.member(archive, "link")

    def test_importer_time_must_be_unique_and_explicit(self):
        for raw in (b"guid: " + b"a" * 32 + b"\n", self.source_meta.read_bytes() + b"timeCreated: 30\n"):
            self.source_meta.write_bytes(raw)
            self.export_recipe["assets"][0]["source_meta_sha256"] = digest(raw)
            self.save_recipes()
            with self.assertRaisesRegex(RuntimeError, "missing or ambiguous"):
                exports.generate_pairs([self.texture], self.work)

    def test_recipe_schema_and_identity_operations_are_restricted(self):
        for module, original, filename in (
            (exports, self.export_recipe, "export-additions.json"),
            (packages, self.package_recipe, "unity-package-additions.json"),
        ):
            for change in ({"output": "Assets/../escape.png"}, {"guid": "bad"}, {"source_sha256": "bad"}):
                recipe = copy.deepcopy(original)
                recipe["assets"][0].update(change)
                write(self.recipe / filename, recipe)
                with self.subTest(module=module.__name__, change=change), self.assertRaises(RuntimeError):
                    module.load_recipe(self.ledger["input_id"]) if module is exports else module.load_recipe()
        self.save_recipes()
        self.export_recipe["assets"][0]["operations"] = [{"op": "invent_content"}]
        self.save_recipes()
        with self.assertRaisesRegex(RuntimeError, "Unsupported"):
            exports.load_recipe(self.ledger["input_id"])

    def test_inherited_check_compares_generated_pairs_with_ledger_without_history(self):
        before = self.snapshot()
        pairs = exports.generate_pairs([self.texture], self.work)
        pairs.update(packages.generate_pairs([self.include]))
        for asset in self.assets:
            target = self.work / "previous" / asset["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pairs[asset["path"]][0])
            Path(str(target) + ".meta").write_bytes(pairs[asset["path"]][1])
        before = self.snapshot()
        result = inherited_state.check(self.work, self.ledger)
        self.assertEqual(result["checked_generated_pairs"], 2)
        self.assertEqual(result["differences"], [])
        self.assertEqual(before, self.snapshot())
        target.write_bytes(b"drift")
        Path(str(target) + ".meta").unlink()
        self.assertEqual(inherited_state.check(self.work, self.ledger)["differences"], [])
        ledger = copy.deepcopy(self.ledger)
        for asset in ledger["assets"]:
            if asset["path"] == self.include["path"]:
                asset.update(sha256="0" * 64, meta_sha256="0" * 64)
        self.assertEqual(
            inherited_state.check(self.work, ledger)["differences"],
            [{"path": self.include["path"], "reason": "generated_pair"}, {"path": self.include["path"] + ".meta", "reason": "generated_pair"}],
        )

    def test_tracked_recipes_only_claim_proven_used_pairs(self):
        actual = inherited_state.load_ledger()
        claimed = exports.cohort(actual) + packages.cohort(actual)
        self.assertEqual(len(claimed), 2)
        self.assertTrue(all(a["usage"] == "used" and a["comparison"]["asset_matches"] and a["comparison"]["meta_matches"] for a in claimed))
        self.assertEqual({Path(a["path"]).name for a in claimed}, {"AndroidNativeWarpRamp.png", "TMPro_Properties.cginc"})
