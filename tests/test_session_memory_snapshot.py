"""Execute the production snapshot transaction with a native callback peer and real files."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_portable_diagnostic_input import extract_class, extract_method

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


class SessionMemorySnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mono = EDITOR / "bin/mono"
        compiler = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not cls.mono.is_file() or not compiler.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="session-memory-snapshot-")
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = (ROOT / "tools/unity/runtime/session/SessionResourceBoundary.cs").read_text()
        code = ["using System; using UnityEngine; public sealed partial class PortSession {"]
        code += [extract_class(source, name) for name in ("public class SessionResourceSample", "class RootWalkSelection")]
        code += [
            extract_method(source, name)
            for name in (
                "    RootWalkSelection ReadResourceDiagnostics()",
                "    bool CompletedRootWalkRequested()",
                "    void CaptureCompletedMemorySnapshot(SessionResourceSample sample)",
            )
        ]
        production = directory / "Production.cs"
        production.write_text("\n".join(code) + "\n}")
        cls.exe = directory / "snapshot.exe"
        result = subprocess.run(
            [
                str(cls.mono),
                str(compiler),
                "-nologo",
                "-langversion:9",
                "-r:" + str(EDITOR / "lib/mono/net_4_x-macos/System.Web.Extensions.dll"),
                "-out:" + str(cls.exe),
                str(production),
                str(ROOT / "tests/fixtures/SessionMemorySnapshotHost.cs"),
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def case(self, name):
        with tempfile.TemporaryDirectory(prefix="snapshot-files-") as directory:
            result = subprocess.run(
                [str(self.mono), str(self.exe), name, directory],
                env=dict(os.environ, MONO_PATH=str(EDITOR / "lib/mono/net_4_x-macos")),
                text=True,
                capture_output=True,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ": PASS", result.stdout)

    def test_only_selected_attempt_and_two_post_cleanup_menus_capture(self):
        self.case("admission")

    def test_live_world_network_and_release_build_refuse_before_native_call(self):
        self.case("idle-only")

    def test_native_completion_keeps_private_file_and_reports_callback_success(self):
        self.case("transaction")

    def test_synchronous_native_callback_does_not_publish_startup_session_zero(self):
        self.case("sync-completion")

    def test_missing_wrong_path_and_failed_native_requests_never_claim_success(self):
        self.case("refusal")
