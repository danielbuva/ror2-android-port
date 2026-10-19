#!/usr/bin/env python3
"""Install, inspect, then remove the disposable ARM64 bootstrap on one device."""

import argparse
import datetime
import hashlib
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "dev.localbootstrap.arm64smoke"
ACTIVITY = PACKAGE + "/com.unity3d.player.UnityPlayerActivity"
REMOTE_SCREENSHOT = "/data/local/tmp/ror2-bootstrap-smoke.png"


def _device_type():
    lab = str(ROOT / "scripts" / "lab")
    if lab not in sys.path:
        sys.path.insert(0, lab)
    from device import Device

    return Device


def _timestamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def _package_exists(device):
    return ("package:" + PACKAGE) in device.sh("pm", "list", "packages", PACKAGE).splitlines()


def _placement_matches(storage, package_path):
    if storage["mode"] == "adopted":
        uuid = storage.get("uuid")
        return bool(uuid) and ("/mnt/expand/" + uuid + "/") in package_path
    return storage["mode"] == "internal" and "/data/app/" in package_path and "/mnt/expand/" not in package_path


def run(argv=None, *, device_factory=None, sleep=time.sleep, timestamp=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", help="Authorized device serial from the local device allowlist")
    parser.add_argument(
        "--adopted",
        action="store_true",
        help="Legacy confirmation that the selected device is configured for adopted storage",
    )
    args = parser.parse_args(argv)

    factory = device_factory or _device_type()
    device = factory(selector=args.device)
    receipt_dir = device.evidence_directory("bootstrap", timestamp or _timestamp())
    receipt_dir.mkdir(parents=True, exist_ok=False)
    apk = ROOT / "builds" / "bootstrap-arm64.apk"
    result = {
        "success": False,
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "serial": device.serial,
        "package": PACKAGE,
        "apk": str(apk),
        "receipt_dir": str(receipt_dir),
    }
    package_absent_before_install = False
    install_attempted = False
    installed = False
    remote_screenshot_created = False

    try:
        if not apk.is_file():
            raise RuntimeError("Bootstrap APK is missing: " + str(apk))
        result["apk_sha256"] = hashlib.sha256(apk.read_bytes()).hexdigest()

        # This disposable package has no update/ownership path. Refuse any
        # pre-existing instance before asking Android to install anything.
        if _package_exists(device):
            raise RuntimeError("Smoke package already exists; inspect its ownership before replacing or removing it.")
        package_absent_before_install = True
        device.validate_apk(apk, PACKAGE)

        # Both measurements are fresh for this invocation. The helper performs
        # ARM64 and reserve checks before any install command is dispatched.
        storage = device.storage()
        result["storage"] = storage
        if args.adopted and storage.get("mode") != "adopted":
            raise RuntimeError("--adopted only confirms a device configured for adopted storage")
        result["capacity"] = device.install_capacity(apk, storage)

        install_args = ["install", "--force-uuid", storage["uuid"] or "internal", str(apk)]
        # adb can report a timeout/transport error after PackageManager has
        # committed the install. Remember dispatch separately from success so
        # the finally block can inspect this selected package before cleanup.
        install_attempted = True
        result["install"] = device.cmd(*install_args, timeout=240)
        installed = True

        result["package_path"] = device.sh("pm", "path", PACKAGE)
        details = device.sh("dumpsys", "package", PACKAGE)
        result["package_details"] = "\n".join(
            line.strip()
            for line in details.splitlines()
            if any(key in line for key in ("codePath=", "volumeUuid=", "primaryCpuAbi=", "installLocation="))
        )
        result["placement_verified"] = _placement_matches(storage, result["package_path"])
        if not result["placement_verified"]:
            raise RuntimeError("Bootstrap package was installed outside the freshly selected storage volume")
        if "arm64-v8a" not in result["package_details"]:
            raise RuntimeError("Installed bootstrap package does not report arm64-v8a")

        device.display(True)
        result["launch"] = device.sh("am", "start", "-W", "-n", ACTIVITY)
        sleep(8)
        pid = device.sh("pidof", PACKAGE).split()[0]
        logs = device.cmd(
            "logcat", "-d", "--pid=" + pid, "-v", "threadtime",
            "Unity:I", "AndroidRuntime:E", "*:S",
        )
        log_path = receipt_dir / "logcat.txt"
        log_path.write_text(logs + "\n")
        result["logcat"] = str(log_path)
        result["marker_found"] = "ROR2_BOOTSTRAP_ARM64_OK" in logs
        result["pid"] = pid
        if not result["marker_found"]:
            raise RuntimeError("Unity bootstrap marker missing; screenshot skipped")

        device.sh("screencap", "-p", REMOTE_SCREENSHOT)
        remote_screenshot_created = True
        screenshot = receipt_dir / "screenshot.png"
        device.cmd("pull", REMOTE_SCREENSHOT, str(screenshot), timeout=30)
        if not screenshot.is_file() or not screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Invalid bootstrap screenshot")
        result["screenshot"] = str(screenshot)
        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        cleanup_errors = []
        cleanup_package = installed
        if install_attempted and not installed and package_absent_before_install:
            try:
                cleanup_package = _package_exists(device)
                result["install_outcome"] = (
                    "package present after failed install dispatch"
                    if cleanup_package
                    else "package absent after failed install dispatch"
                )
            except Exception as exc:
                # The install outcome is uncertain. Never guess and uninstall
                # a package when the selected device cannot confirm its state.
                cleanup_errors.append("install outcome query; package cleanup skipped: " + str(exc))
        if cleanup_package and package_absent_before_install:
            try:
                device.sh("am", "force-stop", PACKAGE)
            except Exception as exc:
                cleanup_errors.append("force-stop: " + str(exc))
            try:
                result["uninstall"] = device.cmd("uninstall", PACKAGE)
                result["removed"] = not _package_exists(device)
                if not result["removed"]:
                    cleanup_errors.append("uninstall verification: smoke package remains installed")
            except Exception as exc:
                cleanup_errors.append("uninstall: " + str(exc))
        if remote_screenshot_created:
            try:
                device.sh("rm", "-f", REMOTE_SCREENSHOT)
            except Exception as exc:
                cleanup_errors.append("remote screenshot cleanup: " + str(exc))
        try:
            device.display(False)
        except Exception as exc:
            cleanup_errors.append("display sleep: " + str(exc))
        if cleanup_errors:
            result["success"] = False
            result["cleanup_errors"] = cleanup_errors
        result_path = receipt_dir / "result.json"
        result["result"] = str(result_path)
        result_path.write_text(json.dumps(result, indent=2) + "\n")

    print(json.dumps(result, indent=2))
    if not result["success"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
