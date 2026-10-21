import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
R3_CAMERA_GAME = "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384"


class NativeViewCameraR3ProfileTests(unittest.TestCase):
    def test_current_game_api_profiles_share_r3_camera_output(self):
        pins = json.loads((ROOT / "recipe/native-view-camera-transform.json").read_text())
        for profile in ("post-audio-point-sound-6f96-api-d540", "post-audio-r10-1ced-game-6f96"):
            self.assertEqual(pins["profiles"][profile]["output_sha256"], R3_CAMERA_GAME)
        source_roles = pins["source_paths"]
        for role in ("marker", "camera_owner", "camera_prerequisites", "transformer", "verifier", "whole_catalog", "build_hook"):
            path = ROOT / source_roles[role]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pins["source_sha256"][role], role)

    def test_recipe_binds_exact_camera_shader_rows(self):
        pins = json.loads((ROOT / "recipe/native-view-camera-transform.json").read_text())
        rows = pins["camera_shader_roots"]["entries"]
        self.assertEqual(
            [(row["catalog_id"], row["address_key"]) for row in rows],
            [
                (16022, "41e90cbc5ad198a438128b019f8d8553"),
                (16025, "5e246b703e2090148a761d52af19744b"),
                (2537, "e4abd95960ed75f4a9f59cac7c40bd9d"),
            ],
        )
        self.assertTrue(all(row["bundle"] == "must_be_present_in_built_manifest" for row in rows))

    def test_build_hook_uses_same_camera_profile_hashes(self):
        pins = json.loads((ROOT / "recipe/native-view-camera-transform.json").read_text())
        hook_text = (ROOT / "scripts/lab/native_view_camera_build_hook.py").read_text()
        self.assertIn('"camera_after_point_sound": "' + R3_CAMERA_GAME + '"', hook_text)
        self.assertIn('"camera_after_r10_1ced": "' + R3_CAMERA_GAME + '"', hook_text)
        self.assertEqual(pins["profiles"]["post-audio-point-sound-6f96-api-d540"]["output_sha256"], R3_CAMERA_GAME)


if __name__ == "__main__":
    unittest.main()
