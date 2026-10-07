"""Read-only, pinned shipped-program recovery; every derived output is private."""
from common import *
import base64, shutil, sys
import UnityPy
import lz4.block
from shader_segments import read_segments, selected_layout

PINS = {
    'unity': ('reference-repos/Abby1591__Unity_Shader_Decompiler', '1ce3a1c47609f8574e091b30e8425d528f2b457c'),
    'd3dasm': ('reference-repos/coconutbird__d3dasm', 'a292206a15daf0723d945a475c6254413eda8551'),
    'cfglib': ('napbat/cfglib', '6e57c166403e80e81a0f51e01aebf5ed47267784'),
    'hlsl': ('reference-repos/javelinlinV2__HLSLDecompiler', 'bc9b39dba5a3ae27e54ea6b3980bd1fac6f4061a'),
    'spirv': ('reference-repos/doitsujin__dxbc-spirv', 'c7f069701227dcb800a01bd93e42f8001b7543e7'),
}
ALIASES = {
    'compressedBlob':'m_CompressedBlob', 'compressedLengths':'m_CompressedLengths',
    'decompressedLengths':'m_DecompressedLengths', 'offsets':'m_Offsets',
    'name':'m_Name', 'val':'m_Value', 'culling':'m_Culling', 'zTest':'m_ZTest',
    'zWrite':'m_ZWrite', 'zClip':'m_ZClip', 'lighting':'m_Lighting', 'fogMode':'m_FogMode',
    'alphaToMask':'m_AlphaToMask', 'conservative':'m_Conservative',
    'offsetFactor':'m_OffsetFactor', 'offsetUnits':'m_OffsetUnits',
    'stencilRef':'m_StencilRef', 'stencilReadMask':'m_StencilReadMask',
    'stencilWriteMask':'m_StencilWriteMask', 'stencilOpFront':'m_StencilOpFront',
    'stencilOpBack':'m_StencilOpBack', 'rtSeparateBlend':'m_RtSeparateBlend',
    'srcBlend':'m_SourceBlend', 'destBlend':'m_DestinationBlend',
    'srcBlendAlpha':'m_SourceBlendAlpha', 'destBlendAlpha':'m_DestinationBlendAlpha',
    'blendOp':'m_BlendOp', 'blendOpAlpha':'m_BlendOpAlpha', 'colMask':'m_ColMask',
}
ALIASES.update({f'prog{x}':f'm_Prog{x}' for x in ['Vertex','Fragment','Geometry','Hull','Domain','RayTracing']})
ALIASES.update({f'rtBlend{i}':f'm_RtBlend{i}' for i in range(8)})

def normalize(value):
    """Schema aliases only; keep original fields, symbols and numerical values."""
    if isinstance(value, list): return [normalize(x) for x in value]
    if isinstance(value, float) and value.is_integer(): return int(value)
    if not isinstance(value, dict): return value
    result = {k:normalize(v) for k,v in value.items()}
    for old,new in ALIASES.items():
        if old in result and new not in result: result[new] = result[old]
    for key in ['m_NameIndices','tags']:
        if isinstance(result.get(key), list):
            pairs = result[key]
            if len({x[0] for x in pairs}) != len(pairs): raise RuntimeError('Duplicate shader metadata names')
            result[key] = dict(pairs)
    for i in range(4):
        if f'm_DefValue[{i}]' in result: result[f'm_DefValue_{i}_'] = result[f'm_DefValue[{i}]']
    if 'm_State' in result and not result.get('m_Name'): result['m_Name'] = result['m_State'].get('m_Name','')
    return result

