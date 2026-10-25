"""Authored editor/native-base composition and script-schema hash contracts."""

import importlib.util
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("properties_identity", ROOT / "scripts/lab/script_identity.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def blob(nodes, common=False):
    strings, encoded = bytearray(), []
    reverse = {text: offset for offset, text in S.COMMON.items()}

    def label(value):
        if common and value in reverse:
            return 0x80000000 | reverse[value]
        start = len(strings)
        strings.extend(value.encode() + b"\0")
        return start

    for index, (version, level, flags, kind, name, size, meta) in enumerate(nodes):
        encoded.append(struct.pack("<hBBIIiiiQ", version, level, flags, label(kind), label(name), size, index, meta, 0))
    return struct.pack("<II", len(nodes), len(strings)) + b"".join(encoded) + strings


NATIVE = [
    (1, 0, 0, "MonoBehaviour", "Base", -1, 0x8000),
    (2, 1, 0, "unsigned int", "m_ObjectHideFlags", 4, 0),
    (1, 1, 0, "string", "m_EditorClassIdentifier", -1, 0x4000),
    (1, 1, 0, "string", "m_Text", -1, 0),
]
ORIGINAL = [
    (1, 0, 0, "MonoBehaviour", "Base", -1, 0x8000),
    (9, 1, 0, "unsigned int", "m_ObjectHideFlags", 4, 0x4000),
    (3, 1, 0, "AuthoredPair", "pair", -1, 0),
    (1, 2, 0, "float", "first", 4, 0),
    (1, 2, 0, "float", "second", 4, 0x4000),
]


def digest(original=ORIGINAL, native=NATIVE, **names):
    return S.properties_hash(
        names.get("name", "HostContract"), names.get("namespace", "Lab"), names.get("assembly", "Fixture.dll"), blob(original), blob(native)
    )


class ScriptPropertiesHashTests(unittest.TestCase):
    def test_editor_base_precedes_original_custom_fields_and_raw_identity_prefix(self):
        # Independent explicit feed: SDK base replaces the original base, SDK
        # custom text is omitted, and original nested fields retain their order.
        data = b"HostContractLabFixture.dll"
        for kind, name, size, flags, version, alignment in (
            ("MonoBehaviour", "Base", -1, 0, 1, 0),
            ("unsigned int", "m_ObjectHideFlags", 4, 0, 2, 0),
            ("string", "m_EditorClassIdentifier", -1, 0, 1, 0x4000),
            ("AuthoredPair", "pair", -1, 0, 3, 0),
            ("float", "first", 4, 0, 1, 0),
            ("float", "second", 4, 0, 1, 0x4000),
        ):
            data += kind.encode() + name.encode() + struct.pack("<iiiI", size, flags, version, alignment)
        self.assertEqual(digest(), S.md4(data))
        self.assertNotEqual(digest(name="Lab", namespace="HostContract"), digest())
        self.assertEqual(S.properties_hash("HostContract", "Lab", "Fixture.dll", blob(ORIGINAL, True), blob(NATIVE, True)), digest())

    def test_only_native_base_and_custom_semantic_metadata_affect_hash(self):
        changed = ORIGINAL.copy()
        changed[1] = (12, 1, 1, "bool", "m_ObjectHideFlags", 1, 0)
        self.assertEqual(digest(changed), digest())
        changed = NATIVE.copy()
        changed[-1] = (8, 1, 0, "float", "ignoredSdkCustom", 4, 0)
        self.assertEqual(digest(native=changed), digest())
        changed = ORIGINAL.copy()
        changed[-1] = (1, 2, 0, "float", "second", 4, 0xC000)
        self.assertEqual(digest(changed), digest())
        for node in ((2, 2, 0, "float", "second", 4, 0x4000), (1, 2, 1, "float", "second", 4, 0x4000), (1, 2, 0, "float", "second", 4, 0)):
            changed[-1] = node
            self.assertNotEqual(digest(changed), digest())

    def test_decoder_refuses_truncation_bad_nesting_and_unknown_common_strings(self):
        source = blob(ORIGINAL, True)
        for broken in (source[:7], source[:-1], blob([]), blob([(1, 1, 0, "float", "orphan", 4, 0)]), blob([ORIGINAL[0], (1, 3, 0, "float", "gap", 4, 0)])):
            with self.subTest(size=len(broken)), self.assertRaises(ValueError):
                S.tree_nodes(broken)
        broken = bytearray(source)
        struct.pack_into("<I", broken, 12, 0x8000FFFF)
        with self.assertRaisesRegex(ValueError, "common string"):
            S.tree_nodes(broken)
        with self.assertRaisesRegex(ValueError, "base absent"):
            digest(native=NATIVE[:2])


if __name__ == "__main__":
    unittest.main()
