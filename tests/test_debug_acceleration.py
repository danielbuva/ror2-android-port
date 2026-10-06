import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lab'))
from debug_acceleration import acceptance_labels, validate_options


class DebugAccelerationEvidenceTests(unittest.TestCase):
    def test_typo_and_truthy_strings_cannot_enable_silent_cheats(self):
        for value in [{'invincible': True}, {'invincibility': 'false'}, {'highDamage': 1}]:
            with self.assertRaises(RuntimeError):
                validate_options(value)
        with self.assertRaisesRegex(RuntimeError, 'purpose'):
            validate_options({'invincibility': True})

    def test_requested_acceleration_cannot_pass_on_an_older_apk(self):
        with self.assertRaisesRegex(RuntimeError, 'APK did not report'):
            acceptance_labels({}, {'highDamage': True, 'purpose': 'Moon integration'})
        old_report = {'debugAcceleration': {'version': 1, 'active': {}, 'events': [],
                      'everAssisted': False, 'normalGameAcceptanceEligible': True}}
        with self.assertRaisesRegex(RuntimeError, 'not observed'):
            acceptance_labels(old_report, {'jumpBoost': True, 'purpose': 'Moon objectives'})

    def test_jump_assistance_stays_excluded_after_disable(self):
        report = {'debugAcceleration': {'version': 1, 'active': {}, 'everAssisted': True,
                  'normalGameAcceptanceEligible': False, 'events': [
                      {'toggle': 'jumpBoost', 'enabled': True},
                      {'toggle': 'jumpBoost', 'enabled': False}]}}
        self.assertFalse(validate_options({})['jumpBoost'])
        self.assertEqual(acceptance_labels(report)['excluded_acceptance'],
                         ['full-normal-run', 'movement', 'navigation'])

    def test_disabling_all_controls_does_not_erase_assisted_history(self):
        report = {'debugAcceleration': {'version': 1, 'active': {}, 'everAssisted': True,
                  'normalGameAcceptanceEligible': False, 'events': [
                      {'toggle': 'fastCharge', 'enabled': True},
                      {'toggle': 'fastCharge', 'enabled': False}]}}
        labels = acceptance_labels(report)
        self.assertFalse(labels['normal_game_acceptance_eligible'])
        self.assertEqual(labels['run_kind'], 'debug-assisted')
        self.assertEqual(labels['excluded_acceptance'], ['full-normal-run', 'holdout'])

    def test_partial_application_and_false_normal_claim_fail_closed(self):
        report = {'debugAcceleration': {'version': 1, 'active': {}, 'everAssisted': True,
                  'normalGameAcceptanceEligible': False, 'events': [
                      {'toggle': 'invincibility', 'enabled': True}]}}
        with self.assertRaisesRegex(RuntimeError, 'not observed'):
            acceptance_labels(report, {'highDamage': True, 'purpose': 'Moon integration'})
        report['debugAcceleration']['normalGameAcceptanceEligible'] = True
        with self.assertRaisesRegex(RuntimeError, 'incorrectly claims'):
            acceptance_labels(report)

    def test_default_off_is_eligible_and_each_effect_lists_its_limit(self):
        report = {'debugAcceleration': {'version': 1, 'active': {}, 'events': [],
                  'everAssisted': False, 'normalGameAcceptanceEligible': True}}
        self.assertTrue(acceptance_labels(report)['normal_game_acceptance_eligible'])
        debug = report['debugAcceleration']
        debug.update(everAssisted=True, normalGameAcceptanceEligible=False,
                     events=[{'toggle': key, 'enabled': True} for key in
                             ['invincibility', 'highDamage', 'fastCharge', 'movementBoost', 'jumpBoost']])
        self.assertEqual(acceptance_labels(report)['excluded_acceptance'],
                         ['death', 'full-normal-run', 'holdout', 'movement', 'navigation', 'normal-combat'])
