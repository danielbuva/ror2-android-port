"""Complete source-only prefab fixture; no game bytes or installed Editor."""

from contextlib import nullcontext
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


def managed_fixture(root):
    pc, path, profile, _, original_target = fixture(root)
    source = pc / "source.bundle"
    source_layout = P.W.read_serialized(P.B.Bundle(source).member("CAB-source"))
    target_stream = io.BytesIO(original_target)
    target_stream.size = len(original_target)
    target_layout = P.W.read_serialized(target_stream)
    names = ("AuthoredBehaviour", "Fixture.Namespace", "Fixture.Assembly")
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
    source_behaviour = bytes(range(16)) + struct.pack("<iq", 0, 51) + b"PRESERVE BEHAVIOUR"
    target_behaviour = source_behaviour[:16] + struct.pack("<iq", 0, 2) + source_behaviour[28:]
    behaviour_type = {**typ(114), "script_id": b"AUTHORED-SCRIPT!", "tree": struct.pack("<II", 1, 4) + bytes(32) + b"PC!\0"}
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
            if identity == -7:
                selected["references"][0]["offset"] = 16
    script_end = (len(target_script) + 7) // 8 * 8
    target_layout["types"][1] = {**behaviour_type, "hash": derived_hash, "script_type": 0}
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

    def test_audio_component_omission_preserves_order_and_every_other_gameobject_byte(self):
        suffix = b"NAME-LAYER-TAG-AND-ACTIVE"
        original = struct.pack("<Iiqiqiq", 3, 0, 71, 0, -19, 0, 48) + suffix
        self.assertEqual(P.remove_components(original, [{"index": 1, "path_id": -19}]), struct.pack("<Iiqiq", 2, 0, 71, 0, 48) + suffix)
        for removals in ([{"index": 1, "path_id": -20}], [{"index": 3, "path_id": 48}], [{"index": 1, "path_id": -19}] * 2):
            with self.subTest(removals=removals), self.assertRaises(ValueError):
                P.remove_components(original, removals)
        with self.assertRaisesRegex(ValueError, "truncated"):
            P.remove_components(original[:10], [])

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


if __name__ == "__main__":
    unittest.main()
