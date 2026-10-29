"""Authored geometry contracts; no original game, SDK or downloaded source needed."""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("obj_mesh_test", ROOT / "tools/phone-build/accepted-output/obj_mesh.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def plane():
    return b"".join(struct.pack("<12f", x, y, 0, 0, 0, 1, 0, 1, 0, 1, x, y) for x, y in ((0, 0), (1, 0), (0, 1)))


class PlaneNative:
    def tangents(self, vertices, indices):
        self.vertices, self.indices = vertices, indices
        return struct.pack("<4f", 1, 0, 0, 1) * len(indices)

    def sort(self, values):
        return list(values)  # One authored triangle; no sorting ambiguity.


class ObjMeshTests(unittest.TestCase):
    def test_robust_normalization_scales_before_squaring_and_keeps_sign(self):
        self.assertEqual([M.f(0.6), M.f(0.8), 0.0], M.robust([3.0, 4.0, 0.0]))
        self.assertEqual([-1.0, 0.0, 0.0], M.robust([-1e30, 0.0, 0.0]))
        self.assertEqual([0.0, 1.0, 0.0], M.robust([1e-6, -1e-6, 0.0]))

    def test_import_retains_source_attributes_and_generates_corner_first_use_order(self):
        source = plane()
        native = PlaneNative()
        result, indices, metric = M.convert(source, struct.pack("<3H", 0, 1, 2), native)
        self.assertEqual(source, native.vertices)
        self.assertEqual([2, 0, 1], native.indices)
        self.assertEqual((0, 1, 2), struct.unpack("<3H", indices))
        self.assertEqual(1.0, metric)
        for at, original in enumerate((2, 0, 1)):
            vertex = result[at * 48 : (at + 1) * 48]
            self.assertEqual(source[original * 48 : original * 48 + 24], vertex[:24])
            self.assertEqual(source[original * 48 + 40 : (original + 1) * 48], vertex[40:])
            self.assertEqual((1.0, 0.0, 0.0, 1.0), struct.unpack("<4f", vertex[24:40]))

    def test_uv_area_threshold_excludes_degenerate_uvs(self):
        rows = [list(struct.unpack_from("<12f", plane(), k)) for k in (0, 48, 96)]
        for vertex in rows:
            vertex[10:12] = [0.0, 0.0]
        value, stats = M.metric(rows, [0, 1, 2], lambda values: list(values))
        self.assertEqual(1.0, value)
        self.assertEqual(1, stats["filtered"]["uv"])

    def test_native_helper_drift_is_detected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program = root / "mesh-obj"
            program.write_bytes(b"authored helper placeholder")
            expected = {"source_sha256": M.sha(ROOT / "tools/phone-build/accepted-output/mesh_obj.c"), "providers": {"public.c": "authored"}}
            (root / "result.json").write_text(json.dumps({"success": True, **expected, "output_sha256": hashlib.sha256(program.read_bytes()).hexdigest()}))
            native = M.Native(root, expected)
            program.write_bytes(b"changed helper")
            with self.assertRaisesRegex(ValueError, "changed"):
                native.run("tangents", b"", 0)


if __name__ == "__main__":
    unittest.main()
