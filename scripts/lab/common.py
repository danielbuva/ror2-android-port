"""Shared local-only configuration, content addressing, and safe subprocess helpers."""

import hashlib
import json
import os
import subprocess
import datetime
import shutil
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = (ROOT / "work").resolve()
RECIPE = ROOT / "recipe"  # audited, tracked build recipes (recipe/README.md)
_hash_cache = ContextVar("lab_build_hash_cache", default=None)


def lane_config():
    path = WORK / "config/build-lane.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def file_identity(path):
    st = Path(path).stat()
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


@contextmanager
def cached_hashes(*, cache_path=None, reuse=False):
    """Reuse verified digests by OS file identity; normal full builds rehash.

    Optional persistence is for iteration only. Keep only identities consulted
    by this operation so old build artifacts cannot grow the cache forever.
    """
    parent = _hash_cache.get()
    hashes = {}
    if parent is None and cache_path is not None and reuse:
        try:
            rows = read(cache_path)
            hashes = {
                tuple(row[:5]): row[5]
                for row in rows
                if len(row) == 6 and all(isinstance(v, int) for v in row[:5]) and isinstance(row[5], str) and len(row[5]) == 64
            }
        except (OSError, ValueError, TypeError):
            hashes = {}
    session = parent if parent is not None else (hashes, set())
    token = _hash_cache.set(session)
    try:
        yield
    finally:
        try:
            if parent is None and cache_path is not None:
                path = Path(cache_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(path.suffix + ".tmp")
                temporary.write_text(json.dumps([list(key) + [session[0][key]] for key in session[1] if key in session[0]], separators=(",", ":")) + "\n")
                temporary.replace(path)
        finally:
            _hash_cache.reset(token)


def toolchain():
    return read(ROOT / "environment/toolchain.json")


def read(p):
    return json.loads(Path(p).read_text())


def write(p, v):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(v, indent=2, sort_keys=True) + "\n")
    tmp.replace(p)


def config():
    return read(WORK / "config/local.json")


def game(work=None):
    configuration = config() if work is None else read(Path(work) / "config/local.json")
    p = Path(configuration["game_path"]).expanduser().resolve()
    if not (p / "Risk of Rain 2_Data/Managed/RoR2.dll").is_file():
        raise RuntimeError("Configured legitimate game installation missing RoR2.dll")
    if p == ROOT or ROOT in p.parents and WORK not in p.parents:
        raise RuntimeError("Game inputs must be external or under ignored work/")
    return p


def sha(p):
    identity = file_identity(p)
    session = _hash_cache.get()
    cache = session[0] if session is not None else None
    if session is not None:
        session[1].add(identity)
    if cache is not None and identity in cache:
        return cache[identity]
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(b)
    if file_identity(p) != identity:
        raise RuntimeError("File changed while computing its SHA-256")
    value = h.hexdigest()
    if cache is not None:
        cache[identity] = value
    return value


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run(args, timeout=120, check=True, **kw):
    p = subprocess.run([str(a) for a in args], capture_output=True, timeout=timeout, **kw)
    if check and p.returncode:
        raise RuntimeError(f"{args[0]} exited {p.returncode}: " + p.stderr.decode(errors="replace")[-2000:] + p.stdout.decode(errors="replace")[-2000:])
    return p


def copy_file_clone(source, destination, *, runner=None):
    """Independent artifact snapshot, sharing APFS blocks when available.

    Callers retain their scope/ownership/hash checks and atomic publication.
    Never use hard links: later writes must not alter the source snapshot.
    """
    source, destination = Path(source), Path(destination)
    if not source.is_file() or source.is_symlink() or destination.is_symlink() or source.resolve() == destination.resolve():
        raise RuntimeError("Artifact copies require regular independent paths")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    cloned = sys.platform == "darwin" and (runner or run)(["/bin/cp", "-c", "-p", source, destination], check=False).returncode == 0
    if not cloned:
        shutil.copy2(source, destination)
    return str(destination)


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def stamp(stage, inputs):
    return digest({"stage": stage, "inputs": inputs, "code": {p.name: sha(p) for p in sorted((ROOT / "scripts/lab").glob("*.py"))}})
