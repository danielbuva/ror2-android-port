import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lab"))
from common_assets_map import extract, generate


SOURCE = """public static class CommonAssets {
 public static CharacterMaster master;
 public static GameObject effect;
 public static PickupDropTable table;
 public static void Load() {
  AsyncOperationHandle<GameObject> asyncOperationHandle = LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/Master");
  asyncOperationHandle.Completed += delegate(AsyncOperationHandle<GameObject> x) { master = x.Result.GetComponent<CharacterMaster>(); };
  asyncOperationHandle = Addressables.LoadAssetAsync<GameObject>("Game/Effect.prefab");
  asyncOperationHandle.Completed += delegate(AsyncOperationHandle<GameObject> x) { effect = x.Result; };
  AsyncOperationHandle<PickupDropTable> asyncOperationHandle2 = Addressables.LoadAssetAsync<PickupDropTable>("Game/Table.asset");
  asyncOperationHandle2.Completed += delegate(AsyncOperationHandle<PickupDropTable> x) { table = x.Result; };
 }
}
public static GlobalEventManager instance;
"""


class CommonAssetsMapTests(unittest.TestCase):
    def test_exact_initializer_and_missing_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "GlobalEventManager.cs"
            source.write_text(SOURCE)
            output = Path(temporary) / "OriginalGlobalCommonAssetMap.cs"
            manifest = {"keys": [{"key": "master-guid"}, {"key": "Game/Effect.prefab"}]}
            report = generate(source, output, "accepted-input", {"Prefabs/Master": "master-guid"}, manifest, {"table"})
            self.assertEqual(report, {"rows": 3, "unlocated_fields": ["table"]})
            self.assertIn('"CharacterMaster","1"', output.read_text())
            self.assertIn('"PickupDropTable","PickupDropTable","0"', output.read_text())
            with self.assertRaisesRegex(RuntimeError, "closure changed"):
                generate(source, output, "accepted-input", {"Prefabs/Master": "master-guid"}, manifest, set())
            with self.assertRaisesRegex(RuntimeError, "initializer changed"):
                extract(SOURCE.replace("effect = x.Result;", "effect = null;"))


if __name__ == "__main__":
    unittest.main()
