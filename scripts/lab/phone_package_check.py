"""Owned-package tests for phone-generated content and two signed fixture APKs."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import time
import uuid
import zipfile

from phone_apk import PACKAGE, update_manifest


def bind_runtime(device, paths, storage):
    if set(paths) != {"persistentDataPath", "filesDir", "externalFilesDir"}:
        raise ValueError("Runtime path report fields differ")
    for path in paths.values():
        parsed = PurePosixPath(path)
        if not parsed.is_absolute() or ".." in parsed.parts or parsed.parts[-2:] != (PACKAGE, "files"):
            raise ValueError("Runtime path must belong to this fixture")
    persistent = device.sh("readlink", "-f", paths["persistentDataPath"]).strip()
    external = device.sh("readlink", "-f", paths["externalFilesDir"]).strip()
    private = device.sh("run-as", PACKAGE, "readlink", "-f", paths["filesDir"]).strip()
    data = device.sh("run-as", PACKAGE, "pwd").strip()
    prefix = "/data/" if storage["mode"] == "internal" else "/mnt/expand/" + storage["uuid"] + "/"
    if not persistent or persistent != external or private != data + "/files" or not private.startswith(prefix):
        raise ValueError("Runtime paths do not match Android storage observations")
    return {
        "paths": paths,
        "directory": persistent,
        "app_data_backing": device.sh("run-as", PACKAGE, "df", "-k", private),
        "runtime_backing": device.sh("df", "-k", persistent),
    }


def package_hash(device, package=PACKAGE):
    packages = device.sh("pm", "list", "packages", package).splitlines()
    if "package:" + package not in packages:
        return None
    paths = device.sh("pm", "path", package).splitlines()
    if len(paths) != 1 or not paths[0].startswith("package:"):
        raise RuntimeError("Expected one installed base APK")
    return device.sh("sha256sum", paths[0][8:]).split()[0]


def cleanup_owned(device, hashes):
    actual = package_hash(device)
    if actual is None:
        return True
    if actual not in hashes:
        raise RuntimeError("Fixture cleanup refused: installed bytes do not match the owned attempts")
    device.sh("am", "force-stop", PACKAGE)
    device.cmd("uninstall", PACKAGE)
    if package_hash(device) is not None:
        raise RuntimeError("Fixture package remains installed")
    return True


def check_action(request):
    from common import ROOT, WORK, now
    from device import Device
    from device_context import command_selectors

    selector, _ = command_selectors()
    if not selector:
        raise RuntimeError("The fixture check requires an explicit --device")
    request = Path(request).resolve()
    if not request.is_relative_to(WORK.resolve()):
        raise ValueError("Select an ignored local fixture-check request with --target")
    value = json.loads(request.read_text())
    if set(value) != {"apks", "candidate", "workspace_receipt"} or len(value["apks"]) != 2:
        raise ValueError("Fixture check request fields do not match the contract")
    device = Device(selector=selector)
    ownership_path = Path(value["workspace_receipt"]).resolve()
    if not ownership_path.is_relative_to(WORK.resolve()):
        raise ValueError("Shell workspace receipt must be local ignored evidence")
    workspace = json.loads(ownership_path.read_text())
    remote = workspace["remote"]
    candidate = value["candidate"]
    if workspace["device"] != device.serial or not re.fullmatch(r"/data/local/tmp/ror2-phone-proof-[0-9a-f]{32}", remote):
        raise ValueError("Shell workspace ownership/device mismatch")
    remote_candidate = PurePosixPath(candidate["remote_path"])
    if ".." in remote_candidate.parts or remote_candidate.parent != PurePosixPath(remote) or not re.fullmatch(r"[0-9a-f]{64}", candidate["sha256"]):
        raise ValueError("Candidate must be a hash-bound file directly in the owned shell workspace")
    for index, item in enumerate(value["apks"]):
        path = Path(item["path"]).resolve()
        if not path.is_relative_to(WORK.resolve()) or item["version_code"] != 3 + index or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Fixture APK path/hash/version mismatch")
        device.validate_apk(path, PACKAGE)
        with zipfile.ZipFile(path) as archive:
            if update_manifest(archive.read("AndroidManifest.xml"), item["version_code"] + 1)[1] != item["version_code"]:
                raise ValueError("Fixture manifest version mismatch")
    directory = WORK / "experiments/phone-packaging" / now()
    directory.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": 1,
        "serial": device.serial,
        "request": value,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "phases": [],
        "installs": [],
        "success": False,
    }
    absent = False
    attempted = False
    owned_hashes = {item["sha256"] for item in value["apks"]}
    runtime = {}

    def save():
        (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    def phase(label, *, expected_source=None, negative=False):
        device.sh("am", "force-stop", PACKAGE)
        if runtime:
            device.sh("rm", "-f", runtime["directory"] + "/phone-content-report.json")
        device.sh("run-as", PACKAGE, "rm", "-f", "files/phone-content-paths.json")
        device.display(True)
        launch = device.sh("am", "start", "-W", "-n", PACKAGE + "/com.unity3d.player.UnityPlayerActivity")
        entry = {"name": label, "launch": launch}
        result["phases"].append(entry)
        save()
        pid = device.sh("pidof", PACKAGE, check=False).strip()
        deadline = time.monotonic() + 60
        try:
            while time.monotonic() < deadline:
                try:
                    paths = json.loads(device.sh("run-as", PACKAGE, "cat", "files/phone-content-paths.json", check=False))
                    break
                except ValueError:
                    time.sleep(1)
            else:
                raise RuntimeError(label + ": runtime path discovery deadline")
            runtime.update(bind_runtime(device, paths, result["installs"][-1]["storage"]))
            entry["runtime"] = dict(runtime)
            while time.monotonic() < deadline:
                try:
                    report = json.loads(device.sh("cat", runtime["directory"] + "/phone-content-report.json", check=False))
                    entry["report"] = report
                    break
                except ValueError:
                    time.sleep(1)
            else:
                raise RuntimeError(label + ": report deadline")
        finally:
            if pid:
                (directory / (label + "-logcat.txt")).write_text(
                    device.cmd("logcat", "-d", "--pid=" + pid.split()[0], "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S")
                )
        save()
        if negative:
            if not report.get("failure", "").startswith("candidate: Candidate hash mismatch") or report.get("bundleLoaded") or report.get("successfulCycles"):
                raise RuntimeError("Mismatched candidate was not refused before native loading")
        elif not (
            report.get("unity") == "2021.3.45f2"
            and report.get("graphics") == "Vulkan"
            and report.get("source") == expected_source
            and report.get("bundleSha256") == candidate["sha256"]
            and report.get("successfulCycles") == 2
            and all(report.get(name) is True for name in ("bundleLoaded", "textMatched", "unloaded"))
            and not report.get("failure")
        ):
            raise RuntimeError(label + ": native content contract failed")

    def select(digest):
        local = directory / "selection.json"
        local.write_text(json.dumps({"sha256": digest}) + "\n")
        device.cmd("push", str(local), runtime["directory"] + "/phone-fixture-selection.json")

    try:
        result["game_before"] = package_hash(device, "dev.ror2lab.arm64")
        if package_hash(device) is not None:
            raise RuntimeError("Fixture package already exists; refusing replacement")
        absent = True
        if device.sh("sha256sum", str(remote_candidate)).split()[0] != candidate["sha256"]:
            raise RuntimeError("Phone-generated candidate bytes drifted")
        for index, item in enumerate(value["apks"]):
            if index and package_hash(device) not in owned_hashes:
                raise RuntimeError("Update requires ownership of the installed fixture")
            if index:
                device.sh("am", "force-stop", PACKAGE)
            storage = device.storage()
            capacity = device.install_capacity(Path(item["path"]), storage)
            install = {"version_code": item["version_code"], "storage": storage, "capacity": capacity}
            result["installs"].append(install)
            attempted = True
            save()
            args = ["install", *(["-r"] if index else []), "--force-uuid", storage["uuid"] or "internal", item["path"]]
            install["output"] = device.cmd(*args, timeout=240)
            install["actual_sha256"] = package_hash(device)
            if install["actual_sha256"] != item["sha256"]:
                raise RuntimeError("Installed fixture hash does not match its explicit APK")
            install["package_path"] = device.sh("pm", "path", PACKAGE)
            details = device.sh("dumpsys", "package", PACKAGE)
            if not re.search(r"\bversionCode=" + str(item["version_code"]) + r"\b", details):
                raise RuntimeError("Installed version code mismatch")
            expected = "/data/app/" if storage["mode"] == "internal" else "/mnt/expand/" + storage["uuid"] + "/"
            if expected not in install["package_path"]:
                raise RuntimeError("Fixture placement does not match fresh selected storage")
            if not index:
                phase("embedded", expected_source="embedded")
                device.sh("am", "force-stop", PACKAGE)
                device.sh("cp", str(remote_candidate), runtime["directory"] + "/phone-candidate.bundle")
                select("0" * 64)
                phase("hash-refusal", negative=True)
                select(candidate["sha256"])
                phase("phone-candidate", expected_source="external-candidate")
                marker = uuid.uuid4().hex
                device.sh("run-as", PACKAGE, "sh", "-c", "mkdir -p files; printf %s " + marker + " > files/owner-update-marker")
                result["marker"] = marker
            else:
                result["data_retained"] = device.sh("run-as", PACKAGE, "cat", "files/owner-update-marker") == result["marker"]
                result["candidate_retained"] = device.sh("sha256sum", runtime["directory"] + "/phone-candidate.bundle").split()[0] == candidate["sha256"]
                if not result["data_retained"] or not result["candidate_retained"]:
                    raise RuntimeError("Owned update did not retain fixture data")
                phase("updated-phone-candidate", expected_source="external-candidate")
            install["app_data_backing"] = runtime["app_data_backing"]
            install["runtime_backing"] = runtime["runtime_backing"]
            save()
        result["success"] = True
    except Exception as error:
        result["error"] = str(error)
    finally:
        errors = []
        if absent and attempted:
            try:
                result["removed"] = cleanup_owned(device, owned_hashes)
            except Exception as error:
                errors.append("owned cleanup: " + str(error))
        try:
            result["display_asleep"] = device.display(False)
            if not result["display_asleep"]:
                errors.append("display sleep is not configured/verified")
        except Exception as error:
            errors.append("display sleep: " + str(error))
        try:
            result["game_after"] = package_hash(device, "dev.ror2lab.arm64")
            result["game_unchanged"] = result.get("game_before") == result["game_after"]
            if not result["game_unchanged"]:
                errors.append("existing game APK changed")
        except Exception as error:
            errors.append("game hash verification: " + str(error))
        if errors:
            result["cleanup_errors"] = errors
            result["success"] = False
        save()
    print(json.dumps({"success": result["success"], "evidence": str(directory), "error": result.get("error")}, indent=2))
    if not result["success"]:
        raise RuntimeError("Phone packaging fixture failed; inspect its retained result")
