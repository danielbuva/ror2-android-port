"""Run the actual touch HUD and input adapter against a synthetic Unity peer."""

import unittest

from layout_csharp import ROOT, run_csharp


class TouchLayoutHudTests(unittest.TestCase):
    def test_opt_in_edit_save_reset_cold_capture_and_corrupt_fallback(self):
        result = run_csharp(
            (ROOT / "tests/fixtures/TouchLayoutHudHost.cs").read_text(),
            [
                "../input/TouchLayoutHudBoundary.cs",
                "../input/AndroidTouchInput.cs",
                "TouchLayoutSession.cs",
                "TouchEditorGesture.cs",
                "TouchLayoutDocument.cs",
                "LayoutPreferenceStore.cs",
                "HudLayoutModel.cs",
                "LayoutProjection.cs",
            ],
        )
        self.assertIn("touch-hud: PASS", result)
