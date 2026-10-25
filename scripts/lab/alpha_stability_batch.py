"""Current: one detached driver lease for SDK recovery, heap attribution and sustained play.

The caller launches this driver once and waits on its explicit atomic done file.
No detached child owns the lease. Public checks retain their own scoped cleanup;
an independent installed-byte/idle/display readback gates release of this lease.
"""

import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import common
from device_context import command_selectors, set_command_selector, validate_serial
from installed_attempt import bind_installed_apk, validate_expected_apk_sha256


DEVICE_FREE_RESERVE_BYTES = 15 * 1024**3
# J1091's native capture sizes inform this allowance. Only one capture remains
# on the device at a time; its verified host transfer removes the device file.
NATIVE_CAPTURE_HEADROOM_BYTES = 4 * 1024**3


def _modules():
    # WORK must be selected before importing any owner that captures it.
    return tuple(importlib.import_module(name) for name in ("settings_write_interrupt_check", "session_memory_check", "session_sustained_check"))


def _device(serial):
    from device import Device

    return Device(selector=serial, work_root=common.WORK)


def _idle_readback(device, expected):
    """Read actual package bytes independently of the receipt's claimed digest."""
    from device import PACKAGE
    from session_cleanup_check import _remote_path_state

    installed = device.owned()
    bind_installed_apk(installed, expected_sha256=expected)
    package_path = installed["package_path"]
    if not package_path.startswith("package:") or "\n" in package_path:
        raise RuntimeError("Expected one installed base APK path")
    actual = device.sh("sha256sum", package_path.removeprefix("package:")).split()
    if not actual or actual[0] != expected:
        raise RuntimeError("Actual installed APK bytes differ")
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    process = device.sh("pidof", PACKAGE, check=False).strip()
    selector = _remote_path_state(device, runtime + "/movement-batch-selection.json")
    pending = _remote_path_state(device, runtime + "/offline-settings-v1/preferences.json.pending")
    if process or selector != "absent" or pending != "absent":
        raise RuntimeError("Requires idle package with absent selector/pending state; preserved existing state")
    return dict(apk_sha256=actual[0], process_absent=True, selector_absent=True, pending_absent=True)


def _terminal_readback(serial, expected):
    device = _device(serial)  # Independent context; never trust a stage's result.
    try:
        proof = _idle_readback(device, expected)
    finally:
        if not device.display(False):
            raise RuntimeError("Independent OLED sleep verification failed")
    proof["oled_asleep"] = True
    return proof


def _sleep_awakened():
    from device import Device

    errors = Device.sleep_awakened()
    if errors:
        raise RuntimeError("Awakened-display cleanup failed: " + "; ".join(errors))


def _prune(root):
    result = subprocess.run(
        [sys.executable, str(root / "scripts/prune-generated.py"), "--apply", "--work-dir", str(root / "work")], capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError("Canonical generated-output pruning failed: " + result.stderr[-1000:])


def _require_capture_capacity(device):
    storage = device.storage()
    selected = storage["internal"] if storage["mode"] == "internal" else storage["adopted"]
    if selected["free_bytes"] < DEVICE_FREE_RESERVE_BYTES + NATIVE_CAPTURE_HEADROOM_BYTES:
        raise RuntimeError("Native heap capture requires 4 GiB headroom above the retained 15 GiB device free-space reserve")


def check_alpha_stability_batch(*, device_serial, expected_apk_sha256, canonical_root, done_file):
    """Run fixed stages synchronously; publish terminal status on success or failure."""
    root = Path(canonical_root).expanduser().resolve()
    if not (root / ".git").is_dir():
        raise ValueError("canonical_root must be the primary Git checkout")
    work = root / "work"
    done = Path(done_file).expanduser()
    if not done.is_absolute() or done != done.resolve() or not done.is_relative_to(work) or done.exists():
        raise ValueError("Use a new absolute --done-file under canonical ignored work/")
    result = dict(success=False, driver_pid=os.getpid(), stages=[], lease_released=False)
    token = uuid.uuid4().hex
    owner = dict(
        workstream="alpha-stability-batch",
        pid=os.getpid(),
        started=common.now(),
        purpose="SDK recovery, three-session native heaps, thirty-minute assisted sustained case",
        token=token,
    )
    acquired = False
    previous_work = common.WORK
    previous_selectors = command_selectors()
    try:
        # Once the output path is trusted, even invalid command identity must
        # publish a terminal receipt for the detached caller waiting on it.
        serial = validate_serial(device_serial)
        expected = validate_expected_apk_sha256(expected_apk_sha256)
        if expected is None:
            raise ValueError("alpha-stability-batch requires --expected-apk-sha256")
        result["apk_sha256"] = expected
        lease = root / ".local/orchestrator/leases" / serial
        lease.parent.mkdir(parents=True, exist_ok=True)
        if lease.parent.resolve() != lease.parent:
            raise RuntimeError("Canonical lease parent cannot be a symlink")
        try:
            lease.mkdir()  # Atomic refusal; do not inspect/reap/replace another owner.
        except FileExistsError as error:
            raise RuntimeError("Selected device lease is busy; no ADB access attempted") from error
        acquired = True
        common.write(lease / "owner.json", owner)
        common.WORK = work  # Explicit canonical local-state selection before Device/import.
        if previous_selectors[1] not in (None, serial):
            raise ValueError("LAB_DEVICE conflicts with explicit batch serial")
        set_command_selector(serial, previous_selectors[1])
        if shutil.disk_usage(root).free < 100 * 1024**3:
            raise RuntimeError("At least 100 GiB host free space is required before native heap capture")
        device = _device(serial)
        result["initial_readback"] = _idle_readback(device, expected)
        _require_capture_capacity(device)
        sdk, memory, sustained = _modules()
        for name, function, kwargs in (
            ("settings-write-interrupt", sdk.check_settings_write_interrupt, {}),
            ("session-memory", memory.check_session_memory, dict(sessions=3, memory_snapshots=True)),
            ("session-sustained", sustained.check_session_sustained, {}),
        ):
            result["active_stage"] = name
            if name == "session-memory":
                _require_capture_capacity(device)
            stage = function(expected_apk_sha256=expected, **kwargs)
            if not isinstance(stage, dict) or stage.get("success") is not True:
                raise RuntimeError(name + " did not return explicit success")
            result["stages"].append(dict(name=name, result=stage))
        result["success"] = True
    except BaseException as error:
        result["error"] = str(error) or type(error).__name__
        result["success"] = False
    finally:
        if acquired:
            try:
                _sleep_awakened()
            except BaseException as error:
                result["display_cleanup_error"] = str(error)
                result["success"] = False
            try:
                result["terminal_readback"] = _terminal_readback(serial, expected)
            except BaseException as error:
                result["terminal_error"] = str(error)
                result["success"] = False
            try:
                _prune(root)
                result["pruned"] = True
            except BaseException as error:
                result["prune_error"] = str(error)
                result["success"] = False
            if "terminal_readback" in result:
                try:
                    if common.read(lease / "owner.json") != owner:
                        raise RuntimeError("Lease owner changed; preserve it")
                    (lease / "owner.json").unlink()
                    lease.rmdir()
                    result["lease_released"] = True
                except BaseException as error:
                    result["lease_error"] = str(error)
                    result["success"] = False
        common.WORK = previous_work
        set_command_selector(*previous_selectors)
        result["finished"] = common.now()
        common.write(done, result)  # Atomic publication only after cleanup/prune/release decision.
    if not result["success"]:
        raise RuntimeError("Alpha stability batch failed; inspect " + str(done))
    return result
