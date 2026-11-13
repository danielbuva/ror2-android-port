"""Current shared-runner operation: pinned, resumable on-phone bundle emission.

The lab runner owns the device lease. Installer Phone owns exact-APK admission;
Device owns storage/display policy; phone_runner owns thermal duty cycling. No
private Python driver is staged or executed. Receipts contain private paths and
stay under ignored work/. A terminal producer failure retains its app and cache.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time
import uuid
import zipfile
import tarfile


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def relative(value):
    path = Path(value)
    if not isinstance(value, str) or not value or path.is_absolute() or any(p in (".", "..") for p in value.split("/")):
        raise ValueError("emission-relative-path-required")
    return path


def load_request(path):
    request = json.loads(Path(path).read_bytes())
    required = {"runner", "tool_apk", "manifest", "request", "done_file", "expected_records", "estimated_output_bytes", "profile", "timeout_seconds"}
    if set(request) != required or request["profile"] not in ("nova", "thor"):
        raise ValueError("emission-request-contract")
    for key in ("tool_apk", "manifest"):
        pin = request[key]
        if set(pin) != {"path", "sha256"} or digest(pin["path"]) != pin["sha256"]:
            raise ValueError("emission-input-pin")
    for name in ("expected_records", "estimated_output_bytes", "timeout_seconds"):
        if type(request[name]) is not int or request[name] <= 0:
            raise ValueError("emission-positive-budget-required")
    relative(request["request"])
    manifest = json.loads(Path(request["manifest"]["path"]).read_bytes())
    files = manifest["files"]
    if request["request"] not in files:
        raise ValueError("emission-request-not-staged")
    for name, pin in files.items():
        relative(name)
        path = Path(pin["source"])
        if path.stat().st_size != pin["bytes"] or digest(path) != pin["sha256"]:
            raise ValueError("emission-staged-input-pin")
    return request, files


def transfer(phone, apk, files, remote, native):
    """Stream pinned inputs/runtime once, without another host copy or archive."""
    with zipfile.ZipFile(apk) as archive:
        pins = json.loads(archive.read("assets/native-hashes.json"))
        links = json.loads(archive.read("assets/python-links.json"))
        command = shlex.join(["run-as", "dev.ror2lab.installertest", "tar", "-xf", "-", "-C", remote])
        process = subprocess.Popen(
            [str(phone.adb), "-s", phone.serial, "shell", command], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        try:
            with tarfile.open(fileobj=process.stdin, mode="w|", format=tarfile.GNU_FORMAT) as tar:
                for name in archive.namelist():
                    if name.startswith("assets/python/") and not name.endswith("/"):
                        info = tarfile.TarInfo("runtime/" + name.removeprefix("assets/"))
                        info.size, info.mode = archive.getinfo(name).file_size, 0o600
                        with archive.open(name) as stream:
                            tar.addfile(info, stream)
                for name, target in links.items():
                    if name.startswith(("python/", "native-links/")):
                        if target not in pins:
                            raise ValueError("emission-native-link-pin")
                        info = tarfile.TarInfo("runtime/" + str(relative(name)))
                        info.type, info.linkname = tarfile.SYMTYPE, native + "/" + str(relative(target))
                        tar.addfile(info)
                for name, pin in files.items():
                    info = tar.gettarinfo(pin["source"], arcname=name)
                    if name == "bundle-lz4":
                        if pin["sha256"] != pins["libbundlelz4.so"]:
                            raise ValueError("emission-codec-pin")
                        info.type, info.size, info.linkname = tarfile.SYMTYPE, 0, native + "/libbundlelz4.so"
                        tar.addfile(info)
                    else:
                        # Sources may be read-only aliases; stage regular bytes.
                        info.type, info.linkname, info.size = tarfile.REGTYPE, "", pin["bytes"]
                        with open(pin["source"], "rb") as stream:
                            tar.addfile(info, stream)
            process.stdin.close()
            if process.wait(timeout=600):
                raise RuntimeError("emission-transfer-failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stderr.close()


def invocation(remote, native, request, attempt):
    python = [native + "/libpythonhost.so", native + "/libpython3.14.so", remote + "/runtime/python"]
    owner = remote + "/repo/tools/phone-build/accepted-output/"
    return [
        "sh",
        "-c",
        'cd "$1" && export LD_LIBRARY_PATH="$2" && shift 2 && exec "$@"',
        "emission",
        remote,
        native + ":" + remote + "/runtime/native-links",
        *python,
        owner + "phone_runner.py",
        "--profile",
        request["profile"],
        "--timeout",
        str(request["timeout_seconds"]),
        "--receipt",
        remote + "/" + attempt + "/thermal.json",
        "--status",
        remote + "/live-thermal.json",
        "--",
        *python,
        owner + "bundle_preload.py",
        "--inputs",
        remote + "/" + request["request"],
        "--output",
        remote + "/" + attempt + "/output",
        "--cache",
        remote + "/cache",
    ]


def collect(phone, state, destination):
    """Small receipts only; generated bundles remain on their device filesystem."""
    result = {}
    for name, suffix in (("emission", "/output/result.json"), ("progress", "/output/emitted/progress.json"), ("thermal", "/thermal.json")):
        path = state["remote"] + "/" + state["attempt"] + suffix
        observed = phone.execute("shell", shlex.join(["run-as", "dev.ror2lab.installertest", "cat", path]), label="emission-" + name, idempotent=True)
        if observed.returncode == 0:
            value = json.loads(observed.stdout)
            write(destination / (name + ".json"), value)
            result[name] = value
    return result


def execute(path, installer, *, dry_run=False, resume=False):
    """Run beneath Runner.execute; its lease spans transfer, wait and cleanup."""
    started = time.monotonic()
    request = json.loads(Path(path).read_bytes())
    done = Path(request["done_file"])
    root = Path(os.environ["LAB_CANONICAL_ROOT"]).resolve()
    if not done.is_absolute() or done != done.resolve() or not done.is_relative_to(root / "work"):
        raise ValueError("emission-absolute-work-done-file-required")
    if dry_run:
        _, files = load_request(path)
        return dict(success=True, dry_run=True, files=len(files), input_bytes=sum(pin["bytes"] for pin in files.values()))
    if done.exists():
        raise ValueError("emission-new-done-file-required")
    destination = done.parent
    destination.mkdir(parents=True, exist_ok=True)
    (destination / ".prune-keep").touch()
    state_path = destination / "device-state.json"
    result = dict(success=False, device_accepted=False, typed_load_accepted=False)
    device = phone = state = None
    job = None
    terminal = False
    previous_work = None
    lease = Path(os.environ["LAB_RUNNER_LEASE"])
    owner = json.loads((lease / "lab-runner.json").read_bytes())
    try:
        request, files = load_request(path)
        import common
        from device_context import command_selectors, set_command_selector

        previous_work, selectors = common.WORK, command_selectors()
        serial = os.environ["LAB_DEVICE_SERIAL"]
        if lease.name != serial or owner["pid"] != os.getppid():
            raise RuntimeError("emission-parent-lease-required")
        common.WORK = root / "work"
        set_command_selector(serial, None)
        from device import Device
        from alpha_stability_batch import _GameThermalOwner

        device = Device(selector=serial)
        storage = device.storage()
        # This operation currently stages symlinked Python extension providers.
        # Emulated external storage cannot preserve those links. Never place
        # staging on a Nova's internal storage as an implicit fallback.
        if storage["mode"] != "internal":
            raise RuntimeError("emission-adopted-external-runtime-staging-unavailable")
        result["storage_before"] = storage
        if resume:
            state = json.loads(state_path.read_bytes())
        active = bool(state and state.get("job") and state.get("terminal") is None)
        if not active:
            required = request["estimated_output_bytes"] + 20 * 1024**3
            if not state or not state.get("staged"):
                required += sum(pin["bytes"] for pin in files.values())
            if storage["internal"]["free_bytes"] < required:
                raise RuntimeError("emission-device-space-budget")
        # Only cooldown observation is reused here; gameplay start/stop methods
        # are never called. The on-phone tool supervisor owns production heat.
        if not active:
            admission = _GameThermalOwner(device, None, destination / "admission.jsonl", time.monotonic() + 1800)
            admission.cool()
            result["admission_battery"] = admission.admission_battery
        result["reattached_without_launch"] = active
        phone = installer.Phone(serial, request["timeout_seconds"])
        apk_hash = request["tool_apk"]["sha256"]
        if resume:
            if (
                state["apk_sha256"] != apk_hash
                or state["manifest_sha256"] != request["manifest"]["sha256"]
                or phone.package_hash(installer.PACKAGE) != apk_hash
            ):
                raise RuntimeError("emission-resume-identity")
            phone.owned_installer, phone.installer_hash = True, apk_hash
        else:
            if phone.occupied(installer.PACKAGE):
                raise RuntimeError("emission-preexisting-package")
            phone.install_volume = "internal"
            phone.install(Path(request["tool_apk"]["path"]))
            home = phone.shell("run-as", installer.PACKAGE, "pwd", label="emission-home").decode().strip()
            details = phone.shell("dumpsys", "package", installer.PACKAGE, label="emission-native-location").decode()
            match = re.search(r"^\s*(?:nativeLibraryDir|legacyNativeLibraryDir)=(/[^\s]+)", details, re.M)
            if not home.startswith(("/data/user/", "/data/data/")) or match is None:
                raise RuntimeError("emission-installed-runtime-location")
            native = match[1]
            probe = phone.execute("shell", shlex.join(["test", "-f", native + "/libpythonhost.so"]), label="emission-native-probe", idempotent=True)
            if probe.returncode:
                native += "/arm64"
            state = dict(
                apk_sha256=apk_hash,
                manifest_sha256=request["manifest"]["sha256"],
                remote=home + "/files/owner-input/emission-" + uuid.uuid4().hex,
                native=native,
            )
            write(state_path, state)  # Ownership survives transfer failure.
            phone.shell("run-as", installer.PACKAGE, "mkdir", "-p", state["remote"], label="emission-input-directory")
            transfer(phone, request["tool_apk"]["path"], files, state["remote"], native)
            state["staged"] = True
            write(state_path, state)
        if not state.get("staged"):
            transfer(phone, request["tool_apk"]["path"], files, state["remote"], state["native"])
            state["staged"] = True
            write(state_path, state)
        phone.storage()  # Installed-code placement and actual app-data backing.
        handle = state.get("job")
        if handle is None or state.get("terminal") is not None:
            admission.cool()  # Installation/streaming may have warmed the device.
            state["attempt"] = "attempt-" + uuid.uuid4().hex
            state.pop("terminal", None)
            phone.shell("run-as", installer.PACKAGE, "mkdir", "-p", state["remote"] + "/" + state["attempt"], label="emission-attempt-directory")

            def persist(handle):
                state["job"] = handle
                write(state_path, state)
                write(lease / "retain.json", dict(reason="emission-remote-outcome-unknown", job=handle, state=str(state_path)))

            job = phone.transport.start_detached(
                invocation(state["remote"], state["native"], request, state["attempt"]),
                root=state["remote"],
                shell_prefix=("run-as", installer.PACKAGE),
                persist=persist,
            )
        else:
            job = installer.TRANSPORT.DetachedJob(**handle)
        observed = phone.transport.wait_detached(job, destination / "logs", timeout=request["timeout_seconds"] + 60, poll_interval=2, capture_logs=False)
        terminal = True
        state["terminal"] = observed.returncode
        write(state_path, state)
        (lease / "retain.json").unlink(missing_ok=True)
        result.update(collect(phone, state, destination))
        emission = result.get("emission", {})
        native_result = emission.get("emission", {})
        count = native_result.get("records", native_result.get("objects"))
        result["success"] = observed.returncode == 0 and native_result.get("structural_accepted") is True and count == request["expected_records"]
        result["records"] = count
        result["bundle"] = {key: emission.get(key) for key in ("bundle", "bytes", "sha256")}
        result["elapsed_seconds"] = time.monotonic() - started
        result["storage_after"] = device.storage()
    except BaseException as error:
        result["error"] = str(error) or type(error).__name__
    finally:
        if phone is not None and phone.owned_installer:
            result["owned_app_and_cache_retained"] = True
        if job is None and state and state.get("job") and state.get("terminal") is None:
            job = installer.TRANSPORT.DetachedJob(**state["job"])
        if job is not None and not terminal:
            write(lease / "retain.json", dict(reason="emission-remote-outcome-unknown", job=job.as_dict(), state=str(state_path)))
            result["lease_retained"] = True
        if device is not None:
            try:
                if not device.display(False):
                    raise RuntimeError("emission-oled-sleep-unverified")
            except BaseException as error:
                result.update(success=False, display_error=str(error))
        if previous_work is not None:
            common.WORK = previous_work
            set_command_selector(*selectors)
        write(done.with_suffix(".operation.json"), result)
    return result
