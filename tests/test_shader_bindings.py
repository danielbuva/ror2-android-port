"""Authored fixtures check shader resource binding failures, without game code."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from shader_source import bind_hlsl
from shader_segments import parameter_layout


class ShaderBindingTests(unittest.TestCase):
    def layout(self,variables,textures=()):
        return {'buffers':[{'slot':0,'variables':variables}], 'textures':textures}

    def variable(self,name,columns=4,matrix=False):
        return {'name':name,'columns':columns,'matrix':matrix,'array_size':0,'type':0,'offset':0}

    def test_matrix_binding_uses_native_columns(self):
        body='void main(float4 v0 : POSITION0, out precise float4 o0 : SV_POSITION0)\n{ o0 = cb0[2] * v0.zzzz; }'
        bound,_,_,_,reads=bind_hlsl(body,self.layout([self.variable('unity_TestMatrix',matrix=True)]),'mapped')
        self.assertEqual(reads[0]['lanes'],['transpose(unity_TestMatrix)[2].'+c for c in 'xyzw'])
        self.assertIn('* v0.zzzz;',bound)

    def test_rejects_unclassified_consumed_lane(self):
        body='void main(out precise float4 o0 : SV_Target0)\n{ o0 = cb0[0]; }'
        with self.assertRaisesRegex(RuntimeError,'no measured binding'):
            bind_hlsl(body,self.layout([self.variable('_Fixture',columns=3)]),'mapped')

    def test_unused_padding_is_not_invented_input(self):
        body='void main(out precise float4 o0 : SV_Target0)\n{ o0.xyz = cb0[0].xyz; }'
        bound,_,_,_,reads=bind_hlsl(body,self.layout([self.variable('_Fixture',columns=3)]),'mapped')
        self.assertEqual(reads[0]['lanes'][-1],'0.0')
        self.assertIn('o0=float4(0,0,0,0);',bound)

    def test_texture_and_independent_sampler_indices(self):
        body='void main(float4 v0 : TEXCOORD0, out precise float4 o0 : SV_Target0)\n{ o0 = t3.Sample(s4, v0.xy); }'
        textures=[{'name':'_FixtureTexture','slot':3,'sampler':4,'dimension':2}]
        bound,*_=bind_hlsl(body,self.layout([],textures),'mapped')
        self.assertIn('_FixtureTexture.Sample(sampler_FixtureTexture, v0.xy)',bound)

    def test_rejects_dynamic_unmeasured_constant_access(self):
        body='void main(float4 v0 : TEXCOORD0, out precise float4 o0 : SV_Target0)\n{ o0 = cb0[int(v0.x)]; }'
        with self.assertRaisesRegex(RuntimeError,'dynamic native constant'):
            bind_hlsl(body,self.layout([]),'mapped')

    def test_parameter_records_reject_unknown_structures(self):
        name=b'Fixture';aligned=struct.pack('<i',len(name))+name+b'\0'
        record=struct.pack('<ii',202012090,1)+aligned+struct.pack('<iii',16,0,1)
        with self.assertRaisesRegex(RuntimeError,'Structured shader constants'):
            parameter_layout(record)

    def test_parameter_records_do_not_ignore_trailing_bytes(self):
        record=struct.pack('<iii',202012090,0,0)+b'extra'
        with self.assertRaisesRegex(RuntimeError,'trailing shader parameter'):
            parameter_layout(record)
