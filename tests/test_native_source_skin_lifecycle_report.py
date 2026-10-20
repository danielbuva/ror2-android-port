from __future__ import annotations

import json
import os
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
DRAFT = os.environ.get("NATIVE_SKIN_SOURCE_ROOT")
if DRAFT:
    ROOT = Path(DRAFT)

    def source(path: str) -> str:
        return (ROOT / "source" / path).read_text()

    manifest_path = ROOT / "source/runtime-sources.json"
    architecture = (ROOT / "source/ARCHITECTURE.md").read_text()
else:
    ROOT = REPO

    def source(path: str) -> str:
        return (ROOT / "tools/unity/runtime" / path).read_text()

    manifest_path = ROOT / "recipe/runtime-sources.json"
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text()


class NativeSourceSkinLifecycleReportTests(unittest.TestCase):
    def test_selector_is_per_run_report_and_default_off(self) -> None:
        session = source("session/PortSession.cs")
        config = session.split("public sealed class SessionConfig", 1)[1].split("public class SessionReport", 1)[0]
        report = session.split("public class SessionReport", 1)[1]
        self.assertNotIn("nativeSourceSkinLifecycleDiagnosticRequested", config)
        self.assertIn("public bool nativeSourceSkinLifecycleDiagnosticRequested;", report)
        self.assertIn("if (r.nativeSourceSkinLifecycleDiagnosticRequested", session)
        self.assertIn('r.phase = "native-source-skin-lifecycle-refused";', session)

    def test_request_flows_to_nova_owned_report_and_native_owner(self) -> None:
        nova = source("input/NovaInputBoundary.cs")
        display = source("input/NovaDiagnosticDisplay.cs")
        self.assertIn("AndroidNativeSourceSkinLifecycle.Report nativeSourceSkinLifecycle;", nova)
        self.assertIn("coordinator.r.nativeSourceSkinLifecycleDiagnosticRequested", nova)
        self.assertIn("nativeSourceSkinRequested, body, coordinator.r.nova.nativeSourceSkinLifecycle", nova)
        self.assertIn("PrepareInactive(model.gameObject, selectedBody, sourceSkinReport)", display)
        self.assertIn("RecordDisplayDeactivated()", display)
        self.assertNotIn("Destroy(nativeSourceSkinLifecycle)", display)

    def test_report_is_scalar_and_actual_event_or_snapshot_driven(self) -> None:
        owner = (ROOT / "AndroidNativeSourceSkinLifecycle.cs").read_text() if DRAFT else source("input/AndroidNativeSourceSkinLifecycle.cs")
        for field in (
            "requested, attached, nativeOwnersActive, selectedSkinReady, animatorInitialized",
            "selectedSkinIndex = -1, currentSkinIndex = -1",
            "controllerIdentity, avatarIdentity, firstFailure",
            "materialCopiesCreated, materialCopiesRetired, materialCopiesReleased",
        ):
            self.assertIn(field, owner)
        self.assertIn("skinController.onSkinApplied += OnSkinApplied", owner)
        self.assertIn("report.materialCopiesCreated++", owner)
        self.assertIn("report.materialCopiesRetired++", owner)
        self.assertIn("report.materialCopiesReleased++", owner)
        self.assertIn("report.ownerDestroyed = true", owner)
        self.assertIn("public void CaptureNativeState()", owner)
        self.assertIn("if (retired.Count != 0)", owner)

    def test_new_runtime_owners_and_architecture_layout_are_listed(self) -> None:
        names = json.loads(manifest_path.read_text())
        self.assertEqual(names, sorted(names))
        self.assertIn("runtime/input/AndroidNativeSourceSkinLifecycle.cs", names)
        self.assertIn("runtime/input/AndroidNativeSkinActivationPolicy.cs", names)
        row = next(line for line in architecture.splitlines() if "| Input and camera |" in line)
        self.assertIn("AndroidNativeSourceSkinLifecycle", row)
        self.assertIn("per-run `SessionReport` selector defaults false", row)


if __name__ == "__main__":
    unittest.main()
