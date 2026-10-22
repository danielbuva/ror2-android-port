"""Host-wide, advisory lock for Unity build processes.

The lock file is persistent. Ownership is represented by ``flock`` on its open
file description, never by the existence of the path or by a PID check. This
means a crashed process releases the kernel lock automatically, while its last
receipt remains available for diagnosis until the next owner replaces it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import uuid
import sys


_registry_guard = threading.Lock()
_registry: dict[str, "_LockState"] = {}
ROOT = Path(__file__).resolve().parents[2]
HOST_BUILD_LOCK = ROOT / "work/coordination/unity-build.lock"
CLAUDE_COORDINATION_LOCK = ROOT / "work/coordination/claude-r9.lock"
INHERITED_FD_ENV = "ROR2LAB_UNITY_BUILD_LOCK_FD"


class _LockState:
    def __init__(self) -> None:
        self.guard = threading.RLock()
        self.fd: int | None = None
        self.depth = 0
        self.owner_thread: int | None = None


def _state_for(path: Path) -> _LockState:
    key = str(path)
    with _registry_guard:
        return _registry.setdefault(key, _LockState())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_receipt(fd: int, receipt: dict) -> None:
    payload = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write updating Unity build lock receipt")
        view = view[written:]
    os.fsync(fd)


def _read_receipt(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _timeout_message(path: Path) -> str:
    receipt = _read_receipt(path)
    if receipt is None:
        detail = "owner receipt is unavailable or incomplete"
    else:
        detail = json.dumps(receipt, sort_keys=True)
    return f"Timed out waiting for host Unity build lock {path}; {detail}"


def assert_build_unblocked(blocker_path: str | os.PathLike[str] | None = None) -> None:
    """Optional task guard, separate from the mandatory host build mutex.

    The incumbent session uses these same CLIs while it owns the coordination
    file. A file's existence cannot authenticate a caller. Orchestrators must
    honor their own task's ownership instructions; LAB_COORDINATION_GUARD=1
    adds a transport check for callers that must wait. An explicit path always
    enforces the check (including migration and isolated host tests).
    """
    if blocker_path is None and os.environ.get("LAB_COORDINATION_GUARD") != "1":
        return
    blocker = Path(blocker_path) if blocker_path is not None else CLAUDE_COORDINATION_LOCK
    if blocker.exists():
        raise RuntimeError("Unity build blocked by active coordination lock: " + str(blocker))


def active_lock_handoff() -> tuple[dict[str, str], tuple[int, ...]]:
    """Return env/pass_fds for a child process that must share this lock."""
    lock_path = HOST_BUILD_LOCK.resolve()
    state = _state_for(lock_path)
    if state.fd is not None and state.depth > 0 and state.owner_thread == threading.get_ident():
        fd = state.fd
    else:
        inherited = os.environ.get(INHERITED_FD_ENV)
        if inherited is None:
            return {}, ()
        # A nested CLI process has no local registry entry for its parent-owned
        # descriptor. Validate and forward that exact open file description;
        # malformed, stale, or unrelated descriptors fail closed.
        fd = _validate_inherited_fd(lock_path, inherited)
    return {INHERITED_FD_ENV: str(fd)}, (fd,)


def assert_host_build_lock_held(lock_path: str | os.PathLike[str]) -> None:
    """Verify the current process still owns the host lock before an editor call."""
    path = Path(lock_path).expanduser().resolve()
    inherited = os.environ.get(INHERITED_FD_ENV)
    if inherited is not None:
        _validate_inherited_fd(path, inherited)
        return
    state = _state_for(path)
    if state.fd is None or state.depth <= 0 or state.owner_thread != threading.get_ident():
        raise RuntimeError("Unity editor operation requires the host build lock")
    _validate_inherited_fd(path, str(state.fd))


def _validate_inherited_fd(path: Path, fd_text: str) -> int:
    try:
        fd = int(fd_text)
        open_stat = os.fstat(fd)
        path_stat = path.stat()
    except (ValueError, OSError) as error:
        raise RuntimeError("Invalid inherited host Unity build lock descriptor") from error
    if (open_stat.st_dev, open_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
        raise RuntimeError("Inherited descriptor does not refer to the host Unity build lock")
    try:
        # flock on the inherited open-file description succeeds for its owner;
        # it does not release or replace the parent's lock.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        raise RuntimeError("Inherited host Unity build lock is not held") from error
    receipt = _read_receipt(path)
    if not receipt or receipt.get("status") != "held":
        raise RuntimeError("Inherited host Unity build lock has no active owner receipt")
    return fd


@contextmanager
def host_build_lock(
    lock_path: str | os.PathLike[str],
    *,
    operation: str,
    timeout: float | None = None,
    poll_interval: float = 0.1,
    inherited_fd: int | None = None,
):
    """Exclusively guard a Unity build, reentrant within the owning thread.

    ``lock_path`` should be a single host-wide persistent path, independent of
    destination project and device. The path is intentionally never unlinked:
    unlinking a flock file can split contenders across different inodes.

    ``timeout=None`` waits indefinitely. A finite timeout raises ``TimeoutError``
    with the current owner receipt when available. Nested calls in the same
    process and thread share the outer lock and update no competing receipt.
    """
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("operation must be a non-empty diagnostic label")
    if timeout is not None and timeout < 0:
        raise ValueError("timeout must be non-negative or None")
    if poll_interval <= 0:
        raise ValueError("poll_interval must be positive")

    path = Path(lock_path).expanduser().resolve()
    if inherited_fd is None:
        inherited = os.environ.get(INHERITED_FD_ENV)
        if inherited is not None:
            inherited_fd = _validate_inherited_fd(path, inherited)
    if inherited_fd is not None:
        _validate_inherited_fd(path, str(inherited_fd))
        yield path
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    state = _state_for(path)
    thread_id = threading.get_ident()
    start = time.monotonic()
    acquired_guard = state.guard.acquire() if timeout is None else state.guard.acquire(timeout=timeout)
    if not acquired_guard:
        raise TimeoutError(_timeout_message(path))

    outermost = state.depth == 0
    try:
        if not outermost:
            if state.owner_thread != thread_id:
                # The RLock should make this unreachable; fail closed if state
                # was corrupted rather than accidentally bypassing flock.
                raise RuntimeError("Unity build lock thread ownership mismatch")
            state.depth += 1
        else:
            fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            state.fd = fd
            lock_deadline = None if timeout is None else start + timeout
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if lock_deadline is not None and time.monotonic() >= lock_deadline:
                        os.close(fd)
                        state.fd = None
                        raise TimeoutError(_timeout_message(path))
                    time.sleep(poll_interval)
            state.owner_thread = thread_id
            state.depth = 1
            try:
                _write_receipt(
                    fd,
                    {
                        "schema": 1,
                        "status": "held",
                        "operation": operation.strip(),
                        "pid": os.getpid(),
                        "host": socket.gethostname(),
                        "thread_id": thread_id,
                        "token": uuid.uuid4().hex,
                        "acquired_at": _utc_now(),
                    },
                )
            except BaseException:
                state.depth = 0
                state.owner_thread = None
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
                state.fd = None
                raise

        try:
            yield path
        finally:
            state.depth -= 1
            if outermost:
                fd = state.fd
                try:
                    if fd is not None:
                        prior = _read_receipt(path) or {}
                        prior.update(status="released", released_at=_utc_now())
                        _write_receipt(fd, prior)
                finally:
                    state.owner_thread = None
                    if fd is not None:
                        try:
                            fcntl.flock(fd, fcntl.LOCK_UN)
                        finally:
                            os.close(fd)
                    state.fd = None
    finally:
        state.guard.release()


def _main() -> int:
    """Run a command under the canonical host lock (used by smoke build)."""
    args = sys.argv[1:]
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        print("usage: python3 scripts/lab/build_lock.py -- COMMAND [ARG ...]", file=sys.stderr)
        return 2
    assert_build_unblocked()
    try:
        with host_build_lock(HOST_BUILD_LOCK, operation="command: " + Path(args[0]).name):
            assert_build_unblocked()
            return subprocess.run(args, pass_fds=active_lock_handoff()[1]).returncode
    except BaseException as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
