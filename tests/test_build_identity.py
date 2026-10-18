import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build
from common import write


class BuildIdentityTests(unittest.TestCase):
    def test_whole_catalog_build_rejects_unstaged_authored_runtime_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "work"
            project = work / "lab-project"
            source = root / "tools/unity/runtime/progression/AndroidProfileBoundary.cs"
            staged = project / "Assets/LabLoadingScene/AndroidProfileBoundary.cs"
            source.parent.mkdir(parents=True)
            staged.parent.mkdir(parents=True)
            source.write_text("new offline award boundary")
            staged.write_text("previous offline award boundary")
            source_name = source.relative_to(root / "tools/unity").as_posix()
            write(root / "recipe/runtime-sources.json", [source_name])
            dependencies = {"com.unity.ugui": "1.0.0"}
            write(root / "recipe/project-layout.json", {"runtime_source_guids": {source_name: "a" * 32}, "dependencies": dependencies})
            staged.with_suffix(".cs.meta").write_text("guid: " + "a" * 32 + "\n")
            write(project / "Packages/manifest.json", {"dependencies": dependencies})
            write(root / "recipe/runtime-config.json", {"launchPlayableSlice": True})
            write(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", {"launchPlayableSlice": True})
            write(root / "recipe/content.json", {"scene": "Assets/Fixture.unity"})
            write(work / "scene-probe-build.json", {"scene": "Assets/Fixture.unity"})
            write(work / "whole-catalog-build.json", {"scope": "test"})
            with patch.object(build, "ROOT", root), patch.object(build, "WORK", work), patch.object(build, "RECIPE", root / "recipe"):
                with self.assertRaisesRegex(RuntimeError, "whole-catalog-code-build"):
                    build.validate_staged_runtime_sources(project)
                staged.write_bytes(source.read_bytes())
                build.validate_staged_runtime_sources(project)

    def test_scene_recipe_and_catalog_manifest_each_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            for folder in ("Assets", "Packages", "ProjectSettings"):
                (project / folder).mkdir(parents=True)
            scene = project / "Assets" / "stage.unity"
            scene.write_text("original scene A")
            tool = root / "scripts/lab/build.py"
            tool.parent.mkdir(parents=True)
            tool.write_text("tool version")
            work = root / "work"
            recipe = work / "scene-probe-build.json"
            manifest = work / "manifest.json"
            write(recipe, {"prefabAssets": ["Assets/graph-a.asset"]})
            write(manifest, {"roots": ["scene A"]})
            write(work / "whole-catalog-build.json", {"manifest": str(manifest)})
            with patch.object(build, "ROOT", root), patch.object(build, "WORK", work), patch.object(build, "toolchain", return_value={"editor": "pinned"}):
                original = build.build_cache_key(project, "vulkan")
                scene.write_text("original scene B")
                changed_scene = build.build_cache_key(project, "vulkan")
                write(recipe, {"prefabAssets": ["Assets/graph-a.asset", "Assets/graph-b.asset"]})
                changed_recipe = build.build_cache_key(project, "vulkan")
                write(manifest, {"roots": ["scene B"]})
                changed_manifest = build.build_cache_key(project, "vulkan")
            self.assertEqual(len({original, changed_scene, changed_recipe, changed_manifest}), 4)


if __name__ == "__main__":
    unittest.main()
