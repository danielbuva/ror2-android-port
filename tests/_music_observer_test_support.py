from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import unittest


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def required_file(variable: str, expected: str) -> Path:
    value = os.environ.get(variable)
    if not value:
        raise unittest.SkipTest(f"set {variable} to the authorized local fixture")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise AssertionError(f"{variable} was supplied but the fixture file is missing: {path}")
    if digest(path) != expected:
        raise AssertionError(f"{variable} fixture does not match its pinned SHA-256")
    return path


def required_directory(variable: str) -> Path:
    value = os.environ.get(variable)
    if not value:
        raise unittest.SkipTest(f"set {variable} to the authorized local fixture")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise AssertionError(f"{variable} was supplied but the fixture directory is missing: {path}")
    return path


def dotnet() -> Path:
    value = os.environ.get("DOTNET") or shutil.which("dotnet")
    if not value:
        local = Path.home() / ".local/share/dotnet/dotnet"
        value = str(local) if local.is_file() else None
    if not value:
        raise unittest.SkipTest("dotnet is unavailable for optional host transform tests")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise AssertionError(f"dotnet was selected but is missing: {path}")
    return path


def cecil() -> Path:
    value = os.environ.get("MUSIC_OBSERVER_CECIL")
    if not value:
        editor = os.environ.get("UNITY_EDITOR")
        if editor:
            contents = Path(editor).expanduser().resolve().parent.parent
            value = str(contents / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll")
    if not value:
        raise unittest.SkipTest("set MUSIC_OBSERVER_CECIL to the pinned Unity Mono.Cecil.dll")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise AssertionError(f"pinned Unity Mono.Cecil fixture is missing: {path}")
    if digest(path) != "8b33668cd03b78b7bcaa96eac82488d88c7c89416f82037ecbe2b781ab9642f8":
        raise AssertionError("pinned Unity Mono.Cecil fixture has drifted")
    return path
