import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from serialization_rebase import RebaseConflict, local_ids, rebase_yaml
from composition_migration import scene_contract


def fixture(component='11', enabled='1', extra=''):
    return ('%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Component:\n'
            '  - component: {fileID: '+component+'}\n  m_Name: Owner\n'
            '--- !u!114 &'+component+'\nMonoBehaviour:\n  m_GameObject: {fileID: 1}\n'
            '  m_Script: {fileID: 99, guid: '+'a'*32+', type: 3}\n'
            '  m_Enabled: '+enabled+'\n'+extra)


class SerializationRebaseTests(unittest.TestCase):
    def test_moved_component_preserves_new_source_fields_and_android_disable(self):
        result, receipt = rebase_yaml(fixture(), fixture(enabled='0'),
                                     fixture('42', extra='  newSourceValue: 7\n'))
        self.assertIn('--- !u!114 &42', result)
        self.assertIn('component: {fileID: 42}', result)
        self.assertIn('m_Enabled: 0', result)
        self.assertIn('newSourceValue: 7', result)
        self.assertEqual(receipt['remapped'], 1)

    def test_external_local_ids_are_not_retargeted(self):
        result = local_ids('local: {fileID: 11}\nexternal: {fileID: 11, guid: '+'a'*32+'}\n', {'11':'42'})
        self.assertIn('local: {fileID: 42}', result)
        self.assertIn('external: {fileID: 11, guid:', result)

    def test_changed_duplicate_component_is_ambiguous(self):
        current = fixture('42')+'--- !u!114'+fixture('43').split('--- !u!114',1)[1]
        with self.assertRaisesRegex(RebaseConflict, 'ambiguous'):
            rebase_yaml(fixture(), fixture(enabled='0'), current)

    def test_overlapping_field_changes_are_not_silently_accepted(self):
        with self.assertRaises(RebaseConflict):
            rebase_yaml(fixture(extra='  value: 1\n'), fixture(extra='  value: 2\n'),
                        fixture('42', extra='  value: 3\n'))

    def test_updated_source_removal_does_not_resurrect_old_component(self):
        current = '%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Component: []\n  m_Name: Owner\n'
        result, receipt = rebase_yaml(fixture(), fixture(enabled='0'), current)
        self.assertEqual(result, current)
        self.assertEqual(receipt['source_removed'], 1)

    def test_owned_removal_clears_new_local_references(self):
        android = '%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Component: []\n  m_Name: Owner\n'
        current = fixture('42').replace('  m_Name: Owner', '  optional: {fileID: 42}\n  m_Name: Owner')
        result, _ = rebase_yaml(fixture(), android, current)
        self.assertNotIn('--- !u!114', result)
        self.assertIn('optional: {fileID: 0}', result)

    def test_scene_update_measures_previews_and_retains_only_zone_network_context(self):
        source = fixture().replace('fileID: 99, guid:', 'fileID: 866789372, guid:')
        source = source.replace('  m_Name: Owner', '  m_Name: Owner\n  m_IsActive: 1')
        source += ('--- !u!4 &12\nTransform:\n  m_GameObject: {fileID: 1}\n  m_Father: {fileID: 0}\n'
                   '--- !u!114 &13\nMonoBehaviour:\n  m_GameObject: {fileID: 1}\n'
                   '  m_Script: {fileID: 372142912, guid: '+'b'*32+', type: 3}\n')
        source = source.replace('  - component: {fileID: 11}', '  - component: {fileID: 11}\n  - component: {fileID: 13}')
        staged, counts, removed = scene_contract(source, source)
        self.assertEqual(counts['previewCallbacks'], 1)
        self.assertEqual(counts['previewNames'], ['Owner'])
        self.assertEqual(removed, ['13'])
        self.assertNotIn('component: {fileID: 13}', staged)
        self.assertNotIn('--- !u!114 &13', staged)
        with self.assertRaisesRegex(RuntimeError, 'Unreviewed'):
            scene_contract(source.replace('866789372', '99'), source.replace('866789372', '99'))


if __name__ == '__main__':
    unittest.main()
