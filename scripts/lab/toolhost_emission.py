"""Current shared-runner operations for pinned on-phone bundle and code producers.

The lab runner owns the device lease. Installer Phone owns exact-APK admission;
Device owns storage/display policy; phone_runner owns thermal duty cycling. No
private Python driver is staged or executed. Receipts contain private paths and
stay under ignored work/. A terminal producer failure retains its app and cache.
"""

from bisect import bisect_left, bisect_right
import hashlib
import importlib.util
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

from evidence_files import open_evidence

SIGNED_CODE = "signed-code"
SIGNED_NATIVE = "signed-native"
CODE_OPERATIONS = (SIGNED_CODE, SIGNED_NATIVE)
BUNDLE_DECODE = "bundle-decode"
CONVERTER_STAGE = "converter-stage"
STAGE_OWNER = "tools/phone-build/owner-apk/lab_stage.py"
STAGE_SUPPORT = {
    STAGE_OWNER,
    "tools/phone-build/accepted-output/phone_runner.py",
    *("tools/phone-build/owner-apk/" + name + ".py" for name in ("release_jobs", "updates", "release", "release_source", "alpha_policy", "atomic_io")),
}
DECODE_OWNER = "repo/tools/phone-build/accepted-output/"
DECODE_BASELINE = "baseline-unity_bundle.py"
DECODE_FILES = {DECODE_BASELINE, *(DECODE_OWNER + name for name in ("bundle_decode_benchmark.py", "unity_bundle.py", "phone_runner.py"))}
RESOURCE_TRACE = "phase-resources.jsonl"
RESOURCE_SUMMARY = "phase-resources.json"
THERMAL_KINDS = ("cpu", "gpu", "soc", "battery", "skin")
NET8_LIBRARIES = (
    "libcoreclr.so",
    "libhostpolicy.so",
    "libSystem.Native.so",
    "libSystem.Globalization.Native.so",
    "libSystem.IO.Compression.Native.so",
    "libSystem.Net.Security.Native.so",
    "libSystem.Security.Cryptography.Native.Android.so",
    "libSystem.Security.Cryptography.Native.OpenSsl.so",
)


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


def load_request(path, *, refresh_repo=False):
    request = json.loads(Path(path).read_bytes())
    required = {"runner", "tool_apk", "manifest", "request", "done_file", "expected_records", "estimated_output_bytes", "profile", "timeout_seconds"}
    operation = request.get("operation")
    signed_code = operation in CODE_OPERATIONS
    decode = operation == BUNDLE_DECODE
    stage = operation == CONVERTER_STAGE
    count = "expected_managed_providers" if signed_code else "expected_blocks" if decode else "expected_records"
    if signed_code or decode:
        required = (required - {"expected_records"}) | {"operation", count}
    if signed_code and "profile_resources" in request:
        if type(request["profile_resources"]) is not bool:
            raise ValueError("signed-code-resource-profile-selector")
        required.add("profile_resources")
    if decode:
        required |= {"expected_decoded_sha256", "retained_tool_sha256"}
    if stage:
        required = (required - {"expected_records"}) | {"operation", "retained_tool_sha256"}
    if "retained_tool_sha256" in request:
        required.add("retained_tool_sha256")
        previous = request["retained_tool_sha256"]
        if not isinstance(previous, str) or not re.fullmatch(r"[0-9a-f]{64}", previous):
            raise ValueError("emission-retained-tool-pin")
        if not signed_code and previous != request["tool_apk"]["sha256"]:
            raise ValueError("emission-bundle-retained-tool-must-match-apk")
    if set(request) != required or request["profile"] not in ("nova", "thor"):
        raise ValueError("emission-request-contract")
    if decode and not re.fullmatch(r"[0-9a-f]{64}", request["expected_decoded_sha256"]):
        raise ValueError("emission-decode-result-pin")
    for key in ("tool_apk", "manifest"):
        pin = request[key]
        if set(pin) != {"path", "sha256"} or digest(pin["path"]) != pin["sha256"]:
            raise ValueError("emission-input-pin")
    for name in ("estimated_output_bytes", "timeout_seconds", *(() if stage else (count,))):
        if type(request[name]) is not int or request[name] <= 0:
            raise ValueError("emission-positive-budget-required")
    relative(request["request"])
    manifest = json.loads(Path(request["manifest"]["path"]).read_bytes())
    files = manifest["files"]
    if request["request"] not in files:
        raise ValueError("emission-request-not-staged")
    if decode and not DECODE_FILES <= files.keys():
        raise ValueError("emission-decode-producer-not-staged")
    if stage and (request["request"] != "stage.json" or any(name != "stage.json" and not name.startswith("repo/") for name in files)):
        raise ValueError("converter-stage-must-transfer-only-producers-and-descriptor")
    for name, pin in files.items():
        relative(name)
        if refresh_repo and name.startswith("repo/"):
            continue  # Explicit refresh replaces these pins from a clean commit.
        path = Path(pin["source"])
        if path.stat().st_size != pin["bytes"] or digest(path) != pin["sha256"]:
            raise ValueError("emission-staged-input-pin")
    if signed_code:
        root = relative(request["request"]).parent
        code = json.loads(Path(files[request["request"]]["source"]).read_bytes())
        required_code = {"source_inputs", "audio_members", "output"}
        private_files = ("input-hashes.json", "work/inventory/files.json")
        if operation == SIGNED_NATIVE:
            required_code = {"bundle", "envelope", "public_key", "key_id", "output"}
            if set(code) == required_code:
                private_files += tuple(relative(code[key]) for key in ("bundle", "envelope", "public_key"))
        if set(code) != required_code or any((root / name).as_posix() not in files for name in private_files):
            raise ValueError("signed-code-staged-input-contract")
        relative(code["output"])
    return request, files


