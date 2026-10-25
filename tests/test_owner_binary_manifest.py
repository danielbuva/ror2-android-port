"""An independently authored manifest checks launcher routing and retained values."""

import importlib.util
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


PATCH = load("owner_manifest", ROOT / "tools/phone-build/owner-apk/binary_manifest.py")
WIRE = load("owner_manifest_wire", ROOT / "scripts/lab/phone_apk.py")
NONE = 0xFFFFFFFF


def authored_manifest(utf8=True, unity=PATCH.UNITY, duplicate=False, version_kind=0x10, duplicate_version=False, omit_version=False):
    strings = [
        "manifest",
        "application",
        "activity",
        "intent-filter",
        "action",
        "category",
        "meta-data",
        "package",
        "versionCode",
        PATCH.ANDROID,
        "name",
        "configChanges",
        "value",
        "dev.owner.authoredfixture",
        unity,
        "android.intent.action.MAIN",
        "android.intent.category.LAUNCHER",
        "authored.marker",
        "Éta𝄞",
    ]
    content, offsets = bytearray(), []
    for text in strings:
        offsets.append(len(content))
        units = len(text.encode("utf-16-le")) // 2
        encoded = text.encode("utf-8" if utf8 else "utf-16-le")
        content += (bytes([units, len(encoded)]) if utf8 else struct.pack("<H", units)) + encoded + (b"\0" if utf8 else b"\0\0")
    content += bytes(-len(content) % 4)
    first = 28 + 4 * len(strings)
    pool = struct.pack("<HHIIIIII", 1, 28, first + len(content), len(strings), 0, 0x100 if utf8 else 0, first, 0)
    pool += struct.pack("<" + "I" * len(offsets), *offsets) + content
    resources = [0] * 13
    resources[8], resources[10], resources[11], resources[12] = 0x0101021B, 0x01010003, 0x0101001F, 0x01010024
    resource_map = struct.pack("<HHI", 0x180, 8, 8 + len(resources) * 4) + struct.pack("<" + "I" * len(resources), *resources)

    def attribute(name, value, kind=3, namespace=9):
        return struct.pack("<IIIHBBI", namespace, name, value if kind == 3 else NONE, 8, 0, kind, value)

    def node(tag, attrs, children=b""):
        block = b"".join(attrs)
        head = struct.pack("<HHIII", 0x102, 16, 36 + len(block), 1, NONE)
        head += struct.pack("<IIHHHHHH", NONE, tag, 20, 20, len(attrs), 0, 0, 0) + block
        return head + children + struct.pack("<HHIIIII", 0x103, 16, 24, 1, NONE, NONE, tag)

    intent = node(3, [], node(4, [attribute(10, 15)]) + node(5, [attribute(10, 16)]))
    marker = node(6, [attribute(10, 17), attribute(12, 18)])
    activity = node(2, [attribute(10, 14), attribute(11, 0x700, 0x10)], intent * (2 if duplicate else 1) + marker)
    versions = [] if omit_version else [attribute(8, 7, version_kind)] * (2 if duplicate_version else 1)
    xml = node(0, [attribute(7, 13, namespace=NONE), *versions], node(1, [], activity))
    return struct.pack("<HHI", 3, 8, 8 + len(pool) + len(resource_map) + len(xml)) + pool + resource_map + xml


