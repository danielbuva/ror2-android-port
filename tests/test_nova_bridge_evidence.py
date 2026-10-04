import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from nova_bridge import current_errors,insert_axes

class NovaEvidenceTests(unittest.TestCase):
    def test_axis_entries_precede_next_top_level_property(self):
        before='InputManager:\n  m_Axes:\n  - m_Name: Original\n  m_UsePhysicalKeys: 0\n'
        self.assertEqual(insert_axes(before,'  - m_Name: Probe\n'),'InputManager:\n  m_Axes:\n  - m_Name: Original\n  - m_Name: Probe\n  m_UsePhysicalKeys: 0\n')
    def test_changed_settings_shape_requires_review(self):
        with self.assertRaisesRegex(RuntimeError,'terminal property changed'):insert_axes('InputManager: {}','unused')
    def test_current_exception_cannot_hide_behind_successful_report(self):
        log='10-03 12:00:00.000 42 53 E Unity : NullReferenceException: original jump\n'
        self.assertEqual(current_errors(log,'42'),[log.strip()])
    def test_historical_other_process_error_is_not_current_failure(self):
        self.assertEqual(current_errors('10-03 12:00:00.000 142 53 E Unity : old failure\n','42'),[])
    def test_only_bracketed_known_windows_rejection_is_allowed(self):
        prefix='10-03 12:00:00.000 42 53 E Unity : '
        archive="Unknown error occurred while loading 'archive:/fixture'."
        known="\n".join(prefix+x for x in ["File's Build target is: 19",archive,"The AssetBundle 'windows-shaders.bundle' can't be loaded because of build target."])
        self.assertEqual(current_errors(known,'42'),[])
        self.assertEqual(current_errors(prefix+archive,'42'),[prefix+archive])