def repin_producers(files, checkout):
    checkout = Path(checkout).resolve()

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(checkout), *arguments])

    if Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() != checkout:
        raise ValueError("emission-checkout-root-required")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("emission-clean-producer-checkout-required")
    tracked = set(git("ls-files", "-z").decode().split("\0"))
    commit = git("rev-parse", "HEAD").decode().strip()
    replaced = 0
    for name in files:
        if name.startswith("repo/"):
            local = name.removeprefix("repo/")
            if local not in tracked:
                raise ValueError("emission-tracked-producer-required")
            source = checkout / local
            files[name] = dict(source=str(source), bytes=source.stat().st_size, sha256=digest(source))
            replaced += 1
    return checkout, commit, replaced


def refresh_manifest(path, checkout):
    """Explicit host-only producer update; retain every pinned non-repo input."""
    request, files = load_request(path, refresh_repo=True)
    checkout, commit, replaced = repin_producers(files, checkout)
    manifest_path = Path(request["manifest"]["path"])
    manifest = json.loads(manifest_path.read_bytes())
    manifest.update(files=files, bytes=sum(pin["bytes"] for pin in files.values()), source_checkout=str(checkout), source_commit=commit)
    write(manifest_path, manifest)
    request["manifest"]["sha256"] = digest(manifest_path)
    request["runner"]["ref"] = commit
    write(path, request)
    return dict(success=True, refreshed_repo_files=replaced, input_bytes=manifest["bytes"], source_commit=commit)


def prepare_stage(path, checkout, name, *, dry_run):
    request, files = load_request(path, refresh_repo=True)
    if request.get("operation") != CONVERTER_STAGE:
        raise ValueError("converter-stage-request-required")
    spec = importlib.util.spec_from_file_location("phone_lab_stage", checkout / STAGE_OWNER)
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    stage = owner.load_stage(files["stage.json"]["source"])
    if Path(stage["producer"]).stem.replace("_", "-") != name:
        raise ValueError("converter-stage-name-mismatch")
    for producer in (*STAGE_SUPPORT, stage["producer"], *owner.PRODUCER_SUPPORT.get(stage["producer"], ())):
        files["repo/" + producer] = {}
    checkout, commit, _ = repin_producers(files, checkout)
    done = Path(request["done_file"])
    canonical = Path(request["runner"]["repo"]).resolve()
    if not done.is_absolute() or done != done.resolve() or not done.is_relative_to(canonical / "work") or done.exists():
        raise ValueError("emission-new-absolute-work-done-file-required")
    if dry_run:
        print(
            json.dumps(
                dict(
                    success=True,
                    dry_run=True,
                    producer=name,
                    source_commit=commit,
                    files=len(files),
                    transfer_bytes=sum(pin["bytes"] for pin in files.values()),
                )
            )
        )
        return None
    manifest = done.with_suffix(".manifest.json")
    write(manifest, dict(files=files, source_commit=commit))
    request.update(manifest=dict(path=str(manifest), sha256=digest(manifest)))
    request["runner"].update(ref=commit, local_ref=True)
    prepared = done.with_suffix(".request.json")
    write(prepared, request)
    return prepared


