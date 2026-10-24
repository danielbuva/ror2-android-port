"""Public runner admission and retained failure evidence, without SDK inputs."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("sdk_runner", Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/build_sdk_runner.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class SdkRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.ndk = self.root / "ndk"
        self.ndk.mkdir()
        self.output = self.root / "output"

    def invoke(self):
        return RUNNER.build(self.source, self.ndk, self.root / "cmake", self.root / "llvm-ar", self.root / "llvm-ranlib", self.root / "llvm-strip", self.output)

    def test_unknown_or_modified_source_refuses_before_output(self):
        for revision, dirty in (("0" * 40, ""), (RUNNER.REVISION, " M src/main.c\n")):
            with self.subTest(revision=revision, dirty=dirty), patch.object(RUNNER.subprocess, "check_output", side_effect=[revision, dirty]):
                with self.assertRaisesRegex(ValueError, "unchanged pinned"):
                    self.invoke()
                self.assertFalse(self.output.exists())

    def test_unknown_sdk_refuses_before_output(self):
        (self.ndk / "source.properties").write_text("Pkg.Revision = unknown\n")
        with patch.object(RUNNER.subprocess, "check_output", side_effect=[RUNNER.REVISION, ""]):
            with self.assertRaisesRegex(ValueError, "NDK r21d"):
                self.invoke()
        self.assertFalse(self.output.exists())

    def test_failure_retains_logs_and_multicall_names(self):
        (self.ndk / "source.properties").write_text("Pkg.Revision = 21.3.6528147\n")
        for name in (
            "build/cmake/android.toolchain.cmake",
            "toolchains/llvm/prebuilt/darwin-x86_64/bin/clang",
            "toolchains/llvm/prebuilt/darwin-x86_64/bin/ld.lld",
        ):
            path = self.ndk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("authored fixture, not an SDK\n")
        tool = self.root / "llvm-ar"
        tool.write_text("#!/bin/sh\nprintf 'deliberate compiler fixture failure\\n' >&2\nexit 9\n")
        tool.chmod(0o700)
        for name in ("cmake", "llvm-ranlib", "llvm-strip"):
            (self.root / name).symlink_to(tool.name)
        with patch.object(RUNNER.subprocess, "check_output", side_effect=[RUNNER.REVISION, ""]):
            with self.assertRaisesRegex(ValueError, "step 0 failed with 9"):
                self.invoke()
        result = json.loads((self.output / "result.json").read_text())
        self.assertFalse(result["success"])
        self.assertIn("deliberate compiler fixture failure", (self.output / "0.stderr").read_text())
        self.assertEqual(Path(result["commands"][0][0]).name, "cmake")
        self.assertEqual(Path(result["commands"][2][0]).name, "llvm-strip")
        self.assertIn("llvm-ranlib", (self.output / "android-toolchain.cmake").read_text())


if __name__ == "__main__":
    unittest.main()
