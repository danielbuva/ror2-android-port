import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from animation_bindings import aim_clip_guids, reference_curves, repair


class AnimationBindingTests(unittest.TestCase):
    def test_aim_discovery_follows_native_layers_and_blend_trees_without_transitions(self):
        controller = """--- !u!91 &1
AnimatorController:
  m_AnimatorLayers:
  - serializedVersion: 5
    m_Name: AimPitch
    m_StateMachine: {fileID: 2}
    m_BlendingMode: 1
  - serializedVersion: 5
    m_Name: Body
    m_StateMachine: {fileID: 3}
    m_BlendingMode: 0
--- !u!1107 &2
AnimatorStateMachine:
  - m_State: {fileID: 4}
--- !u!1102 &4
AnimatorState:
  m_Motion: {fileID: 5}
  m_DstState: {fileID: 3}
--- !u!206 &5
BlendTree:
  - m_Motion: {fileID: 7400000, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 2}
--- !u!1102 &3
AnimatorState:
  m_Motion: {fileID: 7400000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}
"""
        self.assertEqual(aim_clip_guids(controller), {"a" * 32})
        self.assertEqual(aim_clip_guids(controller.replace("m_BlendingMode: 1", "m_BlendingMode: 0")), set())
        with self.assertRaisesRegex(RuntimeError, "Unresolved native aim state"):
            aim_clip_guids(controller.replace("m_Motion: {fileID: 5}", "m_Motion: {fileID: 6}"))

    def test_reference_pose_preserves_native_value_order_and_checked_paths(self):
        path = "Rig/Arm"
        bindings = [dict(path=zlib.crc32(path.encode()), attribute=attribute, typeID=4) for attribute in (1, 3, 4)]
        tree = dict(m_MuscleClip=dict(m_ValueArrayReferencePose=list(range(9))), m_ClipBindingConstant=dict(genericBindings=bindings))
        curves = reference_curves(tree, "    path: Rig/Arm\n")
        self.assertEqual([curve["value"] for curve in curves], list(range(9)))
        self.assertEqual(
            [curve["property"] for curve in curves],
            [prefix + "." + axis for prefix in ("m_LocalPosition", "m_LocalScale", "localEulerAnglesRaw") for axis in "xyz"],
        )
        with self.assertRaisesRegex(RuntimeError, "ambiguous native aim"):
            reference_curves(tree, "    path: OtherRig/Arm\n")
        tree["m_MuscleClip"]["m_ValueArrayReferencePose"].append(9)
        with self.assertRaisesRegex(RuntimeError, "cardinality"):
            reference_curves(tree, "    path: Rig/Arm\n")

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
