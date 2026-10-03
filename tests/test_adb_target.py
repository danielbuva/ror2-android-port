import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from adb_target import authorized_target


class AuthorizedTargetTests(unittest.TestCase):
    def test_second_connected_device_never_changes_selected_target(self):
        inventory = 'List of devices attached\nother-handheld\tdevice\nconfigured-nova\tdevice\n'
        self.assertEqual(authorized_target('configured-nova', inventory), 'configured-nova')

    def test_missing_target_does_not_fall_back_to_other_device(self):
        with self.assertRaises(ValueError):
            authorized_target('configured-nova', 'List of devices attached\nother-handheld\tdevice\n')

    def test_unauthorized_target_does_not_fall_back_to_other_device(self):
        for state in ['offline', 'unauthorized']:
            with self.subTest(state=state), self.assertRaises(ValueError):
                authorized_target('configured-nova', 'configured-nova\t' + state + '\nother-handheld\tdevice\n')

    def test_missing_configuration_does_not_infer_a_target(self):
        with self.assertRaises(ValueError):
            authorized_target(None, 'configured-nova\tdevice\n')
