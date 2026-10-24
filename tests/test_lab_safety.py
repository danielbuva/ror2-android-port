import unittest
import tempfile
import json
import zipfile
import sys
import os
import types
import runpy
import io
import contextlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import device
import device_context
import common
from common import write

REAL_REQUIRE_DEVICE_ACCESS = device.require_device_access
DEFAULT_TEST_SERIAL = "synthetic-default"
SECOND_TEST_SERIAL = "synthetic-secondary"
OTHER_TEST_SERIAL = "synthetic-other"


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patcher = patch.object(device, "WORK", self.root)
        self.patcher.start()
        self.access_patcher = patch.object(device, "require_device_access")
        self.access_patcher.start()
        # These ABI/storage fixtures are ZIP containers, not Android manifests.
        # APK identity rejection is exercised separately with explicit metadata.
        self.identity_patcher = patch.object(device, "validate_apk_identity")
        self.identity_patcher.start()
        self.d = object.__new__(device.Device)
        self.d._work_root = self.root
        self.d.serial = DEFAULT_TEST_SERIAL
        self.d.base = ["must-not-execute-adb"]
        self.d.configuration = dict(device_serial=self.d.serial, device_serials=[self.d.serial], storage_mode="adopted")
        self.d.settings = dict(self.d.configuration)
        self.d.receipt_root = self.root / "device"
        self.d.display_awakened = False
        device.Device._awake_devices.clear()

    def tearDown(self):
        self.identity_patcher.stop()
        self.access_patcher.stop()
        device.Device._awake_devices.clear()
        self.patcher.stop()
        self.temp.cleanup()

    def apk(self, abi="arm64-v8a"):
        p = self.root / "test.apk"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("lib/" + abi + "/libtest.so", b"not executable")
        return p

    def test_existing_unreceipted_package_is_never_modified(self):
        self.d.exists = lambda: True
        with self.assertRaisesRegex(RuntimeError, "ownership receipt"):
            self.d.install(self.apk())

    def test_low_internal_space_blocks_before_install(self):
        self.d.exists = lambda: False
        self.d.storage = lambda: {"internal": {"free_bytes": 128}, "adopted": {"free_bytes": 10**12}}
        self.d.settings["internal_reserve_mib"] = 1024
        with self.assertRaisesRegex(RuntimeError, "Insufficient internal"):
            self.d.install(self.apk())

    def test_wrong_abi_blocks_before_install(self):
        self.d.exists = lambda: False
        self.d.storage = lambda: {}
        with self.assertRaisesRegex(RuntimeError, "only arm64-v8a"):
            self.d.install(self.apk("x86_64"))

    def test_ownership_receipt_bound_to_device_and_placement(self):
        write(self.d.receipt("installed.json"), dict(serial=OTHER_TEST_SERIAL, package=device.PACKAGE, package_path="old"))
        with self.assertRaisesRegex(RuntimeError, "another serial"):
            self.d.owned()

    def test_scoped_receipt_with_another_serial_is_refused(self):
        self.d.serial = SECOND_TEST_SERIAL
        self.d.configuration = {
            "device_serial": DEFAULT_TEST_SERIAL,
            "device_serials": [DEFAULT_TEST_SERIAL, SECOND_TEST_SERIAL],
        }
        self.d.receipt_root = self.root / "device" / self.d.serial
        write(self.d.receipt("installed.json"), dict(serial=OTHER_TEST_SERIAL))
        with self.assertRaisesRegex(RuntimeError, "belongs to another serial"):
            self.d.read_receipt("installed.json")

    def test_receipt_json_symlink_is_rejected_for_read_and_write(self):
        root = self.root / "device"
        root.mkdir()
        outside = self.root / "outside.json"
        outside.write_bytes(b"external sentinel")
        target = root / "installed.json"
        target.symlink_to(outside)

        with self.assertRaisesRegex(RuntimeError, "cannot be a symlink"):
            self.d.read_receipt("installed.json")
        with self.assertRaisesRegex(RuntimeError, "cannot be a symlink"):
            self.d.write_receipt("installed.json", {"package": device.PACKAGE})
        self.assertEqual(outside.read_bytes(), b"external sentinel")

    def test_receipt_root_swapped_to_symlink_after_construction_refuses_write(self):
        # The device instance is constructed with the ordinary legacy path; its
        # later lookup must revalidate that path before any receipt can escape.
        self.d.receipt("installed.json")
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "installed.json"
        sentinel.write_bytes(b"external sentinel")
        (self.root / "device").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            self.d.write_receipt("installed.json", {"package": device.PACKAGE})
        self.assertEqual(sentinel.read_bytes(), b"external sentinel")

    def test_scoped_receipt_root_swapped_after_construction_refuses_write(self):
        self.d.serial = SECOND_TEST_SERIAL
        self.d.configuration = {
            "device_serial": DEFAULT_TEST_SERIAL,
            "device_serials": [DEFAULT_TEST_SERIAL, SECOND_TEST_SERIAL],
        }
        self.d.receipt_root = self.root / "device" / SECOND_TEST_SERIAL
        self.d.receipt("installed.json")
        device_root = self.root / "device"
        device_root.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "installed.json"
        sentinel.write_bytes(b"external scoped sentinel")
        (device_root / SECOND_TEST_SERIAL).symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            self.d.write_receipt("installed.json", {"package": device.PACKAGE})
        self.assertEqual(sentinel.read_bytes(), b"external scoped sentinel")

    def test_evidence_directory_validates_components_without_creating_them(self):
        path = self.d.evidence_directory("bootstrap", "attempt-1")
        self.assertEqual(path, self.root / "device" / "bootstrap" / "attempt-1")
        self.assertFalse(path.exists())
        for components in [("..",), ("nested/name",), ("nested\\name",), ("",)]:
            with self.subTest(components=components), self.assertRaisesRegex(ValueError, "safe names"):
                self.d.evidence_directory(*components)

        self.d.evidence_directory("bootstrap")
        outside = self.root / "outside-bootstrap"
        outside.mkdir()
        sentinel = outside / "sentinel.json"
        sentinel.write_bytes(b"external bootstrap sentinel")
        (self.root / "device").mkdir()
        (self.root / "device" / "bootstrap").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            self.d.evidence_directory("bootstrap", "attempt-1")
        self.assertEqual(sentinel.read_bytes(), b"external bootstrap sentinel")

    def test_settings_and_receipt_roots_are_isolated_between_device_contexts(self):
        configuration = {
            "device_serial": DEFAULT_TEST_SERIAL,
            "device_serials": [DEFAULT_TEST_SERIAL, SECOND_TEST_SERIAL],
            "storage_mode": "adopted",
            "internal_reserve_mib": 2048,
            "sleep_display_when_idle": True,
            "device_settings": {
                SECOND_TEST_SERIAL: {"storage_mode": "internal", "internal_reserve_mib": 3072, "display_count": 2},
            },
        }
        attached = ("List of devices attached\n" + f"{DEFAULT_TEST_SERIAL}\tdevice\n{SECOND_TEST_SERIAL}\tdevice\n").encode()
        write(self.root / "config/local.json", configuration)
        with (
            patch.object(common, "WORK", self.root),
            patch.object(device, "run", return_value=types.SimpleNamespace(stdout=attached)),
            patch.object(device_context, "_COMMAND_SELECTORS", (None, None)),
            patch.dict(os.environ, {}, clear=True),
        ):
            first = device.Device(selector=DEFAULT_TEST_SERIAL, work_root=self.root)
            second = device.Device(selector=SECOND_TEST_SERIAL, work_root=self.root)

        self.assertEqual(first.settings["storage_mode"], "adopted")
        self.assertEqual(first.settings["internal_reserve_mib"], 2048)
        self.assertTrue(first.settings["sleep_display_when_idle"])
        self.assertNotIn("sleep_display_when_idle", second.settings)
        self.assertEqual(second.settings["storage_mode"], "internal")
        self.assertEqual(second.settings["internal_reserve_mib"], 3072)
        self.assertEqual(second.settings["display_count"], 2)
        self.assertNotEqual(first.receipt_root, second.receipt_root)
        self.assertNotEqual(first.install_counter(), second.install_counter())

    def test_device_freezes_config_and_receipt_tree_at_construction(self):
        configuration = {
            "device_serial": DEFAULT_TEST_SERIAL,
            "device_serials": [DEFAULT_TEST_SERIAL],
            "storage_mode": "internal",
        }
        write(self.root / "config/local.json", configuration)
        attached = ("List of devices attached\n" + DEFAULT_TEST_SERIAL + "\tdevice\n").encode()
        elsewhere = self.root / "later-work-tree"
        write(elsewhere / "config/local.json", {**configuration, "device_serial": SECOND_TEST_SERIAL})
        with (
            patch.object(common, "WORK", self.root),
            patch.object(device, "run", return_value=types.SimpleNamespace(stdout=attached)),
            patch.object(device_context, "_COMMAND_SELECTORS", (None, None)),
            patch.dict(os.environ, {}, clear=True),
        ):
            selected = device.Device()

        write(selected.receipt("installed.json"), {"serial": DEFAULT_TEST_SERIAL, "package": device.PACKAGE})
        with patch.object(common, "WORK", elsewhere):
            self.assertEqual(selected.configuration["device_serial"], DEFAULT_TEST_SERIAL)
            self.assertEqual(selected.work_root, self.root)
            self.assertEqual(selected.receipt("installed.json"), self.root / "device/installed.json")
            self.assertEqual(selected.read_receipt("installed.json")["serial"], DEFAULT_TEST_SERIAL)

    def test_relative_work_root_keeps_default_legacy_receipt_and_counter_paths(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            relative_root = Path(temp).name
            write(
                Path(relative_root) / "config/local.json",
                {
                    "device_serial": DEFAULT_TEST_SERIAL,
                    "device_serials": [DEFAULT_TEST_SERIAL],
                    "storage_mode": "internal",
                },
            )
            attached = ("List of devices attached\n" + DEFAULT_TEST_SERIAL + "\tdevice\n").encode()
            with (
                patch.object(common, "WORK", self.root),
                patch.object(device, "run", return_value=types.SimpleNamespace(stdout=attached)),
                patch.object(device_context, "_COMMAND_SELECTORS", (None, None)),
                patch.dict(os.environ, {}, clear=True),
            ):
                selected = device.Device(work_root=relative_root)

            absolute_root = Path(temp).absolute()
            self.assertEqual(selected.work_root, absolute_root)
            self.assertEqual(selected.receipt_root, absolute_root / "device")
            write(selected.receipt("installed.json"), {"package": device.PACKAGE})
            self.assertEqual(selected.read_receipt("installed.json"), {"package": device.PACKAGE})
            self.assertEqual(
                selected.install_counter(),
                absolute_root / "device-install-limits" / (device.digest(DEFAULT_TEST_SERIAL) + ".json"),
            )

            scoped = absolute_root / "device" / DEFAULT_TEST_SERIAL
            scoped.mkdir()
            identity = {
                "serial": DEFAULT_TEST_SERIAL,
                "package": device.PACKAGE,
                "package_path": "/data/app/lab",
                "apk_sha256": "e" * 64,
            }
            marker = {"version": 1, "serial": DEFAULT_TEST_SERIAL, "identity": identity, "sha256": {"installed.json": "f" * 64}}
            marker["marker_sha256"] = device_context._sha256(
                json.dumps({key: marker[key] for key in ("version", "serial", "identity", "sha256")}, sort_keys=True, separators=(",", ":")).encode()
            )
            (scoped / device_context.ACTIVATION_MARKER).write_text(json.dumps(marker))
            with self.assertRaisesRegex(RuntimeError, "receipt root changed"):
                selected.install_counter()

    def test_runtime_path_rejected_before_commands_or_receipt_publish(self):
        calls = []
        self.d.sh = lambda *args, **kwargs: (calls.append(args) or self.fail("Unsafe path reached a device command"))
        unsafe = {"persistentDataPath": "/data/local/tmp/not-the-package"}

        with self.assertRaisesRegex(RuntimeError, "Unexpected runtime"):
            self.d.write_receipt("runtime.json", unsafe)

        self.assertFalse(self.d.receipt("runtime.json").exists())
        self.assertEqual(calls, [])

    def test_internal_backing_mismatch_rejects_receipt_before_remote_write(self):
        self.d.settings["storage_mode"] = "internal"
        self.d.storage = lambda: {
            "mode": "internal",
            "internal": {"total_bytes": 4096},
            "adopted": None,
        }
        calls = []

        def shell(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("df", "-k"):
                return "Filesystem 1K-blocks Used Available Use% Mounted on\ninternal 8 1 7 1% /storage/emulated"
            self.fail("Mismatched runtime backing must reject before remote writes")

        self.d.sh = shell
        runtime = {
            "persistentDataPath": "/storage/emulated/0/Android/data/" + device.PACKAGE + "/files",
        }
        with self.assertRaisesRegex(RuntimeError, "not backed by the selected internal"):
            self.d.write_receipt("runtime.json", runtime)

        self.assertFalse(self.d.receipt("runtime.json").exists())
        self.assertEqual(calls, [("df", "-k", runtime["persistentDataPath"])])

        # Even a stale on-disk snapshot cannot reach mkdir/push when its path
        # resolves to a different backing volume than the selected profile.
        write(self.d.receipt("runtime.json"), runtime)
        self.d.owned = lambda: {}
        with self.assertRaisesRegex(RuntimeError, "not backed by the selected internal"):
            self.d.sync()
        self.assertEqual(
            calls,
            [
                ("df", "-k", runtime["persistentDataPath"]),
                ("df", "-k", runtime["persistentDataPath"]),
            ],
        )

    def test_internal_and_adopted_runtime_snapshots_validate_on_their_own_serials(self):
        configuration = {
            "device_serial": DEFAULT_TEST_SERIAL,
            "device_serials": [DEFAULT_TEST_SERIAL, SECOND_TEST_SERIAL],
            "storage_mode": "internal",
            "device_settings": {SECOND_TEST_SERIAL: {"storage_mode": "adopted"}},
        }
        write(self.root / "config/local.json", configuration)
        attached = ("List of devices attached\n" + DEFAULT_TEST_SERIAL + "\tdevice\n" + SECOND_TEST_SERIAL + "\tdevice\n").encode()
        with (
            patch.object(common, "WORK", self.root),
            patch.object(device, "run", return_value=types.SimpleNamespace(stdout=attached)),
            patch.object(device_context, "_COMMAND_SELECTORS", (None, None)),
            patch.dict(os.environ, {}, clear=True),
        ):
            internal = device.Device(selector=DEFAULT_TEST_SERIAL)
            adopted = device.Device(selector=SECOND_TEST_SERIAL)

        internal_total = 4096 * 1024
        adopted_total = 8192 * 1024
        internal.storage = lambda: {
            "mode": "internal",
            "internal": {"total_bytes": internal_total},
            "adopted": None,
        }
        adopted.storage = lambda: {
            "mode": "adopted",
            "internal": {"total_bytes": 1024},
            "adopted": {"total_bytes": adopted_total},
        }
        observed = []

        def df_for(total_bytes):
            def shell(*args, **kwargs):
                self.assertEqual(args[:2], ("df", "-k"))
                observed.append((args[2], total_bytes))
                blocks = total_bytes // 1024
                return f"Filesystem 1K-blocks Used Available Use% Mounted on\nselected {blocks} 1 {blocks - 1} 1% /selected"

            return shell

        internal.sh = df_for(internal_total)
        adopted.sh = df_for(adopted_total)
        internal_runtime = {
            "persistentDataPath": "/storage/emulated/0/Android/data/" + device.PACKAGE + "/files",
            "marker": "internal",
        }
        adopted_runtime = {
            "persistentDataPath": "/sdcard/Android/data/" + device.PACKAGE + "/files",
            "marker": "adopted",
        }

        internal.write_receipt("runtime.json", internal_runtime)
        adopted.write_receipt("runtime.json", adopted_runtime)
        internal_read = internal.read_receipt("runtime.json")
        adopted_read = adopted.read_receipt("runtime.json")
        self.assertEqual(internal_read["marker"], "internal")
        self.assertEqual(adopted_read["marker"], "adopted")
        self.assertEqual(internal_read["serial"], DEFAULT_TEST_SERIAL)
        self.assertEqual(adopted_read["serial"], SECOND_TEST_SERIAL)
        self.assertEqual(
            observed,
            [
                (internal_runtime["persistentDataPath"], internal_total),
                (adopted_runtime["persistentDataPath"], adopted_total),
                (internal_runtime["persistentDataPath"], internal_total),
                (adopted_runtime["persistentDataPath"], adopted_total),
            ],
        )

    def test_internal_reserve_override_blocks_before_any_device_operation(self):
        self.d.settings.update({"storage_mode": "internal", "internal_reserve_mib": 1536})
        storage = {
            "mode": "internal",
            "internal": {"free_bytes": 1024**3},
            "adopted": None,
        }
        with self.assertRaisesRegex(RuntimeError, "Insufficient internal"):
            self.d.install_capacity(self.apk(), storage)

    def test_dual_physical_display_sleep_requires_both_panels_off(self):
        calls = []

        def shell(*args, **kwargs):
            calls.append(args)
            if args == ("getprop", "ro.product.model"):
                return "Authorized Dual Display"
            if args == ("dumpsys", "power"):
                return "mWakefulness=Asleep"
            if args == ("dumpsys", "display"):
                return "\n".join(
                    [
                        'DisplayDeviceInfo{"panel-left" type INTERNAL state OFF}',
                        'DisplayDeviceInfo{"panel-right" type INTERNAL state OFF}',
                        'DisplayDeviceInfo{"virtual" type VIRTUAL state ON}',
                    ]
                )
            if args == ("input", "keyevent", "KEYCODE_SLEEP"):
                return ""
            self.fail("Unexpected mocked device command: " + repr(args))

        self.d.settings.update(
            {
                "sleep_display_when_idle": True,
                "display_models": ["Authorized Dual Display"],
                "display_count": 2,
            }
        )
        self.d.sh = shell
        self.assertTrue(self.d.display(False))
        self.assertEqual(
            calls,
            [
                ("getprop", "ro.product.model"),
                ("input", "keyevent", "KEYCODE_SLEEP"),
                ("dumpsys", "power"),
                ("dumpsys", "display"),
            ],
        )

    def thor_display_shell(self, bottom_can_power_off):
        state = {"mode": "0", "awake": False, "calls": []}
        self.d.settings.update(sleep_display_when_idle=True, display_models=["AYN Thor"], display_count=2)

        def shell(*args, **kwargs):
            state["calls"].append(args)
            if args == ("getprop", "ro.product.model"):
                return "AYN Thor"
            if args == ("settings", "get", "system", "dual_screen_display_mode"):
                return state["mode"]
            if args[:4] == ("settings", "put", "system", "dual_screen_display_mode"):
                state["mode"] = args[4]
                return ""
            if args[:2] == ("input", "keyevent"):
                state["awake"] = args[2] == "KEYCODE_WAKEUP"
                return ""
            if args == ("dumpsys", "power"):
                return "mWakefulness=" + ("Awake" if state["awake"] else "Asleep")
            if args == ("dumpsys", "display"):
                top = "ON" if state["awake"] else "OFF"
                bottom = "ON" if state["awake"] and not (bottom_can_power_off and state["mode"] == "1") else "OFF"
                return "\n".join(
                    [
                        'DisplayDeviceInfo{"Built-in Screen": type INTERNAL, state ' + top + "}",
                        'DisplayDeviceInfo{"Screen-2": type INTERNAL, state ' + bottom + "}",
                        'DisplayDeviceInfo{"virtual": type VIRTUAL, state ON}',
                    ]
                )
            self.fail("Unexpected mocked device command: " + repr(args))

        self.d.sh = shell
        return state

    def test_thor_top_only_is_verified_and_first_mode_survives_nested_device_context(self):
        state = self.thor_display_shell(True)
        self.assertTrue(self.d.display(True))
        second = object.__new__(device.Device)
        second.__dict__.update(self.d.__dict__)
        self.assertTrue(second.display(True))
        self.assertEqual(device.Device.sleep_awakened(), [])
        self.assertEqual(state["mode"], "0")
        self.assertFalse(state["awake"])
        self.assertEqual(device.Device._awake_devices, {})
        writes = [args[-1] for args in state["calls"] if args[:2] == ("settings", "put")]
        self.assertEqual(writes, ["1", "1", "0"])

    def test_thor_black_vendor_overlay_refuses_and_restores_then_sleeps_both_panels(self):
        state = self.thor_display_shell(False)
        with patch.object(device.time, "monotonic", side_effect=range(30)), patch.object(device.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "Screen-2 OFF"):
                self.d.display(True)
        self.assertFalse(state["awake"])
        self.assertEqual(state["mode"], "0")
        self.assertEqual(device.Device._awake_devices, {})
        self.assertFalse(self.d.display_awakened)

    def test_thor_unknown_mode_is_never_overwritten(self):
        state = self.thor_display_shell(True)
        state["mode"] = "unknown"
        with self.assertRaisesRegex(RuntimeError, "Unknown Thor"):
            self.d.display(True)
        self.assertEqual(state["mode"], "unknown")
        self.assertFalse(state["awake"])
        self.assertFalse(any(args[:2] == ("settings", "put") for args in state["calls"]))
        self.assertEqual(device.Device._awake_devices, {})

    def test_thor_brief_wake_transition_is_not_top_only_acceptance(self):
        state = self.thor_display_shell(False)
        shell = self.d.sh
        sampled = False

        def transient(*args, **kwargs):
            nonlocal sampled
            result = shell(*args, **kwargs)
            if args == ("dumpsys", "display") and state["awake"] and not sampled:
                sampled = True
                return result.replace('"Screen-2": type INTERNAL, state ON', '"Screen-2": type INTERNAL, state OFF')
            return result

        self.d.sh = transient
        clock = [0.0]
        with (
            patch.object(device.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(device.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
        ):
            with self.assertRaisesRegex(RuntimeError, "Screen-2 OFF"):
                self.d.display(True)
        self.assertTrue(sampled)
        self.assertFalse(state["awake"])
        self.assertEqual(state["mode"], "0")

    def test_thor_failed_mode_write_still_restores_original_and_sleeps(self):
        state = self.thor_display_shell(True)
        shell = self.d.sh

        def interrupted(*args, **kwargs):
            result = shell(*args, **kwargs)
            if args == ("settings", "put", "system", "dual_screen_display_mode", "1"):
                raise RuntimeError("Interrupted mode write")
            return result

        self.d.sh = interrupted
        with self.assertRaisesRegex(RuntimeError, "Interrupted mode write"):
            self.d.display(True)
        self.assertFalse(state["awake"])
        self.assertEqual(state["mode"], "0")
        self.assertEqual(device.Device._awake_devices, {})

    def test_production_device_lock_refusal_uses_only_temporary_root(self):
        lock = self.root / "work/coordination/claude-r9.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text("fixture")
        with patch.object(device, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "Device access blocked"):
                REAL_REQUIRE_DEVICE_ACCESS(force=True)

    def test_sync_rejects_arbitrary_destination(self):
        self.d.owned = lambda: {}
        self.d.storage = lambda: {}
        write(self.d.receipt("runtime.json"), {"persistentDataPath": "/data/local/tmp/another-game"})
        with self.assertRaisesRegex(RuntimeError, "Unexpected runtime"):
            self.d.sync()

    def test_adopted_sync_rejects_internal_backing_before_writing(self):
        self.d.owned = lambda: {}
        self.d.storage = lambda: {"mode": "adopted", "adopted": {"total_bytes": 900 * 1024**3}}
        calls = []

        def shell(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("df", "-k"):
                return "Filesystem 1K-blocks Used Available Use% Mounted on\ninternal 100000000 1 99999999 1% /storage/emulated"
            self.fail("Storage rejection must precede writes")

        self.d.sh = shell
        write(self.d.receipt("runtime.json"), {"persistentDataPath": "/storage/emulated/0/Android/data/" + device.PACKAGE + "/files"})
        with self.assertRaisesRegex(RuntimeError, "not backed"):
            self.d.sync()
        self.assertEqual(len(calls), 1)

    def test_reset_absent_package_does_not_call_adb_uninstall(self):
        self.d.exists = lambda: False
        self.assertFalse(self.d.reset()["removed"])

    def test_internal_storage_requires_explicit_mode_and_no_adopted_volume(self):
        self.d.sh = lambda *args, **kwargs: "private:disk mounted " + ("a" * 8 + "-" + ("b" * 4 + "-") * 3 + "c" * 12)
        self.d.settings["storage_mode"] = "internal"
        with self.assertRaisesRegex(RuntimeError, "now has adopted"):
            self.d.storage()

    def test_default_adopted_mode_rejects_missing_volume(self):
        self.d.sh = lambda *args, **kwargs: ""
        with self.assertRaisesRegex(RuntimeError, "mounted adopted"):
            self.d.storage()

    def test_one_apk_limit_reuses_identical_owned_install_and_rejects_replacement(self):
        calls = []
        installed = [False]
        self.d.exists = lambda: installed[0]
        self.d.storage = lambda: {"mode": "internal", "uuid": None, "internal": {"free_bytes": 10**12}, "adopted": None}
        self.d.sh = lambda *args, **kwargs: "package:/data/app/test/base.apk" if args == ("pm", "path", device.PACKAGE) else ""

        def command(*args, **kwargs):
            calls.append(args)
            installed[0] = True
            return "Success"

        self.d.cmd = command
        self.d.settings["apk_install_limit"] = 1
        apk = self.apk()
        self.d.install(apk)
        self.assertTrue(self.d.install(apk)["reused"])
        self.assertEqual(calls[0][:6], ("install", "--streaming", "--no-incremental", "-r", "--force-uuid", "internal"))
        self.assertEqual(len(calls), 1)
        with zipfile.ZipFile(apk, "w") as z:
            z.writestr("lib/arm64-v8a/libtest.so", b"changed")
        with self.assertRaisesRegex(RuntimeError, "limit exhausted"):
            self.d.install(apk)
        installed[0] = False
        with self.assertRaisesRegex(RuntimeError, "limit exhausted"):
            self.d.install(apk)
        self.assertEqual(len(calls), 1)

    def test_display_control_refuses_non_nova_before_sending_key(self):
        calls = []
        self.d.sh = lambda *args, **kwargs: (calls.append(args) or "different-model")
        self.d.settings["sleep_display_when_idle"] = True
        with self.assertRaisesRegex(RuntimeError, "explicitly authorized exact model"):
            self.d.display(False)
        self.assertEqual(calls, [("getprop", "ro.product.model")])

    def test_authorized_update_replaces_same_package_and_counts_dispatches(self):
        calls = []
        installed = [False]
        self.d.exists = lambda: installed[0]
        self.d.storage = lambda: {"mode": "internal", "uuid": None, "internal": {"free_bytes": 10**12}, "adopted": None}
        self.d.sh = lambda *args, **kwargs: "package:/data/app/test/base.apk" if args == ("pm", "path", device.PACKAGE) else ""

        def command(*args, **kwargs):
            calls.append(args)
            installed[0] = True
            return "Success"

        self.d.cmd = command
        apk = self.apk()
        first = self.d.install(apk)
        with zipfile.ZipFile(apk, "w") as z:
            z.writestr("lib/arm64-v8a/libtest.so", b"updated")
        second = self.d.install(apk)
        self.assertEqual(first["package"], second["package"])
        self.assertNotEqual(first["apk_sha256"], second["apk_sha256"])
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call[:6], ("install", "--streaming", "--no-incremental", "-r", "--force-uuid", "internal"))
        counter = json.loads(self.d.install_counter().read_text())
        self.assertEqual(counter["dispatched"], 2)

    def test_display_opt_out_never_queries_device(self):
        self.d.sh = lambda *args, **kwargs: self.fail("Unrequested display operation")
        self.assertFalse(self.d.display(False))

    def test_display_wake_and_sleep_verify_power_state(self):
        calls = []

        def shell(*args, **kwargs):
            calls.append(args)
            if args == ("getprop", "ro.product.model"):
                return "Retroid Pocket Nova"
            if args == ("dumpsys", "power"):
                return "mWakefulness=" + (
                    "Awake" if ("input", "keyevent", "KEYCODE_WAKEUP") in calls and ("input", "keyevent", "KEYCODE_SLEEP") not in calls else "Asleep"
                )
            return ""

        self.d.sh = shell
        self.d.settings["sleep_display_when_idle"] = True
        self.assertTrue(self.d.display(True))
        self.assertTrue(self.d.display_awakened)
        self.assertTrue(self.d.display(False))
        self.assertFalse(self.d.display_awakened)

    def test_failed_cli_sleeps_awakened_display_and_keeps_first_error(self):
        calls = []
        fake = types.ModuleType("device")
        scene = types.ModuleType("scene_runtime")

        class FakeDevice:
            @classmethod
            def sleep_awakened(cls):
                calls.append(("cleanup", "all-registered-instances"))
                return []

        fake.Device = FakeDevice
        stderr = io.StringIO()

        def fail_run():
            raise RuntimeError("deliberate runtime failure")

        scene.movement_batch_run = fail_run
        with (
            patch.dict(sys.modules, {"device": fake, "scene_runtime": scene}),
            patch.object(device_context, "set_command_selector", lambda cli, env: calls.append(("selector", cli, env))),
            patch.object(sys, "argv", ["dev", "prototype", "--action", "movement-batch-run"]),
            contextlib.redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ended:
                runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/lab/main.py"), run_name="__main__")
        self.assertEqual(ended.exception.code, 1)
        self.assertEqual(calls, [("selector", None, None), ("cleanup", "all-registered-instances")])
        self.assertIn("deliberate runtime failure", stderr.getvalue())

    def test_sleep_awakened_cleans_exact_registered_instances(self):
        first = object.__new__(device.Device)
        second = object.__new__(device.Device)
        calls = []
        first.display = lambda awake: calls.append((first, awake))
        second.display = lambda awake: calls.append((second, awake))
        device.Device._awake_devices[("receipt-a", DEFAULT_TEST_SERIAL)] = first
        device.Device._awake_devices[("receipt-b", SECOND_TEST_SERIAL)] = second

        self.assertEqual(device.Device.sleep_awakened(), [])
        self.assertEqual(calls, [(first, False), (second, False)])

    def test_cleanup_failure_does_not_replace_original_cli_error(self):
        fake = types.ModuleType("device")
        scene = types.ModuleType("scene_runtime")

        class FakeDevice:
            @classmethod
            def sleep_awakened(cls):
                return ["display could not sleep"]

        fake.Device = FakeDevice
        fake.set_command_selector = lambda cli, env: None
        scene.movement_batch_run = lambda: (_ for _ in ()).throw(RuntimeError("original command failure"))
        stderr = io.StringIO()
        with (
            patch.dict(sys.modules, {"device": fake, "scene_runtime": scene}),
            patch.object(device_context, "set_command_selector", lambda cli, env: None),
            patch.object(sys, "argv", ["dev", "prototype", "--action", "movement-batch-run"]),
            contextlib.redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ended:
                runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/lab/main.py"), run_name="__main__")
        self.assertEqual(ended.exception.code, 1)
        self.assertIn("original command failure", stderr.getvalue())
        self.assertIn("display could not sleep", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
