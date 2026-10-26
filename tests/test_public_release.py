"""Synthetic public releases and published RSA verification vectors; no keys created."""

import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tested_public_release", ROOT / "tools/phone-build/owner-apk/public_release.py")
PUBLIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLIC)

# Public n/e, message and signature from RFC 7515 Appendix A.2. No private
# component is used or stored. https://www.rfc-editor.org/rfc/rfc7515#appendix-A.2
RFC_MODULUS = (
    "ofgWCuLjybRlzo0tZWJjNiuSfb4p4fAkd_wWJcyQoTbji9k0l8W26mPddx"
    "HmfHQp-Vaw-4qPCJrcS2mJPMEzP1Pt0Bm4d4QlL-yRT-SFd2lZS-pCgNMs"
    "D1W_YpRPEwOWvG6b32690r2jZ47soMZo9wGzjb_7OMg0LOL-bSf63kpaSH"
    "SXndS5z5rexMdbBYUsLA9e-KXBdQOS-UTo7WTBEMa2R2CapHg665xsmtdV"
    "MTBQY4uDZlxvb3qCo5ZwKh9kG4LT6_I5IhlJH7aGhyxXFvUK-DWNmoudF8"
    "NAco9_h9iaGNj8q2ethFkMLs91kzk2PAcDTW9gb54h4FRWyuXpoQ"
)
RFC_SIGNATURE = (
    "cC4hiUPoj9Eetdgtv3hF80EGrhuB__dzERat0XF9g2VtQgr9PJbu3XOiZj5RZmh7"
    "AAuHIm4Bh-0Qc_lF5YKt_O8W2Fp5jujGbds9uJdbF9CUAr7t1dnZcAcQjbKBYNX4"
    "BAynRFdiuB--f_nZLgrnbyTyWzO75vRK5h6xBArLIARNPvkSjtQBMHlb1L07Qe7K"
    "0GarZRmB_eSN9383LcOLn6_dO--xi12jzDwusC-eOkHWEsqtFZESc6BfI7noOPqv"
    "hJ1phCnvWh6IeYI2w9QOYEUipUTI8np6LbgGY9Fs98rqVt5AXLIhWkWywlVmtVrB"
    "p0igcN_IoypGlUPQGe77Rw"
)
RFC_MESSAGE = b"eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGFtcGxlLmNvbS9pc19yb290Ijp0cnVlfQ"


