"""Build a committed worktree through the primary checkout's prepared editor.

The canonical Unity mutex covers source checkout, ordinary ./dev build and source
restoration. No authored file is patched and no Unity project is copied.
"""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from subprocess import Popen
import sys
import signal
import traceback
import time

from build_lock import host_build_lock
from common import ROOT


def git(root, *arguments):
    return subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True, text=True).stdout.strip()


def clean(root):
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("Shared build requires clean source checkouts; preserve and commit local changes first")
    for marker in ("MERGE_HEAD", "rebase-apply", "rebase-merge", "CHERRY_PICK_HEAD"):
        marker_path = Path(git(root, "rev-parse", "--git-path", marker))
        if (marker_path if marker_path.is_absolute() else root / marker_path).exists():
            raise RuntimeError("Shared build refuses an unfinished Git operation")


def invoke(root, arguments, *, env, pass_fds):
    subprocess.run([str(root / "dev"), *arguments], cwd=root, env=env, pass_fds=pass_fds, check=True)


def build_shared_checkout(
    code_only=True, android_symbols="none", capture_player_linker_inputs=False, capture_il2cpp_invocation=False, root=None, iteration_mode=""
):
    """Temporarily select this exact HEAD in the clean primary working tree.

    Refuse concurrent source edits rather than overwriting them. The primary
    branch is restored on build/preflight failure as well as success. This action
    never installs or selects a device.
    """
    root = Path(root or ROOT).resolve(strict=True)
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    primary = common.parent
    if common.name != ".git" or not (primary / "dev").is_file():
        raise RuntimeError("Shared build requires a normal primary checkout in the same repository")
    if android_symbols not in {"none", "debugging"} or capture_il2cpp_invocation and not capture_player_linker_inputs:
        raise ValueError("Invalid shared build options")
    if (
        iteration_mode not in {"", "export-splice", "scripts-only"}
        or iteration_mode
        and (not code_only or android_symbols != "none" or capture_player_linker_inputs)
    ):
        raise ValueError("Invalid shared iteration build options")
    target = git(root, "rev-parse", "HEAD")
    lock = primary / "work/coordination/unity-build.lock"
    with host_build_lock(lock, operation="shared committed-source build " + target):
        clean(root)
        clean(primary)
        if git(root, "rev-parse", "HEAD") != target:
            raise RuntimeError("Worktree HEAD changed while waiting for the shared editor")
        if not code_only and shutil.disk_usage(primary).free < 100 * 1024**3:
            raise RuntimeError("Less than 100 GiB free; prune generated outputs before the full shared build")
        original = git(primary, "rev-parse", "HEAD")
        branch = git(primary, "symbolic-ref", "--quiet", "--short", "HEAD") if git(primary, "rev-parse", "--abbrev-ref", "HEAD") != "HEAD" else None
        receipt_dir = primary / "work/coordination/shared-builds"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = receipt_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + ".json")
        facts = dict(source_commit=target, primary_before=original, primary_branch=branch, code_only=code_only, restored=False, success=False)
        receipt.write_text(json.dumps(facts, indent=2) + "\n")
        # The ordinary child ./dev validates and forwards this exact inherited
        # open-file description; never replace/unlink the persistent lock file.
        import build_lock

        prior_lock = build_lock.HOST_BUILD_LOCK
        build_lock.HOST_BUILD_LOCK = lock
        try:
            inherited_env, descriptors = build_lock.active_lock_handoff()
        finally:
            build_lock.HOST_BUILD_LOCK = prior_lock
        environment = dict(os.environ, **inherited_env)
        switched = target != original
        try:
            if switched:
                git(primary, "switch", "--detach", target)
            invoke(primary, ["preflight", "--host-only"], env=environment, pass_fds=descriptors)
            options = ["prototype", "--action", "whole-catalog-code-build" if code_only else "whole-catalog-build"]
            if iteration_mode:
                options = ["prototype", "--action", "whole-catalog-fast-build" if iteration_mode == "export-splice" else "whole-catalog-scripts-build"]
            if android_symbols == "debugging":
                options.append("--debug-symbols")
            if capture_player_linker_inputs:
                options.append("--capture-player-linker-inputs")
            if capture_il2cpp_invocation:
                options.append("--capture-il2cpp-invocation")
            invoke(primary, options, env=environment, pass_fds=descriptors)
            clean(primary)
            if git(primary, "rev-parse", "HEAD") != target or git(root, "rev-parse", "HEAD") != target:
                raise RuntimeError("Source HEAD changed during the shared build")
            facts["success"] = True
        finally:
            try:
                # Preserve any unexpected edit/ref change. Never reset, stash or
                # discard another worker's files in order to restore the branch.
                clean(primary)
                if git(primary, "rev-parse", "HEAD") != target:
                    raise RuntimeError("Primary HEAD changed; preserve it for recovery")
                if switched:
                    if branch and git(primary, "rev-parse", "refs/heads/" + branch) != original:
                        raise RuntimeError("Primary branch moved; preserve the checkout for recovery")
                    git(primary, "switch", branch) if branch else git(primary, "switch", "--detach", original)
                facts["restored"] = True
            finally:
                facts["success"] = facts["success"] and facts["restored"]
                receipt.write_text(json.dumps(facts, indent=2) + "\n")
        return dict(facts, receipt=str(receipt))


