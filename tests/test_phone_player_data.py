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


def metadata_tree(root):
    """Encode an authored embedded tree, independently of the source reader."""
    strings, records = bytearray(), []

    def label(value):
        offset = len(strings)
        strings.extend(value.encode() + b"\0")
        return offset

    def flatten(node, level):
        kind, name, size, flags, meta, children = node
        records.append(struct.pack("<HBBIIiiiQ", 1, level, flags, label(kind), label(name), size, len(records), meta, 0))
        for child in children:
            flatten(child, level + 1)

    flatten(root, 0)
    return {"tree": struct.pack("<II", len(records), len(strings)) + b"".join(records) + strings}


def metadata_string(name):
    return ("string", name, -1, 0, 0x4000, [("Array", "Array", -1, 1, 0, [("int", "size", 4, 0, 0, []), ("char", "data", 1, 0, 0, [])])])


def script_properties_fixture(root, pc, script_kind=115, sdk_kind=114, custom_name="value", identity_fields=None, object_kind=114):
    """Invented linked MonoBehaviour/MonoScript and SDK native-base inputs."""

    def pointer(kind, name):
        return (kind, name, -1, 0, 0, [("int", "m_FileID", 4, 0, 0, []), ("SInt64", "m_PathID", 8, 0, 0, [])])

    base = [pointer("PPtr<GameObject>", "m_GameObject"), ("int", "m_Enabled", 4, 0, 0, []), pointer("PPtr<MonoScript>", "m_Script")]
    native = ("MonoBehaviour", "Base", -1, 0, 0, base + [metadata_string("m_EditorClassIdentifier")])
    original = ("MonoBehaviour", "Base", -1, 0, 0, base + [("float", custom_name, 4, 0, 0, [])])
    identity_fields = identity_fields or ("m_ClassName", "m_Namespace", "m_AssemblyName")
    script_tree = ("MonoScript", "Base", -1, 0, 0, [metadata_string(name) for name in identity_fields])

    def definition(kind, tree):
        return {
            "class_id": kind,
            "stripped": 0,
            "script_type": 0 if kind == 114 else -1,
            "script_id": b"I" * 16,
            "hash": b"H" * 16,
            **metadata_tree(tree),
            "dependencies": [],
        }

    def serialized(kind, tree, body, identity, externals=()):
        layout = {
            "engine": "2021.3.45f2",
            "platform": 19,
            "trees": True,
            "types": [definition(kind, tree)],
            "objects": [{"path_id": identity, "offset": 0, "bytes": len(body), "type_id": 0}],
            "scripts": [],
            "externals": [{"empty": "", "guid": bytes(16), "type": 0, "path": name} for name in externals],
            "ref_types": [],
            "user": "",
        }
        output = io.BytesIO()
        P.W.write_serialized(output, layout, lambda _: io.BytesIO(body))
        return output.getvalue()

    source_body = bytes(16) + struct.pack("<iqf", 1, -77, 2.5)
    target_body = bytes(16) + struct.pack("<iqf", 1, 33, 2.5)
    source = pc / "authored-properties.assets"
    source.write_bytes(serialized(object_kind, original, source_body, 55, ["archive:/CAB-script/CAB-script"]))
    identity_values = {"m_ClassName": "Fixture", "m_Namespace": "Invented", "m_AssemblyName": "Fixture.dll"}
    script_body = io.BytesIO()
    for name in identity_fields:
        P.OBJECTS.aligned_string(script_body, identity_values[name])
    data = serialized(script_kind, script_tree, script_body.getvalue(), -77)
    script = pc / "authored-script.bundle"
    with script.open("wb") as stream:
        P.W.write_bundle(stream, [("CAB-script", 4, len(data), lambda: io.BytesIO(data))], lambda body, _: body, flags=0x40)
    sdk = root / "authored-editor-resources"
    sdk.write_bytes(serialized(sdk_kind, native, bytes(32), 91))
    sdk_pin = {"bytes": sdk.stat().st_size, "sha256": P.sha(sdk), "path_id": 91}
    selected = {
        "file": "authored-properties",
        "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": P.sha(source)},
        "objects": [
            {
                "source_path_id": 55,
                "path_id": 1,
                "bytes": len(source_body),
                "source_sha256": pin(source_body)[1],
                "sha256": pin(target_body)[1],
                "references": [{"offset": 16, "from": [1, -77], "to": [1, 33]}],
            }
        ],
        "script": [1, 33],
        "externals": ["globalgamemanagers.assets"],
        "script_properties": {"path": script.name, "member": "CAB-script", "bytes": script.stat().st_size, "sha256": P.sha(script), "path_id": -77},
    }
    # Independent explicit feed: SDK native nodes then the one original custom
    # field. All fixture node versions are 1 and only string nodes align.
    feed = bytearray(b"FixtureInventedFixture.dll")

    def hash_node(node):
        kind, name, size, flags, meta, children = node
        feed.extend(kind.encode() + name.encode() + struct.pack("<iiiI", size, flags, 1, meta & 0x4000))
        for child in children:
            hash_node(child)

    hash_node(native)
    hash_node(original[-1][-1])
    return selected, sdk, sdk_pin, P.SCRIPT.md4(feed), target_body


