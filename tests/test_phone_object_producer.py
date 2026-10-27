"""Complete source-only prefab fixture; no game bytes or installed Editor."""

from contextlib import nullcontext
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


P = load("object_producer", ROOT / "tools/phone-build/accepted-output/object_produce.py")
FIXTURE = load("object_bundle_fixture", ROOT / "tests/test_phone_mesh_producer.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def literal_lz4(data, method):
    """Authored valid literal-only block, independent of a native installation."""
    if not method:
        return data
    size = len(data)
    extra = bytearray()
    if size >= 15:
        remainder = size - 15
        while remainder >= 255:
            extra.append(255)
            remainder -= 255
        extra.append(remainder)
    return bytes([min(size, 15) << 4]) + extra + data


def produce(profile, pin, pc, output):
    with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
        return P.produce(profile, pin, pc, output, Path("authored-codec"), "authored-codec-pin")


def typ(class_id):
    return {
        "class_id": class_id,
        "stripped": 0,
        "script_type": -1,
        "hash": bytes([class_id % 256]) * 16,
        "tree": struct.pack("<II", 1, 0) + bytes(32),
        "dependencies": [],
    }


def container_bytes():
    """Independent literal format fixture using authored asset identifiers."""

    def string(value):
        data = value.encode()
        return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)

    return (
        string("authored-target")
        + struct.pack("<Iiqiqiq", 3, 0, -7, 0, 2, 1, 88)
        + struct.pack("<I", 1)
        + string("assets/authored.prefab")
        + struct.pack("<iiiq", 0, 3, 0, -7)
        + struct.pack("<iiiqI", 0, 0, 0, 0, 1)
        + string("authored-target")
        + struct.pack("<I", 1)
        + string("authored-dependency")
        + struct.pack("<B3xiii", 0, 0, 7, 0)
    )


