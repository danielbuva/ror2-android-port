"""Privately recover the measured cloud, snow, terrain and reflection closure."""
from common import *
from shader_deferred import load_analysis,render_state
from shader_programs import NativePrograms
from shader_tessellation import TessellationPrograms
from shader_source import properties
from shader_recovery import PINS

FAMILIES={
 'cloud':(-658352061839041481,'Hopoo Games/FX/Cloud Remap'),
 'opaque-cloud':(-704325499538927933,'Hopoo Games/FX/Opaque Cloud Remap'),
 'snow':(3671293666148614723,'Hopoo Games/Deferred/Snow Topped'),
 'terrain':(5954585457266417408,'Hopoo Games/Deferred/Triplanar Terrain Blend'),
 'grass':(-8989458460904117762,'Hopoo Games/Environment/Waving Grass'),
 'cloth':(-6170440028897955187,'Hopoo Games/Deferred/Wavy Cloth'),
 'ui-alpha':(-8085301563477162814,'Hopoo Games/UI/Animate Alpha'),
 'distortion':(1142643595885926041,'Hopoo Games/FX/Distortion'),
 'speedtree':(-8684109817920462965,'SpeedtreeOverride/SpeedtreeCustom'),
 'water-single':(-8115552462691183134,'CalmWater/Calm Water [DX11]'),
 'water':(-92852985697471365,'CalmWater/Calm Water [DX11] [Double Sided]'),
}
ENGINE={'STEREO_INSTANCING_ON','UNITY_SINGLE_PASS_STEREO','STEREO_MULTIVIEW_ON','STEREO_CUBEMAP_RENDER_ON','INSTANCING_ON','LIGHTPROBE_SH','DYNAMICLIGHTMAP_ON','SHADOWS_SHADOWMASK','LIGHTMAP_ON','DIRLIGHTMAP_COMBINED','UNITY_HDR_ON','SHADOWS_DEPTH','SHADOWS_CUBE','EDITOR_VISUALIZATION','FOG_LINEAR','FOG_EXP','FOG_EXP2','DIRECTIONAL','LIGHTMAP_SHADOW_MIXING','SHADOWS_SCREEN','VERTEXLIGHT_ON','POINT','SPOT','POINT_COOKIE','DIRECTIONAL_COOKIE','SOFTPARTICLES_ON'}

def tags(pairs):
    return 'Tags {'+' '.join(json.dumps(k)+'='+json.dumps(v) for k,v in pairs)+'}\n'

def align_exported_subshader_tags(path, tree, evidence):
    """Restore measured metadata on an owned placeholder; never its shader math."""
    import re,shutil
    work=WORK.resolve();path=Path(path).resolve();evidence=Path(evidence).resolve()
    if (work/'lab-project').resolve() not in path.parents or work not in evidence.parents:
        raise RuntimeError('Shader metadata correction requires owned ignored copies')
    form=tree['m_ParsedForm'];subshaders=form['m_SubShaders'];text=path.read_text()
    names=re.findall(r'^Shader\s+"([^"]+)"',text,re.M)
    pattern=r'(?m)^(\s*SubShader\s*\{\s*\n)\s*Tags\s*\{[^}]*\}'
    if names!=[form['m_Name']] or len(subshaders)!=1 or len(re.findall(pattern,text))!=1:
        raise RuntimeError('Exported shader/tag identity is ambiguous')
    before=sha(path);backup=evidence/('prior-tags-'+digest(str(path.relative_to(work)))[:16]+'.shader')
    if backup.exists():raise RuntimeError('Retain each shader metadata attempt separately')
    shutil.copy2(path,backup)
    original_tags=subshaders[0]['m_Tags']['tags']
    updated=re.sub(pattern,lambda m:m[1]+tags(original_tags).rstrip(),text,count=1)
    path.write_text(updated)
    return {'shader':form['m_Name'],'path':str(path.relative_to(work)),
            'before_sha256':before,'after_sha256':sha(path),'native_tags':original_tags,
            'scope':'Original subshader tags only; placeholder body unchanged, no recovered-math or appearance claim.'}