def read(data):
    chunks = list(WIRE._chunks(data, 8, len(data)))
    pool = next(x for x in chunks if x[0] == 1)
    strings = WIRE._strings(data, *pool[1:])
    resource_chunk = next(x for x in chunks if x[0] == 0x180)
    resources = struct.unpack_from("<" + "I" * ((resource_chunk[3] - 8) // 4), data, resource_chunk[1] + 8)
    stack, elements = [], []
    for kind, start, header, size in chunks:
        if kind == 0x102:
            ns, tag, relative, stride, count = struct.unpack_from("<IIHHH", data, start + header)
            attrs = {}
            for i in range(count):
                ans, name, raw, value_size, reserved, atype, value = struct.unpack_from("<IIIHBBI", data, start + header + relative + i * stride)
                attrs[(None if ans == NONE else strings[ans], strings[name])] = strings[value] if atype == 3 else value
                if ans != NONE:
                    assert name < len(resources)
            element = {"tag": strings[tag], "attributes": attrs, "parents": list(stack)}
            elements.append(element)
            stack.append(element)
        elif kind == 0x103:
            closed = stack.pop()
            assert closed["tag"] == strings[struct.unpack_from("<I", data, start + header + 4)[0]]
    assert not stack
    return strings, resources, elements


class OwnerBinaryManifestTests(unittest.TestCase):
    def test_both_encodings_move_launcher_preserve_existing_identity_and_close_bypass(self):
        for utf8 in (True, False):
            with self.subTest(utf8=utf8):
                original = authored_manifest(utf8=utf8)
                old_strings, old_resources, old_elements = read(original)
                patched = PATCH.patch(original, WIRE)
                strings, resources, elements = read(patched)
                self.assertEqual(strings[: len(old_strings)], old_strings)
                self.assertEqual(resources[: len(old_resources)], old_resources)
                activities = [e for e in elements if e["tag"] == "activity"]
                self.assertEqual(len(activities), 2)
                key = (PATCH.ANDROID, "name")
                unity = next(e for e in activities if e["attributes"][key] == PATCH.UNITY)
                bootstrap = next(e for e in activities if e["attributes"][key] == PATCH.BOOTSTRAP)
                self.assertEqual(unity["attributes"][(PATCH.ANDROID, "exported")], 0)
                self.assertEqual(bootstrap["attributes"][(PATCH.ANDROID, "exported")], 1)
                self.assertEqual(unity["attributes"][(PATCH.ANDROID, "configChanges")], 0x700)
                launchers = [e for e in elements if e["tag"] == "category" and e["attributes"].get(key) == "android.intent.category.LAUNCHER"]
                self.assertEqual(len(launchers), 1)
                self.assertIs(launchers[0]["parents"][-2], bootstrap)
                markers = [e for e in elements if e["tag"] == "meta-data"]
                self.assertEqual(markers[0]["attributes"][(PATCH.ANDROID, "value")], "Éta𝄞")
                self.assertIs(markers[0]["parents"][-1], unity)
                self.assertEqual(elements[0]["attributes"], old_elements[0]["attributes"])
                with self.assertRaisesRegex(ValueError, "already present"):
                    PATCH.patch(patched, WIRE)

    def test_refuses_unknown_activity_ambiguous_launcher_and_truncated_document(self):
        for data in (authored_manifest(unity="dev.owner.OtherActivity"), authored_manifest(duplicate=True), authored_manifest()[:-1]):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                PATCH.patch(data, WIRE)

    def test_owner_upgrade_changes_only_version_among_original_manifest_attributes(self):
        for utf8 in (True, False):
            with self.subTest(utf8=utf8):
                original = authored_manifest(utf8=utf8)
                _, _, before = read(original)
                _, _, after = read(PATCH.patch(original, WIRE, version_code=8))
                expected = dict(before[0]["attributes"])
                expected[(PATCH.ANDROID, "versionCode")] = 8
                self.assertEqual(after[0]["attributes"], expected)

    def test_owner_upgrade_accepts_policy_maximum(self):
        _, _, elements = read(PATCH.patch(authored_manifest(), WIRE, version_code=2100000000))
        self.assertEqual(elements[0]["attributes"][(PATCH.ANDROID, "versionCode")], 2100000000)

    def test_owner_upgrade_refuses_nonincreasing_invalid_and_ambiguous_versions(self):
        for version in (0, -1, True, 7, 6, 2100000001, 2147483647, 2147483648, "8"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                PATCH.patch(authored_manifest(), WIRE, version_code=version)
        for options in ({"version_kind": 3}, {"duplicate_version": True}, {"omit_version": True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                PATCH.patch(authored_manifest(**options), WIRE, version_code=8)
