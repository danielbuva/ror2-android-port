"""A Unity 'Succeeded' terminal with shader errors must never select an APK."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build
import build_lock
from common import read, write


class BuildErrorTests(unittest.TestCase):
    def test_success_with_reported_errors_cannot_publish_build_or_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            (root / "android/Assets").mkdir(parents=True)
            (root / "android/Assets/AuthoredFixture.cs").write_text("// Test-only source fixture\n")
            (root / "scripts/lab").mkdir(parents=True)
            (root / "scripts/lab/build.py").write_text("# Test-only recipe fixture\n")
            (work / "lab-project/Assets").mkdir(parents=True)
            observer = root / "tools/android-write-interruption/LabPendingWriteStop.java"
            observer.parent.mkdir(parents=True)
            observer.write_text("// Test-only observer source fixture\n")

            def editor(target, action):
                if action == "build":
                    write(
                        work / "lab-build/result.json",
                        {
                            "request_id": read(work / "build-request.json")["request_id"],
                            "success": True,
                            "result": "Succeeded",
                            "errors": 36,
                            "apk": "unused-test-output.apk",
                        },
                    )
                return "test fixture"

            with (
                patch.object(build, "ROOT", root),
                patch.object(build, "WORK", work),
                patch.object(build, "HOST_BUILD_LOCK", root / "coordination/unity-build.lock"),
                patch.object(build_lock, "HOST_BUILD_LOCK", root / "coordination/unity-build.lock"),
                patch.object(build, "assert_build_unblocked"),
                patch.object(build, "preflight_host"),
                patch.object(build, "editor", side_effect=editor),
            ):
                with self.assertRaisesRegex(RuntimeError, "build errors=36"):
                    build.build("vulkan", True)
            self.assertFalse((work / "config/current-build.json").exists())
            self.assertFalse((work / "build-cache").exists())
