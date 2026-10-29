"""Generate a native Unity bundle manifest from complete produced bundle inputs.

Build-session indices and cache versions are generated independently. Original
asset identities, code and dependency relationships remain source-owned. This
owner never reads an accepted manifest, build cache or catalog as a supplier.
"""

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


W = module("_manifest_write", HERE / "unity_write.py")
S = module("_manifest_identity", ROOT / "scripts/lab/script_identity.py")
F = module("_manifest_format", ROOT / "scripts/lab/phone_bundle.py")


def schemas():
    """Public 2021 native wire fields; alignment also determines native hashes.

    UnityPy 1.25.3's pinned public type database independently checks both trees.
    No SDK implementation, game type tree or serialized object is embedded here.
    """
    n, text, vector = F.node, F.string_node, F.vector
    asset = F.schemas()[0][1]
    children = list(asset[3])
    for index in (1, 6):
        field = children[index]
        array = field[3][0]
        array = (*array[:4], 0x4000, *array[5:])
        children[index] = (*field[:3], (array,), *field[4:])
    asset = (*asset[:3], tuple(children), *asset[4:])
    hashes = n("Hash128", "AssetBundleHash", 16, [n("UInt8", f"bytes[{i}]", 1) for i in range(16)])
    info = n("AssetBundleInfo", "second", children=(hashes, vector("set", "AssetBundleDependencies", n("int", "data", 4))))
    manifest = n(
        "AssetBundleManifest",
        "Base",
        children=(
            text("m_Name"),
            vector("map", "AssetBundleNames", n("pair", "data", children=(n("int", "first", 4), text("second")))),
            vector("set", "AssetBundlesWithVariant", n("int", "data", 4)),
            vector("map", "AssetBundleInfos", n("pair", "data", children=(n("int", "first", 4), info))),
        ),
    )
    result = []
    for cid, root in ((142, asset), (290, manifest)):
        rows = []

        def walk(node, level):
            kind, name, size, children, meta, flags, version = node
            rows.append(dict(type=kind, name=name, size=size, level=level, meta=meta, flags=flags, version=version))
            for child in children:
                walk(child, level + 1)

        walk(root, 0)
        digest = S.md4(
            b"".join(r["type"].encode() + r["name"].encode() + struct.pack("<iiiI", r["size"], r["flags"], r["version"], r["meta"] & 0x4000) for r in rows)
        )
        result.append(dict(class_id=cid, stripped=0, script_type=-1, hash=digest, tree=S._tree(rows)))
    return result


def manifest_fields(bundles):
    names = sorted(bundles)
    if not names or len(names) > 100000 or any(not re.fullmatch(r"[a-z0-9][a-z0-9._/-]{0,255}", name) or ".." in Path(name).parts for name in names):
        raise ValueError("invalid or empty bundle population")
    ids = {name: index for index, name in enumerate(names)}
    infos = []
    for name in names:
        row = bundles[name]
        if not re.fullmatch("[0-9a-f]{64}", row["sha256"]) or type(row["bytes"]) is not int or row["bytes"] <= 0:
            raise ValueError("invalid produced bundle digest or size")
        dependencies = row["dependencies"]
        if len(dependencies) != len(set(dependencies)) or any(dep not in ids or dep == name for dep in dependencies):
            raise ValueError("missing, duplicate or self bundle dependency")
        digest = bytes.fromhex(row["sha256"])[:16]
        infos.append(
            (
                ids[name],
                dict(AssetBundleHash={f"bytes[{i}]": b for i, b in enumerate(digest)}, AssetBundleDependencies=sorted(ids[dep] for dep in dependencies)),
            )
        )
    return dict(m_Name="AssetBundleManifest", AssetBundleNames=[(ids[name], name) for name in names], AssetBundlesWithVariant=[], AssetBundleInfos=infos)


