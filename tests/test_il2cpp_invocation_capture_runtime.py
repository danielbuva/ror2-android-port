from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(os.environ.get("ROR2LAB_TEST_ROOT", Path(__file__).resolve().parents[1]))
EDITOR_BIN = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin")
MCS = EDITOR_BIN / "mcs"
MONO = EDITOR_BIN / "mono"
sys.path.insert(0, str(ROOT / "scripts/lab"))
from bee_codegen_capture import collect_request_capture  # noqa: E402
from common import toolchain  # noqa: E402
from bee_codegen_capture import editor_version_from_toolchain  # noqa: E402


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

    def run_mode(self, mode: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(MONO), str(self.harness), mode, *args],
            capture_output=True,
            text=True,
            env={**os.environ, "LAB_HOST_TEMP_ROOT": str(self.temp_root)},
        )

    def test_default_off_returns_before_request_access_and_active_false_is_inert(
        self,
    ) -> None:
        no_session = self.run_mode("default-off", "-labWorkRoot")
        self.assertEqual(no_session.returncode, 0, no_session.stderr)
        self.assertIn("before request/path access", no_session.stdout)
        active_false = self.run_mode("active-off")
        self.assertEqual(active_false.returncode, 0, active_false.stderr)
        self.assertIn("disabled request returned", active_false.stdout)

    def test_csharp_json_receipts_join_to_python_host_capture_and_full_toolchain_pin(
        self,
    ) -> None:
        completed = self.run_mode("roundtrip")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        fields = dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)
        project, work, apk = (Path(fields[name]) for name in ("PROJECT", "WORK", "APK"))
        guid = fields["GUID"]
        request_id, source_commit, input_id = "host-request-1", "a" * 40, "b" * 64

        # Confirm JsonUtility's actual C# field names and the Python collector's
        # expected snake_case schema before attempting the causal evidence join.
        pre = json.loads((work / "lab-build/player-linker-inputs/host-request-1.bee-pre.json").read_text())
        post = json.loads((work / "lab-build/player-linker-inputs/host-request-1.bee-post.json").read_text())
        self.assertEqual(pre["request_id"], request_id)
        self.assertEqual(pre["source_commit"], source_commit)
        self.assertEqual(pre["input_id"], input_id)
        self.assertEqual(pre["editor_version"], editor_version_from_toolchain(toolchain()))
        self.assertEqual(post["build_report_guid"], guid)
        self.assertEqual(post["build_report_output_path"], str(apk))

        managed = [
            "Library/Bee/artifacts/Android/ManagedStripped/Assembly-CSharp.dll",
            "Library/Bee/artifacts/Android/ManagedStripped/RoR2.dll",
        ]
        trace_relative = "Library/Bee/artifacts/il2cpp_conv_current.traceevents"
        trace_path = project / trace_relative
        trace_bytes = b'{"pid":"il2cpp_in_graph","tid":1,"ts":10,"dur":5,"ph":"X","name":"il2cpp.exe"},\n'
        trace_path.write_bytes(trace_bytes)
        (project / "Library/Bee/backend_profiler0.traceevents").write_bytes(b"backend profile")
        for index, relative in enumerate(managed):
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(("managed-" + str(index)).encode())
        rsp_relative = "Library/Bee/artifacts/rsp/123.rsp"
        rsp_path = project / rsp_relative
        rsp_path.parent.mkdir(parents=True, exist_ok=True)
        rsp_path.write_text("--convert-to-cpp " + " ".join(f'--assembly="{path}"' for path in managed) + f' --profiler-output-file="{trace_path}"')
        node = {
            "Annotation": "IL2CPP_CodeGen " + trace_relative,
            "Action": f'"/Unity/il2cpp" @"{rsp_relative}"',
            "ProfilerOutput": trace_relative,
            "Inputs": managed + ["/Unity/il2cpp/il2cpp_root"],
            "Outputs": [trace_relative],
        }
        (project / "Library/Bee/Player123.dag.json").write_text(json.dumps({"Nodes": [node]}))
        (project / "Library/Bee/Player123.dag").write_bytes(b"fresh graph")

        digest = hashlib.sha256(apk.read_bytes()).hexdigest()
        result = {
            "request_id": request_id,
            "success": True,
            "errors": 0,
            "build_report_guid": guid,
            "build_report_output_path": str(apk),
            "input_id": input_id,
            "source": {"commit": source_commit},
            "apk": str(apk),
            "apk_sha256": digest,
        }
        receipt = collect_request_capture(
            project_root=project,
            work_root=work,
            snapshot_destination=work / "bee-snapshot",
            final_result=result,
            request_id=request_id,
            source_commit=source_commit,
            input_id=input_id,
            editor_version=editor_version_from_toolchain(toolchain()),
        )
        self.assertEqual(receipt["build_report_guid"], guid)
        self.assertEqual(
            receipt["managed_inputs"],
            [
                {
                    "path": path,
                    "snapshot_name": Path(path).name,
                    "size": len((project / path).read_bytes()),
                    "sha256": hashlib.sha256((project / path).read_bytes()).hexdigest(),
                }
                for path in managed
            ],
        )
        self.assertEqual(receipt["trace_sha256"], hashlib.sha256(trace_bytes).hexdigest())
        self.assertFalse(receipt["argv_vector_binding"])


if __name__ == "__main__":
    unittest.main()
