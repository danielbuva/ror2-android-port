"""Keep the promotional-art exception limited to two reviewed files."""

import gzip
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_audit", ROOT / "scripts/audit-public.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class PublicBrandingAuditTests(unittest.TestCase):
    def test_compressed_recipe_patterns_are_checked_after_bounded_expansion(self):
        path = "recipe/authored.jsonl.gz"
        header = json.dumps({"input_id": "authored"}).encode() + b"\n"
        row = {"path": "original.bundle", "sha256": "authored", "members": []}
        data = gzip.compress(header + json.dumps(row).encode() + b"\n", mtime=0)
        self.assertEqual(AUDIT.violations(path, data), [])
        row["path"] = "/" + "home/" + "audit-fixture/secret"
        private = gzip.compress(header + json.dumps(row).encode() + b"\n", mtime=0)
        self.assertIn("personal home path", AUDIT.violations(path, private))
        self.assertIn("binary, middleware, or raw capture", AUDIT.violations("other/authored.gz", data))
        for malformed in (b"bad gzip", gzip.compress(b"{}\n"), gzip.compress(header + b"not json\n")):
            self.assertIn("invalid compressed recipe", AUDIT.violations(path, malformed))

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
