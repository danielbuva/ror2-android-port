import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/lab'))
import baseline


def report(**overrides):
    value = {'error': '', 'firstFailure': '', 'world': {'seconds': 35.2}, 'stage': {'scene': 'lakes'},
             'debugAcceleration': {'everAssisted': True}, 'profile': {'appliedRuns': 13}}
    value.update(overrides)
    return value


class BaselineAssessmentTests(unittest.TestCase):
    def test_passing_run(self):
        self.assertEqual(baseline.assess('world-35s', report(), report()), [])

    def test_each_criterion_fails_alone(self):
        cases = {
            'stopped: first-failure': ('first-failure', report(), report()),
            'report error': ('world-35s', report(), report(firstFailure='MissingMethodException')),
            'world play under': ('world-35s', report(), report(world={'seconds': 20})),
            'not on Lakes': ('world-35s', report(), report(stage={'scene': 'foggyswamp'})),
            'run not marked assisted': ('world-35s', report(), report(debugAcceleration={})),
            'profile run count': ('world-35s', report(), report(profile={'appliedRuns': 14})),
        }
        for expected, args in cases.items():
            with self.subTest(expected=expected):
                failures = baseline.assess(*args)
                self.assertEqual(len(failures), 1, failures)
                self.assertTrue(failures[0].startswith(expected), failures)

    def test_missing_report_fails(self):
        self.assertIn('no final report', baseline.assess('process-exited', None, None))

    def test_selection_is_assisted_ordinary_commando(self):
        value = baseline.selection('attempt-x')
        self.assertEqual((value['attempt'], value['selectedSurvivor'], value['developerSurvivorOverride']),
                         ('attempt-x', 'Commando', False))
        enabled = [key for key in baseline.DEBUG_OPTIONS if value['debugOptions'][key]]
        self.assertEqual(enabled, ['invincibility'])
        self.assertFalse(value['goldshoresRoute'])


if __name__ == '__main__':
    unittest.main()
