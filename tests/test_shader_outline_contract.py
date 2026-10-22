"""Synthetic fail-closed contracts; no game-derived strings or data."""

from __future__ import annotations

import atexit
import hashlib
import json
import importlib.util
import shutil
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_stage = tempfile.TemporaryDirectory(prefix="outline-public-contract-")
atexit.register(_stage.cleanup)
TEST_ROOT = Path(_stage.name).resolve()
(TEST_ROOT / "scripts/lab").mkdir(parents=True)
(TEST_ROOT / "recipe").mkdir()
for module in ("common.py", "shader_segments.py"):
    shutil.copy2(REPO / "scripts/lab" / module, TEST_ROOT / "scripts/lab" / module)
for module in ("shader_outline.py", "shader_source.py"):
    shutil.copy2(REPO / "scripts/lab" / module, TEST_ROOT / "scripts/lab" / module)
public_recipe = {
    "schema": 1,
    "target": "synthetic",
    "source": {"input_id": "synthetic-input"},
    "stable_output": "generated-shader-candidates/outline-highlight/{input_id}",
    "programs": [],
    "helpers": {"shader_source.py": hashlib.sha256((TEST_ROOT / "scripts/lab/shader_source.py").read_bytes()).hexdigest()},
    "d3dasm": {"revision": "synthetic", "binary_sha256": "0" * 64},
}
(TEST_ROOT / "recipe/shader-outline-candidate.json").write_text(json.dumps(public_recipe), encoding="utf-8")
_path_before_import = sys.path[:]
spec = importlib.util.spec_from_file_location("outline_generator_r3_synthetic", TEST_ROOT / "scripts/lab/shader_outline.py")
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
assert spec.loader is not None
spec.loader.exec_module(generator)
sys.path[:] = _path_before_import
sys.path.insert(0, str(REPO / "scripts/lab"))
from shader_source import bind_hlsl


def spec_for(pass_index: int, stage: str, data: bytes) -> dict:
    return {"pass": pass_index, "stage": stage, "sha256": hashlib.sha256(data).hexdigest()}


