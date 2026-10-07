"""Private Standard/lighting candidate from measured shipped programs and layouts."""
from common import *
from shader_segments import read_segments,selected_layout
from shader_source import bind_hlsl,properties
from shader_recovery import PINS
import base64,re,shutil,UnityPy

FEATURES=['PRINT_CUTOFF','SPLATMAP','FORCE_SPEC','DITHER','CUTOUT','USE_VERTEX_COLORS','FRESNEL_EMISSION','USE_VERTEX_COLORS_FOR_FRESNEL_EMISSION_AND_FLOWMAP','FLOWMAP','LIMBREMOVAL']


def load_analysis(path,identity,shader):
    path=(ROOT/path).resolve()
    if WORK.resolve() not in path.parents:raise RuntimeError('Recovery evidence must be private')
    receipt=read(path/'receipt.json')
    if not receipt.get('analysis_complete') or receipt['shader']!=shader:raise RuntimeError('Incomplete or wrong native shader analysis')
    for p in receipt['programs']:
        if not p.get('dxbc_roundtrip_identical'):raise RuntimeError('Native program roundtrip missing')
    inventory=read(WORK/'inventory/files.json')
    if read(WORK/'config/accepted-input.json')['input_id']!=inventory['input_id']:raise RuntimeError('Shader input not accepted')
    source=game()/receipt['source_bundle'];expected=next(x['sha256'] for x in inventory['files'] if x['path']==receipt['source_bundle'])
    if sha(source)!=expected or receipt['source_sha256']!=expected:raise RuntimeError('Shader source drift')
    objects=[x for x in UnityPy.load(str(source)).objects if x.type.name=='Shader' and x.path_id==identity]
    if len(objects)!=1:raise RuntimeError('Native shader identity ambiguous')
    tree=objects[0].read_typetree();tree['compressedBlob']=base64.b64encode(bytes(tree['compressedBlob'])).decode()
    if json.loads(json.dumps(tree))!=read(path/'original-tree-base64.json'):raise RuntimeError('Native shader tree drift')
    raw,records,programs=read_segments(tree,base64.b64decode(tree['compressedBlob']))
    return tree,raw,records,programs,receipt


def render_state(state,ui=False):
    def value(field,names):
        v=state[field]
        if v['name'] not in ['', '<noninit>']:return '['+v['name']+']'
        n=int(v['val'])
        if n not in names:raise RuntimeError('Unclassified native render state: '+field)
        return names[n]
    compare={0:'Disabled',1:'Never',2:'Less',3:'Equal',4:'LEqual',5:'Greater',6:'NotEqual',7:'GEqual',8:'Always'}
    blend={0:'Zero',1:'One',2:'DstColor',3:'SrcColor',4:'OneMinusDstColor',5:'SrcAlpha',6:'OneMinusSrcColor',7:'DstAlpha',8:'OneMinusDstAlpha',9:'SrcAlphaSaturate',10:'OneMinusSrcAlpha'}
    if state['offsetFactor']['val']!=0 or state['offsetUnits']['val']!=0 or state['rtSeparateBlend']:
        raise RuntimeError('Native separate blending or polygon offset requires measurement')
    b=state['rtBlend0']
    if b['blendOp']['val']!=0 or b['blendOpAlpha']['val']!=0 or (b['colMask']['val']!=15 and not ui):raise RuntimeError('Unmeasured native blend operation or color mask')
    def bv(k):
        v=b[k];return '['+v['name']+']' if v['name'] not in ['', '<noninit>'] else blend[int(v['val'])]
    for k in ['srcBlend','destBlend']:
        if b[k]!=b[k+'Alpha']:raise RuntimeError('Separate native alpha blend requires measurement')
    text='Cull '+value('culling',{0:'Off',1:'Front',2:'Back'})+' ZWrite '+value('zWrite',{0:'Off',1:'On'})+' ZTest '+value('zTest',compare)+' Blend '+bv('srcBlend')+' '+bv('destBlend')+'\n'
    if state['stencilOpFront']!=state['stencilOpBack']:raise RuntimeError('Separate native stencil faces require measurement')
    op=state['stencilOp'] if ui else state['stencilOpFront']
    if ui:
        mask=b['colMask'];text+='ColorMask '+('['+mask['name']+']' if mask['name'] not in ['', '<noninit>'] else str(int(mask['val'])))+'\n'
        operations={0:'Keep',1:'Zero',2:'Replace',3:'IncrSat',4:'DecrSat',5:'Invert',6:'IncrWrap',7:'DecrWrap'}
        def stencil(k,names):
            v=op[k];return '['+v['name']+']' if v['name'] not in ['', '<noninit>'] else names[int(v['val'])]
        stencil_text=' Comp '+stencil('comp',compare)+' Pass '+stencil('pass',operations)+' Fail '+stencil('fail',operations)+' ZFail '+stencil('zFail',operations)
    else:
        if any(op[k]['val']!=0 for k in ['fail','pass','zFail']):raise RuntimeError('Non-keep native stencil operation requires measurement')
        stencil_text=' Comp '+compare[int(op['comp']['val'])]+' Pass Keep Fail Keep ZFail Keep'
    text+='Stencil {Ref '+value('stencilRef',{i:str(i) for i in range(256)})+' ReadMask '+value('stencilReadMask',{i:str(i) for i in range(256)})+' WriteMask '+value('stencilWriteMask',{i:str(i) for i in range(256)})+stencil_text+'}\n'
    return text


