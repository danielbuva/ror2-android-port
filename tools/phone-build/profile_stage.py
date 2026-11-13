"""Measure a host converter command; retain local logs, receipts and a table row.

Usage: profile_stage.py --stage NAME --workspace DIR --evidence DIR
                       [--table FILE] -- COMMAND [ARG ...]
Evidence may contain private command output and must remain under ignored work/.
RSS includes wait4 accounting and a separately sampled simultaneous process tree.
"""

import argparse
import json
import os
from pathlib import Path
import signal
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


def process_tree_rss(pid, rows=None):
    """Sum resident bytes for the command and its current descendants."""
    if rows is None:
        rows = subprocess.run(["ps", "-axo", "pid=,ppid=,rss="], capture_output=True, text=True, check=True).stdout
    processes = [tuple(map(int, line.split())) for line in rows.splitlines() if line.strip()]
    selected = {pid}
    while True:
        children = {child for child, parent, _ in processes if parent in selected}
        if children <= selected:
            return sum(rss * 1024 for child, _, rss in processes if child in selected)
        selected.update(children)


def measure(stage, command, workspace, evidence, *, progress_file=None):
    workspace, evidence = Path(workspace), Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    initial = disk(workspace)
    peak = list(initial)
    tree_peak = 0
    sample_errors = []
    stop = threading.Event()

    def sample():
        nonlocal tree_peak
        samples = None
        try:
            if progress_file is not None:
                samples = (evidence / f"{stage}.samples.jsonl").open("x")
            while True:
                for index, value in enumerate(disk(workspace)):
                    peak[index] = max(peak[index], value)
                rss = process_tree_rss(child.pid)
                tree_peak = max(tree_peak, rss)
                if samples is not None:
                    try:
                        progress = json.loads(Path(progress_file).read_text())
                    except FileNotFoundError:
                        progress = {}
                    value = dict(seconds=time.monotonic() - started, process_tree_rss_bytes=rss)
                    value.update({key: progress.get(key) for key in ("phase", "records_done", "records_total")})
                    samples.write(json.dumps(value) + "\n")
                    samples.flush()
                if stop.wait(1):
                    break
        except Exception as error:
            sample_errors.append(str(error))
        finally:
            if samples is not None:
                samples.close()

    started = time.monotonic()
    with (evidence / f"{stage}.log").open("x") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        thread = threading.Thread(target=sample, daemon=True)
        thread.start()
        try:
            _, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
            elapsed = time.monotonic() - started
        except BaseException:
            os.killpg(child.pid, signal.SIGTERM)
            _, status, _ = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
            raise
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
        "sampled_peak_process_tree_rss_bytes": tree_peak,
        "process_tree_sample_interval_seconds": 1,
        "measurement_errors": sample_errors,
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
    parser.add_argument("--progress-file", type=Path, help="sample phase and record counts alongside process-tree RSS in local JSONL")
    parser.add_argument("--done-file", type=Path, help="write an absolute terminal receipt after lab cleanup, including command failure")
    parser.add_argument("--detach", action="store_true", help="launch this tracked profiler in a new session; requires --done-file")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or Path(args.stage).name != args.stage:
        parser.error("a command and a single-component stage name are required")
    if args.done_file and (not args.done_file.is_absolute() or args.done_file.exists()):
        parser.error("--done-file requires a new absolute path")
    if args.detach:
        if not args.done_file:
            parser.error("--detach requires --done-file")
        args.evidence.mkdir(parents=True, exist_ok=True)
        supervisor_log = args.evidence / f"{args.stage}.supervisor.log"
        launch = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--stage",
            args.stage,
            "--workspace",
            str(args.workspace.resolve()),
            "--evidence",
            str(args.evidence.resolve()),
            "--done-file",
            str(args.done_file),
        ]
        if args.table:
            launch.extend(["--table", str(args.table.resolve())])
        if args.progress_file:
            launch.extend(["--progress-file", str(args.progress_file.resolve())])
        launch.extend(["--", *command])
        with supervisor_log.open("x") as log:
            child = subprocess.Popen(launch, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print(json.dumps(dict(pid=child.pid, done_file=str(args.done_file), supervisor_log=str(supervisor_log.resolve()))), flush=True)
        return 0
    row = dict(stage=args.stage, exit_code=1, success=False)

    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        row.update(measure(args.stage, command, args.workspace, args.evidence, progress_file=args.progress_file))
        row["success"] = row["exit_code"] == 0 and not row.get("measurement_errors")
        if args.table:
            lines = args.table.read_text().splitlines()
            last = max(i for i, line in enumerate(lines) if line.startswith("|"))
            lines.insert(last + 1, table_row(row))
            args.table.write_text("\n".join(lines) + "\n")
        print(json.dumps(row))
    except BaseException as error:
        row["error"] = str(error) or type(error).__name__
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)
        if args.done_file:
            args.done_file.parent.mkdir(parents=True, exist_ok=True)
            cleanup = Path(__file__).resolve().parents[2] / "scripts/prune-generated.py"
            try:
                with args.done_file.with_suffix(".cleanup.log").open("w") as log:
                    row["cleanup_exit_code"] = subprocess.run([sys.executable, str(cleanup), "--apply"], stdout=log, stderr=subprocess.STDOUT).returncode
            except Exception as error:
                row.update(cleanup_exit_code=1, cleanup_error=str(error))
            row["success"] = row["success"] and row["cleanup_exit_code"] == 0
            temporary = args.done_file.with_suffix(args.done_file.suffix + ".tmp")
            temporary.write_text(json.dumps(row, indent=2) + "\n")
            temporary.replace(args.done_file)
            print("WAITING done-file " + str(args.done_file), flush=True)
    if row["exit_code"] < 0:
        return 128 - row["exit_code"]
    return row["exit_code"] or int(not row["success"])


if __name__ == "__main__":
    sys.exit(main())
