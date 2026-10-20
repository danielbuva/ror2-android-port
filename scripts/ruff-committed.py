#!/usr/bin/env python3
"""CI's Ruff step (`.github/workflows/host-tests.yml`) on committed content, before it is pushed.

Checks every Python file changed in BASE..TARGET exactly as committed at TARGET, so another
session's uncommitted work in a shared checkout never affects the result. Used by the tracked
pre-push hook (`scripts/git-hooks/pre-push`) and by tests/test_ruff_changed.py.
Usage: ruff-committed.py [BASE [TARGET]] (default: merge-base with origin/main .. HEAD).
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args, check=True):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=check).stdout


def ruff():
    for candidate in (ROOT / ".local/lab-venv/bin/ruff", Path(sys.executable).with_name("ruff")):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ruff")


def check(base, target):
    files = git("diff", "--name-only", "--diff-filter=ACMR", "-z", base, target, "--", "*.py").split("\0")
    files = [path for path in files if path]
    if not files:
        return 0, "No changed Python files."
    tool = ruff()
    if tool is None:
        return 1, "ruff is missing: uv pip install --python .local/lab-venv/bin/python ruff==0.11.13"
    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory)
        archive = subprocess.run(["git", "-C", str(ROOT), "archive", target, "--", *files], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(tree)], input=archive, check=True)
        # Lint with the configuration committed at TARGET, as CI does.
        for name in ("ruff.toml", "pyproject.toml"):
            config = subprocess.run(["git", "-C", str(ROOT), "show", target + ":" + name], capture_output=True)
            if config.returncode == 0:
                (tree / name).write_bytes(config.stdout)
        report = []
        for args in (["check"], ["format", "--check"]):
            result = subprocess.run([tool, *args, "--", *files], cwd=tree, capture_output=True, text=True)
            if result.returncode:
                report.append("ruff " + " ".join(args) + ":\n" + result.stdout + result.stderr)
    if report:
        return 1, "".join(report) + "Fix with: .local/lab-venv/bin/ruff format <files> && .local/lab-venv/bin/ruff check <files>, then commit."
    return 0, "Ruff passed on %d changed Python files." % len(files)


def main():
    target = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    base = sys.argv[1] if len(sys.argv) > 1 else git("merge-base", "origin/main", target).strip()
    code, message = check(base, target)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
