from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono")
CSC = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe")


class MaterialCacheOwnerTests(unittest.TestCase):
    def test_authored_owner_against_synthetic_source_contracts(self) -> None:
        if not (MONO.is_file() and CSC.is_file()):
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")
        owner = ROOT / "tools/unity/runtime/input/CharacterModelMaterialCacheOwner.cs"
        fixture = ROOT / "tests/fixtures/character_model_material_cache_owner.cs"
        with tempfile.TemporaryDirectory(prefix="material-cache-owner-") as temporary:
            output = Path(temporary) / "MaterialCacheOwnerFixture.exe"
            compile_result = subprocess.run(
                [str(MONO), str(CSC), f"-out:{output}", str(owner), str(fixture)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            run_result = subprocess.run([str(MONO), str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(run_result.returncode, 0, run_result.stdout + run_result.stderr)
            self.assertIn("material cache owner synthetic contract passed", run_result.stdout)


if __name__ == "__main__":
    unittest.main()
