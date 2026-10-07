"""Authored fixtures check shader resource binding failures, without game code."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from shader_source import bind_hlsl
from shader_segments import parameter_layout,selected_layout


class ShaderBindingTests(unittest.TestCase):
    def layout(self,variables,textures=()):
        return {'buffers':[{'slot':0,'variables':variables}], 'textures':textures}

    def variable(self,name,columns=4,matrix=False):
        return {'name':name,'columns':columns,'rows':4 if matrix else 1,'matrix':matrix,'array_size':0,'type':0,'offset':0}

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
        body='Texture2D<float4> t3 : register(t3);\nSamplerState s4 : register(s4);\nvoid main(float4 v0 : TEXCOORD0, out precise float4 o0 : SV_Target0)\n{ o0 = t3.Sample(s4, v0.xy); }'
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

    def test_integer_register_lanes_preserve_bits(self):
        variable=self.variable('_FixtureInteger',columns=1);variable['type']=1
        body='void main(out precise float4 o0 : SV_Target0)\n{ o0.x = float(asint(cb0[0].x)); }'
        bound,_,declarations,_,reads=bind_hlsl(body,self.layout([variable]),'mapped')
        self.assertEqual(reads[0]['lanes'][0],'asfloat(_FixtureInteger)')
        self.assertEqual(declarations['_FixtureInteger'],'int')
        self.assertIn('float(asint(',bound)

    def test_fixed_builtin_matrix_array_uses_native_element(self):
        variable=self.variable('unity_FixtureMatrices',matrix=True);variable['array_size']=2
        body='void main(out precise float4 o0 : SV_Target0)\n{ o0 = cb0[5]; }'
        _,_,_,_,reads=bind_hlsl(body,self.layout([variable]),'mapped')
        self.assertEqual(reads[0]['lanes'][0],'transpose(unity_FixtureMatrices[1])[1].x')

    def test_texture_dimension_disagreement_is_rejected(self):
        body='TextureCube<float4> t0 : register(t0);\nSamplerState s0 : register(s0);\nvoid main(float4 v0 : TEXCOORD0, out precise float4 o0 : SV_Target0)\n{ o0=t0.Sample(s0,v0.xyz); }'
        with self.assertRaisesRegex(RuntimeError,'dimension disagreement'):
            bind_hlsl(body,self.layout([],[{'slot':0,'sampler':0,'name':'_FixtureTexture','dimension':2}]),'mapped')

    def test_unnamed_passes_require_ordinal_identity(self):
        p={'m_State':{'m_Name':''},'m_NameIndices':[],'progFragment':{'m_CommonParameters':{'m_ConstantBufferBindings':[],'m_ConstantBuffers':[],'m_TextureParams':[]}}}
        tree={'m_ParsedForm':{'m_SubShaders':[{'m_Passes':[p,p]}]}}
        record={'parameter_index':0,'stage':'progFragment','pass':''}
        raw=struct.pack('<Iiii',1,16,12,0)+struct.pack('<iii',202012090,0,0)
        with self.assertRaisesRegex(RuntimeError,'ambiguous'):
            selected_layout(tree,raw,record)
        record.update(subshader_index=0,pass_index=1)
        self.assertEqual(selected_layout(tree,raw,record)['buffers'],[])

    def test_cube_comparison_uses_exact_editor_platform_lowering(self):
        body='TextureCube<float4> t0 : register(t0);\nSamplerComparisonState s0_s : register(s0);\nvoid main(float4 v0 : TEXCOORD0, out float4 o0 : SV_Target0)\n{ o0.x=t0.SampleCmpLevelZero(s0_s,v0.xyz,v0.w).x; }'
        texture={'slot':0,'sampler':0,'name':'_FixtureShadow','dimension':4}
        bound,*_=bind_hlsl(body,self.layout([],[texture]),'mapped')
        self.assertIn('AndroidNativeCubeShadow(_FixtureShadow,sampler_FixtureShadow,v0.xyz,v0.w).x',bound)
        self.assertIn('SHADER_API_VULKAN',bound)
        self.assertIn('tex.SampleCmpLevelZero(samp,coord,depth)',bound)
