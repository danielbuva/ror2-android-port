"""Portable source contract and execution of the production catalog-name helper."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TASK = Path(__file__).resolve().parents[1]
OBSERVER = TASK / "tools/unity/runtime/world/SurvivorCombatOutputObserver.cs"
FIXTURE = TASK / "tools/catalog/SurvivorCombatOutputObserverFixture.cs"


def method(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unbalanced method: {signature}")


def production_helper_source():
    source = OBSERVER.read_text()
    return method(source, "static string NativeBodyCatalogNameForFact(BodyIndex bodyIndex)")


class SurvivorDamageCatalogNames(unittest.TestCase):
    def test_native_names_are_sampled_only_when_damage_fact_is_created(self):
        source = OBSERVER.read_text()
        on_damage = method(source, "void OnServerDamageDealt(DamageReport damage)")
        self.assertIn("public string attackerBodyCatalogName, victimBodyCatalogName;", source)
        self.assertEqual(on_damage.count("NativeBodyCatalogNameForFact("), 2)
        self.assertRegex(on_damage, r"attackerBodyCatalogName\s*=\s*NativeBodyCatalogNameForFact\(")
        self.assertRegex(on_damage, r"victimBodyCatalogName\s*=\s*NativeBodyCatalogNameForFact\(")
        self.assertEqual(source.count("NativeBodyCatalogNameForFact("), 3)
        self.assertIn("public const int DamageHistoryCapacity = 32;", source)

    def test_exact_editor_fixture_handles_empty_catalog_and_checks_native_api(self):
        fixture = method(FIXTURE.read_text(), "public static object RunBodyCatalogNameContract()")
        self.assertIn('"GetBodyName"', fixture)
        self.assertIn("BodyIndex.None", fixture)
        self.assertIn("positiveLookupObserved = positiveLookupObserved", fixture)
        self.assertIn("for (int i = 0; i < BodyCatalog.bodyCount; i++)", fixture)
        self.assertNotIn("Require(knownIndex != BodyIndex.None", fixture)

    @unittest.skipUnless(
        Path(
            os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"),
            "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe",
        ).exists()
        and Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"), "MonoBleedingEdge/bin/mono").exists(),
        "pinned Unity Mono compiler/runtime unavailable",
    )
    def test_extracted_production_helper_against_authored_catalog_double(self):
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        runtime = editor / "MonoBleedingEdge/bin/mono"
        stubs = r"""using System;
public enum BodyIndex { None = -1, Known = 0, Missing = 1, NullEntry = 2 }
public static class BodyCatalog
{
    public static string[] bodyNames = { "NativeBodyName", null, null };
    public static int lookups;
    public static string GetBodyName(BodyIndex bodyIndex)
    {
        lookups++;
        int index = (int)bodyIndex;
        return index < 0 || index >= bodyNames.Length ? null : bodyNames[index];
    }
}
"""
        harness = r"""using System;
public static class Program
{
    static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    public static void Main()
    {
        Require(SurvivorCombatOutputObserver.NativeBodyCatalogNameForFact(BodyIndex.None) == string.Empty,
                "None must be empty");
        Require(BodyCatalog.lookups == 0, "None must not query BodyCatalog");
        var nativeName = BodyCatalog.bodyNames[0];
        var known = SurvivorCombatOutputObserver.NativeBodyCatalogNameForFact(BodyIndex.Known);
        Require(object.ReferenceEquals(known, nativeName), "known name must be the native cached string");
        Require(SurvivorCombatOutputObserver.NativeBodyCatalogNameForFact(BodyIndex.Missing) == string.Empty,
                "out-of-range/null lookup must be empty");
        Require(SurvivorCombatOutputObserver.NativeBodyCatalogNameForFact(BodyIndex.NullEntry) == string.Empty,
                "null catalog entry must be empty");
        Require(SurvivorCombatOutputObserver.NativeBodyCatalogNameForFact((BodyIndex)99) == string.Empty,
                "out-of-range catalog index must be empty");
        Console.WriteLine("production catalog-name helper passed");
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="survivor-damage-catalog-names-", dir=None) as temp:
            root = Path(temp)
            helper = root / "ProductionHelper.cs"
            program = root / "Harness.cs"
            executable = root / "catalog-name-tests.exe"
            extracted = production_helper_source().replace(
                "static string NativeBodyCatalogNameForFact(", "public static string NativeBodyCatalogNameForFact(", 1
            )
            helper.write_text(stubs + "\npublic static class SurvivorCombatOutputObserver\n{\n" + extracted + "\n}\n")
            program.write_text(harness)
            compiled = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-out:" + str(executable), str(helper), str(program)],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout)
            result = subprocess.run([str(runtime), str(executable)], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("production catalog-name helper passed", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
