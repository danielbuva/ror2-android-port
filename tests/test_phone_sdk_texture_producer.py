"""Native public BC7 and authored SDK-pipe contracts, without game/Unity input."""

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_phone_texture_producer import FIXTURE, ROOT, T, authored_body, digest, load

SDK_FIXTURE = load("authored_sdk_fixture", ROOT / "tests/test_phone_sdk_codec.py").FIXTURE
BUILD = load("sdk_texture_builder", ROOT / "tools/phone-build/accepted-output/build_texture_sdk.py")


ALPHA_FIXTURE = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
    if(argc!=4 || strcmp(argv[3],"alpha8")) return 64;
    int w=atoi(argv[1]),h=atoi(argv[2]);
    if(w<4 || h<4 || w%4 || h%4 || w*h>4096) return 65;
    unsigned char data[4096],out[4096]={0};
    if(fread(data,1,w*h,stdin)!=(size_t)(w*h) || fgetc(stdin)!=EOF)return 67;
    int offset=0;
    for(int y=0;y<h;y+=4)for(int x=0;x<w;x+=4){
        for(int i=0;i<8;i++)out[offset+i]=data[(y+i/4)*w+x+i%4];
        offset+=16;
    }
    return fwrite(out,1,offset,stdout)==(size_t)offset?0:68;
}
"""


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
        cls.decoder, cls.codec, cls.library, cls.alpha = (cls.root / n for n in ("pixels", "codec", "fixture.so", "alpha"))
        source = ROOT / "tools/phone-build/accepted-output"
        fixture = cls.root / "fixture.c"
        fixture.write_text(SDK_FIXTURE)
        alpha = cls.root / "alpha.c"
        alpha.write_text(ALPHA_FIXTURE)
        for command in (
            [compiler, "-std=c11", str(alpha), "-o", str(cls.alpha)],
            [compiler, "-std=c11", "-O2", "-ffp-contract=off", str(source / "texture_pixels.c"), "-lm", "-o", str(cls.decoder)],
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

    def test_bc45_channel_bias_crop_and_refusal(self):
        selectors = sum((i % 8) << (3 * i) for i in range(16)).to_bytes(6, "little")
        blocks = (bytes((8, 0)) + selectors, bytes((0, 4)) + selectors)
        palettes = ((8, 0, 7, 5, 4, 3, 2, 1), (0, 4, 1, 1, 2, 3, 0, 255))
        for mode in ("bc4", "bc5"):
            block = b"".join(blocks[: 1 if mode == "bc4" else 2])
            for width, height in ((4, 4), (1, 3), (7, 5)):
                encoded = block * (((width + 3) // 4) * ((height + 3) // 4))
                expected = bytes(
                    value
                    for y in range(height)
                    for x in range(width)
                    for value in (palettes[0][(y % 4 * 4 + x % 4) % 8], palettes[1][(y % 4 * 4 + x % 4) % 8] if mode == "bc5" else 0, 0, 255)
                )
                result = subprocess.run([str(self.decoder), str(width), str(height), mode], input=encoded, capture_output=True, timeout=10)
                self.assertEqual((result.returncode, result.stdout), (0, expected))
            for encoded in (block[:-1], block + b"x"):
                result = subprocess.run([str(self.decoder), "4", "4", mode], input=encoded, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)

    def test_native_bc1_matches_qualified_integer_and_transparency_rules(self):
        for width, height in ((4, 4), (1, 3), (61, 47), (128, 128)):
            state, encoded = 631, bytearray()
            for block in range(((width + 3) // 4) * ((height + 3) // 4)):
                values = []
                for _ in range(3):
                    state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
                    values.append(state)
                first, second = (0, 65535) if block % 3 == 0 else (65535, 0) if block % 3 == 1 else (values[0] & 65535, values[1] & 65535)
                encoded.extend(struct.pack("<HHI", first, second, values[2]))
            expected = T.rgba_source(encoded, width, height, 10)
            result = subprocess.run([str(self.decoder), str(width), str(height), "bc1"], input=encoded, capture_output=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout), (0, expected))

    def test_complete_authored_mip_chains(self):
        # Exact-editor observations of authored images; no game or SDK input is needed.
        pins = {
            ("ramp", "linear"): "b4556dd446fb2fefb46fc7aad23123a3efdda5190be43f99f3543eb56bfbb139",
            ("ramp", "srgb"): "e2617c5d917d0e5b0fd5afdd57e31800abb69ef852d528cad7655cefe01c9d80",
            ("noise", "linear"): "a9dc7f7ce1361a7c2388036a5cb8b0dc3b9e51625b763e5bc99f8ba092eb7231",
            ("noise", "srgb"): "9d2be7a6915809d22e13ed27fab49a0816f327189642e9db3c2a8a6835b4bf9d",
        }
        for pattern in ("ramp", "noise"):
            width, height = (256, 4) if pattern == "ramp" else (1024, 1024)
            rgba = bytearray()
            state = 731
            for _y in range(height):
                for x in range(width):
                    if pattern == "ramp":
                        rgba.extend((x, x * 17 % 256, x * 73 % 256, 255))
                    else:
                        for _ in range(3):
                            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
                            rgba.append(state >> 24)
                        rgba.append(255)
            for mode in ("linear", "srgb"):
                result = subprocess.run([str(self.decoder), str(width), str(height), "mips-" + mode], input=rgba, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(hashlib.sha256(result.stdout).hexdigest(), pins[pattern, mode])
        for data in (bytes(63), bytes(65)):
            result = subprocess.run([str(self.decoder), "4", "4", "mips-linear"], input=data, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")

    def test_etc1_mips_tiles_small_levels_and_uses_destination_metric(self):
        rgb = bytes((0, 10, 20, 40, 50, 60, 80, 90, 100, 120, 130, 140))
        selected = {"outputs": [{"mips": 2, "colour_space": 0, "usage": 4}]}
        native = subprocess.run
        calls = []

        def run(command, **kwargs):
            if command[0] == str(self.decoder):
                return native(command, **kwargs)
            self.assertEqual(command, [str(self.alpha), "4", "4", "normal"])
            calls.append(kwargs["input"])
            return subprocess.CompletedProcess(command, 0, bytes([len(calls)]) * 8, b"")

        with patch.object(T.subprocess, "run", side_effect=run):
            result = T.etc1_mips(rgb, 2, 2, selected, {"pixels": str(self.decoder)}, self.alpha)
        self.assertEqual(result, bytes([1]) * 8 + bytes([2]) * 8)
        self.assertEqual(calls[0], b"".join(rgb[((y % 2) * 2 + x % 2) * 3 : ((y % 2) * 2 + x % 2 + 1) * 3] for y in range(4) for x in range(4)))
        self.assertEqual(calls[1], bytes((60, 70, 80)) * 16)
        selected["outputs"][0]["mips"] = 1
        with self.assertRaisesRegex(ValueError, "inconsistent full-chain"):
            T.etc1_mips(rgb, 2, 2, selected, {"pixels": str(self.decoder)}, self.alpha)

    def test_mip_body_projection_keeps_unselected_sentinels(self):
        stream = {"offset": 0, "size": 0, "path": ""}
        source, fields = authored_body("Source", 64, 4, bytes(64), stream)
        fields["m_MipCount"] = [len(source) - 4, 4]
        fields["m_ColorSpace"] = [len(source), 4]
        source = source[:-4] + struct.pack("<ii", 1, 0) + b"TAIL"
        pixels = bytes(range(24))
        target = {"name": "Owner", "alpha_optional": False, "usage": 4, "inline": True, "stream": stream, "mips": 3, "colour_space": 1}
        expected, _ = authored_body("Owner", 24, 34, pixels, stream, 4)
        expected = expected[:-4] + struct.pack("<ii", 3, 1) + b"TAIL"
        self.assertEqual(T.body_output(source, fields, pixels, target, "etc1-mips"), expected)

    def test_native_crunch_rejects_wrong_extents_and_malformed_streams(self):
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("a public C++ compiler is unavailable")
        stubs = self.root / "unused_etc_stubs.cpp"
        stubs.write_text(
            "#include <cstdlib>\n"
            "bool readCompressParams(){std::abort();}\n"
            "void setupAlphaTable(){std::abort();}\n"
            "void compressBlockAlphaFast(unsigned char*,int,int,int,int,unsigned char*){std::abort();}\n"
            "void compressBlockETC2FastPerceptual(unsigned char*,unsigned char*,int,int,int,int,unsigned int&,unsigned int&){std::abort();}\n"
            "double compressBlockDiffFlipFast(unsigned char*,unsigned char*,int,int,int,int,unsigned int&,unsigned int&){std::abort();}\n"
            "void compressBlockDiffFlipFastPerceptual(unsigned char*,unsigned char*,int,int,int,int,unsigned int&,unsigned int&){std::abort();}\n"
        )
        (self.root / "malloc.h").write_text(
            "#ifdef __APPLE__\n#include <malloc/malloc.h>\n#define malloc_usable_size malloc_size\n#else\n#include_next <malloc.h>\n#endif\n"
        )
        tool = self.root / "crunch"
        compilation = subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-O2",
                "-fno-strict-aliasing",
                "-I",
                str(self.root),
                str(ROOT / "tools/phone-build/accepted-output/texture_etc.cpp"),
                str(stubs),
                "-o",
                str(tool),
            ],
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(compilation.returncode, 0, compilation.stderr.decode(errors="replace"))
        for width, height, data in ((0, 4, b""), (4, 8193, b""), (4, 4, b""), (4, 4, b"Hx" + bytes(200)), (1, 3, bytes(range(73)))):
            for mode in ("uncrunch-bc1", "uncrunch-bc3"):
                result = subprocess.run([str(tool), str(width), str(height), mode], input=data, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

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
            self.assertEqual(T.pixels_input(None, body, selected, sdk=sdk, etc_codec=self.alpha), bytes([255]) * 8 + bytes([17, 31, 73, 255]) * 2)

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
            encoded_pixels = bytes([255]) * 8 + pixels[:8]
            target_body, _ = authored_body("Target", 16, 47, encoded_pixels, empty)
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
                        "pixel_sha256": digest(encoded_pixels),
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
            kwargs = {
                "sdk_toolchain": tools,
                "sdk_toolchain_sha256": T.BUNDLE.sha(tools),
                "etc_codec": self.alpha,
                "etc_codec_sha256": T.BUNDLE.sha(self.alpha),
            }
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
            expected = b"".join(bytes([255]) * 8 + bytes([marker, 31, 73, 255]) * 2 for marker in (17, 29, 73, 99))
            self.assertEqual(T.sdk_encode_rgba(rgba, 4, 16, value, self.alpha), expected)
            with self.assertRaisesRegex(ValueError, "codec failed"):
                T.sdk_encode_rgba(rgba[:64] + bytes([42]) + rgba[65:], 4, 16, value, self.alpha)
            with self.assertRaisesRegex(ValueError, "codec failed"):
                T.sdk_encode_rgba(rgba[:-1], 4, 16, value, self.alpha)

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
