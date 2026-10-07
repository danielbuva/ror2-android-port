"""Read the shipped segment table, without interpreting shader math."""
import hashlib, struct
import lz4.block
from UnityPy.export.ShaderConverter import ShaderSubProgram
from UnityPy.streams import EndianBinaryReader


def variants(tree):
    result = {}
    keywords = tree['m_ParsedForm']['m_KeywordNames']
    for subshader_index,subshader in enumerate(tree['m_ParsedForm']['m_SubShaders']):
        for pass_index,p in enumerate(subshader['m_Passes']):
            for stage in ['progVertex', 'progFragment']:
                programs = p[stage]['m_PlayerSubPrograms'][3]
                parameters = p[stage]['m_ParameterBlobIndices'][3]
                if len(programs)!=len(parameters): raise RuntimeError('Shader variant/parameter lengths differ')
                for program,parameter in zip(programs,parameters):
                    index = program['m_BlobIndex']
                    value = {'index':index,'parameter_index':parameter,'gpu_type':program['m_GpuProgramType'],
                             'keywords':sorted(keywords[k] for k in program['m_KeywordIndices']),
                             'pass':p['m_State']['m_Name'],'stage':stage,
                             'subshader_index':subshader_index,'pass_index':pass_index}
                    if index in result and result[index]!=value:
                        raise RuntimeError('Original shader program identity has conflicting consumers')
                    result[index] = value
    return result


def read_segments(tree, blob):
    if tree['platforms']!=[4]: raise RuntimeError('Recovery requires the measured D3D11 platform')
    if not (len(tree['offsets'][0])==len(tree['compressedLengths'][0])==len(tree['decompressedLengths'][0])>0):
        raise RuntimeError('Shader compressed segment tables disagree')
    segments = []
    for offset,size,raw_size in zip(tree['offsets'][0],tree['compressedLengths'][0],tree['decompressedLengths'][0]):
        if offset<0 or size<=0 or offset+size>len(blob): raise RuntimeError('Shader compressed segment extent invalid')
        data = lz4.block.decompress(blob[offset:offset+size],uncompressed_size=raw_size)
        if len(data)!=raw_size: raise RuntimeError('Shader raw segment extent invalid')
        segments.append(data)
    count = struct.unpack_from('<I',segments[0])[0]
    table_size = 4+count*12
    if table_size>len(segments[0]): raise RuntimeError('Shader segment index exceeds table')
    entries = [struct.unpack_from('<iii',segments[0],4+i*12) for i in range(count)]
    declarations = variants(tree)
    parameter_indices = {x['parameter_index'] for x in declarations.values()}
    if set(declarations)&parameter_indices or set(declarations)|parameter_indices!=set(range(count)):
        raise RuntimeError('Original shader declarations do not account for the entire segment table')
    records = []; programs = {}
    for index,(offset,length,segment) in enumerate(entries):
        if segment<0 or segment>=len(segments) or offset<0 or length<=0 or offset+length>len(segments[segment]):
            raise RuntimeError('Shader record extends outside its declared segment')
        data = segments[segment][offset:offset+length]
        record = {'index':index,'segment':segment,'offset':offset,'length':length,
                  'sha256':hashlib.sha256(data).hexdigest(),'kind':'parameters' if index in parameter_indices else 'program'}
        if index in declarations:
            program = ShaderSubProgram(EndianBinaryReader(data,endian='<'))
            declaration = declarations[index]
            if program.m_Version!=202012090 or int(program.m_ProgramType)!=declaration['gpu_type'] or sorted(program.m_Keywords)!=declaration['keywords']:
                raise RuntimeError('Shader native program and serialized variant disagree')
            at = program.m_ProgramCode.find(b'DXBC')
            if at<0: raise RuntimeError('Declared D3D11 program has no DXBC')
            dxbc = program.m_ProgramCode[at:]
            size,chunks = struct.unpack_from('<II',dxbc,24)
            if size!=len(dxbc) or size<32+chunks*4: raise RuntimeError('Shader DXBC extent invalid')
            chunk_offsets = struct.unpack_from('<'+'I'*chunks,dxbc,32)
            if not all(x>=32+chunks*4 and x+8<=size and x+8+struct.unpack_from('<I',dxbc,x+4)[0]<=size for x in chunk_offsets):
                raise RuntimeError('Shader DXBC chunk table invalid')
            record.update(declaration,dxbc_sha256=hashlib.sha256(dxbc).hexdigest())
            programs[index] = dxbc
        records.append(record)
    if len(segments)==1:
        flattened = segments[0]
    else:
        if len(segments[0])!=table_size: raise RuntimeError('Multi-segment normalization expects a table-only first segment')
        starts = {}; cursor = table_size
        for segment in range(1,len(segments)):
            starts[segment] = cursor; cursor+=len(segments[segment])
        flattened = struct.pack('<I',count)+b''.join(struct.pack('<iii',starts[segment]+offset,length,0) for offset,length,segment in entries)+b''.join(segments[1:])
        for index,(offset,length,segment) in enumerate(entries):
            changed = struct.unpack_from('<iii',flattened,4+12*index)
            if flattened[changed[0]:changed[0]+length]!=segments[segment][offset:offset+length]:
                raise RuntimeError('Shader normalization changed native record bytes')
    return flattened,records,programs


