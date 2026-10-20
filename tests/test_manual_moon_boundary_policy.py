#!/usr/bin/env python3
"""Compile and execute the exact ManualMoonBoundary class from the authored owner."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SOURCE = ROOT / "tools/unity/runtime/stage/IntegratedStageBoundary.cs"
HARNESS = ROOT / "tests/fixtures/ManualMoonBoundaryPolicyHost.cs"
TYPE_MARKER = "public static class ManualMoonBoundary"


def extract_braced_type(source: str, marker: str) -> str:
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("unbalanced production type: " + marker)


class ManualMoonBoundaryPolicyTests(unittest.TestCase):
    def test_exact_production_policy_compiles_and_executes_host_contracts(self):
        editor = Path(
            os.environ.get(
                "UNITY_EDITOR_PATH",
                "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
            )
        )
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn toolchain is unavailable")

        production = extract_braced_type(CANDIDATE_SOURCE.read_text(), TYPE_MARKER)
        with tempfile.TemporaryDirectory(prefix="manual-moon-boundary-") as temporary:
            directory = Path(temporary)
            source = directory / "ExtractedManualMoonBoundary.cs"
            output = directory / "manual-moon-boundary.exe"
            source.write_text("using System;\n" + production + "\n")
            compiled = subprocess.run(
                [str(mono), str(compiler), "-nologo", "-langversion:latest", "-target:exe", "-out:" + str(output), str(source), str(HARNESS)],
                cwd=directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout)
            executed = subprocess.run(
                [str(mono), str(output)],
                cwd=directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(executed.returncode, 0, executed.stdout)
            self.assertIn("PASS exact production ManualMoonBoundary policy cases", executed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
