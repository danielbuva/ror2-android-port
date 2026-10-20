import tempfile
import unittest
from pathlib import Path

import UnityPy

from phone_content import ASSET, PAYLOAD, make_bundle, stage


class PhoneContentTests(unittest.TestCase):
    def test_public_schema_bundle_contains_android_text_without_template(self):
        data = make_bundle()
        self.assertEqual(data, make_bundle())
        env = UnityPy.load(data)
        self.assertEqual(len(env.objects), 2)
        text = env.container[ASSET].read()
        self.assertEqual(text.m_Script, PAYLOAD)
        self.assertEqual(text.assets_file.unity_version, "2021.3.45f2")
        self.assertEqual(text.assets_file.target_platform.name, "Android")

    def test_stage_refuses_to_overwrite_an_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root) / "project"
            receipt = stage(project)
            self.assertFalse(receipt["device_accepted"])
            self.assertFalse(receipt["game_inputs"])
            with self.assertRaises(FileExistsError):
                stage(project)