def generate():
    selection=read(WORK/'config/shader-material-analysis.json');out=WORK/'experiments/material-bindings'/now();out.mkdir(parents=True);sources=out/'sources';sources.mkdir()
    write(WORK/'material-bindings-current.json',{'path':str(out.relative_to(ROOT))})
    result={'success':False,'semantic_equivalence_proven':False,'PC_draw_validation_performed':False,'selection':selection,'programs':[]}
    try:
        contexts={name:load_analysis(selection[name],identity,shader) for name,(identity,shader) in FAMILIES.items() if name in selection or name not in ['water','water-single']}
        if ('water' in contexts)!=('water-single' in contexts):raise RuntimeError('Partial native water family selection')
        topology=selection.get('water_topology','native-tessellation')
        if topology not in ['native-tessellation','original-vertices']:raise RuntimeError('Unmeasured native water topology selection')
        result['water_topology']=topology;result['water_geometry_approximation']=topology=='original-vertices'
        reflection=load_analysis(selection['reflections'],3,'Hidden/Internal-DeferredReflections')
        for key in ['d3dasm','hlsl']:
            relative,pin=PINS[key];tool=WORK/relative
            if run(['git','-C',tool,'rev-parse','HEAD']).stdout.decode().strip()!=pin or run(['git','-C',tool,'diff','HEAD','--']).stdout:raise RuntimeError('Recovery tool pin drift')
        exe=WORK/PINS['d3dasm'][0]/'target/release/d3dasm'
        for context in list(contexts.values())+[reflection]:
            if sha(exe)!=context[4]['tool_binary_hashes'][str(exe.relative_to(WORK))]:raise RuntimeError('Native decompiler binary drift')
        material_file=(ROOT/selection['material_inventory']).resolve()
        if WORK.resolve() not in material_file.parents or sha(material_file)!=selection['material_inventory_sha256']:raise RuntimeError('Measured material inventory drift')
        rows=[x.split('|') for x in material_file.read_text().splitlines()];emitter=TessellationPrograms(out,result,exe);families=[]
        for ordinal,(name,context) in enumerate(contexts.items()):
            tree=context[0];form=tree['m_ParsedForm'];sub=form['m_SubShaders'][0];passes=sub['m_Passes'];features=set(form['m_KeywordNames'])-ENGINE-{'UNITY_UI_CLIP_RECT','UNITY_UI_ALPHACLIP'};ui=name=='ui-alpha'
            if name=='speedtree':features-={'ENABLE_WIND','LOD_FADE_PERCENTAGE','LOD_FADE_CROSSFADE'}
            water=name in ['water','water-single'];first_pass=1 if name=='distortion' or water else 0
            materials=[x for x in rows if x[1]==form['m_Name']];sets=sorted({tuple(sorted(set(x[2].split(','))&features)) for x in materials})
            if not sets or len(sets)>128:raise RuntimeError('Unexpected native material closure')
            variants=[]
            for i,keys in enumerate(sets):
                resource='AndroidNativeFamily'+str(ordinal)+'Variant'+str(i)
                text='// Private native candidate; PC draw/semantic parity unverified.\nShader "Porting Lab/'+resource+'" {\nProperties {\n'+properties(tree)+'\n}\nSubShader {\n'+tags(sub['m_Tags']['tags'])
                if name=='distortion' or water:
                    grab=passes[0]
                    if grab['m_Type']!=2 or not grab['m_TextureName'] or any(grab[stage]['m_PlayerSubPrograms'] for stage in ['progVertex','progFragment','progHull','progDomain','progGeometry']):raise RuntimeError('Unmeasured native grab pass')
                    text+='GrabPass {'+json.dumps(grab['m_TextureName'])+'}\n'
                if water:
                    if topology=='original-vertices' and any(k.startswith('_DISPLACEMENTMODE_') for k in keys):raise RuntimeError('Original-vertex water requires measured non-displacement variants')
                    for pi in range(1,len(passes)):
                        p=passes[pi];pairs=[]
                        for fog in [None,'FOG_LINEAR','FOG_EXP']:
                            for sh in [False,True]:
                                for shadow in [False,True]:
                                    engine={'DIRECTIONAL'}|({fog} if fog else set())|({'LIGHTPROBE_SH'} if sh else set())|({'SHADOWS_SCREEN'} if shadow else set())
                                    condition=('defined('+fog+')' if fog else '!defined(FOG_LINEAR) && !defined(FOG_EXP)')+' && '+('' if sh else '!')+'defined(LIGHTPROBE_SH) && '+('' if shadow else '!')+'defined(SHADOWS_SCREEN)'
                                    pairs.append((condition,emitter.quad(context,pi,set(keys)|engine)))
                        text+='Pass {Name '+json.dumps(p['m_State']['m_Name'])+' '+tags(p['m_State']['m_Tags']['tags'])+render_state(p['m_State'])+emitter.water_block(context,pairs,original_vertices=topology=='original-vertices')+'}\n'
                    text+='}}\n';(sources/(resource+'.shader')).write_text(text);variants.append({'resource':resource,'keywords':list(keys)});continue
                text+='Pass {Name '+json.dumps(passes[first_pass]['m_State']['m_Name'])+' '+tags(passes[first_pass]['m_State']['m_Tags']['tags'])+render_state(passes[first_pass]['m_State'],ui=ui)
                if ui:
                    pairs=[]
                    for clip in [False,True]:
                        for alpha in [False,True]:
                            engine=({'UNITY_UI_CLIP_RECT'} if clip else set())|({'UNITY_UI_ALPHACLIP'} if alpha else set());vi,fi=emitter.pair(context,0,set(keys)|engine)
                            condition=('' if clip else '!')+'defined(UNITY_UI_CLIP_RECT) && '+('' if alpha else '!')+'defined(UNITY_UI_ALPHACLIP)';pairs.append((condition,vi,fi))
                    text+=emitter.block(context,pairs,'#pragma multi_compile_local __ UNITY_UI_CLIP_RECT\n#pragma multi_compile_local __ UNITY_UI_ALPHACLIP\n')
                elif name=='cloud':
                    pairs=[]
                    for sh in [False,True]:
                        for soft in [False,True]:
                            engine={'DIRECTIONAL'}|({'LIGHTPROBE_SH'} if sh else set())|({'SOFTPARTICLES_ON'} if soft else set());vi,fi=emitter.pair(context,0,set(keys)|engine)
                            condition=('' if sh else '!')+'defined(LIGHTPROBE_SH) && '+('' if soft else '!')+'defined(SOFTPARTICLES_ON)';pairs.append((condition,vi,fi))
                    text+=emitter.block(context,pairs,'#pragma multi_compile __ LIGHTPROBE_SH\n#pragma multi_compile_particles\n')
                elif name=='distortion':
                    pairs=[]
                    for soft in [False,True]:
                        vi,fi=emitter.pair(context,first_pass,set(keys)|({'SOFTPARTICLES_ON'} if soft else set()));pairs.append((('' if soft else '!')+'defined(SOFTPARTICLES_ON)',vi,fi))
                    text+=emitter.block(context,pairs,'#pragma multi_compile_particles\n')
                elif name=='speedtree':
                    pairs=[]
                    for lod in ['LOD_FADE_PERCENTAGE','LOD_FADE_CROSSFADE']:
                        for wind in [False,True]:
                            vi,fi=emitter.pair(context,0,set(keys)|{'LIGHTPROBE_SH','UNITY_HDR_ON',lod}|({'ENABLE_WIND'} if wind else set()))
                            condition=('' if lod=='LOD_FADE_CROSSFADE' else '!')+'defined(LOD_FADE_CROSSFADE) && '+('' if wind else '!')+'defined(ENABLE_WIND)';pairs.append((condition,vi,fi))
                    text+=emitter.block(context,pairs,'#pragma multi_compile LOD_FADE_PERCENTAGE LOD_FADE_CROSSFADE\n#pragma multi_compile __ ENABLE_WIND\n')
                else:
                    vi,fi=emitter.pair(context,0,set(keys)|{'LIGHTPROBE_SH','UNITY_HDR_ON'});text+=emitter.block(context,[(None,vi,fi)])
                text+='}\n'
                if name=='speedtree':
                    shadow_features={k for r in context[2] if r['kind']=='program' and any(c['subshader_index']==0 and c['pass_index']==1 for c in r.get('consumers',[r])) for k in r['keywords']}&features;pairs=[]
                    for mode in ['SHADOWS_DEPTH','SHADOWS_CUBE']:
                        for lod in ['LOD_FADE_PERCENTAGE','LOD_FADE_CROSSFADE']:
                            for wind in [False,True]:
                                vi,fi=emitter.pair(context,1,(set(keys)&shadow_features)|{mode,lod}|({'ENABLE_WIND'} if wind else set()))
                                condition='defined('+mode+') && '+('' if lod=='LOD_FADE_CROSSFADE' else '!')+'defined(LOD_FADE_CROSSFADE) && '+('' if wind else '!')+'defined(ENABLE_WIND)';pairs.append((condition,vi,fi))
                    text+='Pass {Name "ShadowCaster" '+tags(passes[1]['m_State']['m_Tags']['tags'])+render_state(passes[1]['m_State'])+emitter.block(context,pairs,'#pragma multi_compile_shadowcaster\n#pragma multi_compile LOD_FADE_PERCENTAGE LOD_FADE_CROSSFADE\n#pragma multi_compile __ ENABLE_WIND\n')+'}\n'
                elif name not in ['cloud','ui-alpha','distortion']:
                    shadow_features={k for r in context[2] if r['kind']=='program' and r['pass_index']==1 for k in r['keywords']}&features;pairs=[]
                    for mode in ['SHADOWS_DEPTH','SHADOWS_CUBE']:
                        vi,fi=emitter.pair(context,1,(set(keys)&shadow_features)|{mode});pairs.append(('defined('+mode+')',vi,fi))
                    text+='Pass {Name "ShadowCaster" Tags {"LightMode"="ShadowCaster"}\n'+render_state(passes[1]['m_State'])+emitter.block(context,pairs,'#pragma multi_compile_shadowcaster\n')+'}\n'
                text+='}}\n';(sources/(resource+'.shader')).write_text(text);variants.append({'resource':resource,'keywords':list(keys)})
            families.append({'shader':form['m_Name'],'features':sorted(features),'variants':variants,'source_material_count':len(materials)})
        passes=reflection[0]['m_ParsedForm']['m_SubShaders'][0]['m_Passes'];text='// Private original reflection candidate; PC parity unverified.\nShader "Porting Lab/AndroidNativeDeferredReflections" {Properties {\n'+properties(reflection[0])+'\n}\nSubShader {\n'
        for pi,p in enumerate(passes):
            key_sets=sorted({tuple(r['keywords']) for r in reflection[2] if r['kind']=='program' and r['pass_index']==pi});pairs=[]
            for keys in key_sets:
                vi,fi=emitter.pair(reflection,pi,keys);condition=None if len(key_sets)==1 else ('defined(UNITY_HDR_ON)' if 'UNITY_HDR_ON' in keys else '!defined(UNITY_HDR_ON)');pairs.append((condition,vi,fi))
            text+='Pass {\n'+render_state(p['m_State'])+emitter.block(reflection,pairs,'#pragma multi_compile __ UNITY_HDR_ON\n' if len(key_sets)>1 else '')+'}\n'
        text+='}}\n';(sources/'AndroidNativeDeferredReflections.shader').write_text(text)
        write(sources/'AndroidNativeMaterialFamilies.json',{'families':families,'water_topology':topology,'water_geometry_approximation':topology=='original-vertices','scope':'Measured static material features, mono/noninstanced HDR deferred; cloud SH/soft-particle variants; original reflection candidate, no PC semantic/visual parity'})
        result.update(success=True,families=families,variant_count=sum(len(f['variants']) for f in families),source_sha256_by_file={p.name:sha(p) for p in sources.iterdir()})
    except Exception as e:result['first_failure']=str(e);raise
    finally:write(out/'receipt.json',result)
    print(json.dumps({'success':True,'variants':result['variant_count'],'evidence':str(out.relative_to(ROOT))}));return out
