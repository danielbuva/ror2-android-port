import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lab'))
import device

# `run` is mocked, so the aapt location only has to exist as a string; keep the workstation's real value.
ANDROID_ROOT = {'UNITY_ANDROID_ROOT': os.environ.get('UNITY_ANDROID_ROOT', '/unavailable-android-root')}


@patch.dict(os.environ, ANDROID_ROOT)
class ApkIdentityTests(unittest.TestCase):
    def test_wrong_or_missing_package_stops_before_device_mutation(self):
        android = device.Device.__new__(device.Device)
        android.exists = Mock()
        android.storage = Mock()
        android.cmd = Mock()
        for metadata in [b"package: name='dev.ror2lab.other'\n", b'no package metadata\n']:
            with self.subTest(metadata=metadata), patch.object(
                    device, 'run', return_value=SimpleNamespace(stdout=metadata)):
                with self.assertRaisesRegex(RuntimeError, 'single owned lab package'):
                    android.install(Path('candidate.apk'))
            android.exists.assert_not_called()
            android.storage.assert_not_called()
            android.cmd.assert_not_called()

    def test_same_package_allows_changed_version_and_label(self):
        metadata = ("package: name='" + device.PACKAGE + "' versionCode='2'\n"
                    "application-label:'Updated lab'\n").encode()
        with patch.object(device, 'run', return_value=SimpleNamespace(stdout=metadata)):
            device.validate_apk_identity(Path('candidate.apk'))


if __name__ == '__main__':
    unittest.main()
