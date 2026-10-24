"""Native public BC7 and authored SDK-pipe contracts, without game/Unity input."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_phone_texture_producer import FIXTURE, ROOT, T, authored_body, digest, load

SDK_FIXTURE = load("authored_sdk_fixture", ROOT / "tests/test_phone_sdk_codec.py").FIXTURE
BUILD = load("sdk_texture_builder", ROOT / "tools/phone-build/accepted-output/build_texture_sdk.py")


def mode6(colour):
    """Author a constant BC7 mode-6 block with identical odd-valued endpoints."""
    value, shift = 1 << 6, 7
    for channel in colour:
        for _ in range(2):
            value |= (channel >> 1) << shift
            shift += 7
    value |= 3 << shift  # One shared low bit per endpoint; all four channels odd.
    return value.to_bytes(16, "little")


class SdkTextureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("cc")
        if compiler is None:
            raise unittest.SkipTest("a public host C compiler is unavailable")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.decoder, cls.codec, cls.library = (cls.root / n for n in ("pixels", "codec", "fixture.so"))
        source = ROOT / "tools/phone-build/accepted-output"
        fixture = cls.root / "fixture.c"
        fixture.write_text(SDK_FIXTURE)
        for command in (
            [compiler, "-std=c11", "-O2", str(source / "texture_pixels.c"), "-o", str(cls.decoder)],
            [compiler, "-std=c11", str(source / "sdk_texture_codec.c"), "-ldl", "-o", str(cls.codec)],
            [compiler, "-dynamiclib" if sys.platform == "darwin" else "-shared", "-fPIC", str(fixture), "-o", str(cls.library)],
        ):
            subprocess.run(command, check=True, capture_output=True, timeout=30)

    def tools(self, path):
        value = {
            "command": [str(self.codec), str(self.library)],
            "environment": {},
            "pixels": str(self.decoder),
            "inputs": {str(p): T.BUNDLE.sha(p) for p in (self.codec, self.library, self.decoder)},
        }
        path.write_text(json.dumps(value))
        return value

    def test_bc7_authored_blocks_crop_and_extents(self):
        colours = ((17, 31, 73, 255), (255, 255, 255, 255))
        for colour in colours:
            for width, height in ((4, 4), (1, 3), (8, 4)):
                data = mode6(colour) * ((width + 3) // 4)
                result = subprocess.run([str(self.decoder), str(width), str(height)], input=data, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, bytes(colour) * width * height)
        for data in (b"", mode6(colours[0])[:-1], mode6(colours[0]) + b"x"):
            result = subprocess.run([str(self.decoder), "4", "4"], input=data, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)

    def test_native_bc3_matches_byte_palette_alpha_and_cropping(self):
        import struct

        for first, second in ((231, 17), (17, 231), (73, 73)):
            selectors = sum((i % 8) << (3 * i) for i in range(16))
            colours = sum((i % 4) << (2 * i) for i in range(16))
            block = bytes((first, second)) + selectors.to_bytes(6, "little") + struct.pack("<HHI", 0x1083, 0xE7DA, colours)
            for width, height in ((4, 4), (1, 3), (7, 5)):
                data = block * (((width + 3) // 4) * ((height + 3) // 4))
                result = subprocess.run([str(self.decoder), str(width), str(height), "bc3"], input=data, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, T.rgba_source(data, width, height, 12))
        for data in (block[:-1], block + b"x"):
            result = subprocess.run([str(self.decoder), "4", "4", "bc3"], input=data, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)

    def test_native_dilation_matches_seed_coordinates_and_ties(self):
        for width, height in ((1, 1), (7, 5), (37, 19)):
            for empty in (False, True):
                rgba = bytearray()
                for index in range(width * height):
                    rgba.extend((index * 17 % 256, index * 31 % 256, index * 73 % 256, 0 if empty or index % 11 else 255))
                result = subprocess.run([str(self.decoder), str(width), str(height), "dilate"], input=bytes(rgba), capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, T.dilate_rgba(bytes(rgba), width, height))
        result = subprocess.run([str(self.decoder), "4", "4", "dilate"], input=bytes(63), capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_bc7_to_sdk_rgba_pipe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "sdk.json"
            self.tools(tools)
            encoded = mode6((17, 31, 73, 255))
            body, fields = authored_body("Original", 16, 25, encoded, {"offset": 0, "size": 0, "path": ""})
            start, _ = fields["image data"]
            selected = {
                "pixels": {"member": None, "offset": start + 4, "bytes": 16, "sha256": digest(encoded)},
                "operation": "sdk-rgba",
                "width": 4,
                "height": 4,
                "fields": fields,
            }
            sdk = T.sdk_inputs(tools, T.BUNDLE.sha(tools), root)
            self.assertEqual(T.pixels_input(None, body, selected, sdk=sdk), bytes([17, 31, 73, 255]) * 4)

    def test_source_to_sdk_pack_and_dependency_drift_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            tools = root / "sdk.json"
            self.tools(tools)
            pixels = bytes([17, 31, 73, 255]) * 16
            empty = {"offset": 0, "size": 0, "path": ""}
            body, spans = authored_body("Original", len(pixels), 4, pixels, empty)
            target_body, _ = authored_body("Target", 16, 47, pixels[:16], empty)
            source = pc / "authored.bundle"
            source.write_bytes(FIXTURE.bundle([("CAB-authored", body, 4)], True))
            start, _ = spans["image data"]
            selected = {
                "path_id": 99,
                "offset": 0,
                "bytes": len(body),
                "sha256": digest(body),
                "fields": spans,
                "pixels": {"member": None, "offset": start + 4, "bytes": len(pixels), "sha256": digest(pixels)},
                "operation": "sdk-rgba",
                "width": 4,
                "height": 4,
                "outputs": [
                    {
                        "bundle": "authored-target",
                        "member": "CAB-target",
                        "path_id": 100,
                        "bytes": len(target_body),
                        "sha256": digest(target_body),
                        "name": "Target",
                        "pixel_sha256": digest(pixels[:16]),
                        "pixel_bytes": 16,
                        "inline": True,
                        "stream": empty,
                        "alpha_optional": False,
                        "usage": 0,
                    }
                ],
            }
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "input_id": T.MESH.INPUT_ID,
                        "bundles": [{"path": source.name, "sha256": T.BUNDLE.sha(source), "members": [{"name": "CAB-authored", "textures": [selected]}]}],
                    }
                )
            )
            kwargs = {"sdk_toolchain": tools, "sdk_toolchain_sha256": T.BUNDLE.sha(tools)}
            result = T.produce(profile, T.BUNDLE.sha(profile), pc, root / "output", **kwargs)
            self.assertTrue(result["success"])
            self.assertEqual((root / "output/objects.bin").read_bytes(), target_body)
            with self.assertRaisesRegex(ValueError, "must be new"):
                T.produce(profile, T.BUNDLE.sha(profile), pc, root / "output", **kwargs)
            value = json.loads(tools.read_text())
            value["inputs"][str(self.library)] = "0" * 64
            tools.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "tool input drift"):
                T.produce(profile, T.BUNDLE.sha(profile), pc, root / "drift", sdk_toolchain=tools, sdk_toolchain_sha256=T.BUNDLE.sha(tools))
            self.assertFalse((root / "drift").exists())

    def test_sdk_bands_keep_raster_order_and_refuse_a_bad_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            tools = Path(temporary) / "sdk.json"
            value = self.tools(tools)
            rgba = b"".join(bytes([marker, 31, 73, 255]) * 16 for marker in (17, 29, 73, 99))
            expected = b"".join(bytes([marker, 31, 73, 255]) * 4 for marker in (17, 29, 73, 99))
            self.assertEqual(T.sdk_encode_rgba(rgba, 4, 16, value), expected)
            with self.assertRaisesRegex(ValueError, "codec failed"):
                T.sdk_encode_rgba(rgba[:64] + bytes([42]) + rgba[65:], 4, 16, value)
            with self.assertRaisesRegex(ValueError, "codec failed"):
                T.sdk_encode_rgba(rgba[:-1], 4, 16, value)

    def test_unqualified_sdk_provider_refuses_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provider = root / "authored"
            provider.write_bytes(b"not an SDK provider")
            with self.assertRaisesRegex(ValueError, "SDK codec provider"):
                BUILD.build(provider, None, provider, root / "output")
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
