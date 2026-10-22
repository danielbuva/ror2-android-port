import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts/lab"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("whole_catalog", SCRIPTS / "whole_catalog.py")
whole_catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(whole_catalog)


class CameraShaderRootsTests(unittest.TestCase):
    def setUp(self):
        self.type = whole_catalog.SHADER_LOCATION_TYPE
        expected = whole_catalog.CAMERA_SHADER_ROOTS
        self.metadata = {
            "locations": [{"id": location_id, "type": self.type, "primaryKey": primary_key} for location_id, (_, primary_key) in expected.items()],
            "keys": [{"key": guid, "keyType": "System.String", "locations": [location_id]} for location_id, (guid, _) in expected.items()],
        }
        self.closure = {"converted": {str(location_id): {"resolution": "exact", "source": f"Assets/Original/{location_id}.shader"} for location_id in expected}}

    def test_four_exact_shader_rows_are_added_as_source_paths(self):
        self.assertEqual(
            whole_catalog.camera_shader_roots(self.metadata, self.closure),
            {"Assets/Original/16022.shader", "Assets/Original/16025.shader", "Assets/Original/15950.shader", "Assets/Original/2537.shader"},
        )

    def test_generator_recipe_and_unity_builder_agree_on_exact_shader_roots(self):
        recipe = json.loads((ROOT / "recipe/native-view-camera-transform.json").read_text())["camera_shader_roots"]
        rows = {row["catalog_id"]: (row["address_key"], row["primary_key"]) for row in recipe["entries"]}
        self.assertEqual(rows, whole_catalog.CAMERA_SHADER_ROOTS)
        builder = (ROOT / "tools/catalog/WholeCatalogBuild.cs").read_text()
        block = builder.split("cameraShaderLocations = new Dictionary<int, string>", 1)[1].split("};", 1)[0]
        builder_rows = {int(location): guid for location, guid in re.findall(r'\{\s*(\d+),\s*"([0-9a-f]{32})"\s*\}', block)}
        self.assertEqual(builder_rows, {location: guid for location, (guid, _) in rows.items()})

    def test_missing_filtered_row_refuses_instead_of_emitting_broken_guid(self):
        self.metadata["locations"].pop(0)
        with self.assertRaisesRegex(RuntimeError, "location changed"):
            whole_catalog.camera_shader_roots(self.metadata, self.closure)

    def test_stale_key_that_points_at_another_id_refuses(self):
        self.metadata["keys"][0]["locations"] = [16024]
        with self.assertRaisesRegex(RuntimeError, "address key changed"):
            whole_catalog.camera_shader_roots(self.metadata, self.closure)

    def test_type_or_primary_key_mutant_refuses(self):
        self.metadata["locations"][0]["type"] = "UnityEngine.Texture2D"
        with self.assertRaisesRegex(RuntimeError, "location changed"):
            whole_catalog.camera_shader_roots(self.metadata, self.closure)

    def test_inexact_or_unsafe_source_conversion_refuses(self):
        self.closure["converted"]["16022"]["resolution"] = "exported-filename"
        with self.assertRaisesRegex(RuntimeError, "not exact"):
            whole_catalog.camera_shader_roots(self.metadata, self.closure)
        self.closure["converted"]["16022"] = {"resolution": "exact", "source": "Assets/../outside.shader"}
        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            whole_catalog.camera_shader_roots(self.metadata, self.closure)


if __name__ == "__main__":
    unittest.main()
