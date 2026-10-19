#!/usr/bin/env python3
"""Compile and execute the exact inline policy and lease extracted from the candidate source."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/world/WholeInteractableBoundary.cs"
HARNESS = ROOT / "tests/fixtures/NativeRetiredBindingPolicyHost.cs"
START = "// BEGIN native retired managed-field restore policy (host-test extraction seam)."
END = "// END native retired managed-field restore policy."


def extract_braced_type(source, marker):
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("unbalanced production type: " + marker)


class NativeRetiredBindingPolicyTests(unittest.TestCase):
    def test_production_policy_and_lease_execute_as_host_contracts(self):
        root = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        runtime = root / "MonoBleedingEdge/bin/mono"
        compiler = root / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not runtime.is_file() or not compiler.is_file():
            self.skipTest("pinned editor Mono/Roslyn compiler is unavailable")
        source = SOURCE.read_text()
        begin = source.index(START)
        end = source.index(END, begin) + len(END)
        policy = source[begin:end].replace(START, "").replace(END, "")
        lease = extract_braced_type(source, "internal sealed class NativeBorrowedFieldLease<T>")
        with tempfile.TemporaryDirectory(prefix="native-retired-binding-policy-") as temporary:
            temp = Path(temporary)
            production = temp / "ExtractedProductionContracts.cs"
            executable = temp / "native-retired-policy.exe"
            production.write_text("using System;\n" + lease + "\n" + policy + "\n")
            compile_result = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-out:" + str(executable), str(production), str(HARNESS)],
                cwd=temp,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if compile_result.returncode:
                self.fail(compile_result.stdout)
            run_result = subprocess.run([str(runtime), str(executable)], cwd=temp, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(run_result.returncode, 0, run_result.stdout)
            self.assertIn("PASS retired-wrapper policy and captured-lease contracts", run_result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
