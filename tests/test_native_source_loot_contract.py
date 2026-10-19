#!/usr/bin/env python3
"""Public synthetic contracts and host execution of the extracted production lease."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/native_source_loot_fixture.json"
WORLD = ROOT / "tools/unity/runtime/world/WholeInteractableBoundary.cs"
LIFECYCLE = (ROOT / "tools/unity/runtime/stage/SourceStageIdentityLifecycle.cs").read_text()
HARNESS = ROOT / "tests/fixtures/native_source_loot_lease_harness.cs"


def production_lease_source():
    source = WORLD.read_text()
    marker = "internal sealed class NativeBorrowedFieldLease<T>"
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("production lease class has unbalanced braces")


class NativeSourceLootContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())
        cls.world = WORLD.read_text()

    def test_reviewed_cohorts_and_known_current_table_consumers_are_explicit(self):
        cohorts = self.fixture["source_cohorts"]
        self.assertEqual(cohorts["golemplains"]["identity_count"], 5)
        self.assertEqual(cohorts["lakes"]["identity_count"], 8)
        lakes = {entry["component"]: entry for entry in self.fixture["lakes_native_table_consumers"]}
        self.assertEqual(lakes["ChestBehavior"]["tables"], ["dtChest2"])
        self.assertTrue(lakes["ChestBehavior"]["handled"])
        self.assertEqual(lakes["WakeController"]["tables"], ["dtCursedItemTable", "dtTier2Item", "dtTier1Item"])
        self.assertTrue(lakes["WakeController"]["handled"])
        self.assertFalse(lakes["PickupPickerController"]["handled"])
        self.assertFalse(lakes["CreatePickupsFromDropTable"]["handled"])
        self.assertEqual(lakes["PickupPickerController"]["count"], 2)
        self.assertEqual(lakes["PickupPickerController"]["tables"], ["Chest2:null/null", "Scrapper:pdtUnscrappableItems/null"])
        self.assertEqual(lakes["CreatePickupsFromDropTable"]["tables"], [None])
        self.assertIn('GetComponentsInChildren<ChestBehavior>(true)', self.world)
        self.assertIn('GetComponentsInChildren<WakeController>(true)', self.world)
        self.assertIn('sourceDropTable == null', self.world)
        self.assertIn('pickers.Length == 2', self.world)
        self.assertIn('component.excludedItemsDropTable.name == "pdtUnscrappableItems"', self.world)
        self.assertIn('!component.includedItemsDropTable', self.world)
        self.assertIn('pickupCreators.Length == 1', self.world)
        self.assertIn('ReferenceEquals(pickupCreators[0], wake.shamanPickupCreator)', self.world)

    def test_owned_tables_clone_and_regenerate_from_current_run_without_rolls(self):
        prepare = self.world[self.world.index("public void PrepareNativeSourceInteractableTables"):
                             self.world.index("public void RestoreNativeSourceInteractableTables")]
        self.assertEqual(prepare.count("PrepareNativeBasicTable(scene,"), 4)
        self.assertIn("coordinator.ObjectiveDropTable(source)", prepare)
        self.assertIn("owned.RegenerateDropTable(Run.instance)", prepare)
        self.assertIn("ExpectedNativeBasicChoices(source, Run.instance)", prepare)
        self.assertIn("JsonUtility.ToJson(owned) == originalConfiguration", prepare)
        self.assertIn("JsonUtility.ToJson(source) == originalConfiguration", prepare)
        self.assertNotIn("GeneratePickup(", prepare)
        self.assertNotIn("nextUlong", prepare)
        self.assertNotIn("treasureRng", prepare)
        self.assertNotIn("onRunStartGlobal", prepare)

    def test_resources_and_borrowed_fields_are_transactionally_ordered(self):
        prepare = self.world[self.world.index("void PrepareNativeBasicTable"):
                             self.world.index("static bool IsSupportedNativeBasicTable")]
        self.assertLess(prepare.index("coordinator.ObjectiveDropTable"), prepare.index("nativeSourceDropTableBindings.Add(binding)"))
        self.assertLess(prepare.index("nativeSourceDropTableBindings.Add(binding)"), prepare.index("binding.lease.Bind()"))
        restore = self.world[self.world.index("public void RestoreNativeSourceInteractableTables"):
                             self.world.index("public GameObject WholeInteractableTemplate")]
        self.assertIn("for (int i = nativeSourceDropTableBindings.Count - 1", restore)
        self.assertLess(restore.index("binding.lease.Restore()"), restore.index("nativeSourceDropTableBindings.Clear()"))
        teardown = LIFECYCLE[LIFECYCLE.index("public void Dispose()"):
                              LIFECYCLE.index("void ValidateGlobalSceneIdentityCohort")]
        self.assertLess(teardown.index("RollbackOwnedIdentities();"), teardown.index("RestoreSourceInteractableTables(scene);"))
        self.assertLess(teardown.index("RestoreSourceInteractableTables(scene);"), teardown.index("foreach (var target in toggleStates)"))

    def test_extracted_production_lease_executes_bind_restore_refusal_and_partial_rollback(self):
        editor = Path(os.environ.get(
            "UNITY_EDITOR_PATH",
            "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        runtime = editor / "MonoBleedingEdge/bin/mono"
        if not compiler.is_file() or not runtime.is_file():
            self.skipTest("matching pinned editor Mono/Roslyn compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="native-source-loot-contract-") as temp:
            root = Path(temp)
            helper = root / "NativeBorrowedFieldLease.cs"
            executable = root / "lease-tests.exe"
            helper.write_text("using System;\n" + production_lease_source() + "\n")
            result = subprocess.run([str(runtime), str(compiler), "-nologo", "-out:" + str(executable),
                                     str(helper), str(HARNESS)], cwd=root, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            result = subprocess.run([str(runtime), str(executable)], cwd=root, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("partial rollback passed", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
