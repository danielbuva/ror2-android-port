#!/usr/bin/env python3
"""Own ci-local scratch and recover only recorded, inactive, abandoned runs.

The supervisor cleans after its shell exits. The sweep also recovers recorded
dead-owner runs whose scratch and mounted volume have no open files.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

NAME = re.compile(r"ci-local\.[A-Za-z0-9_]+\Z")
DEVICE = re.compile(r"/dev/disk[0-9]+(?:s[0-9]+)*\Z")
AGE = 1800


def alive(pid, *, group=False):
    try:
        (os.killpg if group else os.kill)(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OverflowError):
        return True
    return True


def regular(path):
    info = path.lstat()
    return stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()


def image_inventory():
    result = subprocess.run(["hdiutil", "info", "-plist"], capture_output=True, timeout=30, check=True)
    data = plistlib.loads(result.stdout)
    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        raise ValueError("invalid image inventory")
    return data["images"]


def devices(image):
    found = set()
    other = set()
    for item in image_inventory():
        if not isinstance(item, dict) or not isinstance(item.get("image-path"), str):
            raise ValueError("invalid image inventory")
        matches = os.path.realpath(item["image-path"]) == str(image)
        entries = item.get("system-entities")
        if not isinstance(entries, list) or not entries:
            raise ValueError("uncertain image devices")
        for entry in entries:
            device = entry.get("dev-entry") if isinstance(entry, dict) else None
            if not isinstance(device, str) or not DEVICE.fullmatch(device):
                raise ValueError("uncertain image device")
            (found if matches else other).add(device)
    if any(a == b or a.startswith(b + "s") or b.startswith(a + "s") for a in found for b in other):
        raise ValueError("ambiguous device ownership")
    return found


def detach(image, *, force=True):
    # Never use cached device numbers: macOS can reuse them after an unmount.
    attached = devices(image)
    # Prefer the whole backing disk when present; otherwise use listed entities.
    targets = sorted(d for d in attached if not any(d.startswith(p + "s") for p in attached))
    for device in targets:
        # Revalidate ownership immediately before each destructive command.
        if device not in devices(image):
            continue
        try:
            result = subprocess.run(["hdiutil", "detach", device], capture_output=True, timeout=30)
            failed = bool(result.returncode)
        except subprocess.TimeoutExpired:
            failed = True
        if failed:
            if device not in devices(image):
                continue
            if not force:
                raise ValueError(f"regular detach failed for {device}")
            subprocess.run(["hdiutil", "detach", "-force", device], capture_output=True, timeout=30, check=True)
    if devices(image):
        raise ValueError("image still attached")


def owned_mounts(scratch, expected_image=None):
    for image in image_inventory():
        entries = image.get("system-entities") if isinstance(image, dict) else None
        if not isinstance(entries, list) or not isinstance(image.get("image-path"), str):
            raise ValueError("invalid mount inventory")
        ours = expected_image is not None and os.path.realpath(image["image-path"]) == str(expected_image)
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid mount inventory")
            mount = entry.get("mount-point")
            if mount is None:
                continue
            if not isinstance(mount, str) or not os.path.isabs(mount):
                raise ValueError("invalid mount location")
            # Check both spelling and resolution: a renamed or foreign image may
            # still be mounted inside our scratch, regardless of image identity.
            resolved = Path(mount).resolve()
            inside = Path(os.path.abspath(mount)).is_relative_to(scratch) or resolved.is_relative_to(scratch)
            if ours:
                if resolved != scratch / "case-sensitive":
                    raise ValueError("owned image mounted outside its expected location")
                yield resolved
            elif inside:
                raise ValueError("scratch contains mounted image")


def require_unmounted(scratch):
    list(owned_mounts(scratch))


def lsof_output(*args):
    result = subprocess.run(["lsof", "-nP", *args], capture_output=True, timeout=15)
    if result.stderr or result.returncode not in (0, 1) or (result.returncode == 1 and result.stdout):
        raise ValueError("lsof could not confirm open files")
    return result.stdout


def scratch_open(scratch):
    prefixes = [os.fsencode(scratch) + b"/"]
    if sys.platform == "darwin" and prefixes[0].startswith(b"/private/"):
        prefixes.append(prefixes[0][len(b"/private") :])
    for field in lsof_output("-F0n").split(b"\0"):
        field = field.lstrip(b"\n")
        if not field.startswith(b"n/"):
            continue
        name = field[1:]
        for prefix in prefixes:
            if name == prefix[:-1]:
                return True
            # flock covers owner.lock. DiskImages holds the backing image open
            # until detach, so query the mounted filesystem independently.
            if name.startswith(prefix) and name[len(prefix) :] not in (b"owner.lock", b"volume.sparseimage"):
                return True
    return False


def linux_mounts():
    # /proc mountinfo includes same-filesystem bind mounts that ismount misses.
    with open("/proc/self/mountinfo", encoding="utf-8") as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024 or not data.strip():
        raise ValueError("invalid mount inventory")
    result = []
    for line in data.splitlines():
        fields = line.split()
        if len(fields) < 10 or "-" not in fields or not fields[4].startswith("/"):
            raise ValueError("invalid mount inventory")
        result.append(Path(re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), fields[4])))
    return result


def require_no_mounts(scratch):
    if sys.platform == "linux":
        if any(mount.is_relative_to(scratch) for mount in linux_mounts()):
            raise ValueError("scratch contains mount")
    # Also refuse non-image filesystems. Never descend across a mount boundary.
    for directory, children, _files in os.walk(scratch, followlinks=False):
        if os.path.ismount(directory):
            raise ValueError("scratch contains mount")
        for child in children:
            path = Path(directory) / child
            if not path.is_symlink() and os.path.ismount(path):
                raise ValueError("scratch contains mount")


def read_record(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 1024:
            raise ValueError("invalid ownership record")
        data = stream.read(1025)
        if len(data) > 1024:
            raise ValueError("oversized ownership record")
        return data.decode("ascii")


def reclaim(path, *, own=False, now=None):
    """Return a fixed outcome. Unknown ownership always preserves the directory."""
    try:
        info = path.lstat()
        if not NAME.fullmatch(path.name) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            return "unowned"
        if not own and (time.time() if now is None else now) - info.st_mtime <= AGE:
            return "recent"
        lock_path = path / "owner.lock"
        if not regular(lock_path):
            return "unowned"
        fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return "busy"
            # Ignore aliases and incomplete startup records, including the tiny
            # interval between launching a child and recording its process group.
            pid_path, record_path = path / "owner.pid", path / "owner.json"
            if not regular(pid_path) or not regular(record_path):
                return "unowned"
            pid = int(read_record(pid_path))
            record = json.loads(read_record(record_path))
            if not isinstance(record, dict):
                return "unowned"
            pgid = record.get("pgid")
            if not 1 < pid <= 2147483647 or record.get("pid") != pid or type(pgid) is not int or not 1 < pgid <= 2147483647:
                return "unowned"
            if (not own and alive(pid)) or alive(pgid, group=True):
                return "live"
            if own and pid != os.getpid():
                return "unowned"
            current = path.lstat()
            if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                return "changed"
            image = path / "volume.sparseimage"
            if os.path.lexists(image) and not regular(image):
                return "unowned"
            if sys.platform == "darwin":
                mounts = list(owned_mounts(path, image))
                if any(lsof_output("-t", "+f", "--", str(mount)) for mount in mounts) or scratch_open(path):
                    return "open-files"
                # A timed-out service request can still attach after its CLI
                # exits. An observed exact mount can be detached and verified.
                if os.path.lexists(path / "attach.pending") and not mounts:
                    return "uncertain-attach"
                detach(image, force=own)
                require_unmounted(path)
            elif image.exists():
                # Never delete an image on a platform unable to reconcile mounts.
                return "unsupported-image"
            elif shutil.which("lsof"):
                if scratch_open(path):
                    return "open-files"
            elif not own and record.get("completed") is not True:
                return "uncertain-descendants"
            require_no_mounts(path)
            current = path.lstat()
            if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino) or not stat.S_ISDIR(current.st_mode):
                return "changed"
            if alive(pgid, group=True) or (not own and alive(pid)):
                return "live"
            shutil.rmtree(path)
            return "removed"
    except FileNotFoundError:
        return "unowned" if not path.exists() else "preserved"
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, plistlib.InvalidFileException) as error:
        print(f"ci-local cleanup: {path.name}: {error}", file=sys.stderr)
        return "preserved"


def sweep(root):
    for path in root.iterdir():
        if NAME.fullmatch(path.name):
            outcome = reclaim(path)
            if outcome == "removed":
                print(f"ci-local cleanup: reaped {path.name}", file=sys.stderr)
            elif outcome in ("preserved", "uncertain-attach"):
                print(f"ci-local cleanup: WARNING kept {path.name} ({outcome})", file=sys.stderr)


def kill_and_reap(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def supervise(command, root):
    root = root.resolve(strict=True)
    sweep(root)
    scratch = Path(tempfile.mkdtemp(prefix="ci-local.", dir=root))
    process = None
    received = []
    previous = {}

    def interrupted(signum, _frame):
        received.append(signum)
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[sig] = signal.signal(sig, interrupted)
    status = 1
    try:
        (scratch / "owner.pid").write_text(str(os.getpid()) + "\n")
        (scratch / "owner.lock").touch(mode=0o600)
        env = os.environ | {"CI_LOCAL_OWNED_SCRATCH": str(scratch)}
        process = subprocess.Popen(command, env=env, start_new_session=True)
        (scratch / "owner.json").write_text(json.dumps({"pid": os.getpid(), "pgid": process.pid, "completed": False}))
        while process.poll() is None:
            if received:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    kill_and_reap(process)
            else:
                time.sleep(0.05)
        status = process.returncode
        if 0 <= status < 128 and not received:
            # On Linux without lsof only ordinary dead-owner runs are swept.
            record = scratch / "owner.complete"
            record.write_text(json.dumps({"pid": os.getpid(), "pgid": process.pid, "completed": True}))
            os.replace(record, scratch / "owner.json")
    finally:
        # Descendants may outlive the shell. Do not remove files under live work;
        # the next startup can reclaim after the whole recorded group has gone.
        if process is None:
            shutil.rmtree(scratch)
            outcome = "removed"
        else:
            outcome = reclaim(scratch, own=True)
        if outcome == "removed":
            print("ci-local cleanup: removed", file=sys.stderr)
        else:
            print(f"ci-local cleanup: WARNING kept {scratch.name} ({outcome})", file=sys.stderr)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 128 + received[0] if received else (128 - status if status < 0 else status)


if __name__ == "__main__":
    root = Path(os.environ.get("TMPDIR", "/tmp")).resolve(strict=True)
    if sys.argv[1:] == ["--sweep"]:
        sweep(root)
    else:
        raise SystemExit(supervise(["bash", *sys.argv[1:]], root))
