"""Lift measured native tessellation I/O; generated instructions stay private."""
from common import *
from shader_source import bind_hlsl
from shader_segments import selected_layout
from shader_programs import NativePrograms,structure,call
import re


def hull_source(assembly):
    """Straight-line fork/join lowering, rejecting unmeasured instructions."""
    required=['profile=hs_5_0','dcl_inputControlPointCount 3','dcl_outputControlPointCount 3',
              'dcl_tessDomain tri','dcl_tessPartitioning fractional_odd','dcl_tessOutputPrimitive triangle_cw']
    if any(x not in assembly for x in required) or 'hs_control_point_phase' in assembly:
        raise RuntimeError('Unmeasured native hull topology/control point phase')
    buffers=re.findall(r'dcl_constantbuffer cb(\d+)\[(\d+)\]',assembly)
    header=''.join(f'cbuffer cb{s}_buffer : register(b{s}) {{float4 cb{s}[{n}];}}\n' for s,n in buffers)
    body=[];ops=[];phase=False;registers=set();outputs=set()
    def operand(value,lanes):
        if value.startswith('-'):return '-('+operand(value[1:],lanes)+')'
        if value.startswith('l('):
            numbers=value[2:-1].split(',')
            if len(numbers)==1:return numbers[0]
            if len(numbers)!=4:raise RuntimeError('Unmeasured hull literal width')
            return 'float'+str(len(lanes))+'('+','.join(numbers[k] for k in lanes)+')'
        match=re.fullmatch(r'(cb\d+\[\d+\]|r\d+|vicp[012]\[0\]|vpc[012])\.([xyzw]+)',value)
        if not match:raise RuntimeError('Unmeasured hull operand: '+value)
        base,swizzle=match.groups()
        if base.startswith('vicp'):base='cp'+base[4]
        if base.startswith('vpc'):base='e'+base[3]
        if base.startswith('r'):registers.add(base)
        if len(swizzle) not in [1,4]:raise RuntimeError('Unmeasured hull operand swizzle')
        return base+'.'+''.join(swizzle[k] if len(swizzle)==4 else swizzle[0] for k in lanes)
    for line in assembly.splitlines():
        line=line.strip()
        if line in ['hs_fork_phase','hs_join_phase']:phase=True;continue
        if not phase or not line or line.startswith('dcl_') or line in ['ret','.end']:continue
        fields=line.split();op,dest,args=fields[0],fields[1],fields[2:]
        match=re.fullmatch(r'(r\d+|o[0-3]):([xyzw]+)',dest)
        if not match:raise RuntimeError('Unmeasured hull destination: '+dest)
        base,mask=match.groups();lanes=['xyzw'.index(x) for x in mask]
        if base.startswith('o'):outputs.add(base);base='e'+base[1:]
        else:registers.add(base)
        expected={'dp3':2,'sqrt':1,'max':2,'mad':3,'mul':2,'add':2,'div':2}
        if op not in expected or len(args)!=expected[op]:raise RuntimeError('Unmeasured hull opcode: '+op)
        if op=='dp3':expression='dot('+','.join(operand(a,[0,1,2]) for a in args)+')'
        elif op in ['sqrt','max','mad']:expression=op+'('+','.join(operand(a,lanes) for a in args)+')'
        else:expression={'mul':' * ','add':' + ','div':' / '}[op].join('('+operand(a,lanes)+')' for a in args)
        body.append(base+'.'+mask+' = '+expression+';');ops.append(op)
    if outputs!={'o0','o1','o2','o3'} or not ops:raise RuntimeError('Native triangle factors incomplete')
    params=['float4 cp'+str(i)+' : CP'+str(i) for i in range(3)]+['out precise float1 out'+str(i)+' : FACTOR'+str(i) for i in range(4)]
    locals=sorted(registers)+['e'+str(i) for i in range(4)]
    text=header+'void main('+', '.join(params)+') {\nprecise float4 '+','.join(x+'=0' for x in locals)+';\n'+'\n'.join(body)+'\n'+''.join('out'+str(i)+'=e'+str(i)+'.x;\n' for i in range(4))+'}\n'
    return text,{'operations':len(ops),'opcodes':ops,'implicit_control_point_passthrough':True}


