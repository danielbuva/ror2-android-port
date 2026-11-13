"""Execute projectile registration with and without sparse startup observation."""

from pathlib import Path
import unittest

from test_native_commerce_release_order import braced_block
from test_retained_catalog_dependencies import execute_host

ROOT = Path(__file__).resolve().parents[1]


class ProjectileCatalogAttributionTests(unittest.TestCase):
    def test_observation_preserves_native_order_identity_and_restoration(self):
        source = (ROOT / "tools/unity/runtime/catalog/WholeCatalogComposed.cs").read_text()
        methods = [
            braced_block(source, signature)
            for signature in (
                "public static int PrepareProjectiles()",
                "internal static int PrepareProjectiles(JObject manifest)",
                "internal static int PrepareProjectiles(JObject manifest, Action<string> trace)",
                "public static void RestoreProjectiles()",
            )
        ]
        host = (ROOT / "tests/fixtures/projectile_catalog_attribution_host.cs").read_text()
        host += "\npublic static partial class WholeCatalogComposed {\n" + "\n".join(methods) + "\n}\n"
        result = execute_host(host, "projectiles")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "projectile observation native order identity restoration PASS")


if __name__ == "__main__":
    unittest.main()
