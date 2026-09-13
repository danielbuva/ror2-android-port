import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('public_audit', Path(__file__).resolve().parents[1] / 'scripts/audit-public.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PublicPrivacyTests(unittest.TestCase):
    def test_raw_bootstrap_capture_is_rejected_even_without_known_identifiers(self):
        self.assertTrue(audit.violations('environment/new-device-capture.json', b'{}'))

    def test_documented_config_placeholder_is_allowed(self):
        self.assertEqual([], audit.violations('environment/lab-config.example.json', b'{"device_serial":"AUTHORIZED_SERIAL"}'))

    def test_private_values_in_ordinary_document_are_rejected(self):
        home = '/'.join(['', 'Users', 'example', 'project']).encode()
        serial = b'{"device_serial":' + b'"example-device"}'
        email = b'person' + b'@' + b'example.com'
        for value in [home, serial, email]:
            with self.subTest(value_type=type(value)):
                self.assertTrue(audit.violations('docs/example.md', value))

    def test_game_payload_cannot_hide_in_source_directory(self):
        self.assertTrue(audit.violations('tools/example.bank', b'data'))
