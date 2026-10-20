"""Opt-in dispatch and cache contracts without Unity or legitimate game input."""

from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import actions
import build


class SymbolBuildModeTests(unittest.TestCase):
    def test_code_build_keeps_default_arguments_and_forwards_explicit_opt_in(self):
        options = {"code_only": True}
        function = Mock(return_value="build-result")
        self.assertEqual(actions._whole_catalog_code_build(function, options, SimpleNamespace()), "build-result")
        function.assert_called_once_with(code_only=True)
        function.reset_mock()
        actions._whole_catalog_code_build(function, options, SimpleNamespace(debug_symbols=True))
        function.assert_called_once_with(code_only=True, android_symbols="debugging")
        self.assertEqual(options, {"code_only": True})

    def test_invalid_or_destination_symbol_requests_refuse_before_build_access(self):
        with patch.object(build, "assert_build_unblocked") as guard:
            with self.assertRaisesRegex(RuntimeError, "mode"):
                build.build("vulkan", android_symbols="other")
            with self.assertRaisesRegex(RuntimeError, "normal lab build path"):
                build.build("vulkan", destination=Path("unused"), android_symbols="debugging")
            guard.assert_not_called()

    def test_symbol_cache_is_separate_and_validator_drift_invalidates_only_that_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script_dir = root / "scripts/lab"
            script_dir.mkdir(parents=True)
            (script_dir / "build.py").write_text("build tool")
            helper = script_dir / "symbol_artifacts.py"
            helper.write_text("validator one")
            project = root / "work/lab-project"
            for child in ["Assets", "Packages", "ProjectSettings"]:
                (project / child).mkdir(parents=True)
            with (
                patch.object(build, "ROOT", root),
                patch.object(build, "WORK", root / "work"),
                patch.object(build, "toolchain", return_value={"editor": "synthetic"}),
            ):
                ordinary = build.build_cache_key(project, "vulkan")
                symbols = build.build_cache_key(project, "vulkan", "debugging")
                self.assertNotEqual(ordinary, symbols)
                self.assertEqual(ordinary, build.build_cache_key(project, "vulkan", "none"))
                helper.write_text("validator two")
                self.assertEqual(ordinary, build.build_cache_key(project, "vulkan"))
                self.assertNotEqual(symbols, build.build_cache_key(project, "vulkan", "debugging"))


if __name__ == "__main__":
    unittest.main()