class SourceMetadataTests(unittest.TestCase):
    def fixture(self):
        tree = metadata_tree(
            (
                "Material",
                "Base",
                -1,
                0,
                0,
                [
                    metadata_string("ignored"),
                    ("PPtr<Shader>", "m_Shader", -1, 0, 0, [("int", "m_FileID", 4, 0, 0, []), ("SInt64", "m_PathID", 8, 0, 0, [])]),
                    ("vector", "m_ValidKeywords", -1, 0, 0x4000, [("Array", "Array", -1, 1, 0, [("int", "size", 4, 0, 0, []), metadata_string("data")])]),
                    metadata_string("m_ShaderKeywords"),
                ],
            )
        )

        def string(value):
            data = value.encode()
            return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)

        body = string("unselected") + struct.pack("<iqI", 2, -19, 2) + string("CUTOUT") + string("FEATURE_\u2603") + string("LEGACY FOG_LINEAR")
        return tree, body

    def test_source_tree_selects_nested_arrays_strings_and_raw_pointer_bits(self):
        tree, body = self.fixture()
        self.assertEqual(
            P.metadata_fields(body, tree, {"m_Shader", "m_ValidKeywords", "m_ShaderKeywords"}),
            {"m_Shader": {"m_FileID": 2, "m_PathID": (1 << 64) - 19}, "m_ValidKeywords": ["CUTOUT", "FEATURE_\u2603"], "m_ShaderKeywords": "LEGACY FOG_LINEAR"},
        )
        self.assertEqual(P.metadata_fields(body, tree, {"absent"}), {})

    def test_source_field_extent_refuses_truncated_or_trailing_bytes(self):
        tree, body = self.fixture()
        for changed in (body[:-1], body + b"extra"):
            with self.subTest(size=len(changed)), self.assertRaises(ValueError):
                P.metadata_fields(changed, tree, {"m_ValidKeywords"})

    def test_source_array_rejects_unbounded_count(self):
        tree, body = self.fixture()
        changed = bytearray(body)
        struct.pack_into("<I", changed, 28, 1000001)
        root = P.OBJECTS.M._mesh.type_tree(io.BytesIO(tree["tree"]))
        with self.assertRaises(ValueError):
            P.metadata_value(changed, root.children[2], 28)


