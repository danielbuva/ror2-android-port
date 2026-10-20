"""Acceptance and hash-proven cleanup for the authored app-sandbox fixture."""

import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile

from phone_package_check import package_hash


PACKAGE = "dev.ror2lab.phonehostfixture"


def cleanup_owned(device, digest):
    actual = package_hash(device, PACKAGE)
    if actual is None:
        return True
    if actual != digest:
        raise RuntimeError("Host cleanup refused: installed fixture hash is unowned")
    device.sh("am", "force-stop", PACKAGE)
    device.cmd("uninstall", PACKAGE)
    if package_hash(device, PACKAGE) is not None:
        raise RuntimeError("Host fixture remains installed")
    return True


def validate_control(apk):
    with zipfile.ZipFile(apk) as archive:
        native = archive.read("lib/arm64-v8a/libtoolprobe.so")
        if native != archive.read("assets/control.bin") or native[:4] != b"\x7fELF" or native[18:20] != b"\xb7\x00":
            raise ValueError("Expected identical authored ARM64 native/control bytes")


def check_action(request):
    from common import ROOT, WORK, now
    from device import Device
    from device_context import command_selectors

    selector, _ = command_selectors()
    if not selector:
        raise RuntimeError("Host fixture requires an explicit --device")
    request = Path(request).resolve()
    if not request.is_relative_to(WORK.resolve()):
        raise ValueError("Host request must be ignored local evidence")
    value = json.loads(request.read_text())
    if set(value) != {"apk", "sha256"}:
        raise ValueError("Expected exact APK path and hash")
    apk = Path(value["apk"]).resolve()
    if not apk.is_relative_to(WORK.resolve()) or hashlib.sha256(apk.read_bytes()).hexdigest() != value["sha256"]:
        raise ValueError("Host APK path/hash mismatch")
    validate_control(apk)
    device = Device(selector=selector)
    device.validate_apk(apk, PACKAGE)
    directory = WORK / "experiments/phone-host" / now()
    directory.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": 1,
        "serial": device.serial,
        "request": value,
        "success": False,
        "reports": [],
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    absent = attempted = False

    def save():
        (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    try:
        result["game_before"] = package_hash(device, "dev.ror2lab.arm64")
        if package_hash(device, PACKAGE) is not None:
            raise RuntimeError("Host fixture already exists; refusing replacement")
        absent = True
        result["storage"] = device.storage()
        result["capacity"] = device.install_capacity(apk, result["storage"])
        save()
        attempted = True
        result["install"] = device.cmd("install", "--force-uuid", result["storage"]["uuid"] or "internal", str(apk), timeout=240)
        if package_hash(device, PACKAGE) != value["sha256"]:
            raise RuntimeError("Installed host APK hash mismatch")
        result["package_path"] = device.sh("pm", "path", PACKAGE)
        storage = result["storage"]
        expected = "/data/app/" if storage["mode"] == "internal" else "/mnt/expand/" + storage["uuid"] + "/"
        if expected not in result["package_path"]:
            raise RuntimeError("Host placement does not match selected storage")
        result["package_details"] = device.sh("dumpsys", "package", PACKAGE)
        for cycle in range(2):
            device.sh("am", "force-stop", PACKAGE)
            device.sh("run-as", PACKAGE, "rm", "-f", "files/host-report.json")
            device.display(True)
            result["launch"] = device.sh("am", "start", "-W", "-n", PACKAGE + "/.HostProbeActivity")
            pid = device.sh("pidof", PACKAGE, check=False).strip()
            deadline = time.monotonic() + 30
            try:
                while time.monotonic() < deadline:
                    try:
                        report = json.loads(device.sh("run-as", PACKAGE, "cat", "files/host-report.json", check=False))
                        result["reports"].append(report)
                        save()
                        break
                    except ValueError:
                        time.sleep(1)
                else:
                    raise RuntimeError("Host report deadline")
            finally:
                if pid:
                    (directory / f"cycle-{cycle}-logcat.txt").write_text(
                        device.cmd("logcat", "-d", "--pid=" + pid.split()[0], "-v", "threadtime", "PhoneHostFixture:I", "AndroidRuntime:E", "*:S")
                    )
            if report.get("success") is not True or report.get("targetSdk") != 30 or report.get("uid", 0) < 10000:
                raise RuntimeError("Installed/writable app-sandbox execution contract failed")
        result["app_data_backing"] = device.sh("run-as", PACKAGE, "sh", "-c", "pwd; df -k .")
        result["success"] = True
    except Exception as error:
        result["failure"] = str(error)
    finally:
        errors = []
        if absent and attempted:
            try:
                result["removed"] = cleanup_owned(device, value["sha256"])
            except Exception as error:
                errors.append("owned cleanup: " + str(error))
        try:
            result["display_asleep"] = device.display(False)
            if not result["display_asleep"]:
                errors.append("display sleep unverified")
        except Exception as error:
            errors.append("display sleep: " + str(error))
        try:
            result["game_after"] = package_hash(device, "dev.ror2lab.arm64")
            result["game_unchanged"] = result.get("game_before") == result["game_after"]
            if not result["game_unchanged"]:
                errors.append("game APK changed")
        except Exception as error:
            errors.append("game hash: " + str(error))
        if errors:
            result["cleanup_errors"] = errors
            result["success"] = False
        save()
    print(json.dumps({"success": result["success"], "evidence": str(directory), "failure": result.get("failure")}, indent=2))
    if not result["success"]:
        raise RuntimeError("Phone host check failed; inspect retained evidence")
