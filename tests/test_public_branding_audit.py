"""Keep the promotional-art exception limited to two reviewed files."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_audit", ROOT / "scripts/audit-public.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class PublicBrandingAuditTests(unittest.TestCase):
    def test_only_two_reviewed_paths(self):
        self.assertEqual(
            set(AUDIT.PUBLIC_BRANDING_SHA256),
            {
                "docs/assets/branding/ror2-android-banner.png",
                "docs/assets/branding/ror2-android-icon.png",
            },
        )

    def test_exact_images_pass_and_modified_bytes_fail(self):
        for path in AUDIT.PUBLIC_BRANDING_SHA256:
            with self.subTest(path=path):
                data = (ROOT / path).read_bytes()
                self.assertEqual(AUDIT.violations(path, data), [])
                self.assertIn("binary, middleware, or raw capture", AUDIT.violations(path, data + b"changed"))
                self.assertIn("binary, middleware, or raw capture", AUDIT.violations("docs/assets/branding/other.png", data))
                self.assertIn("private output directory", AUDIT.violations("work/" + Path(path).name, data))

    def test_reviewed_hash_does_not_skip_sensitive_patterns(self):
        path = next(iter(AUDIT.PUBLIC_BRANDING_SHA256))
        data = b"-----BEGIN " + b"PRIVATE KEY-----"
        with patch.dict(AUDIT.PUBLIC_BRANDING_SHA256, {path: AUDIT.hashlib.sha256(data).hexdigest()}):
            self.assertIn("private key", AUDIT.violations(path, data))
