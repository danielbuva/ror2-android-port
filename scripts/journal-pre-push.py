#!/usr/bin/env python3
"""Repair journals on the checked-out topic via a local fast-forward commit.

The caller must stop a push when this exits 3: Git already captured the old
object ID. Nothing here stages other files, rewrites history, or pushes.
"""

import argparse
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("journal_renumber_for_push", Path(__file__).with_name("journal-renumber.py"))
renumber = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = renumber
SPEC.loader.exec_module(renumber)
INDEX, JOURNAL = renumber.INDEX, renumber.JOURNAL
PATHS = [str(JOURNAL), str(INDEX)]


def git(root, *args, **kwargs):
    return subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout


def repair(root, ref, tip, destination):
    try:
        head_ref = git(root, "symbolic-ref", "-q", "HEAD").decode().strip()
        main = git(root, "rev-parse", "--verify", "origin/main^{commit}").decode().strip()
    except subprocess.CalledProcessError:
        return 0  # Detached checkout or no tracked main: let normal CI validate.
    if (
        ref != head_ref
        or not ref.startswith("refs/heads/")
        or ref in {"refs/heads/main", "refs/heads/master"}
        or destination in {"refs/heads/main", "refs/heads/master"}
        or git(root, "rev-parse", "HEAD").decode().strip() != tip
    ):
        return 0
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", main, tip], cwd=root).returncode
    if ancestry == 1:
        return 0
    if ancestry != 0:
        raise ValueError("cannot verify ancestry against origin/main")
    if not git(root, "diff", "--name-only", main, tip, "--", *PATHS):
        return 0

    baseline = git(root, "show", f"{main}:{JOURNAL}").decode("utf-8")
    originals = [git(root, "show", f"{tip}:{path}") for path in PATHS]
    updated, changes = renumber.renumber(baseline, originals[0].decode("utf-8"))
    # Pin the author instant used for any newly blamed heading, including
    # when the hook runs across midnight or GIT_AUTHOR_DATE has an offset.
    timestamp, offset = git(root, "var", "GIT_AUTHOR_IDENT").decode().rsplit(None, 2)[-2:]
    tz = datetime.strptime(offset, "%z").tzinfo
    pending_date = datetime.fromtimestamp(int(timestamp), tz).strftime("%Y-%m-%d")
    with tempfile.TemporaryDirectory(prefix="journal-pre-push-") as directory:
        contents = Path(directory) / "journal.md"
        contents.write_bytes(updated.encode("utf-8"))
        dates = renumber.journal_index.blame_dates(root, contents=contents, pending_date=pending_date)
    generated = [updated.encode("utf-8"), renumber.journal_index.render_index(updated, dates).encode("utf-8")]
    if generated == originals:
        return 0

    if git(root, "status", "--porcelain", "--untracked-files=no") or any((root / path).read_bytes() != old for path, old in zip(PATHS, originals)):
        raise ValueError("commit or stash tracked changes before automatic journal repair")
    if git(root, "rev-parse", "HEAD").decode().strip() != tip:
        raise ValueError("checked-out branch changed while preparing journal repair")
    if not (root / JOURNAL).is_file() or (root / JOURNAL).is_symlink() or (root / INDEX).is_symlink():
        raise ValueError("journal paths must be regular worktree files")

    try:
        for path, data in zip(PATHS, generated):
            (root / path).write_bytes(data)
        git(
            root,
            "commit",
            "--only",
            "-m",
            "docs: reconcile journal with merged main",
            "--",
            *PATHS,
            env={**os.environ, "GIT_AUTHOR_DATE": f"@{timestamp} {offset}"},
        )
    except (OSError, subprocess.CalledProcessError):
        # Do not undo a completed commit even if a downstream hook misreports it.
        if git(root, "rev-parse", "HEAD").decode().strip() == tip:
            for path, data in zip(PATHS, originals):
                (root / path).write_bytes(data)
        raise
    for line, old, new in changes:
        print(f"pre-push: journal line {line}: {old} -> {new} (body references unchanged)", file=sys.stderr)
    print("pre-push: repaired the journal in a new local commit. Run git push again to include it.", file=sys.stderr)
    return 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ref", "tip", "destination"):
        parser.add_argument(key)
    args = parser.parse_args()
    try:
        return repair(ROOT, args.ref, args.tip, args.destination)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = error.stderr.decode(errors="replace").strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(f"pre-push: journal repair refused: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
