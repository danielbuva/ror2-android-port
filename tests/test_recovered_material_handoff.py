"""Execute the owned recovered-material handoff with authored Unity doubles."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_enemy_actor_observation import EDITOR, ROOT, source_method


class RecoveredMaterialHandoffTests(unittest.TestCase):
    def test_slots_trails_late_replacement_toggle_and_ownership(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("matching Unity Mono compiler is unavailable")
        presentation = (ROOT / "tools/unity/runtime/shaders/AndroidMaterialPresentation.cs").read_text()
        native = (ROOT / "tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs").read_text()
        source = (ROOT / "tests/fixtures/recovered_material_handoff.cs").read_text()
        source += "\npublic static partial class AndroidMaterialPresentation {\n"
        source += "\n".join(
            source_method(presentation, declaration)
            for declaration in (
                "static bool ApplyNative(",
                "public static int ApplyRecovered(",
                "public static void SetEnabled(",
            )
        )
        source += "\n}\npublic static partial class AndroidNativeDeferredPresentation {\n"
        source += source_method(native, "public static bool IsSourceFamily(") + "\n}\n"
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            fixture = scratch / "RecoveredMaterials.cs"
            binary = scratch / "RecoveredMaterials.exe"
            fixture.write_text(source)
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(binary), str(fixture)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(binary)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("recovered material handoff passed", executed.stdout)

    def test_observed_actor_bindings_select_recovered_presentation(self):
        config = json.loads((ROOT / "recipe/runtime-config.json").read_text())
        actors = {actor["name"]: actor for actor in config["objectiveActors"]}
        for name in ("Golem", "Lemurian", "Wisp"):
            with self.subTest(actor=name):
                self.assertTrue(actors[name]["recoveredMaterials"])
                self.assertTrue(actors[name]["bindings"])


if __name__ == "__main__":
    unittest.main()
