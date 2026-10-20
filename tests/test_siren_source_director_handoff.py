"""Public-source host contracts for the opt-in Siren source Director handoff."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "recipe/runtime-sources.json").is_file())
SOURCE_ROOT = ROOT / "tools/unity/runtime/stage"
BOUNDARY = SOURCE_ROOT / "IntegratedStageBoundary.cs"
OWNER = SOURCE_ROOT / "SirenSourceEntrySession.cs"


def declaration(source: str, marker: str) -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed declaration: {marker}")


class SirenSourceDirectorHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boundary = BOUNDARY.read_text(encoding="utf-8")
        cls.owner = OWNER.read_text(encoding="utf-8")
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        cls.compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        cls.mono = editor / "MonoBleedingEdge/bin/mono"

    def test_receipt_preflight_precedes_exact_id2_activation_and_population(self):
        source = self.boundary
        transport = declaration(source, "public IEnumerator TransportIntegratedStage(")
        moon_guard = transport.index("ManualMoonBoundary.RefuseTransport(")
        siren_attempt = transport.index("bool sirenSourceEntryAttempt =")
        objective = transport.index("coordinator.SpawnStageObjective(integratedStageConfig)")
        inactive_guard = transport.index("!coordinator.automaticDirectorHost.activeSelf", siren_attempt)
        prepare = transport.index("SirenSourceEntrySession.Prepare(", inactive_guard)
        retain = transport.index("coordinator.RetainNativeLifecycleObject(sirenSourceEntry)", prepare)
        activate = transport.index("coordinator.automaticDirectorHost.SetActive(true);", retain)
        record = transport.index("sirenSourceEntry.RecordOwnedDirectorActivation(", activate)
        populate = transport.index("coordinator.PopulateWholeStage()", record)
        begin = transport.index("BeginOriginalStage()", populate)

        self.assertLess(moon_guard, siren_attempt)
        self.assertLess(objective, prepare)
        self.assertLess(inactive_guard, prepare)
        self.assertLess(prepare, retain)
        self.assertLess(retain, activate)
        self.assertLess(activate, record)
        self.assertLess(record, populate)
        self.assertLess(populate, begin)
        self.assertEqual(transport.count("SirenSourceEntrySession.Prepare("), 1)
        self.assertIn("!coordinator.r.diagnosticSirenEggInput", transport[inactive_guard:prepare])
        self.assertIn("sirenSourceEntry == null", transport[inactive_guard:prepare])
        guard = transport.rindex("coordinator.Check(", 0, inactive_guard)
        self.assertIn("ReferenceEquals(Stage.instance, coordinator.objectiveStage)", transport[guard:prepare])
        default_branch = transport.index("if (!sirenSourceEntryAttempt)")
        default_activation = transport.index("coordinator.automaticDirectorHost.SetActive(true);", default_branch)
        self.assertLess(default_activation, objective)

    def test_exact_source_id2_id11_and_foreign_identity_guards_remain(self):
        owner = self.owner
        preflight = declaration(owner, "void PreflightSource()")
        self.assertIn('(uint?)controllerRows[0]["scene_id"] == ControllerSceneId', preflight)
        self.assertIn("controllerIdentity.sceneId.Value == ControllerSceneId", preflight)
        self.assertIn('controllerObject.name == "ToggleGroupController"', preflight)
        self.assertIn("!controllerObject.activeSelf && !IsRegistered(controllerIdentity)", preflight)
        self.assertIn("if (sceneId == DirectorSceneId)", preflight)
        self.assertIn('directorRoot.name == "Director"', preflight)
        self.assertIn("!directorRoot.activeSelf", preflight)
        self.assertIn("directorRoot.GetComponent<SceneDirector>()", preflight)
        self.assertIn("VerifyOwnedDirectorIdentityState();", preflight)
        self.assertIn("if (sceneId != ControllerSceneId && sceneId != DirectorSceneId && !nativeToggleTarget)", preflight)

        verify = declaration(owner, "void VerifyOwnedDirectorIdentityState()")
        self.assertIn("current.Length == 1", verify)
        self.assertIn('actualRoot.name == "Director"', verify)
        self.assertIn("ReferenceEquals(actualIdentity.gameObject, actualRoot)", verify)
        self.assertIn("MatchesOwnedSourceDirectorState(", verify)
        record = declaration(owner, "public void RecordOwnedDirectorActivation(GameObject root)")
        self.assertIn("ReferenceEquals(root, directorRoot)", record)
        self.assertIn("directorIdentity.sceneId.Value == DirectorSceneId", record)
        self.assertIn("!IsRegistered(directorIdentity)", record)
        self.assertIn("directorRootActivationExpected = true", record)
        self.assertIn("sceneId != ControllerSceneId && sceneId != DirectorSceneId", preflight)

    def test_id11_spawn_full_multicast_order_default_mode_and_moon_boundary(self):
        boundary = self.boundary
        transport = declaration(boundary, "public IEnumerator TransportIntegratedStage(")
        begin = declaration(boundary, "public IEnumerator BeginOriginalStage()")
        owner = self.owner
        activate_controller = declaration(owner, "public void ActivateAndSpawnController()")
        dispatch = declaration(owner, "public void DispatchAfterNativeRunCallback(Stage stage)")

        self.assertIn("sirenSourceEntry.ActivateAndSpawnController();", begin)
        self.assertLess(begin.index("sirenSourceEntry.ActivateAndSpawnController();"), begin.index("Run.instance.OnServerSceneChanged("))
        self.assertLess(begin.index("Run.instance.OnServerSceneChanged("), begin.index("sirenSourceEntry.DispatchAfterNativeRunCallback("))
        self.assertIn("controllerSpawnOwned && controllerIdentity.isServer && controllerNetworkId.Value != 0", activate_controller)
        self.assertIn("ReferenceEquals(NetworkServer.FindLocalObject(controllerNetworkId), controllerObject)", activate_controller)
        self.assertIn("ValidateFullNativeMulticast()", dispatch)
        self.assertIn("dispatchedHandlers.DynamicInvoke(scene.name)", dispatch)
        self.assertIn("globalDispatched = true", dispatch)
        self.assertIn("VerifyOwnedDirectorIdentityState();", dispatch)
        self.assertIn("foreach (var state in foreignSourceIdentities)", dispatch)
        self.assertIn("!IsRegistered(state.identity)", dispatch)
        self.assertIn("if (!sirenSourceEntryAttempt)", transport)
        self.assertIn("coordinator.automaticDirectorHost.SetActive(true);", transport)
        self.assertIn("ManualMoonBoundary.RefuseTransport(", transport)
        self.assertIn("coordinator.r.pauseBeforeMoon", transport)

    def test_production_owned_id2_state_predicate(self):
        if not self.compiler.is_file() or not self.mono.is_file():
            self.skipTest("pinned Unity Roslyn/Mono host compiler unavailable")
        contract = declaration(self.owner, "internal static bool MatchesOwnedSourceDirectorState(")
        harness = f"""using System;
