"""Compile the actual editor build owner against the exact optional SDK API."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDK = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")


class LabBuildApiTests(unittest.TestCase):
    def test_actual_builder_compiles_with_pinned_build_report_and_android_callback(self):
        mono = SDK / "MonoBleedingEdge/bin/mono"
        csc = SDK / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        references = [SDK / "Managed" / name for name in ("UnityEditor.dll", "UnityEngine.dll", "Newtonsoft.Json.dll")]
        if not all(path.is_file() for path in (mono, csc, *references)):
            self.skipTest("pinned optional editor SDK is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            stub = scratch / "UnrelatedRuntimeOwners.cs"
            stub.write_text(
                "public sealed class LabDiagnostics : UnityEngine.MonoBehaviour {}\n"
                "public static class Il2CppInvocationCapture { public static void CompleteAfterBuild(UnityEditor.Build.Reporting.BuildReport report){} }\n"
            )
            result = subprocess.run(
                [
                    str(mono),
                    str(csc),
                    "-nologo",
                    "-target:library",
                    "-out:" + str(scratch / "LabBuild.dll"),
                    *["-r:" + str(path) for path in references],
                    str(ROOT / "android/Assets/Editor/LabBuild.cs"),
                    str(stub),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
