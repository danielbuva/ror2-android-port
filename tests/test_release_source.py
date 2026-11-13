"""Debug release seam contracts using authored HTTP data, no APK/game/key input.

Only the RSA primitive is mocked; signature routing, trust, update checking and
release-build refusal run through the production updater.
"""

import base64
import copy
import hashlib
import http.server
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/owner-apk"
SPEC = importlib.util.spec_from_file_location("debug_source_updates", SOURCE / "updates.py")
U = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(U)
S = U.SOURCE


class ReleaseSourceTests(unittest.TestCase):
    def setUp(self):
        self.trust = {"repository": "example/owner", "application_id": "dev.ror2lab.alpha", "keys": {"production": "authored production marker"}}
        self.override = {"enabled": True, "base_url": "http://127.0.0.1:9000/", "key_id": "lab-test", "public_key": "authored test marker"}

    def test_absent_override_keeps_production_transport_and_keys(self):
        validate = Mock()
        for debug in (False, True):
            trust, transport = S.configure(self.trust, None, debuggable=debug, validate_public_key=validate)
            self.assertIs(trust, self.trust)
            self.assertIsNone(transport)
        validate.assert_not_called()

    def test_release_build_rejects_url_key_and_combined_override(self):
        validate = Mock()
        for override in (self.override, {"base_url": self.override["base_url"]}, {"key_id": "lab-test", "public_key": "test"}):
            with self.subTest(override=override), self.assertRaisesRegex(ValueError, "forbidden in release builds"):
                S.configure(self.trust, override, debuggable=False, validate_public_key=validate)
        validate.assert_not_called()

    def test_debug_build_requires_explicit_boolean_opt_in(self):
        for enabled in (False, None, "true", 1):
            with self.subTest(enabled=enabled), self.assertRaisesRegex(ValueError, "explicit enabled=true"):
                S.configure(self.trust, dict(self.override, enabled=enabled), debuggable=True, validate_public_key=Mock())
        without_opt_in = dict(self.override)
        del without_opt_in["enabled"]
        with self.assertRaisesRegex(ValueError, "explicit enabled=true"):
            S.configure(self.trust, without_opt_in, debuggable=True, validate_public_key=Mock())

    def test_test_key_is_additional_validated_and_not_persisted_into_trust(self):
        before = copy.deepcopy(self.trust)
        validate = Mock()
        trust, transport = S.configure(self.trust, self.override, debuggable=True, validate_public_key=validate)
        validate.assert_called_once_with("authored test marker")
        self.assertEqual(trust["keys"], {**before["keys"], "lab-test": "authored test marker"})
        self.assertEqual(self.trust, before)
        self.assertEqual(transport.metadata_url(), "http://127.0.0.1:9000/latest.json")
        with self.assertRaisesRegex(ValueError, "production keys cannot be replaced"):
            S.configure(self.trust, dict(self.override, key_id="production"), debuggable=True, validate_public_key=validate)
        with self.assertRaisesRegex(ValueError, "SubjectPublicKeyInfo"):
            S.configure(self.trust, self.override, debuggable=True, validate_public_key=U.public().public_numbers)

    def test_transport_requires_loopback_and_retains_asset_boundary(self):
        for base in ("http://example.test:9000/", "http://127.0.0.1/", "http://user@127.0.0.1:9000/", "http://127.0.0.1:9000/../"):
            with self.subTest(base=base), self.assertRaises(ValueError):
                S.DebugReleaseTransport(base)
        transport = S.DebugReleaseTransport(self.override["base_url"])
        self.assertEqual(transport.asset_url(self.override["base_url"] + "release.json", "release.json"), self.override["base_url"] + "release.json")
        for url in ("http://127.0.0.1:9001/release.json", "http://127.0.0.1:9000/../release.json", "http://127.0.0.1:9000/release.json?token=x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                transport.allowed(url)

    def test_android_flag_ui_and_source_closure_are_wired(self):
        activity = (SOURCE.parent / "managed-host/ToolHostActivity.java").read_text()
        self.assertIn("app.getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE", activity)
        self.assertIn('env.put("ROR2_INSTALLER_DEBUGGABLE", debuggable(app) ? "1" : "0")', activity)
        self.assertIn("TEST RELEASE SOURCE", activity)
        self.assertIn("TEST RELEASE OVERRIDE REJECTED", activity)
        self.assertIn("tools/phone-build/owner-apk/release_source.py", U.public().PUBLISHING_SOURCE_FILES)
        self.assertIn('"owner-apk/release_source.py"', (SOURCE.parent / "managed-host/stage.py").read_text())


class DebugUpdateHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.inputs, self.runtime, self.native = [Path(self.temporary.name) / name for name in ("inputs", "runtime", "native")]
        for path in (self.inputs, self.runtime, self.native):
            path.mkdir()
        self.request = self.inputs / "update-request.json"
        U.write_json(
            self.request,
            {"action": "release-check", "application_id": "dev.ror2lab.alpha", "installed_version": 0, "installed_release_version": 0, "installer_version": 3},
        )
        U.write_json(self.runtime / "release-trust.json", {"repository": "example/owner", "application_id": "dev.ror2lab.alpha", "keys": {}})
        self.release = {
            "version": "authored-1",
            "version_code": 1,
            "application_id": "dev.ror2lab.alpha",
            "minimum_installer_version": 3,
            "data_schema": {"writes": 1, "reads": [1]},
            "bundle_sha256": hashlib.sha256(b"authored tools").hexdigest(),
            "entries": {"payload/authored": {"recipe_sha256": "a" * 64, "producer_sha256": "b" * 64}},
        }
        self.paths = {
            "/release.json": json.dumps(self.release).encode(),
            "/release.sig": json.dumps(
                {"algorithm": "SHA256withRSA", "key_id": "lab-test", "value": base64.b64encode(b"authored signature marker").decode()}
            ).encode(),
            "/public-tools.zip": b"authored tools",
        }
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                data = owner.paths[self.path]
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        base = "http://127.0.0.1:" + str(self.server.server_port) + "/"
        metadata = {
            "draft": False,
            "prerelease": False,
            "tag_name": "owner-v1",
            "assets": [{"name": name, "size": len(data), "browser_download_url": base + name[1:]} for name, data in self.paths.items()],
        }
        for asset in metadata["assets"]:
            asset["name"] = asset["name"][1:]
        self.paths["/latest.json"] = json.dumps(metadata).encode()
        U.write_json(
            self.inputs / "debug-release-source.json", {"enabled": True, "base_url": base, "key_id": "lab-test", "public_key": "authored public marker"}
        )
        self.key_validator = patch.object(U.public(), "public_numbers", return_value=(1, 65537))
        self.key_validator.start()
        self.addCleanup(self.key_validator.stop)

        def verify(message, signature, key):
            if message != U.RELEASE.signed_bytes(self.release) or signature != b"authored signature marker" or key != "authored public marker":
                raise ValueError("release signature invalid")

        self.verifier = patch.object(U.public(), "verify_signature", side_effect=verify)
        self.verifier.start()
        self.addCleanup(self.verifier.stop)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_debug_check_uses_local_source_without_downloading_tools(self):
        U.run(self.request, self.runtime, self.native, debuggable=True)
        self.assertEqual(json.loads((self.inputs / "update-state.json").read_text())["state"], "UPDATE_AVAILABLE")
        self.assertEqual(set(self.requests), {"/latest.json", "/release.json", "/release.sig"})
        self.assertEqual(json.loads((self.runtime / "release-trust.json").read_text())["keys"], {})

    def test_release_refuses_before_network_or_key_validation(self):
        with self.assertRaisesRegex(ValueError, "forbidden in release builds"):
            U.run(self.request, self.runtime, self.native)
        self.assertEqual(self.requests, [])
        self.assertFalse((self.inputs / "release-candidate.json").exists())

    def test_tamper_and_unknown_publisher_still_refuse(self):
        original = self.paths["/release.json"]
        self.paths["/release.json"] = json.dumps(dict(self.release, version="tampered")).encode()
        with self.assertRaisesRegex(ValueError, "signature invalid"):
            U.run(self.request, self.runtime, self.native, debuggable=True)
        self.paths["/release.json"] = original
        signature = json.loads(self.paths["/release.sig"])
        signature["key_id"] = "wrong-key"
        self.paths["/release.sig"] = json.dumps(signature).encode()
        with self.assertRaisesRegex(ValueError, "not trusted"):
            U.run(self.request, self.runtime, self.native, debuggable=True)
        self.assertFalse((self.inputs / "release-candidate.json").exists())
        self.assertNotIn("/public-tools.zip", self.requests)
