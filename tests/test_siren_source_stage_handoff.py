"""Guard Siren source preflight/activation ordering against the Stage owner."""

import unittest
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "recipe/runtime-sources.json").is_file())
BOUNDARY = ROOT / "tools/unity/runtime/stage/IntegratedStageBoundary.cs"
SIREN = ROOT / "tools/unity/runtime/stage/SirenSourceEntrySession.cs"


def declaration(source: str, marker: str) -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
    raise AssertionError("unclosed declaration")


class SirenPreflightOrderTests(unittest.TestCase):
    def test_preflight_and_controller_activation_run_with_temporary_stage_current(self):
        source = declaration(BOUNDARY.read_text(), "public IEnumerator BeginOriginalStage()")
        prepare = source.index("SirenSourceEntrySession.Prepare(")
        retain = source.index("coordinator.RetainNativeLifecycleObject(sirenSourceEntry)")
        activate = source.index("sirenSourceEntry.ActivateAndSpawnController()")
        release = source.index('PortSession.Call(coordinator.objectiveStage, "OnDisable")')
        singletonCheck = source.index('coordinator.Check(!Stage.instance, "Temporary Stage singleton survived original handoff")')
        nativeCallback = source.index("Run.instance.OnServerSceneChanged(coordinator.stageGeometryScene.name)")
        dispatch = source.index("sirenSourceEntry.DispatchAfterNativeRunCallback(coordinator.objectiveStage)")
        self.assertEqual(source.count("SirenSourceEntrySession.Prepare("), 1)
        self.assertEqual(source.count("sirenSourceEntry.ActivateAndSpawnController()"), 1)
        self.assertEqual(source.count("Run.instance.OnServerSceneChanged(coordinator.stageGeometryScene.name)"), 1)
        self.assertEqual(source.count("ReferenceEquals(Stage.instance, coordinator.objectiveStage)"), 2)
        self.assertLess(prepare, retain)
        self.assertLess(retain, activate)
        self.assertIn('"Siren source preflight requires the exact temporary Stage owner"', source)
        self.assertIn('"Siren source activation requires the exact temporary Stage owner"', source)
        self.assertLess(activate, release)
        self.assertLess(release, singletonCheck)
        self.assertLess(singletonCheck, nativeCallback)
        self.assertLess(nativeCallback, dispatch)

    def test_fresh_owner_and_egg_input_off_guard_precedes_preflight_and_mutation(self):
        source = declaration(BOUNDARY.read_text(), "public IEnumerator BeginOriginalStage()")
        guard = source.index('"Siren source-entry attempt requires a fresh source owner and Siren egg input OFF"')
        prepare = source.index("SirenSourceEntrySession.Prepare(")
        retain = source.index("coordinator.RetainNativeLifecycleObject(sirenSourceEntry)")
        activate = source.index("sirenSourceEntry.ActivateAndSpawnController()")
        self.assertLess(guard, prepare)
        self.assertLess(prepare, retain)
        self.assertLess(retain, activate)
        self.assertIn('"Siren source preflight requires the exact temporary Stage owner"', source)
        self.assertIn('"Siren source activation requires the exact temporary Stage owner"', source)
        self.assertIn("!coordinator.r.diagnosticSirenEggInput", source)

    def test_preflight_and_activation_keep_native_stage_and_rng_requirements(self):
        source = SIREN.read_text()
        preflight = declaration(source, "void PreflightSource()")
        activation = declaration(source, "public void ActivateAndSpawnController()")
        for predicate in (
            "scene.isLoaded",
            "SceneManager.GetActiveScene() == scene",
            "NetworkServer.active",
            "Run.instance",
            "Stage.instance",
            "Run.instance.stageRng != null",
        ):
            self.assertIn(predicate, preflight)
        for predicate in ("NetworkServer.active", "Run.instance", "Stage.instance", "SceneManager.GetActiveScene() == scene"):
            self.assertIn(predicate, activation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
