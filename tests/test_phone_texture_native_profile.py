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


def texture_schema():
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
    return node(
        "Base",
        children=[
            text("m_Name"),
            *(node(name, 4) for name in fields),
            node("m_IsAlphaChannelOptional", 1, meta=0x4000),
            node("m_ColorSpace", 4),
            array("m_PlatformBlob", node("data", 1)),
            array("image data", node("data", 1), "TypelessData"),
            node("m_StreamData", children=[node("offset", 8), node("size", 4), text("path")]),
        ],
    )


class TextureNativeProfileTests(unittest.TestCase):
    def test_produces_standalone_textures_with_pinned_schema_and_resource(self):
        schema = texture_schema()
        pixels = bytes(range(16))
        argb = vector(b"ARGB", 4) + struct.pack("<8i", 5, 2, 2, 1, 1, 2, len(pixels), 6) + bytes(16)
        argb += struct.pack("<QI", 3, len(pixels)) + vector(b"sharedassets0.assets.resS", 25)
        empty = vector(b"Empty", 5) + struct.pack("<8i", 1, 0, 0, 1, 1, 2, 0, 0) + bytes(32)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            resource = pc / "sharedassets0.assets.resS"
            resource.write_bytes(b"pad" + pixels)
            (pc / "sharedassets0.assets").write_bytes(serialized(argb, schema, path_id=6, class_id=28, trees=False))
            (pc / "level0").write_bytes(serialized(empty, schema, path_id=7, class_id=28, trees=False))
            source = pc / "authored.bundle"
            source.write_bytes(bundle([("CAB-test", serialized(argb, schema, path_id=6, class_id=28), 4)]))
            coverage = root / "coverage.jsonl"
            coverage.write_text(
                "".join(
                    json.dumps(dict(source=[name, name, identity], status="missing")) + "\n" for name, identity in (("sharedassets0.assets", 6), ("level0", 7))
                )
            )
            witnesses = root / "witnesses.json"
            witnesses.write_text(json.dumps([dict(source=[source.name, "CAB-test", 6], class_id=28, sha256=sha256(source.read_bytes()).hexdigest())]))
            profile_path = root / "profile.json"
            subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(TOOL), str(pc), str(coverage), "--schema-witnesses", str(witnesses), "--output", str(profile_path)],
                check=True,
            )
            profile = json.loads(profile_path.read_bytes())
            self.assertEqual([item["resources"] for item in profile["bundles"]], [{}, {resource.name: sha256(resource.read_bytes()).hexdigest()}])
            command = [
                sys.executable,
                "-B",
                str(TOOL.with_name("texture_produce.py")),
                "--pc",
                str(pc),
                "--profile",
                str(profile_path),
                "--profile-sha256",
                sha256(profile_path.read_bytes()).hexdigest(),
            ]
            pack = root / "pack"
            subprocess.run([*command, "--output", str(pack)], check=True)
            self.assertEqual((pack / "objects.bin").read_bytes(), empty + argb)
            self.assertEqual((pack / "resources.bin").read_bytes(), pixels)
            self.assertTrue(json.loads((pack / "types.json").read_bytes())[0]["tree"])
            resource.write_bytes(b"bad" + pixels)
            result = subprocess.run([*command, "--output", str(root / "resource-drift")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("standalone texture resource drift", result.stderr)
            with source.open("ab") as stream:
                stream.write(b"drift")
            result = subprocess.run([*command, "--output", str(root / "schema-drift")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("standalone texture schema witness drift", result.stderr)

    def test_discovers_original_mips_and_checks_platform_blob(self):
        schema = texture_schema()
        pixels = bytes(range(10))
        header = vector(b"Fixture", 7) + struct.pack("<8i", 1, 4, 2, 2, 1, 2, len(pixels), 0) + bytes(8)
        suffix = vector(pixels, len(pixels)) + bytes(16)
        clean = header + bytes(4) + suffix
        custom = header + vector(b"X", 1) + suffix
        bc3_pixels = bytes(range(32))
        normal = vector(b"Normal", 6) + struct.pack("<8i", 12, 4, 2, 2, 1, 2, len(bc3_pixels), 3) + bytes(12)
        normal += vector(bc3_pixels, len(bc3_pixels)) + bytes(16)
        native_colours = {}
        for fmt, channels in ((3, 3), (4, 4)):
            source_pixels = bytes(range(10 * channels))
            native_header = vector(b"Native", 6) + struct.pack("<8i", fmt, 4, 2, 2, 1, 2, len(source_pixels), 6) + bytes(12)
            native_colours[fmt] = (native_header + vector(source_pixels, len(source_pixels)) + bytes(16), source_pixels)
        bc1_pixels = struct.pack("<HHI", 0x07E0, 0, 0) * 2
        colour = vector(b"Colour", 6) + struct.pack("<8i", 10, 4, 2, 2, 1, 2, len(bc1_pixels), 6) + struct.pack("<3i", 1, 0, 0)
        colour += vector(bc1_pixels, len(bc1_pixels)) + bytes(16)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            source = pc / "authored.bundle"
            source.write_bytes(
                bundle(
                    [
                        ("CAB-test", serialized(clean, schema, path_id=6, class_id=28), 4),
                        ("CAB-blob", serialized(custom, schema, path_id=7, class_id=28), 4),
                        ("CAB-normal", serialized(normal, schema, path_id=8, class_id=28), 4),
                        ("CAB-normal-covered", serialized(normal, schema, path_id=8, class_id=28), 4),
                        ("CAB-colour", serialized(colour, schema, path_id=9, class_id=28), 4),
                        *((f"CAB-native-{fmt}", serialized(body, schema, path_id=fmt, class_id=28), 4) for fmt, (body, _) in native_colours.items()),
                    ]
                )
            )
            coverage = root / "coverage.jsonl"
            coverage.write_text(
                "".join(
                    json.dumps(dict(source=[source.name, member, identity], status="missing")) + "\n"
                    for member, identity in (
                        ("CAB-test", 6),
                        ("CAB-blob", 7),
                        ("CAB-normal", 8),
                        ("CAB-colour", 9),
                        ("CAB-native-3", 3),
                        ("CAB-native-4", 4),
                    )
                )
                + json.dumps(dict(source=[source.name, "CAB-normal-covered", 8], status="exact", record_source=["ignored.bundle", "CAB-other", 8]))
                + "\n"
            )
            output = root / "profile.json"
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(TOOL), str(pc), str(coverage), "--output", str(output)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads(output.read_text())
            members = profile["bundles"][0]["members"]
            self.assertEqual([member["name"] for member in members], ["CAB-native-3", "CAB-native-4", "CAB-test"])
            for member in members[:2]:
                record = member["textures"][0]
                body, source_pixels = native_colours[record["path_id"]]
                self.assertEqual(record["operation"], "copy")
                target = record["outputs"][0]
                self.assertEqual((target["sha256"], target["pixel_sha256"]), (sha256(body).hexdigest(), sha256(source_pixels).hexdigest()))
            record = members[2]["textures"][0]
            self.assertEqual((record["operation"], record["path_id"]), ("copy", 6))
            target = record["outputs"][0]
            self.assertEqual((target["sha256"], target["pixel_sha256"]), (sha256(clean).hexdigest(), sha256(pixels).hexdigest()))
            output = root / "bc3.json"
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(TOOL), str(pc), str(coverage), "--source-bc3", "--output", str(output)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            members = json.loads(output.read_text())["bundles"][0]["members"]
            self.assertEqual([member["name"] for member in members], ["CAB-normal"])
            record = members[0]["textures"][0]
            self.assertEqual((record["operation"], record["path_id"]), ("source-bc3-etc", 8))
            self.assertEqual(record["pixels"]["sha256"], sha256(bc3_pixels).hexdigest())
            target = record["outputs"][0]
            self.assertEqual((target["sha256"], target["pixel_sha256"]), (None, None))
            self.assertEqual((target["bytes"], target["pixel_bytes"], target["usage"], target["alpha_optional"]), (len(normal) - 16, 16, 4, True))
            output = root / "all-bc3.json"
            subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(TOOL), str(pc), str(coverage), "--source-bc3", "--all-originals", "--output", str(output)],
                check=True,
            )
            originals = json.loads(output.read_text())["bundles"][0]["members"]
            self.assertEqual([member["name"] for member in originals], ["CAB-normal", "CAB-normal-covered"])
            self.assertEqual(originals[0], members[0])
            self.assertEqual(originals[1]["textures"][0]["sha256"], record["sha256"])
            output = root / "bc1.json"
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(TOOL), str(pc), str(coverage), "--source-bc1", "--output", str(output)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            members = json.loads(output.read_text())["bundles"][0]["members"]
            self.assertEqual([member["name"] for member in members], ["CAB-colour"])
            record = members[0]["textures"][0]
            self.assertEqual((record["operation"], record["path_id"]), ("source-bc1-etc", 9))
            self.assertEqual(record["pixels"]["sha256"], sha256(bc1_pixels).hexdigest())
            target = record["outputs"][0]
            self.assertEqual((target["bytes"], target["pixel_bytes"], target["usage"], target["alpha_optional"]), (len(colour), 16, 6, True))
