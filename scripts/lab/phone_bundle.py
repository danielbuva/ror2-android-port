"""Standard-library writer for two authored Unity 2021 native fixture types.

This is deliberately not a general asset converter. Schemas describe only the
public native AssetBundle/TextAsset wire contract; no template, Unity output,
class database or game file is consumed. Run this same file on Android.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct


VERSION = "2021.3.45f2"
PAYLOAD = "phone-owned-content-fixture-v1\n"
ASSET = "assets/phone-fixture.txt"


class Writer:
    def __init__(self, endian="<"):
        self.data = bytearray()
        self.endian = endian

    def pack(self, fmt, *values):
        self.data.extend(struct.pack(self.endian + fmt, *values))

    def raw(self, data):
        self.data.extend(data)

    def align(self, size=4):
        self.data.extend(bytes(-len(self.data) % size))

    def zero_string(self, value):
        self.raw(value.encode("utf-8") + b"\0")

    def string(self, value):
        data = value.encode("utf-8")
        self.pack("i", len(data))
        self.raw(data)
        self.align()


def node(kind, name, size=-1, children=(), *, align=False, array=False, version=1):
    return (kind, name, size, tuple(children), 0x4000 if align else 0, 1 if array else 0, version)


def string_node(name):
    return node("string", name, children=(node("Array", "Array", children=(node("int", "size", 4), node("char", "data", 1)), align=True, array=True),))


def pointer(name):
    return node("PPtr<Object>", name, 12, (node("int", "m_FileID", 4), node("SInt64", "m_PathID", 8)))


def asset_info(name):
    return node("AssetInfo", name, 20, (node("int", "preloadIndex", 4), node("int", "preloadSize", 4), pointer("asset")))


def vector(kind, name, element):
    return node(kind, name, children=(node("Array", "Array", children=(node("int", "size", 4), element), array=True),))


def schemas():
    return [
        (
            142,
            node(
                "AssetBundle",
                "Base",
                version=3,
                children=(
                    string_node("m_Name"),
                    vector("vector", "m_PreloadTable", pointer("data")),
                    vector("map", "m_Container", node("pair", "data", children=(string_node("first"), asset_info("second")))),
                    asset_info("m_MainAsset"),
                    node("unsigned int", "m_RuntimeCompatibility", 4),
                    string_node("m_AssetBundleName"),
                    vector("vector", "m_Dependencies", string_node("data")),
                    node("bool", "m_IsStreamedSceneAssetBundle", 1, align=True),
                    node("int", "m_ExplicitDataLayout", 4),
                    node("int", "m_PathFlags", 4),
                    vector("map", "m_SceneHashes", node("pair", "data", children=(string_node("first"), string_node("second")))),
                ),
            ),
        ),
        (49, node("TextAsset", "Base", children=(string_node("m_Name"), string_node("m_Script")))),
    ]


def write_tree(writer, root):
    strings = Writer()
    offsets = {}
    nodes = Writer()
    count = 0

    def offset(value):
        if value not in offsets:
            offsets[value] = len(strings.data)
            strings.zero_string(value)
        return offsets[value]

    def visit(item, level):
        nonlocal count
        kind, name, size, children, meta, flags, version = item
        nodes.pack("hBBIIiiiQ", version, level, flags, offset(kind), offset(name), size, count, meta, 0)
        count += 1
        for child in children:
            visit(child, level + 1)

    visit(root, 0)
    writer.pack("ii", count, len(strings.data))
    writer.raw(nodes.data)
    writer.raw(strings.data)


def make_bundle(payload=PAYLOAD):
    """Write a fresh little-endian Android serialized file in UnityFS 7."""
    asset = Writer()
    asset.string("phone-fixture")
    asset.pack("iiq", 1, 0, 2)  # One preload PPtr to path ID 2.
    asset.pack("i", 1)
    asset.string(ASSET)
    asset.pack("iiiq", 0, 1, 0, 2)  # Container AssetInfo.
    asset.pack("iiiq", 0, 0, 0, 0)  # Null main AssetInfo.
    asset.pack("I", 1)
    asset.string("phone-fixture")
    asset.pack("i", 0)  # Dependencies.
    asset.pack("?", False)
    asset.align()
    asset.pack("iii", 0, 0, 0)  # Explicit layout, path flags, scene hashes.
    text = Writer()
    text.string("phone-fixture")
    text.string(payload)
    objects = [asset.data, text.data]
    body = Writer()
    locations = []
    for data in objects:
        body.align(8)
        locations.append((len(body.data), len(data)))
        body.raw(data)

    meta = Writer()
    meta.zero_string(VERSION)
    meta.pack("i?i", 13, True, 2)  # Android, embedded trees, two types.
    for class_id, tree in schemas():
        meta.pack("i?h", class_id, False, -1)
        meta.raw(bytes(16))  # No imported native type hash.
        write_tree(meta, tree)
        meta.pack("i", 0)
    meta.pack("i", 2)
    for index, (offset, size) in enumerate(locations):
        meta.align()
        meta.pack("qqIi", index + 1, offset, size, index)
    meta.pack("iii", 0, 0, 0)  # Script types, externals, reference types.
    meta.zero_string("")
    data_offset = (48 + len(meta.data) + 15) // 16 * 16
    serialized = Writer(">")
    serialized.pack("IIII", 0, 0, 22, 0)
    serialized.raw(bytes(4))
    serialized.pack("Iqqq", len(meta.data), data_offset + len(body.data), data_offset, 0)
    serialized.raw(meta.data)
    serialized.align(16)
    serialized.raw(body.data)

    directory = Writer(">")
    directory.raw(bytes(16))
    directory.pack("iIIH", 1, len(serialized.data), len(serialized.data), 0)
    directory.pack("iqqI", 1, 0, len(serialized.data), 4)
    directory.zero_string("CAB-phone-build-fixture")
    bundle = Writer(">")
    bundle.zero_string("UnityFS")
    bundle.pack("I", 7)
    bundle.zero_string("5.x.x")
    bundle.zero_string(VERSION)
    size_position = len(bundle.data)
    bundle.pack("qIII", 0, len(directory.data), len(directory.data), 0x40)
    bundle.align(16)
    bundle.raw(directory.data)
    bundle.raw(serialized.data)
    struct.pack_into(">q", bundle.data, size_position, len(bundle.data))
    return bytes(bundle.data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New authored fixture bundle; refuses an existing file")
    args = parser.parse_args()
    data = make_bundle()
    with args.output.open("xb") as output:
        output.write(data)
    print(json.dumps({"unity": VERSION, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
