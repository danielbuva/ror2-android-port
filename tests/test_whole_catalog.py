import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from whole_catalog import original_stage_contexts, analyze, catalog_roots, native_candidates, read_catalog, resolve_path, scene_guid_owners, runtime_key_roots, source_mesh_subobjects
import build
from common import sha, write


class WholePayloadReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.project = self.work/'lab-project'
        self.allowed = sorted(build.WHOLE_PLAYER_INPUTS)
        for name in self.allowed+['Assets/Content.prefab']:
            path = self.project/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        payload = self.work/'generated-android-data/content'
        payload.parent.mkdir()
        payload.write_text('content fixture')
        write(self.work/'whole-catalog-code-base.json', dict(allowed=self.allowed,
              files={'Assets/Content.prefab':sha(self.project/'Assets/Content.prefab')},
              payload={'content':sha(payload)}))
        self.patcher = patch.object(build, 'WORK', self.work)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_code_only_fix_cannot_reuse_changed_game_content(self):
        (self.project/'Assets/LabDiagnostics.cs').write_text('updated harness method')
        build.validate_whole_payload_reuse(self.project)
        (self.project/'Assets/Content.prefab').write_text('changed game content')
        with self.assertRaisesRegex(RuntimeError, 'Content inputs changed'):
            build.validate_whole_payload_reuse(self.project)

    def test_reuse_rejects_corrupted_or_added_payload(self):
        (self.work/'generated-android-data/content').write_text('corrupted')
        with self.assertRaisesRegex(RuntimeError, 'payload identity changed'):
            build.validate_whole_payload_reuse(self.project)


