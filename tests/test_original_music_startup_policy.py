from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_root()
EDITOR_CONTENTS = Path(
    os.environ.get(
        "UNITY_EDITOR_PATH",
        "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
    )
).expanduser()
MONO = EDITOR_CONTENTS / "MonoBleedingEdge/bin/mono"
MCS = EDITOR_CONTENTS / "MonoBleedingEdge/bin/mcs"
CONTRACT = ROOT / "tools/unity/runtime/session/OriginalMusicControllerContract.cs"
HARNESS = ROOT / "tests/fixtures/original_music_startup_policy_harness.cs"
OWNER = ROOT / "tools/unity/runtime/session/PortSessionOriginalMusicControllerOwner.cs"


class OriginalMusicStartupPolicyTests(unittest.TestCase):
    def test_contract_policy_gates_27_cases(self) -> None:
        if not MONO.is_file() or not MCS.is_file():
            self.skipTest("pinned Unity Mono/mcs host tools are unavailable")
        with tempfile.TemporaryDirectory(prefix="original-music-startup-policy-") as temp:
            output = Path(temp) / "OriginalMusicStartupPolicy.exe"
            compiled = subprocess.run(
                [str(MCS), "-nologo", f"-out:{output}", str(CONTRACT), str(HARNESS)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(MONO), str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("PASS: 27 adapted original music startup gate assertions", executed.stdout)

    def test_owner_attempt_is_original_component_only_and_queue_gated(self) -> None:
        owner = OWNER.read_text(encoding="utf-8")
        self.assertIn("outputResultObserved, snapshot.outputAccepted", owner)
        self.assertIn("triggerRoot.AddComponent<TriggerIntroMusicStart>()", owner)
        self.assertNotRegex(owner, r"\b(?:StartIntroMusic|PostEvent|SetState)\s*\(")
        self.assertIn("queue result", owner)
        self.assertIn("does not prove native activation or playback", owner)


if __name__ == "__main__":
    unittest.main()
