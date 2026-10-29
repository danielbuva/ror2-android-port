"""Independent native parsing of authored manifest cohorts; no game/SDK input."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("source_bundle_manifest", ROOT / "tools/phone-build/accepted-output/bundle_manifest.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def facts():
    return {
        "b": dict(sha256=hashlib.sha256(b"second").hexdigest(), bytes=6, dependencies=["a"]),
        "a": dict(sha256=hashlib.sha256(b"first").hexdigest(), bytes=5, dependencies=["b"]),
        "unused": dict(sha256=hashlib.sha256(b"third").hexdigest(), bytes=5, dependencies=[]),
    }


class BundleManifestTests(unittest.TestCase):
    def test_native_declarations_match_independent_public_format_database(self):
        from UnityPy.helpers.Tpk import get_typetree_node
        from UnityPy.helpers.UnityVersion import UnityVersion

        for typ in M.schemas():
            independent = get_typetree_node(typ["class_id"], UnityVersion.from_str(M.F.VERSION))
            rows = M.S.tree_nodes(typ["tree"])
            other = list(independent.traverse())
            self.assertEqual(len(rows), len(other))
            for row, node in zip(rows, other):
                self.assertEqual(
                    (row["type"], row["name"], row["size"], row["version"], row["meta"] & 0x4000, row["flags"]),
                    (node.m_Type, node.m_Name, node.m_ByteSize, node.m_Version, node.m_MetaFlag & 0x4000, int(node.m_Type == "Array")),
                )

    def test_complete_binary_uses_native_tables_and_preserves_cycles(self):
        import UnityPy

        data = M.build(facts())
        self.assertEqual(data, M.build(dict(reversed(list(facts().items())))))
        env = UnityPy.load(data)
        objects = {obj.type.value: obj.read_typetree() for obj in env.objects}
        manifest = objects[290]
        names = dict(manifest["AssetBundleNames"])
        self.assertEqual(names, {0: "a", 1: "b", 2: "unused"})
        self.assertEqual(manifest["AssetBundlesWithVariant"], [])
        for index, info in manifest["AssetBundleInfos"]:
            source = facts()[names[index]]
            self.assertEqual(bytes(info["AssetBundleHash"][f"bytes[{i}]"] for i in range(16)), bytes.fromhex(source["sha256"])[:16])
            self.assertEqual([names[i] for i in info["AssetBundleDependencies"]], source["dependencies"])
        root = dict(objects[142]["m_Container"])["assetbundlemanifest"]
        self.assertEqual(root["asset"], dict(m_FileID=0, m_PathID=2))
        self.assertEqual(objects[142]["m_PreloadTable"], [root["asset"]])
        self.assertEqual(manifest["m_Name"], "AssetBundleManifest")

    def test_content_change_changes_cache_version_without_changing_relationships(self):
        before = M.manifest_fields(facts())
        changed = facts()
        changed["a"]["sha256"] = hashlib.sha256(b"updated").hexdigest()
        after = M.manifest_fields(changed)
        self.assertEqual(before["AssetBundleNames"], after["AssetBundleNames"])
        self.assertNotEqual(before["AssetBundleInfos"][0][1]["AssetBundleHash"], after["AssetBundleInfos"][0][1]["AssetBundleHash"])
        self.assertEqual(before["AssetBundleInfos"][0][1]["AssetBundleDependencies"], after["AssetBundleInfos"][0][1]["AssetBundleDependencies"])

    def test_missing_dependency_cannot_be_silently_omitted(self):
        broken = facts()
        del broken["b"]
        with self.assertRaisesRegex(ValueError, "missing"):
            M.build(broken)

    def test_actual_producer_reads_native_dependency_records_and_checks_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "authored-bundle"
            # Existing standard-library fixture supplies a real, dependency-free
            # class 142 container. The manifest generator has no target input.
            source.write_bytes(M.F.make_bundle())
            inputs = root / "inputs.json"
            row = dict(name="authored-bundle", path=source.name, sha256=M.W.B.sha(source), bytes=source.stat().st_size)
            inputs.write_text(json.dumps(dict(schema="owner-produced-bundle-inputs-v1", bundles=[row])))
            result = M.produce(inputs, root / "out")
            self.assertTrue(result["success"])
            self.assertEqual(result["bundles"]["authored-bundle"]["dependencies"], [])
            self.assertFalse(result["historical_raw_exact"])
            self.assertEqual(result["file"]["sha256"], M.W.B.sha(root / "out/generated-android-data"))
            row["sha256"] = "0" * 64
            inputs.write_text(json.dumps(dict(schema="owner-produced-bundle-inputs-v1", bundles=[row])))
            with self.assertRaisesRegex(ValueError, "input differs"):
                M.produce(inputs, root / "refused")
            self.assertFalse((root / "refused").exists())


if __name__ == "__main__":
    unittest.main()
