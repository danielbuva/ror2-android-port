"""Public-safe contracts for the accepted-input-scoped RampFog action."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

INTEGRATION = next(parent for parent in Path(__file__).resolve().parents if (parent / "scripts/lab/shader_ramp_fog.py").is_file())
REPO = INTEGRATION
PROJECT_ROOT = next(parent for parent in (INTEGRATION, *INTEGRATION.parents) if (parent / "scripts/lab/common.py").is_file())
SOURCE_MODULE = INTEGRATION / "scripts/lab/shader_ramp_fog.py"
PUBLIC_RECIPE = INTEGRATION / "recipe/shader-ramp-fog-candidate.json"


def load_isolated_module(root: Path):
    lab = root / "scripts/lab"
    (lab).mkdir(parents=True)
    (root / "recipe").mkdir()
    for name in ("common.py", "shader_segments.py", "shader_ramp_fog.py"):
        source = PROJECT_ROOT / "scripts/lab" / name if name != "shader_ramp_fog.py" else SOURCE_MODULE
        shutil.copy2(source, lab / name)
    shutil.copy2(PUBLIC_RECIPE, root / "recipe/shader-ramp-fog-candidate.json")
    # A stale/private adjacent recipe must never shadow the fixed public recipe.
    (lab / "recipe_candidate.json").write_text("not-json", encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"shader_ramp_fog_{id(root)}", lab / "shader_ramp_fog.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    old_path = list(sys.path)
    old_modules = {name: sys.modules.pop(name, None) for name in ("common", "shader_segments")}
    sys.path.insert(0, str(lab))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = old_path
        for name, previous in old_modules.items():
            sys.modules.pop(name, None)
            if previous is not None:
                sys.modules[name] = previous
    return module


class ShaderRampFogCandidateTests(unittest.TestCase):
    def test_module_reads_only_fixed_public_recipe(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ramp-fog-mini-root-") as temp:
            root = Path(temp)
            module = load_isolated_module(root)
            self.assertEqual(module.RECIPE_PATH, root.resolve() / "recipe/shader-ramp-fog-candidate.json")
            self.assertEqual(module.RECIPE["target"], "ramp-fog")
            self.assertEqual(module.RECIPE["stable_output"], "generated-shader-candidates/ramp-fog-r4/{input_id}")
            self.assertFalse(module.RECIPE["generation_limits"]["unity_compiled"])
            helper_hash = hashlib.sha256((INTEGRATION / "scripts/lab/shader_deferred.py").read_bytes()).hexdigest()
            self.assertEqual(module.RECIPE["tools"]["shader_deferred_sha256"], helper_hash)
            self.assertEqual(module.RECIPE["stable_output"], "generated-shader-candidates/ramp-fog-r4/{input_id}")

    def test_output_is_stable_input_scoped_and_work_contained(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ramp-fog-path-test-") as temp:
            work = Path(temp) / "work"
            work.mkdir()
            module = load_isolated_module(Path(temp) / "repo")
            output = module.output_path(work, module.SOURCE["input_id"])
            self.assertEqual(output, work.resolve() / "generated-shader-candidates/ramp-fog-r4" / module.SOURCE["input_id"])
            with self.assertRaisesRegex(RuntimeError, "fixed RampFog recipe"):
                module.output_path(work, "another-input")
            module.RECIPE["stable_output"] = "../outside/{input_id}"
            with self.assertRaisesRegex(RuntimeError, "escapes work"):
                module.output_path(work, module.SOURCE["input_id"])

    def test_symlinked_output_parent_refuses(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ramp-fog-symlink-test-") as temp:
            root = Path(temp) / "repo"
            work = Path(temp) / "work"
            work.mkdir()
            module = load_isolated_module(root)
            outside = Path(temp) / "outside"
            outside.mkdir()
            (work / "generated-shader-candidates").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "symlink|outside work"):
                module.output_path(work, module.SOURCE["input_id"])

    def test_bundle_drift_refuses_before_stable_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ramp-fog-drift-test-") as temp:
            root = Path(temp) / "repo"
            work = Path(temp) / "work"
            work.mkdir()
            module = load_isolated_module(root)
            staging = work / ".staging"
            staging.mkdir()
            (staging / "candidate.json").write_text("synthetic candidate", encoding="utf-8")
            bundle = work / "source.bundle"
            bundle.write_bytes(b"original source bytes")
            initial_hash = module.sha_file(bundle)
            bundle.write_bytes(b"changed during generation")
            destination = module.output_path(work, module.SOURCE["input_id"])
            with self.assertRaisesRegex(RuntimeError, "changed during RampFog generation"):
                module._publish_staging(staging, destination, bundle, initial_hash)
            self.assertFalse(destination.exists())
            self.assertTrue((staging / "candidate.json").is_file())

    def test_exclusive_publish_and_overwrite_refusal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ramp-fog-publish-test-") as temp:
            root = Path(temp) / "repo"
            work = Path(temp) / "work"
            work.mkdir()
            module = load_isolated_module(root)
            bundle = work / "source.bundle"
            bundle.write_bytes(b"stable source")
            digest = module.sha_file(bundle)
            staging = work / ".staging"
            staging.mkdir()
            (staging / "candidate.json").write_text("first", encoding="utf-8")
            destination = module.output_path(work, module.SOURCE["input_id"])
            module._publish_staging(staging, destination, bundle, digest)
            self.assertEqual((destination / "candidate.json").read_text(encoding="utf-8"), "first")
            second = work / ".staging-second"
            second.mkdir()
            (second / "candidate.json").write_text("second", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                module._publish_staging(second, destination, bundle, digest)
            self.assertEqual((destination / "candidate.json").read_text(encoding="utf-8"), "first")

    def test_generated_calls_follow_the_recovered_definitions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ramp-fog-order-root-") as temp:
            module = load_isolated_module(Path(temp))
            self._assert_calls_follow_definitions(module)

    def _assert_calls_follow_definitions(self, module) -> None:
        import types

        fake_source = types.ModuleType("shader_source")
        functions = {
            1: "void native_1(float4 p : POSITION0, out precise float4 q : SV_POSITION0, out precise float4 uv : TEXCOORD0) { q=p; uv=p; }",
            2: "void native_2(float4 uv : TEXCOORD0, out precise float4 color : SV_Target0) { color=uv; }",
        }
        params = {
            1: [
                {"out": False, "semantic": "POSITION0", "columns": 4},
                {"out": True, "semantic": "SV_POSITION0", "columns": 4},
                {"out": True, "semantic": "TEXCOORD0", "columns": 4},
            ],
            2: [
                {"out": False, "semantic": "TEXCOORD0", "columns": 4},
                {"out": True, "semantic": "SV_Target0", "columns": 4},
            ],
        }

        def bind_hlsl(_source, _layout, entry):
            index = int(entry.rsplit("_", 1)[1])
            return functions[index], params[index], {}, [], []

        fake_source.bind_hlsl = bind_hlsl
        fake_source.properties = lambda _tree: ""
        fake_deferred = types.ModuleType("shader_deferred")
        fake_deferred.render_state = lambda _state: "Cull Off"
        old_source = sys.modules.get("shader_source")
        old_deferred = sys.modules.get("shader_deferred")
        sys.modules["shader_source"] = fake_source
        sys.modules["shader_deferred"] = fake_deferred
        try:
            module.SOURCE = {"shader_name": "Hidden/Test/RampFog"}
            state = {"lighting": False, "fogMode": -1, "zClip": {"val": 1}, "alphaToMask": {"val": 0}}
            tree = {"m_ParsedForm": {"m_PropInfo": {"m_Props": []}, "m_SubShaders": [{"m_Passes": [{"m_State": state}], "m_LOD": 100, "m_Tags": {"tags": []}}]}}
            signatures = {
                1: {"ISGN": [("POSITION0", 0, "xyzw")], "OSGN": [("SV_POSITION0", 0, "xyzw"), ("TEXCOORD0", 1, "xyzw")]},
                2: {"ISGN": [("TEXCOORD0", 0, "xyzw")], "OSGN": [("SV_Target0", 0, "xyzw")]},
            }
            layouts = {1: {"buffers": [], "textures": []}, 2: {"buffers": [], "textures": []}}
            output = module._shaderlab_candidate(tree, {1: "", 2: ""}, layouts, signatures)
        finally:
            if old_source is None:
                sys.modules.pop("shader_source", None)
            else:
                sys.modules["shader_source"] = old_source
            if old_deferred is None:
                sys.modules.pop("shader_deferred", None)
            else:
                sys.modules["shader_deferred"] = old_deferred
        self.assertLess(output.index(functions[1]), output.index("Varyings vert("))
        self.assertLess(output.index(functions[2]), output.index("float4 frag("))
        self.assertIn(functions[1], output)
        self.assertIn(functions[2], output)

    def test_action_is_current_and_describes_qualification_limits(self) -> None:
        spec = importlib.util.spec_from_file_location("ramp_fog_actions", INTEGRATION / "scripts/lab/actions.py")
        assert spec is not None and spec.loader is not None
        actions = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(actions)
        action = actions.ACTIONS["shader-ramp-fog"]
        self.assertEqual(action.status, "current")
        self.assertEqual((action.module, action.function), ("shader_ramp_fog", "generate"))
        self.assertIn("Host-only", action.help)
        self.assertIn("visual equivalence", action.help)


if __name__ == "__main__":
    unittest.main()