class WholeCatalogTests(unittest.TestCase):
    def test_mesh_subobjects_require_exact_guid_name_type_and_native_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'Assets').mkdir()
            (root/'Assets/skin.asset').write_text('%YAML\nmeshAddress:\n  m_AssetGUID: '+'a'*32+'\n  m_SubObjectName: VultureMesh\n  m_SubObjectType: UnityEngine.Mesh, UnityEngine.CoreModule\n'
                'otherMeshAddress:\n  m_AssetGUID: '+'b'*32+'\n  m_SubObjectName: VultureMesh\n  m_SubObjectType: UnityEngine.Mesh, UnityEngine.CoreModule\n')
            (root/'Assets/VultureMesh.asset').write_text('%YAML\n')
            metadata=dict(keys=[dict(key=g*32,keyType='System.String',locations=[i]) for i,g in enumerate('ab',1)],
                          locations=[dict(id=i,type='UnityEngine.Mesh, UnityEngine.CoreModule') for i in (1,2)])
            native=dict(issues=[dict(location=i,objects=[dict(name=name,type='Mesh',source='Assets/VultureMesh.asset',native_path_id=i)])
                                for i,name in ((1,'VultureMesh'),(2,'OtherMesh'))])
            resolved,unresolved=source_mesh_subobjects(root,dict(files=['Assets/skin.asset'],converted={}),metadata,native)
            self.assertEqual([row['key'] for row in resolved],['a'*32+'[VultureMesh]'])
            self.assertEqual(resolved[0]['native_path_id'],1)
            self.assertEqual([row['key'] for row in unresolved],['b'*32+'[VultureMesh]'])

    def test_runtime_keys_use_exact_original_identity_and_keep_consumers(self):
        data=dict(keys=[dict(key='baked-key',locations=[1]),dict(key='missing-conversion',locations=[2]),dict(key='bundle',locations=[3]),dict(key='typed',keyType='System.Type',locations=[1])],
                  locations=[dict(id=1,internalId='Assets/baked.asset',primaryKey='baked-key'),dict(id=2,internalId='Assets/missing.asset',primaryKey='missing-conversion'),dict(id=3,internalId='library:/bundle')])
        candidates=[dict(key=key,methods=['Original.Method']) for key in ['baked-key','missing-conversion','bundle','typed','Baked-key']]
        roots,edges=runtime_key_roots(data,candidates)
        self.assertEqual(roots,{1,2})
        self.assertEqual([row['key'] for row in edges],['baked-key','missing-conversion'])
        self.assertEqual(edges[0]['methods'],['Original.Method'])
        data['keys'].append(dict(key='stage-name',locations=[1,2]))
        self.assertEqual(runtime_key_roots(data,[dict(key='stage-name',methods=['Original.CompareStage'])]),(set(),[]))
        alias='Legacy/OriginalAsset';guid='b'*32
        data['keys'].append(dict(key=guid,locations=[2]))
        roots,edges=runtime_key_roots(data,[dict(key=alias,methods=['Original.LoadLegacy'])],{alias:guid})
        self.assertEqual(roots,{2})
        self.assertEqual(edges,[dict(key=guid,source_key=alias,locations=[2],methods=['Original.LoadLegacy'])])
        self.assertEqual(runtime_key_roots(data,[dict(key=alias,methods=['Original.LoadLegacy'])]),(set(),[]))

    def test_scene_collision_keeps_original_guid_target_and_both_addresses(self):
        guid='a'*32
        paths=['Assets/stage.unity','Assets/stageTest.unity']
        data=dict(keys=[dict(key=guid,locations=[1])],locations=[dict(id=i+1,internalId=p,type='UnityEngine.ResourceManagement.ResourceProviders.SceneInstance, Unity.ResourceManager') for i,p in enumerate(paths)])
        index, repairs=scene_guid_owners({guid:paths},data,'input')
        self.assertEqual(index[guid],paths[0])
        self.assertEqual(set(index.values()),set(paths))
        self.assertEqual(repairs[0]['source'],paths[1])
        self.assertEqual(scene_guid_owners({guid:paths},data,'input'),(index,repairs))
        data['keys'][0]['locations']=[1,2]
        with self.assertRaisesRegex(RuntimeError,'Ambiguous'):
            scene_guid_owners({guid:paths},data,'input')

    def test_non_scene_guid_collision_still_requires_attribution(self):
        data=dict(keys=[dict(key='a',locations=[1])],locations=[dict(id=1,internalId='Assets/body.prefab',type='UnityEngine.GameObject')])
        with self.assertRaisesRegex(RuntimeError,'Ambiguous'):
            scene_guid_owners({'a':['Assets/body.prefab','Assets/bodyOther.prefab']},data,'input')

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
            (root/'Assets/root.asset').write_text('%YAML\nm_AssetGUID: '+guid+'\nassetGUID: '+guid+'\n')
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

    def test_original_stage_policy_requires_unique_complete_source_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            scene=root/'Assets/RoR2/Base/Scenes/example/example.unity'
            scene.parent.mkdir(parents=True)
            record='--- !u!114 &1\n  monsterDccsPool: {fileID: 11400000, guid: '+('a'*32)+', type: 2}\n  interactableDccsPool: {fileID: 11400000, guid: '+('b'*32)+', type: 2}\n'
            for name,value in [('ignoreArtifactsThatRebuildCards',0),('contentSourceMixLimitOverride',1),('contentSourceMixLimitOverrideValue',3),('contentInteractableOnlySourceMixLimitOverride',0),('contentInteractableOnlySourceMixLimitOverrideValue',2),('sceneDirectorInteractibleCredits',220),('sceneDirectorMonsterCredits',100)]:
                record+='  '+name+': '+str(value)+'\n'
            record+='  bonusInteractibleCreditObjects: []\n--- !u!114 &2\n  usePlacedSpawnPoints: 0\n  expRewardCoefficient: 0.06666667\n  eliteBias: 2\n  spawnDistanceMultiplier: 6\n  monsterSpawnTargetOverride: {fileID: 0}\n'
            scene.write_text(record)
            result=original_stage_contexts(root,['example'],'accepted',{'a'*32:'Original/Monsters','b'*32:'Original/Interactables'})
            self.assertEqual(result['stages']['example']['director_fields']['spawnDistanceMultiplier'],6)
            self.assertEqual(result['stages']['example']['bonus_credits'],[])
            self.assertEqual(result['stages']['example']['monsterDccsPool'],'Original/Monsters')
            self.assertEqual(result['stages']['example']['fields']['contentSourceMixLimitOverrideValue'],3)
            self.assertIs(result['stages']['example']['fields']['contentSourceMixLimitOverride'],True)
            scene.write_text(record.replace('bonusInteractibleCreditObjects: []','bonusInteractibleCreditObjects:\n  - objectThatGrantsPointsIfEnabled: {fileID: 5}\n    points: 160')+'--- !u!1 &5\n  m_Name: Variant\n--- !u!4 &6\n  m_GameObject: {fileID: 5}\n  m_Father: {fileID: 8}\n--- !u!1 &7\n  m_Name: Environment\n--- !u!4 &8\n  m_GameObject: {fileID: 7}\n  m_Father: {fileID: 0}\n')
            result=original_stage_contexts(root,['example'],'accepted',{'a'*32:'Original/Monsters','b'*32:'Original/Interactables'})
            self.assertEqual(result['stages']['example']['bonus_credits'],[{'path':'Environment/Variant','points':160}])
            scene.write_text(scene.read_text().replace('points: 160','points: unknown'))
            with self.assertRaisesRegex(RuntimeError,'bonus credit entry'):
                original_stage_contexts(root,['example'],'accepted',{'a'*32:'Original/Monsters','b'*32:'Original/Interactables'})
            scene.write_text(record+record)
            with self.assertRaisesRegex(RuntimeError,'ambiguous'):
                original_stage_contexts(root,['example'],'accepted',{'a'*32:'Original/Monsters','b'*32:'Original/Interactables'})
            scene.write_text(record.replace('  sceneDirectorMonsterCredits: 100\n',''))
            with self.assertRaisesRegex(RuntimeError,'policy missing'):
                original_stage_contexts(root,['example'],'accepted',{'a'*32:'Original/Monsters','b'*32:'Original/Interactables'})

    def test_state_preload_strings_extend_runtime_closure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'Assets').mkdir()
            guid = 'a'*32
            (root/'Assets/root.asset').write_text('%YAML\n  preloadGUIDReferences:\n  - '+guid+'\n  - \n')
            (root/'Assets/preloaded.prefab').write_text('%YAML\n  m_Name: preloaded\n')
            categories = ['category'+str(i) for i in range(29)]
            helper = '\n'.join('FindLocationsThenAddLoadOperation(AddressablesLabels.'+name+')' for name in categories)
            data = dict(keys=[dict(key='ContentPack:base', locations=[1]),
                              dict(key=categories[0], locations=[1]), dict(key=guid, locations=[2])],
                        providers=[dict(identifier='base')],
                        labels=[dict(name=name, key=name) for name in categories],
                        locations=[dict(id=1, internalId='Assets/root.asset', dependencies=[], type='Example.Config, Example'),
                                   dict(id=2, internalId='Assets/preloaded.prefab', dependencies=[], type='UnityEngine.GameObject, Example')])
            source = root/'catalog.json'
            source.write_text(json.dumps(data))
            result = analyze(source, root, {'b'*32:'Assets/root.asset', 'c'*32:'Assets/preloaded.prefab'}, helper)
            self.assertEqual(result['files'], ['Assets/preloaded.prefab', 'Assets/root.asset'])
            self.assertEqual(result['runtime_roots'], [2])
            self.assertEqual(result['runtime_key_edges'][0]['field'], 'preloadGUIDReferences')
            self.assertEqual(result['summary']['issues']['invalid-preload-key'], 1)
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
