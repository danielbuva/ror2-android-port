"""Authored by-value ABI and bounded pipe controls; no Unity/game library."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/sdk_texture_codec.c"
FIXTURE = """
#include <stddef.h>
#include <string.h>
struct Image {void *pixels; int type,width,height,stride;};
static int initialized;
void libetc_init(void) {initialized=1;}
int libetc_compress(struct Image image,int backend,int format,int quality,int space,void *out,size_t *size) {
    if (!initialized || image.type || image.width!=4 || image.height!=4 || image.stride!=16 ||
        backend!=1 || format!=2 || quality!=1 || space || *size!=16) return 0;
    memcpy(out,image.pixels,16);
    if (((unsigned char*)image.pixels)[0]==42) --*size;
    return 1;
}
"""


class SdkCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("cc")
        if compiler is None:
            raise unittest.SkipTest("a public host C compiler is unavailable")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        root = Path(cls.temporary.name)
        fixture = root / "fixture.c"
        fixture.write_text(FIXTURE)
        cls.library = root / "fixture.so"
        cls.binary = root / "codec"
        subprocess.run(
            [compiler, "-dynamiclib" if sys.platform == "darwin" else "-shared", "-fPIC", str(fixture), "-o", str(cls.library)], check=True, capture_output=True
        )
        subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", str(SOURCE), "-ldl", "-o", str(cls.binary)], check=True, capture_output=True)

    def invoke(self, data, dimensions=("4", "4")):
        return subprocess.run([str(self.binary), str(self.library), *dimensions, "2", "0"], input=data, capture_output=True, timeout=10)

    def test_by_value_descriptor_and_exact_pipe(self):
        pixels = bytes(range(64))
        result = self.invoke(pixels)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, pixels[:16])

    def test_input_and_output_extents_refuse_without_bytes(self):
        for pixels in (bytes(63), bytes(65), bytes([42]) + bytes(63)):
            with self.subTest(length=len(pixels), marker=pixels[0]):
                result = self.invoke(pixels)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
        result = self.invoke(b"", ("8193", "4"))
        self.assertEqual(result.returncode, 65)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
