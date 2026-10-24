"""Exercise the production stage-layer join for both camera ownership paths."""

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeViewWorldCullingTests(unittest.TestCase):
    def test_stage_geometry_is_visible_to_both_camera_paths(self):
        source = (ROOT / "tools/unity/runtime/input/NovaInputBoundary.cs").read_text()
        join = re.findall(r"if \(cfg\.stageGeometry[^\n]*\)\s+display\.camera\.cullingMask \|= LayerIndex\.world\.mask;", source)
        self.assertEqual(len(join), 1)
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        mono = editor / "MonoBleedingEdge/bin/mono"
        csc = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        fixture = r"""
using System;
public class Config { public bool stageGeometry; }
public class Camera { public int cullingMask; }
public class Display { public bool UsesOriginalLocalCamera; public Camera camera=new Camera(); }
public class LayerIndex { public int mask; public static LayerIndex world=new LayerIndex {mask=1<<9}; }
public static class Harness {
 static void Join(Config cfg, Display display) { __JOIN__ }
 public static void Main() {
  foreach(bool stage in new[]{false,true})foreach(bool source in new[]{false,true}) {
   int before=(1<<30)|1;
   var display=new Display {UsesOriginalLocalCamera=source};display.camera.cullingMask=before;
   Join(new Config {stageGeometry=stage},display);
   if(display.camera.cullingMask!=(stage?before|LayerIndex.world.mask:before))
    throw new Exception("stage geometry layer missing or unrelated camera layers changed");
  }
 }
}
""".replace("__JOIN__", join[0])
        with tempfile.TemporaryDirectory(prefix="source-camera-world-layer-") as temp:
            root = Path(temp)
            program, executable = root / "Harness.cs", root / "Harness.exe"
            program.write_text(fixture)
            result = subprocess.run([str(mono), str(csc), "-nologo", "-out:" + str(executable), str(program)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(mono), str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