def wait_for_storage(primary, seconds):
    deadline = time.monotonic() + seconds
    while shutil.disk_usage(primary).free < 100 * 1024**3:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Less than 100 GiB free before full build; storage wait expired")
        time.sleep(min(30, remaining))


def run_request(request_path, *, dry_run=False, detach=False):
    """Supervise the existing build, retaining a terminal receipt on failure too."""
    request_path = Path(request_path).resolve(strict=True)
    request = json.loads(request_path.read_text())
    root = Path(ROOT).resolve(strict=True)
    primary = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    output = Path(request["output"])
    if not output.is_absolute() or not output.resolve().is_relative_to((primary / "work/coordination").resolve()):
        raise ValueError("Build output must be absolute and under primary work/coordination")
    output = output.resolve()
    done = output / "terminal.done.json"
    if done.exists():
        raise RuntimeError("Build already completed; consume its terminal receipt")
    result = dict(success=False, source_commit=request["source_commit"])
    try:
        if git(root, "rev-parse", "HEAD") != request["source_commit"]:
            raise RuntimeError("Requested build source no longer matches worktree HEAD")
        clean(root)
        clean(primary)
        if type(request["full"]) is not bool:
            raise ValueError("full must be a boolean")
        storage_wait = request.get("storage_wait_seconds", 0)
        if type(storage_wait) is not int or not 0 <= storage_wait <= 3600:
            raise ValueError("storage_wait_seconds must be an integer between 0 and 3600")
        storage_ready = not request["full"] or shutil.disk_usage(primary).free >= 100 * 1024**3
        if not storage_ready and not storage_wait:
            raise RuntimeError("Less than 100 GiB free before full build")
        if dry_run:
            return dict(smoke=True, source_commit=request["source_commit"], full=request["full"], storage_ready=storage_ready, done_file=str(done))
        output.mkdir(parents=True, exist_ok=True)
        if detach:
            if (output / "job.json").exists():
                raise RuntimeError("Build already dispatched; consume its terminal receipt")
            with (output / "runner.log").open("w") as log:
                job = Popen(
                    [
                        "/bin/bash",
                        "-c",
                        'source "$1/scripts/env.sh" && exec "$2" "$1/scripts/lab/shared_checkout_build.py" --request "$3"',
                        "shared-build",
                        str(root),
                        sys.executable,
                        str(request_path),
                    ],
                    cwd=root,
                    start_new_session=True,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            (output / "job.json").write_text(json.dumps(dict(pid=job.pid, done_file=str(done))) + "\n")
            return dict(pid=job.pid, done_file=str(done))
        if request["full"]:
            print("Checking full-build headroom; bounded wait=" + str(storage_wait) + " seconds", flush=True)
            wait_for_storage(primary, storage_wait)
        if git(root, "rev-parse", "HEAD") != request["source_commit"]:
            raise RuntimeError("Requested build source changed during storage wait")
        result.update(build_shared_checkout(root=root, code_only=not request["full"]))
    except BaseException:
        if dry_run or detach:
            raise
        result["error"] = traceback.format_exc()
    finally:
        if not dry_run and not detach:
            output.mkdir(parents=True, exist_ok=True)
            try:
                cleanup = subprocess.run([sys.executable, str(root / "scripts/prune-generated.py"), "--apply"], cwd=root, check=False)
                result["prune_exit"] = cleanup.returncode
                result["success"] = result["success"] and cleanup.returncode == 0
            except BaseException:
                result["success"] = False
                result["cleanup_error"] = traceback.format_exc()
            done.write_text(json.dumps(result, indent=2) + "\n")
            print("WAITING done-file " + str(done), flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Current: supervise a committed shared build from request JSON (source_commit, full, output).")
    parser.add_argument("--request", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Validate source, paths and storage without editor actions")
    modes.add_argument("--detach", action="store_true", help="Source scripts/env.sh, launch a new session and always retain a terminal receipt")
    args = parser.parse_args(argv)

    def interrupted(signum, frame):
        raise RuntimeError("Shared build interrupted by signal " + str(signum))

    signal.signal(signal.SIGTERM, interrupted)
    result = run_request(args.request, dry_run=args.dry_run, detach=args.detach)
    print(json.dumps(result), flush=True)
    if args.detach:
        print("WAITING done-file " + result["done_file"], flush=True)
    return 0 if args.dry_run or args.detach or result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
