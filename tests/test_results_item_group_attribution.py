"""Execute the item-group owner with sparse observation and native-style peers."""

from pathlib import Path
import unittest

from test_native_commerce_release_order import braced_block
from test_retained_catalog_dependencies import execute_host

ROOT = Path(__file__).resolve().parents[1]


class ResultsItemGroupAttributionTests(unittest.TestCase):
    def test_order_identity_null_members_and_cleanup(self):
        source = (ROOT / "tools/unity/runtime/progression/IntegratedResultsBoundary.cs").read_text()
        methods = "\n".join(braced_block(source, signature) for signature in ("void PrepareResultsItemGroups()", "void CleanupResultsItemGroups()"))
        host = (ROOT / "tests/fixtures/results_item_group_attribution_host.cs").read_text()
        result = execute_host(host.replace("// OWNER_METHODS", methods), "itemgroups")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "item-group attribution order identity cleanup PASS")


if __name__ == "__main__":
    unittest.main()
