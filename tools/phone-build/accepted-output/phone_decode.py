"""PRIVATE streamed accepted-output reconstruction. No Unity/editor/game execution.

stdin: magic, big-endian manifest length, exact pinned manifest, then each
manifest-selected SDK input or compressed patch frame in target order.
Protected target information in the private package is not a public recipe.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import select
import signal
import struct
import subprocess
import sys
import time
import zipfile
import zlib

MANIFEST_SHA = "93789f88d8fff178e31e1a4b78bc5cf735bb63f6e17d8bfd4518474dbff99d4a"
INPUT_MANIFEST_SHA = "28984aca38ad5d7d5052f7489de4fffeb00ca44b03f149caecc9e94133232160"
CODEC_SHA = "721a84f550c0261d6808c9ba82f03ace65890248f7b43b51ca19ff778e201442"
INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
MIN_DISK = 2 * 1024**3
MIN_RAM = 512 * 1024**2
MAX_RSS = 512 * 1024**2
MAX_SECONDS = 900
started = time.monotonic()
last_guard = 0
child = None


def owned_paths(work, inputs, input_manifest, owner):
    """Admit canonical receipt-owned paths before opening any output."""
    paths = (work, inputs, input_manifest, owner)
    for path in paths:
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("noncanonical owned path refused")
        for component in (path, *path.parents):
            if component.is_symlink():
                raise ValueError("symlink path refused")
    try:
        canonical_owner = owner.resolve(strict=True)
        canonical = tuple(path.resolve(strict=True) for path in paths[:3])
    except FileNotFoundError:
        raise ValueError("selected roots absent") from None
    if any(not path.is_relative_to(canonical_owner) for path in canonical):
        raise ValueError("path outside owned workspace")
    work, inputs, input_manifest = canonical
    if not canonical_owner.is_dir() or not work.is_dir() or not inputs.is_dir() or not input_manifest.is_file():
        raise ValueError("selected roots absent or wrong type")
    return work, inputs, input_manifest, canonical_owner


resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
work, inputs, input_manifest, owner = [Path(x) for x in sys.argv[1:5]]
if not re.fullmatch(r"/data/local/tmp/ror2-phone-proof-[0-9a-f]{32}", str(owner)):
    raise ValueError("unexpected owned workspace")
work, inputs, input_manifest, owner = owned_paths(work, inputs, input_manifest, owner)
result = {
    "schema": 1,
    "success": False,
    "independent_owner_input_producer": False,
    "public_distribution_qualified": False,
    "game_or_editor_executed": False,
    "installs": 0,
    "targets_verified": 0,
    "peak_sampled_family_rss": 0,
    "minimum_free": None,
    "minimum_available_ram": None,
    "compressed_stream_bytes": 0,
    "sdk_stream_bytes": 0,
}


def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def safe(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or str(rel) != name:
        raise ValueError("unsafe manifest path")
    p = root
    for part in rel.parts:
        p = p / part
        if p.is_symlink():
            raise ValueError("symlink component refused")
    return p


def rss(pid):
    try:
        for line in Path("/proc/" + str(pid) + "/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except FileNotFoundError:
        pass
    return 0


def guard(force=False):
    global last_guard
    now = time.monotonic()
    if not force and now - last_guard < 0.2:
        return
    last_guard = now
    if now - started > MAX_SECONDS:
        raise RuntimeError("900s deadline exceeded")
    st = os.statvfs(work)
    free = st.f_bavail * st.f_frsize
    available = next(int(x.split()[1]) * 1024 for x in Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:"))
    family = rss(os.getpid()) + (rss(child.pid) if child and child.poll() is None else 0)
    result["peak_sampled_family_rss"] = max(result["peak_sampled_family_rss"], family)
    result["minimum_free"] = free if result["minimum_free"] is None else min(free, result["minimum_free"])
    result["minimum_available_ram"] = available if result["minimum_available_ram"] is None else min(available, result["minimum_available_ram"])
    if free < MIN_DISK:
        raise RuntimeError("2 GiB disk reserve reached")
    if available < MIN_RAM:
        raise RuntimeError("512 MiB available RAM reserve reached")
    if family > MAX_RSS:
        raise RuntimeError("512 MiB process-family RSS limit reached")


wire = sys.stdin.fileno()


def cancelled(signum, frame):
    raise InterruptedError("owned reconstruction cancelled")


signal.signal(signal.SIGTERM, cancelled)
signal.signal(signal.SIGINT, cancelled)
with (work / "process.json").open("x") as process_record:
    json.dump({"pid": os.getpid(), "driver_sha256": sha(Path(__file__))}, process_record)
    process_record.write("\n")


def read_exact(count):
    output = bytearray()
    while len(output) < count:
        guard()
        if not select.select([wire], [], [], 0.2)[0]:
            continue
        chunk = os.read(wire, min(65536, count - len(output)))
        if not chunk:
            raise EOFError("truncated stream")
        output.extend(chunk)
    return bytes(output)


def copy_stream(count, dest):
    h = hashlib.sha256()
    with dest.open("xb") as f:
        while count:
            chunk = read_exact(min(count, 65536))
            f.write(chunk)
            h.update(chunk)
            count -= len(chunk)
    return h.hexdigest()


def decode_stream(row, dest, codec, reference):
    global child
    command = [str(codec), "-d", "-q", "-c", "--memory=256MB"]
    if reference is not None:
        command += ["--patch-from", str(reference)]
    command += ["-"]
    digest = hashlib.sha256()
    remaining = row["patch_bytes"]
    pending = b""
    with dest.open("xb") as output:
        child = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        os.set_blocking(child.stdin.fileno(), False)
        try:
            while remaining or pending:
                guard()
                if child.poll() is not None:
                    raise RuntimeError("decoder terminated before consuming frame")
                readers = [wire] if remaining and len(pending) < 65536 else []
                writers = [child.stdin.fileno()] if pending else []
                ready_read, ready_write, _ = select.select(readers, writers, [], 0.2)
                if ready_read:
                    data = os.read(wire, min(65536 - len(pending), remaining))
                    if not data:
                        raise EOFError("truncated compressed frame")
                    digest.update(data)
                    remaining -= len(data)
                    pending += data
                if ready_write and pending:
                    try:
                        pending = pending[os.write(child.stdin.fileno(), pending) :]
                    except BlockingIOError:
                        pass
            child.stdin.close()
            while child.poll() is None:
                guard()
                time.sleep(0.05)
            error = child.stderr.read(4096).decode(errors="replace")
            if child.returncode:
                raise RuntimeError("decoder failure: " + error)
            if digest.hexdigest() != row["patch_sha256"]:
                raise RuntimeError("compressed frame hash drift")
            result["compressed_stream_bytes"] += row["patch_bytes"]
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=10)
            child.stderr.close()
            child = None


try:
    codec = work / "zstd-decompress"
    if sha(codec) != CODEC_SHA:
        raise RuntimeError("codec pin differs")
    if sha(input_manifest) != INPUT_MANIFEST_SHA:
        raise RuntimeError("accepted input manifest differs")
    original = json.loads(input_manifest.read_text())
    if original["input_id"] != INPUT_ID or len(original["files"]) != 2749:
        raise RuntimeError("accepted input identity differs")
    if read_exact(8) != b"R2DLT01\n":
        raise ValueError("stream magic differs")
    length = struct.unpack(">I", read_exact(4))[0]
    if not 1 <= length <= 8 * 1024**2:
        raise ValueError("manifest size out of bounds")
    data = read_exact(length)
    if hashlib.sha256(data).hexdigest() != MANIFEST_SHA:
        raise RuntimeError("target manifest pin differs")
    manifest = json.loads(data)
    if manifest["input_id"] != INPUT_ID or len(manifest["targets"]) != 840:
        raise RuntimeError("manifest identity/count differs")
    output = work / "output"
    output.mkdir(mode=0o700)
    guard(True)
    maximum_output = sum(x["bytes"] for x in manifest["targets"]) + sum(x["bytes"] for x in manifest["targets"] if x["path"].startswith("apk/"))
    if result["minimum_free"] < maximum_output + MIN_DISK + 16 * 1024**2:
        raise RuntimeError("insufficient initial capacity for full output and reserve")
    verified = {}
    for row in manifest["targets"]:
        if row["mode"] != "private-delta":
            continue
        ref = row["reference"]
        source = safe(inputs, ref["path"])
        expected = original["files"][ref["path"]]
        if expected != {"bytes": ref["bytes"], "sha256": ref["sha256"]}:
            raise RuntimeError("PC reference differs from accepted input")
        if ref["path"] not in verified:
            if source.stat().st_size != ref["bytes"] or sha(source) != ref["sha256"]:
                raise RuntimeError("PC input bytes differ")
            verified[ref["path"]] = source
    for index, row in enumerate(manifest["targets"]):
        guard(True)
        dest = safe(output, row["path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if row["mode"] == "sdk-copy":
            if copy_stream(row["bytes"], dest) != row["sha256"]:
                raise RuntimeError("SDK stream differs")
            result["sdk_stream_bytes"] += row["bytes"]
        else:
            reference = verified[row["reference"]["path"]] if row["mode"] == "private-delta" else None
            decode_stream(row, dest, codec, reference)
        if dest.stat().st_size != row["bytes"] or sha(dest) != row["sha256"]:
            raise RuntimeError("decoded output differs")
        result["targets_verified"] += 1
        if index % 100 == 0:
            print(
                json.dumps({"phase": "decode", "verified": result["targets_verified"]}),
                flush=True,
            )
    unsigned = output / "reconstructed-unsigned.apk"
    omitted = []
    with zipfile.ZipFile(unsigned, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as apk:
        for row in manifest["targets"]:
            if not row["path"].startswith("apk/"):
                continue
            name = row["path"][4:]
            if name.startswith("META-INF/") and (name.endswith((".RSA", ".DSA", ".EC", ".SF")) or name == "META-INF/MANIFEST.MF"):
                omitted.append(name)
                continue
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with (
                safe(output, row["path"]).open("rb") as source,
                apk.open(info, "w") as dest,
            ):
                while data := source.read(65536):
                    guard()
                    dest.write(data)
    with zipfile.ZipFile(unsigned) as apk:
        expected = {r["path"][4:]: r for r in manifest["targets"] if r["path"].startswith("apk/") and r["path"][4:] not in omitted}
        if set(apk.namelist()) != set(expected):
            raise RuntimeError("unsigned membership differs")
        for name, row in expected.items():
            with apk.open(name) as f:
                if hashlib.file_digest(f, "sha256").hexdigest() != row["sha256"]:
                    raise RuntimeError("unsigned entry differs")
    for name, source in verified.items():
        if sha(source) != original["files"][name]["sha256"]:
            raise RuntimeError("consumed source changed")
    guard(True)
    result.update(
        success=True,
        manifest_sha256=MANIFEST_SHA,
        consumed_pc_files_verified=len(verified),
        target_bytes=sum(r["bytes"] for r in manifest["targets"]),
        payload_files=sum(r["path"].startswith("payload/") for r in manifest["targets"]),
        unsigned_apk_entries=len(expected),
        unsigned_apk_sha256=sha(unsigned),
        signature_entries_omitted=omitted,
        python=sys.version,
        zlib_version=zlib.ZLIB_VERSION,
        codec_sha256=CODEC_SHA,
    )
except Exception as error:
    result.update(error_type=type(error).__name__, error=str(error))
finally:
    result["seconds"] = time.monotonic() - started
    with (work / "result.json").open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps(result), flush=True)
sys.exit(0 if result["success"] else 1)
