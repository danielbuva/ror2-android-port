import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from animation_bindings import repair


class AnimationBindingTests(unittest.TestCase):
    def test_repairs_only_original_animator_parameter_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Assets/WholeGame"
            root.mkdir(parents=True)
            name = "Attack.hitBoxActive"
            key = zlib.crc32(name.encode())
            (root / "source.controller").write_text("  - m_Name: " + name + "\n")
            clip = root / "attack.anim"
            clip.write_text("    attribute: typetree_0x%X_unknown\n" % key + "      attribute: %d\n      script: {fileID: 0}\n      typeID: 95\n" % key)
            result = repair(Path(temporary))
            self.assertEqual(len(result["repaired"]), 1)
            self.assertIn("    attribute: " + name, clip.read_text())
            self.assertEqual(repair(Path(temporary))["repaired"], [])
            clip.write_text("    attribute: typetree_0x%X_unknown\n" % key + "      attribute: %d\n      script: {fileID: 0}\n      typeID: 4\n" % key)
            result = repair(Path(temporary))
            self.assertEqual(result["repaired"], [])
            self.assertEqual(len(result["unresolved"]), 1)


if __name__ == "__main__":
    unittest.main()
