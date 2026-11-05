"""Compile the actual catalog methods and exercise scoped source snapshots."""

from pathlib import Path
import unittest

from test_native_commerce_release_order import braced_block
from test_retained_catalog_dependencies import execute_host

ROOT = Path(__file__).resolve().parents[1]


class ScopedDefinitionManifestTests(unittest.TestCase):
    def test_artifact_registration_and_holders_share_one_snapshot(self):
        source = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text()
        start = source.index('TraceStartup("artifact-family-begin");')
        end = source.index('TraceStartup("drone-catalog-begin");', start)
        host = (ROOT / "tests/fixtures/artifact_holder_scope_host.cs").read_text()
        host += "\npublic static partial class PortSession { static void Prepare() {\n" + source[start:end] + "\n} }\n"
        result = execute_host(host, "scope")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "artifact holder snapshot order identity PASS")

    def test_related_families_share_snapshot_and_keep_identity_checks(self):
        source = (ROOT / "tools/unity/runtime/catalog/WholeCatalogComposed.cs").read_text()
        methods = [
            braced_block(source, signature)
            for signature in (
                "public static RoR2.BuffDef[] BuffDefinitions()",
                "public static RoR2.ItemDef[] ItemDefinitions()",
                "public static T[] DefinitionFamily<T>(System.Collections.Generic.IEnumerable<T> selected)",
                "public static int[][] FamilyLocationGroups(JObject manifest, string category)",
                "public static T[] CategoryFamily<T>(string category, IEnumerable<T> selected)",
                "internal static JObject ReadDefinitionManifest()",
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
        result = execute_host(host, "scope")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "scope identity policy restoration buffs items PASS")


if __name__ == "__main__":
    unittest.main()
