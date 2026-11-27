#!/usr/bin/env python3
"""Print affected unittest modules for a pre-push checkout. Empty output means full suite."""

import ast
from collections import defaultdict
from fnmatch import fnmatchcase
import os
from pathlib import Path
import re
import subprocess
import sys
import tokenize


SMOKE = {"test_content_recipe", "test_dev_help", "test_public_privacy"}
FULL = (
    ".github/*",
    ".git*",
    "ruff.toml",
    "tools/lab-requirements.txt",
    "scripts/ci-*",
    "scripts/git-hooks/*",
    "scripts/host-tests.py",
    "scripts/ruff-committed.py",
    "scripts/audit-public.py",
    "scripts/journal-*.py",
    "scripts/readme-actions.py",
    "dev",
    "tests/__init__.py",
    "tests/test_ci_*.py",
    "tests/test_host_test_runner.py",
)

# These consumers construct paths from names, use globs, or check repository
# contracts. Literal references and imports add more specific tests below.
EXPLICIT = {
    "AGENTS.md": {"test_dev_help"},
    "README.md": {"test_readme_actions"},
    "docs/*.md": {"test_dev_help"},
    ".agents/skills/*/SKILL.md": {"test_dev_help"},
    "tools/phone-build/*README.md": {"test_dev_help"},
    "recipe/README.md": {"test_recipes", "test_siren_native_listening_snapshot"},
    "recipe/*.json": {"test_recipes"},
    "recipe/owner-*.jsonl.gz": {"test_recipes", "test_release_graph"},
    "recipe/templates/*-importer.meta": {"test_importer_rebuild"},
    "tools/unity/*.cs": {"test_runtime_sources"},
    "tools/unity/runtime/*.cs": {"test_lane_source_staging", "test_siren_cleanup_ownership", "test_siren_native_encounter_continuation"},
    "scripts/lab/*_check.py": {"test_alpha_stability_batch"},
    "tests/observer-fixtures/*": {
        "test_assembly_slice",
        "test_music_output_observer",
        "test_observer_stage_hook",
        "test_original_music_native_result_observer",
    },
}
KNOWN_SUFFIXES = {".cs", ".csproj", ".gradle", ".gz", ".java", ".json", ".md", ".meta", ".py", ".sh", ".shader", ".traceevents", ".txt", ".xml"}
FILE_TOKEN = re.compile(r"[\w.-]+(?:/[\w.-]+)*\.[\w.-]+")


def git_paths(*args):
    return {os.fsdecode(path) for path in subprocess.check_output(["git", *args]).split(b"\0") if path}


def test_module(path):
    parent, _, filename = path.rpartition("/")
    if parent == "tests" and filename.startswith("test_") and filename.endswith(".py"):
        return Path(filename).stem
    return None


def import_names(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module
                yield from (f"{node.module}.{alias.name}" for alias in node.names)
            elif node.level:
                yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name in {"import_module", "__import__"} and node.args:
                argument = node.args[0]
            elif name == "Action" and len(node.args) > 1:
                # scripts/lab/actions.py resolves the second field through importlib.
                argument = node.args[1]
            else:
                continue
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                yield argument.value.lstrip(".")


def reverse_dependencies(tracked, changed):
    by_filename = defaultdict(set)
    by_module = defaultdict(set)
    for path in tracked | changed:
        parts = path.split("/")
        by_filename[parts[-1]].add(path)
        if path.endswith(".py"):
            module = parts[:-1] if parts[-1] == "__init__.py" else [*parts[:-1], parts[-1][:-3]]
            while module and module[0].isidentifier():
                by_module[".".join(module)].add(path)
                module = module[1:]
            # Tool folders such as accepted-output aren't packages, but their
            # scripts are importable by basename when added to sys.path.
            if parts[-1] != "__init__.py":
                by_module[parts[-1][:-3]].add(path)

    reverse = defaultdict(set)
    for path in sorted(tracked):
        if not path.endswith(".py"):
            continue
        with tokenize.open(path) as stream:
            source = stream.read()
        tree = ast.parse(source, filename=path)
        if test_module(path) and any(isinstance(node, ast.FunctionDef) and node.name == "load_tests" for node in tree.body):
            raise ValueError(f"custom discovery in {path}")
        for name in import_names(tree):
            while name:
                for dependency in by_module.get(name, ()):
                    reverse[dependency].add(path)
                name = name.rpartition(".")[0]
        # Also see paths in subprocess commands, embedded fixture source and
        # Path expressions split across strings. Ambiguous basenames route to
        # every match because lab tools modify sys.path in several places.
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in FILE_TOKEN.findall(node.value):
                    if token in tracked or token in changed:
                        reverse[token].add(path)
                    else:
                        for dependency in by_filename.get(token.rsplit("/", 1)[-1], ()):
                            reverse[dependency].add(path)
    return reverse


def affected_tests(changed, tracked):
    for path in sorted(changed):
        if any(fnmatchcase(path, pattern) for pattern in FULL):
            raise ValueError(f"check infrastructure changed ({path})")
        suffix = Path(path).suffix
        if suffix not in KNOWN_SUFFIXES or suffix == ".gz" and not path.endswith(".jsonl.gz"):
            raise ValueError(f"unknown file type ({path})")
        if path.startswith("tests/") and suffix == ".py" and (not test_module(path) or path not in tracked):
            raise ValueError(f"test discovery or support changed ({path})")

    reverse = reverse_dependencies(tracked, changed)
    selected = SMOKE.copy()
    for path in sorted(changed):
        pending = [path]
        visited = set()
        impacted = set()
        while pending:
            source = pending.pop()
            if source in visited:
                continue
            visited.add(source)
            module = test_module(source)
            if module and source in tracked:
                impacted.add(module)
            for pattern, modules in EXPLICIT.items():
                if fnmatchcase(source, pattern):
                    impacted.update(modules)
            pending.extend(reverse.get(source, ()))
        if not impacted:
            raise ValueError(f"no mapped tests for {path}")
        selected.update(impacted)

    available = {module for path in tracked if (module := test_module(path))}
    if selected - available:
        raise ValueError(f"mapped tests missing: {', '.join(sorted(selected - available))}")
    return sorted(selected)


def main(base):
    try:
        changed = git_paths("diff", "--name-only", "--no-renames", "-z", base, "HEAD", "--")
        tracked = git_paths("ls-files", "-z")
        selected = affected_tests(changed, tracked)
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as error:
        print(f"ci-local: full host suite ({error})", file=sys.stderr)
    else:
        print("\n".join(selected))


if __name__ == "__main__":
    main(sys.argv[1])
