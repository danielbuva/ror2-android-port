"""Execute the owned source Sobel setup, rendered-camera sample and teardown."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class SourceSobelLifecycleTests(unittest.TestCase):
    def test_original_settings_clone_and_native_volume_cleanup(self):
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        source = (ROOT / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs").read_text()
        methods = "\n".join(
            method(source, signature)
            for signature in (
                "void PrepareSourceSobel(Scene sourceStageScene)",
                "void ObserveSourceSobel(Camera camera)",
                "void ReleaseSourceSobel()",
                "PostProcessVolume CloneSourceGraphicsVolume(PostProcessVolume source, out PostProcessProfile profile)",
                "void PrepareSourceGraphicsResources(PostProcessLayer layer)",
                "Shader SourceGraphicsShader(string resource)",
                "ComputeShader SourceGraphicsCompute(string resource, params string[] kernels)",
            )
        )
        fixture = (ROOT / "tests/fixtures/source_sobel_lifecycle_host.cs").read_text().replace("__METHODS__", methods)
        with tempfile.TemporaryDirectory(prefix="source-sobel-lifecycle-") as temp:
            src, exe = Path(temp) / "Harness.cs", Path(temp) / "Harness.exe"
            src.write_text(fixture)
            subprocess.run([str(mono), str(compiler), "/nologo", "/out:" + str(exe), str(src)], check=True, capture_output=True)
            result = subprocess.run([str(mono), str(exe)], check=True, capture_output=True, text=True)
        self.assertIn("source Sobel lifecycle PASS", result.stdout)

    def test_only_the_requested_visual_camera_prepares_sobel(self):
        source = (ROOT / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs").read_text()
        self.assertIn("if (!audioContextOnly)\n                owner.PrepareSourceSobel(sourceStageScene);", source)
        setup = method(source, "void PrepareSourceSobel(Scene sourceStageScene)")
        self.assertIn("sourceStageScene.GetRootGameObjects()", setup)
        self.assertNotIn("SceneManager.GetActiveScene", setup)
        caller = (ROOT / "tools/unity/runtime/input/NovaInputBoundary.cs").read_text()
        self.assertIn(
            "coordinator.r.nova.nativeSourceSkinLifecycle,\n                                                    coordinator.stageGeometryScene", caller
        )
        for signature in ("public void DisposeOwnedView()", "void OnDisable()"):
            self.assertIn("ReleaseSourceSobel();", method(source, signature))
        self.assertNotIn("RoR2Application.instance =", source)
