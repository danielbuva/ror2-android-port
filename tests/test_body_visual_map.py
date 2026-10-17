import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from body_visual_map import extract, generate


class BodyVisualMapTests(unittest.TestCase):
    def test_exact_initializer_pairs_and_host_location_check(self):
        source = """public static GameObject alphaEffect;
public static GameObject betaEffect;
public static void Resolve()
{
 asyncOperationHandle = LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/Alpha");
 asyncOperationHandle.Completed += delegate(AsyncOperationHandle<GameObject> x)
 {
  alphaEffect = x.Result;
 };
 asyncOperationHandle = Addressables.LoadAssetAsync<GameObject>("Game/Beta.prefab");
 asyncOperationHandle.Completed += delegate(AsyncOperationHandle<GameObject> x)
 {
  betaEffect = x.Result;
 };
\t\t}
"""
        self.assertEqual(extract(source), [("LegacyResourcesAPI", "Prefabs/Alpha", "alphaEffect"), ("Addressables", "Game/Beta.prefab", "betaEffect")])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "CharacterBody.cs"
            output = Path(temporary) / "OriginalBodyVisualMap.cs"
            path.write_text(source)
            report = generate(
                path, output, "accepted-input", {"Prefabs/Alpha": "original-guid"}, {"keys": [{"key": "original-guid"}, {"key": "Game/Beta.prefab"}]}
            )
            self.assertEqual(report, {"rows": 2, "unlocated_fields": []})
            self.assertIn("Game/Beta.prefab", output.read_text())
            self.assertIn("new string[] {", output.read_text())
            health_output = Path(temporary) / "OriginalHealthVisualMap.cs"
            generate(
                path, health_output, "accepted-input", {"Prefabs/Alpha": "original-guid"}, {"keys": [{"key": "original-guid"}, {"key": "Game/Beta.prefab"}]}
            )
            self.assertIn("class OriginalHealthVisualMap", health_output.read_text())
            with self.assertRaisesRegex(RuntimeError, "class name is invalid"):
                generate(
                    path,
                    Path(temporary) / "invalid-map.cs",
                    "accepted-input",
                    {"Prefabs/Alpha": "original-guid"},
                    {"keys": [{"key": "original-guid"}, {"key": "Game/Beta.prefab"}]},
                )
            with self.assertRaisesRegex(RuntimeError, "initializer changed"):
                extract(source.replace("betaEffect = x.Result;", "betaEffect = null;"))


if __name__ == "__main__":
    unittest.main()
