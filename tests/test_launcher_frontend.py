"""Launcher contract and narrow original-art exception; no device readiness claim."""

import importlib.util
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("launcher_public_audit", ROOT / "scripts/audit-public.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class LauncherFrontendTests(unittest.TestCase):
    def test_exact_original_art_only(self):
        self.assertEqual(set(AUDIT.PUBLIC_LAUNCHER_SHA256), {"launcher/background.png"})
        path = "launcher/background.png"
        data = (ROOT / path).read_bytes()
        self.assertEqual(AUDIT.violations(path, data), [])
        for name, content in [(path, data + b"changed"), ("launcher/other.png", data), ("launcher/demo/background.png", data)]:
            self.assertIn("binary, middleware, or raw capture", AUDIT.violations(name, content))
        secret = b"-----BEGIN " + b"PRIVATE KEY-----"
        with patch.dict(AUDIT.PUBLIC_LAUNCHER_SHA256, {path: AUDIT.hashlib.sha256(secret).hexdigest()}):
            self.assertIn("private key", AUDIT.violations(path, secret))

    def test_demo_is_separate_and_public_about_omits_provenance(self):
        app = (ROOT / "launcher/app.js").read_text()
        self.assertNotIn("setInterval", app)
        self.assertNotIn("demo/", app)
        for path in ["launcher/index.html", "launcher/demo/index.html"]:
            self.assertNotIn("The background is original AI-generated artwork", (ROOT / path).read_text())
        self.assertIn("simulated", (ROOT / "launcher/demo/index.html").read_text())

    @unittest.skipUnless(shutil.which("node"), "Node is required for launcher controller contracts")
    def test_controller_contracts(self):
        subprocess.run(["node", "--test", "launcher/tests/controller.test.js"], cwd=ROOT, check=True, capture_output=True, text=True)
