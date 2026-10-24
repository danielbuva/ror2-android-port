"""Independent source-boundary, define and process contracts for the package owner."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/package-assemblies/produce.py"
SPEC = importlib.util.spec_from_file_location("package_assemblies", PATH)
PRODUCER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRODUCER)
GUID = "1234567890abcdef1234567890abcdef"


class PackageAssembliesTests(unittest.TestCase):
    def test_partial_source_order_and_same_assembly_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            asmdef = root / "Owner.asmdef"
            asmdef.write_text(json.dumps({"name": "Owner"}))
            Path(str(asmdef) + ".meta").write_text("guid: " + GUID + "\n")
            for relative in ("Part.Float.cs", "Part.cs", "Editor/Shared.cs", "Foreign/Other.cs", "unused~/Ignored.cs"):
                path = root / relative
                path.parent.mkdir(exist_ok=True)
                path.write_text("// independently authored source boundary fixture\n")
            (root / "Editor/Owner.asmref").write_text(json.dumps({"reference": "GUID:" + GUID}))
            (root / "Foreign/Other.asmdef").write_text(json.dumps({"name": "Other"}))
            actual = [p.relative_to(root).as_posix() for p in PRODUCER.sources(asmdef)]
            self.assertEqual(actual, ["Editor/Shared.cs", "Part.cs", "Part.Float.cs"])
            (root / "Editor/Owner.asmref").write_text(json.dumps({"reference": "Other"}))
            self.assertEqual([p.name for p in PRODUCER.sources(asmdef)], ["Part.cs", "Part.Float.cs"])

    def test_source_redirection_and_output_overlap_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            asmdef = root / "Owner.asmdef"
            asmdef.write_text(json.dumps({"name": "Owner"}))
            Path(str(asmdef) + ".meta").write_text("guid: " + GUID + "\n")
            (root / "original.txt").write_text("independent input")
            (root / "Alias.cs").symlink_to(root / "original.txt")
            with self.assertRaisesRegex(ValueError, "redirected"):
                PRODUCER.sources(asmdef)
            with self.assertRaisesRegex(ValueError, "canonical"):
                PRODUCER.canonical(str(root / "child/.."))
            with self.assertRaisesRegex(ValueError, "overlap"):
                PRODUCER.run({"sdk_install": str(root), "packages": str(root), "output": str(root / "new-output")})
            self.assertFalse((root / "new-output").exists())

    def test_version_defines_do_not_enable_absent_packages(self):
        spec = {
            "versionDefines": [{"name": "present", "expression": "1.0.0", "define": "PRESENT"}, {"name": "absent", "expression": "1.0.0", "define": "ABSENT"}]
        }
        symbols = PRODUCER.symbols("2021.3.45f2", spec, {"present": "1.2.0"})
        self.assertIn("PRESENT", symbols)
        self.assertNotIn("ABSENT", symbols)
        self.assertIn("ENABLE_IL2CPP", symbols)
        self.assertNotIn("UNITY_EDITOR", symbols)
        spec["versionDefines"][0]["expression"] = "[1.0,2.0)"
        with self.assertRaisesRegex(ValueError, "unqualified"):
            PRODUCER.symbols("2021.3.45f2", spec, {"present": "1.2.0"})

    def test_failed_process_keeps_log_and_terminal_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "tmp").mkdir()
            with self.assertRaisesRegex(RuntimeError, "failed"):
                PRODUCER.invoke([sys.executable, "-c", "print('independent failure witness');raise SystemExit(7)"], "failure", root)
            self.assertIn("independent failure witness", (root / "failure.log").read_text())
            self.assertEqual(json.loads((root / "failure.process.json").read_text())["exit_code"], 7)


if __name__ == "__main__":
    unittest.main()
