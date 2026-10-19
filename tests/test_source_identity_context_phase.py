"""Host checks for the acyclic policy-only R5 / strict post-R6 context boundary."""

import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve()
REPO = next(parent for parent in HERE.parents if (parent / "scripts/lab/whole_catalog.py").is_file())
sys.path.insert(0, str(REPO / "scripts/lab"))
# Exercise the production module in the repository stack containing this test.
# Do not select the private authoring copy from an ancestor audit directory.
_draft = REPO / "scripts/lab"
_reader_path = _draft / "source_identity_metadata.py"
_reader_spec = importlib.util.spec_from_file_location("source_identity_metadata_under_test", _reader_path)
_reader_module = importlib.util.module_from_spec(_reader_spec)
_reader_spec.loader.exec_module(_reader_module)
sys.modules["source_identity_metadata"] = _reader_module
read_scene = _reader_module.read_scene
_catalog_path = _draft / "whole_catalog.py"
_catalog_spec = importlib.util.spec_from_file_location("source_identity_whole_catalog_under_test", _catalog_path)
whole_catalog = importlib.util.module_from_spec(_catalog_spec)
_catalog_spec.loader.exec_module(whole_catalog)
_yaml_spec = importlib.util.spec_from_file_location("source_identity_synthetic_yaml", HERE.with_name("test_source_identity_metadata.py"))
_yaml_module = importlib.util.module_from_spec(_yaml_spec)
_yaml_spec.loader.exec_module(_yaml_module)
synthetic_scene = _yaml_module.synthetic_scene


POOL_MONSTER = "a" * 32
POOL_INTERACTABLE = "b" * 32


def original_stage_scene():
    return f"""--- !u!1 &1
ScenePopulation:
  monsterDccsPool: {{fileID: 0, guid: {POOL_MONSTER}, type: 3}}
  interactableDccsPool: {{fileID: 0, guid: {POOL_INTERACTABLE}, type: 3}}
  ignoreArtifactsThatRebuildCards: 0
  contentSourceMixLimitOverride: 0
  contentSourceMixLimitOverrideValue: 0
  contentInteractableOnlySourceMixLimitOverride: 0
  contentInteractableOnlySourceMixLimitOverrideValue: 0
  sceneDirectorInteractibleCredits: 0
  sceneDirectorMonsterCredits: 0
  bonusInteractibleCreditObjects: []
--- !u!1 &2
SceneDirector:
  usePlacedSpawnPoints: 0
  expRewardCoefficient: 1.0
  eliteBias: 0.0
  spawnDistanceMultiplier: 1.0
  monsterSpawnTargetOverride: {{fileID: 0}}
"""


class SourceIdentityContextPhaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.export = self.root / "export"
        self.project = self.root / "project"
        original = self.export / "Assets/RoR2/Base/Scenes/golemplains/golemplains.unity"
        original.parent.mkdir(parents=True)
        original.write_text(original_stage_scene())
        self.pool_keys = {POOL_MONSTER: "monster-pool", POOL_INTERACTABLE: "interactable-pool"}

    def tearDown(self):
        self.temporary.cleanup()

    def test_r5_four_argument_call_remains_policy_only_without_source_scene_receipt(self):
        contexts = whole_catalog.original_stage_contexts(self.export, ["golemplains"], "input", self.pool_keys)
        self.assertNotIn("source_identity_schema_version", contexts)
        self.assertNotIn("source_identity_lifecycle", contexts["stages"]["golemplains"])

    def test_r7_strict_generation_requires_staged_source_and_matching_receipt(self):
        with self.assertRaisesRegex(RuntimeError, "not staged"):
            whole_catalog.original_stage_contexts(self.export, ["golemplains"], "input", self.pool_keys, self.project, {}, include_source_identity=True)

        source_scene = self.project / "Assets/LabLoadingScene/SourceScenes/golemplains/golemplains.unity"
        source_scene.parent.mkdir(parents=True)
        source_scene.write_text(synthetic_scene())
        metadata = read_scene(source_scene)
        with self.assertRaisesRegex(RuntimeError, "source-scene receipt"):
            whole_catalog.source_identity_lifecycle_metadata(self.project, "golemplains", {})
        with self.assertRaisesRegex(RuntimeError, "source-scene receipt"):
            whole_catalog.original_stage_contexts(self.export, ["golemplains"], "input", self.pool_keys, self.project, {}, include_source_identity=True)

        receipts = {"golemplains": metadata["source_scene_sha256"]}
        contexts = whole_catalog.original_stage_contexts(
            self.export, ["golemplains"], "input", self.pool_keys, self.project, receipts, include_source_identity=True
        )
        self.assertEqual(contexts["source_identity_schema_version"], 1)
        self.assertEqual(contexts["stages"]["golemplains"]["source_identity_lifecycle"], metadata)
        self.assertIn("receipt-bound", contexts["scope"])


if __name__ == "__main__":
    unittest.main()
