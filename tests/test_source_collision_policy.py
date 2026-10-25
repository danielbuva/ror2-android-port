"""Source-derived physics policy staging; synthetic inputs contain no game data."""

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import whole_catalog
from composition_io import StageIO


class SourceCollisionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.project = self.work / "lab-project"
        self.game = self.root / "input"
        self.source = self.game / "Risk of Rain 2_Data/globalgamemanagers"
        self.put(self.source, b"synthetic physics settings")
        self.put(self.game / "Risk of Rain 2_Data/Managed/RoR2.dll", b"synthetic managed identity")
        self.write(self.work / "config/local.json", {"game_path": str(self.game)})
        self.write(self.work / "config/accepted-input.json", {"input_id": "synthetic"})
        self.write(
            self.work / "inventory/files.json",
            {
                "input_id": "synthetic",
                "files": [{"path": "Risk of Rain 2_Data/globalgamemanagers", "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}],
            },
        )
        self.layers = [f"Layer {i}" for i in range(32)]
        self.rows = [0xFFFFFFFF] * 32
        self.rows[14] &= ~(1 << 14)
        self.rows[14] &= ~(1 << 7)
        self.rows[7] &= ~(1 << 14)
        self.settings(self.project)
        self.load = patch.dict(
            sys.modules,
            {
                "UnityPy": SimpleNamespace(
                    load=lambda _: SimpleNamespace(
                        objects=[
                            SimpleNamespace(type=SimpleNamespace(name="PhysicsManager"), read_typetree=lambda: {"m_LayerCollisionMatrix": self.rows}),
                            SimpleNamespace(type=SimpleNamespace(name="TagManager"), read_typetree=lambda: {"layers": self.layers}),
                        ]
                    )
                )
            },
        )
        self.load.start()
        self.addCleanup(self.load.stop)

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def write(self, path, data):
        self.put(path, json.dumps(data).encode())

    def settings(self, project):
        self.put(
            project / "ProjectSettings/TagManager.asset",
            ("TagManager:\n  layers:\n" + "".join(f"  - {name}\n" for name in self.layers) + "  m_SortingLayers: []\n").encode(),
        )
        self.physics = project / "ProjectSettings/DynamicsManager.asset"
        self.before = "PhysicsManager:\n  m_QueriesHitTriggers: 1\n  m_LayerCollisionMatrix: " + "ff" * 128 + "\n  m_Gravity: preserved\n"
        self.put(self.physics, self.before.encode())

    def test_exact_source_rows_without_other_setting_or_input_changes(self):
        whole_catalog.stage_source_collision_policy(StageIO(self.work))
        after = self.physics.read_text()
        encoded = after.split("m_LayerCollisionMatrix: ")[1].splitlines()[0]
        self.assertEqual(list(struct.unpack("<32I", bytes.fromhex(encoded))), self.rows)
        self.assertEqual(after.replace(encoded, "ff" * 128), self.before)
        self.assertEqual(self.source.read_bytes(), b"synthetic physics settings")
        receipt = json.loads((self.project / ".rebuild/source-collision-policy.json").read_text())
        self.assertEqual(receipt["rows"], self.rows)
        self.assertEqual(receipt["layers"], self.layers)
        self.assertFalse(self.rows[14] & (1 << 14))
        self.assertTrue(self.rows[14] & (1 << 11))
        self.assertTrue(self.rows[14] & (1 << 12))

    def test_destination_uses_owned_pending_writes(self):
        destination = self.work / "reconstructed"
        self.settings(destination)
        io = StageIO(self.work, destination)
        whole_catalog.stage_source_collision_policy(io)
        self.assertEqual(self.physics.read_text(), self.before)
        self.assertIn(destination / "ProjectSettings/DynamicsManager.asset", io.pending)
        io.flush()
        self.assertEqual(json.loads((destination / ".rebuild/source-collision-policy.json").read_text())["rows"], self.rows)

    def test_bad_shapes_asymmetry_and_layer_drift_refuse_before_mutation(self):
        good = self.rows[:]
        for bad in (good[:-1], [True] * 32, [-1] * 32, [1 << 32] * 32, [float("nan")] * 32, [0] + good[1:]):
            with self.subTest(bad=bad[:1]):
                self.rows = bad
                with self.assertRaises(RuntimeError):
                    whole_catalog.stage_source_collision_policy(StageIO(self.work))
                self.assertEqual(self.physics.read_text(), self.before)
        self.rows = good
        self.layers[14] = "changed index"
        with self.assertRaisesRegex(RuntimeError, "layer names"):
            whole_catalog.stage_source_collision_policy(StageIO(self.work))
        self.assertEqual(self.physics.read_text(), self.before)

    def test_unknown_input_or_duplicate_target_field_refuses(self):
        self.put(self.source, b"changed")
        with self.assertRaisesRegex(RuntimeError, "accepted input"):
            whole_catalog.stage_source_collision_policy(StageIO(self.work))
        self.put(self.source, b"synthetic physics settings")
        self.put(self.physics, (self.before + "  m_LayerCollisionMatrix: " + "ff" * 128 + "\n").encode())
        with self.assertRaisesRegex(RuntimeError, "serialized shape"):
            whole_catalog.stage_source_collision_policy(StageIO(self.work))


if __name__ == "__main__":
    unittest.main()
