from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
OWNER = REPO / "tools/unity/runtime/input/AndroidNativeSourceSkinLifecycle.cs"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


def extract_block(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start : offset + 1]
    raise AssertionError(f"unterminated production block: {signature}")


def harness(model_decl: str) -> str:
    source = OWNER.read_text(encoding="utf-8")
    renderer = extract_block(source, "    public sealed class SceneCameraCallbackRendererSample")
    snapshot = extract_block(source, "    public sealed class SceneCameraCallbackSnapshot")
    method = extract_block(source, "    void CaptureCharacterModelMaterialState(")
    return f"""using System;
using System.Reflection;
using UnityEngine;
using RoR2;

namespace UnityEngine {{ public sealed class Material {{ }} }}
namespace RoR2 {{ {model_decl} }}

public sealed class ProductionProbe
{{
    CharacterModel model;
    {renderer}
    {snapshot}
    public ProductionProbe(CharacterModel value) {{ model = value; }}
    {method}
    public SceneCameraCallbackSnapshot Capture()
    {{ var result = new SceneCameraCallbackSnapshot(); CaptureCharacterModelMaterialState(result); return result; }}
}}

public static class Assertions
{{
    static int checks;
    static void Check(bool ok, string message) {{ checks++; if (!ok) throw new Exception(message); }}
    static void Run()
    {{
        var cacheField = typeof(CharacterModel).GetField("sharedMaterialArrays", BindingFlags.NonPublic | BindingFlags.Static);
        var value = new CharacterModel();
        var probe = new ProductionProbe(value);
        if (cacheField == null || cacheField.FieldType != typeof(Material[][]))
        {{
            var refused = probe.Capture();
            Check(!refused.sharedMaterialCacheKnown, "invalid cache field reported known");
            Check(!string.IsNullOrEmpty(refused.materialObservationError), "invalid cache field had no reason");
        }}
        else
        {{
            cacheField.SetValue(null, new Material[][] {{ new Material[0], new Material[1], null, new Material[3] }});
            var bounded = probe.Capture();
            Check(bounded.sharedMaterialCacheKnown && !bounded.sharedMaterialCacheIsNull, "valid cache not observed");
            Check(bounded.sharedMaterialCacheOuterLength == 4 && bounded.sharedMaterialCacheBucketsComplete, "complete cache shape lost");
            Check(bounded.sharedMaterialCacheBucketsScanned == 4 && bounded.sharedMaterialCacheNullBucketCount == 1, "bucket counts wrong");
            Check(string.Join(",", bounded.sharedMaterialCacheBucketLengths) == "0,1,-1,3", "bucket length encoding wrong");
            Check(bounded.materialDirtyKnown && bounded.materialDirty, "dirty getter not observed");

            cacheField.SetValue(null, null);
            var missing = probe.Capture();
            Check(missing.sharedMaterialCacheKnown && missing.sharedMaterialCacheIsNull, "null cache was not distinguished");
            Check(missing.sharedMaterialCacheOuterLength == -1 && missing.sharedMaterialCacheBucketLengths == null, "null cache fabricated a shape");

            var longCache = new Material[20][];
            for (int i = 0; i < longCache.Length; i++) longCache[i] = new Material[i];
            cacheField.SetValue(null, longCache);
            var truncated = probe.Capture();
            Check(truncated.sharedMaterialCacheOuterLength == 20 && truncated.sharedMaterialCacheBucketsScanned == 16, "scan bound not enforced");
            Check(!truncated.sharedMaterialCacheBucketsComplete && truncated.sharedMaterialCacheBucketLengths.Length == 16, "truncation not explicit");
        }}
        value.ThrowDirty = true;
        var dirtyFailure = probe.Capture();
        Check(!dirtyFailure.materialDirtyKnown, "throwing dirty read was marked known");
        Check(!string.IsNullOrEmpty(dirtyFailure.materialObservationError), "dirty read failure not reported");
        Console.WriteLine("PASS " + checks);
    }}
    public static int Main() {{ Run(); return 0; }}
}}
"""


class MaterialCacheObservationTests(unittest.TestCase):
    def test_exact_production_observer_is_bounded_and_unknown_safe(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn host compiler unavailable")
        variants = {
            "valid": 'public sealed class CharacterModel { private static UnityEngine.Material[][] sharedMaterialArrays; public static bool operator !(CharacterModel value) { return value == null; } public bool ThrowDirty; public bool GetMaterialsDirty() { if (ThrowDirty) throw new InvalidOperationException("getter failed"); return true; } }',
            "missing": 'public sealed class CharacterModel { public static bool operator !(CharacterModel value) { return value == null; } public bool ThrowDirty; public bool GetMaterialsDirty() { if (ThrowDirty) throw new InvalidOperationException("getter failed"); return true; } }',
            "wrong": 'public sealed class CharacterModel { private static UnityEngine.Material[] sharedMaterialArrays; public static bool operator !(CharacterModel value) { return value == null; } public bool ThrowDirty; public bool GetMaterialsDirty() { if (ThrowDirty) throw new InvalidOperationException("getter failed"); return true; } }',
        }
        for name, declaration in variants.items():
            with self.subTest(variant=name), tempfile.TemporaryDirectory(prefix="camera-material-observation-") as tmp:
                directory = Path(tmp)
                source = directory / "ExtractedProductionObserver.cs"
                executable = directory / "observer.exe"
                source.write_text(harness(declaration), encoding="utf-8")
                compiled = subprocess.run(
                    [str(MONO), str(CSC), "-nologo", "-langversion:latest", "-target:exe", f"-out:{executable}", str(source)],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                ran = subprocess.run([str(MONO), str(executable)], cwd=directory, capture_output=True, text=True)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                self.assertIn("PASS", ran.stdout)

    def test_observer_does_not_mutate_or_retain_source_materials(self):
        source = OWNER.read_text(encoding="utf-8")
        method = extract_block(source, "    void CaptureCharacterModelMaterialState(")
        self.assertNotIn("SetValue(", method)
        self.assertNotIn("sharedMaterials =", method)
        self.assertNotIn("renderer.", method)
        self.assertIn('GetField("sharedMaterialArrays"', method)
        self.assertIn("cacheField.FieldType != typeof(Material[][])", method)
        self.assertIn("const int maxBuckets = 16", method)
        self.assertIn("model.GetMaterialsDirty()", method)
        self.assertNotIn("exceptionObserved", method)


if __name__ == "__main__":
    unittest.main()
