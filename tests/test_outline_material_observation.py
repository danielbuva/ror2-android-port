from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


REPO = repo_root()
SOURCE_ROOT = Path(os.environ.get("OUTLINE_OBSERVER_SOURCE_ROOT", REPO))
UNITY = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = UNITY / "MonoBleedingEdge/bin/mono"
CSC = UNITY / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
OWNER = SOURCE_ROOT / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs"
LIFECYCLE = SOURCE_ROOT / "tools/unity/runtime/input/AndroidNativeSourceSkinLifecycle.cs"
POLICY = SOURCE_ROOT / "tools/unity/runtime/input/AndroidNativeSourceOutlinePassObservationPolicy.cs"
FIXTURE = Path(__file__).parent / "fixtures/OutlinePassOwnerCallbackFixture.cs"


def extract_block(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated production block: {signature}")


class OutlineMaterialObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity host Mono/Roslyn is unavailable")
        for path in (OWNER, LIFECYCLE, POLICY, FIXTURE):
            if not path.is_file():
                raise AssertionError(f"outline observer production source is missing: {path.name}")

    def test_composed_owner_callback_and_production_report_execute_once(self) -> None:
        owner = OWNER.read_text(encoding="utf-8")
        lifecycle = LIFECYCLE.read_text(encoding="utf-8")
        fixture = FIXTURE.read_text(encoding="utf-8")
        signatures = (
            "void TryAttachOutlinePassObserver()",
            "void CaptureOwnedOutlinePassObservation(Camera callbackCamera)",
            "void DetachOutlinePassObserver()",
            "void OnDisable()",
            "void OnDestroy()",
        )
        methods = [extract_block(owner, signature) for signature in signatures]
        observation = extract_block(lifecycle, "public sealed class OutlinePassObservation")
        self.assertEqual(fixture.count("// ACTUAL PRODUCTION REPORT DTO IS INSERTED HERE BY THE PUBLIC TEST WRAPPER."), 1)
        self.assertEqual(fixture.count("// ACTUAL PRODUCTION METHODS ARE INSERTED HERE BY THE PUBLIC TEST WRAPPER."), 1)
        generated_source = fixture.replace(
            "// ACTUAL PRODUCTION REPORT DTO IS INSERTED HERE BY THE PUBLIC TEST WRAPPER.",
            "internal static class AndroidNativeSourceSkinLifecycle {\n"
            + observation
            + "\ninternal sealed class Report { public OutlinePassObservation outlinePassObservation; public void Fail(string reason) {} }\n}",
        ).replace("// ACTUAL PRODUCTION METHODS ARE INSERTED HERE BY THE PUBLIC TEST WRAPPER.", "\n\n".join(methods))
        with tempfile.TemporaryDirectory(prefix="outline-material-observation-") as temp_name:
            temp = Path(temp_name)
            generated = temp / "OutlinePassOwnerCallbackFixture.generated.cs"
            generated.write_text(generated_source, encoding="utf-8")
            executable = temp / "outline-observation.exe"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:latest", "-target:exe", f"-out:{executable}", str(POLICY), str(generated)],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], cwd=temp, capture_output=True, text=True, check=False)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("R34 composed owner callback fixture passed: 19", ran.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
