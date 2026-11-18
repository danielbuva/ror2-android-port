"""Build the pinned managed installer fixture through the shared lab runner."""

import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import tarfile
import time
import uuid
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(path, expected):
    path = Path(path).resolve(strict=True)
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(path) != expected:
        raise ValueError("toolhost input pin mismatch: " + path.name)
    return path


def read_plan(request, checkout):
    stage_pin = request["stage_receipt"]
    receipt = pin(stage_pin["path"], stage_pin["sha256"])
    stage = receipt.parent
    staged = json.loads(receipt.read_bytes())
    files = staged["files"]
    required = {"backend-tools.json", "python-native-plan.json", "build_fixture.py", "apksigner.jar", "release-trust.json"}
    if staged.get("success") is not True or staged.get("game_inputs") is not False or not required <= files.keys():
        raise ValueError("toolhost requires a complete, game-free stage receipt")
    for name, expected in files.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name:
            raise ValueError("toolhost unsafe staged path")
        pin(stage / name, expected)
        if name.startswith("repo/"):
            pin(checkout / name.removeprefix("repo/"), expected)
    root = request["tool_root"]
    if not re.fullmatch(r"/data/local/tmp/[A-Za-z0-9_-][A-Za-z0-9_.-]*", root):
        raise ValueError("toolhost requires an explicit internal tool root")
    if not re.fullmatch(r"[0-9a-f]{64}", request["signer_sha256"]):
        raise ValueError("toolhost requires the retained signer pin")
    backend = json.loads((stage / "backend-tools.json").read_bytes())
    overrides = request.get("native_sources", {})
    if overrides.keys() - backend["natives"].keys():
        raise ValueError("toolhost native override has no plan row")
    transfers = {}
    for name, row in backend["natives"].items():
        source = overrides.get(name, row["path"])
        if name in overrides or not source.startswith(root + "/"):
            path = pin(source, row["sha256"])
            target = f"providers/{name}/{path.name}"
            transfers[target] = path
            row["path"] = "@run/" + target
    python_plan = json.loads((stage / "python-native-plan.json").read_bytes())
    for field in ("python_wheels", "texture_sdk_guest"):
        if field not in backend:
            continue
        for name, expected in python_plan[field].items():
            transfers[f"{field}/{name}"] = pin(Path(backend[field]) / name, expected)
        backend[field] = "@run/" + field
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
    cache_key = hashlib.sha256(json.dumps([commit, request], sort_keys=True).encode()).hexdigest()
    return stage, files, backend, transfers, cache_key, commit


def stage_archive(path, stage, files, backend, transfers, remote, package):
    def target(value):
        return remote + "/" + value.removeprefix("@run/") if value.startswith("@run/") else value

    resolved = dict(backend, package=package, natives={name: dict(row, path=target(row["path"])) for name, row in backend["natives"].items()})
    for field in ("python_wheels", "texture_sdk_guest"):
        if field in resolved:
            resolved[field] = target(resolved[field])
    encoded = json.dumps(resolved).encode()
    with tarfile.open(path, "w") as archive:
        for name, expected in files.items():
            if name == "backend-tools.json":
                info = tarfile.TarInfo("stage/" + name)
                info.size = len(encoded)
                archive.addfile(info, io.BytesIO(encoded))
            else:
                archive.add(pin(stage / name, expected), arcname="stage/" + name)
        for name, source in transfers.items():
            archive.add(source, arcname=name)


def invocation(root, remote):
    python = [root + "/python/usr/bin/python3.14", "-I", "-S"]
    stage = remote + "/stage/"
    paths = ":".join(root + "/" + name for name in ("packaging/usr/lib", "python/usr/lib", "usr/lib"))
    return [
        "env",
        "LD_LIBRARY_PATH=" + paths,
        *python,
        stage + "repo/tools/phone-build/accepted-output/phone_runner.py",
        "--profile",
        "thor",
        "--timeout",
        "1800",
        "--receipt",
        remote + "/thermal.json",
        "--",
        *python,
        stage + "build_fixture.py",
        root,
        root + "/material",
        remote + "/output",
        root + "/archives",
    ]


