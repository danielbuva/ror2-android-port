import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from phone_native import build, command_arguments, lump_includes, path_argument


class PhoneNativeTests(unittest.TestCase):
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
