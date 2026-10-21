from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def find_repo_root() -> Path:
    marker = Path("tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs")
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    raise RuntimeError("repository root not found from private test path")


REPO = find_repo_root()
OWNER = REPO / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs"
EDITOR = Path(
    os.environ.get(
        "UNITY_EDITOR_PATH",
        "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
    )
)
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


def extract_exact_resolver(source: str) -> tuple[str, str]:
    fields_start = source.index("    static bool cameraGateFieldsResolved;")
    fields_end_marker = "    static string cameraGateFieldsFailure;"
    fields_end = source.index(fields_end_marker, fields_start) + len(fields_end_marker)
    fields = source[fields_start:fields_end]

    signature = "    static bool ResolveCameraGateObservationFields("
    method_start = source.index(signature)
    opening = source.index("{", method_start)
    depth = 0
    method_end = None
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                method_end = offset + 1
                break
    if method_end is None:
        raise AssertionError("unterminated production resolver body")
    return fields, source[method_start:method_end]


class CameraGateSourceContractTests(unittest.TestCase):
    def test_observation_fields_do_not_extend_mandatory_marker_admission(self):
        source = OWNER.read_text(encoding="utf-8")
        admission = source.split("static Type ResolveOptionalMarkerType()", 1)[1].split("// Resolve optional snapshot-only fields", 1)[0]
        for optional_name in (
            "originalEarlyUpdate",
            "originalContextReady",
            "originalEarlyUpdatePumpCount",
        ):
            self.assertNotIn(f'GetField("{optional_name}"', admission)
            self.assertNotIn(f"cameraGate{optional_name}", admission)
        observation = source.split("static bool ResolveCameraGateObservationFields(", 1)[1].split("// Read-only bounded fields", 1)[0]
        self.assertIn('GetField("originalEarlyUpdate", fields)', observation)
        self.assertIn('GetField("originalContextReady", fields)', observation)
        self.assertIn('GetField("originalEarlyUpdatePumpCount", fields)', observation)
        self.assertIn("earlyUpdate.FieldType != typeof(Action)", observation)
        self.assertIn("contextReady.FieldType != typeof(bool)", observation)
        self.assertIn("pumpCount.FieldType != typeof(int)", observation)
        capture = source.split("public void CaptureUpdateContextObservation(", 1)[1].split("static string ShortText", 1)[0]
        self.assertNotIn(".SetValue(", capture)
        self.assertNotIn(".Invoke(", capture)
        self.assertNotIn("originalEarlyUpdate(", capture)

    def test_exact_production_resolver_with_synthetic_marker_shapes(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn host compiler unavailable")

        source = OWNER.read_text(encoding="utf-8")
        fields, resolver = extract_exact_resolver(source)
        harness = f"""using System;
using System.Reflection;

public static class ProductionResolver
{{
{fields}
{resolver}
}}

sealed class ValidMarker {{ private Action originalEarlyUpdate; private bool originalContextReady; private int originalEarlyUpdatePumpCount; }}
sealed class MissingAction {{ private bool originalContextReady; private int originalEarlyUpdatePumpCount; }}
sealed class MissingBool {{ private Action originalEarlyUpdate; private int originalEarlyUpdatePumpCount; }}
sealed class MissingInt {{ private Action originalEarlyUpdate; private bool originalContextReady; }}
sealed class WrongAction {{ private string originalEarlyUpdate; private bool originalContextReady; private int originalEarlyUpdatePumpCount; }}
sealed class WrongBool {{ private Action originalEarlyUpdate; private int originalContextReady; private int originalEarlyUpdatePumpCount; }}
sealed class WrongInt {{ private Action originalEarlyUpdate; private bool originalContextReady; private long originalEarlyUpdatePumpCount; }}

static class ResolverAssertions
{{
    static int checks;
    static MethodInfo Resolver = typeof(ProductionResolver).GetMethod(
        "ResolveCameraGateObservationFields", BindingFlags.NonPublic | BindingFlags.Static);

    static void Check(bool condition, string message)
    {{
        checks++;
        if (!condition) throw new Exception(message);
    }}

    static bool Resolve(Type markerType, out string failure)
    {{
        object[] args = {{ markerType, null }};
        bool result = (bool)Resolver.Invoke(null, args);
        failure = (string)args[1];
        return result;
    }}

    static void Reject(Type type, string expected)
    {{
        string failure;
        string label = type == null ? "<null>" : type.Name;
        Check(!Resolve(type, out failure), label + " unexpectedly resolved");
        Check(failure == expected, label + " failure mismatch: " + failure);
    }}

    public static int Main()
    {{
        string failure;
        Check(Resolver != null, "exact production resolver method was not extracted");
        Check(Resolve(typeof(ValidMarker), out failure) && failure == null,
            "valid Action/bool/int marker did not resolve");
        Reject(typeof(MissingAction), "optional marker originalEarlyUpdate field missing or not Action");
        string cachedFailure;
        Check(!Resolve(typeof(MissingAction), out cachedFailure) &&
            cachedFailure == "optional marker originalEarlyUpdate field missing or not Action",
            "same-type cached failure changed");
        Reject(typeof(MissingBool), "optional marker originalContextReady field missing or not Boolean");
        Reject(typeof(MissingInt), "optional marker originalEarlyUpdatePumpCount field missing or not Int32");
        Reject(typeof(WrongAction), "optional marker originalEarlyUpdate field missing or not Action");
        Reject(typeof(WrongBool), "optional marker originalContextReady field missing or not Boolean");
        Reject(typeof(WrongInt), "optional marker originalEarlyUpdatePumpCount field missing or not Int32");
        Reject(null, "exact marker type unavailable for optional camera gate observation");
        Check(!Resolve(null, out cachedFailure) &&
            cachedFailure == "exact marker type unavailable for optional camera gate observation",
            "null-type cached failure changed");
        Check(Resolve(typeof(ValidMarker), out failure) && failure == null,
            "resolver failed to recover when a valid marker type replaced a failed type");
        Console.WriteLine("PASS: " + checks + " extracted production resolver assertions");
        return 0;
    }}
}}
"""
        with tempfile.TemporaryDirectory(prefix="camera-gate-resolver-") as temp_name:
            temp = Path(temp_name)
            source_path = temp / "ExtractedProductionResolver.cs"
            executable = temp / "ResolverAssertions.exe"
            source_path.write_text(harness, encoding="utf-8")
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:latest",
                    "-target:exe",
                    f"-out:{executable}",
                    str(source_path),
                ],
                cwd=temp,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], cwd=temp, capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: 19 extracted production resolver assertions", ran.stdout)


if __name__ == "__main__":
    unittest.main()