class GeneratorContractTests(unittest.TestCase):
    def test_production_recipe_is_fixed_public_path_without_private_fallback(self) -> None:
        self.assertEqual(generator.RECIPE_PATH, TEST_ROOT / "recipe/shader-outline-candidate.json")
        self.assertFalse((TEST_ROOT / "scripts/lab/recipe_candidate.json").exists())
        self.assertNotIn("normalized_catalog_reference", generator.EXPECTED)

    def test_binder_retains_only_measured_interpolation_metadata(self) -> None:
        source = "void main(noperspective float4 p : SV_POSITION0) { }"
        _function, params, _declarations, _textures, _used = bind_hlsl(source, {"buffers": [], "textures": []}, "native_test")
        self.assertEqual(params[0]["interpolation"], "noperspective")

    def test_measured_interpolation_is_on_fragment_entry_interface(self) -> None:
        vertex = [
            {"out": False, "name": "position", "semantic": "POSITION0", "columns": 4},
            {"out": False, "name": "uv", "semantic": "TEXCOORD0", "columns": 2},
            {"out": True, "name": "clip", "semantic": "SV_POSITION0", "columns": 4},
            {"out": True, "name": "coord", "semantic": "TEXCOORD1", "columns": 2},
        ]
        fragment = [
            {"out": False, "name": "clip", "semantic": "SV_POSITION0", "columns": 4, "interpolation": "noperspective"},
            {"out": False, "name": "coord", "semantic": "TEXCOORD1", "columns": 2},
            {"out": True, "name": "target", "semantic": "SV_Target0", "columns": 4},
        ]
        generated = generator._wrapper(1, vertex, fragment)
        fragment_interface = generated.split("struct Pass1FragmentInput {", 1)[1].split("};", 1)[0]
        self.assertIn("noperspective float4 SV_POSITION0 : SV_POSITION0;", fragment_interface)
        self.assertIn("float4 frag(Pass1FragmentInput i)", generated)
        vertex_interface = generated.split("struct Pass1VertexOutput {", 1)[1].split("};", 1)[0]
        self.assertNotIn("noperspective", vertex_interface)

    def test_wrapper_rejects_unmeasured_vertex_interpolation(self) -> None:
        vertex = [
            {"out": False, "name": "position", "semantic": "POSITION0", "columns": 4},
            {"out": False, "name": "uv", "semantic": "TEXCOORD0", "columns": 2},
            {"out": True, "name": "clip", "semantic": "SV_POSITION0", "columns": 4, "interpolation": "noperspective"},
        ]
        fragment = [
            {"out": False, "name": "clip", "semantic": "SV_POSITION0", "columns": 4},
            {"out": True, "name": "target", "semantic": "SV_Target0", "columns": 4},
        ]
        with self.assertRaisesRegex(RuntimeError, "vertex-output interpolation"):
            generator._wrapper(0, vertex, fragment)

    def test_program_join_accepts_exact_two_pass_pairs(self) -> None:
        payloads = {4: b"vertex-a", 8: b"pixel-a"}
        expected = {4: spec_for(0, "vertex", payloads[4]), 8: spec_for(1, "fragment", payloads[8])}
        records = [
            {"kind": "program", "index": 4, "pass_index": 0, "stage": "vertex"},
            {"kind": "program", "index": 8, "pass_index": 1, "stage": "fragment"},
        ]
        self.assertEqual(generator.validate_program_records(records, payloads, expected), payloads)

    def test_program_join_rejects_missing_duplicate_cross_pass_and_hash_drift(self) -> None:
        payload = b"vertex-a"
        expected = {4: spec_for(0, "vertex", payload)}
        good = {"kind": "program", "index": 4, "pass_index": 0, "stage": "vertex"}
        cases = [
            ([], {4: payload}),
            ([good, good], {4: payload}),
            ([{**good, "pass_index": 1}], {4: payload}),
            ([{**good, "stage": "fragment"}], {4: payload}),
            ([good], {4: b"changed"}),
        ]
        for records, payloads in cases:
            with self.subTest(records=records, payloads=payloads), self.assertRaises(RuntimeError):
                generator.validate_program_records(records, payloads, expected)

    def test_catalog_join_requires_one_exact_dependency_bundle(self) -> None:
        record = {
            "keys": [{"key": "synthetic-key", "locations": [0]}],
            "locations": [
                {"id": 2, "internalId": "asset/path", "dependencySet": 0},
                {"id": 3, "internalId": "bundle/path", "bundle": {"Hash": "expected"}},
            ],
            "dependencySets": [[1]],
        }
        self.assertEqual(generator.select_bundle_location(record, "synthetic-key", 2, "asset/path", "expected")["id"], 3)
        record["dependencySets"][0].append(1)
        with self.assertRaises(RuntimeError):
            generator.select_bundle_location(record, "synthetic-key", 2, "asset/path", "expected")
        with self.assertRaises(RuntimeError):
            generator.select_bundle_location(record, "synthetic-key", 9, "asset/path", "expected")

    def test_vertex_and_fragment_contract_rejects_width_drift(self) -> None:
        vertex = [
            {"out": False, "name": "p", "semantic": "POSITION0", "columns": 4},
            {"out": False, "name": "uv", "semantic": "TEXCOORD0", "columns": 4},
            {"out": True, "name": "pos", "semantic": "SV_POSITION0", "columns": 4},
            {"out": True, "name": "uvOut", "semantic": "TEXCOORD0", "columns": 2},
        ]
        fragment = [
            {"out": False, "name": "uvIn", "semantic": "TEXCOORD0", "columns": 2},
            {"out": True, "name": "color", "semantic": "SV_Target0", "columns": 4},
        ]
        self.assertIn("native_5", generator._wrapper(1, vertex, fragment))
        fragment[0]["columns"] = 3
        with self.assertRaises(RuntimeError):
            generator._wrapper(1, vertex, fragment)

    def test_stable_target_is_input_scoped_and_never_overwrites_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="outline-action-test-") as temp:
            work = Path(temp)
            (work / "config").mkdir()
            (work / "config/accepted-input.json").write_text(json.dumps({"input_id": generator.EXPECTED["input_id"]}), encoding="utf-8")
            generated = []

            def fake_generate(output: Path) -> dict:
                output.mkdir(parents=True)
                (output / "sources").mkdir()
                payload = b"synthetic-candidate" if not generated else b"changed-candidate"
                (output / "sources/OutlineHighlightCandidate.shader").write_bytes(payload)
                result = {
                    "success": True,
                    "generated_shader_sha256": hashlib.sha256(payload).hexdigest(),
                    "semantic_equivalence_proven": False,
                    "android_compile_or_render_tested": False,
                }
                (output / "manifest.json").write_text(json.dumps(result), encoding="utf-8")
                generated.append(result)
                return result

            with patch.object(generator, "WORK", work), patch.object(generator, "generate_candidate", side_effect=fake_generate):
                with self.assertRaises(RuntimeError):
                    generator.generate("lab")
                first = generator.generate("outline-highlight")
                final = work / "generated-shader-candidates/outline-highlight" / generator.EXPECTED["input_id"]
                before = (final / "sources/OutlineHighlightCandidate.shader").read_bytes()
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    generator.generate("outline-highlight")
                self.assertEqual((final / "sources/OutlineHighlightCandidate.shader").read_bytes(), before)
                self.assertEqual(first["generated_shader_sha256"], generated[0]["generated_shader_sha256"])


if __name__ == "__main__":
    unittest.main()
