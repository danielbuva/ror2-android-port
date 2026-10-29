#!/usr/bin/env python3
"""Local CI inputs only: locked Git objects and pinned, interpreter-specific dependencies.

Every invocation gets a new worktree/index/config. The source store only imports requested
commits and their ancestors, not working files or arbitrary local refs. Never cache results.
Cache directories are private to the repository owner; no reusable worktree is executed.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig

# Change when the environment creation contract changes, not when test inputs change.
ENVIRONMENT_VERSION = 1


def git(repo: Path, *args: str, **kwargs) -> str:
    result = subprocess.run(
        ["git", "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        **kwargs,
    )
    return result.stdout.strip()


def private_directory(path: Path) -> Path:
    """Do not follow cache symlinks or accept caches writable by another account."""
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError(f"unsafe CI cache directory: {path}")
    return path


@contextmanager
def locked(path: Path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise RuntimeError(f"unsafe CI cache lock: {path}")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def cache_root(repo: Path) -> Path:
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve(strict=True)
    return private_directory(common / "ci-cache")


def has_object(repo: Path, revision: str) -> bool:
    return (
        subprocess.run(
            ["git", "--no-replace-objects", "-C", str(repo), "cat-file", "-e", revision], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        == 0
    )


def validate_source_store(store: Path) -> None:
    # A cache is owned state, not a configurable repository supplied by a caller.
    # Reject indirect paths before Git can follow them or write through them.
    for directory, directories, files in os.walk(store):
        for name in directories + files:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise RuntimeError(f"unsafe CI source store: {path}")
    allowed = {
        "core.repositoryformatversion": {"0"},
        "core.bare": {"true"},
        "core.filemode": {"true", "false"},
        # Git init probes these on Darwin/case-insensitive volumes.
        "core.ignorecase": {"true", "false"},
        "core.precomposeunicode": {"true", "false"},
        "core.symlinks": {"true", "false"},
    }
    actual = dict(line.split("=", 1) for line in git(store, "config", "--local", "--list").splitlines())
    if actual.get("core.bare") != "true" or any(value not in allowed.get(name, set()) for name, value in actual.items()):
        raise RuntimeError("CI source store has unexpected local Git configuration")
    if (store / "objects/info/alternates").exists():
        raise RuntimeError("CI source store must not borrow objects from another repository")


def checkout(repo: Path, destination: Path, target: str, base: str) -> None:
    """Append source objects under one short lock; materialize an entirely new tree."""
    cache = cache_root(repo)
    upstream = git(repo, "rev-parse", "--verify", "origin/main^{commit}")
    target = git(repo, "rev-parse", "--verify", f"{target}^{{commit}}")
    # The no-parent lint base is a tree, not a fetchable source ref.
    empty = git(repo, "hash-object", "-t", "tree", "--stdin", input="")
    if base != empty:
        base = git(repo, "rev-parse", "--verify", f"{base}^{{object}}")
    store = cache / "source.git"
    with locked(cache / "source.lock"):
        if not store.exists() and not store.is_symlink():
            private_directory(store)
            git(store, "init", "--bare", "--quiet", "--template=")
        private_directory(store)
        validate_source_store(store)
        missing = [ref for ref in dict.fromkeys((target, upstream, base)) if ref != empty and not has_object(store, ref)]
        if missing:
            git(store, "-c", "fetch.fsckObjects=true", "fetch", "--quiet", "--no-tags", "--no-write-fetch-head", str(repo), *missing)
        git(store, "hash-object", "-w", "-t", "tree", "--stdin", input="")
        for revision in dict.fromkeys((target, upstream, base)):
            git(store, "update-ref", f"refs/ci/{revision}", revision)
    # No clone templates, local config, index, checkout or ignored files are reused.
    destination.mkdir(mode=0o700)
    git(destination, "init", "--quiet", "--template=")
    (destination / ".git/objects/info/alternates").write_text(str(store / "objects") + "\n")
    git(destination, "update-ref", "refs/remotes/origin/main", upstream)
    git(destination, "checkout", "--quiet", "--detach", target)
    if git(destination, "rev-parse", "HEAD") != target or git(destination, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("CI checkout is not a clean tree at the requested commit")
    print(f"ci-local: source objects {'updated' if missing else 'reused'}; fresh checkout", file=sys.stderr)


def interpreter_identity() -> dict:
    executable = Path(sys.executable).resolve(strict=True)
    info = executable.stat()
    return {
        "executable": str(executable),
        "executable_size": info.st_size,
        "executable_mtime_ns": info.st_mtime_ns,
        "version": sys.version,
        "implementation": sys.implementation.name,
        "cache_tag": sys.implementation.cache_tag,
        "abi": sysconfig.get_config_var("SOABI"),
        "platform": sysconfig.get_platform(),
        "machine": platform.machine(),
        "system": platform.system(),
        "libc": platform.libc_ver(),
    }


def requirements_key(requirements: bytes, identity: dict) -> str:
    metadata = json.dumps({"version": ENVIRONMENT_VERSION, "interpreter": identity}, sort_keys=True).encode()
    return hashlib.sha256(metadata + b"\0" + requirements).hexdigest()


def pinned_requirements(content: str) -> dict[str, str]:
    """Reject unkeyed includes/editable paths: this repository uses exact registry pins."""
    pins = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)", line)
        if not match:
            raise RuntimeError(f"CI requirements must be exact package pins, not paths/includes/options: {line}")
        pins[match[1]] = match[2]
    return pins


def readonly_environment(path: Path) -> None:
    # Python/console launchers may be symlinks; never chmod their external target.
    for directory, _, files in os.walk(path):
        for name in files:
            item = Path(directory) / name
            if not item.is_symlink():
                item.chmod(item.stat().st_mode & ~0o222)
        Path(directory).chmod(Path(directory).stat().st_mode & ~0o222)


def remove_environment(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"unsafe CI environment: {path}")
    for directory, _, _ in os.walk(path):
        Path(directory).chmod(0o700)
    shutil.rmtree(path)


def install_environment(path: Path, requirements: Path, pins: dict) -> None:
    # Build in its final path: venv console-script shebangs must not be renamed.
    subprocess.run([sys.executable, "-I", "-m", "venv", str(path)], check=True, stdout=sys.stderr)
    python = path / "bin/python"
    if pins:
        subprocess.run(
            [str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
            check=True,
            stdout=sys.stderr,
        )
    subprocess.run([str(python), "-I", "-m", "pip", "check"], check=True, stdout=sys.stderr)


def dependency_inventory(python: Path) -> dict:
    output = subprocess.check_output(
        [
            str(python),
            "-I",
            "-c",
            "import importlib.metadata as m,json,re; "
            "print(json.dumps({re.sub(r'[-_.]+','-',d.metadata['Name']).lower():d.version for d in m.distributions()},sort_keys=True))",
        ],
        text=True,
    )
    return json.loads(output)


def validate_environment_paths(path: Path) -> None:
    # Venv's lib64 -> lib is legitimate; no directory link may leave the cache.
    path = path.resolve(strict=True)
    for directory, directories, _ in os.walk(path):
        for name in directories:
            entry = Path(directory) / name
            if entry.is_symlink() and not entry.resolve(strict=True).is_relative_to(path):
                raise RuntimeError(f"unsafe CI environment directory: {entry}")
    for name in ("bin", "pyvenv.cfg", "complete.json"):
        if (path / name).is_symlink():
            raise RuntimeError(f"unsafe CI environment path: {path / name}")


def environment(repo: Path, tree: Path) -> Path:
    cache = cache_root(repo)
    environments = private_directory(cache / "venvs")
    requirement_file = tree / "tools/lab-requirements.txt"
    if requirement_file.is_symlink() or not requirement_file.resolve(strict=True).is_relative_to(tree.resolve(strict=True)):
        raise RuntimeError("CI requirements must be a regular file inside the clean checkout")
    requirements = requirement_file.read_bytes()
    pins = pinned_requirements(requirements.decode())
    key = requirements_key(requirements, interpreter_identity())
    path = environments / key
    marker = path / "complete.json"
    with locked(environments / f"{key}.lock"):
        if path.is_symlink():
            raise RuntimeError(f"unsafe CI environment: {path}")
        ready = False
        record = {}
        if path.exists():
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise RuntimeError(f"unsafe CI environment: {path}")
            if marker.is_symlink():
                raise RuntimeError(f"unsafe CI environment marker: {marker}")
            if marker.is_file():
                record = json.loads(marker.read_text())
                if record.get("key") != key or record.get("pins") != pins:
                    raise RuntimeError(f"CI environment metadata mismatch: {path}")
                ready = True
            if not ready:
                remove_environment(path)
        if not ready:
            private_directory(path)
            install_environment(path, requirement_file, pins)
        validate_environment_paths(path)
        inventory = dependency_inventory(path / "bin/python")
        if any(inventory.get(re.sub(r"[-_.]+", "-", name).lower()) != version for name, version in pins.items()):
            raise RuntimeError(f"CI dependency cache pin mismatch: {path}")
        if ready:
            if record.get("distributions") != inventory:
                raise RuntimeError(f"CI dependency cache installed metadata changed: {path}")
        else:
            marker.write_text(json.dumps({"key": key, "pins": pins, "distributions": inventory}, sort_keys=True))
            readonly_environment(path)
    print(f"ci-local: dependency environment {'reused' if ready else 'created'} ({key[:12]})", file=sys.stderr)
    return path / "bin/python"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    source = subparsers.add_parser("checkout")
    source.add_argument("repo", type=Path)
    source.add_argument("destination", type=Path)
    source.add_argument("target")
    source.add_argument("base")
    deps = subparsers.add_parser("environment")
    deps.add_argument("repo", type=Path)
    deps.add_argument("tree", type=Path)
    args = parser.parse_args()
    if args.command == "checkout":
        checkout(args.repo, args.destination, args.target, args.base)
    else:
        print(environment(args.repo, args.tree))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
