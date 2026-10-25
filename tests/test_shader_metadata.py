import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import shader_materials
import shader_metadata as M
from shader_programs import NativePrograms
from shader_segments import variants
from shader_tessellation import TessellationPrograms


def context(name, keywords=(), programs=(), passes=1):
    form = {"m_Name": name, "m_KeywordNames": list(keywords), "m_SubShaders": [{"m_Passes": [{} for _ in range(passes)]}]}
    return ({"m_ParsedForm": form}, None, list(programs), None, {})


def program(index, stage, keys=(), pass_index=0):
    return {"kind": "program", "index": index, "stage": stage, "keywords": sorted(keys), "pass_index": pass_index, "subshader_index": 0}


class ManifestPolicyTests(unittest.TestCase):
    def test_shared_policy_has_no_optional_imports_and_old_callers_use_it(self):
        helper = Path(__file__).resolve().parents[1] / "scripts/lab/shader_metadata.py"
        code = "import runpy,sys; m=runpy.run_path(sys.argv[1]); assert not any(n in sys.modules for n in ('UnityPy','lz4'))"
        subprocess.run([sys.executable, "-S", "-c", code, str(helper)], check=True, capture_output=True, text=True)
        self.assertIs(NativePrograms.pair, M.MetadataPrograms.pair)
        self.assertIs(TessellationPrograms.quad, M.MetadataPrograms.quad)
        self.assertIs(variants, M.variants)

    def test_standard_preserves_sorted_feature_sets_counts_and_resource_ordinals(self):
        rows = [("Assets/C", "Standard Fixture", "CUTOUT,FOG_LINEAR"), ("Assets/A", "Standard Fixture", "FOG_EXP"), ("Assets/B", "Other", "CUTOUT")]
        records = [
            program(11, "progVertex", ["LIGHTPROBE_SH", "UNITY_HDR_ON"]),
            program(12, "progFragment", ["LIGHTPROBE_SH", "UNITY_HDR_ON"]),
            program(21, "progVertex", ["CUTOUT", "LIGHTPROBE_SH", "UNITY_HDR_ON"]),
            program(22, "progFragment", ["CUTOUT", "LIGHTPROBE_SH", "UNITY_HDR_ON"]),
        ]
        source = context("Standard Fixture", programs=records)
        full = M.standard_manifest(rows, source)
        self.assertEqual(full["source_material_count"], 2)
        self.assertEqual(
            full["variants"],
            [
                {"resource": "AndroidNativeStandard0", "keywords": [], "vertex": 11, "fragment": 12},
                {"resource": "AndroidNativeStandard1", "keywords": ["CUTOUT"], "vertex": 21, "fragment": 22},
            ],
        )
        selected = M.standard_manifest(rows, source, {"AndroidNativeStandard1"})
        self.assertEqual(selected, dict(full, variants=[full["variants"][1]]))

    def test_family_order_ui_engine_axes_deferred_water_and_resource_filter(self):
        records = []
        for keys in ([], ["UNITY_UI_CLIP_RECT"], ["UNITY_UI_ALPHACLIP"], ["UNITY_UI_ALPHACLIP", "UNITY_UI_CLIP_RECT"]):
            for stage in ("progVertex", "progFragment"):
                records.append(program(len(records), stage, keys))
        sources = {
            "water": context("Water Fixture", ["_DISPLACEMENTMODE_FIXTURE"], passes=2),
            "ui-alpha": context("UI Fixture", ["UNITY_UI_CLIP_RECT", "UNITY_UI_ALPHACLIP", "FOG_EXP"], records),
        }
        rows = [("Assets/Water", "Water Fixture", "_DISPLACEMENTMODE_FIXTURE"), ("Assets/UI", "UI Fixture", "UNITY_UI_CLIP_RECT,FOG_EXP")]
        result = M.family_manifest(sources, rows)
        self.assertEqual([r["shader"] for r in result["families"]], ["Water Fixture", "UI Fixture"])
        self.assertEqual(result["families"][0]["variants"], [])
        self.assertEqual(
            result["families"][1],
            {"shader": "UI Fixture", "features": [], "variants": [{"resource": "AndroidNativeFamily1Variant0", "keywords": []}], "source_material_count": 1},
        )
        deferred = result["deferred_variants"]
        self.assertEqual(len(deferred), 1)
        self.assertEqual(deferred[0]["materials"], ["Assets/Water"])
        self.assertEqual(deferred[0]["reason"], "Displacement requires deferred original tessellation/PC draw evidence")
        selected = M.family_manifest(sources, rows, resources={"AndroidNativeFamily1Variant0"})
        self.assertEqual(selected["families"], result["families"])
        self.assertEqual(selected["deferred_variants"], [])

    def test_missing_pair_defers_but_ambiguous_source_never_becomes_a_fallback(self):
        source = context("UI Fixture")
        rows = [("Assets/UI", "UI Fixture", "")]
        result = M.family_manifest({"ui-alpha": source}, rows)
        self.assertEqual(result["families"][0]["variants"], [])
        self.assertEqual(json.loads(result["deferred_variants"][0]["reason"].split(": ", 1)[1])["stage"], "progVertex")
        source[2].extend([program(1, "progVertex"), program(2, "progVertex")])
        with self.assertRaisesRegex(RuntimeError, "ambiguous") as error:
            M.family_manifest({"ui-alpha": source}, rows)
        self.assertNotIsInstance(error.exception, M.NativeVariantUnavailable)


class ShaderMetadataTests(unittest.TestCase):
    def test_restores_tags_without_changing_placeholder_body(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            path = work / "lab-project" / "Fixture.shader"
            path.parent.mkdir()
            evidence = work / "evidence"
            evidence.mkdir()
            original = 'Shader "Fixture" {\nSubShader {\nTags {"Queue"="Geometry"}\nPass { /* fixture program */ }\n}\n}\n'
            path.write_text(original)
            tree = {"m_ParsedForm": {"m_Name": "Fixture", "m_SubShaders": [{"m_Tags": {"tags": [("QUEUE", "AlphaTest")]}}]}}
            with patch.object(shader_materials, "WORK", work):
                receipt = shader_materials.align_exported_subshader_tags(path, tree, evidence)
            self.assertIn('"QUEUE"="AlphaTest"', path.read_text())
            self.assertEqual(original.split("Pass {")[1], path.read_text().split("Pass {")[1])
            self.assertEqual(original, next(evidence.glob("prior-tags-*.shader")).read_text())
            self.assertNotEqual(receipt["before_sha256"], receipt["after_sha256"])

    def test_refuses_file_outside_owned_project(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = work / "original.shader"
            source.write_text("original input")
            with patch.object(shader_materials, "WORK", work):
                with self.assertRaisesRegex(RuntimeError, "owned ignored copies"):
                    shader_materials.align_exported_subshader_tags(source, {}, work / "evidence")
            self.assertEqual(source.read_text(), "original input")
