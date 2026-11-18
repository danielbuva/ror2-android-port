"""Check the stage-owned rock spawner retirement ordering."""

from pathlib import Path
import unittest

RUNTIME = Path(__file__).resolve().parents[1] / "tools/unity/runtime"


class StageRockLifecycleTests(unittest.TestCase):
    def test_direct_entry_starts_owned_projectile_service_before_scene_activation(self):
        geometry = (RUNTIME / "stage/StageGeometryBoundary.cs").read_text()
        combat = (RUNTIME / "world/CombatSpineBoundary.cs").read_text()
        session = (RUNTIME / "session/PortSession.cs").read_text()

        direct_entry = geometry.split("public IEnumerator PrepareStageGeometry", 1)[1]
        self.assertLess(direct_entry.index("PrepareProjectileService();"), direct_entry.index("load.MoveNext()"))
        combat_setup = combat.split("public void PrepareCombatScene", 1)[1]
        self.assertIn("PrepareProjectileService();", combat_setup)
        release = combat.split("public void ReleaseProjectileService()", 1)[1]
        self.assertLess(release.index("coordinator.StopStageRockCoroutines();"), release.index("Destroy(projectileHost);"))
        session_cleanup = session.split("CleanupLanding();", 1)[1]
        self.assertLess(session_cleanup.index("ReleaseProjectileService();"), session_cleanup.index("NetworkServer.Shutdown();"))

    def test_owned_spawners_retire_before_their_services(self):
        geometry = (RUNTIME / "stage/StageGeometryBoundary.cs").read_text()
        transport = (RUNTIME / "stage/IntegratedStageBoundary.cs").read_text()
        gameplay = (RUNTIME / "input/NovaInputBoundary.cs").read_text()

        # Collect from the loaded scene, then drop its references at retirement.
        self.assertIn("var roots = coordinator.stageGeometryScene.GetRootGameObjects();", geometry)
        self.assertIn("var previewCallbacks = roots.SelectMany", geometry)
        self.assertIn("stageRockZones = previewCallbacks.OfType<MaulingRockZoneManager>().ToArray();", geometry)
        retirement = geometry.split("public void StopStageRockCoroutines()", 1)[1].split("public bool", 1)[0]
        self.assertIn("foreach (var zone in stageRockZones)", retirement)
        self.assertLess(retirement.index("zone.StopAllCoroutines();"), retirement.index("stageRockZones = Array.Empty"))

        transport_cleanup = transport.index("coordinator.StopStageRockCoroutines();")
        self.assertLess(transport_cleanup, transport.index("NetworkServer.Destroy(projectile.gameObject);"))
        run_cleanup = gameplay.index("coordinator.StopStageRockCoroutines();")
        self.assertLess(run_cleanup, gameplay.index("coordinator.CleanupRunClock();"))
        self.assertLess(run_cleanup, gameplay.index("coordinator.CleanupCombatScene();"))
        geometry_cleanup = geometry.split("public IEnumerator CleanupStageGeometry()", 1)[1]
        self.assertLess(geometry_cleanup.index("StopStageRockCoroutines();"), geometry_cleanup.index("SceneManager.UnloadSceneAsync"))
