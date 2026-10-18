#!/usr/bin/env python3
"""Generate the README's current prototype action table from the registry."""

import argparse
from pathlib import Path
import sys

from lab.actions import ACTIONS


ROOT = Path(__file__).resolve().parents[1]
README = Path("README.md")
START = "<!-- prototype-actions:start -->"
END = "<!-- prototype-actions:end -->"


def render_table(actions=None) -> str:
    """Keep current actions in registry order; never import their implementations."""
    if actions is None:
        actions = ACTIONS.values()
    lines = ["| Command | What it does |", "| --- | --- |"]
    for action in actions:
        if action.status == "current":
            help_text = " ".join(action.help.splitlines()).replace("|", r"\|")
            lines.append(f"| `./dev prototype --action {action.name}` | {help_text} |")
    return "\n".join(lines) + "\n"


def render_readme(readme: str) -> str:
    """Replace only the marked section, rejecting ambiguous or missing markers."""
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one start marker and one end marker")
    start = readme.index(START) + len(START)
    end = readme.index(END)
    if start > end:
        raise ValueError("README action markers are reversed")
    return readme[:start] + "\n\n" + render_table() + "\n" + readme[end:]


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the README action table is stale")
    args = parser.parse_args(argv)
    try:
        destination = root / README
        original = destination.read_bytes()
        expected = render_readme(original.decode("utf-8")).encode("utf-8")
        if args.check:
            if original != expected:
                print(f"{README} action table is stale; run python3 scripts/readme-actions.py", file=sys.stderr)
                return 1
            print(f"{README} action table is up to date.")
        else:
            if original != expected:
                destination.write_bytes(expected)
            print(f"Generated {README} action table.")
    except (OSError, ValueError) as error:
        print(f"Cannot generate README action table: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
