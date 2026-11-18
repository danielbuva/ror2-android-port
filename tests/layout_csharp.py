"""Compile actual dependency-free layout sources where a host C# toolchain exists."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "tools/unity/runtime/layout"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")


def run_csharp(harness, sources):
    mono = shutil.which("mono")
    compiler = shutil.which("mcs")
    if mono and compiler:
        command = [compiler]
    else:
        mono_path = EDITOR / "MonoBleedingEdge/bin/mono"
        csc = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono_path.is_file() or not csc.is_file():
            raise unittest.SkipTest("host Mono/C# compiler and pinned Unity Mono/Roslyn unavailable")
        mono = str(mono_path)
        command = [mono, str(csc)]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "Harness.cs"
        path.write_text(harness)
        exe = root / "layout.exe"
        result = subprocess.run(
            [*command, "-out:" + str(exe), *[str(LAYOUT / name) for name in sources], str(path)], capture_output=True, text=True, timeout=30
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        result = subprocess.run([mono, str(exe)], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout
