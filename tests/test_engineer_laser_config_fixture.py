"""Exercise inert config fixture failure detection with authored synthetic fields."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/catalog/FirstStageDiagnosticGateFixture.cs"
MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono")
CSC = MONO.parent.parent / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


def method(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 0
    for end in range(opening, len(text)):
        depth += (text[end] == "{") - (text[end] == "}")
        if depth == 0:
            return text[start : end + 1]
    raise AssertionError(signature)


class EngineerConfigFixtureTests(unittest.TestCase):
    def test_inherited_binding_failure_sentinels_and_deferred_identity(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")
        text = SOURCE.read_text().split("namespace EngineerConfigFixture", 1)[1]
        helpers = "\n".join(
            method(text, signature) for signature in ("static void Require(", "static bool SameValue(", "static object Sentinel(", "static int ApplyAndCheck(")
        )
        program = r"""
using System;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using UnityEngine;
namespace UnityEngine {
    public class Object { }
    public class SerializeField : Attribute { }
    public class AnimationCurve { public int preWrapMode, postWrapMode; public int[] keys = new int[0]; }
}
class Address { public string AssetGUID; }
class EntityStateGameObject {
    public UnityEngine.Object directReference;
    public Address addressableReference;
    public static implicit operator bool(EntityStateGameObject _) { throw new Exception("unexpected Addressables load"); }
}
struct SerializedValue {
    public object value;
    public object GetValue(FieldInfo _) { return value; }
}
struct SerializedField { public string fieldName; public SerializedValue fieldValue; }
struct Fields { public SerializedField[] serializedFields; }
class EntityStateConfiguration {
    public Type targetType;
    public Fields serializedFieldsCollection;
    public bool omitInstanceWrite, omitStaticWrite;
    public void ApplyStatic() {
        foreach (var item in serializedFieldsCollection.serializedFields) {
            var field = targetType.GetField(item.fieldName);
            if (field != null && field.IsStatic && !omitStaticWrite) field.SetValue(null, item.fieldValue.value);
        }
    }
    public Action<object> BuildInstanceInitializer() {
        var fields = serializedFieldsCollection.serializedFields.Where(s => {
            var f = targetType.GetField(s.fieldName);
            return f != null && !f.IsStatic && f.GetCustomAttribute<SerializeField>() != null;
        }).ToArray();
        if (fields.Length == 0) return null;
        return obj => {
            if (!omitInstanceWrite)
                foreach (var item in fields) targetType.GetField(item.fieldName).SetValue(obj, item.fieldValue.value);
        };
    }
}
class BasePhase { [SerializeField] public float inherited; public float notSerialized; }
class NextPhase : BasePhase { [SerializeField] public EntityStateGameObject reference; public static float shared; }
class Test {
    HELPERS
    static SerializedField Field(string name, object value) {
        return new SerializedField { fieldName = name, fieldValue = new SerializedValue { value = value } };
    }
    static void Reject(Action action, string message) {
        try { action(); } catch (InvalidOperationException e) { if (e.Message.Contains(message)) return; throw; }
        throw new Exception("fixture falsely passed " + message);
    }
    static int Main() {
        var reference = new EntityStateGameObject { addressableReference = new Address { AssetGUID = "synthetic" } };
        var config = new EntityStateConfiguration { targetType = typeof(NextPhase), serializedFieldsCollection = new Fields {
            serializedFields = new[] { Field("inherited", 2f), Field("reference", reference), Field("shared", 3f) } } };
        var phase = new NextPhase();
        Require(ApplyAndCheck(config, phase) == 3 && phase.inherited == 2f && NextPhase.shared == 3f,
                "inherited instance and static config did not apply");
        // Start with configured values: a swallowed/no-op initializer must still fail.
        config.omitInstanceWrite = true;
        Reject(() => ApplyAndCheck(config, phase), "did not replace sentinel");
        config.omitInstanceWrite = false; config.omitStaticWrite = true;
        Reject(() => ApplyAndCheck(config, phase), "did not replace sentinel");
        config.omitStaticWrite = false;
        config.serializedFieldsCollection.serializedFields = new[] { Field("inherited", 2f), Field("inherited", 2f) };
        Reject(() => ApplyAndCheck(config, phase), "Duplicate");
        config.serializedFieldsCollection.serializedFields = new[] { Field("notSerialized", 2f) };
        Reject(() => ApplyAndCheck(config, phase), "not serialized");
        config.serializedFieldsCollection.serializedFields = new[] { Field("absent", 2f) };
        Reject(() => ApplyAndCheck(config, phase), "missing");
        Require(SameValue(reference, new EntityStateGameObject { addressableReference = new Address { AssetGUID = "synthetic" } }),
                "deferred identity comparison");
        Require(!SameValue(reference, new EntityStateGameObject { addressableReference = new Address { AssetGUID = "other" } }),
                "changed deferred identity accepted");
        Require(!SameValue(reference, new EntityStateGameObject { addressableReference = reference.addressableReference,
                directReference = new UnityEngine.Object() }), "direct-reference bypass accepted");
        var a = new AnimationCurve { keys = new[] { 1, 2 }, preWrapMode = 3 };
        var b = new AnimationCurve { keys = new[] { 1, 2 }, preWrapMode = 3 };
        Require(SameValue(a, b), "curve values"); b.keys[1] = 9;
        Require(!SameValue(a, b), "changed curve accepted");
        Console.WriteLine("Engineer config fixture failure detection passed"); return 0;
    }
}
""".replace("HELPERS", helpers)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "ConfigFixture.cs"
            output = Path(tmp) / "ConfigFixture.exe"
            source.write_text(program)
            compiled = subprocess.run([str(MONO), str(CSC), "-nologo", f"-out:{output}", str(source)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(MONO), str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("failure detection passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
