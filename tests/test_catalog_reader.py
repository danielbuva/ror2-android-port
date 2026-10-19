"""Host Addressables catalog reader against an authored synthetic catalog (no game data)."""

import base64
import json
import struct
import tempfile
import unittest
from pathlib import Path

from catalog_reader import dumps, read_object, read_shipped

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY = "Unity.ResourceManager, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"
NAMES = dict(labels=[dict(name="itemDef", key="ItemDef")], providers=[dict(identifier="Example.Base", type="Example.Content, Example, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null")])


def ascii_key(text):
    return bytes([0]) + struct.pack("<i", len(text)) + text.encode("ascii")


def unicode_key(text):
    data = text.encode("utf-16-le")
    return bytes([1]) + struct.pack("<i", len(data)) + data


def json_object(assembly, name, body):
    data = body.encode("utf-16-le")
    return bytes([7, len(assembly)]) + assembly.encode() + bytes([len(name)]) + name.encode() + struct.pack("<i", len(data)) + data


def catalog(keys, buckets, entries, extra, types):
    key_data = struct.pack("<i", len(keys))
    offsets = []
    for key in keys:
        offsets.append(len(key_data))
        key_data += key
    bucket_data = struct.pack("<i", len(buckets))
    for offset, members in zip(offsets, buckets):
        bucket_data += struct.pack("<ii", offset, len(members)) + b"".join(struct.pack("<i", m) for m in members)
    entry_data = struct.pack("<i", len(entries)) + b"".join(struct.pack("<7i", *row) for row in entries)
    return dict(
        m_LocatorId="AddressablesMainContentCatalog",
        m_ProviderIds=["Provider.Bundle", "Provider.Asset"],
        m_InternalIds=["{UnityEngine.AddressableAssets.Addressables.RuntimePath}\\Win\\a.bundle", "Assets/A.prefab", "Assets/B.asset"],
        m_KeyDataString=base64.b64encode(key_data).decode(),
        m_BucketDataString=base64.b64encode(bucket_data).decode(),
        m_EntryDataString=base64.b64encode(entry_data).decode(),
        m_ExtraDataString=base64.b64encode(extra).decode(),
        m_resourceTypes=types,
        m_InternalIdPrefixes=[],
    )


class CatalogReaderTests(unittest.TestCase):
    def build(self, types=None):
        options = json.dumps(dict(m_Hash="abc", m_Crc=7, m_BundleName="b1", m_BundleSize=99))
        extra = json_object(ASSEMBLY, "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions", options)
        keys = [ascii_key("a.bundle"), unicode_key("Prefé"), ascii_key("Assets/B.asset"), bytes([4]) + struct.pack("<i", 42)]
        # Buckets: key -> entry indices. Entry rows: internal, provider, dependency key, hash, data, primary key, type.
        buckets = [[0], [1], [2], [2, 1]]
        entries = [(0, 0, -1, 0, 0, 0, 0), (1, 1, 0, 0, -1, 1, 1), (2, 1, 0, 0, -1, 2, 2)]
        types = types or [
            dict(m_AssemblyName=ASSEMBLY, m_ClassName="UnityEngine.ResourceManagement.ResourceProviders.IAssetBundleResource"),
            dict(m_AssemblyName="UnityEngine.CoreModule, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null", m_ClassName="UnityEngine.GameObject"),
            dict(m_AssemblyName="Example, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null", m_ClassName="Example.Outer+Inner"),
        ]
        directory = Path(tempfile.mkdtemp())
        path = directory / "catalog.json"
        path.write_text(json.dumps(catalog(keys, buckets, entries, extra, types)))
        return read_shipped(path, "/lab/Assets/StreamingAssets/aa", NAMES)

    def test_mirrors_create_locator_and_editor_query(self):
        record = self.build()
        self.assertEqual(record["schemaVersion"], 2)
        self.assertEqual([(k["key"], k["keyType"], k["locations"]) for k in record["keys"]],
                         [("a.bundle", "System.String", [0]), ("Prefé", "System.String", [1]), ("Assets/B.asset", "System.String", [2]), ("42", "System.Int32", [2, 1])])
        bundle, prefab, asset = record["locations"]
        self.assertEqual(bundle["internalId"], "/lab/Assets/StreamingAssets/aa\\Win\\a.bundle")
        self.assertEqual(bundle["provider"], "Provider.Bundlewhole-source-audit")
        self.assertEqual(bundle["bundle"], dict(BundleName="b1", Hash="abc", BundleSize=99, Crc=7))
        self.assertEqual(prefab["primaryKey"], "Prefé")
        self.assertIsNone(prefab["bundle"])
        self.assertEqual(asset["type"], "Example.Outer+Inner, Example, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null")
        # Shared dependency sets: the bundle has none, both assets share the bundle.
        self.assertEqual(record["dependencySets"], [[], [0]])
        self.assertEqual([row["dependencySet"] for row in record["locations"]], [0, 1, 1])
        self.assertEqual(record["labels"], NAMES["labels"])
        self.assertEqual(record["providers"], NAMES["providers"])

    def test_dependencies_drop_unresolved_types_like_typeof_object(self):
        types = [dict(m_AssemblyName="", m_ClassName=""), dict(m_AssemblyName="A", m_ClassName="B"), dict(m_AssemblyName="A", m_ClassName="C")]
        record = self.build(types)
        self.assertIsNone(record["locations"][0]["type"])
        self.assertEqual(record["dependencySets"], [[]])

    def test_newtonsoft_indented_form(self):
        text = dumps(dict(a=[], b=[1, 2], c=None, d="é/\"x\""))
        self.assertEqual(text, '{\n  "a": [],\n  "b": [\n    1,\n    2\n  ],\n  "c": null,\n  "d": "é/\\"x\\""\n}')

    def test_refuses_unmeasured_shapes(self):
        with self.assertRaisesRegex(RuntimeError, "Unsupported catalog object kind"):
            read_object(bytes([5, 2]) + b"ab", 0)

    def test_editor_query_is_retired(self):
        self.assertFalse((ROOT / "tools/catalog/ExportCatalog.cs.txt").exists())
        source = (ROOT / "scripts/lab/whole_catalog.py").read_text()
        self.assertIn("export_source_catalog(out)", source)
        program = (ROOT / "tools/assembly-transforms/Program.cs").read_text()
        self.assertIn('"--catalog-names"', program)


if __name__ == "__main__":
    unittest.main()
