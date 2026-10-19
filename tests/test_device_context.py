import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lab"))
import device_context
from device_context import (
    ACTIVATION_MARKER,
    DeviceContextError,
    device_state_paths,
    migrate_legacy_receipts,
    plan_legacy_receipt_migration,
    receipt_directory,
    select_device,
    storage_policy,
)

DEFAULT_SERIAL = "synthetic-nova"
FUTURE_SERIAL = "synthetic-nova-internal"
THOR_SERIAL = "synthetic-thor"
OTHER_SERIAL = "synthetic-other"


class DeviceContextTests(unittest.TestCase):
    def setUp(self):
        prior_selectors = device_context._COMMAND_SELECTORS
        self.addCleanup(setattr, device_context, "_COMMAND_SELECTORS", prior_selectors)
        self.config = {
            "device_serial": DEFAULT_SERIAL,
            "device_serials": [DEFAULT_SERIAL, FUTURE_SERIAL, THOR_SERIAL],
            "device_settings": {
                DEFAULT_SERIAL: {"storage_mode": "adopted"},
                FUTURE_SERIAL: {"storage_mode": "internal"},
                THOR_SERIAL: {"storage_mode": "internal"},
            },
        }
        self.attached = [
            {"serial": DEFAULT_SERIAL, "state": "device"},
            {"serial": THOR_SERIAL, "state": "device"},
        ]

    def test_command_selectors_freeze_cli_and_environment_values(self):
        with patch.object(device_context, "_COMMAND_SELECTORS", None):
            with patch.dict("os.environ", {"LAB_DEVICE": "from-env"}, clear=False):
                self.assertEqual(device_context.command_selectors(), (None, "from-env"))
                self.assertEqual(device_context.set_command_selector("from-cli", "captured-env"), ("from-cli", "captured-env"))
            with patch.dict("os.environ", {"LAB_DEVICE": "changed-env"}, clear=False):
                self.assertEqual(device_context.command_selectors(), ("from-cli", "captured-env"))

    def test_multiple_attached_devices_require_explicit_selector(self):
        with self.assertRaisesRegex(DeviceContextError, "Multiple attached devices"):
            select_device(self.config, self.attached)
        self.assertEqual(select_device(self.config, self.attached, cli_selector=DEFAULT_SERIAL), DEFAULT_SERIAL)

    def test_single_attached_default_remains_compatible_without_allowlist(self):
        config = {"device_serial": DEFAULT_SERIAL}
        self.assertEqual(select_device(config, [{"serial": DEFAULT_SERIAL, "state": "device"}]), DEFAULT_SERIAL)
        with self.assertRaisesRegex(DeviceContextError, "allowlist"):
            select_device(config, [{"serial": DEFAULT_SERIAL, "state": "device"}], cli_selector=DEFAULT_SERIAL)

    def test_allowlist_is_validated_and_contains_default(self):
        for allowlist in [DEFAULT_SERIAL, [DEFAULT_SERIAL, "../bad"], [DEFAULT_SERIAL, DEFAULT_SERIAL], ["other"]]:
            with self.subTest(allowlist=allowlist), self.assertRaises(DeviceContextError):
                select_device(dict(self.config, device_serials=allowlist), self.attached, cli_selector=DEFAULT_SERIAL)

    def test_explicit_environment_or_cli_selector_uses_only_allowlisted_device(self):
        self.assertEqual(select_device(self.config, self.attached, env_selector=THOR_SERIAL), THOR_SERIAL)
        self.assertEqual(select_device(self.config, self.attached, cli_selector=THOR_SERIAL), THOR_SERIAL)
        with self.assertRaisesRegex(DeviceContextError, "allowlist"):
            select_device(self.config, self.attached, cli_selector="unknown")

    def test_conflicting_selectors_are_rejected(self):
        with self.assertRaisesRegex(DeviceContextError, "different devices"):
            select_device(self.config, self.attached, env_selector=DEFAULT_SERIAL, cli_selector=THOR_SERIAL)

    def test_missing_or_unauthorized_selected_device_never_falls_back(self):
        with self.assertRaisesRegex(DeviceContextError, "attached and authorized"):
            select_device(self.config, [{"serial": THOR_SERIAL, "state": "device"}])
        with self.assertRaisesRegex(DeviceContextError, "attached and authorized"):
            select_device(self.config, [{"serial": DEFAULT_SERIAL, "state": "unauthorized"}])

    def test_unsafe_serial_cannot_be_used_as_a_path_segment(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(DeviceContextError, "safe path segment"):
                device_state_paths(temp, "../../outside")

    def test_each_device_has_a_separate_receipt_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            nova = device_state_paths(temp, DEFAULT_SERIAL)
            thor = device_state_paths(temp, THOR_SERIAL)
            self.assertEqual(nova["installed"], Path(temp) / "device" / DEFAULT_SERIAL / "installed.json")
            self.assertEqual(thor["installed"], Path(temp) / "device" / THOR_SERIAL / "installed.json")
            self.assertNotEqual(nova["installed"], thor["installed"])

    def test_receipt_directory_preserves_default_legacy_state_until_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            scoped = legacy / DEFAULT_SERIAL
            self.assertEqual(receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL}), legacy)
            self.assertEqual(receipt_directory(temp, {"serial": THOR_SERIAL, "default_serial": DEFAULT_SERIAL}), legacy / THOR_SERIAL)
            scoped.mkdir(parents=True)
            self.assertEqual(receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL}), legacy)
            (scoped / ACTIVATION_MARKER).write_text("{}\n")
            with self.assertRaisesRegex(DeviceContextError, "activation marker is invalid"):
                receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL})

    def test_storage_policy_is_explicit_per_device(self):
        self.assertEqual(storage_policy(self.config, DEFAULT_SERIAL), "adopted")
        self.assertEqual(storage_policy(self.config, FUTURE_SERIAL), "internal")
        self.assertEqual(storage_policy(self.config, THOR_SERIAL), "internal")
        with self.assertRaisesRegex(DeviceContextError, "explicit"):
            storage_policy({"storage_mode": "adopted"}, THOR_SERIAL)

    def test_legacy_migration_requires_proof_and_matching_identity(self):
        receipt = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/example",
            "apk_sha256": "a" * 64,
        }
        proof = dict(receipt)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "installed.json"
            target = Path(temp) / "device/nova-current/installed.json"
            lock = Path(temp) / "coordination.lock"
            source.write_text("original receipt")
            with self.assertRaisesRegex(DeviceContextError, "ownership proof"):
                plan_legacy_receipt_migration(source, target, serial=DEFAULT_SERIAL, receipt=receipt, ownership_proof=None, coordination_lock=lock)
            mismatched = dict(receipt, serial=OTHER_SERIAL)
            with self.assertRaisesRegex(DeviceContextError, "does not match"):
                plan_legacy_receipt_migration(source, target, serial=DEFAULT_SERIAL, receipt=mismatched, ownership_proof=proof, coordination_lock=lock)

            lock.write_text("locked")
            with self.assertRaisesRegex(DeviceContextError, "coordination lock"):
                plan_legacy_receipt_migration(source, target, serial=DEFAULT_SERIAL, receipt=receipt, ownership_proof=proof, coordination_lock=lock)
            lock.unlink()
            plan = plan_legacy_receipt_migration(source, target, serial=DEFAULT_SERIAL, receipt=receipt, ownership_proof=proof, coordination_lock=lock)
            self.assertEqual(plan["temporary_target"], target.with_name("installed.json.migration-tmp"))
            self.assertTrue(plan["preserve_source"])
            self.assertIn("target does not already exist", plan["preconditions"])
            self.assertEqual(source.read_text(), "original receipt")
            self.assertFalse(target.exists())
            self.assertFalse(plan["temporary_target"].exists())

    def test_transactional_migration_copies_receipts_and_activates_last(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "b" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            scoped = legacy / DEFAULT_SERIAL
            legacy.mkdir()
            originals = {
                "installed.json": identity,
                "storage.json": {"serial": DEFAULT_SERIAL, "mode": "adopted"},
                "runtime.json": {"persistentDataPath": "/private/path"},
                "last-run.json": {"checkpoint": True},
                "sync.json": {"files": []},
                "diagnostics.json": {"enabled": False},
            }
            original_bytes = {}
            for name, value in originals.items():
                content = (json.dumps(value, sort_keys=True) + "\n").encode()
                (legacy / name).write_bytes(content)
                original_bytes[name] = content
            counter_path = Path(temp) / "device-install-limits/synthetic.json"
            counter_path.parent.mkdir()
            counter_bytes = (json.dumps(dict(serial=DEFAULT_SERIAL, dispatched=1)) + "\n").encode()
            counter_path.write_bytes(counter_bytes)
            lock = Path(temp) / "coordination.lock"
            calls = []
            real_replace = device_context.os.replace

            def record_replace(source, destination):
                calls.append((Path(source), Path(destination)))
                return real_replace(source, destination)

            with patch("device_context.os.replace", side_effect=record_replace):
                result = migrate_legacy_receipts(
                    legacy,
                    scoped,
                    serial=DEFAULT_SERIAL,
                    ownership_proof=identity,
                    coordination_lock=lock,
                    install_counter=counter_path,
                )

            self.assertTrue(result["source_preserved"])
            self.assertEqual(set(result["copied"]), set(originals) | {"device-install-limit.json"})
            self.assertEqual(calls[-1][1], scoped / ACTIVATION_MARKER)
            self.assertTrue((scoped / ACTIVATION_MARKER).is_file())
            self.assertEqual(receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL}), scoped)
            for name, content in original_bytes.items():
                self.assertEqual((legacy / name).read_bytes(), content)
                self.assertEqual((scoped / name).read_bytes(), content)
            self.assertEqual((scoped / "device-install-limit.json").read_bytes(), counter_bytes)
            self.assertEqual(counter_path.read_bytes(), counter_bytes)

            (scoped / "runtime.json").write_text('{"persistentDataPath":"new runtime path"}\n')
            (scoped / "storage.json").write_text(json.dumps(dict(serial=DEFAULT_SERIAL, mode="internal")) + "\n")
            (scoped / "installed.json").write_text(json.dumps(dict(serial=DEFAULT_SERIAL, package="dev.ror2lab.arm64")) + "\n")
            self.assertEqual(receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL}), scoped)
            (scoped / "installed.json").unlink()
            self.assertEqual(receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL}), scoped)

    def test_tampered_activation_marker_refuses_instead_of_falling_back(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "3" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            legacy.mkdir()
            (legacy / "installed.json").write_text(json.dumps(identity))
            scoped = legacy / DEFAULT_SERIAL
            migrate_legacy_receipts(
                legacy,
                scoped,
                serial=DEFAULT_SERIAL,
                ownership_proof=identity,
                coordination_lock=Path(temp) / "lock",
            )
            marker = scoped / ACTIVATION_MARKER
            value = json.loads(marker.read_text())
            value["serial"] = OTHER_SERIAL
            marker.write_text(json.dumps(value))
            with self.assertRaisesRegex(DeviceContextError, "activation marker is invalid"):
                receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL})

    def test_migration_refuses_serial_mismatch_and_conflicting_target(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "c" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            legacy.mkdir()
            (legacy / "installed.json").write_text(json.dumps(identity))
            (legacy / "storage.json").write_text(json.dumps(dict(serial=OTHER_SERIAL)))
            scoped = legacy / DEFAULT_SERIAL
            kwargs = dict(serial=DEFAULT_SERIAL, ownership_proof=identity, coordination_lock=Path(temp) / "lock")
            with self.assertRaisesRegex(DeviceContextError, "serial does not match"):
                migrate_legacy_receipts(legacy, scoped, **kwargs)
            (legacy / "storage.json").write_text(json.dumps(dict(serial=DEFAULT_SERIAL)))
            scoped.mkdir()
            with self.assertRaisesRegex(DeviceContextError, "already exists"):
                migrate_legacy_receipts(legacy, scoped, **kwargs)

    def test_migration_refuses_lock_before_copying(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            legacy.mkdir()
            (legacy / "installed.json").write_text(json.dumps(identity))
            lock = Path(temp) / "lock"
            lock.write_text("active")
            scoped = legacy / DEFAULT_SERIAL
            with self.assertRaisesRegex(DeviceContextError, "coordination lock"):
                migrate_legacy_receipts(legacy, scoped, serial=DEFAULT_SERIAL, ownership_proof=identity, coordination_lock=lock)
            self.assertFalse(scoped.exists())

    def test_source_drift_during_staging_aborts_before_target_publish(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "e" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            legacy.mkdir()
            (legacy / "installed.json").write_text(json.dumps(identity))
            source = legacy / "runtime.json"
            source.write_text('{"persistentDataPath":"original"}\n')
            original_write = device_context._write_fsynced_new
            mutated = False

            def mutate_after_copy(path, data):
                nonlocal mutated
                original_write(path, data)
                if path.name == "runtime.json" and not mutated:
                    source.write_text('{"persistentDataPath":"drifted"}\n')
                    mutated = True

            scoped = legacy / DEFAULT_SERIAL
            with patch("device_context._write_fsynced_new", side_effect=mutate_after_copy):
                with self.assertRaisesRegex(DeviceContextError, "source changed"):
                    migrate_legacy_receipts(
                        legacy,
                        scoped,
                        serial=DEFAULT_SERIAL,
                        ownership_proof=identity,
                        coordination_lock=Path(temp) / "lock",
                    )
            self.assertFalse(scoped.exists())
            self.assertFalse(scoped.with_name(scoped.name + ".migration-tmp").exists())
            self.assertFalse((scoped / ACTIVATION_MARKER).exists())

    def test_lock_appearing_before_target_publish_aborts(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "f" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            legacy.mkdir()
            (legacy / "installed.json").write_text(json.dumps(identity))
            lock = Path(temp) / "lock"
            original_verify = device_context._verify_snapshot

            def create_lock(snapshot):
                original_verify(snapshot)
                lock.write_text("appeared")

            scoped = legacy / DEFAULT_SERIAL
            with patch("device_context._verify_snapshot", side_effect=create_lock):
                with self.assertRaisesRegex(DeviceContextError, "coordination lock"):
                    migrate_legacy_receipts(legacy, scoped, serial=DEFAULT_SERIAL, ownership_proof=identity, coordination_lock=lock)
            self.assertFalse(scoped.exists())
            self.assertFalse(scoped.with_name(scoped.name + ".migration-tmp").exists())

    def test_lock_appearing_after_target_publish_leaves_inactive_conflict(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "1" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            legacy.mkdir()
            installed = (json.dumps(identity) + "\n").encode()
            (legacy / "installed.json").write_bytes(installed)
            lock = Path(temp) / "lock"
            original_verify = device_context._verify_snapshot
            verifications = 0

            def create_lock_before_marker(snapshot):
                nonlocal verifications
                original_verify(snapshot)
                verifications += 1
                if verifications == 2:
                    lock.write_text("appeared")

            scoped = legacy / DEFAULT_SERIAL
            with patch("device_context._verify_snapshot", side_effect=create_lock_before_marker):
                with self.assertRaisesRegex(DeviceContextError, "coordination lock"):
                    migrate_legacy_receipts(legacy, scoped, serial=DEFAULT_SERIAL, ownership_proof=identity, coordination_lock=lock)
            self.assertTrue(scoped.is_dir())
            self.assertFalse((scoped / ACTIVATION_MARKER).exists())
            self.assertEqual((legacy / "installed.json").read_bytes(), installed)
            self.assertEqual(receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL}), legacy)
            with self.assertRaisesRegex(DeviceContextError, "already exists"):
                migrate_legacy_receipts(legacy, scoped, serial=DEFAULT_SERIAL, ownership_proof=identity, coordination_lock=Path(temp) / "clear-lock")

    def test_marker_publish_failure_leaves_target_inactive_and_source_intact(self):
        identity = {
            "serial": DEFAULT_SERIAL,
            "package": "dev.ror2lab.arm64",
            "package_path": "/data/app/lab",
            "apk_sha256": "2" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / "device"
            legacy.mkdir()
            installed = (json.dumps(identity) + "\n").encode()
            (legacy / "installed.json").write_bytes(installed)
            scoped = legacy / DEFAULT_SERIAL
            real_replace = device_context.os.replace

            def fail_marker(source, destination):
                if Path(destination).name == ACTIVATION_MARKER:
                    raise OSError("injected marker publish failure")
                return real_replace(source, destination)

            with patch("device_context.os.replace", side_effect=fail_marker):
                with self.assertRaisesRegex(OSError, "injected marker"):
                    migrate_legacy_receipts(
                        legacy,
                        scoped,
                        serial=DEFAULT_SERIAL,
                        ownership_proof=identity,
                        coordination_lock=Path(temp) / "lock",
                    )
            self.assertTrue(scoped.is_dir())
            self.assertFalse((scoped / ACTIVATION_MARKER).exists())
            self.assertEqual((legacy / "installed.json").read_bytes(), installed)
            self.assertEqual(receipt_directory(temp, {"serial": DEFAULT_SERIAL, "default_serial": DEFAULT_SERIAL}), legacy)
            with self.assertRaisesRegex(DeviceContextError, "already exists"):
                migrate_legacy_receipts(
                    legacy,
                    scoped,
                    serial=DEFAULT_SERIAL,
                    ownership_proof=identity,
                    coordination_lock=Path(temp) / "lock",
                )


if __name__ == "__main__":
    unittest.main()
