#!/usr/bin/env python3
"""Compile the exact failure-witness formatter and check the fail-closed call site."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/commerce/WorldCommerceBoundary.cs"
HARNESS = ROOT / "tests/fixtures/NativeShrineEffectAttributionWitnessHost.cs"


class NativeShrineEffectAttributionWitnessTests(unittest.TestCase):
    def test_production_formatter_and_fail_closed_cleanup_seam(self):
        root = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        runtime = root / "MonoBleedingEdge/bin/mono"
        compiler = root / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not runtime.is_file() or not compiler.is_file():
            self.skipTest("pinned editor Mono/Roslyn compiler is unavailable")

        source = SOURCE.read_text()
        marker = "internal static class NativeShrineEffectAttributionWitness"
        begin = source.index(marker)
        brace = source.index("{", begin)
        depth = 0
        for end in range(brace, len(source)):
            if source[end] == "{":
                depth += 1
            elif source[end] == "}":
                depth -= 1
                if depth == 0:
                    formatter = source[begin : end + 1]
                    break
        else:
            self.fail("production attribution witness type is unbalanced")

        cleanup = source[source.index("public void CleanupWorldCommerce(bool final = false)") :]
        self.assertIn("extra == commerceDirectShrineEffectLoads", cleanup)
        self.assertLess(cleanup.index("coordinator.Check("), cleanup.index("for (int i = 0; i < extra; i++)"))
        self.assertIn("NativeShrineEffectAttributionWitness.Format(", cleanup)

        with tempfile.TemporaryDirectory(prefix="native-shrine-effect-attribution-") as temporary:
            temp = Path(temporary)
            production = temp / "ProductionWitness.cs"
            executable = temp / "ShrineEffectWitness.exe"
            production.write_text("using System;\n" + formatter + "\n")
            compiled = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-langversion:9", "-out:" + str(executable), str(production), str(HARNESS)],
                cwd=temp,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout)
            executed = subprocess.run([str(runtime), str(executable)], cwd=temp, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(executed.returncode, 0, executed.stdout)
            self.assertIn("PASS shrine effect mismatch values and callback attribution formatting", executed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