def fixture(root):
    pc = root / "pc"
    pc.mkdir()
    source_body = struct.pack("<iq", 0, 51) + b"TAIL"
    target_body = struct.pack("<iq", 0, 2) + b"TAIL"
    script_body = b"META"
    source_layout = {
        "engine": "2021.3.1f1",
        "platform": 19,
        "trees": True,
        "types": [typ(4), typ(115), typ(142)],
        "objects": [{"path_id": 51, "offset": 0, "bytes": 4, "type_id": 1}, {"path_id": 61, "offset": 8, "bytes": 16, "type_id": 0}],
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    original = io.BytesIO()
    P.W.write_serialized(original, source_layout, lambda row: io.BytesIO(script_body if row["path_id"] == 51 else source_body))
    source = pc / "source.bundle"
    source.write_bytes(FIXTURE.bundle([("CAB-source", original.getvalue(), 4)], True))
    selected = {
        "name": "authored-target",
        "member": "CAB-target",
        "asset": "Assets/Authored.prefab",
        "root": -7,
        "dependencies": ["authored-dependency"],
        "externals": ["CAB-dependency"],
        "external_objects": [[1, 88]],
    }
    container = container_bytes()
    bodies = {-7: target_body, 1: container, 2: script_body}
    target_layout = {
        "engine": "2021.3.45f2",
        "platform": 13,
        "trees": True,
        "types": [typ(115), typ(4), typ(142)],
        "objects": [
            {"path_id": -7, "offset": 8, "bytes": 16, "type_id": 1},
            {"path_id": 1, "offset": 24, "bytes": len(container), "type_id": 2},
            {"path_id": 2, "offset": 0, "bytes": 4, "type_id": 0},
        ],
        "scripts": [(0, 2)],
        "externals": [{"empty": "", "guid": bytes(16), "type": 0, "path": "archive:/CAB-dependency/CAB-dependency"}],
        "ref_types": [],
        "user": "",
    }
    target = io.BytesIO()
    P.W.write_serialized(target, target_layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    selected["serialized_sha256"] = digest(target.getvalue())
    expected_bundle = io.BytesIO()
    P.W.write_bundle(expected_bundle, [("CAB-target", 4, len(target.getvalue()), lambda: io.BytesIO(target.getvalue()))], literal_lz4)
    selected["sha256"] = digest(expected_bundle.getvalue())
    selected["bytes"] = len(expected_bundle.getvalue())
    profile = {
        "input_id": P.M.INPUT_ID,
        "sources": [{"path": source.name, "sha256": P.B.sha(source), "member": "CAB-source"}],
        "bundle": selected,
        "objects": [
            {
                "path_id": -7,
                "source": [0, 61],
                "source_sha256": digest(source_body),
                "bytes": 16,
                "sha256": digest(target_body),
                "references": [{"offset": 0, "from": [0, 51], "to": [0, 2]}],
            },
            {"path_id": 1, "type_source": 0, "bytes": len(container), "sha256": digest(container)},
            {"path_id": 2, "source": [0, 51], "source_sha256": digest(script_body), "bytes": 4, "sha256": digest(script_body)},
        ],
    }
    path = root / "profile.json"
    path.write_text(json.dumps(profile))
    return pc, path, profile, bodies, target.getvalue()


def packed_fixture(root):
    pc, profile_path, profile, bodies, serialized = fixture(root)
    directory = root / "record-pack"
    directory.mkdir()
    record_profile = "a" * 64
    data = b"AUTHORED"
    row = {
        "bundle": "authored-target",
        "member": "CAB-target",
        "path_id": -7,
        "offset": 0,
        "bytes": len(bodies[-7]),
        "sha256": digest(bodies[-7]),
        "resource": {
            "offset": 0,
            "bytes": len(data),
            "sha256": digest(data),
            "stream": {"path": "archive:/CAB-target/CAB-target.resS", "offset": 8, "size": len(data)},
        },
    }
    (directory / "objects.bin").write_bytes(bodies[-7])
    (directory / "resources.bin").write_bytes(data)
    (directory / "index.jsonl").write_text(json.dumps(row) + "\n")
    receipt = {"success": True, "input_id": P.M.INPUT_ID, "profile_sha256": record_profile}
    receipt["outputs"] = {
        name: {"bytes": (directory / name).stat().st_size, "sha256": P.B.sha(directory / name)} for name in ("objects.bin", "resources.bin", "index.jsonl")
    }
    (directory / "result.json").write_text(json.dumps(receipt))
    selected = profile["objects"][0]
    selected.pop("source")
    selected.pop("source_sha256")
    selected.pop("references")
    selected.update(record=record_profile, type_source=[0, 61])
    complete = io.BytesIO()
    P.W.write_bundle(
        complete,
        [("CAB-target", 4, len(serialized), lambda: io.BytesIO(serialized)), ("CAB-target.resS", 0, 16, lambda: io.BytesIO(bytes(8) + data))],
        literal_lz4,
    )
    profile["bundle"].update(bytes=len(complete.getvalue()), sha256=digest(complete.getvalue()))
    profile_path.write_text(json.dumps(profile))
    return pc, profile_path, directory, profile, row, serialized


def scene_fixture(root, *, preload_dependency=False, global_owner=False, engine="2021.3.45f2"):
    """Authored two-member scene with overlapping IDs and external scripts."""
    pc = root / "pc"
    pc.mkdir()
    shared, main = "BuildPlayer-authored.sharedAssets", "BuildPlayer-authored"

    def string(value):
        data = value.encode()
        return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)

    mono = {**typ(114), "script_id": bytes(16), "script_type": 99}
    original_first = bytes(16) + struct.pack("<iqiqiqiq", 0, 71, 8, 90, 8, 80, 0, 91)
    first = bytes(16) + struct.pack("<iqiqiqiq", 1, 7, 2, 90, 3, 80, 1, 3)
    original_second = bytes(16) + struct.pack("<iqiqiq", 0, 72, 9, 80, 4, 123)
    second = bytes(16) + struct.pack("<iqiqiq", 1, 8, 3, 80, 4, 123)
    original_gameobject = struct.pack("<II", 0, 0) + string("SceneInfo" if global_owner else "Map owner") + struct.pack("<HB", 0, 1)
    gameobject = struct.pack("<Iiq", 1, 0, 1) + original_gameobject[4:-1] + bytes(1)
    original_occlusion = bytes(range(16)) + struct.pack("<iqIiqiqIiq", 8, 80, 2, 0, 81, 0, 82, 1, 0, 83)
    occlusion_without_renderers = original_occlusion[:28] + bytes(4) + original_occlusion[56:]
    occlusion = bytes(range(16)) + struct.pack("<iqIIiq", 3, 80, 0, 1, 0, 4)
    source_bodies = {
        71: (typ(115), b"FIRST"),
        72: (typ(115), b"SECOND"),
        81: (mono, original_first),
        82: (mono, original_second),
        83: (typ(1), original_gameobject),
        84: (typ(29), original_occlusion),
        91: (typ(43), b"ORIGINAL-MESH"),
        101: (typ(150), string("Original preload") + struct.pack("<Iiq", 1, 0, 83)),
        102: (typ(142), b"ORIGINAL-CONTAINER"),
    }
    source_layout = {
        "engine": "2021.3.1f1",
        "platform": 19,
        "trees": True,
        "types": [typ(115), mono, typ(1), typ(43), typ(150), typ(142), typ(29)],
        "objects": [],
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    offset = 0
    for identity, (kind, body) in source_bodies.items():
        offset = (offset + 7) // 8 * 8
        source_layout["objects"].append({"path_id": identity, "offset": offset, "bytes": len(body), "type_id": source_layout["types"].index(kind)})
        offset += len(body)
    source_serialized = io.BytesIO()
    P.W.write_serialized(source_serialized, source_layout, lambda row: io.BytesIO(source_bodies[row["path_id"]][1]))
    source = pc / "original.bundle"
    source.write_bytes(FIXTURE.bundle([("CAB-original", source_serialized.getvalue(), 4)], True))
    # Independent expected native bodies: sorted unique dependencies translated
    # into the shared member's external table; all scene-local PPtrs excluded.
    pointers = [(1, 80), (1, 404), (2, 123), (3, 90)] if preload_dependency else [(1, 80), (2, 123), (3, 90)]
    preload = string("") + struct.pack("<I", len(pointers)) + b"".join(struct.pack("<iq", *pointer) for pointer in pointers)
    preload += struct.pack("<I", 1) + string("authored-dependency") + bytes(1)
    container = (
        string("authored-scene")
        + struct.pack("<II", 0, 1)
        + string("Assets/WholeGame/SceneCase/Room.unity")
        + struct.pack("<iiiq", 0, 0, 0, 0)
        + struct.pack("<iiiqI", 0, 0, 0, 0, 1)
        + string("")
        + struct.pack("<I", 0)
        + struct.pack("<B3xiii", 1, 0, 7, 0)
    )
    bodies = {
        shared: {1: preload, 2: container, 3: b"SHARED", 7: b"FIRST", 8: b"SECOND"},
        main: {1: first, 2: second, 3: b"MAIN", 4: gameobject, 5: occlusion},
    }
    shared_external = ["CAB-A", "Library/unity default resources", "CAB-B"]
    main_external = [shared, "CAB-B", "CAB-A", "Library/unity default resources"]

    def external(path, native=False):
        return {"empty": "", "guid": bytes.fromhex("00000000000000000e00000000000000") if native else bytes(16), "type": 0, "path": path}

    expected_layouts = {
        shared: {
            "types": [typ(115), typ(150), typ(142), typ(43)],
            "scripts": [],
            "externals": [external("archive:/CAB-A/CAB-A"), external("Library/unity default resources", True), external("archive:/CAB-B/CAB-B")],
        },
        main: {
            "types": [{**mono, "script_type": 0}, {**mono, "script_type": 1}, typ(43), typ(1), typ(29)],
            "scripts": [(1, 7), (1, 8)],
            "externals": [
                external("archive:/" + main + "/" + shared),
                external("archive:/CAB-B/CAB-B"),
                external("archive:/CAB-A/CAB-A"),
                external("Library/unity default resources", True),
            ],
        },
    }
    serialized = {}
    for name, physical, type_ids in ((shared, [7, 8, 1, 2, 3], [0, 0, 1, 2, 3]), (main, [1, 2, 3, 4, 5], [0, 1, 2, 3, 4])):
        layout = {"engine": engine, "platform": 13, "trees": True, "ref_types": [], "user": "", **expected_layouts[name]}
        offset, objects = 0, []
        for identity, type_id in zip(physical, type_ids, strict=True):
            offset = (offset + 7) // 8 * 8
            body = bodies[name][identity]
            objects.append({"path_id": identity, "offset": offset, "bytes": len(body), "type_id": type_id})
            offset += len(body)
        layout["objects"] = sorted(objects, key=lambda row: row["path_id"])
        stream = io.BytesIO()
        P.W.write_serialized(stream, layout, lambda row, name=name: io.BytesIO(bodies[name][row["path_id"]]))
        serialized[name] = stream.getvalue()
    expected_bundle = io.BytesIO()
    P.W.write_bundle(
        expected_bundle, [(name, 4, len(data), lambda data=data: io.BytesIO(data)) for name, data in serialized.items()], literal_lz4, engine=engine
    )
    pack = root / "pack"
    pack.mkdir()
    (pack / "objects.bin").write_bytes(b"SHAREDMAIN")
    pack_rows = [
        {"bundle": "authored-scene", "member": name, "path_id": 3, "offset": offset, "bytes": len(body), "sha256": digest(body)}
        for name, offset, body in ((shared, 0, b"SHARED"), (main, 6, b"MAIN"))
    ]
    (pack / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in pack_rows))
    record_pin = "c" * 64
    (pack / "result.json").write_text(
        json.dumps(
            {
                "success": True,
                "input_id": P.M.INPUT_ID,
                "profile_sha256": record_pin,
                "outputs": {name: {"bytes": (pack / name).stat().st_size, "sha256": P.B.sha(pack / name)} for name in ("objects.bin", "index.jsonl")},
            }
        )
    )

    def source_selection(name, identity, original_id, **policy):
        body = bodies[name][identity]
        return {
            "path_id": identity,
            "source": [0, original_id],
            "source_sha256": digest(source_bodies[original_id][1]),
            "bytes": len(body),
            "sha256": digest(body),
            **policy,
        }

    def packed_selection(name):
        body = bodies[name][3]
        return {"path_id": 3, "record": record_pin, "type_source": [0, 91], "bytes": len(body), "sha256": digest(body)}

    def refs(original, body, positions):
        return [
            {"offset": offset, "from": list(struct.unpack_from("<iq", original, offset)), "to": list(struct.unpack_from("<iq", body, offset))}
            for offset in positions
        ]

    profile = {
        "input_id": P.M.INPUT_ID,
        "sources": [{"path": source.name, "member": "CAB-original", "sha256": P.B.sha(source)}],
        "bundle": {
            "name": "authored-scene",
            "bytes": len(expected_bundle.getvalue()),
            "sha256": digest(expected_bundle.getvalue()),
            "scene_path": "Assets/WholeGame/SceneCase/Room.unity",
            "dependencies": ["authored-dependency"],
            "members": [
                {
                    "name": shared,
                    "externals": shared_external,
                    "serialized_sha256": digest(serialized[shared]),
                    "objects": [
                        {"path_id": 1, "type_source": [0, 101], "generate": "PreloadData", "bytes": len(preload), "sha256": digest(preload)},
                        {"path_id": 2, "type_source": [0, 102], "generate": "AssetBundle", "bytes": len(container), "sha256": digest(container)},
                        packed_selection(shared),
                        source_selection(shared, 7, 71),
                        source_selection(shared, 8, 72),
                    ],
                },
                {
                    "name": main,
                    "externals": main_external,
                    "serialized_sha256": digest(serialized[main]),
                    "objects": [
                        source_selection(main, 1, 81, references=refs(original_first, first, [16, 28, 40, 52])),
                        source_selection(main, 2, 82, references=refs(original_second, second, [16, 28, 40])),
                        packed_selection(main),
                        source_selection(
                            main, 4, 83, **({"inactive_global_owner": "SceneInfo"} if global_owner else {"inactive_map_zone": True}), append_components=[1]
                        ),
                        source_selection(main, 5, 84, clear_static_renderers=2, references=refs(occlusion_without_renderers, occlusion, [16, 36])),
                    ],
                },
            ],
        },
    }
    if preload_dependency:
        profile["bundle"]["preload_dependencies"] = [
            {
                "source": [0, 83],
                "source_sha256": digest(original_gameobject),
                "preload_source": [0, 101],
                "preload_sha256": digest(source_bodies[101][1]),
                "source_pointer": [0, 83],
                "to": [1, 404],
            }
        ]
    if engine != "2021.3.45f2":
        profile["bundle"]["engine"] = engine
    path = root / "scene-profile.json"
    path.write_text(json.dumps(profile))
    return pc, path, profile, pack, bodies, serialized, expected_bundle.getvalue()


def character_master_schema(include_debug=True):
    """Authored native vocabulary plus one retained custom field and debug flag."""
    strings = b"AuthoredValue\0" + (b"isUnkillable\0" if include_debug else b"")
    nodes = [
        struct.pack("<hBBIIiiiQ", 1, 0, 0, 0x80000107, 0x80000037, -1, 0, 0, 0),
        struct.pack("<hBBIIiiiQ", 1, 1, 0, 0x800003A6, 0, 4, 1, 0, 0),
    ]
    if include_debug:
        nodes.append(struct.pack("<hBBIIiiiQ", 1, 1, 0, 0x800003A0, len(b"AuthoredValue\0"), 1, 2, 0x4000, 0))
    return struct.pack("<II", len(nodes), len(strings)) + b"".join(nodes) + strings


def rewrite_managed_source(pc, profile, mutate):
    """Re-pin deliberately changed authored source, so policy admission is tested."""
    source = pc / "source.bundle"
    member = P.B.Bundle(source).member("CAB-source")
    layout = P.W.read_serialized(member)
    bodies = {}
    for row in layout["objects"]:
        member.seek(layout["data_offset"] + row["offset"])
        bodies[row["path_id"]] = P.B.exact(member, row["bytes"])
    mutate(layout, bodies)
    offset = 0
    for row in layout["objects"]:
        offset = (offset + 7) // 8 * 8
        row.update(offset=offset, bytes=len(bodies[row["path_id"]]))
        offset += row["bytes"]
    stream = io.BytesIO()
    P.W.write_serialized(stream, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    source.write_bytes(FIXTURE.bundle([("CAB-source", stream.getvalue(), 4)], True))
    profile["sources"][0]["sha256"] = P.B.sha(source)
    for row in profile["objects"]:
        if "source" in row:
            row["source_sha256"] = digest(bodies[row["source"][1]])


def managed_fixture(root, *, omit_master=False, disable=False, plugin_order=False, master_value=False):
    pc, path, profile, _, original_target = fixture(root)
    source = pc / "source.bundle"
    source_layout = P.W.read_serialized(P.B.Bundle(source).member("CAB-source"))
    target_stream = io.BytesIO(original_target)
    target_stream.size = len(original_target)
    target_layout = P.W.read_serialized(target_stream)
    names = ("CharacterMaster", "RoR2", "RoR2.dll") if omit_master else ("AuthoredBehaviour", "Fixture.Namespace", "Fixture.Assembly")
    if plugin_order:
        names = names[:2] + ("RoR2.dll",)
    script = io.BytesIO()
    P.aligned_string(script, "Different display name")
    script.write(struct.pack("<i", -17))
    hash_offset = script.tell()
    original_hash, derived_hash = bytes(range(16)), bytes(reversed(range(16)))
    script.write(original_hash)
    for value in names:
        P.aligned_string(script, value)
    script.write(b"PRESERVE SCRIPT TAIL")
    source_script = script.getvalue()
    target_script = source_script[:hash_offset] + derived_hash + source_script[hash_offset + 16 :]
    if plugin_order:
        target_script = target_script[: hash_offset - 4] + bytes(4) + target_script[hash_offset:]
    source_behaviour = bytes(range(16)) + struct.pack("<iq", 0, 51) + b"PRESERVE BEHAVIOUR"
    if disable:
        source_behaviour = source_behaviour[:12] + b"\x01\0\0\0" + source_behaviour[16:]
    if omit_master:
        source_behaviour += struct.pack("<I", master_value)
    target_behaviour = source_behaviour[:16] + struct.pack("<iq", 0, 2) + source_behaviour[28:]
    if disable:
        target_behaviour = target_behaviour[:12] + bytes(1) + target_behaviour[13:]
    if omit_master:
        target_behaviour = target_behaviour[:-4]
    behaviour_type = {**typ(114), "script_id": b"AUTHORED-SCRIPT!", "tree": struct.pack("<II", 1, 4) + bytes(32) + b"PC!\0"}
    if omit_master:
        behaviour_type["tree"] = character_master_schema()
    source_layout["types"][0] = behaviour_type
    source_bodies = {51: source_script, 61: source_behaviour}
    for layout in (source_layout, target_layout):
        layout.pop("bytes")
        layout.pop("data_offset")
    source_layout["objects"] = [
        {"path_id": 51, "offset": 0, "bytes": len(source_script), "type_id": 1},
        {"path_id": 61, "offset": (len(source_script) + 7) // 8 * 8, "bytes": len(source_behaviour), "type_id": 0},
    ]
    serialized = io.BytesIO()
    P.W.write_serialized(serialized, source_layout, lambda row: io.BytesIO(source_bodies[row["path_id"]]))
    source.write_bytes(FIXTURE.bundle([("CAB-source", serialized.getvalue(), 4)], True))
    profile["sources"][0]["sha256"] = digest(source.read_bytes())
    selectors = {"script": [0, 51], "behaviour": [0, 61]}
    bodies = {-7: target_behaviour, 1: container_bytes(), 2: target_script}
    for selected in profile["objects"]:
        identity = selected["path_id"]
        selected.update(bytes=len(bodies[identity]), sha256=digest(bodies[identity]))
        if identity != 1:
            selected["source_sha256"] = digest(source_bodies[selected["source"][1]])
            selected["properties_hash"] = selectors
            if omit_master:
                selected["omit_character_master_unkillable"] = True
            if identity == -7:
                selected["references"][0]["offset"] = 16
                if disable:
                    selected["disable_original_behaviour"] = True
            elif plugin_order:
                selected["plugin_import_default_execution_order"] = True
    script_end = (len(target_script) + 7) // 8 * 8
    target_layout["types"][1] = {**behaviour_type, "hash": derived_hash, "script_type": 0}
    if omit_master:
        target_layout["types"][1]["tree"] = character_master_schema(False)
    for row in target_layout["objects"]:
        identity = row["path_id"]
        row.update(bytes=len(bodies[identity]), offset={2: 0, -7: script_end, 1: (script_end + len(target_behaviour) + 7) // 8 * 8}[identity])
    target = io.BytesIO()
    P.W.write_serialized(target, target_layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    bundle = io.BytesIO()
    P.W.write_bundle(bundle, [("CAB-target", 4, len(target.getvalue()), lambda: io.BytesIO(target.getvalue()))], literal_lz4)
    profile["bundle"].update(serialized_sha256=digest(target.getvalue()), sha256=digest(bundle.getvalue()), bytes=len(bundle.getvalue()))
    sdk = root / "sdk"
    sdk.mkdir()
    sdk_path = sdk / "native-resources"
    sdk_tree = struct.pack("<II", 1, 8) + bytes(32) + b"NATIVE!\0"
    sdk_layout = {**source_layout, "types": [{**behaviour_type, "tree": sdk_tree}], "objects": [{"path_id": 73, "offset": 0, "bytes": 4, "type_id": 0}]}
    with sdk_path.open("wb") as stream:
        P.W.write_serialized(stream, sdk_layout, lambda row: io.BytesIO(b"BASE"))
    profile["sdk"] = {"path": sdk_path.name, "sha256": digest(sdk_path.read_bytes()), "path_id": 73}
    path.write_text(json.dumps(profile))
    return pc, path, profile, sdk, names, behaviour_type, sdk_tree, derived_hash, bodies, target.getvalue()


class ObjectProducerTests(unittest.TestCase):
    def test_default_material_uses_pinned_sdk_and_existing_player_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk"
            sdk.mkdir()
            source = sdk / "builtin"
            source.write_bytes(b"SDK-MATERIAL")
            definition = typ(21)
            metadata = {"objects": [{"path_id": 10303, "type_id": 0, "offset": 0, "bytes": source.stat().st_size}], "types": [definition], "data_offset": 0}
            selected = {
                "sdk_source": {"path": "builtin", "sha256": digest(source.read_bytes()), "path_id": 10303},
                "shader_source": [0, 46],
                "references": [{"offset": 0, "from": [0, 46], "to": [0, 114]}],
            }
            helper = Mock()
            helper.shared_default_material.return_value = struct.pack("<iq", 0, 46)
            with (
                patch.object(P.W, "read_serialized", return_value=metadata),
                patch.object(P, "source_record", return_value=(b"ORIGINAL-SHADER", typ(48))),
                patch.object(P, "module", return_value=helper),
            ):
                self.assertEqual(P.default_material(selected, [], sdk, root / "output"), struct.pack("<iq", 0, 114))
            helper.shared_default_material.assert_called_once_with(b"SDK-MATERIAL", definition, b"ORIGINAL-SHADER")

    def test_plugin_import_order_preserves_script_identity_and_derived_hash_in_complete_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, path, profile, sdk, names, _, _, derived, bodies, serialized = managed_fixture(root, plugin_order=True)
            real_module = P.module
            helper = Mock(properties_hash=Mock(return_value=derived))
            with (
                patch.object(P, "module", side_effect=lambda name, location=None: helper if name == "script_identity" else real_module(name, location)),
                patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)),
            ):
                result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("codec"), "pin", sdk=sdk)
            self.assertTrue(result["success"])
            member = P.B.Bundle(root / "produced/payload/authored-target").member("CAB-target")
            self.assertEqual(P.B.exact(member, member.size), serialized)
            offset, actual_names = P.script_fields(bodies[2])
            self.assertEqual(actual_names, names)
            self.assertEqual(bodies[2][offset - 4 : offset], bytes(4))
            self.assertEqual(bodies[2][offset : offset + 16], derived)
            with self.assertRaisesRegex(ValueError, "admitted original DLL script"):
                P.plugin_import_order(bodies[2].replace(b"RoR2.dll", b"Evil.dll"))

    def test_original_preload_admits_only_pinned_gameobject_membership(self):
        gameobject = b"AUTHORED GAMEOBJECT"
        preload = struct.pack("<I", 3) + b"Old\0" + struct.pack("<Iiq", 1, 1, 19)
        for failure, message in (
            (None, None),
            ("object-class", "preload GameObject drift"),
            ("object-hash", "preload GameObject drift"),
            ("preload-class", "scene preload drift"),
            ("preload-hash", "scene preload drift"),
            ("external-index", "external file drift"),
            ("external-member", "relationship drift"),
            ("local-member", "relationship drift"),
            ("membership", "relationship drift"),
            ("identity", "relationship drift"),
            ("duplicate", "relationship drift"),
        ):
            with self.subTest(failure=failure):
                original = preload
                profiles = [{"member": "CAB-scene"}, {"member": "CAB-original-dependency"}]
                dependency = {
                    "source": [1, 19],
                    "source_sha256": digest(gameobject),
                    "preload_source": [0, 1],
                    "preload_sha256": digest(preload),
                    "source_pointer": [1, 19],
                    "to": [2, 91],
                }
                external = "archive:/original/CAB-original-dependency"
                if failure == "external-index":
                    dependency["source_pointer"][0] = 2
                elif failure == "external-member":
                    external = "archive:/original/CAB-unrelated"
                elif failure == "local-member":
                    dependency["source_pointer"][0] = 0
                    original = original[:-12] + struct.pack("<iq", 0, 19)
                elif failure == "membership":
                    original = original[:-12] + struct.pack("<iq", 1, 20)
                elif failure == "identity":
                    dependency["source_pointer"][1] = 20
                    original = original[:-12] + struct.pack("<iq", 1, 20)
                elif failure == "duplicate":
                    original = original[:8] + struct.pack("<Iiqiq", 2, 1, 19, 1, 19)
                dependency["preload_sha256"] = "0" * 64 if failure == "preload-hash" else digest(original)
                if failure == "object-hash":
                    dependency["source_sha256"] = "0" * 64
                sources = []
                for body, kind, identity, externals in (
                    (original, 4 if failure == "preload-class" else 150, 1, [{"path": external}]),
                    (gameobject, 4 if failure == "object-class" else 1, 19, []),
                ):
                    metadata = {"data_offset": 0, "types": [typ(kind)], "externals": externals}
                    objects = {identity: {"offset": 0, "bytes": len(body), "type_id": 0}}
                    sources.append((None, None, io.BytesIO(body), metadata, objects))
                if message:
                    with self.assertRaisesRegex(ValueError, message):
                        P.check_preload_dependencies(sources, profiles, [dependency])
                else:
                    P.check_preload_dependencies(sources, profiles, [dependency])

    def test_original_preload_direct_managed_root_requires_pinned_class_and_membership(self):
        body = b"AUTHORED MANAGED ROOT"
        preload = struct.pack("<IIiq", 0, 1, 1, 19)
        dependency = dict(
            source=[1, 19],
            source_class_id=114,
            source_sha256=digest(body),
            preload_source=[0, 1],
            preload_sha256=digest(preload),
            source_pointer=[1, 19],
            to=[2, 91],
        )
        profiles = [{"member": "CAB-scene"}, {"member": "CAB-root"}]
        sources = [(None, None, None, {"externals": [{"path": "CAB-root"}]}, None)]
        with patch.object(P, "source_record", side_effect=lambda _, selector: (preload, typ(150)) if selector == [0, 1] else (body, typ(114))):
            P.check_preload_dependencies(sources, profiles, [dependency])
            for change in ({"source_class_id": 1}, {"source_sha256": "0" * 64}, {"source_pointer": [1, 20]}, {"transform": {}}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    P.check_preload_dependencies(sources, profiles, [dependency | change])

    def test_original_preload_component_requires_unique_reciprocal_membership(self):
        for kind, class_id, size in (("Rigidbody", 54, 36), ("Transform", 4, 68)):
            self.check_preload_component(kind, class_id, size)

    def check_preload_component(self, kind, class_id, size):
        for failure in (None, "class", "length", "hash", "owner", "member", "index", "duplicate", "pointer"):
            with self.subTest(kind=kind, failure=failure):
                components = [(0, 71), (0, 72), (0, 73), (0, 20)]
                if failure == "duplicate":
                    components[0] = (0, 20)
                gameobject = struct.pack("<I", len(components)) + b"".join(struct.pack("<iq", *p) for p in components)
                rigidbody = struct.pack("<iq", 0, 99 if failure == "owner" else 19) + bytes(size - 12)
                if failure == "length":
                    rigidbody += bytes(4)
                preload = struct.pack("<IIiq", 0, 1, 1, 21 if failure == "pointer" else 20)
                profiles = [{"member": "CAB-scene"}, {"member": "CAB-original"}]
                dependency = {
                    "source": [1, 19],
                    "source_sha256": digest(gameobject),
                    "preload_source": [0, 1],
                    "preload_sha256": digest(preload),
                    "source_pointer": [1, 21 if failure == "pointer" else 20],
                    "to": [2, 91],
                    kind.lower(): {
                        "source": [0 if failure == "member" else 1, 20],
                        "sha256": "0" * 64 if failure == "hash" else digest(rigidbody),
                        "component_index": 2 if failure == "index" else 3,
                    },
                }
                bodies = [
                    {1: (preload, typ(150)), 20: (rigidbody, typ(class_id))},
                    {19: (gameobject, typ(1)), 20: (rigidbody, typ(1 if failure == "class" else class_id))},
                ]
                sources = curve_sources(bodies, profiles)
                sources[0][3]["externals"] = [{"path": "archive:/original/CAB-original"}]
                if failure:
                    with self.assertRaisesRegex(ValueError, kind + "|relationship drift"):
                        P.check_preload_dependencies(sources, profiles, [dependency])
                else:
                    P.check_preload_dependencies(sources, profiles, [dependency])

    def test_original_preload_builtin_membership_without_source_object(self):
        pointers = [(26, identity) for identity in (10001, 10202, 10210)]
        preload = struct.pack("<II", 0, len(pointers)) + b"".join(struct.pack("<iq", *pointer) for pointer in pointers)
        metadata = {"data_offset": 0, "types": [typ(150)], "externals": [{"path": "unused"}] * 25 + [{"path": "archive:/builtin/unity default resources"}]}
        sources = [(None, None, io.BytesIO(preload), metadata, {1: {"offset": 0, "bytes": len(preload), "type_id": 0}})]
        dependencies = [
            {"preload_source": [0, 1], "preload_sha256": digest(preload), "source_pointer": list(pointer), "to": [1, pointer[1]]} for pointer in pointers
        ]
        P.check_preload_dependencies(sources, [{"member": "CAB-scene"}], dependencies)
        dependencies[0]["to"][1] = 999
        with self.assertRaisesRegex(ValueError, "builtin relationship drift"):
            P.check_preload_dependencies(sources, [{"member": "CAB-scene"}], dependencies)
        dependencies[0]["to"][1] = 10001
        metadata["externals"][-1] = {"path": "archive:/builtin/unrelated"}
        with self.assertRaisesRegex(ValueError, "builtin relationship drift"):
            P.check_preload_dependencies(sources, [{"member": "CAB-scene"}], dependencies)

    def test_preload_uses_record_dependencies_in_owning_member_external_order(self):
        members = [
            {"name": "CAB-shared", "externals": ["unity default resources", "unity_builtin_extra"], "objects": [{"path_id": 4, "record": "shader-profile"}]},
            {"name": "CAB-scene", "externals": ["CAB-shared", "unity_builtin_extra", "unity default resources"], "objects": []},
        ]
        packed = {
            ("CAB-shared", 4): (None, {"dependencies": [{"source": {"member": "CAB-original", "path_id": 90, "body_sha256": "original-pin"}, "to": [2, 6]}]})
        }
        body = P.preload_data({"preload_dependencies": [], "dependencies": []}, members[1], members, packed)
        self.assertEqual(body, struct.pack("<IIiqIB", 0, 1, 2, 6, 0, 0))

    def test_complete_scene_retains_original_preload_dependency_beyond_direct_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, path, profile, pack, bodies, _, expected_bundle = scene_fixture(root, preload_dependency=True)
            with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
                result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
            self.assertTrue(result["success"])
            self.assertEqual((root / "produced/payload/authored-scene").read_bytes(), expected_bundle)
            member = P.B.Bundle(root / "produced/payload/authored-scene").member(profile["bundle"]["members"][0]["name"])
            layout = P.W.read_serialized(member)
            preload = next(row for row in layout["objects"] if row["path_id"] == 1)
            member.seek(layout["data_offset"] + preload["offset"])
            body = P.B.exact(member, preload["bytes"])
            self.assertEqual(body, next(iter(bodies.values()))[1])
            count = struct.unpack_from("<I", body, 4)[0]
            self.assertEqual([struct.unpack_from("<iq", body, 8 + 12 * i) for i in range(count)], [(1, 80), (1, 404), (2, 123), (3, 90)])
            for destination in ([0, 404], [4, 404], [1, 0]):
                profile["bundle"]["preload_dependencies"][0]["to"] = destination
                with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, "absent destination"):
                    P.preload_data(profile["bundle"], profile["bundle"]["members"][0], profile["bundle"]["members"])
            profile["bundle"]["preload_dependencies"][0].update(to=[1, 404], source_pointer=[0, 84])
            path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "GameObject relationship drift"):
                P.produce(path, P.B.sha(path), pc, root / "failed", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
            self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])

    def test_character_master_omission_keeps_script_and_behaviour_schema_hashes_consistent(self):
        for master_value in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, _, sdk, names, original_type, sdk_tree, derived, bodies, serialized = managed_fixture(
                    root, omit_master=True, master_value=master_value
                )
                identity = load("authored_script_identity", ROOT / "scripts/lab/script_identity.py")
                helper = Mock(properties_hash=Mock(return_value=derived), tree_nodes=identity.tree_nodes)
                real_module = P.module
                with (
                    patch.object(P, "module", side_effect=lambda name, location=None: helper if name == "script_identity" else real_module(name, location)),
                    patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)),
                ):
                    result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("codec"), "pin", sdk=sdk)
                self.assertTrue(result["success"])
                helper.properties_hash.assert_called_once_with(*names, character_master_schema(False), sdk_tree)
                member = P.B.Bundle(root / "produced/payload/authored-target").member("CAB-target")
                self.assertEqual(P.B.exact(member, member.size), serialized)
                layout = P.W.read_serialized(member)
                mb = next(kind for kind in layout["types"] if kind["class_id"] == 114)
                self.assertEqual(mb, {**original_type, "hash": derived, "script_type": 0, "tree": character_master_schema(False)})
                self.assertEqual([node["name"] for node in identity.tree_nodes(mb["tree"])], ["Base", "AuthoredValue"])
                for row in layout["objects"]:
                    member.seek(layout["data_offset"] + row["offset"])
                    actual = P.B.exact(member, row["bytes"])
                    self.assertEqual(actual, bodies[row["path_id"]])
                    if row["path_id"] == 2:
                        offset, actual_names = P.script_fields(actual)
                        self.assertEqual(actual_names, names)
                        self.assertEqual(actual[offset : offset + 16], derived)

    def test_character_master_omission_rejects_identity_schema_class_and_value_drift(self):
        for failure, message in (
            ("name", "requires original CharacterMaster"),
            ("class", "selectors have wrong classes"),
            ("field", "final field drift"),
            ("field-type", "final field drift"),
            ("field-alignment", "final field drift"),
            ("shared-string", "final field string is shared"),
            ("string-tail", "final field drift"),
            ("value", "final value drift"),
            ("padding", "final value drift"),
            ("policy", "requires original CharacterMaster"),
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, profile, sdk, _, _, _, derived, _, _ = managed_fixture(root, omit_master=True)

                def mutate(layout, bodies):
                    if failure == "name":
                        bodies[51] = bodies[51].replace(b"CharacterMaster", b"AuthoredMasterX")
                    elif failure == "class":
                        layout["types"][0]["class_id"] = 4
                    elif failure in ("field", "field-type", "field-alignment", "shared-string", "string-tail"):
                        tree = layout["types"][0]["tree"]
                        if failure == "field":
                            tree = tree.replace(b"isUnkillable", b"otherFlagXYZ")
                        elif failure == "field-type":
                            tree = bytearray(tree)
                            struct.pack_into("<I", tree, 8 + 2 * 32 + 4, 0x800003A6)
                            tree = bytes(tree)
                        elif failure in ("field-alignment", "shared-string"):
                            tree = bytearray(tree)
                            if failure == "field-alignment":
                                struct.pack_into("<i", tree, 8 + 2 * 32 + 20, 0)
                            else:
                                struct.pack_into("<I", tree, 8 + 32 + 8, len(b"AuthoredValue\0"))
                            tree = bytes(tree)
                        else:
                            tree = bytearray(tree)
                            struct.pack_into("<I", tree, 4, struct.unpack_from("<I", tree, 4)[0] + 5)
                            tree = bytes(tree) + b"TAIL\0"
                        layout["types"][0]["tree"] = tree
                    elif failure in ("value", "padding"):
                        body = bytearray(bodies[61])
                        body[-4 if failure == "value" else -1] = 2 if failure == "value" else 1
                        bodies[61] = bytes(body)

                rewrite_managed_source(pc, profile, mutate)
                if failure == "policy":
                    for selected in profile["objects"]:
                        if "omit_character_master_unkillable" in selected:
                            selected["omit_character_master_unkillable"] = "yes"
                path.write_text(json.dumps(profile))
                identity = load("authored_script_identity", ROOT / "scripts/lab/script_identity.py")
                helper = Mock(properties_hash=Mock(return_value=derived), tree_nodes=identity.tree_nodes)
                real_module = P.module
                with (
                    patch.object(P, "module", side_effect=lambda name, location=None: helper if name == "script_identity" else real_module(name, location)),
                    self.assertRaisesRegex(ValueError, message),
                ):
                    P.produce(path, P.B.sha(path), pc, root / "failed", Path("codec"), "pin", sdk=sdk)
                self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])

    def test_original_behaviour_disable_preserves_all_other_emitted_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, path, _, sdk, _, _, _, derived, bodies, serialized = managed_fixture(root, disable=True)
            original = (pc / "source.bundle").read_bytes()
            helper = Mock(properties_hash=Mock(return_value=derived))
            real_module = P.module
            with (
                patch.object(P, "module", side_effect=lambda name, location=None: helper if name == "script_identity" else real_module(name, location)),
                patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)),
            ):
                result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("codec"), "pin", sdk=sdk)
            self.assertTrue(result["success"])
            emitted = P.B.Bundle(root / "produced/payload/authored-target").member("CAB-target")
            self.assertEqual(P.B.exact(emitted, emitted.size), serialized)
            self.assertEqual(bodies[-7][12:16], bytes(4))
            self.assertEqual(bodies[-7][:12], bytes(range(12)))
            self.assertTrue(bodies[-7].endswith(b"PRESERVE BEHAVIOUR"))
            self.assertEqual((pc / "source.bundle").read_bytes(), original)

    def test_original_behaviour_disable_rejects_class_enabled_padding_and_policy_drift(self):
        for failure in ("class", "disabled", "padding", "policy"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, profile, sdk, _, _, _, _, _, _ = managed_fixture(root, disable=True)

                def mutate(layout, bodies):
                    if failure == "class":
                        layout["types"][0]["class_id"] = 4
                    elif failure in ("disabled", "padding"):
                        body = bytearray(bodies[61])
                        body[12 if failure == "disabled" else 13] = 0 if failure == "disabled" else 1
                        bodies[61] = bytes(body)

                rewrite_managed_source(pc, profile, mutate)
                if failure == "policy":
                    profile["objects"][0]["disable_original_behaviour"] = False
                path.write_text(json.dumps(profile))
                with self.assertRaisesRegex(ValueError, "requires an enabled MonoBehaviour"):
                    P.produce(path, P.B.sha(path), pc, root / "failed", Path("codec"), "pin", sdk=sdk)
                self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])

    def test_managed_properties_are_derived_from_original_identity_and_sdk_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, path, profile, sdk, names, original_type, sdk_tree, derived, bodies, serialized = managed_fixture(root)
            inputs = [pc / "source.bundle", sdk / "native-resources", path]
            before = [item.read_bytes() for item in inputs]
            helper = Mock(properties_hash=Mock(return_value=derived))
            real_module = P.module
            with (
                patch.object(P, "module", side_effect=lambda name, location=None: helper if name == "script_identity" else real_module(name, location)),
                patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)),
            ):
                result = P.produce(path, P.B.sha(path), pc, root / "managed", Path("codec"), "pin", sdk=sdk)
            helper.properties_hash.assert_called_once_with(*names, original_type["tree"], sdk_tree)
            self.assertTrue(result["success"])
            self.assertEqual([item.read_bytes() for item in inputs], before)
            self.assertEqual(set(profile["sdk"]), {"path", "sha256", "path_id"})
            for selected in profile["objects"]:
                if selected["path_id"] != 1:
                    self.assertEqual(selected["properties_hash"], {"script": [0, 51], "behaviour": [0, 61]})
            emitted = P.B.Bundle(root / "managed/payload/authored-target").member("CAB-target")
            self.assertEqual(P.B.exact(emitted, emitted.size), serialized)
            layout = P.W.read_serialized(emitted)
            managed_type = next(row for row in layout["types"] if row["class_id"] == 114)
            self.assertEqual(managed_type, {**original_type, "hash": derived, "script_type": 0})
            for row in layout["objects"]:
                emitted.seek(layout["data_offset"] + row["offset"])
                self.assertEqual(P.B.exact(emitted, row["bytes"]), bodies[row["path_id"]])

    def test_managed_properties_require_pinned_sdk_and_check_inputs_after_production(self):
        for failure, message in (
            ("required", "pinned owner SDK"),
            ("pin", "SDK script metadata drift"),
            ("class", "SDK script base is not MonoBehaviour"),
            ("profile", "require SDK metadata"),
            ("sdk-changed", "SDK script metadata changed during production"),
            ("pc-changed", "original object input changed during production"),
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, profile, sdk, _, _, _, derived, _, _ = managed_fixture(root)
                sdk_path = sdk / "native-resources"
                if failure == "pin":
                    profile["sdk"]["sha256"] = "0" * 64
                elif failure == "class":
                    with sdk_path.open("rb") as stream:
                        stream.size = sdk_path.stat().st_size
                        layout = P.W.read_serialized(stream)
                    layout["types"] = [typ(4)]
                    with sdk_path.open("wb") as stream:
                        P.W.write_serialized(stream, layout, lambda row: io.BytesIO(b"BASE"))
                    profile["sdk"]["sha256"] = digest(sdk_path.read_bytes())
                elif failure == "profile":
                    profile.pop("sdk")
                path.write_text(json.dumps(profile))

                def derive(*args):
                    if failure in ("sdk-changed", "pc-changed"):
                        changed = sdk_path if failure == "sdk-changed" else pc / "source.bundle"
                        with changed.open("ab") as stream:
                            stream.write(b"DRIFT")
                    return derived

                real_module = P.module
                helper = Mock(properties_hash=Mock(side_effect=derive))
                with (
                    patch.object(P, "module", side_effect=lambda name, location=None: helper if name == "script_identity" else real_module(name, location)),
                    patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)),
                    self.assertRaisesRegex(ValueError, message),
                ):
                    P.produce(path, P.B.sha(path), pc, root / "failed", Path("codec"), "pin", sdk=None if failure == "required" else sdk)
                receipt = json.loads((root / "failed/result.json").read_text())
                self.assertFalse(receipt["success"])
                self.assertIn(message, receipt["error"])

    def test_complete_two_member_scene_preserves_scripts_dependencies_and_pack_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, path, profile, pack, bodies, serialized, expected_bundle = scene_fixture(root)
            before = P.B.sha(pc / "original.bundle")
            with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
                result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
            self.assertTrue(result["success"])
            self.assertEqual(result["objects"], 10)
            self.assertEqual(result["object_bytes"], sum(len(body) for member in bodies.values() for body in member.values()))
            self.assertEqual((root / "produced/payload/authored-scene").read_bytes(), expected_bundle)
            emitted = P.B.Bundle(root / "produced/payload/authored-scene")
            self.assertEqual(list(emitted.members), list(serialized))
            self.assertEqual([row[2] for row in emitted.members.values()], [4, 4])
            for name, expected in serialized.items():
                member = emitted.member(name)
                self.assertEqual(P.B.exact(member, member.size), expected)
            layouts = json.loads((root / "produced/layout.json").read_text())["members"]
            self.assertEqual([row["name"] for row in layouts], list(serialized))
            self.assertEqual(layouts[0]["scripts"], [])
            self.assertEqual(layouts[1]["scripts"], [[1, 7], [1, 8]])
            self.assertEqual(result["serialized_sha256"], {name: digest(data) for name, data in serialized.items()})
            rows = [json.loads(line) for line in (root / "produced/index.jsonl").read_text().splitlines()]
            self.assertEqual(
                [(row["member"], row["path_id"]) for row in rows], [(name, identity) for name, member in bodies.items() for identity in sorted(member)]
            )
            packed = (root / "produced/objects.bin").read_bytes()
            for row in rows:
                self.assertEqual(packed[row["offset"] : row["offset"] + row["bytes"]], bodies[row["member"]][row["path_id"]])
            self.assertEqual(P.B.sha(pc / "original.bundle"), before)

    def test_scene_mapzone_and_generated_native_types_are_checked(self):
        for failure, message in (
            ("policy", "active original GameObject"),
            ("class", "active original GameObject"),
            ("preload", "original PreloadData type"),
            ("bundle", "original AssetBundle type"),
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, profile, pack, _, _, _ = scene_fixture(root)
                shared, main = profile["bundle"]["members"]
                owner = next(row for row in main["objects"] if row["path_id"] == 4)
                if failure == "policy":
                    owner["inactive_map_zone"] = False
                elif failure == "class":
                    owner.pop("append_components")
                    owner.update(source=[0, 91], source_sha256=digest(b"ORIGINAL-MESH"))
                elif failure == "preload":
                    shared["objects"][0]["type_source"] = [0, 102]
                else:
                    shared["objects"][1]["type_source"] = [0, 101]
                path.write_text(json.dumps(profile))
                with self.assertRaisesRegex(ValueError, message):
                    P.produce(path, P.B.sha(path), pc, root / "failed", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
                self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])

    def test_named_global_owner_suppression_emits_the_complete_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, path, profile, pack, _, _, expected = scene_fixture(root, global_owner=True)
            with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
                result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
            self.assertTrue(result["success"])
            self.assertEqual((root / "produced/payload/authored-scene").read_bytes(), expected)

    def test_retained_legacy_engine_is_preserved_in_both_headers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, path, profile, pack, _, _, expected = scene_fixture(root, engine="2021.3.33f1")
            with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
                result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
            self.assertTrue(result["success"])
            self.assertEqual((root / "produced/payload/authored-scene").read_bytes(), expected)
            emitted = P.B.Bundle(root / "produced/payload/authored-scene")
            for member in emitted.members:
                self.assertEqual(P.W.read_serialized(emitted.member(member))["engine"], "2021.3.33f1")

    def test_global_owner_suppression_checks_original_identity_and_active_tail(self):
        for name in ("SceneInfo", "Director", "GameManager", "RoR2Application"):
            encoded = name.encode()
            original = struct.pack("<IiqII", 1, 0, 713, 9, len(encoded)) + encoded + bytes(-len(encoded) % 4) + struct.pack("<HB", 17, 1)
            self.assertEqual(P.deactivate_global_owner(original, name), original[:-1] + bytes(1))
            for body, selected in (
                (original, "Other"),
                (original, "Director" if name != "Director" else "SceneInfo"),
                (original[:-1] + bytes(1), name),
                (original + bytes(1), name),
            ):
                with self.subTest(name=name, selected=selected), self.assertRaises(ValueError):
                    P.deactivate_global_owner(body, selected)

    def test_original_windows_bundle_copy_needs_no_codec_or_comparison_supplier(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            body = FIXTURE.bundle([("CAB-authored", b"OWNER ORIGINAL", 0)], True)
            source = pc / "original.bundle"
            source.write_bytes(body)
            profile = {"input_id": P.M.INPUT_ID, "original_bundle": {"path": source.name, "bytes": len(body), "sha256": digest(body)}}
            path = root / "copy-profile.json"
            path.write_text(json.dumps(profile))
            result = P.produce(path, P.B.sha(path), pc, root / "copied", None, None)
            self.assertTrue(result["success"])
            self.assertEqual((root / "copied/payload/windows-shaders.bundle").read_bytes(), body)
            self.assertEqual(result["outputs"]["payload/windows-shaders.bundle"], {"bytes": len(body), "sha256": digest(body)})
            self.assertEqual(source.read_bytes(), body)
            with self.assertRaisesRegex(ValueError, "outside original"):
                P.produce(path, P.B.sha(path), pc, pc / "nested", None, None)
            source.write_bytes(body + b"DRIFT")
            with self.assertRaisesRegex(ValueError, "input drift"):
                P.produce(path, P.B.sha(path), pc, root / "drift", None, None)
            self.assertFalse((root / "drift").exists())

    def test_original_bundle_copy_keeps_a_failed_receipt_when_source_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            source = pc / "original.bundle"
            source.write_bytes(b"ORIGINAL")
            profile = {"input_id": P.M.INPUT_ID, "original_bundle": {"path": source.name, "bytes": 8, "sha256": digest(b"ORIGINAL")}}
            path = root / "profile.json"
            path.write_text(json.dumps(profile))
            copyfile = P.shutil.copyfile

            def drift(original, destination):
                copyfile(original, destination)
                original.write_bytes(b"MUTATION")

            with patch.object(P.shutil, "copyfile", side_effect=drift), self.assertRaisesRegex(ValueError, "changed during"):
                P.produce(path, P.B.sha(path), pc, root / "failed", None, None)
            self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])

    def test_audio_component_omission_preserves_order_and_every_other_gameobject_byte(self):
        suffix = b"NAME-LAYER-TAG-AND-ACTIVE"
        original = struct.pack("<Iiqiqiq", 3, 0, 71, 0, -19, 0, 48) + suffix
        self.assertEqual(P.remove_components(original, [{"index": 1, "path_id": -19}]), struct.pack("<Iiqiq", 2, 0, 71, 0, 48) + suffix)
        for removals in ([{"index": 1, "path_id": -20}], [{"index": 3, "path_id": 48}], [{"index": 1, "path_id": -19}] * 2):
            with self.subTest(removals=removals), self.assertRaises(ValueError):
                P.remove_components(original, removals)
        with self.assertRaisesRegex(ValueError, "truncated"):
            P.remove_components(original[:10], [])

    def test_scene_array_policies_reject_wrong_source_classes_and_relationships(self):
        for failure, message in (
            ("append-class", "component addition requires"),
            ("append-missing", "existing produced components"),
            ("occlusion-class", "original OcclusionCullingSettings"),
            ("occlusion-count", "static-renderer array drift"),
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, profile, pack, _, _, _ = scene_fixture(root)
                owner, occlusion = profile["bundle"]["members"][1]["objects"][-2:]
                if failure == "append-class":
                    owner.pop("inactive_map_zone")
                    owner.update(source=[0, 91], source_sha256=digest(b"ORIGINAL-MESH"))
                elif failure == "append-missing":
                    owner["append_components"] = [999]
                elif failure == "occlusion-class":
                    occlusion.update(source=[0, 91], source_sha256=digest(b"ORIGINAL-MESH"))
                else:
                    occlusion["clear_static_renderers"] = 3
                path.write_text(json.dumps(profile))
                with self.assertRaisesRegex(ValueError, message):
                    P.produce(path, P.B.sha(path), pc, root / "failed", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
                self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])

    def test_android_builtin_sprite_external_uses_native_resource_identity(self):
        layout, _ = P.make_layout({"externals": ["Resources/unity_builtin_extra", "CAB-external", "Library/unity default resources"]}, [])
        self.assertEqual(
            layout["externals"][0], {"empty": "", "guid": bytes.fromhex("00000000000000000f00000000000000"), "type": 0, "path": "Resources/unity_builtin_extra"}
        )
        self.assertEqual(layout["externals"][1]["path"], "archive:/CAB-external/CAB-external")
        self.assertEqual(layout["externals"][1]["guid"], bytes(16))
        self.assertEqual(
            layout["externals"][2],
            {"empty": "", "guid": bytes.fromhex("00000000000000000e00000000000000"), "type": 0, "path": "Library/unity default resources"},
        )

    def test_complete_bundle_uses_produced_records_and_resource_positions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, profile, pack, _, _, serialized = packed_fixture(root)
            before = P.B.sha(pc / "source.bundle")
            with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
                result = P.produce(profile, P.B.sha(profile), pc, root / "complete", Path("codec"), "pin", [(pack, P.B.sha(pack / "result.json"))])
            self.assertTrue(result["success"])
            self.assertEqual(result["record_packs"], {"a" * 64: P.B.sha(pack / "result.json")})
            emitted = P.B.Bundle(root / "complete/payload/authored-target")
            self.assertEqual(P.B.exact(emitted.member("CAB-target"), len(serialized)), serialized)
            self.assertEqual(P.B.exact(emitted.member("CAB-target.resS"), 16), bytes(8) + b"AUTHORED")
            self.assertEqual(P.B.sha(pc / "source.bundle"), before)

    def test_pack_receipts_outputs_identities_and_extents_are_checked(self):
        for failure in ("receipt", "failed", "profile", "output", "extent", "missing", "duplicate", "foreign-resource"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, profile_path, pack, profile, row, _ = packed_fixture(root)
                receipt = json.loads((pack / "result.json").read_text())
                if failure == "failed":
                    receipt["success"] = False
                elif failure == "profile":
                    receipt["profile_sha256"] = "b" * 64
                elif failure == "extent":
                    row["offset"] = 100
                elif failure == "missing":
                    row["member"] = "CAB-another"
                elif failure == "foreign-resource":
                    row["resource"]["stream"]["path"] = "archive:/CAB-another/CAB-target.resS"
                lines = [row] * (2 if failure == "duplicate" else 1)
                (pack / "index.jsonl").write_text("".join(json.dumps(item) + "\n" for item in lines))
                receipt["outputs"]["index.jsonl"] = {"bytes": (pack / "index.jsonl").stat().st_size, "sha256": P.B.sha(pack / "index.jsonl")}
                (pack / "result.json").write_text(json.dumps(receipt))
                pin = P.B.sha(pack / "result.json")
                if failure == "receipt":
                    pin = "0" * 64
                if failure == "output":
                    (pack / "resources.bin").write_bytes(b"DRIFTING")
                with self.assertRaises(ValueError):
                    P.produce(profile_path, P.B.sha(profile_path), pc, root / "failed", Path("codec"), "pin", [(pack, pin)])
                self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])

    def test_multiple_rooted_assets_preserve_shared_preloads_and_partition_offsets(self):
        selected = {
            "name": "two-assets",
            "dependencies": [],
            "assets": [
                {"path": "Assets/Second.asset", "root": 8, "preload": [[1, 20], [0, -4], [0, 8]]},
                {"path": "Assets/First.asset", "root": -4, "preload": [[0, -4]]},
            ],
        }
        body = P.asset_bundle(selected, [-4, 8])
        stream = io.BytesIO(body)

        def string():
            size = struct.unpack("<I", stream.read(4))[0]
            value = stream.read(size)
            stream.read(-stream.tell() % 4)
            return value

        self.assertEqual(string(), b"two-assets")
        self.assertEqual(struct.unpack("<I", stream.read(4))[0], 4)
        self.assertEqual([struct.unpack("<iq", stream.read(12)) for _ in range(4)], [(1, 20), (0, -4), (0, 8), (0, -4)])
        self.assertEqual(struct.unpack("<I", stream.read(4))[0], 2)
        self.assertEqual(string(), b"assets/first.asset")
        self.assertEqual(struct.unpack("<iiiq", stream.read(20)), (3, 1, 0, -4))
        self.assertEqual(string(), b"assets/second.asset")
        self.assertEqual(struct.unpack("<iiiq", stream.read(20)), (0, 3, 0, 8))
        with self.assertRaisesRegex(ValueError, "absent local"):
            P.asset_bundle(selected, [8])

    def test_dummy_shader_keeps_original_keywords_and_material_values(self):
        prefix = struct.pack("<I", 4) + b"Demo" + struct.pack("<iq", 2, 77)
        first = struct.pack("<I", 3) + b"ONE\0"
        second = struct.pack("<I", 3) + b"TWO\0"
        third = struct.pack("<I", 5) + b"THREE\0\0\0"
        suffix = bytes(range(64))
        original = prefix + struct.pack("<I", 2) + first + second + struct.pack("<I", 1) + third + suffix
        expected = prefix + struct.pack("<II", 0, 3) + first + second + third + suffix
        self.assertEqual(P.demote_material_keywords(original), expected)
        self.assertEqual(len(original), len(expected))
        self.assertEqual(P.demote_material_keywords(expected), expected)
        with self.assertRaises((ValueError, EOFError)):
            P.demote_material_keywords(prefix + struct.pack("<I", 100000))

    def test_container_preload_partition_order_is_explicit(self):
        selected = {"name": "authored-bundle", "asset": "Assets/Authored.prefab", "root": 7, "external_objects": [[2, 91], [1, -18]], "dependencies": []}
        for external_first in (False, True):
            with self.subTest(external_first=external_first):
                selected["external_preload_first"] = external_first
                body = P.asset_bundle(selected, [7, -6])
                size = struct.unpack_from("<I", body)[0]
                offset = (4 + size + 3) // 4 * 4
                count = struct.unpack_from("<I", body, offset)[0]
                self.assertEqual(count, 4)
                actual = [struct.unpack_from("<iq", body, offset + 4 + 12 * index) for index in range(count)]
                local, external = [(0, -6), (0, 7)], [(2, 91), (1, -18)]
                self.assertEqual(actual, external + local if external_first else local + external)

    def test_complete_source_only_pack_and_source_derived_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, profile, _, bodies, expected = fixture(root)
            before = P.B.sha(pc / "source.bundle")
            result = produce(profile, P.B.sha(profile), pc, root / "produced")
            self.assertTrue(result["success"])
            self.assertEqual(result["objects"], 3)
            self.assertEqual(result["serialized_sha256"], digest(expected))
            self.assertEqual((root / "produced/objects.bin").read_bytes(), b"".join(bodies[key] for key in sorted(bodies)))
            layout = json.loads((root / "produced/layout.json").read_text())
            self.assertEqual(layout["data_offset"], 4096)
            self.assertEqual(layout["bytes"], len(expected))
            self.assertEqual(layout["types"][0]["tree"], typ(115)["tree"].hex())
            self.assertEqual(P.B.sha(pc / "source.bundle"), before)
            emitted = P.B.Bundle(root / "produced/payload/authored-target").member("CAB-target")
            self.assertEqual(P.B.exact(emitted, emitted.size), expected)
            rows = [json.loads(line) for line in (root / "produced/index.jsonl").read_text().splitlines()]
            self.assertEqual([row["path_id"] for row in rows], [-7, 1, 2])
            self.assertEqual([row["bundle"] for row in rows], ["authored-target"] * 3)
            with self.assertRaisesRegex(ValueError, "new and outside"):
                produce(profile, P.B.sha(profile), pc, root / "produced")
            with self.assertRaisesRegex(ValueError, "profile drift"):
                produce(profile, "0" * 64, pc, root / "drift-profile")

    def test_failed_source_and_destination_admission_are_receipted(self):
        for failure in ("bundle", "body", "destination", "structure"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, profile, _, _ = fixture(root)
                if failure == "bundle":
                    (pc / "source.bundle").write_bytes(b"input drift")
                elif failure == "body":
                    profile["objects"][0]["source_sha256"] = "0" * 64
                elif failure == "destination":
                    profile["objects"][0]["sha256"] = "0" * 64
                else:
                    profile["bundle"]["serialized_sha256"] = "0" * 64
                path.write_text(json.dumps(profile))
                with self.assertRaises(ValueError):
                    produce(path, P.B.sha(path), pc, root / "failed")
                receipt = json.loads((root / "failed/result.json").read_text())
                self.assertFalse(receipt["success"])
                self.assertIn("error", receipt)

    def test_checked_remap_rejects_overlaps_escape_and_wrong_identity(self):
        body = b"KEEP" + struct.pack("<iq", 4, -500) + b"TAIL"
        row = {"offset": 4, "from": [4, -500], "to": [0, 123]}
        self.assertEqual(P.remap(body, [row]), b"KEEP" + struct.pack("<iq", 0, 123) + b"TAIL")
        for refs in ([row, row], [{**row, "offset": -4}], [{**row, "offset": 8}], [{**row, "offset": 5}], [{**row, "from": [4, -501]}]):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                P.remap(body, refs)

    def test_missing_script_and_duplicate_identity_refuse_layout(self):
        selected = {"externals": []}
        mb = {**typ(114), "script_id": bytes(16)}
        with self.assertRaisesRegex(ValueError, "script absent"):
            P.make_layout(selected, [{"path_id": 3, "type": mb, "body": bytes(16) + struct.pack("<iq", 0, 7)}])
        row = {"path_id": 8, "type": typ(4), "body": b"AUTHORED"}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            P.make_layout(selected, [row, row])

    def test_scene_null_script_preserves_native_type_without_shifting_script_table(self):
        null_type = {**typ(114), "hash": bytes(16), "script_id": bytes(16)}
        for failure in (None, "length", "hash", "script_id", "script_type", "dangling"):
            with self.subTest(failure=failure):
                original_type = copy.deepcopy(null_type)
                body = bytes(32)
                if failure == "length":
                    body += bytes(4)
                elif failure in ("hash", "script_id"):
                    original_type[failure] = bytes([1]) * 16
                elif failure == "script_type":
                    original_type["script_type"] = 0
                elif failure == "dangling":
                    body = bytes(16) + struct.pack("<iq", 0, 999) + bytes(4)
                records = [
                    {"path_id": 8, "type": original_type, "body": body},
                    {"path_id": 9, "type": {**null_type, "script_type": 99}, "body": bytes(16) + struct.pack("<iq", 1, 12) + bytes(4)},
                ]
                if failure:
                    with self.assertRaisesRegex(ValueError, "null-script|script absent"):
                        P.make_layout({"externals": ["CAB-scripts"]}, records, ["CAB-scene"])
                else:
                    layout, bodies = P.make_layout({"externals": ["CAB-scripts"]}, records, ["CAB-scene"])
                    self.assertEqual(layout["scripts"], [(1, 12)])
                    self.assertEqual(layout["types"][0], null_type)
                    self.assertEqual(layout["types"][1]["script_type"], 0)
                    self.assertEqual(bodies[8], bytes(32))
                    self.assertEqual(records[0]["type"], null_type)

    def test_scene_null_script_components_retain_individual_type_slots(self):
        null_type = {**typ(114), "hash": bytes(16), "script_id": bytes(16)}
        records = [
            {"path_id": 12, "type": null_type, "body": bytes(32)},
            {"path_id": 8, "type": typ(4), "body": b"FIRST"},
            {"path_id": 9, "type": null_type, "body": bytes(32)},
            {"path_id": 10, "type": typ(4), "body": b"SECOND"},
            {"path_id": 11, "type": {**null_type, "script_type": 99}, "body": bytes(16) + struct.pack("<iq", 1, 42) + bytes(4)},
        ]
        layout, bodies = P.make_layout({"externals": ["CAB-scripts"]}, records, ["CAB-scene"])
        self.assertEqual(layout["types"], [typ(4), null_type, {**null_type, "script_type": 0}, null_type])
        self.assertEqual([(row["path_id"], row["type_id"]) for row in layout["objects"]], [(8, 0), (9, 1), (10, 0), (11, 2), (12, 3)])
        self.assertEqual(layout["scripts"], [(1, 42)])
        self.assertEqual(bodies, {row["path_id"]: row["body"] for row in records})
        self.assertEqual(null_type["script_type"], -1)

    def test_script_table_and_type_indices_follow_produced_script_order(self):
        mono = {**typ(114), "script_id": bytes(16), "script_type": 99}
        body = bytes(16) + struct.pack("<iq", 0, 12) + b"PRESERVED"
        records = [
            {"path_id": 8, "type": mono, "body": body},
            {"path_id": 12, "type": typ(115), "body": b"SECOND"},
            {"path_id": -8, "type": typ(115), "body": b"FIRST"},
        ]
        layout, bodies = P.make_layout({"externals": []}, records)
        self.assertEqual(layout["scripts"], [(0, -8), (0, 12)])
        self.assertEqual(layout["types"][1]["script_type"], 1)
        self.assertEqual(mono["script_type"], 99)
        self.assertEqual(bodies[8], body)
        self.assertEqual([(row["path_id"], row["offset"]) for row in layout["objects"]], [(-8, 0), (8, 16), (12, 8)])


CURVE_RECORD_FIXTURE = load("curve_record_fixture", ROOT / "tests/test_phone_record_producer.py")
CURVE_MESH_FIXTURE = CURVE_RECORD_FIXTURE.F


def curve_type(body, node, class_id):
    value = CURVE_RECORD_FIXTURE.serialized(body, node, class_id)
    source = io.BytesIO(value)
    source.size = len(value)
    return P.W.read_serialized(source)["types"][0]


def curve_sources(records, profiles):
    """Build genuine serialized members consumed by unchanged source_record."""
    result = []
    for member_records, profile in zip(records, profiles):
        types, objects, bodies, offset = [], [], {}, 0
        for identity, (body, typ) in sorted(member_records.items()):
            types.append(typ)
            offset = (offset + 7) // 8 * 8
            objects.append(dict(path_id=identity, offset=offset, bytes=len(body), type_id=len(types) - 1))
            bodies[identity] = body
            offset += len(body)
        layout = dict(
            engine="2021.3.45f2",
            platform=19,
            trees=True,
            types=types,
            objects=objects,
            scripts=[],
            externals=profile.get("externals", []),
            ref_types=[],
            user="",
        )
        serialized = io.BytesIO()
        P.W.write_serialized(serialized, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
        serialized.size = len(serialized.getvalue())
        metadata = P.W.read_serialized(serialized)
        result.append((None, None, serialized, metadata, {r["path_id"]: r for r in metadata["objects"]}))
    return result


def bezier_fixture(*, endpoint=True):
    F = CURVE_MESH_FIXTURE
    u32 = lambda name: F.node(name, 4, kind="UInt32")
    vec3 = lambda name: F.node(name, children=[F.node(axis, 4, kind="float") for axis in ("x", "y", "z")])
    ptr = lambda name: F.node(name, 12, kind="PPtr<Object>")
    node = F.node(
        "Base", children=[ptr("m_GameObject"), u32("retainedBefore"), F.array("m_Positions", vec3("data")), ptr("retainedMaterial"), u32("retainedAfter")]
    )
    line = struct.pack("<iqII", 0, 1, 0xAABBCCDD, 5) + struct.pack("<15f", *([99.0, 98.0, 97.0] * 5))
    line += struct.pack("<iqI", 7, -1234567890123, 0xFEDCBA98)
    line_type = curve_type(line, node, 120)
    curve_schema = F.node(
        "Base",
        children=[
            ptr("m_GameObject"),
            u32("m_Enabled"),
            ptr("m_Script"),
            F.text("m_Name"),
            vec3("v0"),
            vec3("p1"),
            vec3("v1"),
            ptr("endTransform"),
            F.node("animateBezierWind", 1, kind="UInt8", meta=0x4000),
            vec3("windMagnitude"),
            vec3("windFrequency"),
        ],
    )
    # p0 comes from parent scale+translation: (1,2,3)*(2,3,4)+(10,20,30)=(12,26,42).
    # p1 comes from endpoint (-1,2,3) through the same parent, or its original literal.
    curve = struct.pack("<iqIiqI", 0, 1, 1, 1, 100, 0)
    curve += struct.pack("<9f", 0, 8, 0, 8, 26, 42, 0, 0, 8) + struct.pack("<iq", 0, 40 if endpoint else 0) + bytes(28)
    assert len(curve) == 108
    curve_typ = curve_type(curve, curve_schema, 114)
    go_schema = F.node("Base", children=[F.array("m_Component", ptr("data")), u32("retained")])
    go = struct.pack("<IiqiqiqI", 3, 0, 30, 0, 10, 0, 20, 0x10203040)
    go_type = curve_type(go, go_schema, 1)
    transform_schema = F.node(
        "Base",
        children=[
            ptr("m_GameObject"),
            F.node("m_LocalRotation", children=[F.node(a, 4, kind="float") for a in ("x", "y", "z", "w")]),
            vec3("m_LocalPosition"),
            vec3("m_LocalScale"),
            F.array("m_Children", ptr("data")),
            ptr("m_Father"),
        ],
    )

    def transform(goid, position, scale=(1, 1, 1), parent=0):
        return struct.pack("<iq4f3f3fIiq", 0, goid, 0, 0, 0, 1, *position, *scale, 0, 0, parent)

    start = transform(1, (1, 2, 3), parent=31)
    parent = transform(3, (10, 20, 30), (2, 3, 4))
    end = transform(2, (-1, 2, 3), parent=31)
    transform_typ = curve_type(start, transform_schema, 4)

    def text(value):
        raw = value.encode()
        return struct.pack("<I", len(raw)) + raw + bytes(-len(raw) % 4)

    script = text("BezierCurveLine") + struct.pack("<i", 1600) + bytes(range(16)) + text("BezierCurveLine") + text("") + text("RoR2.dll")
    script_schema = F.node(
        "Base", children=[F.text("m_Name"), u32("m_ExecutionOrder"), F.node("hash", 16), F.text("m_ClassName"), F.text("m_Namespace"), F.text("m_AssemblyName")]
    )
    script_typ = curve_type(script, script_schema, 115)
    records = [
        {1: (go, go_type), 10: (line, line_type), 20: (curve, curve_typ), 30: (start, transform_typ), 31: (parent, transform_typ), 40: (end, transform_typ)},
        {100: (script, script_typ)},
    ]
    profiles = [
        dict(member="CAB-authored-line", externals=[dict(empty="", guid=bytes(16), type=0, path="archive:/CAB-authored-script/CAB-authored-script")]),
        dict(member="CAB-authored-script"),
    ]
    return records, profiles


class BezierCurveLineTests(unittest.TestCase):
    # This is a closed polynomial fixture, not a second evaluation of helper Lerp.
    # P(t)=(12-4t, 26+8t(1-t), 42+8t(1-t)), t=0,1/4,1/2,3/4,1.
    EXPECTED = struct.pack("<15f", 12, 26, 42, 11, 27.5, 43.5, 10, 28, 44, 9, 27.5, 43.5, 8, 26, 42)

    def result(self, records, profiles, body=None):
        source = curve_sources(records, profiles)
        return P.rebuild_bezier_line(records[0][10][0] if body is None else body, source, profiles, [0, 10], [0, 20])

    def mutate(self, records, identity, offset, data, member=0):
        body, typ = records[member][identity]
        value = bytearray(body)
        value[offset : offset + len(data)] = data
        records[member][identity] = bytes(value), typ

    def test_original_transform_hierarchy_and_endpoint_rebuild_known_polynomial_only(self):
        records, profiles = bezier_fixture()
        before = copy.deepcopy(records)
        result = self.result(records, profiles)
        self.assertEqual(result[20:80], self.EXPECTED)
        self.assertEqual(result[:20], records[0][10][0][:20])
        self.assertEqual(result[80:], records[0][10][0][80:])
        self.assertEqual(struct.unpack_from("<iq", result, 80), (7, -1234567890123))
        self.assertEqual(records, before)

    def test_captured_wind_evaluates_original_curve_without_geometry_literals(self):
        records, profiles = bezier_fixture()
        self.mutate(records, 20, 80, bytes([1]))
        self.mutate(records, 20, 84, struct.pack("<6f", 0, 2, 0, 0, 0, 0))
        source = curve_sources(records, profiles)
        # sin(pi/2) adds two to each original Y control offset: +4*t*(1-t).
        result = P.rebuild_bezier_line(records[0][10][0], source, profiles, [0, 10], [0, 20], [0, 1.5707963705062866, 0])
        expected = struct.pack("<15f", 12, 26, 42, 11, 28.25, 43.5, 10, 29, 44, 9, 28.25, 43.5, 8, 26, 42)
        self.assertEqual(result[20:80], expected)
        self.assertEqual(result[:20], records[0][10][0][:20])
        self.assertEqual(result[80:], records[0][10][0][80:])

    def test_captured_build_rounding_changes_only_pinned_coordinate(self):
        records, profiles = bezier_fixture()
        body = records[0][10][0]
        source = curve_sources(records, profiles)
        bits = struct.unpack("<I", struct.pack("<f", 27.5))[0]
        capture = [{"word": 4, "evaluated_bits": bits, "build_bits": bits + 1}]
        result = P.rebuild_bezier_line(body, source, profiles, [0, 10], [0, 20], build_rounding=capture)
        expected = bytearray(self.EXPECTED)
        struct.pack_into("<I", expected, 16, bits + 1)
        self.assertEqual(result[20:80], expected)
        self.assertEqual(result[:20], body[:20])
        self.assertEqual(result[80:], body[80:])
        self.mutate(records, 31, 32, struct.pack("<f", 21))
        with self.assertRaisesRegex(ValueError, "rounding operand drift"):
            P.rebuild_bezier_line(body, curve_sources(records, profiles), profiles, [0, 10], [0, 20], build_rounding=capture)

    def test_null_endpoint_uses_original_literal_p1(self):
        records, profiles = bezier_fixture(endpoint=False)
        self.assertEqual(self.result(records, profiles)[20:80], self.EXPECTED)

    def test_rotated_scaled_parent_rebuilds_known_world_polynomial(self):
        records, profiles = bezier_fixture()
        # Exact half-turn around Z: parent TRS maps (x,y,z) to
        # (10-2x,20-3y,30+4z). Original control offsets stay in world space.
        self.mutate(records, 31, 12, struct.pack("<4f", 0, 0, 1, 0))
        expected = struct.pack("<15f", 8, 14, 42, 9, 15.5, 43.5, 10, 16, 44, 11, 15.5, 43.5, 12, 14, 42)
        self.assertEqual(self.result(records, profiles)[20:80], expected)

    def test_rect_transform_parent_preserves_common_trs(self):
        records, profiles = bezier_fixture()
        body, parent_type = records[0][31]
        records[0][31] = (body + bytes(40), {**parent_type, "class_id": 224})
        self.assertEqual(self.result(records, profiles)[20:80], self.EXPECTED)
        records[0][31] = (body + bytes(40), {**parent_type, "class_id": 54})
        with self.assertRaisesRegex(ValueError, "record class drift"):
            self.result(records, profiles)

    def test_mutated_body_must_equal_original_line(self):
        records, profiles = bezier_fixture()
        body = bytearray(records[0][10][0])
        body[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "original line member"):
            self.result(records, profiles, bytes(body))

    def test_original_source_contract_mutants_are_rejected(self):
        cases = [
            ("curve GO", 20, 0, struct.pack("<iq", 0, 2), "GameObject differs"),
            ("external GO", 20, 0, struct.pack("<iq", 1, 1), "GameObject differs"),
            ("absent line component", 1, 20, struct.pack("<q", 99), "component membership"),
            ("external component", 1, 4, struct.pack("<i", 1), "component membership"),
            ("duplicate curve component", 1, 8, struct.pack("<q", 20), "component membership"),
            ("starting transform backlink", 30, 0, struct.pack("<iq", 0, 999), "GameObject"),
            ("parent cycle", 31, 56, struct.pack("<iq", 0, 30), "parent cycle"),
            ("external parent", 30, 56, struct.pack("<iq", 1, 31), "parent escapes"),
            ("animated wind", 20, 80, bytes([1]), "animated Bezier wind"),
            ("external endpoint", 20, 68, struct.pack("<iq", 1, 40), "endTransform escapes"),
            ("nonfinite source", 20, 32, struct.pack("<f", float("nan")), "nonfinite"),
        ]
        for label, identity, offset, data, error in cases:
            with self.subTest(label=label):
                records, profiles = bezier_fixture()
                self.mutate(records, identity, offset, data)
                with self.assertRaisesRegex(ValueError, error):
                    self.result(records, profiles)

    def test_wrong_operand_classes_cannot_supply_curve_values(self):
        for identity, class_id in [(10, 4), (20, 120), (1, 4), (30, 1), (31, 1), (40, 1)]:
            with self.subTest(identity=identity):
                records, profiles = bezier_fixture()
                body, typ = records[0][identity]
                typ = {**typ, "class_id": class_id}
                # Keep valid serialized type encoding when class_id changes from MonoBehaviour.
                if class_id != 114:
                    typ.pop("script_id", None)
                records[0][identity] = (body, typ)
                with self.assertRaisesRegex(ValueError, "record class|transform differs"):
                    self.result(records, profiles)

    def test_script_class_namespace_and_assembly_are_original_identity(self):
        for original, revised in [(b"BezierCurveLine", b"VezierCurveLine"), (b"RoR2.dll", b"Evil.dll")]:
            with self.subTest(original=original):
                records, profiles = bezier_fixture()
                body, typ = records[1][100]
                records[1][100] = (body.replace(original, revised), typ)
                with self.assertRaisesRegex(ValueError, "script identity differs"):
                    self.result(records, profiles)

    def test_script_must_be_a_unique_original_member_provider(self):
        records, profiles = bezier_fixture()
        profiles[1]["member"] = "CAB-different"
        with self.assertRaisesRegex(ValueError, "script provider differs"):
            self.result(records, profiles)
        records, profiles = bezier_fixture()
        records.append(copy.deepcopy(records[1]))
        profiles.append(copy.deepcopy(profiles[1]))
        with self.assertRaisesRegex(ValueError, "script provider differs"):
            self.result(records, profiles)

    def test_source_array_count_and_curve_schema_are_checked(self):
        records, profiles = bezier_fixture()
        body, typ = records[0][10]
        body = body[:16] + struct.pack("<I", 1) + body[20:32] + body[80:]
        records[0][10] = (body, typ)
        with self.assertRaisesRegex(ValueError, "position array drift"):
            self.result(records, profiles)
        records, profiles = bezier_fixture()
        body, typ = records[0][20]
        typ = {**typ, "tree": typ["tree"].replace(b"windFrequency\0", b"windFrequencX\0")}
        records[0][20] = (body, typ)
        with self.assertRaisesRegex(ValueError, "schema drift"):
            self.result(records, profiles)


def bezier_production_fixture(root):
    pc, path, profile, _, _ = fixture(root)
    records, source_profiles = bezier_fixture()
    source_profiles[0]["member"] = "CAB-source"
    records[0][99] = (b"Original unused container", typ(142))
    sources = curve_sources(records, source_profiles)
    source = pc / "source.bundle"
    source.write_bytes(FIXTURE.bundle([(selected["member"], value[2].getvalue(), 4) for selected, value in zip(source_profiles, sources)], True))
    profile["sources"] = [dict(path=source.name, member=p["member"], sha256=P.B.sha(source)) for p in source_profiles]
    original = records[0][10][0]
    # Retain the original GO field. Relocate only the material dependency after
    # curve reconstruction, proving the helper runs on the original source body.
    output_line = original[:20] + BezierCurveLineTests.EXPECTED + struct.pack("<iq", 1, 88) + original[92:]
    script = records[1][100][0]
    bodies = {-7: output_line, 1: container_bytes(), 2: script}
    aligned = lambda n: (n + 7) // 8 * 8
    line_offset = aligned(len(script))
    container_offset = aligned(line_offset + len(output_line))
    layout = dict(
        engine="2021.3.45f2",
        platform=13,
        trees=True,
        types=[records[1][100][1], records[0][10][1], typ(142)],
        objects=[
            dict(path_id=-7, offset=line_offset, bytes=len(output_line), type_id=1),
            dict(path_id=1, offset=container_offset, bytes=len(bodies[1]), type_id=2),
            dict(path_id=2, offset=0, bytes=len(script), type_id=0),
        ],
        scripts=[(0, 2)],
        externals=[dict(empty="", guid=bytes(16), type=0, path="archive:/CAB-dependency/CAB-dependency")],
        ref_types=[],
        user="",
    )
    serialized = io.BytesIO()
    P.W.write_serialized(serialized, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    bundle = io.BytesIO()
    P.W.write_bundle(bundle, [("CAB-target", 4, len(serialized.getvalue()), lambda: io.BytesIO(serialized.getvalue()))], literal_lz4)
    digest = lambda b: hashlib.sha256(b).hexdigest()
    profile["bundle"].update(serialized_sha256=digest(serialized.getvalue()), sha256=digest(bundle.getvalue()), bytes=len(bundle.getvalue()))
    profile["objects"] = [
        dict(
            path_id=-7,
            source=[0, 10],
            source_sha256=digest(original),
            bezier_curve_line=[0, 20],
            bytes=len(output_line),
            sha256=digest(output_line),
            references=[dict(offset=80, **{"from": [7, -1234567890123], "to": [1, 88]})],
        ),
        dict(path_id=1, type_source=0, bytes=len(bodies[1]), sha256=digest(bodies[1])),
        dict(path_id=2, source=[1, 100], source_sha256=digest(script), bytes=len(script), sha256=digest(script)),
    ]
    path.write_text(json.dumps(profile))
    return pc, path, profile, output_line, bundle.getvalue()


class BezierOwnerProductionTests(unittest.TestCase):
    def test_full_owner_reconstructs_before_pointer_relocation_and_persists_exact_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pc, path, profile, line, bundle = bezier_production_fixture(root)
            with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
                result = P.produce(path, P.B.sha(path), pc, root / "produced", Path("authored-codec"), "authored-codec-pin")
            self.assertTrue(result["success"])
            self.assertEqual((root / "produced/payload/authored-target").read_bytes(), bundle)
            index = [json.loads(l) for l in (root / "produced/index.jsonl").read_text().splitlines()]
            row = next(r for r in index if r["path_id"] == -7)
            data = (root / "produced/objects.bin").read_bytes()[row["offset"] : row["offset"] + row["bytes"]]
            self.assertEqual(data, line)
            self.assertEqual(data[20:80], BezierCurveLineTests.EXPECTED)
            self.assertEqual(struct.unpack_from("<iq", data, 80), (1, 88))


LEGACY_IDENTITY = P.module("script_identity", ROOT / "scripts/lab/script_identity.py")


def legacy_policy_fixture():
    def curve(name, editor):
        children = [CURVE_MESH_FIXTURE.node(n, 4, kind="float") for n in ["time", "value", "inSlope", "outSlope"]]
        if editor:
            children.append(CURVE_MESH_FIXTURE.node("tangentMode", 4, kind="int"))
        children.extend(
            [
                CURVE_MESH_FIXTURE.node("weightedMode", 4, kind="int"),
                CURVE_MESH_FIXTURE.node("inWeight", 4, kind="float"),
                CURVE_MESH_FIXTURE.node("outWeight", 4, kind="float"),
            ]
        )
        key = CURVE_MESH_FIXTURE.node("data", 32 if editor else 28, children=children, kind="Keyframe")
        return CURVE_MESH_FIXTURE.node(
            name,
            kind="AnimationCurve",
            children=[
                CURVE_MESH_FIXTURE.array("m_Curve", key),
                *[CURVE_MESH_FIXTURE.node(n, 4, kind="int") for n in ["m_PreInfinity", "m_PostInfinity", "m_RotationOrder"]],
            ],
        )

    boolean = lambda name: CURVE_MESH_FIXTURE.node(name, 1, kind="UInt8", meta=0x4000)
    source = CURVE_MESH_FIXTURE.node(
        "Base",
        kind="MonoBehaviour",
        children=[
            curve("alphaCurve", False),
            boolean("disableOnEnd"),
            boolean("disableObjectOnEnd"),
            boolean("resetOnEnable"),
            CURVE_MESH_FIXTURE.node("time", 4, kind="float"),
            CURVE_MESH_FIXTURE.node("retained", 12, kind="PPtr<Object>"),
        ],
    )
    sdk = CURVE_MESH_FIXTURE.node("Base", kind="MonoBehaviour", children=[CURVE_MESH_FIXTURE.text("m_EditorClassIdentifier"), curve("m_Falloff", True)])
    body = struct.pack("<I4fI2f3I", 1, 0, 1, 2, 3, 0, 0.25, 0.75, 2, 2, 4) + bytes(12) + struct.pack("<fiq", 3.5, 7, -1234567)

    def tree(body, node):
        raw = CURVE_RECORD_FIXTURE.serialized(body, node, 114)
        stream = io.BytesIO(raw)
        stream.size = len(raw)
        md = P.W.read_serialized(stream)
        return md["types"][0]["tree"]

    sdkbody = bytes(4) + struct.pack("<I4fII2f3I", 1, 0, 1, 2, 3, 0, 0, 0.25, 0.75, 2, 2, 4)
    return body, tree(body, source), tree(sdkbody, sdk)


class LegacyBarrierPolicyTests(unittest.TestCase):
    def test_only_zero_additions_are_removed_and_tail_and_runtime_curve_are_retained(self):
        body, tree, sdk = legacy_policy_fixture()
        result, projected = P.legacy_animate_fields(body, tree, LEGACY_IDENTITY)
        self.assertEqual(result, body[:48] + body[56:])
        self.assertEqual(result[-16:], body[-16:])
        self.assertEqual(P.legacy_animate_fields(result, projected, LEGACY_IDENTITY), (result, projected))
        fields = [n["name"] for n in LEGACY_IDENTITY.tree_nodes(projected) if n["level"] == 1]
        self.assertEqual(fields, ["alphaCurve", "disableOnEnd", "time", "retained"])
        hashed = P.legacy_animate_hash_tree(projected, sdk, LEGACY_IDENTITY)
        self.assertEqual(next((n["size"] for n in LEGACY_IDENTITY.tree_nodes(projected) if n["type"] == "Keyframe")), 28)
        self.assertEqual(next((n["size"] for n in LEGACY_IDENTITY.tree_nodes(hashed) if n["type"] == "Keyframe")), 32)
        self.assertEqual(sum((n["name"] == "tangentMode" for n in LEGACY_IDENTITY.tree_nodes(hashed))), 1)
        self.assertNotEqual(
            LEGACY_IDENTITY.properties_hash("AnimateShaderAlpha", "RoR2", "RoR2.dll", projected, sdk),
            LEGACY_IDENTITY.properties_hash("AnimateShaderAlpha", "RoR2", "RoR2.dll", hashed, sdk),
        )

    def test_nonzero_value_or_alignment_padding_is_never_discarded(self):
        body, tree, _ = legacy_policy_fixture()
        for offset in [48, 49, 52, 55]:
            with self.subTest(offset=offset):
                changed = bytearray(body)
                changed[offset] = 1
                with self.assertRaisesRegex(ValueError, "zero aligned"):
                    P.legacy_animate_fields(bytes(changed), tree, LEGACY_IDENTITY)

    def test_wrong_field_shape_and_sdk_curve_are_rejected(self):
        body, tree, sdk = legacy_policy_fixture()
        for original, replacement in [(b"disableObjectOnEnd\x00", b"disableObjectOnBad\x00"), (b"resetOnEnable\x00", b"resetOnEnabXX\x00")]:
            with self.subTest(original=original):
                with self.assertRaisesRegex(ValueError, "membership"):
                    P.legacy_animate_fields(body, tree.replace(original, replacement), LEGACY_IDENTITY)
        _, projected = P.legacy_animate_fields(body, tree, LEGACY_IDENTITY)
        with self.assertRaisesRegex(ValueError, "curve schema absent"):
            P.legacy_animate_hash_tree(projected, sdk.replace(b"m_Falloff\x00", b"m_FallBad\x00"), LEGACY_IDENTITY)
        with self.assertRaisesRegex(ValueError, "tangent schema"):
            P.legacy_animate_hash_tree(projected, sdk.replace(b"tangentMode\x00", b"tangentMade\x00"), LEGACY_IDENTITY)


class ReflectionProbeImportTests(unittest.TestCase):
    def fixture(self, mode=0, texture=(0, 0), mode_name="m_Mode"):
        f = CURVE_MESH_FIXTURE
        root = f.node(
            "Base",
            kind="ReflectionProbe",
            children=[
                f.node("m_IntensityMultiplier", 4, kind="float"),
                f.node(mode_name, 4, kind="int"),
                f.node("m_BakedTexture", 12, kind="PPtr<Texture>"),
                f.node("m_CustomBakedTexture", 12, kind="PPtr<Texture>"),
                f.node("m_BoxSize", 12, kind="Vector3f"),
            ],
        )
        body = struct.pack("<fiiqiq3f", 1.25, mode, 34, -9876543, *texture, 20, 30, 40)
        raw = CURVE_RECORD_FIXTURE.serialized(body, root, 215)
        stream = io.BytesIO(raw)
        stream.size = len(raw)
        return body, P.W.read_serialized(stream)["types"][0]

    def test_only_mode_changes_and_original_textures_and_bounds_are_retained(self):
        body, typ = self.fixture()
        result = P.custom_reflection_probe(body, typ)
        self.assertEqual(result, body[:4] + struct.pack("<i", 2) + body[8:])
        self.assertEqual(body[4:8], bytes(4))
        self.assertEqual(typ["class_id"], 215)

    def test_wrong_class_nonbaked_mode_and_assigned_custom_texture_are_rejected(self):
        body, typ = self.fixture()
        with self.assertRaisesRegex(ValueError, "ReflectionProbe"):
            P.custom_reflection_probe(body, {**typ, "class_id": 114})
        for options in [{"mode": 1}, {"mode": 2}, {"texture": (0, 12)}, {"texture": (3, 0)}]:
            with self.subTest(options=options):
                body, typ = self.fixture(**options)
                with self.assertRaises(ValueError):
                    P.custom_reflection_probe(body, typ)

    def test_schema_drift_and_unowned_trailing_bytes_cannot_be_discarded(self):
        body, typ = self.fixture(mode_name="unknown")
        with self.assertRaisesRegex(ValueError, "fields missing"):
            P.custom_reflection_probe(body, typ)
        body, typ = self.fixture()
        for malformed in [body[:-1], body + b"UNOWNED"]:
            with self.assertRaises((ValueError, struct.error)):
                P.custom_reflection_probe(malformed, typ)


if __name__ == "__main__":
    unittest.main()
