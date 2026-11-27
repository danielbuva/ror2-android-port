"""Source-discovered texture selectors using authored Unity bundle metadata."""

from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from test_phone_mesh_producer import array, bundle, node, serialized, text, vector


TOOL = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/texture_native_profile.py"


class TextureNativeProfileTests(unittest.TestCase):
    def test_discovers_inline_alpha8_partial_mips_and_checks_platform_blob(self):
        fields = (
            "m_TextureFormat",
            "m_Width",
            "m_Height",
            "m_MipCount",
            "m_ImageCount",
            "m_TextureDimension",
            "m_CompleteImageSize",
            "m_LightmapFormat",
        )
        schema = node(
            "Base",
            children=[
                text("m_Name"),
                *(node(name, 4) for name in fields),
                node("m_IsAlphaChannelOptional", 1, meta=0x4000),
                array("m_PlatformBlob", node("data", 1)),
                array("image data", node("data", 1), "TypelessData"),
                node("m_StreamData", children=[node("offset", 8), node("size", 4), text("path")]),
            ],
        )
        pixels = bytes(range(10))
        header = vector(b"Fixture", 7) + struct.pack("<8i", 1, 4, 2, 2, 1, 2, len(pixels), 0) + bytes(4)
        suffix = vector(pixels, len(pixels)) + bytes(16)
        clean = header + bytes(4) + suffix
        custom = header + vector(b"X", 1) + suffix

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            source = pc / "authored.bundle"
            source.write_bytes(
                bundle(
                    [("CAB-test", serialized(clean, schema, path_id=6, class_id=28), 4), ("CAB-blob", serialized(custom, schema, path_id=7, class_id=28), 4)]
                )
            )
            coverage = root / "coverage.jsonl"
            coverage.write_text(
                "".join(
                    json.dumps(dict(source=[source.name, member, identity], status="missing")) + "\n" for member, identity in (("CAB-test", 6), ("CAB-blob", 7))
                )
            )
            output = root / "profile.json"
            result = subprocess.run([sys.executable, "-B", str(TOOL), str(pc), str(coverage), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads(output.read_text())
            members = profile["bundles"][0]["members"]
            self.assertEqual([member["name"] for member in members], ["CAB-test"])
            record = members[0]["textures"][0]
            self.assertEqual((record["operation"], record["path_id"]), ("copy", 6))
            target = record["outputs"][0]
            self.assertEqual((target["sha256"], target["pixel_sha256"]), (sha256(clean).hexdigest(), sha256(pixels).hexdigest()))