def b64url(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def der(tag, value):
    size = len(value)
    length = bytes([size]) if size < 128 else bytes([0x82, size >> 8, size & 255]) if size > 255 else bytes([0x81, size])
    return bytes([tag]) + length + value


def public_vector_pem():
    # Encode the already-public RFC key as SPKI, not a key generation operation.
    key = der(48, der(2, b"\0" + b64url(RFC_MODULUS)) + der(2, b64url("AQAB")))
    spki = der(48, bytes.fromhex("300d06092a864886f70d0101010500") + der(3, b"\0" + key))
    return b"-----BEGIN PUBLIC KEY-----\n" + base64.b64encode(spki) + b"\n-----END PUBLIC KEY-----\n"


def release_body():
    return {
        "version": "alpha-2",
        "version_code": 2,
        "application_id": "dev.ror2lab.alpha",
        "minimum_installer_version": 1,
        "bundle_sha256": "f" * 64,
        "entries": {"apk/example.txt": {"recipe_sha256": "a" * 64, "producer_sha256": "b" * 64}},
    }


class PublicSignatureTests(unittest.TestCase):
    def test_rfc_public_vector_and_corruption(self):
        public, signature = public_vector_pem(), b64url(RFC_SIGNATURE)
        PUBLIC.verify_signature(RFC_MESSAGE, signature, public)
        for message, value in (
            (RFC_MESSAGE + b"x", signature),
            (RFC_MESSAGE, signature[:-1]),
            (RFC_MESSAGE, b"\0" * len(signature)),
            (RFC_MESSAGE, b"\xff" * len(signature)),
        ):
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                PUBLIC.verify_signature(message, value, public)

    @unittest.skipUnless(shutil.which("openssl"), "optional independent public-vector verifier unavailable")
    def test_public_vector_also_verifies_with_openssl(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "public.pem").write_bytes(public_vector_pem())
            (root / "signature").write_bytes(b64url(RFC_SIGNATURE))
            (root / "message").write_bytes(RFC_MESSAGE)
            subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(root / "public.pem"), "-signature", str(root / "signature"), str(root / "message")],
                check=True,
                capture_output=True,
                timeout=10,
            )

    def test_strict_json_and_public_key_parsing(self):
        for value in ('{"release":1,"release":2}', '{"n":NaN}', '{"n":Infinity}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PUBLIC.load_json(value)
        for key in (b"not a public key", public_vector_pem() + b"extra", public_vector_pem().replace(b"PUBLIC KEY", b"CERTIFICATE")):
            with self.assertRaises(ValueError):
                PUBLIC.public_numbers(key)
        with self.assertRaises(ValueError):
            PUBLIC._der(b"\x30\x81\x01a", 48)

    def test_envelope_binds_exact_canonical_body_and_trust(self):
        body = release_body()
        body["version"] = "alpha\n\u00e9\U0001f680"
        envelope = {"release": body, "signature": {"algorithm": "SHA256withRSA", "key_id": "reviewed", "value": "YWJj"}}
        with patch.object(PUBLIC, "verify_signature") as verify:
            self.assertEqual(PUBLIC.verify_envelope(json.dumps(envelope), {"reviewed": public_vector_pem()}), body)
            verify.assert_called_once_with(PUBLIC.RELEASE.signed_bytes(body), b"abc", public_vector_pem())
        self.assertIn(b"alpha\\n\\u00e9\\ud83d\\ude80", PUBLIC.RELEASE.signed_bytes(body))
        for change in ({"algorithm": "none"}, {"key_id": "downloaded"}, {"value": "invalid!"}, {"extra": "field"}):
            changed = copy.deepcopy(envelope)
            changed["signature"].update(change)
            with self.subTest(change=change), patch.object(PUBLIC, "verify_signature") as verify, self.assertRaises(ValueError):
                PUBLIC.verify_envelope(changed, {"reviewed": public_vector_pem()})
            verify.assert_not_called()


class PublicBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repository"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Fixture")
        self.git("config", "user.email", "fixture")
        for path, data in {
            "recipe/a.json": '{"schema":1,"example":"a"}',
            "recipe/b.json": '{"schema":1,"example":"b"}',
            "tools/producer.py": '# Authored synthetic producer\nprint("fixture")\n',
            "LICENSE": "Authored fixture license\n",
        }.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data)
        self.commit()
        self.plan = {
            "schema": 1,
            "files": ["LICENSE"],
            "entries": {
                "apk/a.txt": {"recipe_files": ["recipe/a.json"], "producer_files": ["tools/producer.py"], "job": "recipe/a.json"},
                "payload/b": {"recipe_files": ["recipe/b.json"], "producer_files": ["tools/producer.py"], "job": "recipe/b.json"},
            },
        }

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.STDOUT)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "test: synthetic public files")

    def build(self, name="public.zip"):
        return PUBLIC.build_bundle(self.root, self.plan, Path(self.temporary.name) / name)

    def test_repeatable_archive_and_exact_members(self):
        first, second = self.build("first.zip"), self.build("second.zip")
        self.assertEqual(first, second)
        with zipfile.ZipFile(Path(self.temporary.name) / "first.zip") as archive:
            self.assertEqual(set(archive.namelist()), {"LICENSE", "recipe/a.json", "recipe/b.json", "tools/producer.py", "bundle-index.json"})
            for item in archive.infolist():
                self.assertEqual(item.date_time, (1980, 1, 1, 0, 0, 0))
        with self.assertRaises(FileExistsError):
            self.build("first.zip")

    def test_dirty_and_untracked_bytes_never_enter_bundle(self):
        (self.root / "tools/producer.py").write_text("DIRTY UNREVIEWED")
        (self.root / "recipe/untracked.json").write_text("private untracked bytes")
        self.build()
        with zipfile.ZipFile(Path(self.temporary.name) / "public.zip") as archive:
            self.assertNotIn(b"DIRTY", archive.read("tools/producer.py"))
        self.plan["files"].append("recipe/untracked.json")
        with self.assertRaisesRegex(ValueError, "committed regular"):
            self.build("untracked.zip")

    def test_transitive_shared_producer_and_one_recipe_changes(self):
        first = self.build("first.zip")
        (self.root / "recipe/a.json").write_text('{"schema":1,"example":"changed"}')
        self.commit()
        second = self.build("second.zip")
        self.assertNotEqual(first["entries"]["apk/a.txt"]["recipe_sha256"], second["entries"]["apk/a.txt"]["recipe_sha256"])
        self.assertEqual(first["entries"]["payload/b"], second["entries"]["payload/b"])
        (self.root / "tools/producer.py").write_text('# Shared dependency changed\nprint("fixture")\n')
        self.commit()
        third = self.build("third.zip")
        for name in first["entries"]:
            self.assertNotEqual(second["entries"][name]["producer_sha256"], third["entries"][name]["producer_sha256"])

    def test_private_binary_symlink_and_traversal_refused(self):
        (self.root / "recipe/key.p12").write_text("synthetic forbidden container")
        (self.root / "recipe/link.json").symlink_to("a.json")
        self.commit()
        for path in ("recipe/key.p12", "recipe/link.json", "../outside.json", "work/private.json"):
            self.plan["files"] = [path]
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.build("rejected.zip")
        self.assertFalse((Path(self.temporary.name) / "rejected.zip").exists())

    def test_dependency_fingerprints_cannot_be_substituted(self):
        result = self.build()
        body = release_body()
        body["entries"] = result["entries"]
        PUBLIC.validate_bundle_index(result["index"], body)
        bad = copy.deepcopy(result["index"])
        bad["files"]["tools/producer.py"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "fingerprints"):
            PUBLIC.validate_bundle_index(bad, body)
        bad = copy.deepcopy(result["index"])
        bad["entries"]["apk/a.txt"]["job"] = "recipe/b.json"
        with self.assertRaisesRegex(ValueError, "job must belong"):
            PUBLIC.validate_bundle_index(bad, body)

    def test_client_rejects_private_file_kinds_and_modified_launcher_art(self):
        for name in ("tools/private.p12", "tools/unsigned.apk", "tools/native.so", "payload/game.bundle", "launcher/background.png"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                PUBLIC.public_source_path(name, "f" * 64)
        self.assertEqual(PUBLIC.public_source_path("launcher/background.png", PUBLIC.LAUNCHER_ART_SHA256), "launcher/background.png")
        self.assertEqual(PUBLIC.public_source_path("recipe/templates/original-assembly.meta", "f" * 64), "recipe/templates/original-assembly.meta")

    def test_incomplete_publication_fails_before_signing(self):
        result = self.build()
        body = release_body()
        body.update(bundle_sha256=result["bundle_sha256"], entries=result["entries"])
        with self.assertRaisesRegex(ValueError, "lacks installer/assembly/toolchain"):
            PUBLIC.validate_publication(Path(self.temporary.name) / "public.zip", body)

    def test_cli_emits_detached_signature_assets_not_envelope(self):
        (self.root / "plan.json").write_text(json.dumps(self.plan))
        self.commit()
        public = Path(self.temporary.name) / "public.pem"
        public.write_bytes(public_vector_pem())
        output = Path(self.temporary.name) / "published"

        def sign(body, key_id, private, public):
            return {"release": body, "signature": {"algorithm": "SHA256withRSA", "key_id": key_id, "value": "YWJj"}}

        arguments = [
            "public_release.py",
            "--repository",
            str(self.root),
            "--plan",
            "plan.json",
            "--output",
            str(output),
            "--version",
            "owner-v2",
            "--version-code",
            "2",
            "--key-id",
            "test-public-vector",
            "--signing-key",
            "NOT-PROVISIONED",
            "--public-key",
            str(public),
        ]
        with (
            patch.object(sys, "argv", arguments),
            patch.object(PUBLIC, "validate_publication") as validate,
            patch.object(PUBLIC, "sign_envelope", side_effect=sign),
        ):
            PUBLIC.main()
        validate.assert_called_once()
        self.assertEqual(set(path.name for path in output.iterdir()), {"release.json", "release.sig", "public-tools.zip"})
        self.assertEqual(PUBLIC.load_json((output / "release.json").read_bytes())["version_code"], 2)
        self.assertNotIn("signature", PUBLIC.load_json((output / "release.json").read_bytes()))
        self.assertEqual(PUBLIC.load_json((output / "release.sig").read_bytes())["key_id"], "test-public-vector")


if __name__ == "__main__":
    unittest.main()
