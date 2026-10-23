"""Execute the production asset owner and check its real lifecycle boundaries."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/catalog/OriginalEquipmentHighlightAssetsBoundary.cs"
FIXTURES = ROOT / "tests/fixtures"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class EquipmentHighlightAssetsOwnerTests(unittest.TestCase):
    def test_production_owner_contract(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        with tempfile.TemporaryDirectory(prefix="equipment-highlight-assets-") as name:
            executable = Path(name) / "owner-contract.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:9",
                    f"-out:{executable}",
                    str(SOURCE),
                    str(FIXTURES / "EquipmentHighlightOwnerStubs.cs"),
                    str(FIXTURES / "EquipmentHighlightOwnerProgram.cs"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("original-equipment-highlight-owner-contract: PASS", ran.stdout)

    def test_setup_precedes_spawn_and_release_precedes_bundle_unload(self):
        session = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text()
        stats = session.split("    IEnumerator OriginalStats(", 1)[1].split("    IEnumerator SpawnBoundary(", 1)[0]
        prepare = stats.index("PrepareOriginalEquipmentHighlightAssets();")
        self.assertLess(stats.index('"SetEquipmentDefs"'), prepare)
        self.assertLess(prepare, stats.index("SpawnBoundary(body, cfg)"))
        self.assertIn("!body.gameObject.activeInHierarchy", stats[:prepare])
        self.assertLess(stats.index("r.originalEquipmentHighlightAssets.ready", prepare), stats.index("SpawnBoundary(body, cfg)"))
        catalogs = (ROOT / "tools/unity/runtime/catalog/BodyCatalogBoundary.cs").read_text()
        cleanup = catalogs.split("    void CleanupBodyCatalog()", 1)[1].split("    BodyCatalogSession ", 1)[0]
        self.assertLess(cleanup.index("CleanupOriginalEquipmentHighlightAssets();"), cleanup.index("artifactBundle.Unload(true)"))
        self.assertLess(cleanup.index("CleanupOriginalEquipmentHighlightAssets();"), cleanup.index("WholeCatalogComposed.Release();"))
        world = (ROOT / "tools/unity/runtime/world/IntegratedWorldBoundary.cs").read_text()
        self.assertNotIn("CleanupOriginalEquipmentHighlightAssets();", world)


if __name__ == "__main__":
    unittest.main()
