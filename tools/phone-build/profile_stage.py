"""Measure a host converter command; retain local logs, receipts and a table row.

Usage: profile_stage.py --stage NAME --workspace DIR --evidence DIR
                       [--table FILE] -- COMMAND [ARG ...]
Evidence may contain private command output and must remain under ignored work/.
RSS follows wait4 child accounting, not simultaneous process-tree memory.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def disk(root):
    """Logical and allocated regular-file bytes, without following symlinks."""
    logical = allocated = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(base) / name).is_symlink()]
        for name in files:
            path = Path(base) / name
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue  # Stage may remove temporary files while sampling.
            if path.is_file() and not path.is_symlink():
                logical += stat.st_size
                allocated += stat.st_blocks * 512
    return logical, allocated


def table_row(row):
    return (
        f"| {row['stage']} (exit {row['exit_code']}) | {row['wall_seconds']:.3f} | "
        f"{row['user_seconds']:.3f}/{row['system_seconds']:.3f} | {row['peak_rss_bytes']} | "
        f"{row['peak_workspace_logical_bytes']}/{row['final_workspace_logical_bytes']} | "
        f"{row['input_block_operations']}/{row['output_block_operations']} |"
    )


def measure(stage, command, workspace, evidence):
    workspace, evidence = Path(workspace), Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    initial = disk(workspace)
    peak = list(initial)
    stop = threading.Event()

    def sample():
        while not stop.wait(1):
            for index, value in enumerate(disk(workspace)):
                peak[index] = max(peak[index], value)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        with (evidence / f"{stage}.log").open("x") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            _, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
        elapsed = time.monotonic() - started
    finally:
        stop.set()
        thread.join()
    final = disk(workspace)
    peak = [max(a, b) for a, b in zip(peak, final)]
    row = {
        "stage": stage,
        "exit_code": child.returncode,
        "wall_seconds": elapsed,
        "user_seconds": usage.ru_utime,
        "system_seconds": usage.ru_stime,
        "peak_rss_bytes": usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024),
        "input_block_operations": usage.ru_inblock,
        "output_block_operations": usage.ru_oublock,
        "initial_workspace_logical_bytes": initial[0],
        "peak_workspace_logical_bytes": peak[0],
        "final_workspace_logical_bytes": final[0],
        "initial_workspace_allocated_bytes": initial[1],
        "peak_workspace_allocated_bytes": peak[1],
        "final_workspace_allocated_bytes": final[1],
    }
    (evidence / f"{stage}.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--table", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or Path(args.stage).name != args.stage:
        parser.error("a command and a single-component stage name are required")
    row = measure(args.stage, command, args.workspace, args.evidence)
    if args.table:
        lines = args.table.read_text().splitlines()
        last = max(i for i, line in enumerate(lines) if line.startswith("|"))
        lines.insert(last + 1, table_row(row))
        args.table.write_text("\n".join(lines) + "\n")
    print(json.dumps(row))
    return row["exit_code"] if row["exit_code"] >= 0 else 128 - row["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
