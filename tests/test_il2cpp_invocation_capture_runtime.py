from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("ROR2LAB_TEST_ROOT", Path(__file__).resolve().parents[1]))
EDITOR_BIN = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin")
MCS = EDITOR_BIN / "mcs"
MONO = EDITOR_BIN / "mono"


class Il2CppInvocationCaptureRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MCS.is_file() or not MONO.is_file():
            raise unittest.SkipTest("pinned Unity Mono compiler/runtime is unavailable")
        cls.build_temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", tempfile.gettempdir()))
        cls.temp_root = Path(cls.build_temp.name)
        cls.harness = cls.temp_root / "Il2CppCaptureHarness.exe"
        sources = [
            ROOT / "tests/Il2CppCaptureUnityStubs.cs",
            ROOT / "android/Assets/Editor/Il2CppInvocationCapture.cs",
            ROOT / "tests/Il2CppCaptureHarness.cs",
        ]
        subprocess.run(
            [str(MCS), "-out:" + str(cls.harness), *(str(path) for path in sources)],
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "build_temp"):
            cls.build_temp.cleanup()

    def run_case(self, mode: str, *, opted: bool = False) -> subprocess.CompletedProcess[str]:
        work = self.temp_root / "fixture"
        env = dict(os.environ)
        env["LAB_HOST_TEMP_ROOT"] = str(self.temp_root)
        args = [str(MONO), str(self.harness), mode]
        if opted:
            args.extend(["-labWorkRoot", str(self.temp_root / "fixture/unity-project/.rebuild/unity/request-work")])
        return subprocess.run(args, capture_output=True, text=True, env=env)

    def test_request_gates_and_capture_lifecycle_contracts(self) -> None:
        default = self.run_case("default-off")
        self.assertEqual(default.returncode, 0, default.stderr)
        missing_value = subprocess.run(
            [str(MONO), str(self.harness), "default-off", "-labWorkRoot"],
            capture_output=True,
            text=True,
            env={**os.environ, "LAB_HOST_TEMP_ROOT": str(self.temp_root)},
        )
        self.assertEqual(missing_value.returncode, 0, missing_value.stderr)
        for mode, expected, explicit_root in [
            ("explicit-off", "explicit-off host contract passed", True),
            ("split-root", "distinct project/work-root host contract passed", True),
            ("default-root", "distinct project/work-root host contract passed", False),
            ("wrong-active", "wrong-active-request refusal host contract passed", False),
            ("duplicate-directory", "duplicate-directory refusal host contract passed", True),
            ("cancel", "cancel cleanup host contract passed", True),
        ]:
            with self.subTest(mode=mode):
                result = self.run_case(mode, opted=explicit_root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
