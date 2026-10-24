"""Compile the actual editor build owner against the exact optional SDK API."""

from pathlib import Path
import os
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
                'public static class Host { public static int Main(){ string owned="BuildFailedException: ROR2LAB_ITERATION_EXPORT_COMPLETE authored";'
                'if(!LabBuild.IsOwnedIterationCancellation(new[]{"Building Player failed",owned,owned},"authored"))return 1;'
                'if(LabBuild.IsOwnedIterationCancellation(new[]{"Building Player failed"},"authored"))return 2;'
                'if(LabBuild.IsOwnedIterationCancellation(new[]{owned,"unrelated shader failure"},"authored"))return 3;'
                'if(LabBuild.IsOwnedIterationCancellation(new[]{owned,"Building Player failed","Building Player failed"},"authored"))return 4;'
                'if(LabBuild.IsOwnedIterationCancellation(new[]{owned},"another-request"))return 5;return 0;} }\n'
            )
            result = subprocess.run(
                [
                    str(mono),
                    str(csc),
                    "-nologo",
                    "-target:exe",
                    "-out:" + str(scratch / "LabBuild.exe"),
                    *["-r:" + str(path) for path in references],
                    str(ROOT / "android/Assets/Editor/LabBuild.cs"),
                    str(stub),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(
                [str(mono), str(scratch / "LabBuild.exe")],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "MONO_PATH": str(SDK / "Managed")},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
