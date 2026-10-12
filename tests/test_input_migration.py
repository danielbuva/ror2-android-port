import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from input_migration import compare_surfaces, guard_comparison


class InputMigrationTests(unittest.TestCase):
    def fixture(self):
        return [dict(file='RoR2.dll', sha256='old', surface=dict(name='Game, Version=1', references=[],
                types=[dict(name='Body', contract='type', fieldOrder=['health'],
                            fields=[dict(name='health', type='Single', contract='public')],
                            methods=[dict(name='Void Body::Tick()', contract='public', body='IL')])]))]

    def test_same_version_does_not_hide_removed_field_and_changed_gameplay(self):
        old = self.fixture()
        new = copy.deepcopy(old)
        new[0]['sha256'] = 'new'
        t = new[0]['surface']['types'][0]
        t['fields'] = []
        t['fieldOrder'] = []
        t['methods'][0]['body'] = 'new IL'
        result = compare_surfaces(old, new)['assemblies'][0]
        self.assertTrue(result['same_identity'])
        self.assertFalse(result['same_bytes'])
        self.assertEqual(result['removed_fields'], ['Body::health'])
        self.assertEqual(result['changed_method_bodies'], ['Void Body::Tick()'])

    def test_guard_is_not_reusable_when_signature_or_body_is_missing(self):
        old = self.fixture()
        new = copy.deepcopy(old)
        new[0]['surface']['types'][0]['methods'] = []
        rows = guard_comparison(old, new, dict(methods=['Void Body::Tick()']))
        self.assertFalse(rows[0]['new_exists'])
        self.assertFalse(rows[0]['same_contract'])
        self.assertFalse(rows[0]['same_body'])

    def test_added_assembly_and_removed_type_stay_explicit(self):
        old = self.fixture()
        new = copy.deepcopy(old)
        new[0]['surface']['types'] = []
        new.append(dict(file='NewServices.dll'))
        result = compare_surfaces(old, new)
        self.assertEqual(result['added_assemblies'], ['NewServices.dll'])
        self.assertEqual(result['assemblies'][0]['removed_types'], ['Body'])