public static class ProductionContract {{ {contract} }}
public static class Program {{
  static void Need(bool value, string message) {{ if (!value) throw new Exception(message); }}
  public static int Main() {{
    object root = new object(), identity = new object();
    bool Match(object actualRoot, object actualIdentity, bool active, bool expected, bool registered) =>
      ProductionContract.MatchesOwnedSourceDirectorState(root, actualRoot, identity, actualIdentity, active, expected, registered);
    Need(Match(root, identity, false, false, false), "receipt inactive root must pass before activation");
    Need(Match(root, identity, true, true, false), "recorded exact-root activation may pass");
    Need(!Match(root, identity, true, false, false), "unrecorded activation must fail");
    Need(!Match(root, identity, false, true, false), "unexpected deactivation must fail");
    Need(!Match(new object(), identity, true, true, false), "replacement root must fail");
    Need(!Match(root, new object(), true, true, false), "replacement identity must fail");
    Need(!Match(root, identity, true, true, true), "registered identity must fail");
    Need(!Match(null, identity, false, false, false), "missing root must fail");
    return 0;
  }}
}}
"""
        with tempfile.TemporaryDirectory(prefix="siren-director-handoff-") as temporary:
            temp = Path(temporary)
            source = temp / "ProductionContract.cs"
            executable = temp / "ProductionContract.exe"
            source.write_text(harness, encoding="utf-8")
            result = subprocess.run(
                [str(self.mono), str(self.compiler), "-nologo", "-langversion:9", "-target:exe", f"-out:{executable}", str(source)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            run = subprocess.run([str(self.mono), str(executable)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
