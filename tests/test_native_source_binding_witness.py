"""Execute the production rollback witness formatter with authored host cases."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/unity/runtime/world/WholeInteractableBoundary.cs"
FIXTURE = ROOT / "tests/fixtures/NativeSourceBindingWitnessHost.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


class NativeSourceBindingWitnessTests(unittest.TestCase):
    def test_production_formatter_reports_independent_rollback_predicates(self):
        runtime = EDITOR / "bin/mono"
        compiler = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not runtime.is_file() or not compiler.is_file():
            self.skipTest("matching Unity Mono compiler/runtime is unavailable")
        owner = OWNER.read_text()
        formatter = "using System;\n" + owner[owner.index("internal static class NativeSourceBindingWitnessFormatter") :]
        with tempfile.TemporaryDirectory(prefix="native-source-binding-witness-") as temporary:
            scratch = Path(temporary)
            helper = scratch / "ProductionWitness.cs"
            output = scratch / "WitnessHost.exe"
            helper.write_text(formatter)
            compiled = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-langversion:9", "-out:" + str(output), str(helper), str(FIXTURE)],
                cwd=scratch,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(runtime), str(output)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("PASS native source binding witness formatting", executed.stdout)


if __name__ == "__main__":
    unittest.main()
