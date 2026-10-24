"""Execute source SceneInfo audio admission, rollback and retirement methods."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(source, signature):
    start = source.index(signature)
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class SourceStageAudioLifecycleTests(unittest.TestCase):
    def test_native_readiness_keeps_original_activation_and_rollback_ownership(self):
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        source = (ROOT / "tools/unity/runtime/stage/StageGeometryBoundary.cs").read_text()
        methods = "\n".join(
            method(source, signature)
            for signature in (
                "static bool IsOriginalSceneAudio(",
                "public SceneInfo ActivateSourceSceneInfo(",
                "public void DeactivateSourceSceneInfo(",
            )
        )
        fixture = (ROOT / "tests/fixtures/source_stage_audio_lifecycle_host.cs").read_text().replace("__METHODS__", methods)
        with tempfile.TemporaryDirectory(prefix="source-stage-audio-lifecycle-") as temp:
            root = Path(temp)
            source_path, executable = root / "Harness.cs", root / "Harness.exe"
            source_path.write_text(fixture)
            built = subprocess.run([str(mono), str(compiler), "-nologo", "-out:" + str(executable), str(source_path)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(mono), str(executable)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
