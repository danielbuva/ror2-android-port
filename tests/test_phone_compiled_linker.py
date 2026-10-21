import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_compiled_linker as handoff


class CompiledLinkerContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        repository = Path(__file__).resolve().parents[1]
        for name in (handoff.SOURCE, "scripts/lab/phone_managed_compile.py"):
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes((repository / name).read_bytes())
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "test: authored compiler handoff"], cwd=self.root, check=True
        )
        self.template = self.root / "template"
        self.template.mkdir()
        plan = self.template / "plan.json"
        plan.write_text(json.dumps(dict(game_inputs=False, desktop_editor_roots=True, native_registry={"authored": True})))
        inputs = self.template / "inputs"
        inputs.mkdir()
        (inputs / "Assembly-CSharp.dll").write_bytes(b"authored previous implementation")
        (inputs / "Assembly-CSharp.pdb").write_bytes(b"authored previous symbols")
        (self.template / "phone_linker.py").write_text("# authored nonexecuted child substitute\n")
        original = {p.relative_to(self.template).as_posix(): handoff.sha(p) for p in self.template.rglob("*") if p.is_file()}
        (self.template / "input-manifest.json").write_text(json.dumps(original, indent=2) + "\n")
        self.compiler = self.root / "compiler"
        self.compiler.mkdir()
        (self.compiler / "authored-source.cs").write_text("// public source substitute\n")
        receipt = dict(
            schema=1,
            profile=handoff.COMPILER_PROFILE,
            source_commit=handoff.COMPILER_SOURCE,
            game_inputs=False,
            inputs={"authored-source.cs": handoff.sha(self.compiler / "authored-source.cs")},
        )
        (self.compiler / "inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
        self.output = self.root / "compiler-output"
        self.output.mkdir()
        outputs = {}
        for name in handoff.OUTPUTS:
            (self.output / name).write_bytes(("authored Android output " + name).encode())
            outputs[name] = handoff.sha(self.output / name)
        (self.output / "references.json").write_text(json.dumps(dict(scope="authored reference substitute", source_commit=handoff.COMPILER_SOURCE)) + "\n")
        result = dict(
            schema=1,
            success=True,
            exit_code=0,
            source_commit=handoff.COMPILER_SOURCE,
            host="android",
            runtime="8.0.32",
            inputs_sha256=handoff.sha(self.compiler / "inputs.json"),
            outputs=outputs,
            reference_count=157,
            reference_report_sha256=handoff.sha(self.output / "references.json"),
            game_inputs=False,
            player_built=False,
            unity_player_compilation_qualified=False,
            managed_game_compilation_qualified=False,
        )
        (self.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        for change in (
            patch.object(handoff, "TEMPLATE_SHA", handoff.sha(self.template / "input-manifest.json")),
            patch.object(handoff, "COMPILER_INPUTS_SHA", handoff.identity(self.compiler / "inputs.json")[1]),
            patch.object(handoff, "REFERENCE_REPORT_SHA", handoff.identity(self.output / "references.json")[1]),
            patch.object(handoff, "OUTPUTS", outputs),
        ):
            change.start()
            self.addCleanup(change.stop)
        self.work = self.root / "work"

    def stage(self):
        return handoff.stage(self.root, self.template, self.compiler, self.output, self.work)[0]

    def test_new_handoff_changes_only_two_template_inputs_and_preserves_original(self):
        before = {p.relative_to(self.template).as_posix(): handoff.sha(p) for p in self.template.rglob("*") if p.is_file()}
        stage = self.stage()
        manifest, provenance = handoff.validate(stage)
        changed = [name for name, digest in json.loads((stage / "template-manifest.json").read_text()).items() if manifest[name] != digest]
        self.assertEqual(sorted(changed), ["inputs/Assembly-CSharp.dll", "inputs/Assembly-CSharp.pdb"])
        self.assertFalse(provenance["desktop_compiled_fixture_input"])
        self.assertTrue(provenance["desktop_editor_roots"])
        self.assertFalse(provenance["managed_game_compilation_qualified"])
        self.assertEqual(before, {p.relative_to(self.template).as_posix(): handoff.sha(p) for p in self.template.rglob("*") if p.is_file()})

    def test_unknown_template_or_compiler_outputs_refuse_before_staging(self):
        file = self.template / "plan.json"
        original = file.read_bytes()
        file.write_text("{}")
        with self.assertRaisesRegex(ValueError, "input drift"):
            self.stage()
        self.assertFalse(self.work.exists())
        file.write_bytes(original)
        (self.output / "Assembly-CSharp.dll").write_bytes(b"authored compiler output drift")
        with self.assertRaisesRegex(ValueError, "output drift"):
            self.stage()
        self.assertFalse(self.work.exists())

    def test_supplier_receipt_drift_and_scope_mismatch_refuse(self):
        (self.compiler / "authored-source.cs").write_text("// changed source\n")
        with self.assertRaisesRegex(ValueError, "supplier input drift"):
            self.stage()
        self.assertFalse(self.work.exists())
        (self.compiler / "authored-source.cs").write_text("// public source substitute\n")
        file = self.output / "result.json"
        result = json.loads(file.read_text())
        result["managed_game_compilation_qualified"] = True
        file.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, "scope differs"):
            self.stage()
        self.assertFalse(self.work.exists())

    def test_identical_inputs_after_unrelated_commit_keep_actual_commit_and_raw_receipts(self):
        commit = "a" * 40
        for file in (self.compiler / "inputs.json", self.output / "references.json"):
            value = json.loads(file.read_text())
            value["source_commit"] = commit
            file.write_text(json.dumps(value, indent=2) + "\n")
        file = self.output / "result.json"
        value = json.loads(file.read_text())
        value.update(
            source_commit=commit, inputs_sha256=handoff.sha(self.compiler / "inputs.json"), reference_report_sha256=handoff.sha(self.output / "references.json")
        )
        file.write_text(json.dumps(value, indent=2) + "\n")
        stage = self.stage()
        _, provenance = handoff.validate(stage)
        self.assertEqual(provenance["compiler_source_commit"], commit)
        self.assertEqual(provenance["compiler_inputs_sha256"], handoff.sha(self.compiler / "inputs.json"))
        self.assertEqual(provenance["compiler_result_sha256"], handoff.sha(file))
        self.assertEqual((stage / "compiler-inputs.json").read_bytes(), (self.compiler / "inputs.json").read_bytes())

    def test_staged_foreign_files_links_and_template_changes_refuse(self):
        for control in ("foreign", "link", "template"):
            stage = self.stage()
            if control == "foreign":
                (stage / "extra.rsp").write_text("// unknown input")
            elif control == "link":
                (stage / "escape").symlink_to(self.root, target_is_directory=True)
            else:
                file = stage / "plan.json"
                file.write_text("{}")
                manifest = json.loads((stage / "input-manifest.json").read_text())
                manifest["plan.json"] = handoff.sha(file)
                (stage / "input-manifest.json").write_text(json.dumps(manifest))
            with self.subTest(control=control), self.assertRaises(ValueError):
                handoff.validate(stage)

    def invoke(self, stage, *, exit_code=0, mutate=False):
        output = stage.parent / (stage.name + "-output-test")

        def run(arguments, **kwargs):
            self.assertEqual(arguments[:4], [sys.executable, "-I", "-S", "-B"])
            self.assertIn(str(stage / "phone_linker.py"), arguments)
            output.mkdir()
            stripped = output / "stripped"
            stripped.mkdir()
            file = stripped / "Assembly-CSharp.dll"
            file.write_bytes(b"authored stripped output")
            receipt = dict(
                success=exit_code == 0,
                exit_code=exit_code,
                input_manifest_sha256=handoff.sha(stage / "input-manifest.json"),
                outputs={file.name: handoff.sha(file)},
            )
            (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
            if mutate:
                (stage / "inputs/Assembly-CSharp.dll").write_bytes(b"authored concurrent drift")
            return SimpleNamespace(returncode=exit_code, stdout="authored linker control\n", stderr="")

        with patch.object(handoff.subprocess, "run", side_effect=run):
            return output, handoff.strip(stage, self.root / "owned-tools", output)

    def test_child_receipt_and_stripped_outputs_are_bound_without_rewriting_linker_result(self):
        stage = self.stage()
        output, result = self.invoke(stage)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["linker_result_sha256"], handoff.sha(output / "result.json"))
        before = handoff.sha(output / "result.json")
        self.assertFalse(result["desktop_compiled_fixture_input"])
        with self.assertRaisesRegex(ValueError, "fresh owned sibling"):
            handoff.strip(stage, self.root / "tools", output)
        self.assertEqual(before, handoff.sha(output / "result.json"))

    def test_failed_child_or_changed_inputs_keep_failure_receipts(self):
        for kwargs in (dict(exit_code=9), dict(mutate=True)):
            stage = self.stage()
            output, result = self.invoke(stage, **kwargs)
            with self.subTest(kwargs=kwargs):
                self.assertFalse(result["success"])
                self.assertIn("failure", result)
                self.assertEqual(result, json.loads((output / "handoff-result.json").read_text()))


if __name__ == "__main__":
    unittest.main()
