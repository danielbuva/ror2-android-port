"""Authored graph, identity and serialization contracts; no original game inputs."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from owner_audio_prefab import Flow, export_id, render, scalar


def pointer(path):
    return {"m_FileID": 0, "m_PathID": path}


def fixture():
    return [
        {
            "type": "GameObject",
            "class_id": 1,
            "path_id": 17,
            "tree": {
                "m_Component": [{"component": pointer(29)}, {"component": pointer(43)}],
                "m_Layer": 3,
                "m_Name": "Authored Root",
                "m_Tag": 0,
                "m_IsActive": True,
            },
        },
        {
            "type": "Transform",
            "class_id": 4,
            "path_id": 29,
            "tree": {
                "m_GameObject": pointer(17),
                "m_LocalRotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                "m_LocalPosition": {"x": 2.0, "y": 3.0, "z": 5.0},
                "m_LocalScale": {"x": 1.0, "y": 1.0, "z": 1.0},
                "m_Children": [],
                "m_Father": pointer(0),
            },
        },
        {
            "type": "MonoBehaviour",
            "class_id": 114,
            "path_id": 43,
            "script": {"assembly": "RoR2.dll", "namespace": "RoR2.WwiseUtils", "class": "SoundbankLoader"},
            "tree": {
                "m_GameObject": pointer(17),
                "m_Enabled": 1,
                "m_Script": {"m_FileID": 1, "m_PathID": 101},
                "m_Name": "",
                "soundbankStrings": ["authored_bank", "false"],
                "decodeBank": False,
                "saveDecodedBank": True,
            },
        },
    ]


class OwnerAudioPrefabTests(unittest.TestCase):
    def test_export_ids_match_independent_empty_hash_vectors(self):
        self.assertEqual(export_id(1, 0), 10**15 + 0xEF46DB3751D8E999 % 10**15)
        self.assertEqual(export_id(4, 1), 4 * 10**15 + 0xD5AFBA1336A3BE4B % 10**15)
        self.assertEqual(len({export_id(114, n) for n in range(13)}), 13)

    def test_whole_authored_graph_preserves_values_references_and_signed_zero(self):
        rows = fixture()
        before = deepcopy(rows)
        output = render(rows, {"RoR2.dll": "a" * 32}, {}).decode()
        self.assertEqual(rows, before)
        self.assertEqual(output.count("--- !u!"), 3)
        self.assertIn("m_GameObject: {fileID: 1709254077376921}", output)
        self.assertIn("m_LocalPosition: {x: 2, y: 3, z: 5}", output)
        self.assertIn("m_LocalEulerAnglesHint: {x: 0, y: -0, z: -0}", output)
        self.assertIn("  - authored_bank\n  - 'false'\n", output)
        self.assertIn("  decodeBank: 0\n  saveDecodedBank: 1\n", output)
        self.assertIn("  m_Name:\n", output)
        self.assertNotIn("m_PathID", output)

    def test_unknown_graph_and_script_shapes_refuse_instead_of_dropping_data(self):
        base = fixture()
        mutations = [
            lambda rows: rows[0]["tree"]["m_Component"].reverse(),
            lambda rows: rows[2]["tree"].update(m_GameObject=pointer(999)),
            lambda rows: rows[1]["tree"].update(m_Children=[pointer(999)]),
            lambda rows: rows[1]["tree"].update(m_LocalRotation={"x": 1, "y": 0, "z": 0, "w": 0}),
            lambda rows: rows[2]["tree"].update(unexpected_field="must not disappear"),
            lambda rows: rows[2]["script"].update(**{"class": "Unknown"}),
        ]
        for mutate in mutations:
            rows = deepcopy(base)
            mutate(rows)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                render(rows, {"RoR2.dll": "a" * 32}, {})

    def test_external_reference_requires_an_explicit_binding(self):
        rows = fixture()
        rows[2]["script"] = {"assembly": "AK.Wwise.Unity.MonoBehaviour.dll", "namespace": "", "class": "AkInitializer"}
        rows[2]["tree"] = {k: v for k, v in rows[2]["tree"].items() if k in {"m_GameObject", "m_Enabled", "m_Script", "m_Name"}}
        rows[2]["tree"]["InitializationSettings"] = {"m_FileID": 2, "m_PathID": 71}
        with self.assertRaisesRegex(ValueError, "unknown prefab reference"):
            render(rows, {"AK.Wwise.Unity.MonoBehaviour.dll": "b" * 32}, {})
        output = render(rows, {"AK.Wwise.Unity.MonoBehaviour.dll": "b" * 32}, {(2, 71): {"fileID": 11400000, "guid": "c" * 32, "type": 2}})
        self.assertIn(b"InitializationSettings: {fileID: 11400000, guid: cccccccccccccccccccccccccccccccc, type: 2}", output)

    def test_scalar_representation_keeps_reserved_text_and_rejects_nonfinite(self):
        self.assertEqual(scalar("false"), "'false'")
        self.assertEqual(scalar(""), "")
        self.assertEqual(scalar(Flow(fileID=0)), "{fileID: 0}")
        self.assertEqual(scalar(-0.0), "-0")
        for value in (float("nan"), float("inf"), "unsafe\nline"):
            with self.assertRaises(ValueError):
                scalar(value)


if __name__ == "__main__":
    unittest.main()
