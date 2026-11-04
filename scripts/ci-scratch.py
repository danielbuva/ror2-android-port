#!/usr/bin/env python3
"""Own ci-local scratch and recover only recorded, inactive, abandoned runs.

No broad temporary-directory cleanup. An uncertain image mapping is a refusal.
The supervisor cleans ordinarily completed shells. Abnormal or uncertain runs
remain preserved for owner reconciliation; SIGKILL recovery is not claimed.
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


def devices(image):
    result = subprocess.run(["hdiutil", "info", "-plist"], capture_output=True, timeout=30, check=True)
    data = plistlib.loads(result.stdout)
    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        raise ValueError("invalid image inventory")
    found = set()
    other = set()
    for item in data["images"]:
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


def detach(image):
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
            subprocess.run(["hdiutil", "detach", "-force", device], capture_output=True, timeout=30, check=True)
    if devices(image):
        raise ValueError("image still attached")


def require_unmounted(scratch):
    result = subprocess.run(["hdiutil", "info", "-plist"], capture_output=True, timeout=30, check=True)
    data = plistlib.loads(result.stdout)
    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        raise ValueError("invalid mount inventory")
    for image in data["images"]:
        entries = image.get("system-entities") if isinstance(image, dict) else None
        if not isinstance(entries, list):
            raise ValueError("invalid mount inventory")
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
            if Path(os.path.abspath(mount)).is_relative_to(scratch) or Path(os.path.realpath(mount)).is_relative_to(scratch):
                raise ValueError("scratch contains mounted image")


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
            if record.get("completed") is not True:
                return "uncertain-descendants"
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
            # A service may finish an attach after its CLI has died. Only the
            # setup owner removes this marker after confirmed CLI completion.
            if os.path.lexists(path / "attach.pending"):
                return "uncertain-attach"
            image = path / "volume.sparseimage"
            if image.is_symlink():
                return "unowned"
            if sys.platform == "darwin":
                detach(image)
                require_unmounted(path)
            elif image.exists():
                # Never delete an image on a platform unable to reconcile mounts.
                return "unsupported-image"
            require_no_mounts(path)
            current = path.lstat()
            if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino) or not stat.S_ISDIR(current.st_mode):
                return "changed"
            if alive(pgid, group=True) or (not own and alive(pid)):
                return "live"
            shutil.rmtree(path)
            return "removed"
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, plistlib.InvalidFileException):
        return "preserved"


def sweep(root):
    for path in root.iterdir():
        if NAME.fullmatch(path.name):
            reclaim(path)


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
    (scratch / "owner.pid").write_text(str(os.getpid()) + "\n")
    (scratch / "owner.lock").touch(mode=0o600)
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
            # Only an ordinary completed CI shell supplies this recovery claim.
            # A killed supervisor/shell cannot certify escaped descendants.
            record = scratch / "owner.complete"
            record.write_text(json.dumps({"pid": os.getpid(), "pgid": process.pid, "completed": True}))
            os.replace(record, scratch / "owner.json")
    finally:
        # Descendants may outlive the shell. Do not remove files under live work;
        # the next startup can reclaim after the whole recorded group has gone.
        outcome = reclaim(scratch, own=True) if process is not None else "preserved"
        print("ci-local cleanup: " + outcome, file=sys.stderr)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 128 + received[0] if received else (128 - status if status < 0 else status)


if __name__ == "__main__":
    raise SystemExit(supervise(["bash", *sys.argv[1:]], Path(os.environ.get("TMPDIR", "/tmp"))))