def verify_apk(apk, stage, files, build, request, package):
    from device import validate_apk_identity

    if build["success"] is not True or digest(apk) != build["apk_sha256"]:
        raise ValueError("toolhost APK receipt mismatch")
    with ZipFile(apk) as archive:
        for name, expected in files.items():
            if (name.startswith("repo/") or name == "release-trust.json") and hashlib.sha256(archive.read("assets/" + name)).hexdigest() != expected:
                raise ValueError("toolhost packaged source drift: " + name)
        for name, expected in build["native_hashes"].items():
            if hashlib.sha256(archive.read("lib/arm64-v8a/" + name)).hexdigest() != expected:
                raise ValueError("toolhost packaged native drift: " + name)
    java = Path(os.environ["UNITY_ANDROID_ROOT"]) / "OpenJDK/bin/java"
    output = subprocess.check_output([java, "-jar", stage / "apksigner.jar", "verify", "--print-certs", apk], text=True)
    signers = re.findall(r"Signer #[0-9]+ certificate SHA-256 digest: ([a-f0-9]+)", output)
    if signers != [request["signer_sha256"]]:
        raise ValueError("toolhost APK signer mismatch")
    validate_apk_identity(apk, package)


def execute(request, plan, out, *, runner, serial, lease, transport_module, package):
    from alpha_stability_batch import _GameThermalOwner
    from device import Device

    stage, files, backend, transfers, cache_key, _ = plan
    root = request["tool_root"]
    remote = root + "/toolhost-" + uuid.uuid4().hex
    transport = transport_module.AdbTransport(runner.adb, serial)
    device = Device(selector=serial, work_root=runner.repo / "work")
    out.mkdir(parents=True, exist_ok=True)

    def shell(*command):
        return transport.run("shell", shlex.join(command), label="toolhost-shell", timeout=180)

    def collect(name, source):
        transport.run("pull", source, out / name, label="toolhost-evidence", timeout=180, idempotent=True)
        return json.loads((out / name).read_bytes())

    storage = device.storage()
    if storage["mode"] != "internal" or storage["internal"]["free_bytes"] < 22 * 1024**3:
        raise ValueError("toolhost requires internal tool storage and 22 GiB free")
    (out / "storage-before.json").write_text(json.dumps(storage) + "\n")
    cooldown = _GameThermalOwner(device, None, out / "admission.jsonl", time.monotonic() + 900)
    cooldown.cool()
    archive = out / "stage.tar"
    job = None
    terminal = False
    created = False
    try:
        stage_archive(archive, stage, files, backend, transfers, remote, package)
        shell("mkdir", "-m", "700", remote)
        created = True
        transport.run("push", archive, remote + "/stage.tar", label="toolhost-stage", timeout=300, idempotent=True)
        shell("tar", "-xf", remote + "/stage.tar", "-C", remote)
        shell("rm", remote + "/stage.tar")

        def persist(handle):
            (lease / "retain.json").write_text(json.dumps(dict(job=handle, remote=remote, output=str(out))) + "\n")

        job = transport.start_detached(invocation(root, remote), label="toolhost-build", persist=persist)
        observed = transport.wait_detached(job, out / "logs", label="toolhost-build", timeout=1860, poll_interval=2, capture_logs=False)
        terminal = True
        thermal = collect("thermal.json", remote + "/thermal.json")
        build = collect("build-receipt.json", remote + "/output/build-receipt.json")
        if observed.returncode or thermal["success"] is not True:
            raise ValueError("toolhost supervised build failed")
        apk = out / "signed.apk"
        transport.run("pull", remote + "/output/signed.apk", apk, label="toolhost-apk", timeout=300, idempotent=True)
        verify_apk(apk, stage, files, build, request, package)
    finally:
        archive.unlink(missing_ok=True)
        if terminal:
            transport.cleanup_detached(job)
            (lease / "retain.json").unlink(missing_ok=True)
        if created and (job is None or terminal) and not (lease / "retain.json").exists():
            shell("rm", "-rf", remote)
            (out / "storage-after.json").write_text(json.dumps(device.storage()) + "\n")
    return dict(success=True, apk_sha256=build["apk_sha256"], cache_key=cache_key)
