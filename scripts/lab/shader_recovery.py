"""Read-only, pinned Cloud Intersection recovery; every derived output is private."""
from common import *
import base64, shutil, struct, sys
import UnityPy
import lz4.block
from UnityPy.export.ShaderConverter import ShaderProgram
from UnityPy.streams import EndianBinaryReader

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

def recover():
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
        if free<100*1024**2: raise RuntimeError('Less than 100 MiB for this fixed two-program analysis')
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
        def command(label, args, **kwargs):
            p = run(args, check=False, timeout=180, **kwargs)
            (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
            receipt['commands'].append({'label':label,'args':[str(x) for x in args],'exit_code':p.returncode})
            if p.returncode: raise RuntimeError('Shader recovery failed at '+label+'; private evidence retained')
            return p
        relative = 'Risk of Rain 2_Data/StreamingAssets/aa/StandaloneWindows64/ror2-base-shaders_shader_assets_all_31e119f89c9f8d77f8f8199c00774974.bundle'
        source = game()/relative; source_hash = sha(source)
        expected = next(x['sha256'] for x in read(WORK/'inventory/files.json')['files'] if x['path']==relative)
        if source_hash != expected: raise RuntimeError('Shader input drift; review and explicitly accept before recovery')
        objects = [x for x in UnityPy.load(str(source)).objects if x.type.name=='Shader' and x.path_id==-15541403510422607]
        if len(objects)!=1: raise RuntimeError('Original Cloud Intersection identity is ambiguous')
        obj = objects[0]; tree = obj.read_typetree()
        if tree['m_ParsedForm']['m_Name']!='Hopoo Games/FX/Cloud Intersection Remap': raise RuntimeError('Original shader name changed')
        if tree['platforms']!=[4] or len(tree['offsets'][0])!=1 or tree['offsets'][0][0]!=0:
            raise RuntimeError('This action requires the measured single-segment D3D11 shader')
        blob = bytes(tree['compressedBlob']); tree['compressedBlob'] = base64.b64encode(blob).decode()
        if len(blob)!=tree['compressedLengths'][0][0]: raise RuntimeError('Original compressed segment extent changed')
        write(out/'original-tree-base64.json', tree)
        adapted = normalize(tree); adapted['m_Name'] = tree['m_ParsedForm']['m_Name']; write(out/'tool-input.json', adapted)
        raw = lz4.block.decompress(blob, uncompressed_size=tree['decompressedLengths'][0][0])
        if len(raw)!=tree['decompressedLengths'][0][0]: raise RuntimeError('Decompressed segment extent changed')
        program = ShaderProgram(EndianBinaryReader(raw,endian='<'), obj.version)
        keywords = ['DIRECTIONAL','LIGHTPROBE_SH','TRIPLANAR']; selected = []
        for gpu_type in [15,17]:
            matches = []
            for i,p in enumerate(program.m_SubPrograms):
                if p.m_Version!=202012090 or int(p.m_ProgramType)!=gpu_type or sorted(p.m_Keywords)!=keywords: continue
                at = p.m_ProgramCode.find(b'DXBC')
                if at<0: continue
                data = p.m_ProgramCode[at:]; size,chunks = struct.unpack_from('<II',data,24)
                if size!=len(data) or size<32+4*chunks: raise RuntimeError('Invalid original DXBC extent')
                offsets = struct.unpack_from('<'+'I'*chunks,data,32)
                if not all(x>=32+4*chunks and x+8<=size and x+8+struct.unpack_from('<I',data,x+4)[0]<=size for x in offsets):
                    raise RuntimeError('Invalid original DXBC chunk table')
                matches.append((i,data))
            if len(matches)!=1: raise RuntimeError('Original shader variant is ambiguous')
            i,data = matches[0]; target = out/f'unity-{i}.dxbc'; target.write_bytes(data)
            selected.append({'unity_subprogram':i,'gpu_type':gpu_type,'keywords':keywords,'sha256':sha(target)})
        receipt.update(shader=adapted['m_Name'],source_bundle=relative,source_sha256=source_hash,programs=selected,
                       selection_scope='Measured non-stereo/non-instanced TRIPLANAR pair; live PC draw not observed')
        command('unity-stage0',[sys.executable,tools['unity']/'Extract.py',out/'tool-input.json','--out-dir',out/'unity-stage0','--flat'])
        if (out/'unity-stage0/blob.bin').read_bytes()!=raw: raise RuntimeError('Stage0 changed the native shader blob')
        dll = tools['unity']/'Shader Decompiler/bin/Release/net10.0/Shader Decompiler.dll'
        receipt['unity_tool_binary_sha256'] = sha(dll)
        named = command('unity-decompile',['dotnet',dll,out/'unity-stage0','--out-root',out/'unity-recovered','--no-surface-shaders','--dump-stages','--dump-keywords'])
        functions = sum('Stage 2: collected ' in line for line in named.stdout.decode(errors='replace').splitlines())
        if functions!=64: raise RuntimeError('Unity decompiler did not retain all 64 native executable functions')
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
            compiled = command(f'hlsl-{i}',[wine,'--bottle','shader-recovery','--no-gui','--workdir',hlsl,hlsl/'cmd_Decompiler.exe','-D','-V',hlsl/f.name],env=env)
            if b'Decompiler validation pass succeeded' not in compiled.stdout+compiled.stderr or not (hlsl/f'unity-{i}.hlsl').is_file():
                raise RuntimeError('HLSLDecompiler did not confirm its HLSL recompilation')
            spirv = tools['spirv']/'builddir/tools'; spv = out/f'unity-{i}.spv'
            command(f'spirv-{i}-disasm',[spirv/'dxbc_disasm',f])
            command(f'spirv-{i}-ir',[spirv/'dxbc_compiler',f,'--ir-asm','--convert-only'])
            command(f'spirv-{i}-lowered',[spirv/'dxbc_compiler',f,'--ir-asm','--spv',spv])
            if spv.read_bytes()[:4]!=b'\x03\x02\x23\x07': raise RuntimeError('SPIR-V output header missing')
            selected_program.update(dxbc_roundtrip_identical=True,hlsl_recompilation_passed=True,
                output_hashes={str(p.relative_to(out)):sha(p) for p in [out/f'unity-{i}.hlsl',out/f'unity-{i}.d3dasm',
                                                     hlsl/f'unity-{i}.hlsl',spv]})
        receipt['success'] = True
        receipt['scope'] = 'Extraction/tool execution and lossless DXBC roundtrip only; generated named ShaderLab has known reconstruction errors'
    except Exception as error:
        receipt['first_failure'] = str(error)
        raise
    finally:
        receipt['original_bundle_unchanged'] = source is not None and source.is_file() and source_hash is not None and sha(source)==source_hash
        write(out/'receipt.json', receipt)
    print(json.dumps({'success':receipt['success'],'evidence':str(out.relative_to(ROOT)),
                      'scope':receipt['scope'],'semantic_equivalence_proven':False}))
