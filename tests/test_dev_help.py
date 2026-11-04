"""Every public dev command/action must disclose its lifecycle without running it."""

import ast
import contextlib
import io
import os
from pathlib import Path
import re
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import actions


def tree(name):
    return ast.parse((ROOT / "scripts/lab" / name).read_text())


def choices(source, argument):
    for node in ast.walk(source):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == argument:
                return ast.literal_eval(next(kw.value for kw in node.keywords if kw.arg == "choices"))
    raise AssertionError(f"No choices found for {argument}")


def action_names(source):
    names = set()
    for node in ast.walk(source):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if not (isinstance(left, ast.Name) and left.id == "action" or isinstance(left, ast.Attribute) and left.attr == "action"):
            continue
        for value in node.comparators:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                names.add(value.value)
            elif isinstance(value, (ast.Set, ast.List, ast.Tuple)):
                names.update(ast.literal_eval(value))
    return names


class DevHelpTests(unittest.TestCase):
    def help(self, *arguments):
        output = io.StringIO()
        with patch.dict(os.environ), patch.object(sys, "argv", ["dev", *arguments, "--help"]), contextlib.redirect_stdout(output):
            os.environ.pop("LAB_LANE", None)
            with self.assertRaises(SystemExit) as ended:
                runpy.run_path(str(ROOT / "scripts/lab/main.py"), run_name="__main__")
        self.assertEqual(ended.exception.code, 0)
        return output.getvalue()

    def test_every_top_level_command_has_a_help_label(self):
        labels = dict(re.findall(r"^  ([a-z-]+): (current|historical)$", self.help(), re.MULTILINE))
        self.assertEqual(set(choices(tree("main.py"), "command")), set(labels))

    def test_every_prototype_action_has_a_visible_valid_status(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            actions.print_actions()
        status = None
        listed = {}
        for line in output.getvalue().splitlines():
            if line in ("current:", "historical:"):
                status = line[:-1]
            else:
                listed[line.split()[0]] = status
        for action in (*actions.ACTIONS.values(), actions.DEFAULT_ACTION):
            with self.subTest(action=action.name):
                self.assertIn(action.status, ("current", "historical"))
                self.assertEqual(listed.get(action.name), action.status)

    def test_editor_and_perf_actions_have_architecture_labels(self):
        architecture = (ROOT / "docs/ARCHITECTURE.md").read_text()
        labels = re.findall(r"^\| (editor|perf) \| `([^`]+)` \| (current|historical) \|$", architecture, re.MULTILINE)
        editor = {name for command, name, _ in labels if command == "editor"}
        build_editor = next(node for node in tree("build.py").body if isinstance(node, ast.FunctionDef) and node.name == "editor")
        self.assertEqual(editor, action_names(tree("editor.py")) | action_names(build_editor) | {"inspect"})
        documented = editor | {name for command, name, _ in labels if command == "perf"}
        known = documented | set(actions.ACTIONS) | {actions.DEFAULT_ACTION.name, "list"}
        self.assertEqual(action_names(tree("main.py")) - known, set(), "New CLI action needs an explicit lifecycle label")
        self.assertIn(("perf", "cpu", "current"), labels)
        self.assertIn(("perf", "inspect", "current"), labels)

    def test_lane_action_choices_are_labelled_in_help(self):
        help_text = self.help("lane")
        label = next(line for line in help_text.splitlines() if "Current: create" in line)
        for name in choices(tree("build_lanes.py"), "--action"):
            self.assertIn(name, label)
