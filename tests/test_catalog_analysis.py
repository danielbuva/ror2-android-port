"""R2–R4's host catalog analysis inside the destination (J725); no game data is read."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import catalog_analysis
from common import read, write

INPUT = "a" * 64


class CatalogAnalysisTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / "work"
        self.dest = self.root / "destination"
        self.recipe = self.root / "recipe"
        write(self.recipe / "catalog-typed-corrections.json", dict(schema=1, input_id=INPUT, catalog_sha256="c" * 64, conversions={"7": dict(source="Assets/A.mat")}))
        patcher = patch.object(catalog_analysis, "RECIPE", self.recipe)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def fake_chain(self, closure_catalog="c" * 64, inspected=True):
        import whole_catalog

        def audit_into(out, work):
            self.calls.append("audit")
            for name in ("original-catalog-contract.json", "source-guid-index.json", "source-guid-repairs.json"):
                write(out / name, {})
            (out / "source-catalog.json").write_text("{}")
            write(out / "host-closure.json", dict(source_catalog_sha256=closure_catalog))

        def native_inventory_into(out, destination, work):
            self.calls.append("native")
            self.assertEqual(destination, out / "native-containers")
            return dict(success=inspected, bundles=[], errors=[])

        def reconcile_into(out, native, work):
            self.calls.append("reconcile")
            receipt = read(out / "typed-import-conversions.json")
            self.assertEqual(receipt["conversions"], {"7": dict(source="Assets/A.mat")})
            write(out / "native-conversions.json", {})
            write(out / "reconciled-closure.json", {})
            return {}, {}

        return patch.multiple(whole_catalog, audit_into=audit_into, native_inventory_into=native_inventory_into, reconcile_into=reconcile_into)

    def test_runs_the_live_chain_once_and_keeps_integration_attempts(self):
        attempt = self.dest / ".rebuild/catalog-inputs/integration-x/manifest.json"
        write(attempt, {})
        with self.fake_chain():
            out = catalog_analysis.ensure(self.work, self.dest, INPUT)
            catalog_analysis.ensure(self.work, self.dest, INPUT)
        self.assertEqual(self.calls, ["audit", "native", "reconcile"])
        self.assertTrue(attempt.is_file())
        self.assertEqual(set(read(out / "analysis-complete.json")["outputs"]), set(catalog_analysis.OUTPUTS))

    def test_changed_output_or_input_regenerates(self):
        with self.fake_chain():
            out = catalog_analysis.ensure(self.work, self.dest, INPUT)
            (out / "host-closure.json").write_text(json.dumps(dict(source_catalog_sha256="c" * 64, edited=True)))
            catalog_analysis.ensure(self.work, self.dest, INPUT)
        self.assertEqual(self.calls.count("audit"), 2)

    def test_corrections_for_another_catalog_are_refused(self):
        with self.fake_chain(closure_catalog="d" * 64), self.assertRaisesRegex(RuntimeError, "different shipped catalog"):
            catalog_analysis.ensure(self.work, self.dest, INPUT)
        self.assertFalse((self.dest / ".rebuild/catalog-inputs/analysis-complete.json").exists())

    def test_incomplete_inspection_is_refused(self):
        with self.fake_chain(inspected=False), self.assertRaisesRegex(RuntimeError, "inspection incomplete"):
            catalog_analysis.ensure(self.work, self.dest, INPUT)

    def test_recipe_for_another_input_is_refused(self):
        with self.fake_chain(), self.assertRaisesRegex(RuntimeError, "accepted input"):
            catalog_analysis.ensure(self.work, self.dest, "b" * 64)


if __name__ == "__main__":
    unittest.main()