def build(bundles):
    """Return a complete uncompressed UnityFS file; no codec or editor needed."""
    types = schemas()
    fields = manifest_fields(bundles)
    container = dict(
        m_Name="generated-android-data",
        m_PreloadTable=[dict(m_FileID=0, m_PathID=2)],
        m_Container=[("assetbundlemanifest", dict(preloadIndex=0, preloadSize=1, asset=dict(m_FileID=0, m_PathID=2)))],
        m_MainAsset=dict(preloadIndex=0, preloadSize=0, asset=dict(m_FileID=0, m_PathID=0)),
        m_RuntimeCompatibility=1,
        m_AssetBundleName="generated-android-data",
        m_Dependencies=[],
        m_IsStreamedSceneAssetBundle=False,
        m_ExplicitDataLayout=0,
        m_PathFlags=7,
        m_SceneHashes=[],
    )
    bodies = [W.write_shader_body(W.shader_node(typ["tree"]), value) for typ, value in zip(types, (container, fields))]
    rows, offset = [], 0
    for index, body in enumerate(bodies):
        offset = (offset + 7) // 8 * 8
        rows.append(dict(path_id=index + 1, type_id=index, offset=offset, bytes=len(body)))
        offset += len(body)
    layout = dict(engine=F.VERSION, platform=13, trees=False, types=types, objects=rows, scripts=[], externals=[], ref_types=[], user="")
    serialized = io.BytesIO()
    W.write_serialized(serialized, layout, lambda row: io.BytesIO(bodies[row["path_id"] - 1]))
    raw = serialized.getvalue()
    name = "CAB-" + hashlib.sha256(raw).hexdigest()[:32]
    output = io.BytesIO()
    W.write_bundle(output, [(name, 4, len(raw), lambda: io.BytesIO(raw))], lambda data, method: data, flags=0x40)
    return output.getvalue()


def produce(inputs, output):
    inputs, output = Path(inputs).resolve(strict=True), Path(output).resolve()
    request_bytes = inputs.read_bytes()
    request = json.loads(request_bytes)
    if set(request) != {"schema", "bundles"} or request["schema"] != "owner-produced-bundle-inputs-v1":
        raise ValueError("unsupported produced bundle input contract")
    files, pins = {}, {}
    for row in request["bundles"]:
        if set(row) != {"name", "path", "sha256", "bytes"} or row["name"] in files:
            raise ValueError("duplicate bundle or unsupported input fields")
        path = Path(row["path"])
        path = (inputs.parent / path).resolve(strict=True) if not path.is_absolute() else path.resolve(strict=True)
        pin = dict(sha256=W.B.sha(path), bytes=path.stat().st_size)
        if pin != {key: row[key] for key in pin}:
            raise ValueError("produced bundle input differs")
        files[row["name"]], pins[path] = path, pin
    sys.path.insert(0, str(ROOT / "scripts/lab"))
    from whole_catalog import produced_bundle_metadata

    facts = produced_bundle_metadata(files)
    raw = build(facts)  # Refuses incomplete dependency graphs before output.
    if inputs.read_bytes() != request_bytes or any(dict(sha256=W.B.sha(path), bytes=path.stat().st_size) != pin for path, pin in pins.items()):
        raise ValueError("bundle inputs changed during production")
    output.mkdir(exist_ok=False)
    destination = output / "generated-android-data"
    destination.write_bytes(raw)
    if destination.read_bytes() != raw:
        raise ValueError("persisted manifest differs")
    receipt = dict(
        success=True,
        phase="bundle-manifest-produced",
        input_sha256=hashlib.sha256(request_bytes).hexdigest(),
        producer_sha256=W.B.sha(Path(__file__)),
        bundles=facts,
        file=dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
        cache_hash_policy="sha256-prefix-128",
        historical_raw_exact=False,
        phone_qualified=False,
        runtime_qualified=False,
    )
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = produce(args.inputs, args.output)
    print(json.dumps(dict(success=result["success"], file=result["file"], bundles=len(result["bundles"]))))


if __name__ == "__main__":
    main()