def domain_source(source):
    """Flatten the declared control-point patch without changing expressions."""
    control=re.search(r'struct DsControlPoint\s*\{(.*?)\};',source,re.S)
    fields=re.findall(r'float4 (\w+)\s*:\s*(\w+)\s*;',control[1] if control else '')
    signature=re.search(r'void main\((.*?)\)\s*(?=\{)',source,re.S)
    if not signature or not fields or len(fields)!=4:raise RuntimeError('Unmeasured native domain declaration')
    patch=re.search(r'DsPatch (\w+), const OutputPatch<DsControlPoint, 3> (\w+), ',signature[1])
    bary=re.match(r'float3 (\w+) : SV_DomainLocation, ',signature[1])
    if not patch or not bary:raise RuntimeError('Unmeasured native domain patch')
    body=source[source.index('{',signature.end()):]
    if re.search(r'\b'+patch[1]+r'\b',body):raise RuntimeError('Consumed native patch constants need separate recovery')
    parameters=[];mapping={}
    for i in range(3):
        for field,semantic in fields:
            name='cp'+str(i)+'_'+field;parameters.append('float4 '+name+' : CP'+str(i)+'_'+semantic)
            for identifier in [patch[2],'vertices']:
                old=identifier+'['+str(i)+'].'+field;body=body.replace(old,name);mapping[old]=name
    if re.search(r'\b(vertices|'+patch[2]+r')\[',body):raise RuntimeError('Unresolved domain control-point reference')
    params=signature[1].replace(patch[0],'')+', '+', '.join(parameters)
    header=source[:control.start()]
    return header+'void main('+params+')\n'+body,{'fields':fields,'identifier_mapping':mapping,'body_expressions_unchanged':True}


