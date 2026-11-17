"""Independent source-boundary, define and process contracts for the package owner."""

import importlib.util
import json
import shlex
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/package-assemblies/produce.py"
SPEC = importlib.util.spec_from_file_location("package_assemblies", PATH)
PRODUCER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRODUCER)
GUID = "1234567890abcdef1234567890abcdef"


class PackageAssembliesTests(unittest.TestCase):
    def test_prepare_archives_reuses_compiler_selection_and_keeps_original_meta(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source/com.unity.ugui@1.0.0"
            assembly = source / "Runtime"
            assembly.mkdir(parents=True)
            files = {
                "Runtime/UI.asmdef": '{"name":"UnityEngine.UI"}',
                "Runtime/UI.asmdef.meta": "guid: " + GUID,
                "Runtime/Selected.cs": "class Selected {}",
                "Runtime/Selected.cs.meta": "guid: " + GUID,
                "Runtime/Editor/Other.asmdef": '{"name":"Other"}',
                "Runtime/Editor/Ignored.cs": "class Ignored {}",
                "Samples~/Unused.cs": "class Unused {}",
            }
            for name, content in files.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            rows = (("com.unity.ugui", "Runtime/UI.asmdef"),)
            compiler_files = {source.name + "/" + name: PRODUCER.sha(source / name) for name in list(files)[:3]}
            settings = {
                "packages": {"com.unity.ugui": "1.0.0"},
                "groups": {"UnityEngine.UI": {"source_count": 1, "input_count": 3, "aggregate_sha256": PRODUCER.aggregate(compiler_files)}},
            }
            archives = root / "archives"
            archives.mkdir()
            archive = archives / "com.unity.ugui-1.0.0.tgz"
            with tarfile.open(archive, "w:gz") as output:
                output.add(source, arcname="com.unity.ugui")
            pins = {archive.name: PRODUCER.sha(archive)}
            prepared = root / "prepared"
            with patch.object(PRODUCER, "ROWS", rows), patch.object(PRODUCER, "ARCHIVES", pins), patch.object(PRODUCER, "profile", return_value=settings):
                result = PRODUCER.prepare_inputs(archives, prepared)
                self.assertTrue(result["success"])
                packages = prepared / "packages"
                meta = source.name + "/Runtime/Selected.cs.meta"
                self.assertEqual(result["files"], {**compiler_files, meta: PRODUCER.sha(source / "Runtime/Selected.cs.meta")})
                self.assertEqual(PRODUCER.package_group(packages, settings, *rows[0])[3], compiler_files)
                archive.write_bytes(b"changed archive")
                with self.assertRaisesRegex(ValueError, "archive drift"):
                    PRODUCER.prepare_inputs(archives, root / "changed")

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

    def test_generated_pathmap_keeps_owner_spaces_in_one_option(self):
        path = Path("/owner/My Packages/source roots")
        self.assertEqual(shlex.split(PRODUCER.pathmap_option(path)), ["/pathmap:/owner/My Packages/source roots=/owner/packages"])

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
