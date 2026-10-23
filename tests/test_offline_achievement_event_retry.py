"""Execute the production event owner; collaborators model transaction boundaries only."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/progression/AndroidProfileBoundary.cs"
FIXTURE = ROOT / "tests/fixtures/offline_achievement_event_retry_host.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
COMPILER = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


def production_method(source: str) -> str:
    signature = "void RecordOfflineOriginalEvent(string identifier, string eventSource = null)"
    # Ignore braces in comments/strings while preserving the actual source bytes.
    lexical = re.compile(r"//[^\n]*|/\*.*?\*/|@\"(?:[^\"]|\"\")*\"|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", re.S)
    masked = lexical.sub(lambda match: " " * len(match.group()), source)
    start = source.index(signature)
    opening = masked.index("{", start + len(signature))
    depth = 0
    for end in range(opening, len(masked)):
        if masked[end] == "{":
            depth += 1
        elif masked[end] == "}":
            depth -= 1
            if depth == 0:
                return source[start : end + 1]
    raise AssertionError("Unclosed production event owner")


class OfflineAchievementEventRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (MONO.is_file() and COMPILER.is_file()):
            raise unittest.SkipTest("pinned Unity Mono/Roslyn host compiler is unavailable")
        scratch = ROOT / "work/host-tests/offline-achievement-event-retry"
        scratch.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="compile-", dir=scratch)
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        source = directory / "OfflineAchievementEventRetryHost.cs"
        cls.executable = directory / "OfflineAchievementEventRetryHost.exe"
        harness = FIXTURE.read_text() + "\npartial class AndroidProfileSession {\n" + production_method(SOURCE.read_text()) + "\n}\n"
        source.write_text(harness)
        compiled = subprocess.run(
            [str(MONO), str(COMPILER), "-nologo", f"-out:{cls.executable}", str(source)],
            cwd=directory,
            capture_output=True,
            text=True,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def run_contract(self, scenario):
        result = subprocess.run([str(MONO), str(self.executable), scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: " + scenario, result.stdout)

    def test_failed_candidate_can_retry_the_same_genuine_event(self):
        self.run_contract("candidate-failure")

    def test_failed_commit_can_retry_the_same_genuine_event(self):
        self.run_contract("commit-failure")

    def test_reentrant_event_keeps_its_in_flight_reservation(self):
        self.run_contract("reentrant")

    def test_assisted_event_is_refused_and_deduplicated(self):
        self.run_contract("assisted")

    def test_successful_refusal_remains_deduplicated(self):
        self.run_contract("refused")

    def test_post_commit_observation_failure_keeps_reservation(self):
        self.run_contract("observation-failure")

    def test_post_commit_report_failure_keeps_reservation(self):
        self.run_contract("report-failure")


if __name__ == "__main__":
    unittest.main()
