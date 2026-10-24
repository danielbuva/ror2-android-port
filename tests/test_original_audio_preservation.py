"""Execute actual source-audio root and projectile policies without native audio."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OriginalAudioPreservationTests(unittest.TestCase):
    def test_authored_root_enable_state_and_projectile_source_sound(self):
        source = (ROOT / "tools/unity/runtime/world/AutomaticSpawnBoundary.cs").read_text()
        start = source.index("            int preservedAudioRootCallbacks = 0;")
        end = source.index("            if (automaticModel)", start)
        fixture = (ROOT / "tests/fixtures/original_audio_preservation_host.cs").read_text()
        fixture = fixture.replace("__ROOT_LOOP__", source[start:end])
        projectile = (ROOT / "tools/unity/runtime/world/SilentProjectileBoundary.cs").read_text()
        fixture = projectile + "\n" + fixture.replace("using System;", "").replace("using System.Linq;", "").replace("using System.Reflection;", "")
        fixture = "using System;\nusing System.Linq;\nusing System.Reflection;\n" + fixture
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="original-audio-preservation-") as temp:
            root = Path(temp)
            source_path, executable = root / "Harness.cs", root / "Harness.exe"
            source_path.write_text(fixture)
            built = subprocess.run([str(mono), str(compiler), "-nologo", "-out:" + str(executable), str(source_path)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(mono), str(executable)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
