import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs"
UNITY = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def extract_method(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise AssertionError(f"Unclosed production method: {declaration}")


class ToolbotSkillFamilyNameShadowTests(unittest.TestCase):
    def test_production_identity_and_refusal_with_shadowed_family_name(self):
        mono = UNITY / "bin/mono"
        compiler = UNITY / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.exists() or not compiler.exists():
            self.skipTest("matching Unity Mono compiler is unavailable")

        source = SOURCE.read_text()
        capture = extract_method(source, "    void CaptureToolbotOffhandIdentity()")
        describe = extract_method(source, "    string DescribeToolbotComponent(int componentIndex)")
        matches = extract_method(source, "    bool ToolbotSelectedComponentMatches(int componentIndex,")

        host = r'''using System;
using UnityEngine;
namespace UnityEngine {
 public class Object { public static implicit operator bool(Object value) => value != null; }
 public class ScriptableObject : Object { public string name { get; set; } }
}
public sealed class SkillFamily : UnityEngine.ScriptableObject {
 public new string name => null;
 public int catalogIndex;
}
public sealed class SkillDef : UnityEngine.ScriptableObject { public int skillIndex; }
public sealed class GenericSkill : UnityEngine.Object {
 public SkillFamily skillFamily; public SkillDef skillDef; public string skillName;
}
public sealed class VariantRow { public int skillCatalogIndex; public string skillName; }
public sealed class ComponentRow {
 public int componentIndex, familyCatalogIndex, selectedLoadoutVariantIndex;
 public int selectedLoadoutSkillCatalogIndex, runtimeSkillCatalogIndex;
 public string runtimeDefinitionStatus; public VariantRow[] variants;
}
public sealed class InventoryRow { public string status; public int bodyIndex; public ComponentRow[] components; }
public sealed class ObserverReport { public InventoryRow skillVariantInventory; }
public sealed class Locator { public GenericSkill primary, secondary, special; }
public sealed class CharacterBody : UnityEngine.Object {
 public int bodyIndex; public GenericSkill[] skills; public Locator skillLocator;
 public T[] GetComponents<T>() => (T[])(object)skills;
}
public sealed class Result { public int toolbotOffhandPhase; public string toolbotOffhandOutcome; }
public static class BodyCatalog { public static int FindBodyIndex(string name) => 258; }
public static class SkillCatalog {
 public static SkillDef[] defs = new SkillDef[256];
 public static SkillDef GetSkillDef(int index) => index >= 0 && index < defs.Length ? defs[index] : null;
}
public sealed class SurvivorSkillInputCoverage {
 public ObserverReport observed; public object combatOutput; public CharacterBody body;
 public GenericSkill[] toolbotSkillComponents; public float toolbotDeadline, toolbotPhaseEnteredAt;
 public Result report = new Result();
''' + capture + "\n" + describe + "\n" + matches + r'''
 public static SurvivorSkillInputCoverage Make() {
  var c = new SurvivorSkillInputCoverage { combatOutput = new object() };
  c.body = new CharacterBody { bodyIndex = 258, skillLocator = new Locator() };
  c.observed = new ObserverReport { skillVariantInventory = new InventoryRow {
   status = "available", bodyIndex = 258, components = new ComponentRow[5] } };
  c.body.skills = new GenericSkill[5];
  int[] families = {141, 142, 143, 143, 144};
  int[] variants = {0, 3, 0, 0, 1};
  int[] skills = {195, 193, 192, 192, 201};
  string[] familyNames = {"ToolbotBodyPrimary1", "ToolbotBodyPrimary2", "ToolbotBodySecondary", "ToolbotBodyUtility", "ToolbotBodySpecialFamily"};
  string[] skillNames = {"ToolbotBodyFireNailgun", "ToolbotBodyFireBuzzsaw", "ToolbotBodyFireSpear", "ToolbotBodyFireSpear", "ToolbotDualWield"};
  string[] serializedNames = {"FireNailgun", "FireSpear", "FireSpear", "FireSpear", "Swap"};
  for (int i = 0; i < 5; i++) {
   var family = new SkillFamily { catalogIndex = families[i] };
   ((UnityEngine.ScriptableObject)family).name = familyNames[i];
   var definition = new SkillDef { name = skillNames[i], skillIndex = skills[i] };
   SkillCatalog.defs[skills[i]] = definition;
   c.body.skills[i] = new GenericSkill { skillFamily = family, skillDef = definition, skillName = serializedNames[i] };
   var variantRows = new VariantRow[variants[i] + 1];
   variantRows[variants[i]] = new VariantRow { skillCatalogIndex = skills[i], skillName = skillNames[i] };
   c.observed.skillVariantInventory.components[i] = new ComponentRow {
    componentIndex = i, familyCatalogIndex = families[i], selectedLoadoutVariantIndex = variants[i],
    selectedLoadoutSkillCatalogIndex = skills[i], runtimeSkillCatalogIndex = skills[i],
    runtimeDefinitionStatus = "matches-selected-native-loadout", variants = variantRows
   };
  }
  c.body.skillLocator.primary = c.body.skills[0];
  c.body.skillLocator.secondary = c.body.skills[2];
  c.body.skillLocator.special = c.body.skills[4];
  return c;
 }
 static void Check(bool condition, string label) { if (!condition) throw new Exception(label); }
 static void Refuse(Action action, string label) {
  try { action(); }
  catch (ArgumentException e) {
   Check(e.Message.StartsWith("Toolbot offhand selected-identity refusal:", StringComparison.Ordinal), label + " wrong refusal: " + e.Message);
   return;
  }
  throw new Exception(label + " was accepted");
 }
 public static void Main() {
  var good = Make();
  Check(good.body.skills[1].skillFamily.name == null, "fixture must reproduce the hidden null getter");
  Check(((ScriptableObject)good.body.skills[1].skillFamily).name == "ToolbotBodyPrimary2", "base ScriptableObject name");
  good.CaptureToolbotOffhandIdentity();
  Check(good.report.toolbotOffhandOutcome == "waiting-for-owned-live-diagnostic-input", "valid selection accepted");
  var detail = good.DescribeToolbotComponent(1);
  Check(detail.Contains("genericSkillName=FireSpear"), "serialized GenericSkill label preserved");
  Check(detail.Contains("familyName=ToolbotBodyPrimary2"), "family diagnostic uses base name");
  Check(detail.Contains("skillDefName=ToolbotBodyFireBuzzsaw"), "SkillDef name remains distinct");

  Action<Action<SurvivorSkillInputCoverage>, string> mutation = (change, label) => {
   var c = Make(); change(c); Refuse(c.CaptureToolbotOffhandIdentity, label);
  };
  mutation(c => ((ScriptableObject)c.body.skills[1].skillFamily).name = "WrongFamily", "family name");
  mutation(c => c.observed.skillVariantInventory.components[1].componentIndex++, "component tuple");
  mutation(c => c.observed.skillVariantInventory.components[1].familyCatalogIndex++, "family catalog tuple");
  mutation(c => c.observed.skillVariantInventory.components[1].selectedLoadoutVariantIndex++, "selected variant tuple");
  mutation(c => c.observed.skillVariantInventory.components[1].selectedLoadoutVariantIndex = 4, "variant bounds");
  mutation(c => c.observed.skillVariantInventory.components[1].selectedLoadoutSkillCatalogIndex++, "selected SkillDef index");
  mutation(c => c.observed.skillVariantInventory.components[1].runtimeSkillCatalogIndex++, "runtime SkillDef index");
  mutation(c => c.observed.skillVariantInventory.components[1].runtimeDefinitionStatus = "differs-from-selected-native-loadout", "runtime definition status");
  mutation(c => c.observed.skillVariantInventory.components[1].variants = null, "variant tuple absent");
  mutation(c => c.observed.skillVariantInventory.components[1].variants = new VariantRow[0], "variant array bounds");
  mutation(c => c.observed.skillVariantInventory.components[1].variants[3] = null, "variant tuple null");
  mutation(c => c.observed.skillVariantInventory.components[1].variants[3].skillCatalogIndex++, "variant catalog index");
  mutation(c => c.observed.skillVariantInventory.components[1].variants[3].skillName = "WrongSkill", "variant name tuple");
  mutation(c => SkillCatalog.defs[193].name = "WrongDefinition", "catalog SkillDef identity");
  mutation(c => SkillCatalog.defs[193] = null, "catalog SkillDef missing");
  Console.WriteLine("Toolbot family-name shadow, selected identity and refusal passed");
 }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "ToolbotFamilyNameHost.cs"
            output_path = Path(directory) / "ToolbotFamilyNameHost.exe"
            source_path.write_text(host)
            compiled = subprocess.run(
                [str(mono), str(compiler), "-nologo", "-langversion:9", "-out:" + str(output_path), str(source_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output_path)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("Toolbot family-name shadow, selected identity and refusal passed", executed.stdout)


if __name__ == "__main__":
    unittest.main()