def recover(target='lab'):
    specs = {
        'lab':(-15541403510422607,'Hopoo Games/FX/Cloud Intersection Remap','FORWARD',['DIRECTIONAL','LIGHTPROBE_SH','TRIPLANAR'],64),
        'standard':(-197252232775272061,'Hopoo Games/Deferred/Standard','DEFERRED',['DITHER','LIGHTPROBE_SH','LIMBREMOVAL'],3024),
    }
    if target not in specs: raise RuntimeError('Shader recovery target must be lab or standard')
    identity,shader_name,pass_name,keywords,expected_programs = specs[target]
    out = WORK/'experiments/shader-recovery'/now(); out.mkdir(parents=True)
    receipt = {'success':False, 'read_only':True, 'semantic_equivalence_proven':False,
               'Android_shader_acceptance':False, 'PC_draw_validation_performed':False, 'commands':[]}
    write(WORK/'shader-recovery-current.json', {'path':str(out.relative_to(ROOT))})
    source = None; source_hash = None
    try:
        base = game(); inventory = read(WORK/'inventory/files.json')
        current = {str(p.relative_to(base)):(p.stat().st_size,p.stat().st_mtime_ns) for p in base.rglob('*') if p.is_file()}
        prior = {x['path']:(x['size'],x['mtime_ns']) for x in inventory['files']}
        if current!=prior or read(WORK/'config/accepted-input.json')['input_id']!=inventory['input_id']:
            raise RuntimeError('Shader input drift; review inventory and explicitly accept before recovery')
        free = shutil.disk_usage(ROOT).free
        minimum = (100 if target=='lab' else 1024)*1024**2
        if free<minimum: raise RuntimeError('Insufficient headroom for this fixed shader analysis')
        write(out/'preflight.json', {'success':True,'input_id':inventory['input_id'],'host_free_bytes':free,
                                    'scope':'Read-only, existing-tool shader analysis only; Unity builds retain their 10 GiB guard'})
        tools = {}
        for name,(relative,pin) in PINS.items():
            path = WORK/relative
            if run(['git','-C',path,'rev-parse','HEAD']).stdout.decode().strip() != pin:
                raise RuntimeError('Shader analysis tool pin changed: '+name)
            if run(['git','-C',path,'diff','HEAD','--']).stdout:
                raise RuntimeError('Shader analysis tool has tracked changes: '+name)
            tools[name] = path
        write(out/'tool-pins.json', PINS)
        def command(label, args, allow_failure=False, **kwargs):
            p = run(args, check=False, timeout=300, **kwargs)
            (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
            receipt['commands'].append({'label':label,'args':[str(x) for x in args],'exit_code':p.returncode})
            if p.returncode and not allow_failure: raise RuntimeError('Shader recovery failed at '+label+'; private evidence retained')
            return p
        relative = 'Risk of Rain 2_Data/StreamingAssets/aa/StandaloneWindows64/ror2-base-shaders_shader_assets_all_31e119f89c9f8d77f8f8199c00774974.bundle'
        source = game()/relative; source_hash = sha(source)
        expected = next(x['sha256'] for x in read(WORK/'inventory/files.json')['files'] if x['path']==relative)
        if source_hash != expected: raise RuntimeError('Shader input drift; review and explicitly accept before recovery')
        objects = [x for x in UnityPy.load(str(source)).objects if x.type.name=='Shader' and x.path_id==identity]
        if len(objects)!=1: raise RuntimeError('Original shader identity is ambiguous')
        obj = objects[0]; tree = obj.read_typetree()
        if tree['m_ParsedForm']['m_Name']!=shader_name: raise RuntimeError('Original shader name changed')
        blob = bytes(tree['compressedBlob']); tree['compressedBlob'] = base64.b64encode(blob).decode()
        write(out/'original-tree-base64.json', tree)
        adapted = normalize(tree); adapted['m_Name'] = tree['m_ParsedForm']['m_Name']; write(out/'tool-input.json', adapted)
        raw,records,programs = read_segments(tree,blob)
        if len(programs)!=expected_programs: raise RuntimeError('Native executable program coverage changed')
        write(out/'native-records.json',records)
        selected = []
        for gpu_type in [15,17]:
            matches = [(r['index'],programs[r['index']]) for r in records if r['kind']=='program' and
                       r['gpu_type']==gpu_type and r['keywords']==keywords and r['pass']==pass_name]
            if len(matches)!=1: raise RuntimeError('Original shader variant is ambiguous')
            i,data = matches[0]; program_file = out/f'unity-{i}.dxbc'; program_file.write_bytes(data)
            write(out/f'unity-{i}-layout.json',selected_layout(tree,raw,records[i]))
            selected.append({'unity_subprogram':i,'gpu_type':gpu_type,'keywords':keywords,'sha256':sha(program_file),
                             'parameter_index':records[i]['parameter_index']})
        receipt.update(shader=adapted['m_Name'],source_bundle=relative,source_sha256=source_hash,programs=selected,
                       native_executable_programs=len(programs),native_record_count=len(records),
                       selection_scope='Measured material keywords, non-stereo/non-instanced pair; live PC draw not observed')
        command('unity-stage0',[sys.executable,tools['unity']/'Extract.py',out/'tool-input.json','--out-dir',out/'unity-stage0','--flat'])
        first_size=tree['compressedLengths'][0][0]; first_raw_size=tree['decompressedLengths'][0][0]
        original_first = lz4.block.decompress(blob[:first_size],uncompressed_size=first_raw_size)
        stage_blob = out/'unity-stage0/blob.bin'
        if stage_blob.read_bytes()!=original_first: raise RuntimeError('Stage0 changed the native first segment')
        (out/'unity-stage0/original-segment-0.bin').write_bytes(original_first)
        stage_blob.write_bytes(raw)
        receipt['segment_rebasing_record_bytes_unchanged'] = True
        dll = tools['unity']/'Shader Decompiler/bin/Release/net10.0/Shader Decompiler.dll'
        receipt['unity_tool_binary_sha256'] = sha(dll)
        options = ['--no-surface-shaders']+(['--no-fuse-temps'] if target=='standard' else [])
        named = command('unity-decompile',['dotnet',dll,out/'unity-stage0','--out-root',out/'unity-recovered']+options)
        functions = sum('Stage 2: collected ' in line for line in named.stdout.decode(errors='replace').splitlines())
        if functions!=expected_programs: raise RuntimeError('Unity decompiler did not retain all native executable functions')
        receipt['named_executable_functions'] = functions
        shaders = list((out/'unity-recovered').glob('*.shader'))
        if len(shaders)!=1 or shaders[0].stat().st_size<1000:
            raise RuntimeError('Unity decompiler did not emit the full named shader')
        receipt['named_shader_sha256'] = sha(shaders[0])
        wine = Path('/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine')
        prefix = WORK/'toolchains/crossover-bottles'
        if not (prefix/'shader-recovery/cxbottle.conf').is_file(): raise RuntimeError('Isolated shader-analysis bottle is missing')
        env = os.environ.copy(); env['CX_BOTTLE_PATH'] = str(prefix)
        hlsl = out/'hlsl-decompiler'; hlsl.mkdir()
        for name in ['cmd_Decompiler.exe','d3dcompiler_46.dll']:
            shutil.copy2(tools['hlsl']/'RenderDoc_DXBC2HLSL_shader_view_files/v2'/name,hlsl/name)
        receipt['tool_binary_hashes'] = {str(p.relative_to(WORK)):sha(p) for p in [dll,
            tools['d3dasm']/'target/release/d3dasm',hlsl/'cmd_Decompiler.exe',hlsl/'d3dcompiler_46.dll',
            tools['spirv']/'builddir/tools/dxbc_disasm',tools['spirv']/'builddir/tools/dxbc_compiler']}
        for selected_program in selected:
            i = selected_program['unity_subprogram']; f = out/f'unity-{i}.dxbc'; exe = tools['d3dasm']/'target/release/d3dasm'
            for fmt in ['hlsl','d3dasm']:
                command(f'd3dasm-{i}-{fmt}',[exe,f,'--emit',fmt,'--output',out/f'unity-{i}.{fmt}'])
            if 'not decompiled' in (out/f'unity-{i}.hlsl').read_text(): raise RuntimeError('d3dasm rejected executable instructions')
            rebuilt = out/f'unity-{i}.roundtrip.dxbc'
            command(f'd3dasm-{i}-assemble',[exe,out/f'unity-{i}.d3dasm','--assemble','--output',rebuilt])
            if sha(rebuilt)!=sha(f): raise RuntimeError('d3dasm roundtrip changed original bytecode')
            shutil.copy2(f,hlsl/f.name)
            command(f'hlsl-{i}-emit',[wine,'--bottle','shader-recovery','--no-gui','--workdir',hlsl,hlsl/'cmd_Decompiler.exe','-D',hlsl/f.name],env=env)
            emitted = hlsl/f'unity-{i}.hlsl'
            if not emitted.is_file(): raise RuntimeError('HLSLDecompiler did not emit its independent output')
            # Validation can fail independently of extraction/IR. Preserve the
            # counterexample and still finish other tools on the same bytecode.
            compiled = command(f'hlsl-{i}-validate',[wine,'--bottle','shader-recovery','--no-gui','--workdir',hlsl,hlsl/'cmd_Decompiler.exe','-D','-V',hlsl/f.name],env=env,allow_failure=True)
            validated = compiled.returncode==0 and b'Decompiler validation pass succeeded' in compiled.stdout+compiled.stderr
            if not validated:
                receipt.setdefault('validation_failures',[]).append({'program':i,'evidence':f'hlsl-{i}-validate.stdout'})
            spirv = tools['spirv']/'builddir/tools'; spv = out/f'unity-{i}.spv'
            command(f'spirv-{i}-disasm',[spirv/'dxbc_disasm',f])
            command(f'spirv-{i}-ir',[spirv/'dxbc_compiler',f,'--ir-asm','--convert-only'])
            command(f'spirv-{i}-lowered',[spirv/'dxbc_compiler',f,'--ir-asm','--spv',spv])
            if spv.read_bytes()[:4]!=b'\x03\x02\x23\x07': raise RuntimeError('SPIR-V output header missing')
            selected_program.update(dxbc_roundtrip_identical=True,hlsl_recompilation_passed=validated,
                output_hashes={str(p.relative_to(out)):sha(p) for p in [out/f'unity-{i}.hlsl',out/f'unity-{i}.d3dasm',
                                                     hlsl/f'unity-{i}.hlsl',spv]})
        if sha(source)!=source_hash: raise RuntimeError('Original shader bundle changed during analysis')
        receipt['analysis_complete'] = True
        receipt['success'] = not receipt.get('validation_failures')
        if not receipt['success']: receipt['first_failure'] = 'Independent HLSL recompilation failed; original programs and other tool outputs retained'
        receipt['scope'] = 'Extraction/tool execution and lossless DXBC roundtrip only; generated named ShaderLab has known reconstruction errors'
    except Exception as error:
        receipt['first_failure'] = str(error)
        raise
    finally:
        receipt['original_bundle_unchanged'] = source is not None and source.is_file() and source_hash is not None and sha(source)==source_hash
        write(out/'receipt.json', receipt)
    print(json.dumps({'success':receipt['success'],'evidence':str(out.relative_to(ROOT)),
                      'scope':receipt['scope'],'semantic_equivalence_proven':False}))
    if not receipt['success']: raise RuntimeError(receipt['first_failure'])
