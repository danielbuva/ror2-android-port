"""Interruption evidence must distinguish an uncommitted store from a completed save."""

import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import settings_write_interrupt_check as check  # noqa: E402


class InterruptedWriteEvidenceTests(unittest.TestCase):
    witness = dict(success=True, createObserved=True, pendingPresentAfterStop=True)

    def test_a_completed_save_is_not_interruption_evidence(self):
        with self.assertRaisesRegex(RuntimeError, "Missed pre-commit"):
            check.interrupted_transaction("old valid JSON", "new valid JSON", dict(state="absent"), self.witness)

    def test_unchanged_primary_without_a_retained_pending_file_is_not_enough(self):
        with self.assertRaisesRegex(RuntimeError, "Missed pre-commit"):
            check.interrupted_transaction("old valid JSON", "old valid JSON", dict(state="absent"), self.witness)

    def test_real_old_primary_and_partial_pending_can_satisfy_the_observed_contract(self):
        with tempfile.TemporaryDirectory() as root:
            primary = Path(root) / "preferences.json"
            pending = Path(root) / "preferences.json.pending"
            primary.write_text('{"version":1,"invertY":false}')
            before = primary.read_text()
            pending.write_text('{"version":')
            check.interrupted_transaction(before, primary.read_text(), dict(state="file"), self.witness)
            self.assertEqual(primary.read_text(), before)
            self.assertEqual(pending.read_text(), '{"version":')

    def test_synthetic_or_failed_observer_reports_cannot_qualify_real_interruption(self):
        for witness in (None, {}, dict(self.witness, success=False), dict(self.witness, createObserved=1), dict(self.witness, pendingPresentAfterStop=False)):
            with self.subTest(witness=witness), self.assertRaisesRegex(RuntimeError, "No successful native"):
                check.interrupted_transaction("old", "old", dict(state="file"), witness)

    def test_missing_artifact_identity_refuses_before_device_access(self):
        with patch.object(check, "Device", side_effect=AssertionError("unexpected device access")):
            with self.assertRaisesRegex(ValueError, "requires --expected-apk-sha256"):
                check.check_settings_write_interrupt()
