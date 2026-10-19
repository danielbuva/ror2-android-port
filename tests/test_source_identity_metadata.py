"""Portable synthetic-YAML contracts for the production source scene reader."""

import importlib.util
import hashlib
import tempfile
import unittest
from pathlib import Path


def _load_reader():
    here = Path(__file__).resolve()
    for parent in here.parents:
        private_candidate = parent / "source_identity_metadata.py"
        public_module = parent / "scripts/lab/source_identity_metadata.py"
        if private_candidate.is_file():
            path = private_candidate
            break
        if public_module.is_file():
            path = public_module
            break
    else:
        raise RuntimeError("source_identity_metadata.py was not found from the test or repository root")
    spec = importlib.util.spec_from_file_location("source_identity_metadata_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


read_scene = _load_reader().read_scene
GOLDEN_ROOT_HASH = "24b7a5111ef7cbd1a43dd76458cc5a147e5301b214c4d3017951a344992a9863"


def _game_object(file_id, name, active=True):
    return f"""--- !u!1 &{file_id}
GameObject:
  m_Component: []
  m_Name: {name}
  m_IsActive: {1 if active else 0}
"""


def _transform(file_id, owner, father, root_order, children=()):
    child_rows = "".join(f"  - {{fileID: {child}}}\n" for child in children)
    return f"""--- !u!4 &{file_id}
Transform:
  m_GameObject: {{fileID: {owner}}}
  m_Children:
{child_rows}  m_Father: {{fileID: {father}}}
  m_RootOrder: {root_order}
"""


def _network_identity(component_id, owner, scene_id):
    return f"""--- !u!114 &{component_id}
MonoBehaviour:
  m_GameObject: {{fileID: {owner}}}
  m_Script: {{fileID: 372142912, guid: d382a022563c7517aadbc92ca1060016, type: 3}}
  m_SceneId:
    m_Value: {scene_id}
"""


def _toggle_controller(component_id, owner, groups):
    group_text = ""
    for refs, minimum, maximum in groups:
        group_text += "  - objects:\n"
        group_text += "".join(f"    - {{fileID: {ref}}}\n" for ref in refs)
        group_text += f"    minEnabled: {minimum}\n    maxEnabled: {maximum}\n"
    return f"""--- !u!114 &{component_id}
MonoBehaviour:
  m_GameObject: {{fileID: {owner}}}
  m_Script: {{fileID: 1517225185, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}}
  toggleGroups:
{group_text}"""


def synthetic_scene(*, same_shape_root=False, bad_child_order=False, missing_target=False, duplicate_scene_id=False):
    target_a, target_b = (2, 3) if not missing_target else (2, 999)
    second_id = 11 if duplicate_scene_id else 12
    child_b_order = 9 if bad_child_order else 1
    blocks = [
        _game_object(1, "Røøt", active=False),
        _game_object(2, "Dup", active=False),
        _game_object(3, "Dup"),
        _game_object(4, "Tail"),
        _game_object(5, "雪", active=False),
        _game_object(6, "ToggleGroupController"),
        _game_object(7, "ZeroIdentity"),
        _transform(11, 1, 0, 0, (12, 13, 14)),
        _transform(12, 2, 11, 0),
        _transform(13, 3, 11, child_b_order, (15,)),
        _transform(14, 4, 11, 2),
        _transform(15, 5, 13, 0),
        _transform(16, 6, 0, 1),
        _transform(17, 7, 0, 2),
        _network_identity(101, 2, 11),
        _network_identity(102, 3, second_id),
        _network_identity(103, 6, 13),
        _network_identity(104, 7, 0),
        _toggle_controller(201, 6, [([target_a, 0, target_b, 0], 1, 2), ([4, 0], 0, 1)]),
    ]
    if same_shape_root:
        blocks.extend(
            [
                _game_object(8, "Røøt", active=False),
                _game_object(30, "Dup", active=False),
                _game_object(31, "Dup"),
                _game_object(32, "雪", active=False),
                _game_object(33, "Tail"),
                _transform(118, 8, 0, 3, (119, 120, 121)),
                _transform(119, 30, 118, 0),
                _transform(120, 31, 118, 1, (122,)),
                _transform(121, 33, 118, 2),
                _transform(122, 32, 120, 0),
            ]
        )
    else:
        blocks.extend(
            [
                _game_object(8, "Røøt", active=False),
                _game_object(9, "Other"),
                _transform(18, 8, 0, 3, (19,)),
                _transform(19, 9, 18, 0),
            ]
        )
    return "".join(blocks)


class ProductionSourceIdentityReaderTests(unittest.TestCase):
    def read_synthetic(self, contents):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.unity"
            path.write_bytes(contents.encode("utf-8"))
            return read_scene(path)

    def test_unicode_duplicate_names_ordered_path_and_null_slot_layout(self):
        result = self.read_synthetic(synthetic_scene())
        self.assertEqual(result["toggle_controllers"][0]["groups"][0]["objects"][0]["transform_path"][0]["root_shape_sha256"], GOLDEN_ROOT_HASH)
        groups = result["toggle_controllers"][0]["groups"]
        controller = result["toggle_controllers"][0]
        self.assertEqual((controller["source_component_file_id"], controller["source_game_object_file_id"], controller["scene_id"]), (201, 6, 13))
        self.assertEqual(groups[0]["objects"][0]["transform_path"][0]["same_name_root_count"], 2)
        self.assertEqual([(group["min_enabled"], group["max_enabled"]) for group in groups], [(1, 2), (0, 1)])
        slots = groups[0]["objects"]
        self.assertEqual([slot["source_game_object_file_id"] for slot in slots], [2, 0, 3, 0])
        self.assertEqual([index for index, slot in enumerate(slots) if slot["transform_path"] is None], [1, 3])
        self.assertEqual([slots[0]["transform_path"][1]["index"], slots[2]["transform_path"][1]["index"]], [0, 1])
        self.assertEqual(groups[1]["objects"][1]["transform_path"], None)
        self.assertEqual([row["scene_id"] for row in result["network_identities"]], [11, 12, 13])

    def test_source_scene_receipt_hash_covers_raw_newline_bytes(self):
        lf_result = self.read_synthetic(synthetic_scene())
        crlf_bytes = synthetic_scene().replace("\n", "\r\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.unity"
            path.write_bytes(crlf_bytes)
            crlf_result = read_scene(path)
        self.assertEqual(crlf_result["network_identities"], lf_result["network_identities"])
        self.assertEqual(crlf_result["source_scene_sha256"], hashlib.sha256(crlf_bytes).hexdigest())
        self.assertNotEqual(crlf_result["source_scene_sha256"], lf_result["source_scene_sha256"])

    def test_rejects_identical_referenced_roots_and_parent_child_order_drift(self):
        with self.assertRaisesRegex(ValueError, "Duplicate same-name, same-shape roots"):
            self.read_synthetic(synthetic_scene(same_shape_root=True))
        with self.assertRaisesRegex(ValueError, "sibling index differs"):
            self.read_synthetic(synthetic_scene(bad_child_order=True))

    def test_rejects_missing_reference_and_duplicate_nonzero_scene_id(self):
        with self.assertRaisesRegex(ValueError, "Referenced GameObject has no Transform"):
            self.read_synthetic(synthetic_scene(missing_target=True))
        with self.assertRaisesRegex(ValueError, "Duplicate nonzero NetworkIdentity scene ID"):
            self.read_synthetic(synthetic_scene(duplicate_scene_id=True))


if __name__ == "__main__":
    unittest.main()
