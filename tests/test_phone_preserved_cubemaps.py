"""Original HDR cubemap chain retention with authored, non-game records."""

import io
import struct
import unittest

from test_phone_texture_producer import T, authored_body, digest


EMPTY = {"offset": 0, "size": 0, "path": ""}


def cube_body(pixels, fmt=24, mips=3, stride=48):
    body, fields = authored_body("Source", stride, fmt, pixels, EMPTY)
    fields["m_MipCount"] = [len(body) - 4, 4]
    fields["m_ColorSpace"] = [len(body), 4]
    return body[:-4] + struct.pack("<ii", mips, 0) + b"TAIL", fields


class PreservedCubemapTests(unittest.TestCase):
    def test_all_original_faces_and_mips_survive_without_a_codec(self):
        # Poisoned lower mips deliberately differ from the top; this contract
        # must never regenerate them, convert their transfer, or reorder faces.
        pixels = b"".join(bytes([face * 3 + mip]) * 16 for face in range(6) for mip in range(3))
        body, fields = cube_body(pixels)
        start = fields["image data"][0] + 4
        selected = dict(
            width=4, height=4, fields=fields, operation="cube-preserve", pixels=dict(member=None, offset=start, bytes=len(pixels), sha256=digest(pixels))
        )
        self.assertEqual(T.pixels_input(None, body, selected), pixels)
        selected["pixels"].update(member="authored.resS", offset=7)

        class Bundle:
            def member(self, name):
                self_name = "authored.resS"
                if name != self_name:
                    raise AssertionError(name)
                return io.BytesIO(b"PREFIX!" + pixels)

        self.assertEqual(T.pixels_input(Bundle(), body, selected), pixels)
        selected["pixels"]["sha256"] = digest(b"different")
        with self.assertRaisesRegex(ValueError, "original texture pixels drift"):
            T.pixels_input(Bundle(), body, selected)

    def test_native_body_keeps_source_format_mips_colour_and_face_stride(self):
        pixels = bytes(range(48)) * 6
        body, fields = cube_body(pixels)
        target = dict(name="Owner", alpha_optional=False, usage=0, inline=True, stream=EMPTY, mips=3, colour_space=0)
        expected, _ = authored_body("Owner", 48, 24, pixels, EMPTY)
        expected = expected[:-4] + struct.pack("<ii", 3, 0) + b"TAIL"
        self.assertEqual(T.body_output(body, fields, pixels, target, "cube-preserve"), expected)
        for change in (dict(mips=2), dict(colour_space=1), dict(usage=2), dict(alpha_optional=True)):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "metadata differs from source"):
                T.body_output(body, fields, pixels, dict(target, **change), "cube-preserve")

    def test_half_float_chains_are_preserved_without_quantization(self):
        # Includes fractional and above-one half values, unlike RGBA8 storage.
        texel = struct.pack("<4e", 0.0003, 0.5, 12.75, 1)
        pixels = texel * (16 + 4 + 1) * 6
        body, fields = cube_body(pixels, fmt=17, stride=168)
        self.assertEqual(T.preserve_cube_mips(pixels, body, dict(width=4, height=4, fields=fields)), pixels)

    def test_source_chain_and_format_mismatch_are_rejected(self):
        for width, height, fmt, mips, stride, size in (
            (4, 4, 24, 3, 48, 287),
            (4, 4, 24, 3, 32, 192),
            (4, 4, 17, 3, 48, 288),
            (4, 4, 4, 3, 48, 288),
            (4, 2, 24, 3, 48, 288),
            (3, 3, 24, 3, 48, 288),
            (4, 4, 24, 4, 64, 384),
        ):
            pixels = bytes(size)
            body, fields = cube_body(pixels, fmt, mips, stride)
            with self.subTest(width=width, fmt=fmt, mips=mips, size=size), self.assertRaises(ValueError):
                T.preserve_cube_mips(pixels, body, dict(width=width, height=height, fields=fields))
