"""Authored fixtures for the SDK/converter player-data target-tree boundary."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("player_data", ROOT / "tools/phone-build/accepted-output/player_data.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def pin(data):
    return len(data), hashlib.sha256(data).hexdigest()


def font_fixture(pc):
    """Authored native bodies; expected player metadata is packed independently."""
    source_bodies = [
        bytearray(b"authored material".ljust(148, b"!")),
        bytearray(b"authored texture".ljust(120, b"?")),
        bytearray(b"authored font bytes".ljust(192, b"~")),
    ]
    struct.pack_into("<iq", source_bodies[0], 20, 3, 10101)
    struct.pack_into("<iq", source_bodies[0], 76, 0, -27)
    struct.pack_into("<iq", source_bodies[2], 32, 0, -91)
    struct.pack_into("<iq", source_bodies[2], 48, 0, -27)
    bodies = [bytearray(body) for body in source_bodies]
    struct.pack_into("<iq", bodies[0], 20, 1, 10101)
    struct.pack_into("<iq", bodies[0], 76, 0, 2)
    struct.pack_into("<iq", bodies[2], 32, 0, 1)
    struct.pack_into("<iq", bodies[2], 48, 0, 2)
    types = [
        {"class_id": kind, "stripped": 0, "script_type": -1, "hash": bytes([index + 1]) * 16, "tree": struct.pack("<II", 1, 0) + bytes(32), "dependencies": []}
        for index, kind in enumerate((21, 28, 128))
    ]
    source_ids = (-91, -27, -93)
    offsets = (0, 152, 272)
    externals = [{"empty": "", "guid": bytes([index + 5]) * 16, "type": 0, "path": "authored dependency " + str(index)} for index in range(3)]
    source_layout = {
        "engine": "2021.3.45f2",
        "platform": 19,
        "trees": True,
        "types": types,
        "objects": [
            {"path_id": identity, "offset": offset, "bytes": len(body), "type_id": index}
            for index, (identity, offset, body) in enumerate(zip(source_ids, offsets, source_bodies))
        ],
        "scripts": [],
        "externals": externals,
        "ref_types": [],
        "user": "source-only metadata",
    }
    serialized = io.BytesIO()
    P.W.write_serialized(serialized, source_layout, lambda row: io.BytesIO(source_bodies[row["type_id"]]))
    data = serialized.getvalue()
    source = pc / "authored-font.bundle"
    with source.open("wb") as stream:
        P.W.write_bundle(stream, [("CAB-authored-font", 4, len(data), lambda: io.BytesIO(data))], lambda body, method: body, flags=0x40)
    # Independent v22 destination header/type/object/external records, no writer.
    meta = bytearray(b"2021.3.45f2\0" + struct.pack("<i?I", 13, False, 3))
    for index, kind in enumerate((21, 28, 128)):
        meta.extend(struct.pack("<iBh", kind, 0, -1) + bytes([index + 1]) * 16)
    meta.extend(struct.pack("<I", 3))
    for index, (offset, body) in enumerate(zip(offsets, bodies)):
        meta.extend(bytes(-len(meta) % 4))
        meta.extend(struct.pack("<qqIi", index + 1, offset, len(body), index))
    meta.extend(struct.pack("<II", 0, 1) + b"\0" + bytes([7]) * 16 + struct.pack("<i", 0) + b"authored dependency 2\0" + struct.pack("<I", 0) + b"\0")
    expected = bytearray(struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", len(meta), 4096 + 272 + len(bodies[2]), 4096, 0))
    expected.extend(meta)
    expected.extend(bytes(4096 - len(expected)))
    expected.extend(bodies[0] + bytes(4) + bodies[1] + bodies[2])
    references = [
        [{"offset": 20, "from": [3, 10101], "to": [1, 10101]}, {"offset": 76, "from": [0, -27], "to": [0, 2]}],
        [],
        [{"offset": 32, "from": [0, -91], "to": [0, 1]}, {"offset": 48, "from": [0, -27], "to": [0, 2]}],
    ]
    selected = {
        "file": "authored-font-player",
        "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": P.sha(source), "member": "CAB-authored-font"},
        "externals": [2],
        "objects": [
            {
                "source_path_id": source_id,
                "path_id": index + 1,
                "bytes": len(before),
                "source_sha256": pin(before)[1],
                "sha256": pin(after)[1],
                "references": refs,
            }
            for index, (source_id, before, after, refs) in enumerate(zip(source_ids, source_bodies, bodies, references))
        ],
    }
    return selected, bytes(expected)


def text_fixture(pc, profile_root):
    """Two independent TextAsset bodies, source reuse and authored JSON."""

    def aligned(value):
        data = value.encode("utf-8")
        result = struct.pack("<I", len(data)) + data
        return result + bytes(-len(result) % 4)

    before = aligned("Original line breaks") + aligned("authored punctuation: )]!?\n")
    recipe = profile_root / "authored-runtime.json"
    recipe.write_text('{"greeting":"hello \u2603","active":true}')
    script = '{\n  "greeting": "hello \\u2603",\n  "active": true\n}\n'
    generated = aligned("AuthoredRuntime") + aligned(script)
    definition = {"class_id": 49, "stripped": 0, "script_type": -1, "hash": b"T" * 16, "tree": struct.pack("<II", 1, 0) + bytes(32), "dependencies": []}
    layout = {
        "engine": "2021.3.45f2",
        "platform": 19,
        "trees": True,
        "types": [definition],
        "objects": [{"path_id": -51, "offset": 0, "bytes": len(before), "type_id": 0}],
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    serialized = io.BytesIO()
    P.W.write_serialized(serialized, layout, lambda row: io.BytesIO(before))
    source = pc / "authored-text.bundle"
    data = serialized.getvalue()
    with source.open("xb") as stream:
        P.W.write_bundle(stream, [("CAB-authored-text", 4, len(data), lambda: io.BytesIO(data))], lambda body, method: body, flags=0x40)
    expected = {}
    for name, body in (("original-text-player", before), ("authored-json-player", generated)):
        meta = bytearray(b"2021.3.45f2\0" + struct.pack("<i?I", 13, False, 1))
        meta.extend(struct.pack("<iBh", 49, 0, -1) + b"T" * 16 + struct.pack("<I", 1))
        meta.extend(bytes(-len(meta) % 4))
        meta.extend(struct.pack("<qqIiIII", 1, 0, len(body), 0, 0, 0, 0))
        meta.extend(b"\0")
        header = struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", len(meta), 4096 + len(body), 4096, 0)
        expected[name] = header + meta + bytes(4096 - len(header) - len(meta)) + body
    selected = {
        "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": P.sha(source), "member": "CAB-authored-text"},
        "files": [
            {"file": "original-text-player", "source_path_id": -51, "source_sha256": pin(before)[1], "bytes": len(before), "sha256": pin(before)[1]},
            {
                "file": "authored-json-player",
                "name": "AuthoredRuntime",
                "recipe": {"path": recipe.name, "bytes": recipe.stat().st_size, "sha256": P.sha(recipe)},
                "bytes": len(generated),
                "sha256": pin(generated)[1],
            },
        ],
    }
    return selected, expected


def sprite_fixture(pc):
    """An authored standalone Sprite, preserving all non-identity body bytes."""
    source_body = bytearray(b"!" * 160)
    struct.pack_into("<I", source_body, 0, 6)
    source_body[4:10] = b"sprite"
    key = 72
    source_body[key + 24 : key + 64] = bytes(40)
    struct.pack_into("<iq", source_body, key + 40, 0, 11)
    name = "0123456789abcdef0011223344556677"
    texture = "fedcba98765432100011223344556677"
    expected_body = bytearray(source_body)
    expected_body[key : key + 24] = bytes.fromhex("1032547698badcfe00112233445566772003450100000000")
    struct.pack_into("<iq", expected_body, key + 40, 1, 1)
    layout = {
        "engine": "2021.3.45f2",
        "platform": 19,
        "trees": False,
        "types": [{"class_id": 213, "stripped": 0, "script_type": -1, "hash": b"S" * 16}],
        "objects": [{"path_id": 37, "offset": 0, "bytes": len(source_body), "type_id": 0}],
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    source = pc / "authored-sprites.assets"
    with source.open("xb") as output:
        P.W.write_serialized(output, layout, lambda row: io.BytesIO(source_body))
    meta = bytearray(b"2021.3.45f2\0" + struct.pack("<i?I", 13, False, 1))
    meta.extend(struct.pack("<iBh", 213, 0, -1) + b"S" * 16 + struct.pack("<I", 1))
    meta.extend(bytes(-len(meta) % 4))
    meta.extend(struct.pack("<qqIiII", 1, 0, len(expected_body), 0, 0, 1))
    meta.extend(b"\0" + bytes(16) + struct.pack("<i", 0) + texture.encode() + b"\0" + struct.pack("<I", 0) + b"\0")
    header = struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", len(meta), 4096 + len(expected_body), 4096, 0)
    expected = header + meta + bytes(4096 - len(header) - len(meta)) + expected_body
    selected = {
        "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": P.sha(source)},
        "files": [
            {
                "file": name,
                "texture": texture,
                "objects": [
                    {
                        "source_path_id": 37,
                        "path_id": 1,
                        "bytes": len(source_body),
                        "source_sha256": pin(source_body)[1],
                        "sha256": pin(expected_body)[1],
                        "references": [{"offset": key + 40, "from": [0, 11], "to": [1, 1]}],
                    }
                ],
            }
        ],
    }
    return selected, {name: bytes(expected)}


class PlayerDataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.pc, self.sdk, self.converter, self.output = [self.root / name for name in ("pc", "sdk", "converter", "new")]
        self.pc.mkdir()
        (self.pc / "owner.bin").write_bytes(b"original installation must remain unchanged")
        self.projects = ["Assembly-CSharp.dll", "Newtonsoft.Json.dll", "Authored.Game.dll", "MCPForUnity.Runtime.dll"]
        scripting = {
            "names": ["UnityEngine.CoreModule.dll", "UnityEngine.ClusterInputModule.dll", "Authored.Game.dll", "Assembly-CSharp.dll"],
            "types": [2, 2, 16, 16],
        }
        original_rows = [
            {"assemblyName": assembly, "nameSpace": "Authored", "className": "Start", "methodName": "Run", "loadTypes": 0, "isUnityClass": False}
            for assembly in ("Authored.Game", "Assembly-CSharp", "UnavailablePlatform")
        ]
        initializers = {"root": original_rows}
        self.profile = {"input_id": P.INPUT_ID, "sources": {}, "outputs": {}, "project_assemblies": self.projects}
        for name, value in (("ScriptingAssemblies.json", scripting), ("RuntimeInitializeOnLoads.json", initializers)):
            source = self.pc / name
            source.write_text(json.dumps(value))
            self.profile["sources"][name] = {"path": name, "bytes": source.stat().st_size, "sha256": P.sha(source)}
        expected_initializers = [
            {"assemblyName": "Assembly-CSharp", "nameSpace": "", "className": name, "methodName": method, "loadTypes": 0, "isUnityClass": False}
            for name, method in (
                ("PortSession", "Init"),
                ("CharacterDirectionProbe", "Init"),
                ("ControllerAddressProbe", "Init"),
                ("EntityStateTickProbe", "Init"),
                ("WholeCatalogBootstrap", "Initialize"),
            )
        ] + [original_rows[1], original_rows[0]]
        self.generated = {
            "ScriptingAssemblies.json": json.dumps(
                {"names": ["UnityEngine.CoreModule.dll"] + self.projects, "types": [2, 16, 16, 16, 16]}, separators=(",", ":")
            ).encode(),
            "RuntimeInitializeOnLoads.json": (json.dumps({"root": expected_initializers}, separators=(",", ":")) + "\n").encode(),
        }
        self.profile["font"], font_bytes = font_fixture(self.pc)
        self.generated[self.profile["font"]["file"]] = font_bytes
        self.profile["text_assets"], text_bytes = text_fixture(self.pc, self.root)
        self.profile["sprites"], sprite_bytes = sprite_fixture(self.pc)
        self.generated.update(sprite_bytes)
        self.generated.update(text_bytes)
        self.profile["outputs"] = {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in self.generated.items()}
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_hash = P.sha(self.profile_path)
        self.bodies = {P.DEFAULT: b"authored SDK defaults\0", **{name: ("authored resource " + name).encode() for name in P.RESOURCES}}
        for name, body in self.bodies.items():
            file = (self.sdk / "Data" if name == P.DEFAULT else self.converter / "data") / name.removeprefix("Managed/")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(body)
        self.resources = {name: pin(data) for name, data in self.bodies.items() if name != P.DEFAULT}
        self.receipt = {
            "exit_code": 0,
            "inputs_unchanged": True,
            "input_assemblies": 90,
            "files": {"data/" + name.removeprefix("Managed/"): {"bytes": size, "sha256": digest} for name, (size, digest) in self.resources.items()},
        }
        self.save_receipt()
        for mocker in (
            patch.dict(P.SDK.FILES, {"Data/" + P.DEFAULT: pin(self.bodies[P.DEFAULT])}),
            patch.object(P, "RESOURCES", self.resources),
            patch.object(P, "RESERVE", 0),
        ):
            mocker.start()
            self.addCleanup(mocker.stop)

    def save_receipt(self):
        (self.converter / "result.json").write_text(json.dumps(self.receipt))
        self.receipt_hash = P.sha(self.converter / "result.json")

    def produce(self, output=None, texture_packs=()):
        return P.produce(self.profile_path, self.profile_hash, self.pc, self.sdk, self.converter, self.receipt_hash, output or self.output, texture_packs)

    def failed(self):
        self.assertFalse(json.loads((self.output / "result.json").read_text())["success"])

    def test_source_only_complete_target_tree_and_receipt(self):
        before = (self.pc / "owner.bin").read_bytes()
        result = self.produce()
        self.assertTrue(result["success"])
        self.assertEqual(set(result["files"]), {P.TARGET + name for name in self.bodies | self.generated})
        self.assertEqual(json.loads((self.output / "result.json").read_text()), result)
        for name, body in self.bodies.items():
            self.assertEqual((self.output / (P.TARGET + name)).read_bytes(), body)
            row = result["files"][P.TARGET + name]
            self.assertEqual((row["bytes"], row["sha256"]), pin(body))
            self.assertEqual(row["source_role"], "sdk" if name == P.DEFAULT else "converter")
        for name, body in self.generated.items():
            self.assertEqual((self.output / (P.TARGET + name)).read_bytes(), body)
        self.assertEqual((self.pc / "owner.bin").read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "must be new"):
            self.produce()

    def test_sprite_source_override_is_used_and_recorded(self):
        sprites = self.profile["sprites"]
        selected = sprites["files"][0]
        selected["source"] = dict(sprites["source"])
        source = self.pc / selected["source"]["path"]
        alternate = self.pc / "alternate-sprites.assets"
        source.rename(alternate)
        selected["source"]["path"] = alternate.name
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_hash = P.sha(self.profile_path)
        result = self.produce()
        name = P.TARGET + selected["file"]
        self.assertEqual(result["files"][name]["source"], alternate.name)
        self.assertEqual((self.output / name).read_bytes(), self.generated[selected["file"]])

    def test_standalone_script_keeps_type_and_fields_with_external_script_table(self):
        source_body = bytes(16) + struct.pack("<iq", 1, 77) + b"DATA"
        target_body = bytes(16) + struct.pack("<iq", 1, 33) + b"DATA"
        source = self.pc / "authored-script.assets"
        source_type = {"class_id": 114, "stripped": 0, "script_type": 9, "script_id": b"I" * 16, "hash": b"H" * 16}
        layout = {
            "engine": "2021.3.45f2",
            "platform": 19,
            "trees": False,
            "types": [source_type],
            "objects": [{"path_id": 55, "offset": 0, "bytes": 32, "type_id": 0}],
            "scripts": [(1, 77)] * 10,
            "externals": [],
            "ref_types": [],
            "user": "",
        }
        with source.open("xb") as output:
            P.W.write_serialized(output, layout, lambda row: io.BytesIO(source_body))
        selected = {
            "file": "00112233445566778899aabbccddeeff",
            "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": P.sha(source)},
            "objects": [
                {
                    "source_path_id": 55,
                    "path_id": 1,
                    "bytes": 32,
                    "source_sha256": pin(source_body)[1],
                    "sha256": pin(target_body)[1],
                    "references": [{"offset": 16, "from": [1, 77], "to": [1, 33]}],
                }
            ],
            "script": [1, 33],
            "externals": ["globalgamemanagers.assets"],
        }
        destination = self.root / "script-output"
        before = P.sha(source)
        P.object_file(self.pc, selected, destination)
        with destination.open("rb") as stream:
            stream.size = destination.stat().st_size
            result = P.W.read_serialized(stream)
            stream.seek(result["data_offset"])
            self.assertEqual(stream.read(), target_body)
        self.assertEqual(result["types"], [{**source_type, "script_type": 0}])
        self.assertEqual(result["scripts"], [(1, 33)])
        self.assertEqual(result["externals"][0]["path"], "globalgamemanagers.assets")
        self.assertEqual(P.sha(source), before)
        selected["script"] = [1, 34]
        with self.assertRaisesRegex(ValueError, "script relationship"):
            P.object_file(self.pc, selected, self.root / "wrong-script")

    def test_materials_use_original_values_checked_references_and_existing_keyword_policy(self):
        def string(value):
            data = value.encode()
            return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)

        prefix = string("Authored material")
        keywords = struct.pack("<I", 1) + string("SOURCE_FEATURE") + struct.pack("<I", 1) + string("SOURCE_DISABLED")
        tail = struct.pack("<iq4f", 0, -91, 0.125, -2.5, 7.0, 0.0)
        source_body = prefix + struct.pack("<iq", 3, 77) + keywords + tail
        relocated = prefix + struct.pack("<iq", 1, 1) + keywords + struct.pack("<iq", 2, 1) + tail[12:]
        demoted = prefix + struct.pack("<iqII", 1, 1, 0, 2) + string("SOURCE_FEATURE") + string("SOURCE_DISABLED") + relocated[-len(tail) :]
        source_type = {"class_id": 21, "stripped": 0, "script_type": -1, "hash": b"M" * 16}
        layout = {
            "engine": "2021.3.45f2",
            "platform": 19,
            "trees": False,
            "types": [source_type],
            "objects": [{"path_id": -27, "offset": 0, "bytes": len(source_body), "type_id": 0}],
            "scripts": [],
            "externals": [],
            "ref_types": [],
            "user": "",
        }
        source = self.pc / "authored-material.assets"
        with source.open("xb") as stream:
            P.W.write_serialized(stream, layout, lambda row: io.BytesIO(source_body))
        before = P.sha(source)
        selections = []
        for index, body in enumerate((relocated, demoted)):
            name = "00112233445566778899aabbccddee" + f"{index:04x}"
            selected = {
                "file": name,
                "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": before},
                "externals": ["authored-shader", "authored-texture"],
                "objects": [
                    {
                        "source_path_id": -27,
                        "path_id": 1,
                        "bytes": len(body),
                        "source_sha256": pin(source_body)[1],
                        "sha256": pin(body)[1],
                        "references": [
                            {"offset": len(prefix), "from": [3, 77], "to": [1, 1]},
                            {"offset": len(source_body) - len(tail), "from": [0, -91], "to": [2, 1]},
                        ],
                    }
                ],
            }
            if index:
                selected["objects"][0]["keyword_policy"] = "dummy-shader-demote-valid"
            selections.append(selected)
            # Independently pack the one-object v22 player metadata.
            meta = bytearray(b"2021.3.45f2\0" + struct.pack("<i?IiBh", 13, False, 1, 21, 0, -1) + b"M" * 16 + struct.pack("<I", 1))
            meta.extend(bytes(-len(meta) % 4))
            meta.extend(struct.pack("<qqIiII", 1, 0, len(body), 0, 0, 2))
            for external in selected["externals"]:
                meta.extend(bytes(17) + struct.pack("<i", 0) + external.encode() + b"\0")
            meta.extend(bytes(5))
            expected = struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", len(meta), 4096 + len(body), 4096, 0) + meta
            expected += bytes(4096 - len(expected)) + body
            self.profile["outputs"][name] = {"bytes": len(expected), "sha256": pin(expected)[1]}
            self.generated[name] = expected
        self.profile["objects"] = selections
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_hash = P.sha(self.profile_path)
        result = self.produce()
        for selected in selections:
            name = selected["file"]
            self.assertEqual((self.output / (P.TARGET + name)).read_bytes(), self.generated[name])
            self.assertEqual(result["files"][P.TARGET + name]["source"], source.name)
        self.assertEqual(P.sha(source), before)
        selections[1]["objects"][0]["keyword_policy"] = "unknown"
        with self.assertRaisesRegex(ValueError, "keyword policy"):
            P.object_file(self.pc, selections[1], self.root / "wrong-material-policy")

    def test_texture_pack_composition_keeps_original_native_fields_and_inline_records(self):
        pack = self.root / "texture-pack"
        pack.mkdir()
        pixels = b"PIXEL"
        native = b"original native texture fields!!"
        native += bytes(-len(native) % 4)
        descriptor = {"offset": 9876, "size": len(pixels), "path": "archive:/authored/texture.resS"}
        path = descriptor["path"].encode()
        streamed = (
            native + bytes(4) + struct.pack("<QI", descriptor["offset"], descriptor["size"]) + struct.pack("<I", len(path)) + path + bytes(-len(path) % 4)
        )
        inlined = native + struct.pack("<I", len(pixels)) + pixels + bytes(3) + bytes(16)
        rows = []
        targets = []
        for index, body in enumerate((streamed, inlined)):
            row = {
                "bundle": "authored-bundle",
                "member": "CAB-authored",
                "path_id": index + 10,
                "offset": 0 if not index else len(streamed),
                "bytes": len(body),
                "sha256": pin(body)[1],
            }
            if not index:
                row["resource"] = {"offset": 0, "bytes": len(pixels), "sha256": pin(pixels)[1], "stream": descriptor}
            rows.append(row)
            name = "ffeeddccbbaa9988776655443322" + f"{index:04x}"
            targets.append({"file": name, **{key: row[key] for key in ("bundle", "member", "path_id")}})
            # Independent one-native-object serialized envelope; source font
            # fixture's Texture2D type hash is 16 copies of byte 2.
            meta = bytearray(b"2021.3.45f2\0" + struct.pack("<i?IiBh", 13, False, 1, 28, 0, -1) + bytes([2]) * 16 + struct.pack("<I", 1))
            meta.extend(bytes(-len(meta) % 4))
            meta.extend(struct.pack("<qqIiIII", 1, 0, len(inlined), 0, 0, 0, 0) + b"\0")
            expected = struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", len(meta), 4096 + len(inlined), 4096, 0) + meta
            expected += bytes(4096 - len(expected)) + inlined
            self.profile["outputs"][name] = {"bytes": len(expected), "sha256": pin(expected)[1]}
            self.generated[name] = expected
        (pack / "objects.bin").write_bytes(streamed + inlined)
        (pack / "resources.bin").write_bytes(pixels)
        (pack / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        producer = {"success": True, "input_id": P.INPUT_ID, "profile_sha256": "authored-source-profile", "outputs": {}}

        def save_producer():
            producer["outputs"] = {
                name: {"bytes": (pack / name).stat().st_size, "sha256": P.sha(pack / name)} for name in ("objects.bin", "resources.bin", "index.jsonl")
            }
            (pack / "result.json").write_text(json.dumps(producer))
            return P.sha(pack / "result.json")

        receipt_pin = save_producer()
        self.profile["textures"] = [{"profile_sha256": producer["profile_sha256"], "files": targets}]
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_hash = P.sha(self.profile_path)
        result = self.produce(texture_packs=[(pack, receipt_pin)])
        for target in targets:
            name = target["file"]
            self.assertEqual((self.output / (P.TARGET + name)).read_bytes(), self.generated[name])
            self.assertEqual(result["files"][P.TARGET + name]["source"], receipt_pin)
        self.assertEqual(result["texture_packs"], {producer["profile_sha256"]: receipt_pin})
        with self.assertRaisesRegex(ValueError, "missing source-produced"):
            self.produce(self.root / "no-pack")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            self.produce(self.root / "wrong-receipt", [(pack, "0" * 64)])
        (pack / "resources.bin").write_bytes(b"WRONG")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            self.produce(self.root / "changed-pack", [(pack, receipt_pin)])
        (pack / "resources.bin").write_bytes(pixels)
        rows[0]["resource"]["stream"]["offset"] += 1
        (pack / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        changed_pin = save_producer()
        with self.assertRaisesRegex(ValueError, "stream descriptor differs"):
            self.produce(self.root / "wrong-descriptor", [(pack, changed_pin)])
        producer["success"] = False
        failed_pin = save_producer()
        with self.assertRaisesRegex(ValueError, "unsuccessful texture producer"):
            self.produce(self.root / "failed-producer", [(pack, failed_pin)])

    def test_receipt_drift_failure_membership_and_resource_hash_fail_closed(self):
        mutations = ("pin", "failure", "changed-inputs", "missing", "comparison-hash")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                receipt = json.loads(json.dumps(self.receipt))
                if mutation == "failure":
                    receipt["exit_code"] = 1
                elif mutation == "changed-inputs":
                    receipt["inputs_unchanged"] = False
                elif mutation == "missing":
                    receipt["files"].pop(next(iter(receipt["files"])))
                elif mutation == "comparison-hash":
                    receipt["files"][next(iter(receipt["files"]))]["sha256"] = "0" * 64
                (self.converter / "result.json").write_text(json.dumps(receipt))
                receipt_hash = "0" * 64 if mutation == "pin" else P.sha(self.converter / "result.json")
                output = self.root / mutation
                with self.assertRaises(ValueError):
                    P.produce(self.profile_path, self.profile_hash, self.pc, self.sdk, self.converter, receipt_hash, output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])

    def test_source_drift_and_missing_provider_have_no_target_fallback(self):
        source = self.converter / "data" / next(iter(self.resources)).removeprefix("Managed/")
        for missing in (False, True):
            with self.subTest(missing=missing):
                output = self.root / ("missing" if missing else "drift")
                source.unlink() if missing else source.write_bytes(b"changed provider")
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])

    def test_output_disjointness_and_redirection_leave_sources_untouched(self):
        for root in (self.pc, self.sdk, self.converter):
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, "separate"):
                self.produce(root / "new")
            self.assertFalse((root / "new").exists())
        alias = self.root / "redirected"
        alias.symlink_to(self.pc, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "separate"):
            self.produce(alias / "new")
        provider = self.sdk / "Data" / P.DEFAULT
        other = self.root / "other"
        provider.rename(other)
        provider.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "redirected"):
            self.produce()
        self.failed()
        self.assertEqual(other.read_bytes(), self.bodies[P.DEFAULT])

    def test_readback_and_source_changes_are_detected(self):
        copy = shutil.copyfile
        for target in ("output", "source", "receipt"):
            with self.subTest(target=target):
                output = self.root / target

                def corrupt(source, destination):
                    result = copy(source, destination)
                    if source.name == P.DEFAULT:
                        selected = destination if target == "output" else source if target == "source" else self.converter / "result.json"
                        selected.write_bytes(b"changed during production")
                    return result

                with patch.object(P.shutil, "copyfile", side_effect=corrupt), self.assertRaises(ValueError):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])
                (self.sdk / "Data" / P.DEFAULT).write_bytes(self.bodies[P.DEFAULT])
                self.save_receipt()

    def test_original_metadata_identity_and_recipe_drift_refuse(self):
        with self.assertRaisesRegex(ValueError, "profile drift"):
            P.produce(self.profile_path, "0" * 64, self.pc, self.sdk, self.converter, self.receipt_hash, self.output)
        self.assertFalse(self.output.exists())
        for mutation in ("original", "order", "path"):
            with self.subTest(mutation=mutation):
                profile = json.loads(json.dumps(self.profile))
                if mutation == "original":
                    source = self.pc / "ScriptingAssemblies.json"
                    old = source.read_bytes()
                    source.write_bytes(b"changed PC metadata")
                elif mutation == "order":
                    profile["project_assemblies"].reverse()
                else:
                    profile["sources"]["ScriptingAssemblies.json"]["path"] = "../profile.json"
                self.profile_path.write_text(json.dumps(profile))
                self.profile_hash = P.sha(self.profile_path)
                output = self.root / mutation
                with self.assertRaises(ValueError):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])
                if mutation == "original":
                    source.write_bytes(old)

    def test_text_source_and_authored_recipe_drift_refuse_without_fallback(self):
        for mutation in ("source", "body", "recipe", "recipe-path", "file-path", "generated-body"):
            with self.subTest(mutation=mutation):
                profile = json.loads(json.dumps(self.profile))
                text = profile["text_assets"]
                if mutation == "source":
                    text["source"]["sha256"] = "0" * 64
                elif mutation == "body":
                    text["files"][0]["source_sha256"] = "0" * 64
                elif mutation == "recipe":
                    text["files"][1]["recipe"]["sha256"] = "0" * 64
                elif mutation == "recipe-path":
                    text["files"][1]["recipe"]["path"] = "../authored-runtime.json"
                elif mutation == "file-path":
                    text["files"][0]["file"] = "../escaped"
                else:
                    text["files"][1]["name"] = "Unpinned authored name"
                self.profile_path.write_text(json.dumps(profile))
                self.profile_hash = P.sha(self.profile_path)
                output = self.root / mutation
                with self.assertRaises(ValueError):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])
                self.assertFalse((output / "apk/assets/bin/escaped").exists())

    def test_sprite_guid_regeneration_preserves_non_identity_body_and_refuses_atlas(self):
        body = bytearray(160)
        struct.pack_into("<I", body, 0, 6)
        body[4:10] = b"sprite"
        body[72:96] = b"original importer key!!!"
        expected_key = bytes.fromhex("1032547698badcfe00112233445566772003450100000000")
        result = P.sprite_key(bytes(body), "0123456789abcdef0011223344556677")
        self.assertEqual(result[:72], body[:72])
        self.assertEqual(result[72:96], expected_key)
        self.assertEqual(result[96:], body[96:])
        for offset in (96, 100, 124):
            changed = bytearray(body)
            changed[offset] = 1
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "layout"):
                P.sprite_key(changed, "0123456789abcdef0011223344556677")
        with self.assertRaisesRegex(ValueError, "GUID"):
            P.sprite_key(body, "../escaped")

    def test_sprite_crop_recovers_source_rect_pivot_border_and_preserves_geometry(self):
        body = bytearray(b"!" * 200)
        struct.pack_into("<I", body, 0, 4)
        body[4:8] = b"Demo"
        header, rectangle_offset = 8, 144
        struct.pack_into("<4f2f4f", body, header, 0, 0, 100, 80, 0, 0, 10, 0, 20, 12)
        struct.pack_into("<2f", body, header + 44, 0.5, 0.5)
        struct.pack_into("<6f", body, rectangle_offset, 5, 7, 80, 60, 10, 8)
        result = P.sprite_crop(body, rectangle_offset)
        self.assertEqual(struct.unpack_from("<4f", result, header), (5, 7, 80, 60))
        self.assertEqual(struct.unpack_from("<2f", result, header + 16), (0, 2.0000016689300537))
        self.assertEqual(struct.unpack_from("<4f", result, header + 24), (0, 0, 10, 0))
        self.assertEqual(struct.unpack_from("<2f", result, header + 44), (0.5, 0.5333333611488342))
        self.assertEqual(result[rectangle_offset + 16 : rectangle_offset + 24], bytes(8))
        self.assertEqual(result[header + 52 : rectangle_offset], body[header + 52 : rectangle_offset])
        self.assertEqual(result[rectangle_offset + 24 :], body[rectangle_offset + 24 :])
        with self.assertRaisesRegex(ValueError, "crop extent"):
            P.sprite_crop(body, len(body))

    def test_authored_full_rectangle_uses_original_bounds_pivot_and_pixel_scale(self):
        original = bytearray(200)
        struct.pack_into("<I", original, 0, 4)
        original[4:8] = b"Demo"
        struct.pack_into("<4f", original, 8, 0, 0, 100, 80)
        struct.pack_into("<f2f", original, 48, 20, 0.25, 0.75)
        struct.pack_into("<6f", original, 144, 0, 0, 100, 80, 0, 0)
        before = bytes(original)
        result = P.full_rectangle_sprite(original, 144)
        size = struct.unpack_from("<I", result)[0]
        self.assertEqual(result[4 : size + 4], b"Owned full-rectangle Demo")
        header = (size + 7) // 4 * 4
        self.assertEqual(struct.unpack_from("<4f", result, header), (0, 0, 100, 80))
        self.assertEqual(struct.unpack_from("<6H", result, header + 184), (0, 1, 2, 2, 1, 3))
        self.assertEqual(struct.unpack_from("<12f", result, header + 264), (-1.25, 1, 0, 3.75, 1, 0, -1.25, -3, 0, 3.75, -3, 0))
        self.assertEqual(result[header + 312 : header + 344], bytes(32))
        self.assertEqual(bytes(original), before)
        source = self.pc / "full-rectangle-source.assets"
        layout = {
            "engine": "2021.3.45f2",
            "platform": 19,
            "trees": False,
            "types": [{"class_id": 213, "stripped": 0, "script_type": -1, "hash": b"S" * 16}],
            "objects": [{"path_id": 51, "offset": 0, "bytes": len(original), "type_id": 0}],
            "scripts": [],
            "externals": [],
            "ref_types": [],
            "user": "",
        }
        with source.open("xb") as stream:
            P.W.write_serialized(stream, layout, lambda row: io.BytesIO(original))
        name = "0123456789abcdef0011223344556677"
        expected = P.sprite_key(result, name)
        selected = {
            "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": P.sha(source)},
            "file": name,
            "texture": "fedcba98765432100011223344556677",
            "full_rectangle": True,
            "crop_rectangle_offset": 144,
            "objects": [
                {
                    "source_path_id": 51,
                    "path_id": 1,
                    "source_bytes": len(original),
                    "bytes": len(expected),
                    "source_sha256": pin(original)[1],
                    "sha256": pin(expected)[1],
                }
            ],
        }
        destination = self.root / "full-rectangle-output"
        P.object_file(self.pc, selected, destination)
        with destination.open("rb") as stream:
            stream.size = destination.stat().st_size
            output_layout = P.W.read_serialized(stream)
            self.assertEqual(output_layout["objects"][0]["bytes"], len(expected))
            stream.seek(output_layout["data_offset"])
            self.assertEqual(stream.read(), expected)
        struct.pack_into("<f", original, 48, 0)
        with self.assertRaisesRegex(ValueError, "pixels-per-unit"):
            P.full_rectangle_sprite(original, 144)

    def test_font_source_object_reference_and_output_metadata_drift_refuse(self):
        for mutation in ("bundle", "body", "reference", "metadata", "memory-bound"):
            with self.subTest(mutation=mutation):
                profile = json.loads(json.dumps(self.profile))
                font = profile["font"]
                if mutation == "bundle":
                    font["source"]["sha256"] = "0" * 64
                elif mutation == "body":
                    font["objects"][0]["source_sha256"] = "0" * 64
                elif mutation == "reference":
                    font["objects"][0]["references"][0]["from"][0] = 2
                elif mutation == "metadata":
                    font["externals"] = [1]
                else:
                    font["objects"][0]["bytes"] = P.W.B.LIMIT
                self.profile_path.write_text(json.dumps(profile))
                self.profile_hash = P.sha(self.profile_path)
                output = self.root / mutation
                with self.assertRaises(ValueError):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