class ShaderManifestTextTests(unittest.TestCase):
    def test_generated_manifest_uses_source_text_type_and_checked_json_body(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            pc = root / "pc"
            pc.mkdir()
            selected, _ = text_fixture(pc, root)
            manifest = {"features": ["AUTHORED"], "variants": [{"resource": "Fixture", "keywords": []}]}
            stream = io.BytesIO()
            P.OBJECTS.aligned_string(stream, "FixtureManifest")
            P.OBJECTS.aligned_string(stream, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            body = stream.getvalue()
            item = {"file": "authored-manifest-player", "name": "FixtureManifest", "manifest": "standard", "bytes": len(body), "sha256": pin(body)[1]}
            selected["files"] = [item]
            selected["manifests"] = {"path": "fixture-selectors.json"}
            output = root / "output"
            (output / P.TARGET).mkdir(parents=True)
            with patch.object(P, "shader_manifests", return_value=({"standard": manifest}, [])) as source:
                P.text_files(root, pc, selected, output)
            source.assert_called_once_with(root, pc, selected["manifests"])
            data = (output / P.TARGET / item["file"]).read_bytes()
            self.assertEqual(data[4096:], body)
            # Independently inspect the stripped native type and local identity.
            self.assertEqual(data[48:65], b"2021.3.45f2\0" + struct.pack("<i?", 13, False))
            self.assertEqual(struct.unpack_from("<I", data, 65)[0], 1)
            self.assertEqual(data[69:92], struct.pack("<iBh", 49, 0, -1) + b"T" * 16)
            selected["files"][0]["name"] = "Unpinned name"
            rejected = root / "rejected"
            (rejected / P.TARGET).mkdir(parents=True)
            with (
                patch.object(P, "shader_manifests", return_value=({"standard": manifest}, [])),
                self.assertRaisesRegex(ValueError, "produced TextAsset body differs"),
            ):
                P.text_files(root, pc, selected, rejected)
            self.assertFalse((rejected / P.TARGET / item["file"]).exists())


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


def builtin_fixture(root):
    """Authored editor-only fields surround independently named runtime fields."""
    name = struct.pack("<I", 7) + b"Builtin\0"
    editor_prefix = b"editor object fields".ljust(40, b"!")
    texture_header = bytes(range(40))
    pixels = b"authored inline mip pixels and sampler data"
    texture = editor_prefix + name + b"editor hash!!!!!" + texture_header + b"VT!?" + pixels
    sprite_header = bytes(range(60))
    original_key = b"source GUID!!!!!" + struct.pack("<q", 21300000)
    runtime_rd = struct.pack("<iqiq", 0, 701, 0, 0) + b"original geometry and UV data".ljust(372, b"g")
    physics_and_bones = struct.pack("<II", 0, 0)
    sprite = (
        editor_prefix
        + name
        + sprite_header
        + b"atlas name/tag!!"
        + original_key
        + bytes(16)
        + runtime_rd
        + b"editor atlas geometry".ljust(396, b"d")
        + physics_and_bones
        + b"editor sprite ID".ljust(36, b"i")
    )
    types = [{"class_id": cid, "stripped": 0, "script_type": -1, "hash": b"E" * 16} for cid in (28, 213)]
    layout = {
        "engine": "2021.3.45f2",
        "platform": -2,
        "trees": False,
        "types": types,
        "objects": [
            {"path_id": 701, "offset": 0, "bytes": len(texture), "type_id": 0},
            {"path_id": 702, "offset": (len(texture) + 7) // 8 * 8, "bytes": len(sprite), "type_id": 1},
        ],
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    source = root / "authored-unity_builtin_extra"
    with source.open("xb") as stream:
        P.W.write_serialized(stream, layout, lambda row: io.BytesIO(texture if row["type_id"] == 0 else sprite))
    expected_texture = name + texture_header + pixels
    expected_rd = struct.pack("<iqiq", 0, 1, 0, 0) + runtime_rd[24:]
    expected_sprite = name + sprite_header + bytes(8) + b"\x0f" + bytes(7) + struct.pack("<q", 702) + bytes(16) + expected_rd + physics_and_bones
    selected = {
        "file": "0000000000000000f000000000000000",
        "source": {"bytes": source.stat().st_size, "sha256": P.sha(source)},
        "textures": [701],
        "sprites": [702],
    }
    return source, selected, (expected_texture, expected_sprite)


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

    def produce(self, output=None, texture_packs=(), builtin_extra=None, editor_resources=None):
        return P.produce(
            self.profile_path,
            self.profile_hash,
            self.pc,
            self.sdk,
            self.converter,
            self.receipt_hash,
            output or self.output,
            texture_packs,
            builtin_extra,
            editor_resources,
        )

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

    def test_builtin_editor_fields_are_removed_and_runtime_data_and_pc_types_preserved(self):
        source, selected, expected = builtin_fixture(self.root)
        self.profile["builtin_ui"] = selected
        destination = self.root / "builtin-player"
        P.builtin_ui(self.pc, self.profile, source, destination)
        with destination.open("rb") as stream:
            stream.size = destination.stat().st_size
            layout = P.W.read_serialized(stream)
            self.assertEqual(layout["platform"], 13)
            self.assertFalse(layout["trees"])
            self.assertEqual([row["hash"] for row in layout["types"]], [bytes([2]) * 16, b"S" * 16])
            self.assertEqual(layout["externals"], [])
            for row, body in zip(layout["objects"], expected):
                stream.seek(layout["data_offset"] + row["offset"])
                self.assertEqual(stream.read(row["bytes"]), body)
        self.profile["outputs"][selected["file"]] = {"bytes": destination.stat().st_size, "sha256": P.sha(destination)}
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_hash = P.sha(self.profile_path)
        result = self.produce(builtin_extra=source)
        self.assertEqual((self.output / (P.TARGET + selected["file"])).read_bytes(), destination.read_bytes())
        self.assertEqual(result["files"][P.TARGET + selected["file"]]["source_role"], "sdk-and-pc-types")
        with self.assertRaisesRegex(ValueError, "explicit --builtin-extra"):
            self.produce(self.root / "builtin-missing")
        source.write_bytes(b"changed SDK source")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            self.produce(self.root / "builtin-drift", builtin_extra=source)

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

    def test_selected_script_hash_uses_actual_original_identity_and_sdk_base(self):
        selected, sdk, sdk_pin, expected_hash, target_body = script_properties_fixture(self.root, self.pc)
        native = P.script_sdk_schema(sdk, sdk_pin)
        destination = self.root / "properties-player"
        P.object_file(self.pc, selected, destination, native)
        with destination.open("rb") as stream:
            stream.size = destination.stat().st_size
            layout = P.W.read_serialized(stream)
            self.assertEqual(layout["types"], [{"class_id": 114, "stripped": 0, "script_type": 0, "script_id": b"I" * 16, "hash": expected_hash}])
            self.assertEqual(layout["scripts"], [(1, 33)])
            stream.seek(layout["data_offset"])
            self.assertEqual(stream.read(), target_body)
        changed, sdk, sdk_pin, changed_hash, _ = script_properties_fixture(self.root, self.pc, custom_name="different")
        self.assertNotEqual(changed_hash, expected_hash)
        P.object_file(self.pc, changed, self.root / "changed-properties", P.script_sdk_schema(sdk, sdk_pin))
        with (self.root / "changed-properties").open("rb") as stream:
            stream.size = (self.root / "changed-properties").stat().st_size
            self.assertEqual(P.W.read_serialized(stream)["types"][0]["hash"], changed_hash)

    def test_selected_script_requires_admitted_sdk_and_linked_original_script(self):
        selected, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc)
        with self.assertRaisesRegex(ValueError, "explicit --editor-resources"):
            P.script_sdk_schema(None, sdk_pin)
        with self.assertRaisesRegex(ValueError, "SDK base schema"):
            P.object_file(self.pc, selected, self.root / "missing-sdk")
        native = P.script_sdk_schema(sdk, sdk_pin)
        for field, value in (("path_id", -78), ("member", "CAB-other")):
            changed = json.loads(json.dumps(selected))
            changed["script_properties"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "source relationship"):
                P.object_file(self.pc, changed, self.root / ("wrong-" + field), native)
        for script_kind, sdk_kind, message in ((115, 21, "SDK script base"), (21, 114, "MonoScript type")):
            selected, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc, script_kind, sdk_kind)
            with self.subTest(kind=message), self.assertRaisesRegex(ValueError, message):
                native = P.script_sdk_schema(sdk, sdk_pin)
                P.object_file(self.pc, selected, self.root / ("wrong-type-" + str(script_kind)), native)
        selected, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc, identity_fields=("m_ClassName", "m_Namespace"))
        with self.assertRaisesRegex(ValueError, "identity fields"):
            P.object_file(self.pc, selected, self.root / "missing-identity", P.script_sdk_schema(sdk, sdk_pin))
        selected, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc, object_kind=21)
        with self.assertRaisesRegex(ValueError, "standalone MonoBehaviour"):
            P.object_file(self.pc, selected, self.root / "wrong-object-class", P.script_sdk_schema(sdk, sdk_pin))

    def test_sdk_base_requires_embedded_schema_and_rechecks_after_read(self):
        _, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc)
        read = P.W.read_serialized
        with sdk.open("rb") as stream:
            stream.size = sdk.stat().st_size
            layout = read(stream)
        layout["trees"] = False
        with sdk.open("wb") as stream:
            P.W.write_serialized(stream, layout, lambda _: io.BytesIO(bytes(32)))
        sdk_pin.update(bytes=sdk.stat().st_size, sha256=P.sha(sdk))
        with self.assertRaisesRegex(ValueError, "SDK script base type/schema"):
            P.script_sdk_schema(sdk, sdk_pin)
        _, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc)
        original = sdk.read_bytes()

        def mutate_after_read(*args):
            result = read(*args)
            sdk.write_bytes(original + b"during read")
            return result

        with patch.object(P.W, "read_serialized", side_effect=mutate_after_read), self.assertRaisesRegex(ValueError, "bytes differ"):
            P.script_sdk_schema(sdk, sdk_pin)

    def test_script_provider_drift_before_and_after_output_refuses(self):
        selected, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc)
        native = P.script_sdk_schema(sdk, sdk_pin)
        script = self.pc / selected["script_properties"]["path"]
        original = script.read_bytes()
        script.write_bytes(original + b"drift")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            P.object_file(self.pc, selected, self.root / "early-script-drift", native)
        script.write_bytes(original)
        write = P.W.write_serialized

        def mutate_script(*args):
            write(*args)
            script.write_bytes(original + b"late drift")

        with patch.object(P.W, "write_serialized", side_effect=mutate_script), self.assertRaisesRegex(ValueError, "bytes differ"):
            P.object_file(self.pc, selected, self.root / "late-script-drift", native)

    def test_sdk_drift_is_rechecked_before_read_and_after_final_output(self):
        _, sdk, sdk_pin, _, _ = script_properties_fixture(self.root, self.pc)
        original = sdk.read_bytes()
        sdk.write_bytes(original + b"early drift")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            P.script_sdk_schema(sdk, sdk_pin)
        sdk.write_bytes(original)
        self.profile["script_properties_sdk"] = sdk_pin
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_hash = P.sha(self.profile_path)
        write = P.W.write_serialized

        def mutate_sdk(*args):
            write(*args)
            sdk.write_bytes(original + b"late drift")

        with patch.object(P.W, "write_serialized", side_effect=mutate_sdk), self.assertRaisesRegex(ValueError, "bytes differ"):
            self.produce(editor_resources=sdk)
        self.failed()

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
        renamed = string("NativeUiMaterial0") + relocated[len(prefix) :]
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
        for index, body in enumerate((relocated, demoted, renamed)):
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
                        "source_bytes": len(source_body),
                        "source_sha256": pin(source_body)[1],
                        "sha256": pin(body)[1],
                        "references": [
                            {"offset": len(prefix), "from": [3, 77], "to": [1, 1]},
                            {"offset": len(source_body) - len(tail), "from": [0, -91], "to": [2, 1]},
                        ],
                    }
                ],
            }
            if index == 1:
                selected["objects"][0]["keyword_policy"] = "dummy-shader-demote-valid"
            elif index == 2:
                selected["objects"][0]["rename"] = "NativeUiMaterial0"
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

    def test_material_clone_filters_by_original_shader_and_preserves_source_ranges(self):
        def string(value):
            data = value.encode()
            return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)

        def property(name, kind):
            return (
                string(name)
                + string("Authored description")
                + struct.pack("<I", 1)
                + string("Authored attribute")
                + struct.pack("<iI4f", kind, 19, 0.25, -3.0, 7.0, 1.0)
                + string("authored default")
                + struct.pack("<i", 2)
            )

        def environment(name, pointer, values):
            return string(name) + struct.pack("<iq4f", *pointer, *values)

        shader_body = string("Original shader") + struct.pack("<I", 3) + property("_KeepA", 4) + property("_Scalar", 2) + property("_KeepB", 4)
        # Material order deliberately differs from the shader's property order.
        env_b = environment("_KeepB", (3, 71), (2.0, 0.5, -4.0, 6.0))
        env_removed = environment("_Discard", (5, 90), (8.0, -1.0, 0.25, 11.0))
        env_a = environment("_KeepA", (7, -82), (0.125, 9.0, -2.0, 3.0))
        keywords = struct.pack("<I", 1) + string("SOURCE_ON") + struct.pack("<I", 1) + string("SOURCE_OFF")
        fields = struct.pack("<IBB2xiI", 4, 1, 0, 2333, 1) + string("SourceTag") + string("SourceValue") + struct.pack("<I", 1) + string("SourcePass")
        prefix = string("Original material") + struct.pack("<iq", 2, 99) + keywords + fields
        tail = (
            struct.pack("<I", 1)
            + string("_Integer")
            + struct.pack("<iI", -12, 1)
            + string("_Scalar")
            + struct.pack("<fI", -7.25, 1)
            + string("_Colour")
            + struct.pack("<4fI", 0.125, -2.0, 3.0, 0.5, 0)
        )
        material_body = prefix + struct.pack("<I", 3) + env_b + env_removed + env_a + tail
        expected = string("FontMaterialFixture") + struct.pack("<iq", 1, 1) + keywords + fields + struct.pack("<I", 2)
        expected += environment("_KeepB", (2, 1), (2.0, 0.5, -4.0, 6.0)) + environment("_KeepA", (3, 1), (0.125, 9.0, -2.0, 3.0)) + tail

        def write_source(path, body, kind):
            layout = {
                "engine": "2021.3.45f2",
                "platform": 19,
                "trees": False,
                "types": [{"class_id": kind, "stripped": 0, "script_type": -1, "hash": b"F" * 16}],
                "objects": [{"path_id": 55, "offset": 0, "bytes": len(body), "type_id": 0}],
                "scripts": [],
                "externals": [],
                "ref_types": [],
                "user": "",
            }
            with path.open("wb") as stream:
                P.W.write_serialized(stream, layout, lambda row: io.BytesIO(body))
            return {"path": path.name, "bytes": path.stat().st_size, "sha256": P.sha(path)}

        material_path, shader_path = self.pc / "clone-material.assets", self.pc / "clone-shader.assets"
        selected = {
            "file": "authored-clone",
            "source": write_source(material_path, material_body, 21),
            "material_shader": {**write_source(shader_path, shader_body, 48), "path_id": 55},
            "externals": ["authored-shader", "authored-texture-b", "authored-texture-a"],
            "objects": [
                {
                    "source_path_id": 55,
                    "path_id": 1,
                    "source_bytes": len(material_body),
                    "bytes": len(expected),
                    "source_sha256": pin(material_body)[1],
                    "sha256": pin(expected)[1],
                    "rename": "FontMaterialFixture",
                    "references": [
                        {"offset": len(string("Original material")), "from": [2, 99], "to": [1, 1]},
                        {"offset": len(prefix) + 4 + len(string("_KeepB")), "from": [3, 71], "to": [2, 1]},
                        {"offset": len(prefix) + 4 + len(env_b) + len(env_removed) + len(string("_KeepA")), "from": [7, -82], "to": [3, 1]},
                    ],
                }
            ],
        }
        destination = self.root / "material-clone"
        P.object_file(self.pc, selected, destination)
        with destination.open("rb") as stream:
            stream.size = destination.stat().st_size
            layout = P.W.read_serialized(stream)
            stream.seek(layout["data_offset"])
            self.assertEqual(stream.read(), expected)
        self.assertEqual(layout["types"], [{"class_id": 21, "stripped": 0, "script_type": -1, "hash": b"F" * 16}])
        self.assertEqual(P.sha(material_path), selected["source"]["sha256"])
        self.assertEqual(P.sha(shader_path), selected["material_shader"]["sha256"])
        with shader_path.open("ab") as stream:
            stream.write(b"drift")
        with self.assertRaisesRegex(ValueError, "player-data bytes differ"):
            P.object_file(self.pc, selected, self.root / "shader-drift-before")
        selected["material_shader"] = {**write_source(shader_path, shader_body, 21), "path_id": 55}
        with self.assertRaisesRegex(ValueError, "shader source type"):
            P.object_file(self.pc, selected, self.root / "wrong-shader-type")
        selected["material_shader"] = {**write_source(shader_path, shader_body, 48), "path_id": 55}
        selected["source"] = write_source(material_path, material_body, 28)
        with self.assertRaisesRegex(ValueError, "only material texture"):
            P.object_file(self.pc, selected, self.root / "wrong-clone-type")
        selected["source"] = write_source(material_path, material_body, 21)
        original_write = P.W.write_serialized

        def drift_after_write(*args):
            original_write(*args)
            with shader_path.open("ab") as stream:
                stream.write(b"late drift")

        with patch.object(P.W, "write_serialized", side_effect=drift_after_write):
            with self.assertRaisesRegex(ValueError, "player-data bytes differ"):
                P.object_file(self.pc, selected, self.root / "shader-drift-after")
        self.assertTrue((self.root / "shader-drift-after").is_file())
        with self.assertRaisesRegex(ValueError, "string bound"):
            P.material_textures(struct.pack("<I", 4097), {"_KeepA"})
        with self.assertRaisesRegex(ValueError, "count bound"):
            P.material_textures(string("") + bytes(12) + struct.pack("<I", 4097), {"_KeepA"})
        with self.assertRaisesRegex(ValueError, "truncated"):
            P.material_textures(material_body[: len(prefix) + 6], {"_KeepA"})

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
