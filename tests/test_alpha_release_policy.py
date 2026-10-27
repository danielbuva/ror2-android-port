"""Authored metadata/byte witnesses only: no real APK, key, game or device."""

import copy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
import zipfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


A = load("tested_alpha_policy", ROOT / "tools/phone-build/owner-apk/alpha_policy.py")
U = load("tested_alpha_updates", ROOT / "tools/phone-build/owner-apk/updates.py")
M = load("alpha_manifest_fixtures", ROOT / "tests/test_owner_binary_manifest.py")


class IssuedVersionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binding = {"source_sha256": "a" * 64, "input_sha256": "b" * 64, "toolchain_sha256": "c" * 64, "publisher_version_code": 50, "purpose": "update"}

    def reserve(self, installed=0, **binding):
        return A.reserve(self.root, installed_version=installed, binding=dict(self.binding, **binding))

    def test_same_frozen_source_and_failed_cancelled_attempts_never_reuse(self):
        self.assertEqual(self.reserve(), 1)
        # No bind: a failed/cancelled/process-killed attempt is still burned.
        self.assertEqual(self.reserve(), 2)
        self.assertEqual(self.reserve(12), 13)
        self.assertEqual(self.reserve(12, publisher_version_code=1, purpose="rollback"), 14)
        self.assertEqual(json.loads((self.root / "issued-versions.json").read_text())["last_issued"], 14)

    def test_parallel_reservations_have_one_durable_monotonic_high_water(self):
        with ThreadPoolExecutor(max_workers=4) as workers:
            issued = list(workers.map(lambda _: self.reserve(), range(12)))
        self.assertEqual(sorted(issued), list(range(1, 13)))
        state = json.loads((self.root / "issued-versions.json").read_text())
        self.assertEqual(state["last_issued"], 12)
        self.assertEqual(set(state["issues"]), set(map(str, range(1, 13))))

    def test_bind_is_once_only_and_contains_every_output_identity(self):
        number = self.reserve()
        A.bind(self.root, number, apk_sha256="d" * 64, payload_sha256="e" * 64, signer_sha256="f" * 64)
        row = json.loads((self.root / "issued-versions.json").read_text())["issues"][str(number)]
        self.assertEqual(row, dict(self.binding, status="signed", apk_sha256="d" * 64, payload_sha256="e" * 64, signer_sha256="f" * 64))
        with self.assertRaisesRegex(ValueError, "cannot be reused"):
            A.bind(self.root, number, apk_sha256="d" * 64, payload_sha256="e" * 64, signer_sha256="f" * 64)

    def test_installed_code_cannot_replace_lost_issued_ledger(self):
        with self.assertRaisesRegex(ValueError, "ledger lost"):
            self.reserve(1)
        self.assertFalse((self.root / "issued-versions.json").exists())

    def test_exhaustion_never_changes_receipt(self):
        self.reserve()
        self.assertEqual(self.reserve(A.MAX_VERSION_CODE - 1), A.MAX_VERSION_CODE)
        before = (self.root / "issued-versions.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "2100000000"):
            self.reserve()
        self.assertEqual((self.root / "issued-versions.json").read_bytes(), before)

    def test_refuses_invalid_codes_and_redirected_or_corrupt_ledger(self):
        for value in (True, -1, 2100000001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.reserve(value)
        destination = self.root / "unrelated"
        destination.write_text("private witness")
        (self.root / "issued-versions.json").symlink_to(destination)
        with self.assertRaisesRegex(ValueError, "redirected"):
            self.reserve()
        self.assertEqual(destination.read_text(), "private witness")
        (self.root / "issued-versions.json").unlink()
        (self.root / "issued-versions.json").write_text("{")
        with self.assertRaises(ValueError):
            self.reserve()

    def test_final_alpha_identity_and_publisher_order_are_separate(self):
        release = {
            "version": "older-source",
            "version_code": 2,
            "application_id": A.APPLICATION_ID,
            "minimum_installer_version": 3,
            "bundle_sha256": "a" * 64,
            "entries": {"payload/witness": {"recipe_sha256": "b" * 64, "producer_sha256": "c" * 64}},
            "data_schema": {"writes": 1, "reads": [1]},
        }
        request = {"application_id": A.APPLICATION_ID, "installed_version": 101, "installed_release_version": 1, "installer_version": 3}
        U.verify_context(release, request, require_new=True)
        with self.assertRaises(ValueError):
            U.verify_context(release, {k: v for k, v in request.items() if k != "installed_release_version"})
        with self.assertRaisesRegex(ValueError, "publisher release rollback"):
            U.verify_context(release, dict(request, installed_release_version=3))
        with self.assertRaisesRegex(ValueError, "final alpha"):
            U.verify_context(dict(release, application_id="dev.ror2lab.arm64"), dict(request, application_id="dev.ror2lab.arm64"))
        with self.assertRaisesRegex(ValueError, "schema"):
            U.verify_context({k: v for k, v in release.items() if k != "data_schema"}, request)
        with self.assertRaisesRegex(ValueError, "migration"):
            U.verify_context(dict(release, data_schema={"writes": 2, "reads": [1, 2]}), request)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.inputs = Path(self.temporary.name)

    def receipt(self, name, version):
        path = self.inputs / "work/releases" / name / "signing/signed.apk"
        path.parent.mkdir(parents=True)
        # A plain authored text witness, deliberately not an Android artifact.
        path.write_text("authored retained reference " + name)
        return {
            "application_id": A.APPLICATION_ID,
            "installed_readback_verified": True,
            "version_code": version,
            "signer_sha256": "c" * 64,
            "apk": str(path),
            "sha256": U.RELEASE.digest(path),
            "bytes": path.stat().st_size,
            "release": {"application_id": A.APPLICATION_ID, "data_schema": {"writes": 1, "reads": [1]}},
        }

    def test_same_key_compatible_rollback_references_source_without_copy(self):
        current, previous = self.receipt("build-current", 12), self.receipt("build-previous", 10)
        before = {p: p.read_bytes() for p in self.inputs.rglob("signed.apk")}
        self.assertEqual(A.rollback(self.inputs, current, previous, 12), Path(previous["apk"]))
        self.assertEqual({p: p.read_bytes() for p in self.inputs.rglob("signed.apk")}, before)
        for kind in ("signer", "schema", "drift", "installed"):
            old = copy.deepcopy(previous)
            actual = 12
            if kind == "signer":
                old["signer_sha256"] = "d" * 64
            elif kind == "schema":
                old["release"]["data_schema"] = {"writes": 2, "reads": [2]}
            elif kind == "drift":
                old["sha256"] = "f" * 64
            else:
                actual = 13
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                A.rollback(self.inputs, current, old, actual)

    def test_pruning_keeps_two_installed_slots_and_one_active_not_game_data(self):
        rows = [self.receipt("build-" + name, index + 1) for index, name in enumerate(("old", "previous", "current", "pending"))]
        for filename, row in zip(("previous-installed-release.json", "installed-release.json", "owner-apk-ready.json"), rows[1:]):
            U.write_json(self.inputs / filename, row)
        unrelated = self.inputs / "work/game-data/profile"
        unrelated.parent.mkdir()
        unrelated.write_text("untouched")
        U.prune_releases(self.inputs)
        self.assertFalse(Path(rows[0]["apk"]).exists())
        self.assertTrue(all(Path(row["apk"]).exists() for row in rows[1:]))
        self.assertEqual(unrelated.read_text(), "untouched")

    def test_reversion_preserves_manifest_except_literal_version(self):
        for utf8 in (True, False):
            data = M.PATCH.patch(M.authored_manifest(utf8=utf8), M.WIRE, version_code=5, application_id=A.APPLICATION_ID)
            changed = M.PATCH.reversion(data, M.WIRE, version_code=101)
            self.assertEqual(len(data), len(changed))
            self.assertLessEqual(sum(a != b for a, b in zip(data, changed)), 4)
            self.assertEqual(M.read(changed)[2][0]["attributes"][(M.PATCH.ANDROID, "versionCode")], 101)
            for code in (5, 4, 0, True, A.MAX_VERSION_CODE + 1):
                with self.subTest(code=code), self.assertRaises(ValueError):
                    M.PATCH.reversion(data, M.WIRE, version_code=code)
            with self.assertRaisesRegex(ValueError, "identity"):
                M.PATCH.reversion(M.authored_manifest(), M.WIRE, version_code=101)

    def test_explicit_rollback_reversions_retained_source_same_signer_higher_code_and_burns_failure(self):
        current, previous = self.receipt("build-current", 12), self.receipt("build-previous", 10)
        for row, publisher in ((current, 2), (previous, 1)):
            row["release"].update(
                version="authored-" + str(publisher),
                version_code=publisher,
                minimum_installer_version=3,
                bundle_sha256="a" * 64,
                entries={"payload/witness": {"recipe_sha256": "b" * 64, "producer_sha256": "c" * 64}},
            )
            row.update(input_sha256="b" * 64, envelope={"release": row["release"], "signature": "mocked boundary"})
            with zipfile.ZipFile(row["apk"], "w") as archive:
                archive.writestr(
                    "AndroidManifest.xml", M.PATCH.patch(M.authored_manifest(), M.WIRE, version_code=row["version_code"], application_id=A.APPLICATION_ID)
                )
                archive.writestr("assets/owner-bootstrap/payload-index.json", '{"authored":true}')
                archive.writestr("assets/witness", "synthetic payload " + str(publisher))
                archive.writestr("META-INF/OWNER.SF", "obsolete authored signature witness")
            row.update(sha256=U.RELEASE.digest(row["apk"]), bytes=Path(row["apk"]).stat().st_size, payload_sha256=U.payload_identity(row["apk"]))
        for filename, row in (("installed-release.json", current), ("previous-installed-release.json", previous)):
            U.write_json(self.inputs / filename, row)
        original = Path(previous["apk"]).read_bytes()
        runtime, native = self.inputs / "runtime", self.inputs / "native"
        runtime.mkdir()
        native.mkdir()
        U.write_json(
            runtime / "release-trust.json",
            {"repository": "example/authored", "application_id": A.APPLICATION_ID, "keys": {"authored": "mocked public boundary"}},
        )
        U.write_json(self.inputs / "update-config.json", {"key_directory": "retained-key"})
        request = self.inputs / "update-request.json"
        U.write_json(
            request,
            {"action": "release-rollback", "application_id": A.APPLICATION_ID, "installed_version": 12, "installed_release_version": 2, "installer_version": 3},
        )
        binding = {"source_sha256": "a" * 64, "input_sha256": "b" * 64, "toolchain_sha256": "c" * 64, "publisher_version_code": 2, "purpose": "update"}
        A.reserve(self.inputs / "work/releases", installed_version=0, binding=binding)
        A.reserve(self.inputs / "work/releases", installed_version=12, binding=binding)  # Failed code 13 remains burned.
        signer = ["c" * 64]

        def sign(owner, release, signing, output, **context):
            self.assertEqual(context["installed_version"], 12)
            self.assertGreater(context["install_version_code"], 13)
            self.assertEqual(release["version_code"], 1)
            output.mkdir()
            target = output / "signed.apk"
            shutil.copyfile(signing["unsigned"], target)
            return {"apk_sha256": U.RELEASE.digest(target), "apk_bytes": target.stat().st_size, "signer_sha256": signer[0]}

        exists = Path.is_file

        def key_presence(path):
            return True if path in {self.inputs / "retained-key/owner.p12", self.inputs / "retained-key/password"} else exists(path)

        with (
            patch.object(Path, "is_file", key_presence),
            patch.object(U.public(), "verify_envelope", return_value=previous["release"]),
            patch.object(U, "toolchain_identity", return_value="e" * 64),
            patch.object(U.RELEASE, "sign_release", side_effect=sign),
            patch.object(U.shutil, "disk_usage", return_value=SimpleNamespace(free=10 * 1024**3)),
        ):
            U.run(request, runtime, native)
            ready = json.loads((self.inputs / "owner-apk-ready.json").read_text())
            self.assertEqual((ready["version_code"], ready["release"]["version_code"]), (14, 1))
            self.assertEqual(ready["payload_sha256"], previous["payload_sha256"])
            with zipfile.ZipFile(ready["apk"]) as archive:
                self.assertEqual(M.read(archive.read("AndroidManifest.xml"))[2][0]["attributes"][(M.PATCH.ANDROID, "versionCode")], 14)
                self.assertEqual(archive.read("assets/witness"), b"synthetic payload 1")
                self.assertNotIn("META-INF/OWNER.SF", archive.namelist())
            self.assertEqual(Path(previous["apk"]).read_bytes(), original)
            self.assertFalse(list(self.inputs.rglob("rollback-unsigned.apk")))
            signer[0] = "f" * 64
            with self.assertRaisesRegex(ValueError, "signer differs"):
                U.run(request, runtime, native)
            self.assertFalse((self.inputs / "owner-apk-ready.json").exists())
        ledger = json.loads((self.inputs / "work/releases/issued-versions.json").read_text())
        self.assertEqual(ledger["last_issued"], 15)
        self.assertEqual(ledger["issues"]["14"]["status"], "signed")
        self.assertEqual(ledger["issues"]["15"]["status"], "reserved")
        self.assertEqual(json.loads((self.inputs / "installed-release.json").read_text())["version_code"], 12)
        self.assertEqual(Path(previous["apk"]).read_bytes(), original)

    def test_rollback_space_failure_keeps_original_and_creates_no_output(self):
        owner = load("alpha_existing_apk_owner", ROOT / "tools/phone-build/owner-apk/build_owner_apk.py")
        receipt = self.receipt("build-witness", 1)
        output = self.inputs / "rollback.zip"
        with patch.object(owner.shutil, "disk_usage", return_value=type("Space", (), {"free": 0})()):
            with self.assertRaisesRegex(ValueError, "insufficient space"):
                owner.reversion(Path(receipt["apk"]), output, wire_helper=ROOT / "scripts/lab/phone_apk.py", version_code=2, expected_sha256=receipt["sha256"])
        self.assertTrue(Path(receipt["apk"]).exists())
        self.assertFalse(output.exists())
