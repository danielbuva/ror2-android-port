"""Build a committed worktree through the primary checkout's prepared editor.

The canonical Unity mutex covers source checkout, ordinary ./dev build and source
restoration. No authored file is patched and no Unity project is copied.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

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
