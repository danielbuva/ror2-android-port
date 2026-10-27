"""Synthetic local import/public-plan binding; no game inputs or key generation."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tested_install_inputs", ROOT / "tools/phone-build/owner-apk/install_inputs.py")
INPUTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INPUTS)
OWNER = INPUTS.module("tested_source_profile_owner", ROOT / "tools/phone-build/owner-apk/build_owner_apk.py")


class InstallInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo, self.inputs = self.root / "repo", self.root / "private"
        self.repo.mkdir()
        self.inputs.mkdir()
        self.manifest = {
            "schema": 1,
            "game_version": "synthetic-v1",
            "files": [{"path": "Data/example.txt", "bytes": 7, "sha256": hashlib.sha256(b"example").hexdigest()}],
        }
        manifest_path = self.repo / "recipe/inputs.json"
        manifest_path.parent.mkdir()
        manifest_path.write_text(json.dumps(self.manifest))
        self.plan = {
            "schema": 1,
            "required_inputs": "recipe/inputs.json",
            "workspace_bytes": 1234,
            "configuration": {"bindings": {"game": ".", "data": "Data"}},
            "stages": [{"id": name, "title": name, "jobs": []} for name in INPUTS.STAGES],
        }
        self.index = {"files": {"recipe/inputs.json": INPUTS.UPDATES.RELEASE.digest(manifest_path)}, "install_plan": self.plan}

    def import_fixture(self):
        path = self.inputs / "import/files/Data/example.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"example")
        return path

    def test_description_and_private_config_are_derived_from_verified_recipe(self):
        self.import_fixture()
        description = INPUTS.describe(self.index, self.repo, self.inputs)
        self.assertEqual(description["manifest"], self.manifest)
        self.assertEqual(description["import_root"], "import")
        self.assertEqual(description["workspace_bytes"], 1234)
        config = INPUTS.prepare(self.index, self.repo, self.inputs)
        self.assertEqual(config["bindings"], {"game": "import/files", "data": "import/files/Data"})
        self.assertEqual(config["key_directory"], "signing/owner")
        self.assertEqual(json.loads((self.inputs / "input-hashes.json").read_text()), {"import/files/Data/example.txt": self.manifest["files"][0]["sha256"]})
        self.assertFalse((self.inputs / "signing").exists())

    def test_source_drift_and_changed_import_refused_even_with_receipt(self):
        imported = self.import_fixture()
        INPUTS.prepare(self.index, self.repo, self.inputs)
        imported.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Found version: unknown.*Supported versions: synthetic-v1"):
            INPUTS.prepare(self.index, self.repo, self.inputs)
        imported.write_bytes(b"example")
        (self.repo / "recipe/inputs.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "source changed"):
            INPUTS.describe(self.index, self.repo, self.inputs)

    def test_stale_extra_private_files_never_reach_root_bindings(self):
        self.import_fixture()
        (self.inputs / "import/files/stale.txt").write_text("old synthetic release")
        with self.assertRaisesRegex(ValueError, "another selection"):
            INPUTS.prepare(self.index, self.repo, self.inputs)
        self.assertFalse((self.inputs / "input-hashes.json").exists())

    def test_binding_cannot_select_private_tool_or_key_directory(self):
        self.import_fixture()
        self.plan["configuration"]["bindings"]["escape"] = "../../signing"
        with self.assertRaises(ValueError):
            INPUTS.prepare(self.index, self.repo, self.inputs)
        self.plan["configuration"]["bindings"]["escape"] = "Unselected"
        with self.assertRaisesRegex(ValueError, "admitted original"):
            INPUTS.prepare(self.index, self.repo, self.inputs)

    def test_invalid_stage_and_workspace_schema_refused(self):
        for change in (
            lambda p: p.update(workspace_bytes=True),
            lambda p: p["stages"].reverse(),
            lambda p: p["configuration"].update(key_directory="attacker"),
            lambda p: p["stages"][0].update(jobs=["recipe/inputs.json"]),
        ):
            value = copy.deepcopy(self.plan)
            change(value)
            with self.assertRaises(ValueError):
                INPUTS.validate_plan(value, self.index["files"])

    def test_source_receipt_pins_actual_cache_only_and_never_uses_packet(self):
        outputs = {}
        for name in ("apk/example.txt", "payload/example.txt"):
            path = self.inputs / "work/releases/cache" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic output")
            outputs[name] = path
        release = {"entries": {name: {} for name in outputs}}
        path, digest = INPUTS.assembly_profile(outputs, self.inputs, release)
        self.assertEqual(digest, INPUTS.UPDATES.RELEASE.digest(path))
        value = json.loads(path.read_text())
        self.assertEqual(value["schema"], "owner-source-output-v1")
        self.assertNotIn("sources", value)
        self.assertTrue(all(set(row) == {"path", "bytes", "sha256"} for row in value["targets"]))
        outputs["apk/example.txt"] = self.repo / "recipe/inputs.json"
        with self.assertRaises(ValueError):
            INPUTS.assembly_profile(outputs, self.inputs, release)

    def test_source_payload_requires_existing_android_bootstrap_shape_and_bounds(self):
        OWNER.validate_source_payload(["payload/example.bundle"], {"payload/example.bundle": 10})
        for names, sizes in (
            ([], {}),
            (["payload/sub/file"], None),
            (["payload/" + str(i) for i in range(513)], None),
            (["payload/example"], {"payload/example": 2 * 1024**3}),
            (["payload/a", "payload/b", "payload/c"], {"payload/" + n: 2 * 1024**3 - 1 for n in "abc"}),
        ):
            with self.assertRaises(ValueError):
                OWNER.validate_source_payload(names, sizes)

    def test_first_install_creates_nested_private_signing_directory_before_key_boundary(self):
        request = {}
        for name in ("unsigned", "java", "zipalign", "apksigner_jar"):
            path = self.root / (name + ".synthetic")
            path.write_bytes(b"synthetic placeholder; not executable")
            request[name] = str(path)
        keys = self.inputs / "signing/owner"
        request["key_directory"] = str(keys)
        request_path = self.root / "sign-request.json"
        request_path.write_text(json.dumps(request))
        with (
            patch.object(OWNER.secrets, "token_urlsafe", side_effect=RuntimeError("synthetic stop before credential generation")),
            patch.object(OWNER.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
                OWNER.sign(request_path, self.root / "signed-output")
            run.assert_not_called()
        self.assertTrue(keys.is_dir())
        self.assertEqual(keys.stat().st_mode & 0o777, 0o700)
        self.assertFalse((keys / "owner.p12").exists())

    def test_source_assembler_requires_complete_cohort_and_rechecks_each_hash(self):
        sdk = INPUTS.module("synthetic_sdk_contract", ROOT / "tools/phone-build/accepted-output/sdk_package.py")
        names = OWNER.CODE_ENTRIES | sdk.SDK_ENTRIES
        outputs = {}
        for name in names | {"assets/synthetic.txt"}:
            key = "apk/" + name
            path = self.inputs / "work/releases/cache" / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic " + name.encode())
            outputs[key] = path
        payload = self.inputs / "work/releases/cache/payload/synthetic.bundle"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"authored synthetic payload fixture")
        outputs["payload/synthetic.bundle"] = payload
        manifest, digest = INPUTS.assembly_profile(outputs, self.inputs, {"entries": {name: {} for name in outputs}})
        request = {
            "manifest": str(manifest),
            "manifest_sha256": digest,
            "targets": str(self.inputs / "work/releases/cache"),
            "code": {name: str(outputs["apk/" + name]) for name in names},
        }
        with patch.object(OWNER.PACKET, "profile", side_effect=AssertionError("private packet must not be read")):
            self.assertTrue(OWNER.check(request)["assembly_ready"])
            outputs["apk/" + sorted(names)[0]].write_bytes(b"changed")
            self.assertFalse(OWNER.check(request)["assembly_ready"])
        request["code"].pop(sorted(names)[0])
        with self.assertRaises(ValueError):
            OWNER.check(request)


if __name__ == "__main__":
    unittest.main()
