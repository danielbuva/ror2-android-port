"""Host golden-vector companion for the exact-editor C# parity fixture."""

import base64
import hashlib
import re
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "tools/catalog/SourceIdentityTransformParityFixture.cs"


def shape(name, children=()):
    encoded_name = base64.b64encode(name.encode("utf-8")).decode("ascii")
    return encoded_name + "|" + str(len(children)) + "[" + "".join(children) + "]"


class TransformHashParityVectorTests(unittest.TestCase):
    def test_unicode_ordered_tree_matches_editor_fixture_golden_hash(self):
        root_signature = shape(
            "Røøt",
            [
                shape("Dup"),
                shape("Dup", [shape("雪")]),
                shape("Tail"),
            ],
        )
        digest = hashlib.sha256(root_signature.encode("ascii")).hexdigest()
        fixture = FIXTURE.read_text()
        expected = re.search(r'ExpectedShapeHash = "([0-9a-f]{64})"', fixture)
        self.assertIsNotNone(expected)
        self.assertEqual(digest, expected.group(1))


if __name__ == "__main__":
    unittest.main()