class TessellationPrograms(NativePrograms):
    def bound(self,context,index):
        stage=context[2][index]['stage']
        if stage not in ['progHull','progDomain']:return super().bound(context,index)
        key=(context[0]['m_ParsedForm']['m_Name'],index)
        if key in self.cache:return self.cache[key]
        tree,raw,records,programs,_=context;stem='program-'+digest(key[0])[:12]+'-'+str(index)
        original=self.out/(stem+'.dxbc');original.write_bytes(programs[index]);asm=self.out/(stem+'.d3dasm');rebuilt=self.out/(stem+'.roundtrip.dxbc');hlsl=self.out/(stem+'.hlsl')
        run([self.exe,original,'--emit','d3dasm','--output',asm]);run([self.exe,asm,'--assemble','--output',rebuilt])
        if sha(original)!=sha(rebuilt):raise RuntimeError('Native tessellation roundtrip changed')
        if stage=='progHull':source,correction=hull_source(asm.read_text())
        else:
            run([self.exe,original,'--emit','hlsl','--output',hlsl]);source,correction=domain_source(hlsl.read_text())
        fixed=self.out/(stem+'-lowered.hlsl');fixed.write_text(source)
        layout=selected_layout(tree,raw,records[index]);write(self.out/(stem+'-layout.json'),layout)
        function,params,declarations,_,reads=bind_hlsl(source,layout,'native_'+str(index));data=(function,params,declarations,layout['textures']);self.cache[key]=data
        self.result['programs'].append({'shader':key[0],'index':index,'dxbc_sha256':sha(original),'hlsl_sha256':sha(fixed),'layout':layout,'constant_bindings':reads,'origin':'Native ALU/compound-I-O lowering','correction':correction,'native_roundtrip_identical':True,'keywords':records[index]['keywords']})
        return data

    def quad(self,context,pass_index,keys):
        indices=[]
        for stage in ['progVertex','progHull','progDomain','progFragment']:
            found=[r['index'] for r in context[2] if r['kind']=='program' and r['stage']==stage and r['keywords']==sorted(keys) and any(c['subshader_index']==0 and c['pass_index']==pass_index for c in r.get('consumers',[r]))]
            if len(found)!=1:raise RuntimeError('Ambiguous native tessellation stage: '+stage+'/'+str(keys))
            indices.append(found[0])
        return indices

    def water_block(self,context,variants,original_vertices=False):
        inputs=set();controls=set();varyings=set();targets=set();entries=[]
        for condition,indices in variants:
            vi,hi,di,fi=indices;v,h,d,f=[self.bound(context,i) for i in indices]
            inputs.update(p['semantic'] for p in v[1] if not p['out']);controls.update(p['semantic'] for p in v[1] if p['out']);varyings.update(p['semantic'] for p in d[1] if p['out']);targets.update(p['semantic'] for p in f[1] if p['out'])
            if any(p['semantic'] not in varyings and p['semantic']!='SV_IsFrontFace0' for p in f[1] if not p['out']):raise RuntimeError('Native domain/pixel signature mismatch')
            if {p['semantic'] for p in h[1] if not p['out']}!={'CP0','CP1','CP2'}:raise RuntimeError('Unmeasured hull input shape')
            declaration={};textures={}
            for stage in [v,h,d,f]:
                for name,kind in stage[2].items():
                    if name in declaration and declaration[name]!=kind:raise RuntimeError('Native tessellation constant type mismatch')
                    declaration[name]=kind
                for texture in stage[3]:
                    name=texture['name']
                    if name in textures and any(textures[name][k]!=texture[k] for k in ['dimension','sampler_type']):raise RuntimeError('Native texture type mismatch')
                    textures[name]=texture
            source='#if '+condition+'\n'+'\n'.join(kind+' '+name+';' for name,kind in sorted(declaration.items()))+'\n'
            source+='\n'.join(('Texture2D' if t['dimension']==2 else 'TextureCube')+'<float4> '+t['name']+'; '+t['sampler_type']+' sampler'+t['name']+';' for t in textures.values() if t['name']!='unity_SpecCube0')+'\n'+'\n'.join(x[0] for x in [v,h,d,f])+'\n'
            source+='Control vert(AppData i) {Control o=(Control)0;'+call(vi,v[1])+'return o;}\n'
            source+='Factors factors(InputPatch<Control,3> p) {Factors o;native_'+str(hi)+'(p[0].INTERNALTESSPOS0,p[1].INTERNALTESSPOS0,p[2].INTERNALTESSPOS0,o.edge[0],o.edge[1],o.edge[2],o.inside);return o;}\n'
            source+='[domain("tri")][partitioning("fractional_odd")][outputtopology("triangle_cw")][outputcontrolpoints(3)][patchconstantfunc("factors")]\nControl hull(InputPatch<Control,3> p,uint id:SV_OutputControlPointID) {return p[id];}\n'
            args=[]
            for p in d[1]:
                if p['out']:arg='o.'+p['semantic']
                elif p['semantic']=='SV_DomainLocation':arg='bary'
                else:
                    match=re.fullmatch(r'CP([012])_(\w+)',p['semantic'])
                    if not match or match[2] not in controls:raise RuntimeError('Domain control signature mismatch')
                    arg='p['+match[1]+'].'+match[2]
                args.append(arg+('.'+'xyzw'[:p['columns']] if p['columns']<4 else ''))
            source+='[domain("tri")] Varyings domain(Factors factors,const OutputPatch<Control,3> p,float3 bary:SV_DomainLocation) {Varyings o=(Varyings)0;native_'+str(di)+'('+','.join(args)+');return o;}\n'
            if original_vertices:
                # Evaluate the recovered domain at one original control point.
                # This removes subdivision, not native material expressions.
                # It is an explicit topology approximation, never equivalence.
                begin=source.index('Control vert(')
                source=source[:begin]+'Varyings vert(AppData i) {Control cp=(Control)0;'+call(vi,v[1],outputs='cp')+'Varyings o=(Varyings)0;native_'+str(di)+'('+','.join(re.sub(r'p\[[012]\]', 'cp',a).replace('bary.xyz','float3(1,0,0)') for a in args)+');return o;}\n'
            face=',bool face:SV_IsFrontFace' if any(p['semantic']=='SV_IsFrontFace0' for p in f[1]) else ''
            source+='Targets frag(Varyings i'+face+') {Targets o=(Targets)0;'+call(fi,f[1])+'return o;}\n#endif\n';entries.append(source)
        directives='#pragma target 4.0\n#pragma vertex vert\n' if original_vertices else '#pragma target 4.6\n#pragma vertex vert\n#pragma hull hull\n#pragma domain domain\n'
        return 'HLSLPROGRAM\n'+directives+'#pragma fragment frag\n#pragma multi_compile __ LIGHTPROBE_SH\n#pragma multi_compile __ SHADOWS_SCREEN\n#pragma multi_compile __ FOG_LINEAR FOG_EXP\n#include "UnityCG.cginc"\n'+structure('AppData',inputs)+'\n'+structure('Control',controls)+'\nstruct Factors {float edge[3]:SV_TessFactor;float inside:SV_InsideTessFactor;};\n'+structure('Varyings',varyings)+'\n'+structure('Targets',targets)+'\n'+''.join(entries)+'ENDHLSL\n'
