"""Bind locally recovered shader programs; never publish generated math."""
from common import *
import base64, re
import UnityPy
from shader_segments import read_segments, selected_layout


def properties(tree):
    lines = []
    for p in tree['m_ParsedForm']['m_PropInfo']['m_Props']:
        values = [p[f'm_DefValue[{i}]'] for i in range(4)]
        kind = p['m_Type']
        if kind in [0,1]:
            label = 'Color' if kind==0 else 'Vector'; value = '('+','.join(map(str,values))+')'
        elif kind in [2,3]:
            label = 'Float' if kind==2 else f'Range({values[1]},{values[2]})'; value = str(values[0])
        elif kind==4 and p['m_DefTexture']['m_TexDim'] in [1,2,4]:
            label = {1:'any',2:'2D',4:'Cube'}[p['m_DefTexture']['m_TexDim']]; value = json.dumps(p['m_DefTexture']['m_DefaultName'])+' {}'
        else: raise RuntimeError('Unmeasured recovered property type')
        lines.append(f'{p["m_Name"]} ({json.dumps(p["m_Description"])}, {label}) = {value}')
    return '\n'.join(lines)


def bind_hlsl(source, layout, entry):
    """Change resources/constants only; keep executable expressions unchanged."""
    signature = re.search(r'void main\((.*?)\)\s*(?=\{)',source,re.S)
    if not signature: raise RuntimeError('Unexpected recovered entry signature')
    parameters = []
    for item in re.split(r'\s*,\s*',signature[1].strip()):
        match = re.fullmatch(r'(out (?:precise )?)?float([1-4]) (\w+) : (\w+)',item.strip())
        if not match:
            face=re.fullmatch(r'uint (\w+) : SV_IsFrontFace0',item.strip())
            if not face:raise RuntimeError('Unmeasured shader I/O shape')
            parameters.append({'out':False,'name':face[1],'semantic':'SV_IsFrontFace0','columns':1,'type':'uint'});continue
        parameters.append({'out':bool(match[1]),'name':match[3],'semantic':match[4],'columns':int(match[2])})
    body = source[source.index('{',signature.end()):]
    buffers = {b['slot']:b for b in layout['buffers']}; used = []; declarations = {}
    def constant(match):
        slot,index = map(int,match.group(1,2)); start=index*16
        if slot not in buffers: raise RuntimeError('Unbound original constant buffer')
        variables = buffers[slot]['variables']; lanes = []
        for lane in range(4):
            offset = start+lane*4; candidates = []
            for v in variables:
                stride=64 if v['matrix'] else 16
                size=stride*v['array_size'] if v['array_size'] else 64 if v['matrix'] else v['columns']*4
                if v['type'] not in [0,1]: raise RuntimeError('Unmeasured constant type binding')
                if v['offset']<=offset<v['offset']+size: candidates.append(v)
            if len(candidates)>1: raise RuntimeError('Overlapping native constants')
            if not candidates:
                # Never fill a lane that the native expression actually reads.
                suffix = body[match.end():]; swizzle = re.match(r'\.([xyzw]+)',suffix)
                if not swizzle or 'xyzw'[lane] in swizzle[1]: raise RuntimeError('Used native constant lane has no measured binding')
                lanes.append('0.0');continue
            v=candidates[0]; delta=offset-v['offset']; name=v['name'];reference=name
            if v['array_size']:
                stride=64 if v['matrix'] else 16;reference+='['+str(delta//stride)+']';delta%=stride
                if not v['matrix'] and delta>=v['columns']*4:raise RuntimeError('Consumed native array padding needs measurement')
            if v['matrix']:
                if v['type']!=0 or v['rows']!=4 or v['columns']!=4:raise RuntimeError('Unmeasured matrix binding')
                expression=f'transpose({reference})[{delta//16}].'+ 'xyzw'[(delta%16)//4]
            else: expression=reference+('.'+'xyzw'[delta//4] if v['columns']>1 else '')
            # d3dasm models all CB registers as float4; native integer lanes
            # contain integer bits, not a numeric float conversion.
            if v['type']==1:expression='asfloat('+expression+')'
            lanes.append(expression)
            if (not name.startswith('unity_') or name in ['unity_LightmapFade','unity_WorldToLight']) and name not in ['_Time','_WorldSpaceCameraPos','_ProjectionParams','_ZBufferParams','_ScreenParams','_LightShadowData','_LightProjectionParams','_WorldSpaceLightPos0']:
                if v['array_size']:raise RuntimeError('Non-builtin array declarations need a separate measured contract')
                declarations[name]='float4x4' if v['matrix'] else ('int' if v['type']==1 else 'float')+(str(v['columns']) if v['columns']>1 else '')
        used.append({'slot':slot,'register':index,'lanes':lanes})
        return '(float4('+','.join(lanes)+'))'
    body = re.sub(r'cb(\d+)\[(\d+)\]',constant,body)
    if re.search(r'\bcb\d+\b',body): raise RuntimeError('Unbound dynamic native constant access')
    textures=[]
    for t in layout['textures']:
        texture=f't{t["slot"]}'; sampler=f's{t["sampler"]}'; name=t['name']
        declaration=re.search(r'\b(Texture2D|TextureCube)<float4> '+texture+r' : register\(t'+str(t['slot'])+r'\);',source)
        if not declaration:raise RuntimeError('Unmeasured native texture declaration')
        dimension=2 if declaration[1]=='Texture2D' else 4
        if t['dimension'] not in [None,dimension] or t.get('multisampled'): raise RuntimeError('Native texture dimension disagreement')
        t['dimension']=dimension;t['dxbc_declaration']=declaration[0]
        body=re.sub(r'\b'+texture+r'\b',name,body)
        body=re.sub(r'\b'+sampler+r'(?:_s)?\b','sampler'+name,body)
        sampler_declaration=re.search(r'\b(SamplerState|SamplerComparisonState) '+sampler+r'(?:_s)? : register\(s'+str(t['sampler'])+r'\);',source)
        if not sampler_declaration:raise RuntimeError('Unmeasured native sampler declaration')
        t['sampler_type']=sampler_declaration[1]
        if dimension==4 and t['sampler_type']=='SamplerComparisonState' and name+'.SampleCmpLevelZero(' in body:
            # The exact editor's HLSLSupport.cginc uses implicit comparison
            # sampling for GL/Vulkan cube shadows: explicit LOD is unsupported.
            # This is resource lowering, with the native comparison/math intact.
            body=body.replace(name+'.SampleCmpLevelZero(', 'AndroidNativeCubeShadow('+name+',')
            t['platform_lowering']='Unity2021.3 HLSLSupport cube comparison API: SampleCmp on GL/Vulkan; LevelZero on D3D/Metal'
        textures.append(name)
    if re.search(r'\b[ts]\d+\b',body): raise RuntimeError('Unbound native texture/sampler')
    # DXBC signatures can expose float4 registers while writing only consumed
    # lanes. Unity's source compiler requires all out lanes initialized. These
    # defaults precede every original write; original written lanes are intact.
    body='{\n'+''.join(p['name']+'=float'+str(p['columns'])+'('+','.join('0' for _ in range(p['columns']))+');\n' for p in parameters if p['out'])+body[1:]
    signature_text=signature[0].replace('void main(','void '+entry+'(')
    macros='\n'.join(re.findall(r'^#define [^\n]+',source[:signature.start()],re.M))
    if 'AndroidNativeCubeShadow(' in body:
        macros+='\n#ifndef AndroidNativeCubeShadow\n#if defined(SHADER_API_VULKAN) || defined(SHADER_API_GLCORE) || defined(SHADER_API_GLES3)\n#define AndroidNativeCubeShadow(tex,samp,coord,depth) tex.SampleCmp(samp,coord,depth)\n#else\n#define AndroidNativeCubeShadow(tex,samp,coord,depth) tex.SampleCmpLevelZero(samp,coord,depth)\n#endif\n#endif\n'
    return macros+'\n'+signature_text+'\n'+body,parameters,declarations,textures,used


def generate():
    selection=WORK/'config/shader-source-analysis.json'
    if not selection.exists(): raise RuntimeError('Select a receipted private Cloud analysis in work/config/shader-source-analysis.json')
    source_analysis=ROOT/read(selection)['path']
    source_analysis=source_analysis.resolve()
    if WORK.resolve() not in source_analysis.parents: raise RuntimeError('Shader analysis must be private')
    receipt=read(source_analysis/'receipt.json')
    if not receipt.get('success') or receipt['shader']!='Hopoo Games/FX/Cloud Intersection Remap':
        raise RuntimeError('A passing same-program Cloud tool chain is required')
    inventory=read(WORK/'inventory/files.json')
    if read(WORK/'config/accepted-input.json')['input_id']!=inventory['input_id']: raise RuntimeError('Shader input has not been accepted')
    expected=next(x['sha256'] for x in inventory['files'] if x['path']==receipt['source_bundle'])
    source_bundle=game()/receipt['source_bundle']
    if sha(source_bundle)!=expected or receipt['source_sha256']!=expected: raise RuntimeError('Shader source drift')
    from shader_recovery import PINS
    tool=WORK/PINS['d3dasm'][0];pin=PINS['d3dasm'][1]
    if run(['git','-C',tool,'rev-parse','HEAD']).stdout.decode().strip()!=pin or run(['git','-C',tool,'diff','HEAD','--']).stdout:
        raise RuntimeError('d3dasm source pin changed')
    exe=tool/'target/release/d3dasm'
    if sha(exe)!=receipt['tool_binary_hashes'][str(exe.relative_to(WORK))]: raise RuntimeError('d3dasm binary differs from analysis')
    tree=read(source_analysis/'original-tree-base64.json')
    objects=[o for o in UnityPy.load(str(source_bundle)).objects if o.type.name=='Shader' and o.path_id==-15541403510422607]
    if len(objects)!=1: raise RuntimeError('Original intersection identity changed')
    actual=objects[0].read_typetree();actual['compressedBlob']=base64.b64encode(bytes(actual['compressedBlob'])).decode()
    # JSON archives represent native tuple pairs as lists; compare that exact
    # storage representation, without shader-tool aliases or value rewrites.
    if json.loads(json.dumps(actual))!=tree: raise RuntimeError('Private shader tree differs from the accepted source bundle')
    raw,records,programs=read_segments(tree,base64.b64decode(tree['compressedBlob']))
    out=WORK/'experiments/shader-bindings'/now();out.mkdir(parents=True)
    write(WORK/'shader-bindings-current.json',{'path':str(out.relative_to(ROOT))})
    result={'success':False,'source_analysis':str(source_analysis.relative_to(ROOT)), 'source_sha256':receipt['source_sha256'],
            'semantic_equivalence_proven':False,'PC_draw_validation_performed':False,'programs':[]}
    try:
        definitions=[];declarations={};textures=set();inputs=set();outputs=set();vertex={};fragment={}
        for index in [8,6,42,39,40,41]:
            record=records[index];original=out/f'unity-{index}.dxbc';original.write_bytes(programs[index])
            hlsl=out/f'unity-{index}.hlsl';assembly=out/f'unity-{index}.d3dasm';rebuilt=out/f'unity-{index}.roundtrip.dxbc'
            for fmt,dest in [('hlsl',hlsl),('d3dasm',assembly)]:run([exe,original,'--emit',fmt,'--output',dest])
            run([exe,assembly,'--assemble','--output',rebuilt])
            if sha(original)!=sha(rebuilt):raise RuntimeError('Native roundtrip changed')
            layout=selected_layout(tree,raw,record);write(out/f'unity-{index}-layout.json',layout)
            bound,params,decls,tex,used=bind_hlsl(hlsl.read_text(),layout,'native_'+str(index))
            definitions.append(bound);textures.update(tex)
            for name,kind in decls.items():
                if name in declarations and declarations[name]!=kind:raise RuntimeError('Cross-stage constant type disagreement')
                declarations[name]=kind
            if record['stage']=='progVertex':
                vertex[index]=params;inputs.update(p['semantic'] for p in params if not p['out']);outputs.update(p['semantic'] for p in params if p['out'])
            else:fragment[index]=params
            result['programs'].append({'index':index,'dxbc_sha256':sha(original),'layout_sha256':sha(out/f'unity-{index}-layout.json'),
                                      'native_roundtrip_identical':True,'constant_bindings':used,'keywords':record['keywords']})
        def structure(name,semantics):return 'struct '+name+' {\n'+'\n'.join('float4 '+s+' : '+s+';' for s in sorted(semantics))+'\n};'
        def call(index,params):return 'native_'+str(index)+'('+','.join(('o.' if p['out'] else 'i.')+p['semantic'] for p in params)+');'
        vertex_entry='Varyings vert(AppData i) { Varyings o=(Varyings)0; if (_TriplanarOn>0.5) {'+call(6,vertex[6])+'} else {'+call(8,vertex[8])+'} return o; }'
        def pixel(index):return 'native_'+str(index)+'('+','.join('result' if p['out'] else 'i.'+p['semantic'] for p in fragment[index])+');'
        fragment_entry='float4 frag(Varyings i):SV_Target {float4 result; if (_TriplanarOn>0.5) {if (_FadeFromVertexColorsOn>0.5) {'+pixel(41)+'} else {'+pixel(40)+'}} else {if (_FadeFromVertexColorsOn>0.5) {'+pixel(39)+'} else {'+pixel(42)+'}} return result;}'
        declarations.update({'_TriplanarOn':'float','_FadeFromVertexColorsOn':'float'})
        state=tree['m_ParsedForm']['m_SubShaders'][0]['m_Passes'][0]['m_State']
        if state['zWrite']['val']!=0 or state['zTest']['val']!=4 or state['culling']['name']!='_Cull':raise RuntimeError('Source intersection render state changed')
        blend=state['rtBlend0']
        if blend['srcBlend']['name']!='_SrcBlendFloat' or blend['destBlend']['name']!='_DstBlendFloat':raise RuntimeError('Source blend binding changed')
        shader='// Generated privately from shipped programs; bindings adapted, PC parity unverified.\nShader "Porting Lab/Android Intersection Presentation" {\nProperties {\n'+properties(tree)+'\n}\nSubShader {Tags {"Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True"}\nPass {Name "FORWARD" Tags {"LightMode"="ForwardBase"} Blend [_SrcBlendFloat] [_DstBlendFloat] Cull [_Cull] ZTest LEqual ZWrite Off\nHLSLPROGRAM\n#pragma target 4.0\n#pragma vertex vert\n#pragma fragment frag\n#include "UnityCG.cginc"\n'
        shader+='\n'.join(kind+' '+name+';' for name,kind in sorted(declarations.items()))+'\n'
        shader+='\n'.join('Texture2D<float4> '+name+'; SamplerState sampler'+name+';' for name in sorted(textures))+'\n'
        shader+=structure('AppData',inputs)+'\n'+structure('Varyings',outputs)+'\n'+'\n'.join(definitions)+'\n'+vertex_entry+'\n'+fragment_entry+'\nENDHLSL\n}}}\n'
        sources=out/'sources';sources.mkdir();dest=sources/'AndroidIntersectionPresentation.shader';dest.write_text(shader)
        result.update(success=True,source_sha256_by_file={dest.name:sha(dest)},generator_sha256=sha(__file__),
                      output_initialization='Zero before original writes to satisfy Unity out-parameter checks; native written lanes preserved',
                      scope='Native float32 expressions and measured bindings, four material feature combinations; mono/non-instanced ForwardBase only; final semantic and PC visual validation open')
    except Exception as error:
        result['first_failure']=str(error);raise
    finally:write(out/'receipt.json',result)
    print(json.dumps({'success':True,'evidence':str(out.relative_to(ROOT)),'device_rendering_verified':False}))
    return out
