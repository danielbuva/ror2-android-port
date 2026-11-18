"""Synthetic receipts only; no retained game evidence or private replay required."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import historical_receipts as receipts
import input_migration
import scene_runtime
from common import write


class HistoricalReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = "work/retained/optional-presentation-transformation.json"
        self.data = dict(
            input_sha256="a" * 64,
            output_sha256="b" * 64,
            assembly_identity_preserved=True,
            type_field_method_contracts_preserved=True,
            module_identity_preserved=True,
            methods=["System.Void Fixture::Tick()"],
        )
        self.save_source()

    def save_source(self):
        write(self.root / self.source, self.data)
        self.digest = hashlib.sha256((self.root / self.source).read_bytes()).hexdigest()

    def pin(self):
        return receipts.pin(receipts.NAME, self.source, self.digest, root=self.root)

    def resolve(self, identity="a" * 64):
        return receipts.resolve(receipts.NAME, root=self.root, original_sha256=identity)

    def test_preserves_bytes_and_selection_at_non_timestamp_path(self):
        before = (self.root / self.source).read_bytes()
        selected = self.pin()
        self.assertEqual(self.resolve(), (self.data, selected))
        self.assertEqual((self.root / self.source).read_bytes(), before)
        self.assertEqual(selected["sha256"], self.digest)

    def test_missing_selection_fails_before_inventory_or_output(self):
        work = self.root / "work"
        baseline = work / "preserved"
        write(work / "inputs/latest-preserved.json", dict(path=str(baseline), input_id="fixture"))
        write(baseline / "receipt.json", dict(success=True, input_id="fixture"))
        write(baseline / "metadata/files.json", dict(files=[dict(path="Risk of Rain 2_Data/Managed/RoR2.dll", sha256="a" * 64)]))
        with patch.object(input_migration, "ROOT", self.root), patch.object(input_migration, "WORK", work), patch("inventory.inspect") as inspect:
            with self.assertRaisesRegex(RuntimeError, "Missing named historical receipt"):
                input_migration.check_update()
            inspect.assert_not_called()
        self.assertFalse((work / "experiments").exists())

    def test_does_not_replace_existing_selection(self):
        self.pin()
        with self.assertRaises(FileExistsError):
            self.pin()
        self.resolve()

    def test_rejects_drift_and_missing_source(self):
        self.pin()
        (self.root / self.source).write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            self.resolve()
        (self.root / self.source).unlink()
        with self.assertRaisesRegex(RuntimeError, "restore the specific retained evidence"):
            self.resolve()

    def test_rejects_wrong_preserved_input(self):
        self.pin()
        with self.assertRaisesRegex(RuntimeError, "does not match preserved"):
            self.resolve("c" * 64)

    def test_rejects_wrong_expected_hash(self):
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            receipts.pin(receipts.NAME, self.source, "c" * 64, root=self.root)
        self.assertFalse((self.root / "work/config").exists())

    def test_rejects_invalid_contracts(self):
        for changes in ({"methods": []}, {"methods": ["x", "x"]}, {"methods": [1]}, {"input_sha256": "bad"}, {"module_identity_preserved": False}):
            with self.subTest(changes=changes):
                original = self.data.copy()
                self.data.update(changes)
                self.save_source()
                with self.assertRaises(RuntimeError):
                    self.pin()
                self.data = original

    def test_rejects_unknown_name_and_escaping_or_symlink_paths(self):
        with self.assertRaisesRegex(RuntimeError, "Unknown historical receipt"):
            receipts.pin("../other", self.source, self.digest, root=self.root)
        for path in ("outside.json", "/tmp/outside.json", "work/../outside.json"):
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, "under ignored work"):
                receipts.pin(receipts.NAME, path, self.digest, root=self.root)
        (self.root / "work/link").symlink_to(self.root / "work/retained", target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlinks"):
            receipts.pin(receipts.NAME, "work/link/optional-presentation-transformation.json", self.digest, root=self.root)

    def test_rejects_selection_identity_tampering(self):
        selection = self.pin()
        selection["name"] = "different"
        write(self.root / "work/config/historical-receipts" / (receipts.NAME + ".json"), selection)
        with self.assertRaisesRegex(RuntimeError, "schema/name"):
            self.resolve()


class SceneHistoricalReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contracts = {
            receipts.SCENE_ASSEMBLIES: {"original_assemblies": {"Fixture.dll": "a" * 64}},
            receipts.AUDIO_IDENTITIES: {"rows": [{"resolved": True, "error": None} for _ in range(8)]},
            receipts.AUDIO_CLOSURE: {"unresolved": [], "files": [{"path": "Fixture/prefab.prefab", "sha256": "b" * 64}]},
            receipts.TELEPORT_QUERY: {
                "locations": [
                    {"internalId": "Assets/RoR2/Base/Common/TeleportOutController/matTPInOut.mat", "type": "UnityEngine.Material", "key": "fixture-material"}
                ]
            },
        }

    def pin(self, name, data=None):
        source = "work/retained/relocated/" + name + ".json"
        write(self.root / source, self.contracts[name] if data is None else data)
        digest = hashlib.sha256((self.root / source).read_bytes()).hexdigest()
        return receipts.pin(name, source, digest, root=self.root)

    def test_each_relocated_contract_is_explicit_hash_bound_and_read_only(self):
        for name, data in self.contracts.items():
            with self.subTest(name=name):
                selection = self.pin(name)
                self.assertEqual(receipts.resolve(name, root=self.root), (data, selection))
                path = self.root / selection["path"]
                before = path.read_bytes()
                receipts.resolve(name, root=self.root)
                self.assertEqual(path.read_bytes(), before)
                path.write_bytes(before + b" ")
                with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                    receipts.resolve(name, root=self.root)
                path.unlink()
                with self.assertRaisesRegex(RuntimeError, "restore the specific retained evidence"):
                    receipts.resolve(name, root=self.root)

    def test_missing_selections_fail_before_consumer_staging(self):
        with patch.object(scene_runtime, "ROOT", self.root), patch("build.preflight") as preflight:
            with self.assertRaisesRegex(RuntimeError, "Missing named historical receipt"):
                scene_runtime.scene_prepare()
            preflight.assert_not_called()
        with patch.object(scene_runtime, "ROOT", self.root), patch.object(scene_runtime, "startup_prepare") as startup:
            with self.assertRaisesRegex(RuntimeError, "Missing named historical receipt"):
                scene_runtime.audio_assets_prepare()
            startup.assert_not_called()
            self.pin(receipts.AUDIO_IDENTITIES)
            with self.assertRaisesRegex(RuntimeError, "Missing named historical receipt"):
                scene_runtime.audio_assets_prepare()
            startup.assert_not_called()
        with patch.object(scene_runtime, "ROOT", self.root), patch.object(scene_runtime, "body_root_order_prepare") as body:
            with self.assertRaisesRegex(RuntimeError, "Missing named historical receipt"):
                scene_runtime.body_start_loadout_prepare(teleport_material=True)
            body.assert_not_called()

    def test_valid_named_receipts_reach_existing_pipeline_without_relocating_evidence(self):
        for name in self.contracts:
            self.pin(name)
        for consumer, dependency, kwargs in (
            (scene_runtime.scene_prepare, "build.preflight", {}),
            (scene_runtime.audio_assets_prepare, "scene_runtime.startup_prepare", {}),
            (scene_runtime.body_start_loadout_prepare, "scene_runtime.body_root_order_prepare", {"teleport_material": True}),
        ):
            with (
                self.subTest(consumer=consumer.__name__),
                patch.object(scene_runtime, "ROOT", self.root),
                patch(dependency, side_effect=RuntimeError("pipeline boundary")) as pipeline,
            ):
                with self.assertRaisesRegex(RuntimeError, "pipeline boundary"):
                    consumer(**kwargs)
                pipeline.assert_called_once()
        self.assertFalse((self.root / "work/experiments").exists())

    def test_scene_contract_refusals(self):
        cases = (
            (receipts.SCENE_ASSEMBLIES, {"original_assemblies": {"../Fixture.dll": "a" * 64}}),
            (receipts.SCENE_ASSEMBLIES, {"original_assemblies": {"Fixture.dll": "bad"}}),
            (receipts.AUDIO_IDENTITIES, {"rows": [{"resolved": False, "error": None}] * 8}),
            (receipts.AUDIO_CLOSURE, {"unresolved": ["fixture"], "files": []}),
            (receipts.AUDIO_CLOSURE, {"unresolved": [], "files": [{"path": "../escape", "sha256": "b" * 64}]}),
            (receipts.TELEPORT_QUERY, {"locations": []}),
            (receipts.TELEPORT_QUERY, {"locations": self.contracts[receipts.TELEPORT_QUERY]["locations"] * 2}),
        )
        for name, data in cases:
            with self.subTest(name=name, data=data), self.assertRaises(RuntimeError):
                self.pin(name, data)

    def test_named_scene_selection_cannot_be_swapped_to_another_kind(self):
        selection = self.pin(receipts.SCENE_ASSEMBLIES)
        write(self.root / "work/config/historical-receipts" / (receipts.AUDIO_IDENTITIES + ".json"), selection)
        with self.assertRaisesRegex(RuntimeError, "schema/name"):
            receipts.resolve(receipts.AUDIO_IDENTITIES, root=self.root)


if __name__ == "__main__":
    unittest.main()
