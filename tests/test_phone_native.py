import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from phone_bundle import make_bundle
from phone_content import stage as stage_content
from phone_native import build, command_arguments, compiler_arguments, fixture_request, lump_includes, path_argument, reuse_objects
from tests.test_phone_apk import manifest


class PhoneNativeTests(unittest.TestCase):
    def test_shared_fixture_guard_binds_actual_authored_sources_not_only_the_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary).resolve() / "work"
            project = work / "rebuild/phone-content/authored/project"
            stage_content(project)
            apk = project.parent / "fixture.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", manifest())
                archive.writestr("assets/phone-fixture.bundle", make_bundle())
            value = {"project": str(project), "apk": str(apk), "sha256": hashlib.sha256(apk.read_bytes()).hexdigest()}
            request = work / "request.json"
            request.write_text(json.dumps(value))
            with patch("common.WORK", work):
                self.assertEqual(fixture_request(request), (value, project))
                request.write_text(json.dumps(value | {"unknown": {}}))
                with self.assertRaisesRegex(ValueError, "Expected explicit"):
                    fixture_request(request)
                request.write_text(json.dumps(value))
                (project / "Assets/ContentFixture.cs").write_text("unrecorded source change")
                with self.assertRaisesRegex(ValueError, "Staged fixture source drift"):
                    fixture_request(request)

    def test_lump_regeneration_preserves_order_and_refuses_extra_directives(self):
        node = {"WriteTextFilePayload": '// generated\n#include "second.cpp"\n#include "first.cpp"\n', "FilesThatMightBeIncluded": ["first.cpp", "second.cpp"]}
        self.assertEqual(lump_includes(node), ["second.cpp", "first.cpp"])
        with self.assertRaises(ValueError):
            lump_includes(node | {"WriteTextFilePayload": node["WriteTextFilePayload"] + "#define CHANGE 1\n"})
        with self.assertRaises(ValueError):
            lump_includes(node | {"FilesThatMightBeIncluded": ["first.cpp"]})

    def test_structured_argument_mapping_keeps_literal_defines_and_output_ownership(self):
        compiler = Path("/supplied/compiler")
        roots = [(Path("/supplied/sdk"), "unity")]
        tokens = [str(compiler), '-DNAME="literal"', "-I/supplied/sdk/include", "-I.", "-o", "obj/result.o", "-c", "/supplied/sdk/source.cpp"]
        actual = command_arguments(shlex.join(tokens), compiler, roots, set())
        self.assertEqual(actual[0], '-DNAME="literal"')
        self.assertEqual(actual[1], {"path": "unity/include", "prefix": "-I"})
        self.assertEqual(actual[2], {"path": "project", "prefix": "-I"})
        self.assertEqual(actual[4], {"output": "obj/result.o"})
        self.assertEqual(actual[-1], {"path": "unity/source.cpp", "prefix": ""})
        for command in (shlex.join(tokens) + " && unexpected", shlex.join([str(compiler), "-o", "../escape.o"])):
            with self.assertRaises(ValueError):
                command_arguments(command, compiler, roots, set())
        with self.assertRaises(ValueError):
            path_argument("/unknown/source.cpp", roots)
        with self.assertRaises(ValueError):
            path_argument("/supplied/sdk/../private.cpp", roots)

    def test_staged_input_drift_stops_before_compiler_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            (stage / "source.cpp").write_text("changed")
            (stage / "input-manifest.json").write_text(json.dumps({"source.cpp": hashlib.sha256(b"original").hexdigest()}))
            output = root / "output"
            with patch("phone_native.subprocess.run") as run:
                self.assertFalse(build(stage, root, output))
                run.assert_not_called()
                with self.assertRaises(FileExistsError):
                    build(stage, root, output)
            result = json.loads((output / "result.json").read_text())
            self.assertIn("input drift", result["failure"])
            self.assertFalse(result["success"])
            self.assertEqual(result["commands"], [])

    def test_link_uses_explicit_pinned_static_libraries_without_implicit_runtime(self):
        argv = compiler_arguments(Path("/stage"), Path("/tools"), Path("/out"), ["-shared", "-fuse-ld=bfd"], link=True)
        self.assertIn("-nostdlib++", argv)
        self.assertIn("--unwindlib=none", argv)
        self.assertIn("/stage/ndk/libgcc.a", argv)
        self.assertNotIn("-fuse-ld=bfd", argv)

    def test_relink_reuses_only_exact_objects_sources_and_compile_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            old, new, prior, output = (root / name for name in ("old", "new", "prior", "output"))
            for path in (old, new, prior, output):
                path.mkdir()
            plan = {"compile": [{"arguments": ["-c", {"path": "source.cpp", "prefix": ""}], "output": "sample.o"}]}
            for path in (old, new):
                (path / "plan.json").write_text(json.dumps(plan))
                (path / "input-manifest.json").write_text(json.dumps({"source.cpp": "same-source-hash"}))
            (prior / "sample.o").write_bytes(b"compiled-object")
            result = {
                "completed": 1,
                "input_manifest_sha256": hashlib.sha256((old / "input-manifest.json").read_bytes()).hexdigest(),
                "commands": [{"label": "compile-000", "exit": 0, "args": compiler_arguments(old, root, prior, plan["compile"][0]["arguments"])}],
            }
            (prior / "result.json").write_text(json.dumps(result))
            request = {
                "output": str(prior),
                "stage": str(old),
                "result_sha256": hashlib.sha256((prior / "result.json").read_bytes()).hexdigest(),
                "objects": {"sample.o": hashlib.sha256(b"compiled-object").hexdigest()},
            }
            self.assertEqual(len(reuse_objects(new, root, output, request)), 1)
            self.assertEqual((output / "sample.o").read_bytes(), b"compiled-object")
            (prior / "sample.o").write_bytes(b"different")
            with self.assertRaisesRegex(ValueError, "object drift"):
                reuse_objects(new, root, output, request)
            (prior / "sample.o").write_bytes(b"compiled-object")
            (new / "input-manifest.json").write_text(json.dumps({"source.cpp": "different-source-hash"}))
            with self.assertRaisesRegex(ValueError, "source/target inputs differ"):
                reuse_objects(new, root, output, request)
            (new / "input-manifest.json").write_text((old / "input-manifest.json").read_text())
            plan["compile"][0]["arguments"].append("-O3")
            (new / "plan.json").write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "compile plan differs"):
                reuse_objects(new, root, output, request)
