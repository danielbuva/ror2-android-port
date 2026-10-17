#!/usr/bin/env python3
"""Generate the journal navigation table using one Git blame invocation."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import subprocess
import sys
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
JOURNAL = Path("docs/PORTING_JOURNAL.md")
INDEX = Path("docs/JOURNAL_INDEX.md")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
ENTRY_ID = re.compile(r"^(J\d+(?:/J\d+)*)\s+(?:—\s+)?(.+)$")
BLAME_HEADER = re.compile(r"^[0-9a-f]+ \d+ (\d+)(?: \d+)?$")


@dataclass(frozen=True)
class Entry:
    entry_id: str
    title: str
    line_number: int
    anchor: str
    summary: str


def github_slug(heading: str) -> str:
    """Slug rendered heading text; duplicate suffixes are handled by the parser.

    Rules: https://docs.github.com/en/get-started/writing-on-github/
    getting-started-with-writing-and-formatting-on-github/
    basic-writing-and-formatting-syntax#section-links
    """
    heading = re.sub(r"!?\[([^\]]*)\]\([^)]+\)", r"\1", heading)
    heading = re.sub(r"<[^>]*>", "", heading)
    heading = re.sub(r"(?<!\w)(_+)(.+?)\1(?!\w)", r"\2", heading)
    characters = []
    for character in heading.strip().lower():
        if character == " ":
            characters.append("-")
        elif character in "-_" or unicodedata.category(character)[0] in "LMN":
            characters.append(character)
    return "".join(characters)


def first_sentence(body: str, limit: int = 160) -> str:
    """Keep sentence punctuation, ignoring inline code and embedded decimal dots."""
    text = " ".join(body.split())
    code_ticks = 0
    for match in re.finditer(r"`+|[.!?]", text):
        token = match.group()
        if token.startswith("`"):
            if code_ticks == 0:
                code_ticks = len(token)
            elif code_ticks == len(token):
                code_ticks = 0
            continue
        if code_ticks:
            continue
        end = match.end()
        # Include closing quotation marks, parentheses and Markdown emphasis.
        while end < len(text) and text[end] in '\"\'”’)]}*_':
            end += 1
        if end == len(text) or text[end].isspace():
            text = text[:end]
            break
    if len(text) > limit:
        return text[:limit - 1].rstrip() + "…"
    return text


def parse_journal(text: str) -> list[Entry]:
    """Read entries in source order and allocate anchors across all headings.

    Entries are H2 headings plus J-numbered H3 headings: the journal writes 36
    standalone entries (J169, J170, J402–J431) at H3. Other H3s stay in the body.
    """
    lines = text.splitlines()
    headings = []
    used_anchors = set()
    fence = ""
    for line_number, line in enumerate(lines, 1):
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            continue
        if fence:
            continue
        match = HEADING.match(line)
        if not match:
            continue
        level, heading = match.groups()
        base = github_slug(heading)
        anchor = base
        suffix = 0
        while anchor in used_anchors:
            suffix += 1
            anchor = f"{base}-{suffix}"
        used_anchors.add(anchor)
        if level == "##" or (level == "###" and ENTRY_ID.fullmatch(heading)):
            headings.append((line_number, heading, anchor))

    entries = []
    for position, (line_number, heading, anchor) in enumerate(headings):
        match = ENTRY_ID.fullmatch(heading)
        if not match:
            raise ValueError(f"Unrecognized journal heading at line {line_number}")
        entry_id, title = match.groups()
        end = headings[position + 1][0] - 1 if position + 1 < len(headings) else len(lines)
        body = "\n".join(lines[line_number:end])
        entries.append(Entry(entry_id, title, line_number, anchor, first_sentence(body)))
    return entries


def blame_dates(root: Path) -> dict[int, str]:
    """Map final line numbers to author dates in the author's recorded timezone.

    Using author-tz (not the machine's zone) keeps --check identical on a UTC CI runner.
    """
    output = subprocess.check_output(
        ["git", "blame", "--line-porcelain", JOURNAL.as_posix()],
        cwd=root,
        text=True,
        encoding="utf-8",
        stderr=subprocess.PIPE,
    )
    dates = {}
    line_number = None
    author_time = None
    author_tz = None
    for line in output.splitlines():
        match = BLAME_HEADER.fullmatch(line)
        if match:
            line_number = int(match.group(1))
            author_time = None
            author_tz = None
        elif line.startswith("author-time "):
            author_time = int(line.removeprefix("author-time "))
        elif line.startswith("author-tz "):
            offset = line.removeprefix("author-tz ")
            minutes = int(offset[1:3]) * 60 + int(offset[3:5])
            author_tz = timezone(timedelta(minutes=-minutes if offset[0] == "-" else minutes))
        elif line.startswith("\t"):
            if line_number is None or author_time is None or author_tz is None:
                raise ValueError("Git blame record lacks a line number, author-time or author-tz")
            dates[line_number] = datetime.fromtimestamp(author_time, author_tz).strftime("%Y-%m-%d")
    return dates


def escape_cell(text: str) -> str:
    return text.replace("|", r"\|")


def render_index(journal: str, dates: dict[int, str]) -> str:
    lines = [
        "# Porting journal index",
        "",
        "Generated from [PORTING_JOURNAL.md](PORTING_JOURNAL.md); do not edit by hand.",
        "Regenerate from the repository root with `python3 scripts/journal-index.py`.",
        "CI freshness check: `python3 scripts/journal-index.py --check`.",
        "Search this index before repeating an experiment, then read the linked evidence.",
        "",
        "Newest entries appear first (reverse journal order). Dates use the heading line's",
        "Git blame author date in the author's timezone. Summaries show the first sentence, capped at 160 characters.",
        "",
        "| Entry | Date | Title | First sentence |",
        "| --- | --- | --- | --- |",
    ]
    for entry in reversed(parse_journal(journal)):
        if entry.line_number not in dates:
            raise ValueError(f"Missing Git blame date for heading at line {entry.line_number}")
        cells = [
            f"[{entry.entry_id}](PORTING_JOURNAL.md#{entry.anchor})",
            dates[entry.line_number],
            entry.title,
            entry.summary,
        ]
        lines.append("| " + " | ".join(escape_cell(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the index is missing or stale")
    args = parser.parse_args(argv)
    try:
        journal = (root / JOURNAL).read_text(encoding="utf-8")
        expected = render_index(journal, blame_dates(root)).encode("utf-8")
        destination = root / INDEX
        if args.check:
            if not destination.exists() or destination.read_bytes() != expected:
                print(f"{INDEX} is stale; run python3 scripts/journal-index.py", file=sys.stderr)
                return 1
            print(f"{INDEX} is up to date.")
        else:
            destination.write_bytes(expected)
            print(f"Generated {INDEX}.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Cannot generate journal index: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
