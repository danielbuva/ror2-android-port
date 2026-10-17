import contextlib
import io
import json
import runpy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lab'))
import build
import common
import project_manifest
from common import sha, write


class ProjectManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.work = self.root/'work'
        self.project = self.work/'lab-project'
        for area in project_manifest.AREAS:
            (self.project/area).mkdir(parents=True)
        self.contents = {
            'Assets/fixture.asset': 'synthetic file contents only',
            'Assets/fixture.asset.meta': 'synthetic metadata only',
            'Packages/manifest.json': '{"synthetic": true}',
            'ProjectSettings/FixtureSettings.asset': 'synthetic settings only',
        }
        for path, text in self.contents.items():
            (self.project/path).write_text(text)
        for module in (project_manifest, build):
            for name, value in (('ROOT', self.root), ('WORK', self.work)):
                patcher = patch.object(module, name, value)
                patcher.start()
                self.addCleanup(patcher.stop)

    def capture(self, **kwargs):
        return project_manifest.capture(self.project, **kwargs)

    def test_identical_trees_compare_equal_independent_of_location(self):
        other = self.root/'other-project'
        shutil.copytree(self.project, other)
        (self.project/'Library').mkdir()
        (self.project/'Library/ignored').write_text('not a build input')
        before, after = self.capture(), project_manifest.capture(other)
        self.assertEqual(before, after)
        self.assertEqual(project_manifest.compare(before, after), {
            'equal': True, 'areas': {}, 'summary': 'Project manifests match.'})

    def test_added_removed_and_changed_files_include_metadata_and_settings(self):
        before = self.capture()
        (self.project/'Assets/added.asset').write_text('added')
        (self.project/'Assets/added.asset.meta').write_text('added metadata')
        (self.project/'Assets/fixture.asset').unlink()
        (self.project/'Assets/fixture.asset.meta').write_text('changed metadata')
        (self.project/'Packages/manifest.json').unlink()
        (self.project/'ProjectSettings/FixtureSettings.asset').write_text('changed settings')
        result = project_manifest.compare(before, self.capture())
        self.assertFalse(result['equal'])
        self.assertEqual(result['areas'], {
            'Assets': {'added': ['Assets/added.asset', 'Assets/added.asset.meta'],
                       'removed': ['Assets/fixture.asset'], 'changed': ['Assets/fixture.asset.meta']},
            'Packages': {'added': [], 'removed': ['Packages/manifest.json'], 'changed': []},
            'ProjectSettings': {'added': [], 'removed': [], 'changed': ['ProjectSettings/FixtureSettings.asset']},
        })
        self.assertEqual(result['summary'], 'Project manifests differ: 2 added, 2 removed, 2 changed.')

    def test_same_size_content_change_is_reported(self):
        before = self.capture()
        path = self.project/'Assets/fixture.asset'
        path.write_text('x'*path.stat().st_size)
        result = project_manifest.compare(before, self.capture())
        self.assertEqual(result['areas']['Assets']['changed'], ['Assets/fixture.asset'])

    def test_each_file_kind_reports_addition_removal_and_change(self):
        baseline = self.capture()
        for name, text in self.contents.items():
            with self.subTest(path=name):
                path = self.project/name
                area = name.split('/')[0]
                path.unlink()
                missing = self.capture()
                self.assertEqual(project_manifest.compare(baseline, missing)['areas'][area]['removed'], [name])
                path.write_text(text)
                self.assertEqual(project_manifest.compare(missing, self.capture())['areas'][area]['added'], [name])
                path.write_text(text+' changed')
                self.assertEqual(project_manifest.compare(baseline, self.capture())['areas'][area]['changed'], [name])
                path.write_text(text)

    def test_tree_root_file_conflict_fails_closed(self):
        folder = self.project/'ProjectSettings'
        (folder/'FixtureSettings.asset').unlink()
        folder.rmdir()
        folder.write_text('synthetic file conflicts with input tree')
        with self.assertRaises(NotADirectoryError):
            self.capture()

    def test_manifest_contains_only_names_hashes_and_sizes(self):
        manifest = self.capture()
        encoded = json.dumps(manifest)
        self.assertEqual(set(manifest), {'version', 'files', 'external'})
        self.assertEqual(set(manifest['files']), set(self.contents))
        for path, text in self.contents.items():
            self.assertNotIn(text, encoded)
            self.assertEqual(manifest['files'][path], {
                'sha256': sha(self.project/path), 'size': len(text.encode())})
        self.assertNotIn(str(self.root), encoded)
        self.assertEqual(manifest['external'], {})

    def test_extra_inputs_are_project_local_files(self):
        path = self.project/'.fixture.json'
        path.write_text('extra synthetic input')
        manifest = self.capture(extra=['.fixture.json', path, 'Assets/fixture.asset'])
        self.assertEqual(len(manifest['files']), len(self.contents)+1)
        self.assertEqual(manifest['files']['.fixture.json']['sha256'], sha(path))
        with self.assertRaisesRegex(RuntimeError, 'must be a file'):
            self.capture(extra=['missing.json'])

    def test_extra_paths_cannot_escape_project(self):
        outside = self.work/'outside.txt'
        outside.write_text('must not be hashed')
        for path in (outside, '../outside.txt'):
            with self.subTest(path=path), patch.object(project_manifest, 'sha') as hash_file:
                with self.assertRaisesRegex(RuntimeError, 'outside project'):
                    self.capture(extra=[path])
                hash_file.assert_not_called()

    def test_file_and_directory_symlinks_cannot_escape_project(self):
        outside = self.root/'outside'
        outside.mkdir()
        (outside/'fixture').write_text('must not be hashed')
        for target in (outside/'fixture', outside):
            with self.subTest(target=target):
                link = self.project/'Assets/link'
                link.symlink_to(target, target_is_directory=target.is_dir())
                try:
                    with patch.object(project_manifest, 'sha') as hash_file:
                        with self.assertRaisesRegex(RuntimeError, 'outside project'):
                            self.capture()
                        hash_file.assert_not_called()
                finally:
                    link.unlink()

    def test_internal_directory_symlinks_are_refused_including_extra_paths(self):
        (self.project/'alias').symlink_to(self.project/'Assets', target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'symbolic links'):
            self.capture(extra=['alias/fixture.asset'])
        (self.project/'Assets/loop').symlink_to(self.project/'Assets', target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'symbolic links'):
            self.capture()

    def test_unreadable_tree_fails_instead_of_omitting_inputs(self):
        with patch.object(Path, 'iterdir', side_effect=PermissionError('synthetic unreadable tree')):
            with self.assertRaises(PermissionError):
                self.capture()

    def test_external_selection_matches_build_cache_payload(self):
        recipe = self.work/'scene-probe-build.json'
        manifest = self.work/'catalog-manifest.json'
        write(recipe, {'synthetic': 'bundle recipe'})
        write(manifest, {'synthetic': 'catalog manifest'})
        for location in (manifest, manifest.relative_to(self.root)):
            with self.subTest(location=location):
                write(self.work/'whole-catalog-build.json', {'manifest': str(location)})
                # Observe the cache's existing payload without modifying its result or source.
                with patch.object(build, 'digest', side_effect=lambda value: value), \
                        patch.object(build, 'toolchain', return_value={}), \
                        patch.object(build, 'sha', side_effect=lambda path: '0'*64 if Path(path).name == 'build.py' else sha(path)):
                    cache = build.build_cache_key(self.project, 'vulkan')
                captured = self.capture()
                self.assertEqual(captured['external'], cache['external'])
                self.assertEqual({path: record['sha256'] for path, record in captured['files'].items()}, cache['inputs'])
                self.assertEqual(captured['external'], {'bundle_recipe': sha(recipe), 'whole_catalog_manifest': sha(manifest)})

    def test_each_external_input_reports_drift_and_removal(self):
        for name, filename in (('bundle_recipe', 'scene-probe-build.json'),
                               ('whole_catalog_manifest', 'catalog-manifest.json')):
            with self.subTest(name=name):
                path = self.work/filename
                write(path, {'synthetic': 'before'})
                if name == 'whole_catalog_manifest':
                    write(self.work/'whole-catalog-build.json', {'manifest': str(path)})
                before = self.capture()
                write(path, {'synthetic': 'after'})
                self.assertEqual(project_manifest.compare(before, self.capture())['areas']['external']['changed'], ['external/'+name])
                (self.work/('whole-catalog-build.json' if name == 'whole_catalog_manifest' else filename)).unlink()
                self.assertEqual(project_manifest.compare(before, self.capture())['areas']['external']['removed'], ['external/'+name])

    def test_missing_whole_catalog_manifest_fails_closed(self):
        write(self.work/'whole-catalog-build.json', {'manifest': 'missing.json'})
        with self.assertRaisesRegex(RuntimeError, 'manifest is missing'):
            self.capture()

    def test_invalid_receipts_fail_closed(self):
        good = self.capture()
        invalid = [{}, dict(good, version=2), dict(good, files=[])]
        for path, record in (('../escape', {'sha256': '0'*64, 'size': 1}),
                             ('/absolute', {'sha256': '0'*64, 'size': 1}),
                             ('Assets/fixture', {'sha256': 'invalid', 'size': 1}),
                             ('Assets/fixture', {'sha256': '0'*64, 'size': -1}),
                             ('Assets/fixture', {'sha256': '0'*64, 'size': 1, 'contents': 'forbidden'})):
            invalid.append(dict(good, files={path: record}))
        for receipt in invalid:
            with self.subTest(receipt=receipt), self.assertRaises(RuntimeError):
                project_manifest.compare(receipt, good)

    def cli(self, *args):
        output = io.StringIO()
        with patch.object(common, 'WORK', self.work), patch.object(sys, 'argv', ['dev', 'prototype', *args]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            try:
                runpy.run_path(str(ROOT/'scripts/lab/main.py'), run_name='__main__')
            except SystemExit as result:
                return result.code, output.getvalue()
        return 0, output.getvalue()

    def test_cli_writes_receipt_and_compare_exit_status_tracks_drift(self):
        code, output = self.cli('--action', 'project-manifest-capture')
        self.assertEqual(code, 0)
        receipt = Path(output.strip())
        self.assertEqual(receipt.parent, self.work/'receipts/project-manifest')
        self.assertEqual(json.loads(receipt.read_text()), self.capture())
        code, output = self.cli('--action', 'project-manifest-compare', '--compare', str(receipt), str(receipt))
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)['equal'])
        (self.project/'Assets/fixture.asset').write_text('drift')
        other = self.work/'other-receipt.json'
        write(other, self.capture())
        code, output = self.cli('--action', 'project-manifest-compare', '--compare', str(receipt), str(other))
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output)['equal'])

    def test_cli_requires_both_receipt_paths_for_compare_action(self):
        for args in (('--action', 'project-manifest-compare'), ('--compare', 'a.json', 'b.json')):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args)[0], 2)


if __name__ == '__main__':
    unittest.main()
