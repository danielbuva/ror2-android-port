#!/usr/bin/env python3
"""Renumber branch-only journal entries above merged main, then regenerate the index.

Host-only: no fetch, commits, staging, or device access. Resolve textual conflicts by
keeping main's entries unchanged and retaining each branch addition as a separate
heading. IDs alone cannot identify ownership: compare complete entries instead.
"""

import argparse
from collections import Counter
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("journal_index_for_renumber", Path(__file__).with_name("journal-index.py"))
journal_index = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = journal_index
SPEC.loader.exec_module(journal_index)
JOURNAL = journal_index.JOURNAL
INDEX = journal_index.INDEX
NUMBER = re.compile(r"J(\d+)")
SINGLE_HEADING = re.compile(r"^(##[ \t]+)J\d+(?=[ \t])")
CONFLICT = re.compile(r"^(?:<{7}|={7}|>{7}|\|{7})(?:\s|$)", re.MULTILINE)


@dataclass(frozen=True)
class Block:
    entry_id: str
    line: int
    text: str

    @property
    def identity(self) -> str:
        # Trailing blank separators are not evidence, and appending an entry can
        # add them to main's last block without editing its heading or body.
        return self.text.rstrip("\r\n")

    @property
    def content(self) -> str:
        return re.sub(r"^(#{2,3}[ \t]+)J\d+(?:/J\d+)*", r"\1", self.identity, count=1)


def blocks(text: str) -> tuple[str, list[Block]]:
    if CONFLICT.search(text):
        raise ValueError("resolve journal conflict markers first, preserving both sets of entries")
    lines = text.splitlines(keepends=True)
    entries = journal_index.parse_journal(text)
    result = []
    for position, entry in enumerate(entries):
        end = entries[position + 1].line_number - 1 if position + 1 < len(entries) else len(lines)
        result.append(Block(entry.entry_id, entry.line_number, "".join(lines[entry.line_number - 1 : end])))
    preamble = "".join(lines[: entries[0].line_number - 1]) if entries else text
    return preamble, result


def renumber(main: str, branch: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Return text and (line, old ID, new ID) changes, or refuse ambiguous ownership.

    Every main entry must occur exactly once, unchanged and in main's order. Main
    can already contain historical duplicate IDs; new entries with colliding IDs
    are safe only when their complete contents are distinct. Never rewrite body
    references: a collided old number may refer to main or to a branch entry.
    """
    main_preamble, main_blocks = blocks(main)
    branch_preamble, branch_blocks = blocks(branch)
    if main_preamble.rstrip("\r\n") != branch_preamble.rstrip("\r\n"):
        raise ValueError("journal preamble differs from main; reconcile it explicitly first")
    counts = Counter(block.identity for block in branch_blocks)
    main_counts = Counter(block.identity for block in main_blocks)
    if any(count != 1 for count in main_counts.values()):
        raise ValueError("main contains identical duplicate entries; ownership is ambiguous")
    for block in main_blocks:
        if counts[block.identity] != 1:
            raise ValueError(f"main entry {block.entry_id} is missing, edited, or duplicated; preserve it unchanged")
    preserved = [block.identity for block in branch_blocks if block.identity in main_counts]
    if preserved != [block.identity for block in main_blocks]:
        raise ValueError("main entries have been reordered; restore main's order first")
    known_contents = {block.content for block in main_blocks}
    next_number = max((int(number) for block in main_blocks for number in NUMBER.findall(block.entry_id)), default=0) + 1
    changes = []
    output = [branch_preamble]
    for block in branch_blocks:
        if block.identity in main_counts:
            output.append(block.text)
            continue
        if block.content in known_contents or counts[block.identity] != 1:
            raise ValueError(f"branch entry at line {block.line} duplicates another entry; ownership is ambiguous")
        known_contents.add(block.content)
        if not SINGLE_HEADING.match(block.text):
            raise ValueError(f"new entry at line {block.line} must use a single ## J<n> heading")
        new_id = f"J{next_number}"
        next_number += 1
        output.append(SINGLE_HEADING.sub(lambda match: match[1] + new_id, block.text, count=1))
        if block.entry_id != new_id:
            changes.append((block.line, block.entry_id, new_id))
    return "".join(output), changes


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True, encoding="utf-8", stderr=subprocess.PIPE)


def merged_main(root: Path, ref: str) -> str:
    """Pin the baseline once; accept a completed or currently resolving merge."""
    commit = git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()
    candidates = ["HEAD"]
    try:
        candidates.extend(git(root, "rev-parse", "--verify", "MERGE_HEAD").splitlines())
    except subprocess.CalledProcessError:
        pass
    for candidate in candidates:
        result = subprocess.run(["git", "merge-base", "--is-ancestor", commit, candidate], cwd=root, capture_output=True)
        if result.returncode == 0:
            return git(root, "show", f"{commit}:{JOURNAL.as_posix()}")
        if result.returncode != 1:
            raise ValueError("cannot verify that main has been merged")
    raise ValueError(f"merge {ref} into this branch before renumbering")


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-ref", default="origin/main", help="already fetched and merged baseline (default: origin/main)")
    parser.add_argument("--dry-run", action="store_true", help="report heading changes without writing either file")
    args = parser.parse_args(argv)
    try:
        baseline = merged_main(root, args.main_ref)
        journal_path, index_path = root / JOURNAL, root / INDEX
        original = journal_path.read_bytes()
        updated, changes = renumber(baseline, original.decode("utf-8"))
        for line, old, new in changes:
            print(f"Line {line}: {old} -> {new}")
        if args.dry_run:
            print(f"Would renumber {len(changes)} headings and regenerate {INDEX}.")
            return 0
        old_index = index_path.read_bytes() if index_path.exists() else None
        try:
            # Blame must see the new headings, just as journal-index.py does.
            journal_path.write_bytes(updated.encode("utf-8"))
            rendered = journal_index.render_index(updated, journal_index.blame_dates(root))
            index_path.write_bytes(rendered.encode("utf-8"))
        except (OSError, ValueError, subprocess.CalledProcessError):
            journal_path.write_bytes(original)
            if old_index is not None:
                index_path.write_bytes(old_index)
            elif index_path.exists():
                index_path.unlink()
            raise
        print(f"Renumbered {len(changes)} headings; generated {INDEX}. Review branch references and links before staging.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Cannot renumber journal: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
