"""Synthetic full-scene lighting qualification and readiness admission."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


C = load("lighting_compare_test", "tools/phone-build/accepted-output/scene_compare.py")
OWNER = load("lighting_readiness_test", "tools/phone-build/owner-apk/build_owner_apk.py")


def tree(nodes):
    strings = bytearray()
    raw = bytearray()

    def label(text):
        start = len(strings)
        strings.extend(text.encode() + b"\0")
        return start

    for level, kind, name, size, flags in nodes:
        raw.extend(struct.pack("<HBBIIiiiQ", 1, level, flags, label(kind), label(name), size, 0, 0, 0))
    return struct.pack("<II", len(nodes), len(strings)) + raw + strings


AMBIENT = tree(
    [
        (0, "RenderSettings", "Base", -1, 0),
        (1, "float", "m_Exposure", 4, 0),
        (1, "SH", "m_AmbientProbe", 108, 0),
        (1, "PPtr<Cubemap>", "m_CustomReflection", 12, 0),
        (1, "int", "m_Exact", 4, 0),
    ]
)
TEXTURE = tree(
    [
        (0, "Cubemap", "Base", -1, 0),
        (1, "int", "m_TextureFormat", 4, 0),
        (1, "TypelessData", "image data", -1, 0),
        (2, "Array", "Array", -1, 1),
        (3, "int", "size", 4, 0),
        (3, "UInt8", "data", 1, 0),
    ]
)
LIGHTMAP = tree(
    [
        (0, "LightmapSettings", "Base", -1, 0),
        (1, "vector", "m_Lightmaps", -1, 0),
        (2, "Array", "Array", -1, 1),
        (3, "int", "size", 4, 0),
        (3, "PPtr<Texture2D>", "data", 12, 0),
    ]
)


def serialized(records):
    types, objects, bodies = [], [], {}
    offset = 0
    for pid, cid, schema, body in records:
        types.append(dict(class_id=cid, stripped=0, script_type=-1, hash=bytes([cid % 256]) * 16, tree=schema, dependencies=[]))
        objects.append(dict(path_id=pid, offset=offset, bytes=len(body), type_id=len(types) - 1))
        bodies[pid] = body
        offset = (offset + len(body) + 7) // 8 * 8
    layout = dict(engine="2021.3.45f2", platform=13, trees=True, types=types, objects=objects, scripts=[], externals=[], ref_types=[], user="")
    output = io.BytesIO()
    C.W.write_serialized(output, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    return output.getvalue()


def ambient(delta=0, cid=104, exposure=1.0, pointer=2):
    body = struct.pack("<28fiqi", exposure, *([1.0 + delta] + [1.0] * 26), 0, pointer, 7)
    return serialized([(1, cid, AMBIENT, body)])


def rule(bound=0.125):
    return dict(
        path_id=1,
        class_id=104,
        samples=[
            dict(
                field=["m_AmbientProbe"], channels=27, max_abs=[bound] + [0] * 26, measurement="Synthetic per-channel maximum from authored reference/candidate"
            )
        ],
    )


class LightingToleranceTests(unittest.TestCase):
    def compare(self, old, new, rules=None):
        return C.compare_member(C.member(old), C.member(new), [rule()] if rules is None else rules)

    def test_boundary_is_separate_from_exact_and_over_bound_refuses(self):
        self.assertEqual(self.compare(ambient(), ambient())["status"], "raw-exact")
        result = self.compare(ambient(), ambient(0.125))
        self.assertEqual(result["status"], "tolerance-accepted")
        self.assertEqual(result["records"][0]["measured"][0]["max_abs"], [0.125] + [0] * 26)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.compare(ambient(), ambient(0.25))

    def test_nonlighting_fields_pointers_metadata_and_unselected_bytes_refuse(self):
        for candidate in (ambient(0.125, exposure=2), ambient(0.125, pointer=3), ambient(0.125, cid=105), ambient(0.125)[:60] + b"X" + ambient(0.125)[61:]):
            with self.subTest(digest=hashlib.sha256(candidate).hexdigest()), self.assertRaises((ValueError, UnicodeError)):
                self.compare(ambient(), candidate)
        with self.assertRaisesRegex(ValueError, "non-lighting member"):
            self.compare(ambient(), ambient(0.125), [])

    def test_class_and_field_scope_nonfinite_and_missing_bounds_refuse(self):
        for change in ("class", "field", "nan", "negative", "missing"):
            selected = rule()
            if change == "class":
                selected["class_id"] = 105
            elif change == "field":
                selected["samples"][0]["field"] = ["m_Exposure"]
            elif change == "nan":
                selected["samples"][0]["max_abs"][0] = float("nan")
            elif change == "negative":
                selected["samples"][0]["max_abs"][0] = -1
            else:
                selected["samples"] = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.compare(ambient(), ambient(0.125), [selected])
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            self.compare(ambient(), ambient(float("nan")))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.compare(ambient(), ambient(0.125), [rule(), rule()])

    def test_only_bound_reflections_and_lightmaps_allow_texel_differences(self):
        for cid, owner_id, owner_class, owner_tree, owner_body in (
            (89, "reflection_owner", 104, AMBIENT, struct.pack("<28fiqi", *([1.0] * 28), 0, 2, 7)),
            (28, "lightmap_owner", 157, LIGHTMAP, struct.pack("<Iiq", 1, 0, 2)),
        ):

            def data(delta):
                texels = struct.pack("<4e", 1.0 + delta, 1, 1, 1)
                return serialized([(1, owner_class, owner_tree, owner_body), (2, cid, TEXTURE, struct.pack("<iI", 17, len(texels)) + texels)])

            selected = dict(
                path_id=2,
                class_id=cid,
                samples=[dict(field=["image data", "Array", "payload"], channels=4, max_abs=[0.125, 0, 0, 0], measurement="Synthetic texel envelope")],
                **{owner_id: 1},
            )
            self.assertEqual(self.compare(data(0), data(0.125), [selected])["status"], "tolerance-accepted")
            selected[owner_id] = 2
            with self.assertRaisesRegex(ValueError, "binding"):
                self.compare(data(0), data(0.125), [selected])

    def test_lightprobe_coefficients_use_complete_native_arrays(self):
        schema = tree(
            [
                (0, "LightProbes", "Base", -1, 0),
                (1, "vector", "m_BakedCoefficients", -1, 0),
                (2, "Array", "Array", -1, 1),
                (3, "int", "size", 4, 0),
                (3, "SH", "data", 108, 0),
            ]
        )
        before = serialized([(1, 258, schema, struct.pack("<I54f", 2, *([1.0] * 54)))])
        after = serialized([(1, 258, schema, struct.pack("<I54f", 2, *([1.125] + [1.0] * 53)))])
        selected = rule()
        selected["class_id"] = 258
        selected["samples"][0]["field"] = ["m_BakedCoefficients", "Array", "payload"]
        self.assertEqual(self.compare(before, after, [selected])["status"], "tolerance-accepted")

    def test_readiness_requires_pinned_visual_review_and_counts_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "payload/scene"
            target.parent.mkdir()
            target.write_bytes(ambient(0.125))
            reference = root / "reference"
            reference.write_bytes(ambient())
            baseline = C.B.sha(reference)

            def pin(name, value):
                path = root / name
                path.write_text(json.dumps(value))
                return dict(path=str(path), sha256=C.B.sha(path))

            recipe = dict(reference_sha256=baseline, members={"": [rule()]})
            visual = dict(
                reference_sha256=baseline, candidate_sha256=C.B.sha(target), parity=True, review="Synthetic visual-review contract; no game parity claim"
            )
            selection = dict(reference=str(reference), recipe=pin("recipe.json", recipe), visual=pin("visual.json", visual))
            request = dict(manifest="unused", manifest_sha256=OWNER.PROFILE, targets=str(root), lighting_tolerance={"payload/scene": selection})
            targets = [dict(path="payload/scene", bytes=reference.stat().st_size, sha256=baseline), dict(path="payload/other", bytes=3, sha256="0" * 64)]
            with patch.object(OWNER.PACKET, "profile", return_value=(b"", dict(targets=targets))):
                report = OWNER.check(request)
                self.assertEqual(report["tolerance_accepted_count"], 1)
                self.assertEqual(report["exact_count"], 0)
                self.assertEqual(report["drift_explained_count"], 0)
                self.assertEqual(report["blocked_entries"], ["payload/other"])
                self.assertFalse(report["device_qualified"])
                visual["parity"] = False
                selection["visual"] = pin("visual.json", visual)
                self.assertEqual(OWNER.check(request)["tolerance_accepted_count"], 0)
                visual["parity"] = True
                visual["candidate_sha256"] = "0" * 64
                selection["visual"] = pin("visual.json", visual)
                self.assertEqual(OWNER.check(request)["entries"][0]["status"], "invalid")
                selection["recipe"]["sha256"] = "0" * 64
                self.assertEqual(OWNER.check(request)["entries"][0]["status"], "invalid")

    def test_bundle_checks_all_members_and_numerical_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def bundle(path, data, resource=b"exact resource"):
                entries = [("CAB-authored", 4, len(data), lambda: io.BytesIO(data)), ("CAB-authored.resS", 0, len(resource), lambda: io.BytesIO(resource))]
                with path.open("wb") as stream:
                    C.W.write_bundle(stream, entries, lambda data, method: data, flags=0x40, block_size=128)

            old, new = root / "old", root / "new"
            bundle(old, ambient())
            bundle(new, ambient(0.125))
            recipe = dict(reference_sha256=C.B.sha(old), members={"CAB-authored": [rule()]})
            self.assertEqual(C.qualify(old, new, recipe)["status"], "tolerance-accepted")
            bundle(new, ambient(0.125), b"wrong resource")
            with self.assertRaisesRegex(ValueError, "unselected"):
                C.qualify(old, new, recipe)


if __name__ == "__main__":
    unittest.main()
