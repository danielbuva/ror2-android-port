import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from whole_catalog import analyze, catalog_roots, native_candidates, read_catalog, resolve_path


class WholeCatalogTests(unittest.TestCase):
    def test_unverified_content_is_still_a_root(self):
        data = dict(keys=[dict(key='ContentPack:base', locations=[1, 2]),
                          dict(key='Items', locations=[1, 2, 3])],
                    providers=[dict(identifier='base')], labels=[dict(name='items', key='Items')])
        packs, roots = catalog_roots(data, ['items'])
        self.assertEqual(roots, {1, 2})
        self.assertEqual(packs[0]['categories']['items'], [1, 2])

    def test_missing_provider_label_fails_instead_of_empty_success(self):
        data = dict(keys=[], providers=[dict(identifier='base')], labels=[])
        with self.assertRaisesRegex(RuntimeError, 'provider label absent'):
            catalog_roots(data, [])

    def test_unresolved_imported_model_is_not_guessed(self):
        self.assertEqual(resolve_path('Assets/Model.fbx', {'Assets/Model.asset', 'Assets/Model.prefab'}),
                         (None, 'unresolved-conversion'))

    def test_case_collision_is_not_silently_selected(self):
        self.assertEqual(resolve_path('Assets/NAME.asset', {'Assets/Name.asset', 'Assets/name.asset'}),
                         (None, 'unresolved-conversion'))
        self.assertEqual(resolve_path('Assets/NAME.asset', {'Assets/Name.asset'}),
                         ('Assets/Name.asset', 'exported-filename-case'))

    def test_native_object_mapping_requires_type_name_and_owner(self):
        record = dict(address='Assets/Actors/model.fbx', type='Mesh', name='Body', path_id=123, serialized_file='source-file')
        exports = {('Assets/Actors', 'Mesh', 'Body'): ['Assets/Actors/Body.asset'],
                   ('Assets/Actors', 'GameObject', 'Body'): ['Assets/Actors/Body.prefab']}
        objects, issues = native_candidates([record], exports)
        self.assertEqual(objects[0]['source'], 'Assets/Actors/Body.asset')
        self.assertEqual(objects[0]['native_path_id'], 123)
        self.assertFalse(issues)
        exports[('Assets/Actors', 'Mesh', 'Body')].append('Assets/Actors/Body_0.asset')
        objects, issues = native_candidates([record], exports)
        self.assertFalse(objects)
        self.assertEqual(issues[0]['category'], 'ambiguous-exported-object')

    def test_compact_graph_retains_all_dependencies_without_duplicate_arrays(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'catalog.json'
            path.write_text(json.dumps(dict(schemaVersion=2, dependencySets=[[4, 5]],
                                            locations=[dict(id=i, dependencySet=0) for i in [1, 2]])))
            data = read_catalog(path)
            self.assertEqual(data['locations'][0]['dependencies'], [4, 5])
            self.assertIs(data['locations'][0]['dependencies'], data['locations'][1]['dependencies'])

    def test_runtime_reference_edges_expand_beyond_provider_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            guid = 'a'*32
            (root/'Assets').mkdir()
            (root/'Assets/root.asset').write_text('%YAML\nm_AssetGUID: '+guid+'\n')
            (root/'Assets/dependency.asset').write_text('%YAML\nm_Name: dependency\n')
            categories = ['category'+str(i) for i in range(29)]
            helper = '\n'.join('FindLocationsThenAddLoadOperation(AddressablesLabels.'+name+')' for name in categories)
            data = dict(keys=[dict(key='ContentPack:base', locations=[1]),
                              dict(key=categories[0], locations=[1]), dict(key=guid, locations=[2])],
                        providers=[dict(identifier='base')],
                        labels=[dict(name=name, key=name) for name in categories],
                        locations=[dict(id=i, internalId='Assets/'+name+'.asset', dependencies=[], type='Example.Asset, Example')
                                   for i, name in [(1, 'root'), (2, 'dependency')]])
            source = root/'catalog.json'
            source.write_text(json.dumps(data))
            result = analyze(source, root, {'b'*32: 'Assets/root.asset', 'c'*32: 'Assets/dependency.asset'}, helper)
            self.assertEqual(result['files'], ['Assets/dependency.asset', 'Assets/root.asset'])
            self.assertEqual(result['summary']['catalog_roots'], 1)
            self.assertEqual(result['summary']['soft_reference_edges'], 1)
            self.assertEqual(result['summary']['quarantine'], [])

    def test_broken_original_dependency_graph_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = ['category'+str(i) for i in range(29)]
            data = dict(keys=[dict(key='ContentPack:base', locations=[1])],
                        providers=[dict(identifier='base')], labels=[dict(name=n, key=n) for n in names],
                        locations=[dict(id=1, internalId='Assets/root.asset', dependencies=[99])])
            source = root/'catalog.json'
            source.write_text(json.dumps(data))
            helper = '\n'.join('FindLocationsThenAddLoadOperation(AddressablesLabels.'+n+')' for n in names)
            with self.assertRaisesRegex(RuntimeError, 'Broken original catalog dependency'):
                analyze(source, root, {}, helper)
