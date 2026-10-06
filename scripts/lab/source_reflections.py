"""Recover exact source probe textures omitted by scene export; no rebaking."""
import collections,re,json,struct
from pathlib import Path
from common import WORK,game,read,sha

def mappings(export):
 import UnityPy
 files={}
 serial_to_bundle=collections.defaultdict(set)
 for p in (WORK/'inventory/graphics').glob('*.json'):
  r=read(p);path=r.get('file')
  if not path:continue
  files[path]=r
  for f in r.get('serialized_files',[]):serial_to_bundle[Path(f['name']).name].add(path)
 cached={}
 def environment(rel):
  if rel not in cached:cached[rel]=UnityPy.load(str(game()/rel))
  return cached[rel]
 def resolve(reader,p):
  if p['m_FileID']==0:return reader.assets_file.objects[p['m_PathID']],None
  ext=reader.assets_file.externals[p['m_FileID']-1]
  candidates=serial_to_bundle[Path(ext.path).name]
  if len(candidates)!=1:raise RuntimeError('Ambiguous native external')
  rel=next(iter(candidates));obj=next(o for o in environment(rel).objects if o.path_id==p['m_PathID'])
  return obj,rel
 rows=[]
 for name in ['golemplains','foggyswamp','frozenwall','dampcavesimple','skymeadow']:
  rels=[x for x in files if '/ror2-base-'+name+'_scenes_all_' in x]
  if len(rels)!=1:raise RuntimeError('Source scene bundle ambiguous')
  rel=rels[0];env=environment(rel)
  text=(export/('Assets/RoR2/Base/Scenes/'+name+'/'+name+'.unity')).read_text()
  blocks=re.split(r'(?=^--- !u!)',text,flags=re.M)[1:]
  byid={re.match(r'--- !u!\d+ &(-?\d+)',b)[1]:b for b in blocks}
  probes=[b for b in blocks if b.startswith('--- !u!215 ')]
  stage=[]
  for obj in env.objects:
   if obj.type.name!='ReflectionProbe':continue
   t=obj.read_typetree();go,_=resolve(obj,t['m_GameObject']);gt=go.read_typetree()
   transform=next(o for o in env.objects if o.type.name=='Transform' and o.read_typetree()['m_GameObject']==t['m_GameObject'])
   pos=transform.read_typetree()['m_LocalPosition']
   matches=[]
   for b in probes:
    oid=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',b)[1];owner=byid[oid]
    oname=re.search(r'^  m_Name: (.*)$',owner,re.M)[1]
    if oname.startswith('"'):oname=json.loads(oname)
    elif oname.startswith("'") and oname.endswith("'"):oname=oname[1:-1].replace("''", "'")
    if oname!=gt['m_Name']:continue
    tb=next(b for b in blocks if b.startswith('--- !u!4 ') and re.search(r'm_GameObject: \{fileID: (-?\d+)\}',b)[1]==oid)
    xyz=re.search(r'm_LocalPosition: \{x: ([^,]+), y: ([^,]+), z: ([^}]+)\}',tb).groups()
    if all(struct.pack('<f',float(a))==struct.pack('<f',pos[k]) for a,k in zip(xyz,['x','y','z'])):matches.append(b)
   if len(matches)!=1:raise RuntimeError('Native probe mapping ambiguous: '+name+' '+gt['m_Name'])
   cube,cuberel=resolve(obj,t['m_BakedTexture']);ct=cube.read_typetree()
   if t['m_Mode']!=0 or t['m_CustomBakedTexture']['m_PathID']!=0:raise RuntimeError('Original reflection probe is not the measured baked contract')
   if cube.type.name!='Cubemap':raise RuntimeError('Native reflection is not cubemap')
   containers=[]
   for co in environment(cuberel or rel).objects:
    if co.type.name!='AssetBundle':continue
    for path,info in co.read_typetree()['m_Container']:
     if info['asset']['m_PathID']==cube.path_id and info['asset']['m_FileID']==0:containers.append(path)
   if len(containers)!=1:raise RuntimeError('Cubemap container mapping ambiguous')
   source=(export/containers[0]).resolve()
   if not source.is_relative_to((export/'Assets').resolve()):raise RuntimeError('Cubemap container escapes generated source assets')
   if not source.is_file():raise RuntimeError('Exact exported cubemap missing')
   meta=Path(str(source)+'.meta');mt=meta.read_text()
   if 'textureShape: 2' not in mt:raise RuntimeError('Exported texture importer not cubemap')
   guid=re.search(r'^guid: ([a-f0-9]{32})',mt,re.M)[1]
   stage.append({'source_mode':t['m_Mode'],'source_custom_texture':t['m_CustomBakedTexture'],'probe_file_id':re.match(r'--- !u!215 &(-?\d+)',matches[0])[1],'owner_name':gt['m_Name'],'local_position':pos,'source_native_path_id':obj.path_id,'original_cube_name':ct['m_Name'],'cube_container':containers[0],'cube_guid':guid,'exported_cube_sha256':sha(source),'source_bundle':rel,'source_bundle_sha256':sha(game()/rel),'cube_bundle':cuberel or rel,'cube_bundle_sha256':sha(game()/(cuberel or rel))})
  if len(stage)!=len(probes):raise RuntimeError('Native/exported probe count mismatch')
  rows.append({'stage':name,'probes':stage})
  print(name,len(stage),'exact original probe/cubemap mappings',flush=True)
 return {"input_id":read(WORK/"inventory/files.json")["input_id"],"method":"Native baked texture -> source external/container -> exact exported Cubemap; unique owner/float32-position match","rows":rows}
