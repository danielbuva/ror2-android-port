"""Source-reference staging contract; no Editor or game input is needed."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sprite_fixture", ROOT / "scripts/lab/sprite_native_fixture.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


class SpriteNativeFixtureTests(unittest.TestCase):
    def prepare(self, root):
        for name in (
            F.SOURCE,
            F.BOOTSTRAP,
            "tools/phone-build/accepted-output/SpriteNativeFixtureRunner.cs",
            "tools/phone-build/accepted-output/SpriteNativeFixtureBuild.cs",
        ):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        manifest = root / "smoke/Packages/manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes((ROOT / "smoke/Packages/manifest.json").read_bytes())
        image = root / "original.png"
        image.write_bytes(b"authored staging-only image fixture")
        item = {
            "id": "authored",
            "png": str(image),
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "rect": [0, 0, 4, 4],
            "pivot": [0.5, 0.5],
            "border": [0, 0, 0, 0],
            "pixels_per_unit": 100,
            "extrude": 1,
            "mesh_type": 1,
        }
        request = root / "request.json"
        request.write_text(json.dumps({"items": [item]}))
        return request, image

    def test_staging_references_pinned_images_without_copying_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, image = self.prepare(root)
            before = image.read_bytes()
            result = F.stage(root, request, root / "work/fixture")
            project = Path(result["project"])
            self.assertEqual(list(project.rglob("*.png")), [])
            self.assertEqual(image.read_bytes(), before)
            staged = json.loads((project / "sprite-source-request.json").read_text())
            self.assertEqual(staged["items"][0]["png"], str(image))
            self.assertIn("2021.3.45f2", (project / "ProjectSettings/ProjectVersion.txt").read_text())
            self.assertEqual((project / "Assets/SpriteNativeFixture.cs").read_bytes(), (root / F.SOURCE).read_bytes())

    def test_changed_image_refuses_before_creating_a_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, image = self.prepare(root)
            image.write_bytes(b"changed source")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                F.stage(root, request, root / "work/refused")
            self.assertFalse((root / "work/refused").exists())

    def test_android_fixture_has_a_separate_package_and_no_embedded_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, _ = self.prepare(root)
            result = F.stage(root, request, root / "work/android", android=True)
            project = Path(result["project"])
            self.assertEqual(result["package"], "dev.ror2lab.spritefixture")
            self.assertTrue((project / "Assets/SpriteNativeFixtureRunner.cs").is_file())
            self.assertTrue((project / "Assets/Editor/SpriteNativeFixtureBuild.cs").is_file())
            self.assertEqual(list(project.rglob("*.png")), [])


if __name__ == "__main__":
    unittest.main()