def parameter_layout(data):
    """Measured 2021.3 parameter records; reject unknown structures/layouts."""
    cursor = 0
    def integer():
        nonlocal cursor
        if cursor+4>len(data): raise RuntimeError('Shader parameter read exceeds native record')
        value = struct.unpack_from('<i',data,cursor)[0]; cursor+=4
        return value
    def count():
        value = integer()
        if value<0 or value>4096: raise RuntimeError('Shader parameter count invalid')
        return value
    def name():
        nonlocal cursor
        size = count()
        if cursor+size>len(data): raise RuntimeError('Shader parameter name exceeds native record')
        value = data[cursor:cursor+size].decode('utf-8'); cursor=(cursor+size+3)//4*4
        return value
    if integer()!=202012090: raise RuntimeError('Shader parameter version changed')
    buffers = []
    for _ in range(count()):
        buffer_name,size = name(),integer(); parameters = []
        for _ in range(count()):
            variable = name(); kind,rows,columns,matrix,array_size,offset = [integer() for _ in range(6)]
            if rows<1 or rows>4 or columns<1 or columns>4 or matrix not in [0,1] or array_size<0 or offset<0 or offset>=size:
                raise RuntimeError('Unsupported shader constant shape/offset')
            parameters.append({'name':variable,'type':kind,'rows':rows,'columns':columns,'matrix':bool(matrix),
                               'array_size':array_size,'offset':offset})
        if count()!=0: raise RuntimeError('Structured shader constants need separately measured decoding')
        buffers.append({'name':buffer_name,'size':size,'variables':parameters})
    bindings = []
    for _ in range(count()):
        resource_name = name(); kind,slot,extra = integer(),integer(),integer()
        if kind not in [0,1] or slot<0 or (kind==1 and extra!=0):
            raise RuntimeError(f'Unsupported shader resource binding: {resource_name!r} ({kind},{slot},{extra}) at {cursor}')
        binding = {'name':resource_name,'kind':kind,'slot':slot,'extra':extra}
        if kind==0: binding['native_texture_descriptor'] = integer()
        bindings.append(binding)
    if cursor!=len(data): raise RuntimeError('Unclassified trailing shader parameter data')
    return {'buffers':buffers,'bindings':bindings}


