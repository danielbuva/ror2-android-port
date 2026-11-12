"""Compile the actual catalog methods and exercise scoped source snapshots."""

from pathlib import Path
import unittest

from test_native_commerce_release_order import braced_block
from test_retained_catalog_dependencies import execute_host

ROOT = Path(__file__).resolve().parents[1]


class ScopedDefinitionManifestTests(unittest.TestCase):
    def test_artifacts_holders_drones_and_projectiles_share_one_snapshot(self):
        source = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text()
        start = source.index('TraceStartup("artifact-family-begin");')
        end = source.index('TraceStartup("skins-begin");', start)
        host = (ROOT / "tests/fixtures/artifact_holder_scope_host.cs").read_text()
        host += "\npublic static partial class PortSession { static void Prepare() {\n" + source[start:end] + "\n} }\n"
        result = execute_host(host, "scope")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "artifact holder drone projectile snapshot order identity PASS")

    def test_game_modes_keep_native_order_snapshot_and_cleanup(self):
        source = (ROOT / "tools/unity/runtime/stage/TeleporterWorldBoundary.cs").read_text()
        bridges = [braced_block(source, "void " + name + "(JObject manifest = null)") for name in ("PrepareObjectiveRuleCatalog", "PrepareOriginalGameModes")]
        methods = [
            braced_block(source, signature)
            for signature in (
                "public void PrepareObjectiveRuleCatalog(JObject manifest = null)",
                "public void PrepareOriginalGameModes(JObject manifest = null)",
                "public void CleanupOriginalGameModes()",
            )
        ]
        host = (ROOT / "tests/fixtures/game_mode_manifest_scope_host.cs").read_text()
        host += "\npublic partial class PortSession {\n" + "\n".join(bridges)
        host += "\nsealed partial class TeleporterWorldSession {\n" + "\n".join(methods) + "\n} }\n"
        result = execute_host(host, "scope")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "game-mode snapshot native order identity restoration PASS")

    def test_related_families_share_snapshot_and_keep_identity_checks(self):
        source = (ROOT / "tools/unity/runtime/catalog/WholeCatalogComposed.cs").read_text()
        methods = [
            braced_block(source, signature)
            for signature in (
                "sealed class DefinitionManifestIndex",
                "static DefinitionManifestIndex IndexDefinitionManifest(JObject manifest)",
                "public static RoR2.BuffDef[] BuffDefinitions()",
                "public static RoR2.ItemDef[] ItemDefinitions()",
                "public static RoR2.KeyItemDef[] KeyItemDefinitions()",
                "public static RoR2.ItemGroupType[] ItemGroupTypes()",
                "public static RoR2.ItemGroupProvider[] ItemGroupProviders()",
                "public static T[] DefinitionFamily<T>(System.Collections.Generic.IEnumerable<T> selected)",
                "public static int[][] FamilyLocationGroups(JObject manifest, string category)",
                "public static T[] CategoryFamily<T>(string category, IEnumerable<T> selected)",
                "internal static JObject ReadDefinitionManifest()",
                "internal static void ResetDefinitionManifest()",
                "internal static T[] CategoryFamily<T>(JObject manifest, string category, IEnumerable<T> selected)",
                "internal static T[] CategoryFamily<T>(JObject manifest, string category, IEnumerable<T> selected, Action<string> trace)",
                'public static void PopulateDefinitionFields<T>(string family, T[] definitions, string prefix = "")',
                'internal static void PopulateDefinitionFields<T>(JObject manifest, string family, T[] definitions, string prefix = "")',
                "public static void PopulateBodyFields(GameObject[] prefabs)",
                "internal static void PopulateBodyFields(JObject manifest, GameObject[] prefabs)",
            )
        ]
        host = (ROOT / "tests/fixtures/scoped_definition_manifest_host.cs").read_text()
        host += "\npublic static partial class WholeCatalogComposed {\n" + "\n".join(methods) + "\n}\n"
        profile = (ROOT / "tools/unity/runtime/progression/AndroidProfileBoundary.cs").read_text()
        calls = []
        for label in ("survivorDef", "unlockableDef"):
            start = profile.index("WholeCatalogComposed.CategoryFamily(manifest, RoR2.ContentManagement.AddressablesLabels." + label)
            end = profile.index(";", start)
            calls.append(profile[start : end - 1] if label == "unlockableDef" else profile[start:end])
        host += "\npublic partial class ProfileScope {\n" + braced_block(profile, "void PrepareAndroidProfile(CharacterBody player, JObject manifest)")
        rule_call = profile[profile.index("coordinator.PrepareObjectiveRuleCatalog(manifest);") :].splitlines()[0]
        host += (
            "\nvoid Prepare(CharacterBody player, JObject manifest) { survivors = " + calls[0] + "; unlockables = " + calls[1] + "; " + rule_call + " }\n}\n"
        )
        result = execute_host(host, "scope")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "scope identity policy restoration buffs items PASS")


if __name__ == "__main__":
    unittest.main()
