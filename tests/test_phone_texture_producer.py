"""Authored BC1 and byte-range texture contracts; no game or editor inputs."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


T = load("texture_producer", ROOT / "tools/phone-build/accepted-output/texture_produce.py")
JPEG_BUILD = load("jpeg_builder", ROOT / "tools/phone-build/accepted-output/build_texture_jpeg.py")
ETC_BUILD = load("etc_builder", ROOT / "tools/phone-build/accepted-output/build_texture_etc.py")
FIXTURE = load("authored_bundle_fixture", ROOT / "tests/test_phone_mesh_producer.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def string(value):
    encoded = value.encode()
    return struct.pack("<I", len(encoded)) + encoded + b"\0" * (-len(encoded) % 4)


def authored_body(name, image_size, texture_format, pixels, stream, usage=0):
    """Independent field ordering with sentinel bytes between selected fields."""
    data = bytearray(b"AUTHORED")
    spans = {}
    values = [
        ("m_Name", string(name)),
        ("m_CompleteImageSize", struct.pack("<I", image_size)),
        ("m_TextureFormat", struct.pack("<i", texture_format)),
        ("m_IsAlphaChannelOptional", b"\0"),
        (None, b"\x11\x22\x33"),
        ("m_LightmapFormat", struct.pack("<i", usage)),
        (None, b"KEEP"),
        ("image data", struct.pack("<I", len(pixels)) + pixels + b"\0" * (-len(pixels) % 4)),
        ("m_StreamData", struct.pack("<QI", stream["offset"], stream["size"]) + string(stream["path"])),
    ]
    for key, value in values:
        if key:
            spans[key] = [len(data), len(value)]
        data.extend(value)
    data.extend(b"TAIL")
    return bytes(data), spans


class TextureProducerTests(unittest.TestCase):
    def test_rgba_bc3_palette_alpha_and_logical_cropping(self):
        selectors = sum((index % 8) << (3 * index) for index in range(16))
        colours = struct.pack("<HHI", 0, 0xFFFF, 0xAAAAAAAA)
        block = bytes([0, 255]) + selectors.to_bytes(6, "little") + colours
        alphas = [0, 255, 51, 102, 153, 204, 0, 255] * 2
        self.assertEqual(T.rgba_source(block, 4, 4, 12), b"".join(bytes([85, 85, 85, a]) for a in alphas))
        block = bytes([255, 0]) + selectors.to_bytes(6, "little") + colours
        alphas = [255, 0, 218, 182, 145, 109, 72, 36] * 2
        self.assertEqual(T.rgba_source(block, 4, 4, 12), b"".join(bytes([85, 85, 85, a]) for a in alphas))
        self.assertEqual(T.rgba_source(block, 1, 1, 12), bytes([85, 85, 85, 255]))
        transparent = struct.pack("<HHI", 0, 0xFFFF, 0xFFFFFFFF)
        self.assertEqual(T.rgba_source(transparent, 4, 4, 10), bytes(64))
        self.assertEqual(T.rgba_source(struct.pack("<HH", 0, 65535), 2, 1, 9), bytes([0, 0, 0, 255, 255, 0, 0, 255]))
        for fmt, source in ((3, bytes(2)), (4, bytes(3)), (9, b"x"), (10, bytes(7)), (12, bytes(15)), (99, b"")):
            with self.subTest(fmt=fmt), self.assertRaises(ValueError):
                T.rgba_source(source, 1, 1, fmt)

    def test_normal_unpack_uses_ag_coordinates_and_integer_blue(self):
        source = bytes([19, 128, 49, 128, 31, 128, 29, 255, 0, 128, 0, 0, 6, 0, 12, 128])
        self.assertEqual(T.normal_rgb(source), bytes([128, 128, 254, 255, 128, 127, 0, 128, 127, 128, 0, 127]))

    def test_public_alpha_source_provider_drift_refuses_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provider = root / "authored-source"
            provider.write_bytes(b"authored non-provider fixture")
            with self.assertRaisesRegex(ValueError, "provider drift"):
                ETC_BUILD.build(provider, provider, root / "output")
            self.assertFalse((root / "output").exists())

    def test_alpha_inline_source_and_target_field_projection(self):
        pixels = bytes(range(16))
        empty = {"offset": 0, "size": 0, "path": ""}
        body, fields = authored_body("Alpha source", 16, 1, pixels, empty)
        target = {"name": "Authored target", "alpha_optional": False, "usage": 0, "inline": True, "stream": empty}
        expected, _ = authored_body(target["name"], 16, 47, pixels, empty)
        self.assertEqual(T.body_output(body, fields, pixels, target, "alpha8-etc2"), expected)
        start, _ = fields["image data"]
        selected = {"pixels": {"member": None, "offset": start + 4, "bytes": 16, "sha256": digest(pixels)}, "operation": "alpha8-etc2", "width": 4, "height": 4}
        with self.assertRaisesRegex(ValueError, "ETC codec required"):
            T.pixels_input(None, body, selected)

    def test_public_alpha_codec_authored_pixels_and_input_extent(self):
        codec = os.environ.get("ROR2_TEXTURE_ETC")
        if not codec:
            self.skipTest("explicit locally built public Alpha8 codec is absent")
        # These three complete block hashes derive solely from authored alpha
        # patterns (zero, opaque and an asymmetric ramp), never game pixels.
        controls = (
            (bytes(16), "b0aa3ff40c657793d226b9fcd215c20d6a93313be1bf327b69144d40220817a4"),
            (bytes([255]) * 16, "8f9ccc8e3d3b453e5cb747a105908186456f2056af1cd4f3f049b60fed2d343c"),
            (bytes(range(0, 256, 17)), "1fa5776f4e0f0720374eb294f5a8fbae7e2edbb716977f1d8b012b14934ce901"),
        )
        for pixels, pin in controls:
            selected = {
                "pixels": {"member": None, "offset": 0, "bytes": len(pixels), "sha256": digest(pixels)},
                "operation": "alpha8-etc2",
                "width": 4,
                "height": 4,
            }
            result = T.pixels_input(None, pixels, selected, etc_codec=Path(codec))
            self.assertEqual(len(result), 16)
            self.assertEqual(digest(result), pin)
        for args, data in ((["4", "4"], bytes(15)), (["4", "4"], bytes(17)), (["2", "4"], bytes(8)), (["8193", "4"], b"")):
            with self.subTest(args=args, bytes=len(data)):
                result = subprocess.run([codec, *args, "alpha8"], input=data, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_public_rgb_codec_and_normal_source_pipeline(self):
        codec = os.environ.get("ROR2_TEXTURE_ETC")
        if not codec:
            self.skipTest("explicit locally built public ETC codec is absent")
        empty = {"offset": 0, "size": 0, "path": ""}
        controls = (
            (3, 0, bytes([0, 255, 0]) * 16, "8960179770da4d8fcd19e783e9955be93cf0e04587801bb1ee97eddbe291b617"),
            (3, 0, bytes([17, 31, 73]) * 16, "12480c7cdf8719afca8fc7f63fa8cfac4fc7b445924da0644e8d618b65981344"),
            (4, 3, bytes([19, 128, 49, 128]) * 16, "5e2ad0f0d6efbe7f93981a44ee8846830e265f7a767f54427f23e44880da1eab"),
        )
        for fmt, usage, pixels, pin in controls:
            body, fields = authored_body("Original", len(pixels), fmt, pixels, empty, usage)
            start, _ = fields["image data"]
            selected = {
                "fields": fields,
                "pixels": {"member": None, "offset": start + 4, "bytes": len(pixels), "sha256": digest(pixels)},
                "operation": "etc1",
                "width": 4,
                "height": 4,
                "jpeg": False,
            }
            encoded = T.pixels_input(None, body, selected, etc_codec=Path(codec))
            self.assertEqual(len(encoded), 8)
            self.assertEqual(digest(encoded), pin)
            target = {"name": "Converted", "alpha_optional": False, "usage": 4 if usage == 3 else 0, "inline": True, "stream": empty}
            expected, _ = authored_body(target["name"], 8, 34, encoded, empty, target["usage"])
            self.assertEqual(T.body_output(body, fields, encoded, target, "etc1"), expected)

    def test_public_jpeg_source_provider_drift_refuses_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provider = root / "authored-source"
            provider.write_bytes(b"authored non-provider fixture")
            with self.assertRaisesRegex(ValueError, "provider drift"):
                JPEG_BUILD.build(provider, provider, provider, root / "output")
            self.assertFalse((root / "output").exists())

    def test_public_jpeg_codec_authored_pixels_and_input_extent(self):
        codec = os.environ.get("ROR2_TEXTURE_JPEG")
        if not codec:
            self.skipTest("explicit locally built public JPEG codec is absent")
        # Constant grayscale blocks have exact DC values and neutral chroma.
        pixels = bytes(16 * 8 * 3) + bytes([255]) * (16 * 8 * 3)
        result = subprocess.run([codec, "16", "16"], input=pixels, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, pixels)
        for args, data in ((["16", "16"], pixels[:-1]), (["16", "16"], pixels + b"x"), (["0", "16"], b""), (["8193", "1"], b"")):
            with self.subTest(args=args, bytes=len(data)):
                result = subprocess.run([codec, *args], input=data, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_dilation_uses_original_seed_coordinates_and_preserves_alpha(self):
        # A single visible texel extends 31 positions, without wrapping an edge.
        hidden, visible = bytes([17, 29, 41, 0]), bytes([103, 151, 197, 1])
        source = visible + hidden * 64
        expected = visible + (visible[:3] + b"\0") * 31 + hidden * 33
        self.assertEqual(T.dilate_rgba(source, 65, 1), expected)
        self.assertEqual(T.dilate_rgba(source, 1, 65), expected)
        # Cardinal jumps cannot reach diagonal corners from this isolated seed.
        source = hidden * 4 + visible + hidden * 4
        filled = visible[:3] + b"\0"
        expected = hidden + filled + hidden + filled + visible + filled + hidden + filled + hidden
        self.assertEqual(T.dilate_rgba(source, 3, 3), expected)
        # Equal-distance coordinates retain the existing seed before neighbors;
        # left precedes right for a newly reached texel.
        red, blue = bytes([211, 13, 7, 255]), bytes([5, 11, 223, 9])
        source = red + hidden * 3 + blue
        expected = red + (red[:3] + b"\0") * 2 + blue[:3] + b"\0" + blue
        self.assertEqual(T.dilate_rgba(source, 5, 1), expected)
        self.assertEqual(T.dilate_rgba(hidden * 6, 3, 2), hidden * 6)
        for width, height, data in ((0, 1, b""), (True, 1, visible), (1, 1, visible[:3]), (8193, 1, b"")):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                T.dilate_rgba(data, width, height)

    def test_bc1_palette_selectors_and_logical_edge_cropping(self):
        # Red/blue endpoints and all four selectors in each row.
        block = struct.pack("<HHI", 0xF800, 0x001F, 0xE4E4E4E4)
        expected_row = bytes([255, 0, 0, 0, 0, 255, 170, 0, 85, 85, 0, 170])
        self.assertEqual(T.dxt1_rgb(block, 4, 4), expected_row * 4)
        green = struct.pack("<HHI", 0x07E0, 0, 0)
        blue = struct.pack("<HHI", 0x001F, 0, 0)
        red = struct.pack("<HHI", 0xF800, 0, 0)
        white = struct.pack("<HHI", 0xFFFF, 0, 0)
        expected = (bytes([0, 255, 0]) * 4 + bytes([0, 0, 255])) * 4 + bytes([255, 0, 0]) * 4 + bytes([255, 255, 255])
        self.assertEqual(T.dxt1_rgb(green + blue + red + white, 5, 5), expected)
        # Three-colour mode uses black for the transparent selector after RGB projection.
        transparent = struct.pack("<HHI", 0, 0xFFFF, 0xFFFFFFFF)
        self.assertEqual(T.dxt1_rgb(transparent, 4, 4), bytes(48))
        halfway = struct.pack("<HHI", 0, 0xFFFF, 0xAAAAAAAA)
        self.assertEqual(T.dxt1_rgb(halfway, 4, 4), bytes([127, 127, 127]) * 16)
        for width, height, data in ((0, 4, block), (True, 4, block), (4, 4, block[:7]), (8193, 4, block)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                T.dxt1_rgb(data, width, height)

    def test_source_only_external_and_inline_packs_and_refusals(self):
        encoded = struct.pack("<HHI", 0xF800, 0, 0)
        expected_pixels = bytes([255, 0, 0]) * 16
        empty = {"offset": 0, "size": 0, "path": ""}
        source_stream = {"offset": 4, "size": 8, "path": "archive:/CAB-authored/CAB-authored.resS"}
        body, fields = authored_body("Source", 8, 10, b"", source_stream)
        target_stream = {"offset": 64, "size": 48, "path": "archive:/CAB-target/CAB-target.resS"}
        outputs = []
        expected_bodies = []
        for inline in (False, True):
            name = "Inline Ēta" if inline else "External"
            stream = empty if inline else target_stream
            expected_body, _ = authored_body(name, 48, 3, expected_pixels if inline else b"", stream)
            expected_bodies.append(expected_body)
            outputs.append(
                {
                    "bundle": "target.bundle",
                    "member": "CAB-target",
                    "path_id": 2 if inline else 1,
                    "bytes": len(expected_body),
                    "sha256": digest(expected_body),
                    "name": name,
                    "pixel_sha256": digest(expected_pixels),
                    "pixel_bytes": 48,
                    "inline": inline,
                    "stream": stream,
                    "alpha_optional": False,
                    "usage": 0,
                }
            )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            source = pc / "authored.bundle"
            source.write_bytes(FIXTURE.bundle([("CAB-authored", b"HEAD" + body, 4), ("CAB-authored.resS", b"LEAD" + encoded, 0)], True))
            source_hash = T.BUNDLE.sha(source)
            selected = {
                "path_id": 99,
                "offset": 4,
                "bytes": len(body),
                "sha256": digest(body),
                "fields": fields,
                "pixels": {"member": "CAB-authored.resS", "offset": 4, "bytes": 8, "sha256": digest(encoded)},
                "operation": "dxt1-rgb",
                "width": 4,
                "height": 4,
                "outputs": outputs,
            }
            profile = {
                "input_id": T.MESH.INPUT_ID,
                "bundles": [{"path": source.name, "sha256": source_hash, "members": [{"name": "CAB-authored", "textures": [selected]}]}],
            }
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(profile))
            result = T.produce(profile_path, T.BUNDLE.sha(profile_path), pc, root / "output")
            self.assertTrue(result["success"])
            self.assertEqual(result["objects"], 2)
            self.assertEqual((root / "output/objects.bin").read_bytes(), b"".join(expected_bodies))
            self.assertEqual((root / "output/resources.bin").read_bytes(), expected_pixels)
            index = [json.loads(line) for line in (root / "output/index.jsonl").read_text().splitlines()]
            self.assertEqual(index[0]["resource"]["stream"], target_stream)
            self.assertNotIn("resource", index[1])
            self.assertEqual(T.BUNDLE.sha(source), source_hash)
            with self.assertRaises(ValueError):
                T.produce(profile_path, T.BUNDLE.sha(profile_path), pc, root / "output")
            with self.assertRaisesRegex(ValueError, "profile drift"):
                T.produce(profile_path, "0" * 64, pc, root / "profile-drift")
            selected["operation"] = "dxt1-rgb-jpeg"
            profile_path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "codec required"):
                T.produce(profile_path, T.BUNDLE.sha(profile_path), pc, root / "missing-codec")
            with self.assertRaisesRegex(ValueError, "codec drift"):
                T.produce(profile_path, T.BUNDLE.sha(profile_path), pc, root / "codec-drift", source, "0" * 64)
            with self.assertRaisesRegex(ValueError, "overlap"):
                T.produce(profile_path, T.BUNDLE.sha(profile_path), pc, root / "game-as-codec", source, source_hash)
            self.assertFalse((root / "game-as-codec").exists())
            selected["operation"] = "dxt1-rgb"
            outputs[0]["pixel_sha256"] = "0" * 64
            profile_path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "pixels differ"):
                T.produce(profile_path, T.BUNDLE.sha(profile_path), pc, root / "pixel-drift")
            self.assertFalse(json.loads((root / "pixel-drift/result.json").read_text())["success"])
            source.write_bytes(b"authored drift")
            with self.assertRaisesRegex(ValueError, "bundle drift"):
                T.produce(profile_path, T.BUNDLE.sha(profile_path), pc, root / "input-drift")

    def test_field_and_inline_source_bounds(self):
        empty = {"offset": 0, "size": 0, "path": ""}
        body, fields = authored_body("Source", 3, 3, b"RGB", empty)
        target = {"name": "Target", "alpha_optional": False, "usage": 0, "inline": True, "stream": empty}
        expected, _ = authored_body("Target", 3, 3, b"RGB", empty)
        self.assertEqual(T.body_output(body, fields, b"RGB", target, "copy"), expected)
        for replacement in ([-1, 4], [len(body), 4], fields["m_Name"]):
            broken = dict(fields, m_TextureFormat=replacement)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                T.body_output(body, broken, b"RGB", target, "copy")
        with self.assertRaisesRegex(ValueError, "escape"):
            T.pixels_input(None, body, {"pixels": {"member": None, "offset": -1, "bytes": 1, "sha256": digest(b"L")}, "operation": "copy"})


if __name__ == "__main__":
    unittest.main()