def selected_layout(tree, flattened, record):
    index = record['parameter_index']; offset,length,segment = struct.unpack_from('<iii',flattened,4+12*index)
    if segment!=0: raise RuntimeError('Parameter layout requires normalized segment offsets')
    native = parameter_layout(flattened[offset:offset+length])
    if 'subshader_index' in record and 'pass_index' in record:
        p=tree['m_ParsedForm']['m_SubShaders'][record['subshader_index']]['m_Passes'][record['pass_index']]
        if p['m_State']['m_Name']!=record['pass']:raise RuntimeError('Shader pass identity differs from native record')
    else:
        matches=[p for s in tree['m_ParsedForm']['m_SubShaders'] for p in s['m_Passes'] if p['m_State']['m_Name']==record['pass']]
        if len(matches)!=1:raise RuntimeError('Shader pass name is ambiguous; native ordinal required')
        p=matches[0]
    names = {i:n for n,i in p['m_NameIndices']}; common = p[record['stage']]['m_CommonParameters']
    buffers = {b['name']:b for b in native['buffers'] if b['name']}
    bindings = {b['name']:b['slot'] for b in native['bindings'] if b['kind']==1}
    for b in common['m_ConstantBufferBindings']:
        name = names[b['m_NameIndex']]; slot = b['m_Index']
        if name in bindings and bindings[name]!=slot: raise RuntimeError('Native/common shader binding disagreement')
        bindings[name] = slot
    for b in common['m_ConstantBuffers']:
        name = names[b['m_NameIndex']]
        if name not in buffers: raise RuntimeError('Common constant buffer absent from native parameter record')
        buffer = buffers[name]
        if b['m_Size']!=buffer['size'] and not b.get('m_IsPartialCB'):
            raise RuntimeError('Native/common shader buffer size disagreement')
        additions = [{'name':names[v['m_NameIndex']],'type':v['m_Type'],'offset':v['m_Index'],
                      'rows':1,'columns':v['m_Dim'],'matrix':False,'array_size':v['m_ArraySize']} for v in b['m_VectorParams']]
        for v in b['m_MatrixParams']:
            if v['m_RowCount']!=4: raise RuntimeError('Common non-square matrix layout is unmeasured')
            additions.append({'name':names[v['m_NameIndex']],'type':v['m_Type'],'offset':v['m_Index'],
                              'rows':4,'columns':4,'matrix':True,'array_size':v['m_ArraySize']})
        for variable in additions:
            span=(64 if variable['matrix'] else variable['columns']*4)*max(1,variable['array_size'])
            if variable['offset']>=buffer['size'] and b.get('m_IsPartialCB'):
                native.setdefault('omitted_common_variables',[]).append(variable)
                continue
            if variable['offset']+span>buffer['size']:raise RuntimeError('Common shader variable exceeds native buffer')
            previous = next((v for v in buffer['variables'] if v['name']==variable['name']),None)
            if previous and previous!=variable: raise RuntimeError('Native/common constant parameter disagreement')
            if not previous: buffer['variables'].append(variable)
    for name,buffer in buffers.items():
        if name not in bindings: raise RuntimeError('Native shader constant buffer has no measured slot')
        buffer['slot'] = bindings[name]
    textures = [{'name':names[t['m_NameIndex']],'slot':t['m_Index'],'sampler':t['m_SamplerIndex'],
                 'dimension':t['m_Dim'],'multisampled':t['m_MultiSampled']} for t in common['m_TextureParams']]
    for binding in native['bindings']:
        if binding['kind']==0:
            known = next((t for t in textures if t['name']==binding['name']),None)
            if known and (known['slot']!=binding['slot'] or known['sampler']!=binding['extra']):
                raise RuntimeError('Native/common shader texture binding disagreement')
            if not known:
                textures.append({'name':binding['name'],'slot':binding['slot'],'sampler':binding['extra'],
                                 'native_texture_descriptor':binding['native_texture_descriptor'],
                                 'dimension':None,'scope':'Per-variant binding absent from common layout; resolve dimension from native DXBC declaration'})
    return {'parameter_index':index,'stage':record['stage'],'pass':record['pass'],
            'buffers':sorted(buffers.values(),key=lambda b:b['slot']),'textures':textures,
            'omitted_common_variables':native.get('omitted_common_variables',[])}
