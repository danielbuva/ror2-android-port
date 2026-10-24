"""Execute the native feedback product sources with controlled GUI/platform peers."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "tools/unity/runtime/input"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class AndroidFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="android-feedback-host-")
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        # Compile the complete production OnGUI method too: the fixture's world
        # widget must never execute on the event opening or leaving feedback.
        source = (RUNTIME / "NovaInputBoundary.cs").read_text()
        method = source.split("    void OnGUI()\n", 1)[1].split("    bool IsNovaInput()", 1)[0]
        caller = directory / "Caller.cs"
        caller.write_text("using UnityEngine;\npublic sealed partial class PortSession {\nvoid OnGUI()\n" + method + "\n}\n")
        application = (ROOT / "tools/unity/runtime/session/OfflineApplicationBoundary.cs").read_text()
        application_method = application.split("        public void ObserveOfflineApplicationInput()\n", 1)[1].split(
            "        public bool DrawOfflineStart()", 1
        )[0]
        application_caller = directory / "ApplicationInput.cs"
        application_caller.write_text(
            "using UnityEngine;\npublic sealed partial class PortSession {\n"
            "sealed partial class OfflineApplicationSession {\n"
            "public void ObserveOfflineApplicationInput()\n" + application_method + "\n}\n}\n"
        )
        lifetime = application.split("        // Application screen lifetime:", 1)[1].split("        public DifficultyIndex SelectedOfflineDifficulty()", 1)[0]
        lifetime = lifetime.split("        int priorScreenSleepTimeout;", 1)[1]
        application_caller.write_text(
            application_caller.read_text()
            + "\npublic sealed partial class PortSession { sealed partial class OfflineApplicationSession {\n"
            + "int priorScreenSleepTimeout;"
            + lifetime
            + "\n} public void KeepAwake() { if (applicationInput == null) applicationInput = new OfflineApplicationSession(this); applicationInput.KeepScreenAwake(); }"
            + " public void ReleaseScreen() { applicationInput?.Dispose(); } }\n"
        )
        cls.executable = directory / "feedback.exe"
        compiled = subprocess.run(
            [
                str(MONO),
                str(CSC),
                "-nologo",
                "-langversion:9",
                f"-out:{cls.executable}",
                str(RUNTIME / "AndroidFeedbackDraft.cs"),
                str(RUNTIME / "AndroidFeedbackScreen.cs"),
                str(RUNTIME / "OfflineSettingsBoundary.cs"),
                str(caller),
                str(application_caller),
                str(ROOT / "tests/fixtures/android_feedback_host.cs"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def run_case(self, name):
        result = subprocess.run([str(MONO), str(self.executable), name], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ": PASS", result.stdout)

    def test_model_requires_current_preview_consent_and_exact_shared_text(self):
        self.run_case("model-consent")

    def test_model_rejects_empty_text_and_bounds_public_build_facts(self):
        self.run_case("model-bounds")

    def test_screen_consent_edit_back_and_exact_copy_browser_text(self):
        self.run_case("screen-consent")

    def test_screen_refusals_do_not_claim_copy_or_browser_success(self):
        self.run_case("screen-errors")

    def test_escape_clears_notes_consent_and_focus(self):
        self.run_case("screen-escape")

    def test_settings_pause_input_isolation_and_cleanup(self):
        self.run_case("settings-lifecycle")

    def test_application_input_gives_settings_priority_over_hidden_start_menu(self):
        self.run_case("start-menu-input")

    def test_end_run_requires_explicit_confirmation_and_cancel_preserves_pause(self):
        self.run_case("end-run-confirmation")

    def test_screen_policy_spans_loading_and_restores_only_owned_state(self):
        self.run_case("screen-policy")


if __name__ == "__main__":
    unittest.main()
