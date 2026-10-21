"""Consumer ownership contracts; inert upstream doubles contain no SDK/game data."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_compiled_converter as handoff


ROOT = Path(__file__).resolve().parents[1]
SUPPLIER = """import hashlib, json
from pathlib import Path
def validate(root):
    root=Path(root)
    manifest=json.loads((root/'input-manifest.json').read_text())
    for name,digest in manifest.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('upstream input drift')
    return manifest,json.loads((root/'provenance.json').read_text())
"""


class PhoneCompiledConverterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root, self.work, self.template, self.supplier, self.output = (self.base / name for name in ("repo", "work", "template", "supplier", "output"))
        for path in (self.root, self.work, self.template, self.supplier, self.output):
            path.mkdir()
        self.tool = self.base / "tool"
        self.tool.mkdir()
        for name in ("phone_compiled_converter.py", "phone_converter.py", "phone_managed_compile.py"):
            target = self.root / "scripts/lab" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "scripts/lab" / name, target)
        (self.root / "scripts/lab/phone_compiled_linker.py").write_text(SUPPLIER)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "build: author fixture"], cwd=self.root, check=True)
        upstream = dict(source_commit="a" * 40, compiler_source_commit="b" * 40, compiler_result_sha256="compiler-result")
        (self.supplier / "phone_compiled_linker.py").write_text(SUPPLIER)
        self.write(self.supplier / "provenance.json", upstream)
        self.manifest(self.supplier)
        stripped = self.output / "stripped"
        stripped.mkdir()
        self.members = {"Assembly-CSharp.dll": b"new actual compiler/stripper bytes", "Assembly-CSharp.pdb": b"new actual symbols"}
        for name, data in self.members.items():
            (stripped / name).write_bytes(data)
            target = self.template / handoff.STRIPPED / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"different old replay bytes")
        self.closure = {name: handoff.sha(stripped / name) for name in self.members}
        inner_result = dict(success=True, exit_code=0, input_manifest_sha256=handoff.sha(self.supplier / "input-manifest.json"), outputs=self.closure)
        self.write(self.output / "result.json", inner_result)
        self.write(
            self.output / "handoff-result.json",
            dict(
                schema=1,
                profile="authored-android-compiler-linker-v1",
                **upstream,
                **inner_result,
                **handoff.SCOPE,
                linker_result_sha256=handoff.sha(self.output / "result.json"),
            ),
        )
        shutil.copyfile(ROOT / "scripts/lab/phone_converter.py", self.template / "phone_converter.py")
        self.write(
            self.template / "plan.json",
            dict(game_inputs=False, desktop_editor_roots=True, desktop_stripping_inputs=False, stripping_origin="phone-unitylinker"),
        )
        self.manifest(self.template)
        patches = patch.multiple(
            handoff,
            TEMPLATE_SHA=handoff.sha(self.template / "input-manifest.json"),
            SUPPLIER_SHA=handoff.sha(self.supplier / "phone_compiled_linker.py"),
            STRIPPED_SHA=handoff.fingerprint(self.closure),
        )
        patches.start()
        self.addCleanup(patches.stop)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, indent=2) + "\n")

    def manifest(self, root):
        self.write(
            root / "input-manifest.json",
            {
                path.relative_to(root).as_posix(): handoff.sha(path)
                for path in sorted(root.rglob("*"))
                if path.is_file() and path != root / "input-manifest.json"
            },
        )

    def stage(self):
        return handoff.stage(self.root, self.template, self.supplier, self.output, self.work)[0]

    def child(self, argv, **kwargs):
        self.assertEqual(argv[1:4], ["-I", "-S", "-B"])
        stage, output = Path(argv[-3]), Path(argv[-1])
        (output / "cpp").mkdir(parents=True)
        (output / "data/Metadata").mkdir(parents=True)
        (output / "cpp/Fixture.cpp").write_bytes(b"authored generated code")
        (output / "data/Metadata/global-metadata.dat").write_bytes(b"authored metadata")
        outputs = {path.relative_to(output).as_posix(): handoff.sha(path) for path in output.rglob("*") if path.is_file()}
        self.write(output / "result.json", dict(success=True, exit_code=0, input_manifest_sha256=handoff.sha(stage / "input-manifest.json"), outputs=outputs))
        return subprocess.CompletedProcess(argv, 0, "", "")

    def test_stage_copies_actual_inputs_and_preserves_suppliers(self):
        before = {str(root): handoff.sha(root / "input-manifest.json") for root in (self.supplier, self.template)}
        stage = self.stage()
        manifest, result = handoff.validate(stage)
        self.assertTrue(manifest)
        self.assertEqual(result["profile"], handoff.PROFILE)
        for name, data in self.members.items():
            self.assertEqual((stage / "converter" / handoff.STRIPPED / name).read_bytes(), data)
        self.assertEqual(before, {str(root): handoff.sha(root / "input-manifest.json") for root in (self.supplier, self.template)})
        self.assertFalse(any(path.name == "__pycache__" for path in stage.rglob("*")))

    def test_rehashed_changed_stripped_bytes_remain_unqualified(self):
        stage = self.stage()
        (stage / "converter" / handoff.STRIPPED / "Assembly-CSharp.dll").write_bytes(b"unknown compilation")
        self.manifest(stage / "converter")
        self.manifest(stage)
        with self.assertRaisesRegex(ValueError, "stripping closure"):
            handoff.validate(stage)

    def test_scope_cannot_be_promoted_by_rehashing_the_descriptor(self):
        stage = self.stage()
        file = stage / "compiled-provenance.json"
        value = json.loads(file.read_text())
        value["managed_game_compilation_qualified"] = True
        self.write(file, value)
        self.manifest(stage)
        with self.assertRaisesRegex(ValueError, "provenance"):
            handoff.validate(stage)

    def test_upstream_result_failure_is_not_a_converter_input(self):
        value = json.loads((self.output / "result.json").read_text())
        value["success"] = False
        self.write(self.output / "result.json", value)
        with self.assertRaisesRegex(ValueError, "supplier result/provenance"):
            self.stage()

    def test_links_and_foreign_files_refuse(self):
        stage = self.stage()
        target = stage / "unknown"
        target.write_bytes(b"foreign file")
        with self.assertRaisesRegex(ValueError, "Foreign"):
            handoff.validate(stage)
        target.unlink()
        target.symlink_to(self.template / "plan.json")
        self.manifest(stage)
        with self.assertRaisesRegex(ValueError, "links"):
            handoff.validate(stage)

    def test_actual_child_outputs_are_bound_without_legacy_oracle_substitution(self):
        stage = self.stage()
        output = stage.with_name(stage.name + "-output-actual")
        with patch.object(handoff.subprocess, "run", side_effect=self.child):
            result = handoff.convert(stage, self.tool, output)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["converter_result_sha256"], handoff.sha(output / "result.json"))
        self.assertEqual(set(result["outputs"]), {"cpp/Fixture.cpp", "data/Metadata/global-metadata.dat"})
        self.assertFalse(result["player_built"])

    def test_child_input_mutation_refuses_after_execution(self):
        stage = self.stage()

        def drift(*args, **kwargs):
            result = self.child(*args, **kwargs)
            (stage / "converter/plan.json").write_text("{}")
            return result

        output = stage.with_name(stage.name + "-output-mutant")
        with patch.object(handoff.subprocess, "run", side_effect=drift):
            result = handoff.convert(stage, self.tool, output)
        self.assertFalse(result["success"])
        self.assertIn("input drift", result["failure"])

    def test_foreign_or_existing_output_refuses_before_tool_execution(self):
        stage = self.stage()
        with patch.object(handoff.subprocess, "run") as child:
            for output in (self.work / "foreign", stage):
                with self.assertRaisesRegex(ValueError, "fresh owned sibling"):
                    handoff.convert(stage, self.tool, output)
            child.assert_not_called()


if __name__ == "__main__":
    unittest.main()
