import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from common import sha
from stage_variants import include_runtime_graph_roots


class StageVariantGraphRootsTests(unittest.TestCase):
    def test_new_variant_graphs_become_explicit_shared_bundle_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            paths = [f"Assets/WholeGame/RoR2/Base/Scenes/goolake/{name}.asset" for name in ("goolakeGroundNodegraph", "goolakeAirNodegraph")]
            accepted = {}
            for path in paths:
                file = project / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(path)
                accepted[path] = sha(file)
            config = {"integratedStages": [{"name": "goolake", "groundGraph": paths[0].lower(), "airGraph": paths[1].lower()}]}
            recipe = {"prefabAssets": [paths[0]]}
            self.assertEqual(include_runtime_graph_roots(config, recipe, project, accepted), [paths[1]])
            self.assertEqual(include_runtime_graph_roots(config, recipe, project, accepted), [])
            self.assertEqual(recipe["prefabAssets"], paths)
            (project / paths[1]).write_text("changed")
            with self.assertRaisesRegex(RuntimeError, "Accepted variant graph changed"):
                include_runtime_graph_roots(config, recipe, project, accepted)


if __name__ == "__main__":
    unittest.main()
