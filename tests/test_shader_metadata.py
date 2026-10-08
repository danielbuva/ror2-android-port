import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lab'))
import shader_materials


class ShaderMetadataTests(unittest.TestCase):
    def test_restores_tags_without_changing_placeholder_body(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            path = work / 'lab-project' / 'Fixture.shader'
            path.parent.mkdir()
            evidence = work / 'evidence'
            evidence.mkdir()
            original = 'Shader "Fixture" {\nSubShader {\nTags {"Queue"="Geometry"}\nPass { /* fixture program */ }\n}\n}\n'
            path.write_text(original)
            tree = {'m_ParsedForm': {'m_Name': 'Fixture', 'm_SubShaders': [
                {'m_Tags': {'tags': [('QUEUE', 'AlphaTest')]}}]}}
            with patch.object(shader_materials, 'WORK', work):
                receipt = shader_materials.align_exported_subshader_tags(path, tree, evidence)
            self.assertIn('"QUEUE"="AlphaTest"', path.read_text())
            self.assertEqual(original.split('Pass {')[1], path.read_text().split('Pass {')[1])
            self.assertEqual(original, next(evidence.glob('prior-tags-*.shader')).read_text())
            self.assertNotEqual(receipt['before_sha256'], receipt['after_sha256'])

    def test_refuses_file_outside_owned_project(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = work / 'original.shader'
            source.write_text('original input')
            with patch.object(shader_materials, 'WORK', work):
                with self.assertRaisesRegex(RuntimeError, 'owned ignored copies'):
                    shader_materials.align_exported_subshader_tags(source, {}, work / 'evidence')
            self.assertEqual(source.read_text(), 'original input')