def transfer(phone, apk, files, remote, native, *, signed_code=False, signed_native=False):
    """Stream pinned inputs/runtime once, without another host copy or archive."""
    with zipfile.ZipFile(apk) as archive:
        pins = json.loads(archive.read("assets/native-hashes.json"))
        links = json.loads(archive.read("assets/python-links.json"))
        roots = ("python/",)
        link_roots = ("python/", "native-links/")
        if signed_code:
            roots += ("dotnet/", "clang/21/")
            link_roots += ("dotnet/",)
            links.update({"dotnet/shared/Microsoft.NETCore.App/8.0.32/" + lib: lib for lib in NET8_LIBRARIES})
            links.update({"native-links/libcrypto.so.3": "libcrypto.so", "native-links/libssl.so.3": "libssl.so"})
        if signed_native:
            roots += ("gnu/", "data-hashes.json")
            for name in ("assets/gnu/libgnu-tool-adapter.so", "assets/data-hashes.json"):
                archive.getinfo(name)
        command = shlex.join(["run-as", "dev.ror2lab.installertest", "tar", "-xf", "-", "-C", remote])
        process = subprocess.Popen(
            [str(phone.adb), "-s", phone.serial, "shell", command], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        try:
            with tarfile.open(fileobj=process.stdin, mode="w|", format=tarfile.GNU_FORMAT) as tar:
                for name in archive.namelist():
                    if name.startswith(tuple("assets/" + root for root in roots)) and not name.endswith("/"):
                        info = tarfile.TarInfo("runtime/" + name.removeprefix("assets/"))
                        info.size, info.mode = archive.getinfo(name).file_size, 0o600
                        with archive.open(name) as stream:
                            tar.addfile(info, stream)
                for name, target in links.items():
                    if name.startswith(link_roots):
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
                if signed_code:
                    info = tarfile.TarInfo("runtime/repo")
                    info.type, info.linkname = tarfile.SYMTYPE, "../repo"
                    tar.addfile(info)
            process.stdin.close()
            if process.wait(timeout=600):
                raise RuntimeError("emission-transfer-failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stderr.close()


def invocation(remote, native, request, attempt, *, owner_input=None):
    runtime = remote + "/runtime"
    python = [native + "/libpythonhost.so", native + "/libpython3.14.so", runtime + "/python"]
    owner = remote + "/repo/tools/phone-build/"
    environment = ["LD_LIBRARY_PATH=" + native + ":" + runtime + "/native-links"]
    if request.get("operation") == CONVERTER_STAGE:
        producer = [
            remote + "/repo/" + STAGE_OWNER,
            remote + "/" + request["request"],
            remote + "/repo",
            owner_input,
            remote + "/" + attempt + "/artifacts",
            native,
            runtime,
            remote + "/" + attempt + "/stage.json",
            *python,
        ]
    elif request.get("operation") in CODE_OPERATIONS:
        environment += [
            "ROR2LAB_BUILD_DOTNET_ROOT=" + runtime + "/dotnet",
            "ROR2LAB_BUILD_HOSTFXR=" + native + "/libhostfxr10.so",
            "ROR2LAB_BUILD_DOTNET_LAUNCHER=" + native + "/libdotnetmuxer.so",
            "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1",
            "DOTNET_MULTILEVEL_LOOKUP=0",
        ]
        producer = [owner + "owner-code/run_android.py", remote + "/" + request["request"], runtime, native]
    elif request.get("operation") == BUNDLE_DECODE:
        producer = [
            owner + "accepted-output/bundle_decode_benchmark.py",
            remote + "/" + request["request"],
            remote + "/" + DECODE_BASELINE,
            remote + "/" + attempt + "/decode.json",
        ]
    else:
        producer = [
            owner + "accepted-output/bundle_preload.py",
            "--inputs",
            remote + "/" + request["request"],
            "--output",
            remote + "/" + attempt + "/output",
            "--cache",
            remote + "/cache",
            # The APK's Python lacks _multiprocessing; host emission stays parallel.
            "--workers",
            "1",
        ]
    return [
        "sh",
        "-c",
        # Android env treats the '=' in PackageManager paths as an assignment.
        'cd "$1" || exit; shift; while [ "$1" != -- ]; do export "$1" || exit; shift; done; shift; exec "$@"',
        "emission",
        remote,
        *environment,
        "--",
        *python,
        owner + "accepted-output/phone_runner.py",
        "--profile",
        request["profile"],
        "--timeout",
        str(request["timeout_seconds"]),
        "--receipt",
        remote + "/" + attempt + "/thermal.json",
        "--status",
        remote + "/live-thermal.json",
        *(["--samples", remote + "/" + attempt + "/" + RESOURCE_TRACE] if request.get("profile_resources") else []),
        "--",
        *python,
        *producer,
    ]


def collect(phone, state, destination, *, code_output=None, decode=False, stage=False, signed_native=False, failed=False):
    """Small receipts only; generated bundles remain on their device filesystem."""
    result = {}
    attempt = state["attempt"]
    receipts = {"thermal": attempt + "/thermal.json"}
    if stage:
        receipts.update(stage=attempt + "/stage.json", scoreboard=attempt + "/scoreboard.json")
    elif decode:
        receipts["decode"] = attempt + "/decode.json"
    elif code_output is None:
        receipts.update(emission=attempt + "/output/result.json", progress=attempt + "/output/emitted/progress.json")
    elif signed_native:
        receipts["native_release"] = code_output + "/result.json"
    else:
        receipts.update(
            code=code_output + "/result.json",
            converter=code_output + "/backend/converter/result.json",
            measurements=code_output + "/android-measurements.json",
        )
        if failed:
            receipts["managed"] = code_output + "/managed-production/result.json"
    for name, suffix in receipts.items():
        path = state["remote"] + "/" + suffix
        observed = phone.execute("shell", shlex.join(["run-as", "dev.ror2lab.installertest", "cat", path]), label="emission-" + name, idempotent=True)
        if observed.returncode == 0:
            value = json.loads(observed.stdout)
            filename = "code-result.json" if name == "code" else name + ".json"
            write(destination / filename, value)
            result[name] = value
    return result


def collect_evidence(phone, package, state, destination, *, code_output, failed, jobs_root=None):
    """Keep producer logs, timings and crash artifacts before deleting owned scratch."""
    if failed:
        crash = destination / "logs/crash"
        crash.mkdir(parents=True, exist_ok=True)
        # Android exposes native tombstone reports in the crash buffer. Physical
        # /data/tombstones files are normally inaccessible on retail devices.
        for name, argv in (
            ("crash.log", ["logcat", "-b", "crash", "-d", "-v", "threadtime"]),
            ("exit-info.txt", ["shell", "dumpsys", "activity", "exit-info", package]),
            ("tombstone-access.txt", ["shell", "ls", "/data/tombstones"]),
        ):
            observed = phone.execute(*argv, label="emission-" + name, idempotent=True)
            (crash / name).write_bytes(observed.stdout if not observed.returncode else observed.stderr)
    output_roots = [state["attempt"]]
    if code_output is not None:
        output_roots.append(code_output)
    if jobs_root is not None:
        output_roots.append(jobs_root)
    command = r"""
cd "$1" || exit
shift
for dir do
    if [ -d "$dir" ]; then
        find "$dir" -type f \( -path '*/logs/*' -o -name '*.log' -o -name '*.process.json' -o -name 'phase-resources.jsonl' \
            -o -iname 'tombstone_[0-9][0-9]' -o -iname 'tombstone_[0-9][0-9].pb' -o -name 'hs_err_pid*.txt' \) -print0 || exit
    fi
done
"""
    prefix = ["run-as", package]
    remote = state["remote"]
    listed = phone.execute(
        "shell", shlex.join([*prefix, "sh", "-c", command, "emission", remote, *output_roots]), label="emission-evidence-list", idempotent=True
    )
    if listed.returncode:
        raise RuntimeError("emission-evidence-list-failed")
    for name in filter(None, listed.stdout.split(b"\0")):
        path = relative(os.fsdecode(name))
        if not any(path.is_relative_to(root) for root in output_roots):
            raise RuntimeError("emission-evidence-path")
        target = destination / "logs/producer" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".partial")
        try:
            with temporary.open("wb") as stream:
                pulled = subprocess.run(
                    [str(phone.adb), "-s", phone.serial, "shell", "-T", shlex.join([*prefix, "cat", remote + "/" + path.as_posix()])],
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=False,
                )
            if pulled.returncode:
                raise RuntimeError("emission-evidence-pull-failed")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def summarize_resources(trace, code_output):
    """Join captured producer-tree samples to subprocess BOOTTIME windows."""
    with open_evidence(trace) as stream:
        samples = [json.loads(line) for line in stream]
    ticks = [sample["boottime_seconds"] for sample in samples]
    if any(left > right for left, right in zip(ticks, ticks[1:])):
        raise ValueError("resource trace BOOTTIME moved backwards")

    stages, unclocked = [], []
    for path in sorted(code_output.rglob("*.process.json")):
        name = path.relative_to(code_output).as_posix()
        process = json.loads(path.read_bytes())
        start, end = process.get("started_boottime_seconds"), process.get("ended_boottime_seconds")
        if start is None or end is None:
            unclocked.append(name)
            continue
        if end < start:
            raise ValueError("reversed subprocess BOOTTIME window: " + name)
        left, right = bisect_left(ticks, start), bisect_right(ticks, end)
        window = samples[left:right]
        resources = [sample for sample in window if "process_tree_rss_bytes" in sample]
        volume = [sample["volume_available_bytes"] for sample in resources]
        boundaries = [start, *ticks[left:right], end]
        stages.append(
            dict(
                process=name,
                exit_code=process.get("exit_code"),
                started_boottime_seconds=start,
                ended_boottime_seconds=end,
                boottime_elapsed_seconds=end - start,
                observed_pause_seconds=process.get("paused_seconds"),
                samples=len(window),
                paused_samples=sum(sample["paused"] for sample in window),
                largest_sample_gap_seconds=max(right - left for left, right in zip(boundaries, boundaries[1:])),
                resource_samples=len(resources),
                sampled_peak_celsius={
                    kind: max((sample[kind + "_celsius"] for sample in window if sample.get(kind + "_celsius") is not None), default=None)
                    for kind in THERMAL_KINDS
                },
                sampled_process_tree_rss_peak_bytes=max((sample["process_tree_rss_bytes"] for sample in resources), default=None),
                sampled_volume_available_bytes=dict(
                    first=volume[0] if volume else None, minimum=min(volume, default=None), last=volume[-1] if volume else None
                ),
            )
        )
    stages.sort(key=lambda stage: stage["started_boottime_seconds"])
    return dict(samples=len(samples), stages=stages, unclocked_process_receipts=unclocked)


def execute(path, installer, *, dry_run=False, resume=False, restage=False):
    """Run beneath Runner.execute; its lease spans transfer, wait and cleanup."""
    started = time.monotonic()
    request = json.loads(Path(path).read_bytes())
    signed_native = request.get("operation") == SIGNED_NATIVE
    signed_code = request.get("operation") in CODE_OPERATIONS
    decode = request.get("operation") == BUNDLE_DECODE
    stage = request.get("operation") == CONVERTER_STAGE
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
    result = dict(success=False, device_accepted=False)
    if signed_code or decode or stage:
        result["operation"] = request["operation"]
    else:
        result.update(typed_load_accepted=False, record_workers=1)
    device = phone = state = None
    job = None
    terminal = False
    retained_tool = False
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
        if (signed_code or stage) and (restage or (resume and not active)):
            raise RuntimeError("signed-code-resume-requires-active-handle")
        if state and state.get("retained_tool") and not active:
            raise RuntimeError("emission-retained-tool-requires-fresh-request")
        if restage and (not resume or active or state.get("terminal") is None):
            raise RuntimeError("emission-restage-confirmed-terminal-required")
        if not active:
            required = request["estimated_output_bytes"] + 20 * 1024**3
            if restage or not state or not state.get("staged"):
                required += sum(pin["bytes"] for pin in files.values())
            if storage["internal"]["free_bytes"] < required:
                raise RuntimeError("emission-device-space-budget")
        # Only cooldown observation is reused here; gameplay start/stop methods
        # are never called. The on-phone tool supervisor owns production heat.
        if not active:
            admission_options = {"charge_override": False} if stage else {}
            admission = _GameThermalOwner(device, None, destination / "admission.jsonl", time.monotonic() + 1800, **admission_options)
            admission.cool()
            result["admission_battery"] = admission.admission_battery
        result["reattached_without_launch"] = active
        phone = installer.Phone(serial, request["timeout_seconds"])
        apk_hash = request["tool_apk"]["sha256"]
        if resume:
            if (
                state["apk_sha256"] != apk_hash
                or (not restage and state["manifest_sha256"] != request["manifest"]["sha256"])
                or phone.package_hash(installer.PACKAGE) != apk_hash
            ):
                raise RuntimeError("emission-resume-identity")
            retained_tool = state.get("retained_tool", False)
            phone.owned_installer, phone.installer_hash = not retained_tool, apk_hash
            if restage:
                # Explicit producer qualification replaces only this receipt's
                # confirmed-terminal scratch. Unknown jobs never reach here.
                previous = state["remote"]
                parent, separator, name = previous.rpartition("/files/owner-input/emission-")
                if not separator or not parent.startswith(("/data/user/", "/data/data/")) or not re.fullmatch(r"[0-9a-f]{32}", name):
                    raise RuntimeError("emission-restage-owned-root-required")
                phone.shell("run-as", installer.PACKAGE, "rm", "-rf", previous, label="emission-retire-staging")
                state = dict(
                    apk_sha256=apk_hash, manifest_sha256=request["manifest"]["sha256"], remote=parent + separator + uuid.uuid4().hex, native=state["native"]
                )
                write(state_path, state)
                phone.shell("run-as", installer.PACKAGE, "mkdir", "-p", state["remote"], label="emission-input-directory")
                result["restaged_after_terminal"] = True
        else:
            apk = Path(request["tool_apk"]["path"])
            previous = request.get("retained_tool_sha256")
            if phone.occupied(installer.PACKAGE):
                if not previous or phone.package_hash(installer.PACKAGE) != previous:
                    raise RuntimeError("emission-preexisting-package")
                retained_tool = True
                if previous != apk_hash:
                    # PackageManager enforces the existing signer on replacement.
                    # Preserve the earlier run's data and never claim app cleanup.
                    from device import validate_apk_identity

                    validate_apk_identity(apk, installer.PACKAGE)
                    phone.transport.install(
                        apk,
                        "internal",
                        label="emission-update-retained-tool",
                        timeout=600,
                        reconcile=lambda: phone.package_hash(installer.PACKAGE) == apk_hash,
                    )
            else:
                if previous and not signed_code:
                    raise RuntimeError("emission-retained-tool-not-installed")
                phone.install_volume = "internal"
                phone.install(apk)
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
                retained_tool=retained_tool,
            )
            write(state_path, state)  # Ownership survives transfer failure.
            phone.shell("run-as", installer.PACKAGE, "mkdir", "-p", state["remote"], label="emission-input-directory")
        if not state.get("staged"):
            transfer(phone, request["tool_apk"]["path"], files, state["remote"], state["native"], signed_code=signed_code, signed_native=signed_native)
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

            invocation_options = {"owner_input": str(Path(state["remote"]).parent)} if stage else {}
            job = phone.transport.start_detached(
                invocation(state["remote"], state["native"], request, state["attempt"], **invocation_options),
                root=state["remote"],
                shell_prefix=("run-as", installer.PACKAGE),
                persist=persist,
            )
        else:
            job = installer.TRANSPORT.DetachedJob(**handle)
        observed = phone.transport.wait_detached(
            job, destination / "logs", timeout=request["timeout_seconds"] + 60, poll_interval=2, capture_logs=False, transfer_logs=not stage
        )
        code_output = None
        if signed_code:
            code_request = json.loads(Path(files[request["request"]]["source"]).read_bytes())
            code_output = (relative(request["request"]).parent / "work" / relative(code_request["output"])).as_posix()
        try:
            if stage:
                result.update(collect(phone, state, destination, stage=True))
                report = result.get("stage", {})
                result["transfer_bytes"] = sum(pin["bytes"] for pin in files.values())
                result["success"] = observed.returncode == 0 and report.get("success") is True and "thermal" in result
                if not result["success"]:
                    result["first_failure"] = (
                        report.get("first_failure")
                        or result.get("thermal", {}).get("error")
                        or f"converter stage exit {observed.returncode} or missing receipt"
                    )
            elif signed_native:
                result.update(collect(phone, state, destination, code_output=code_output, signed_native=True, failed=observed.returncode != 0))
                report = result.get("native_release", {})
                result["success"] = (
                    observed.returncode == 0
                    and report.get("success") is True
                    and report.get("phase") == "native-built"
                    and report.get("managed_providers") == request["expected_managed_providers"]
                    and "thermal" in result
                )
            elif signed_code:
                result.update(collect(phone, state, destination, code_output=code_output, failed=observed.returncode != 0))
                code = result.get("code", {})
                backend, converter = code.get("backend", {}), result.get("converter", {})
                result["success"] = (
                    observed.returncode == 0
                    and code.get("success") is True
                    and code.get("phase") == "converted-native-planned"
                    and code.get("upstream_managed_generation_qualified") is True
                    and code.get("managed_providers") == request["expected_managed_providers"]
                    and backend.get("native", {}).get("success") is True
                    and converter.get("inputs_unchanged") is True
                    and converter.get("input_assemblies") == backend.get("stripped_assemblies")
                    and "data/Metadata/global-metadata.dat" in converter.get("files", {})
                    and "measurements" in result
                    and "thermal" in result
                )
            elif decode:
                result.update(collect(phone, state, destination, decode=True))
                report = result.get("decode", {})
                result["success"] = (
                    observed.returncode == 0
                    and report.get("blocks") == request["expected_blocks"]
                    and report.get("decoded_sha256") == request["expected_decoded_sha256"]
                    and "thermal" in result
                )
            else:
                result.update(collect(phone, state, destination))
                emission = result.get("emission", {})
                native_result = emission.get("emission", {})
                count = native_result.get("records", native_result.get("objects"))
                result["success"] = observed.returncode == 0 and native_result.get("structural_accepted") is True and count == request["expected_records"]
                result["records"] = count
                result["bundle"] = {key: emission.get(key) for key in ("bundle", "bytes", "sha256")}
        finally:
            jobs_root = (relative(request["request"]).parent / "work/releases/jobs").as_posix() if signed_native else None
            if not stage:
                collect_evidence(phone, installer.PACKAGE, state, destination, code_output=code_output, failed=not result["success"], jobs_root=jobs_root)
            if request.get("profile_resources"):
                evidence = destination / "logs/producer"
                try:
                    profile = summarize_resources(evidence / state["attempt"] / RESOURCE_TRACE, evidence / (jobs_root or code_output))
                    write(destination / RESOURCE_SUMMARY, profile)
                    result["phase_resource_summary"] = RESOURCE_SUMMARY
                except (OSError, ValueError, KeyError, TypeError) as error:
                    result["phase_resource_summary_error"] = str(error)
        state["terminal"] = observed.returncode
        write(state_path, state)
        terminal = True
        (lease / "retain.json").unlink(missing_ok=True)
        result["elapsed_seconds"] = time.monotonic() - started
        result["storage_after"] = device.storage()
    except BaseException as error:
        result["success"] = False
        result["error"] = str(error) or type(error).__name__
    finally:
        if job is None and state and state.get("job") and state.get("terminal") is None:
            job = installer.TRANSPORT.DetachedJob(**state["job"])
        if job is not None and not terminal:
            write(lease / "retain.json", dict(reason="emission-remote-outcome-unknown", job=job.as_dict(), state=str(state_path)))
            result["lease_retained"] = True
        if retained_tool and state and (terminal or job is None):
            try:
                remote = state["remote"]
                if not re.fullmatch(r"/data/(?:user/[0-9]+|data)/dev\.ror2lab\.installertest/files/owner-input/emission-[0-9a-f]{32}", remote):
                    raise RuntimeError("emission-retained-scratch-root-required")
                if phone.package_hash(installer.PACKAGE) != apk_hash:
                    raise RuntimeError("emission-retained-tool-cleanup-identity")
                phone.shell("run-as", installer.PACKAGE, "rm", "-rf", remote, label="emission-retained-scratch-cleanup")
                result["retained_tool_preserved"] = True
            except BaseException as error:
                result.update(success=False, cleanup_error=str(error))
        elif phone is not None and phone.owned_installer:
            if signed_code and (terminal or job is None):
                try:
                    phone.remove_owned_installer()
                    result["owned_app_removed"] = True
                except BaseException as error:
                    result.update(success=False, cleanup_error=str(error), owned_app_and_cache_retained=True)
            else:
                result["owned_app_and_cache_retained"] = True
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
