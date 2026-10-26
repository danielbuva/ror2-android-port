"""Release update acceptance with authored files, no game or device input."""

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-apk/release.py"
SPEC = importlib.util.spec_from_file_location("phone_release", PATH)
OWNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OWNER)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.release = {
            "version": "alpha-2",
            "version_code": 2,
            "application_id": "dev.ror2lab.alpha",
            "minimum_installer_version": 1,
            "bundle_sha256": "f" * 64,
            "entries": {name: {"recipe_sha256": "a" * 64, "producer_sha256": "b" * 64} for name in ("apk/classes.dex", "payload/example")},
        }
        self.context = dict(installer_version=1, application_id="dev.ror2lab.alpha", installed_version=1)

    def test_incremental_first_noop_and_one_changed_recipe(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []

            def produce(name, row, output):
                calls.append(name)
                output.write_text(name + row["recipe_sha256"])

            options = dict(self.context, root=temporary, input_sha256="c" * 64, produce=produce)
            first = OWNER.rebuild(self.release, **options)
            self.assertEqual(first["rebuilt"], sorted(self.release["entries"]))
            calls.clear()
            self.assertEqual(OWNER.rebuild(self.release, **options)["rebuilt"], [])
            self.assertEqual(calls, [])
            self.release["entries"]["payload/example"]["recipe_sha256"] = "d" * 64
            self.assertEqual(OWNER.rebuild(self.release, **options)["rebuilt"], ["payload/example"])
            self.assertEqual(calls, ["payload/example"])
            # Original-input drift invalidates cached transformation outputs.
            options["input_sha256"] = "e" * 64
            self.assertEqual(len(OWNER.rebuild(self.release, **options)["rebuilt"]), 2)

    def test_update_requires_retained_key_then_delegates_existing_signer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = {"key_directory": str(root / "keys")}
            owner = Mock()
            with self.assertRaisesRegex(ValueError, "key lost"):
                OWNER.sign_release(owner, self.release, request, root / "signed", **self.context)
            owner.sign.assert_not_called()
            (root / "keys").mkdir()
            for name in ("owner.p12", "password"):
                (root / "keys" / name).write_text("retained fixture")
            OWNER.sign_release(owner, self.release, request, root / "signed", **self.context)
            owner.sign.assert_called_once()

    def test_signed_bytes_are_independent_of_dictionary_order(self):
        reordered = dict(reversed(list(self.release.items())))
        self.assertEqual(OWNER.signed_bytes(self.release), OWNER.signed_bytes(reordered))

    def test_identity_version_and_minimum_installer(self):
        for field, value in (("application_id", "other.package"), ("version_code", 1), ("version_code", 2100000001), ("minimum_installer_version", 2)):
            release = copy.deepcopy(self.release)
            release[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                OWNER.validate(release, **self.context)
