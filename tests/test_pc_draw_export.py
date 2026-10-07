"""Authored replay fixtures; no PC capture or graphics execution is implied."""
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S

path=Path(__file__).resolve().parents[1]/'tools/shaders/export_pc_draw.py'
spec=importlib.util.spec_from_file_location('pc_draw_export',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class DrawExportTests(unittest.TestCase):
    def fixture(self,short=False):
        rd=S(GraphicsAPI=S(D3D11=1),ActionFlags=S(Drawcall=1),ShaderStage=S(Vertex=0,Hull=1,Domain=2,Geometry=3,Pixel=4))
        action=S(eventId=8,flags=1,numIndices=3,numInstances=1,indexOffset=2,vertexOffset=7,instanceOffset=0,children=[])
        dxbc=b'DXBC'+b'\0'*20+struct.pack('<II',32,0)
        reflection=S(rawBytes=dxbc,inputSignature=[],outputSignature=[],constantBlocks=[])
        used=S(descriptor=S(resource='authored-buffer',byteOffset=16,byteSize=4))
        reads=[]
        def buffer(resource,offset,length):
            reads.append((resource,offset,length));return b'\x00\x00' if short else b'\x01\x02\x03\x04'
        pipe=S(GetShaderReflection=lambda stage:reflection if stage==4 else None,
               GetConstantBlocks=lambda *args:[used],GetShader=lambda stage:'fixture-shader',
               GetShaderEntryPoint=lambda stage:'main',GetReadOnlyResources=lambda *args:[],GetSamplers=lambda *args:[])
        controller=S(GetAPIProperties=lambda:S(pipelineType=1),GetRootActions=lambda:[action],SetFrameEvent=lambda *args:None,
                     GetPipelineState=lambda:pipe,GetD3D11PipelineState=lambda:S(inputAssembly=S(),rasterizer=S(),outputMerger=S()),
                     GetTextures=lambda:[],GetBuffers=lambda:[],GetResources=lambda:[],GetBufferData=buffer)
        return controller,rd,reads

    def test_bound_constant_range_and_unknown_owner_are_preserved(self):
        c,rd,reads=self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            result=module.export(c,rd,8,Path(directory))
            self.assertEqual(reads,[('authored-buffer',16,4)])
            self.assertEqual((Path(directory)/'Pixel-cb-0.bin').read_bytes(),b'\x01\x02\x03\x04')
            self.assertEqual(result['owner_association'],'unavailable')
            self.assertEqual(result['stages'][0]['stage'],'Pixel')

    def test_truncated_buffer_and_unlinked_unity_sidecar_reject(self):
        c,rd,_=self.fixture(short=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'extent differs'):
                module.export(c,rd,8,Path(directory))
            with self.assertRaisesRegex(ValueError,'no evidence linking'):
                module.export(c,rd,8,Path(directory),{'event_id':9})

    def test_absent_or_non_draw_event_is_not_capture_success(self):
        with self.assertRaisesRegex(ValueError,'not a draw'):
            module.find_draw([S(eventId=8,flags=0,children=[])],8,1)
        c,rd,_=self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'absent'):
                module.export(c,rd,9,Path(directory))
