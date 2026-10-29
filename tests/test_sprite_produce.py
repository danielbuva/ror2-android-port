"""Authored original-bundle → PNG/native supplier → record-pack contract."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


P = load("sprite_produce", ROOT / "tools/phone-build/accepted-output/sprite_produce.py")
S = load("sprite_record_fixture", ROOT / "tests/test_sprite_native_record.py")
R = load("serialized_fixture", ROOT / "tests/test_phone_record_producer.py")
F = S.F


def fixture(directory):
    pc = directory / "original"
    pc.mkdir()
    body, root, native = S.fixture()
    _, spans = P.A.fields(body, root)
    point = spans[("m_RD", "textureRect")][0]
    body = body[:point] + struct.pack("<I", 64) + body[point:]
    rd = next(node for node in root.children if node.name == "m_RD")
    rd.children.insert(next(i for i, node in enumerate(rd.children) if node.name == "textureRect"), F.node("settingsRaw", 4))
    _, spans = P.A.fields(body, root)
    body = bytearray(body)
    struct.pack_into("<iq", body, spans[("m_RD", "texture")][0], 0, 88)
    body = bytes(body)
    rgba = bytes((i * 17) % 256 for i in range(16 * 8 * 4))
    texture = struct.pack("<iii", 16, 8, 4) + F.vector(rgba, len(rgba))
    texture_root = F.node(
        "Base", children=[F.node("m_Width", 4), F.node("m_Height", 4), F.node("m_TextureFormat", 4), F.array("image data", F.node("data", 1))]
    )

    def metadata(body, root, class_id):
        raw = R.serialized(body, root, class_id=class_id)
        stream = io.BytesIO(raw)
        stream.size = len(raw)
        return P.W.read_serialized(stream)

    first = metadata(body, root, 213)
    second = metadata(texture, texture_root, 28)
    first["types"].append(second["types"][0])
    first.pop("data_offset")
    first.pop("bytes")
    first["objects"] = [dict(path_id=77, offset=0, bytes=len(body), type_id=0), dict(path_id=88, offset=len(body), bytes=len(texture), type_id=1)]
    stream = io.BytesIO()
    P.W.write_serialized(stream, first, lambda obj: io.BytesIO(body if obj["path_id"] == 77 else texture))
    bundle = pc / "original.bundle"
    bundle.write_bytes(F.bundle([("CAB-authored", stream.getvalue(), 4)]))
    references = [dict(offset=spans[("m_RD", "texture")][0], **{"from": [0, 88], "to": [0, 99]})]
    expected = P.A.O.remap(P.A.O.module("player_data").sprite_key(body, "1" * 32), references)
    target = dict(
        bundle="authored-output", member="CAB-output", path_id=123, bytes=len(expected), sha256=hashlib.sha256(expected).hexdigest(), references=references
    )
    selected = dict(
        id="authored",
        path_id=77,
        sha256=hashlib.sha256(body).hexdigest(),
        texture=dict(path_id=88, sha256=hashlib.sha256(texture).hexdigest()),
        importer_guid="1" * 32,
        outputs=[target],
    )
    profile = directory / "profile.json"
    profile.write_text(
        json.dumps(
            dict(
                schema=1,
                input_id=P.M.INPUT_ID,
                bundles=[dict(path="original.bundle", sha256=P.B.sha(bundle), members=[dict(name="CAB-authored", objects=[selected])])],
            )
        )
    )
    native.update(id="authored", vertex_xy_bits=[0] * 8, triangles=[0] * 6, physics=[])
    supplier = directory / "native.json"
    supplier.write_text(json.dumps(dict(success=True, unity_version="2021.3.45f2", items=[native])))
    decoder = directory / "unused-rgba32-decoder"
    decoder.write_bytes(b"authored pinned decoder identity; RGBA32 needs no executable")
    return pc, bundle, profile, supplier, decoder, rgba, expected


class SpriteProduceTests(unittest.TestCase):
    def test_original_pixels_and_native_output_produce_exact_persisted_pack(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pc, bundle, profile, native, decoder, rgba, expected = fixture(directory)
            original_hash = P.B.sha(bundle)
            prepared = directory / "prepared"
            receipt = P.prepare(profile, P.B.sha(profile), pc, decoder, P.B.sha(decoder), prepared)
            self.assertTrue(receipt["success"])
            request = json.loads((prepared / "sprite-source-request.json").read_text())["items"][0]
            self.assertEqual(request["mesh_type"], 1)
            self.assertEqual(request["rect"], [0, 0, 16, 8])
            png = Path(request["png"]).read_bytes()
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            chunks, offset = {}, 8
            while offset < len(png):
                length = struct.unpack_from(">I", png, offset)[0]
                kind, data = png[offset + 4 : offset + 8], png[offset + 8 : offset + 8 + length]
                self.assertEqual(struct.unpack_from(">I", png, offset + 8 + length)[0], zlib.crc32(kind + data))
                chunks[kind] = data
                offset += 12 + length
            scanlines = zlib.decompress(chunks[b"IDAT"])
            self.assertEqual(scanlines[:65], b"\0" + rgba[-64:])
            self.assertEqual(scanlines[-65:], b"\0" + rgba[:64])
            output = directory / "pack"
            result = P.produce(profile, P.B.sha(profile), pc, native, P.B.sha(native), output)
            self.assertTrue(result["success"])
            self.assertEqual((output / "objects.bin").read_bytes(), expected)
            self.assertEqual(json.loads((output / "index.jsonl").read_text())["offset"], 0)
            self.assertEqual(P.B.sha(bundle), original_hash)

    def test_provider_drift_and_output_inside_original_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pc, _, profile, native, decoder, _, _ = fixture(directory)
            with self.assertRaisesRegex(ValueError, "decoder drift"):
                P.prepare(profile, P.B.sha(profile), pc, decoder, "0" * 64, directory / "bad-provider")
            self.assertFalse((directory / "bad-provider").exists())
            with self.assertRaisesRegex(ValueError, "outside original"):
                P.produce(profile, P.B.sha(profile), pc, native, P.B.sha(native), pc / "forbidden-output")
            self.assertFalse((pc / "forbidden-output").exists())


if __name__ == "__main__":
    unittest.main()
