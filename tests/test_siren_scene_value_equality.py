"""Execute the production scene guard with value-type scene doubles."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/stage/SirenSourceEntrySession.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def declaration(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start : offset + 1]
    raise AssertionError("Unclosed production declaration")


class SceneValueEqualityTests(unittest.TestCase):
    def test_production_scene_guard_compares_value_identity(self):
        source = SOURCE.read_text()
        self.assertIn("SirenSourceEntryContract.IsSameScene(controllerObject.scene, scene)", source)
        helper = declaration(source, "public static bool IsSameScene<TScene>(")
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity Mono/Roslyn compiler unavailable")
        fixture = (
            """using System;
public struct SceneDouble
{
    public int handle;
    public SceneDouble(int value) { handle = value; }
    public override bool Equals(object value) => value is SceneDouble other && handle == other.handle;
    public override int GetHashCode() => handle;
}
public static class SirenSourceEntryContract
{
"""
            + helper
            + """
}
public static class SceneGuardFixture
{
    static void Need(bool value, string message) { if (!value) throw new Exception(message); }
    public static void Main()
    {
        Need(SirenSourceEntryContract.IsSameScene(new SceneDouble(7), new SceneDouble(7)), "same scene must match");
        Need(!SirenSourceEntryContract.IsSameScene(new SceneDouble(7), new SceneDouble(8)), "different scene must refuse");
        Console.WriteLine("production-scene-value-guard-passed");
    }
}
"""
        )
        with tempfile.TemporaryDirectory(prefix="siren-scene-value-guard-") as directory:
            temp = Path(directory)
            src = temp / "SceneGuard.cs"
            exe = temp / "SceneGuard.exe"
            src.write_text(fixture)
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(exe), str(src)], cwd=temp, capture_output=True, text=True
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(exe)], cwd=temp, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("production-scene-value-guard-passed", executed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
