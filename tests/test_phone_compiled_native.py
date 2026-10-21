"""Native consumer contracts with authored SDK/producer doubles, no native tools."""

import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_compiled_native as consumer
from phone_bundle import make_bundle
from phone_content import stage as stage_content
from tests.test_phone_apk import manifest as apk_manifest


ROOT = Path(__file__).resolve().parents[1]
PRODUCER = """import json
from pathlib import Path
def validate(root):
    root=Path(root)
    return json.loads((root/'input-manifest.json').read_text()),json.loads((root/'provenance.json').read_text())
"""
BUILDER = """import hashlib,json,shutil
from pathlib import Path
from phone_native import fixture_request
def stage(project,destination,editor,android,generated_cpp=None):
    destination=Path(destination);destination.mkdir()
    for name,data in {'unity/sdk.c':b'authored sdk','ndk/lib.a':b'authored target archive'}.items():
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    shutil.copytree(generated_cpp,destination/'project/Library/Bee/artifacts/Android/il2cppOutput/cpp')
    shutil.copyfile(__file__,destination/'phone_native.py')
    plan={'graph_sha256':'fixture-graph','compile':[{'arguments':['-O2'],'output':'obj/fixture.o'}],'link':['-shared'],'library':'libil2cpp.so','changes':['authored relocation'],'game_inputs':False,'desktop_stripping_and_codegen_inputs':False,'desktop_stripping_inputs':True,'codegen_origin':'phone-converter'}
    (destination/'plan.json').write_text(json.dumps(plan,indent=2)+'\\n')
    files={p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.rglob('*') if p.is_file()}
    (destination/'input-manifest.json').write_text(json.dumps(files,indent=2)+'\\n')
"""


class PhoneCompiledNativeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root, self.work, self.template, self.converter, self.output, self.editor, self.android = (
            self.base / name for name in ("repo", "work", "template", "converter", "output", "editor", "android")
        )
        for path in (self.root, self.work, self.template, self.converter, self.output, self.editor, self.android):
            path.mkdir()
        for name in ("phone_compiled_native.py", "phone_managed_compile.py"):
            target = self.root / "scripts/lab" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "scripts/lab" / name, target)
        (self.root / "scripts/lab/phone_native.py").write_text(BUILDER)
        (self.root / "scripts/lab/phone_compiled_converter.py").write_text(PRODUCER)
        for name in consumer.FIXTURE_FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "test: authored native consumer"], cwd=self.root, check=True
        )
        (self.editor / "MacOS").mkdir()
        (self.editor / "MacOS/Unity").write_bytes(b"authored SDK identity")
        project = self.work / "rebuild/phone-content/authored/project"
        stage_content(project)
        apk = project.parent / "base.apk"
        self.data = dict(zip(consumer.DATA, (b"authored metadata", b"authored resources")))
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("AndroidManifest.xml", apk_manifest())
            archive.writestr("assets/phone-fixture.bundle", make_bundle())
            for key, value in self.data.items():
                archive.writestr(consumer.DATA[key], value)
        self.request = self.work / "fixture-request.json"
        self.write(self.request, dict(project=str(project), apk=str(apk), sha256=consumer.sha(apk)))
        for name, data in {"unity/sdk.c": b"authored sdk", "ndk/lib.a": b"authored target archive"}.items():
            path = self.template / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.manifest(self.template)
        (self.converter / "phone_compiled_converter.py").write_text(PRODUCER)
        (self.converter / "converter").mkdir()
        self.write(self.converter / "converter/plan.json", dict(graph_sha256="fixture-graph"))
        self.write(self.converter / "converter/input-manifest.json", {})
        upstream = dict(source_commit="a" * 40, supplier_source_commit="b" * 40, compiler_source_commit="c" * 40)
        self.write(self.converter / "provenance.json", upstream)
        self.manifest(self.converter)
        (self.output / "cpp").mkdir()
        (self.output / "cpp/Fixture.cpp").write_bytes(b"actual authored generated source")
        for name, data in self.data.items():
            path = self.output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        outputs = {path.relative_to(self.output).as_posix(): consumer.sha(path) for path in self.output.rglob("*") if path.is_file()}
        self.write(
            self.output / "result.json",
            dict(success=True, exit_code=0, input_manifest_sha256=consumer.sha(self.converter / "converter/input-manifest.json"), outputs=outputs),
        )
        self.write(
            self.output / "handoff-result.json",
            dict(
                schema=1,
                profile="authored-android-compiler-converter-v1",
                **upstream,
                **consumer.SCOPE,
                success=True,
                exit_code=0,
                input_manifest_sha256=consumer.sha(self.converter / "input-manifest.json"),
                converter_result_sha256=consumer.sha(self.output / "result.json"),
                outputs=outputs,
            ),
        )
        patches = patch.multiple(
            consumer,
            CONVERTER_SHA=consumer.sha(self.converter / "phone_compiled_converter.py"),
            NATIVE_SHA=consumer.sha(self.root / "scripts/lab/phone_native.py"),
            TEMPLATE_SHA=consumer.sha(self.template / "input-manifest.json"),
            APK_SHA=consumer.sha(apk),
            FIXTURE_SHA=consumer.sha(project / "fixture-inputs.json"),
            SDK_SHA=consumer.sha(self.editor / "MacOS/Unity"),
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
                path.relative_to(root).as_posix(): consumer.sha(path)
                for path in sorted(root.rglob("*"))
                if path.is_file() and path != root / "input-manifest.json"
            },
        )

    def stage(self):
        with patch("common.WORK", self.work):
            return consumer.stage(self.root, self.template, self.request, self.converter, self.output, self.editor, self.android, self.work)[0]

    def child(self, argv, **kwargs):
        self.assertEqual(argv[1:4], ["-I", "-S", "-B"])
        native, output = Path(argv[-3]), Path(argv[-1])
        output.mkdir()
        header = bytearray(64)
        header[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into("<HHI", header, 16, 3, 183, 1)
        (output / "libil2cpp.so").write_bytes(header + b"authored native result")
        self.write(
            output / "result.json",
            dict(
                success=True,
                input_manifest_sha256=consumer.sha(native / "input-manifest.json"),
                completed=1,
                library_sha256=consumer.sha(output / "libil2cpp.so"),
            ),
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    def run_native(self, stage):
        output = stage.with_name(stage.name + "-output-test")
        with patch.object(consumer.subprocess, "run", side_effect=self.child):
            result = consumer.build(stage, self.base / "tool", output)
        self.assertTrue(result["success"], result)
        return output, dict(stage=str(stage), output=str(output), result_sha256=consumer.sha(output / "handoff-result.json"))

    def test_actual_cpp_metadata_and_unchanged_compile_options_reach_native_stage(self):
        stage = self.stage()
        consumer.validate(stage)
        self.assertEqual((stage / "native" / consumer.CPP / "Fixture.cpp").read_bytes(), (self.output / "cpp/Fixture.cpp").read_bytes())
        base = json.loads((stage / "native-base-plan.json").read_text())
        plan = json.loads((stage / "native/plan.json").read_text())
        self.assertEqual((base["compile"], base["link"]), (plan["compile"], plan["link"]))
        self.assertFalse(plan["desktop_stripping_inputs"])
        self.assertFalse(any(path.name == "__pycache__" for path in stage.rglob("*")))

    def test_metadata_must_match_exact_player_before_native_capture(self):
        path = self.output / "data/Metadata/global-metadata.dat"
        path.write_bytes(b"different metadata")
        for name in ("result.json", "handoff-result.json"):
            value = json.loads((self.output / name).read_text())
            value["outputs"]["data/Metadata/global-metadata.dat"] = consumer.sha(path)
            if name == "handoff-result.json":
                value["converter_result_sha256"] = consumer.sha(self.output / "result.json")
            self.write(self.output / name, value)
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            self.stage()

    def test_rehashed_compile_option_change_refuses(self):
        stage = self.stage()
        path = stage / "native/plan.json"
        value = json.loads(path.read_text())
        value["compile"][0]["arguments"] = ["-O0"]
        self.write(path, value)
        self.manifest(stage / "native")
        self.manifest(stage)
        with self.assertRaisesRegex(ValueError, "options changed"):
            consumer.validate(stage)

    def test_rehashed_sdk_change_refuses(self):
        stage = self.stage()
        (stage / "native/unity/sdk.c").write_bytes(b"different SDK")
        self.manifest(stage / "native")
        self.manifest(stage)
        with self.assertRaisesRegex(ValueError, "changed an input"):
            consumer.validate(stage)

    def test_native_and_converter_graph_generations_must_match(self):
        stage = self.stage()
        self.write(stage / "converter/converter/plan.json", dict(graph_sha256="another-graph"))
        self.manifest(stage)
        with self.assertRaisesRegex(ValueError, "another fixture generation"):
            consumer.validate(stage)

    def test_foreign_stage_files_and_links_refuse(self):
        stage = self.stage()
        (stage / "unknown").write_bytes(b"unknown")
        with self.assertRaisesRegex(ValueError, "Foreign"):
            consumer.validate(stage)
        (stage / "unknown").unlink()
        (stage / "unknown").symlink_to(self.template / "input-manifest.json")
        self.manifest(stage)
        with self.assertRaisesRegex(ValueError, "links"):
            consumer.validate(stage)

    def test_native_result_binds_exact_player_library_pair(self):
        stage = self.stage()
        output, request = self.run_native(stage)
        apk, library = consumer.library_input(request)
        self.assertEqual(apk, stage / "fixture/base.apk")
        self.assertEqual(library, output / "libil2cpp.so")
        library.write_bytes(b"not a native library")
        with self.assertRaisesRegex(ValueError, "ELF64"):
            consumer.library_input(request)

    def test_rehashed_scope_promotion_refuses(self):
        stage = self.stage()
        output, request = self.run_native(stage)
        path = output / "handoff-result.json"
        value = json.loads(path.read_text())
        value["managed_game_compilation_qualified"] = True
        self.write(path, value)
        request["result_sha256"] = consumer.sha(path)
        with self.assertRaisesRegex(ValueError, "handoff/scope"):
            consumer.library_input(request)

    def test_foreign_and_reused_output_refuse_before_compilation(self):
        stage = self.stage()
        with patch.object(consumer.subprocess, "run") as child:
            for output in (stage, self.work / "foreign"):
                with self.assertRaisesRegex(ValueError, "fresh owned sibling"):
                    consumer.build(stage, self.base / "tool", output)
            child.assert_not_called()

    def test_child_input_mutation_refuses_after_execution(self):
        stage = self.stage()

        def drift(*args, **kwargs):
            result = self.child(*args, **kwargs)
            (stage / "native/plan.json").write_text("{}")
            return result

        output = stage.with_name(stage.name + "-output-mutant")
        with patch.object(consumer.subprocess, "run", side_effect=drift):
            result = consumer.build(stage, self.base / "tool", output)
        self.assertFalse(result["success"])
        self.assertIn("input drift", result["failure"])

    def test_explicit_fixture_context_is_restored_on_guard_failure(self):
        import common

        prior = common.ROOT, common.WORK
        value = json.loads(self.request.read_text())
        self.write(self.request, dict(value, unknown=True))
        with self.assertRaisesRegex(ValueError, "Expected explicit"):
            self.stage()
        self.assertEqual((common.ROOT, common.WORK), prior)

    def test_child_timeout_preserves_bounded_diagnostics_and_failure_receipt(self):
        for stdout, stderr, partial in ((None, None, False), (b"\xff" + b"x" * 100000, "e" * 100000, True)):
            with self.subTest(partial_output=partial):
                stage = self.stage()
                stage_hash = consumer.sha(stage / "input-manifest.json")
                output = stage.with_name(stage.name + "-output-timeout")

                def timeout(argv, **kwargs):
                    self.assertEqual(kwargs["timeout"], 1800)
                    if partial:
                        self.child(argv, **kwargs)
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=stdout, stderr=stderr)

                with patch.object(consumer.subprocess, "run", side_effect=timeout):
                    result = consumer.build(stage, self.base / "tool", output)
                self.assertFalse(result["success"])
                self.assertTrue(result["timed_out"])
                self.assertIsNone(result["exit_code"])
                self.assertEqual(result["timeout_seconds"], 1800)
                self.assertIn("timed out", result["failure"])
                self.assertNotIn("library_sha256", result)
                self.assertNotIn("native_built", result)
                self.assertEqual(result, json.loads((output / "handoff-result.json").read_text()))
                self.assertLessEqual((output / "stdout.log").stat().st_size, 65536)
                self.assertLessEqual((output / "stderr.log").stat().st_size, 65536)
                self.assertLessEqual((output / "driver.log").stat().st_size, 131072)
                self.assertEqual(result["stdout_truncated"], partial)
                self.assertEqual(result["stderr_truncated"], partial)
                self.assertEqual(consumer.sha(stage / "input-manifest.json"), stage_hash)
                if partial:
                    self.assertIn("\ufffd", (output / "stdout.log").read_text())
                    self.assertTrue(json.loads((output / "result.json").read_text())["success"])

    def test_normal_completion_keeps_full_long_stdout_and_stderr(self):
        stdout, stderr = "normal stdout " * 10000, "normal stderr " * 10000
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code):
                stage = self.stage()
                output = stage.with_name(stage.name + "-output-normal")

                def completed(argv, **kwargs):
                    self.child(argv, **kwargs)
                    return subprocess.CompletedProcess(argv, exit_code, stdout, stderr)

                with patch.object(consumer.subprocess, "run", side_effect=completed):
                    result = consumer.build(stage, self.base / "tool", output)
                self.assertEqual(result["success"], exit_code == 0)
                self.assertEqual(result["exit_code"], exit_code)
                self.assertEqual((output / "driver.log").read_text(), stdout + stderr)
                self.assertNotIn("timed_out", result)
                self.assertNotIn("stdout_truncated", result)
                self.assertFalse((output / "stdout.log").exists())
                self.assertFalse((output / "stderr.log").exists())


if __name__ == "__main__":
    unittest.main()
