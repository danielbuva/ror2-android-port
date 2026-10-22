from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipe"


class OriginalMusicCameraCohortTests(unittest.TestCase):
    def test_camera_extension_preserves_music_sources_and_identity_rows(self):
        runtime = json.loads((RECIPE / "runtime-sources.json").read_text())
        camera = json.loads((RECIPE / "runtime-sources.native-view-camera.json").read_text())
        owner = json.loads((RECIPE / "original-audio-owner-sources.json").read_text())
        layout = json.loads((RECIPE / "project-layout.json").read_text())

        music = {
            "runtime/session/OriginalMusicControllerContract.cs",
            "runtime/session/PortSessionOriginalMusicControllerOwner.cs",
        }
        helper = "runtime/input/AndroidNativeSourceCameraPrerequisites.cs"
        self.assertTrue(music.issubset(runtime))
        self.assertTrue(music.issubset(camera))
        self.assertTrue(music.issubset(owner["runtime_sources"]))
        self.assertIn(helper, runtime)
        self.assertIn(helper, camera)
        self.assertIn(helper, owner["runtime_sources"])
        self.assertEqual(runtime, sorted(set(runtime)))
        self.assertEqual(camera, runtime)
        self.assertEqual(owner["runtime_sources"], runtime)
        for source in runtime:
            self.assertEqual(owner["project_layout_source_guids"][source], layout["runtime_source_guids"][source])
        self.assertIn(helper, layout["runtime_source_guids"])
        for source in music:
            self.assertIn(source, layout["runtime_source_guids"])

    def test_owner_recipe_retains_music_selection_and_default_off_claims(self):
        owner = json.loads((RECIPE / "original-audio-owner-sources.json").read_text())
        self.assertEqual(owner["schema"], "original-audio-owner-ancestor-r2")
        self.assertIn("MusicController", owner["integration"])
        self.assertTrue(owner["parent_manifest_sha256"].isalnum())


if __name__ == "__main__":
    unittest.main()
