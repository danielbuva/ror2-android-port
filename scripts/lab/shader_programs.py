"""Resource/I-O emitter shared only by the measured native shader candidates."""
from common import *
from shader_segments import selected_layout
from shader_source import bind_hlsl
from shader_recovery import PINS
import shutil

def structure(name,semantics):
    return 'struct '+name+' {\n'+'\n'.join('float4 '+s+' : '+s+';' for s in sorted(semantics))+'\n};'


def call(index,params,inputs='i',outputs='o'):
    def argument(p):
        if p['semantic']=='SV_IsFrontFace0':return '(face?1u:0u)'
        result=(outputs if p['out'] else inputs)+'.'+p['semantic']
        return result+('.'+'xyzw'[:p['columns']] if p['columns']<4 else '')
    return 'native_'+str(index)+'('+','.join(argument(p) for p in params)+');'


class NativePrograms:
    def __init__(self,out,result,exe):
        self.out=out;self.result=result;self.exe=exe;self.cache={}
    def bound(self,context,index):
        tree,raw,records,programs,_=context;key=(tree['m_ParsedForm']['m_Name'],index)
        if key in self.cache:return self.cache[key]
        prefix=tree['m_ParsedForm']['m_Name'];stem='program-'+digest(prefix)[:12]+'-'+str(index);f=self.out/(stem+'.dxbc');f.write_bytes(programs[index]);hlsl=self.out/(stem+'.hlsl');asm=self.out/(stem+'.d3dasm');rebuilt=self.out/(stem+'.roundtrip.dxbc')
        run([self.exe,f,'--emit','hlsl','--output',hlsl]);run([self.exe,f,'--emit','d3dasm','--output',asm]);run([self.exe,asm,'--assemble','--output',rebuilt])
        if sha(f)!=sha(rebuilt):raise RuntimeError('Native roundtrip changed')
        origin='d3dasm'
        if 'not decompiled' in hlsl.read_text():
            fallback=self.out/(stem+'-independent');fallback.mkdir();tool=WORK/PINS['hlsl'][0]/'RenderDoc_DXBC2HLSL_shader_view_files/v2'
            for name in ['cmd_Decompiler.exe','d3dcompiler_46.dll']:shutil.copy2(tool/name,fallback/name)
            shutil.copy2(f,fallback/f.name);env=os.environ.copy();env['CX_BOTTLE_PATH']=str(WORK/'toolchains/crossover-bottles')
            wine=Path('/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine')
            p=run([wine,'--bottle','shader-recovery','--no-gui','--workdir',fallback,fallback/'cmd_Decompiler.exe','-D','-V',fallback/f.name],env=env,check=False,timeout=120)
            (fallback/'validation.stdout').write_bytes(p.stdout);(fallback/'validation.stderr').write_bytes(p.stderr)
            if p.returncode or b'Decompiler validation pass succeeded' not in p.stdout+p.stderr:raise RuntimeError('Independent shadow-program HLSL validation failed: '+stem)
            hlsl=fallback/(stem+'.hlsl');origin='HLSLDecompiler validated fallback; d3dasm sample-c instruction counterexample preserved'
        layout=selected_layout(tree,raw,records[index]);write(self.out/(stem+'-layout.json'),layout)
        function,params,declarations,_,reads=bind_hlsl(hlsl.read_text(),layout,'native_'+str(index))
        data=(function,params,declarations,layout['textures']);self.cache[key]=data
        self.result['programs'].append({'shader':prefix,'index':index,'dxbc_sha256':sha(f),'hlsl_sha256':sha(hlsl),'layout':layout,'constant_bindings':reads,'origin':origin,'native_roundtrip_identical':True,'keywords':records[index]['keywords']})
        return data
    def block(self,context,pairs,entry_directives=''):
        inputs=set();varyings={'SV_POSITION0'};targets=set();definitions=[];declarations={};textures={};entry=[]
        for condition,vi,fi in pairs:
            v=self.bound(context,vi);f=self.bound(context,fi)
            inputs.update(p['semantic'] for p in v[1] if not p['out']);varyings.update(p['semantic'] for p in v[1] if p['out']);targets.update(p['semantic'] for p in f[1] if p['out'])
            if any(p['semantic'] not in varyings and p['semantic']!='SV_IsFrontFace0' for p in f[1] if not p['out']):raise RuntimeError('Native vertex/pixel signature mismatch')

            if any(k in v[2] and v[2][k]!=kind for k,kind in f[2].items()):raise RuntimeError('Native stages disagree about constant type')
            declaration=dict(v[2]);declaration.update(f[2]);tex={x['name']:x for x in v[3]+f[3]}
            prefix='#if '+condition+'\n' if condition else ''
            declarations.update(declaration);textures.update(tex)
            source=prefix+'\n'.join(kind+' '+name+';' for name,kind in sorted(declaration.items()))+'\n'+'\n'.join(('Texture2D' if t['dimension']==2 else 'TextureCube')+'<float4> '+t['name']+'; '+t['sampler_type']+' sampler'+t['name']+';' for t in tex.values() if t['name']!='unity_SpecCube0')+'\n'+v[0]+'\n'+f[0]+'\n'
            source+='Varyings vert(AppData i) {Varyings o=(Varyings)0;'+call(vi,v[1])+'return o;}\n'
            face=', bool face : SV_IsFrontFace' if any(p['semantic']=='SV_IsFrontFace0' for p in f[1]) else ''
            source+='Targets frag(Varyings i'+face+') {Targets o=(Targets)0;'+call(fi,f[1])+'return o;}\n'
            if condition:source+='#endif\n'
            entry.append(source)
        return 'HLSLPROGRAM\n#pragma target 4.0\n#pragma vertex vert\n#pragma fragment frag\n'+entry_directives+'#include "UnityCG.cginc"\n'+structure('AppData',inputs)+'\n'+structure('Varyings',varyings)+'\n'+structure('Targets',targets)+'\n'+''.join(entry)+'ENDHLSL\n'
    def pair(self,context,pass_index,keys,subshader_index=0):
        matches=[]
        for stage in ['progVertex','progFragment']:
            found=[r['index'] for r in context[2] if r['kind']=='program' and r['stage']==stage and r['keywords']==sorted(keys) and any(c['pass_index']==pass_index and c['subshader_index']==subshader_index for c in r.get('consumers',[r]))]
            if len(found)!=1:raise RuntimeError('Native feature/pass pair is ambiguous: '+str(keys))
            matches.append(found[0])
        return matches