def generate():
    selection=read(WORK/'config/shader-deferred-analysis.json')
    out=WORK/'experiments/deferred-bindings'/now();out.mkdir(parents=True);sources=out/'sources';sources.mkdir()
    write(WORK/'deferred-bindings-current.json',{'path':str(out.relative_to(ROOT))})
    result={'success':False,'semantic_equivalence_proven':False,'PC_draw_validation_performed':False,'selection':selection,'programs':[]}
    try:
        standard=load_analysis(selection['standard'],-197252232775272061,'Hopoo Games/Deferred/Standard')
        lighting=load_analysis(selection['lighting'],5,'Hidden/Internal-DeferredShading')
        for key in ['d3dasm','hlsl']:
            path,pin=PINS[key];tool=WORK/path
            if run(['git','-C',tool,'rev-parse','HEAD']).stdout.decode().strip()!=pin or run(['git','-C',tool,'diff','HEAD','--']).stdout:raise RuntimeError('Recovery tool pin drift')
        exe=WORK/PINS['d3dasm'][0]/'target/release/d3dasm'
        if sha(exe)!=standard[4]['tool_binary_hashes'][str(exe.relative_to(WORK))]:raise RuntimeError('Native decompiler binary drift')
        material_file=ROOT/selection['material_inventory'];material_file=material_file.resolve()
        if WORK.resolve() not in material_file.parents or sha(material_file)!=selection['material_inventory_sha256']:raise RuntimeError('Measured material inventory drift')
        rows=[x.split('|') for x in material_file.read_text().splitlines() if '|Hopoo Games/Deferred/Standard|' in x]
        feature_sets=sorted({tuple(sorted(set(x[2].split(','))&set(FEATURES))) for x in rows})
        if not rows or len(feature_sets)>128:raise RuntimeError('Unexpected native material closure')
        from shader_programs import NativePrograms
        emitter=NativePrograms(out,result,exe);bound=emitter.bound;block=emitter.block;pair=emitter.pair
        variants=[];tree=standard[0];passes=tree['m_ParsedForm']['m_SubShaders'][0]['m_Passes']
        shadow_features=set(k for r in standard[2] if r['kind']=='program' and r['pass_index']==1 for k in r['keywords'])&set(FEATURES)
        for i,features in enumerate(feature_sets):
            name='AndroidNativeStandard'+str(i);vi,fi=pair(standard,0,set(features)|{'LIGHTPROBE_SH','UNITY_HDR_ON'})
            shader='// Private recovered candidate; PC draw/semantic parity unverified.\nShader "Porting Lab/'+name+'" {\nProperties {\n'+properties(tree)+'\n}\nSubShader {Tags {"RenderType"="Opaque"}\n'
            shader+='Pass {Name "DEFERRED" Tags {"LightMode"="Deferred"}\n'+render_state(passes[0]['m_State'])+block(standard,[(None,vi,fi)])+'}\n'
            shadow_pairs=[]
            for keyword in ['SHADOWS_DEPTH','SHADOWS_CUBE']:
                svi,sfi=pair(standard,1,(set(features)&shadow_features)|{keyword});shadow_pairs.append(('defined('+keyword+')',svi,sfi))
            shader+='Pass {Name "ShadowCaster" Tags {"LightMode"="ShadowCaster"}\n'+render_state(passes[1]['m_State'])+block(standard,shadow_pairs,'#pragma multi_compile_shadowcaster\n')+'}\n}}\n'
            (sources/(name+'.shader')).write_text(shader);variants.append({'resource':name,'keywords':list(features),'vertex':vi,'fragment':fi})
        light_tree=lighting[0];passes=light_tree['m_ParsedForm']['m_SubShaders'][0]['m_Passes'];allkeys=sorted(set(k for r in lighting[2] if r['kind']=='program' and r['pass_index']==0 for k in r['keywords']));pairs=[]
        for keys in sorted({tuple(r['keywords']) for r in lighting[2] if r['kind']=='program' and r['pass_index']==0}):
            vi,fi=pair(lighting,0,keys);condition=' && '.join(('defined('+k+')' if k in keys else '!defined('+k+')') for k in allkeys);pairs.append((condition,vi,fi))
        shader='// Private recovered lighting candidate; no PC semantic-parity claim.\nShader "Porting Lab/AndroidNativeDeferredLighting" {Properties {\n'+properties(light_tree)+'\n}\nSubShader {\n'
        shader+='Pass {Tags {"SHADOWSUPPORT"="true"}\n'+render_state(passes[0]['m_State'])+block(lighting,pairs,'#pragma multi_compile_lightpass\n#pragma multi_compile __ UNITY_HDR_ON\n')+'}\n'
        vi,fi=pair(lighting,1,[]);shader+='Pass {\n'+render_state(passes[1]['m_State'])+block(lighting,[(None,vi,fi)])+'}\n}}\n';(sources/'AndroidNativeDeferredLighting.shader').write_text(shader)
        write(sources/'AndroidNativeStandardVariants.json',{'features':FEATURES,'variants':variants,'source_material_count':len(rows),'scope':'Measured static material features, mono/noninstanced SH/HDR Standard and original custom lighting; other families/reflections/PC parity remain open'})
        result.update(success=True,material_count=len(rows),variant_count=len(variants),source_sha256_by_file={p.name:sha(p) for p in sources.iterdir()},scope='Source program candidate, not Android execution or PC parity; original comparison-sampler fallback tool paths explicit')
    except Exception as error:result['first_failure']=str(error);raise
    finally:write(out/'receipt.json',result)
    print(json.dumps({'success':True,'evidence':str(out.relative_to(ROOT)),'variants':result['variant_count']}));return out
