"""Exercise the actual opt-in profiler owner and restoration with native doubles."""

from pathlib import Path
import unittest

from test_native_commerce_release_order import braced_block
from test_retained_catalog_dependencies import execute_host

ROOT = Path(__file__).resolve().parents[1]


class LoadingProfileCaptureTests(unittest.TestCase):
    def test_capture_request_closure_and_restore(self):
        owner = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text()
        capture = braced_block(owner, "public sealed class LoadingProfileCapture : IDisposable")
        host = (ROOT / "tests/fixtures/loading_profile_capture_host.cs").read_text()
        observer = braced_block(owner, "IEnumerator ObserveLoadingProfile()")
        result = execute_host(host + "\n" + capture + "\npartial class Monitor {\n" + observer + "\n}", "capture")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("loading profile opt-in closure restoration PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
