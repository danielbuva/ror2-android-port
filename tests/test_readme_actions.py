import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/readme-actions.py"
with patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
    SPEC = importlib.util.spec_from_file_location("readme_actions", SCRIPT)
    readme_actions = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(readme_actions)


def template():
    return f"# Before\r\n\r\n{readme_actions.START}\nold table\n{readme_actions.END}\n\nAfter.\n"


class ReadmeActionsRenderTests(unittest.TestCase):
    def test_render_filters_historical_and_preserves_registry_order_and_help(self):
        actions = [
            SimpleNamespace(name="z-first", status="current", help="First help."),
            SimpleNamespace(name="old", status="historical", help="Historical help."),
            SimpleNamespace(name="a-last", status="current", help="Last help."),
        ]
        self.assertEqual(
            readme_actions.render_table(actions),
            "| Command | What it does |\n| --- | --- |\n"
            "| `./dev prototype --action z-first` | First help. |\n"
            "| `./dev prototype --action a-last` | Last help. |\n",
        )

    def test_render_escapes_help_pipes_and_keeps_multiline_help_in_one_row(self):
        action = SimpleNamespace(name="example", status="current", help="A | B.\nNext line.")
        self.assertIn(r"| A \| B. Next line. |", readme_actions.render_table([action]))

    def test_render_is_idempotent_and_preserves_surrounding_text(self):
        original = template()
        rendered = readme_actions.render_readme(original)
        self.assertEqual(readme_actions.render_readme(rendered), rendered)
        self.assertEqual(rendered.split(readme_actions.START)[0], original.split(readme_actions.START)[0])
        self.assertEqual(rendered.split(readme_actions.END)[1], original.split(readme_actions.END)[1])
        self.assertIn(readme_actions.render_table(), rendered)

    def test_invalid_markers_are_rejected(self):
        for source in (
            "",
            readme_actions.START,
            readme_actions.END,
            template() + readme_actions.START,
            template() + readme_actions.END,
            readme_actions.END + "\n" + readme_actions.START,
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                readme_actions.render_readme(source)


class ReadmeActionsCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.readme = self.root / "docs" / "DEVELOPING.md"
        self.readme.parent.mkdir()
        self.landing = self.root / "README.md"
        self.landing.write_text("Player landing page.\n", encoding="utf-8")
        self.readme.write_bytes(template().encode("utf-8"))

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return readme_actions.main(list(args), root=self.root)

    def test_generation_leaves_player_landing_untouched(self):
        self.assertEqual(self.command(), 0)
        self.assertEqual(self.command("--check"), 0)
        self.assertEqual(self.landing.read_text(encoding="utf-8"), "Player landing page.\n")

    def test_generate_is_idempotent(self):
        self.assertEqual(self.command(), 0)
        expected = self.readme.read_bytes()
        self.assertEqual(self.command(), 0)
        self.assertEqual(self.readme.read_bytes(), expected)

    def test_check_stale_and_fresh_without_writing(self):
        original = self.readme.read_bytes()
        self.assertEqual(self.command("--check"), 1)
        self.assertEqual(self.readme.read_bytes(), original)
        self.assertEqual(self.command(), 0)
        generated = self.readme.read_bytes()
        with patch.object(Path, "write_bytes", side_effect=AssertionError("--check must not write")):
            self.assertEqual(self.command("--check"), 0)
        self.assertEqual(self.readme.read_bytes(), generated)
        self.readme.write_bytes(generated.replace(b"| Command |", b"| Stale |"))
        stale = self.readme.read_bytes()
        self.assertEqual(self.command("--check"), 1)
        self.assertEqual(self.readme.read_bytes(), stale)

    def test_check_detects_registry_changes(self):
        self.assertEqual(self.command(), 0)
        original = self.readme.read_bytes()
        action = SimpleNamespace(name="new-action", status="current", help="New help.")
        with patch.dict(readme_actions.ACTIONS, {action.name: action}):
            self.assertEqual(self.command("--check"), 1)
        self.assertEqual(self.readme.read_bytes(), original)

    def test_missing_readme_and_invalid_markers_fail_without_writing(self):
        self.readme.unlink()
        self.assertEqual(self.command("--check"), 2)
        self.assertFalse(self.readme.exists())
        self.readme.write_text("No markers.\n", encoding="utf-8")
        for args in ((), ("--check",)):
            self.assertEqual(self.command(*args), 2)
            self.assertEqual(self.readme.read_text(encoding="utf-8"), "No markers.\n")

    def test_cli_check_from_another_directory(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)


if __name__ == "__main__":
    unittest.main()
