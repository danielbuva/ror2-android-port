#!/usr/bin/env python3
"""Bounded optional creation/attachment of ci-local's disposable sparse image."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

CREATE_FAILED = 1
ATTACH_STATE_UNCERTAIN = 2


def run_hdiutil(argv: list[str], timeout_seconds: float) -> int | None:
    """Return the CLI status, or None after killing and reaping our timed-out child."""
    try:
        completed = subprocess.run(argv, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        return None
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("timeout_seconds", type=float)
    parser.add_argument("image", type=Path)
    parser.add_argument("mountpoint", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error("timeout must be finite and positive")

    create = [
        "hdiutil",
        "create",
        "-size",
        # Producers require 2 GiB free in addition to their output. The fixture
        # volume must leave that reserve available after APFS formatting.
        "4g",
        "-fs",
        "Case-sensitive APFS",
        "-volname",
        "ci-local",
        "-type",
        "SPARSE",
        str(args.image),
        "-quiet",
    ]
    create_status = run_hdiutil(create, args.timeout_seconds)
    if create_status is None:
        print("ci-local: hdiutil create timed out; using ordinary temporary directory", file=sys.stderr)
        return CREATE_FAILED
    if create_status != 0:
        print(f"ci-local: hdiutil create failed ({create_status}); using ordinary temporary directory", file=sys.stderr)
        return CREATE_FAILED

    attach = [
        "hdiutil",
        "attach",
        str(args.image),
        "-mountpoint",
        str(args.mountpoint),
        "-nobrowse",
        "-quiet",
    ]
    attach_status = run_hdiutil(attach, args.timeout_seconds)
    if attach_status is None:
        print(
            "ci-local: hdiutil attach timed out; mount state is uncertain, preserving scratch image",
            file=sys.stderr,
        )
        return ATTACH_STATE_UNCERTAIN
    if attach_status != 0:
        print(f"ci-local: hdiutil attach failed ({attach_status}); using ordinary temporary directory", file=sys.stderr)
        return CREATE_FAILED
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
