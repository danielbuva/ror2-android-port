"""Execute the bounded Siren recorder copied from its authored production source."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNITY = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
MONO = UNITY / "bin/mono"
CSC = UNITY / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
SOURCE = Path(os.environ.get("SIREN_NAVIGATION_SOURCE", ROOT / "tools/unity/runtime/input/SirenNavigationObservation.cs"))
CONTRACT = ROOT / "tests/fixtures/siren_navigation_observation_host.cs"


def declaration(source, name):
    start = source.index(name)
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise AssertionError("unclosed production declaration: " + name)


class SirenNavigationObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("Pinned Unity host compiler unavailable")
        if not SOURCE.is_file():
            raise AssertionError("Siren navigation production source is missing")
        if not CONTRACT.is_file():
            raise AssertionError("Siren navigation host contract fixture is missing")

    def test_production_recorder_executes_bounded_host_contract(self):
        source = SOURCE.read_text()
        declarations = [
            declaration(source, "public struct SirenNavigationObservationSample"),
            declaration(source, "public sealed class SirenNavigationObservationReport"),
            declaration(source, "public static class SirenNavigationObservationPolicy"),
            declaration(source, "public interface ISirenNavigationObservationReader"),
            declaration(source, "public sealed class SirenNavigationObservationRecorder"),
        ]
        unity_stubs = "namespace UnityEngine { public struct Vector2 { public float x,y; public Vector2(float x,float y){this.x=x;this.y=y;} public static Vector2 zero => new Vector2(0,0); } public struct Vector3 { public float x,y,z; } }\n"
        host = "using System;\nusing UnityEngine;\nnamespace RoR2 {}\n" + unity_stubs + "\n".join(declarations) + CONTRACT.read_text()
        with tempfile.TemporaryDirectory(prefix="siren-navigation-host-") as temporary:
            directory = Path(temporary)
            cs = directory / "SirenNavigationHost.cs"
            exe = directory / "SirenNavigationHost.exe"
            cs.write_text(host)
            subprocess.run([str(MONO), str(CSC), "-nologo", "-langversion:9", "-out:" + str(exe), str(cs)], check=True, cwd=directory)
            result = subprocess.run([str(MONO), str(exe)], check=True, cwd=directory, text=True, capture_output=True)
        self.assertIn("siren-navigation-recorder-state-contract-passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
