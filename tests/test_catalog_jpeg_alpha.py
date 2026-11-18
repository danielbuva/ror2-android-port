import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from catalog_jpeg_alpha import DXT5_NORMAL, lossless_pixels, texture_importer


class CatalogJpegAlphaTests(unittest.TestCase):
    def test_preserves_all_channels_and_skips_opaque_sources(self):
        image = Image.new("RGBA", (2, 1))
        image.putdata([(40, 50, 60, 0), (200, 100, 3, 255)])
        self.assertEqual(lossless_pixels(image, 0).tobytes(), image.tobytes())
        self.assertIsNone(lossless_pixels(Image.new("RGBA", (1, 1), (1, 2, 3, 255)), 0))

    def test_decodes_normal_x_from_source_alpha(self):
        image = Image.new("RGBA", (1, 1), (212, 127, 0, 51))
        restored = lossless_pixels(image, DXT5_NORMAL)
        self.assertEqual(restored.getpixel((0, 0)), (51, 127, 229, 212))

    def test_keeps_importer_identity_and_normal_settings(self):
        default = (
            "  - serializedVersion: 3\n"
            "    buildTarget: DefaultTexturePlatform\n"
            "    maxTextureSize: 2048\n"
            "    textureFormat: -1\n"
            "    textureCompression: 2\n"
            "    crunchedCompression: 1\n"
            "    allowsAlphaSplitting: 1\n"
            "    overridden: 0\n"
        )
        metadata = (
            "guid: 0123456789abcdef0123456789abcdef\nTextureImporter:\n"
            "  textureType: 0\n  alphaUsage: 0\n  alphaIsTransparency: 1\n"
            "  platformSettings:\n" + default + "  spriteSheet:\n"
        )
        android = (
            "  - serializedVersion: 3\n"
            "    buildTarget: Android\n"
            "    maxTextureSize: 2048\n"
            "    textureFormat: 4\n"
            "    textureCompression: 0\n"
            "    crunchedCompression: 0\n"
            "    allowsAlphaSplitting: 0\n"
            "    overridden: 1\n"
        )
        expected = metadata.replace("alphaUsage: 0", "alphaUsage: 1").replace("alphaIsTransparency: 1", "alphaIsTransparency: 0")
        expected = expected.replace(default, default + android)
        self.assertEqual(texture_importer(metadata, False), expected)
        self.assertEqual(texture_importer(expected, False), expected)
        normal = metadata.replace("textureType: 0", "textureType: 1")
        self.assertEqual(texture_importer(normal, True), normal)
