from common import *
import collections,gc

def graphics():
 import UnityPy
 inv=read(WORK/'inventory/files.json');base=game();out=WORK/'inventory/graphics';out.mkdir(parents=True,exist_ok=True);results=[]
 for entry in inv['files']:
  p=base/entry['path']
  if not (entry['category']=='bundle' or p.name in ['globalgamemanagers','resources.assets','sharedassets0.assets','globalgamemanagers.assets','level0','unity_builtin_extra']):continue
  key=digest({'sha':entry['sha256'],'unitypy':UnityPy.__version__,'schema':3});cache=out/(key+'.json')
  if cache.exists():results.append(read(cache));continue
  r={'file':entry['path'],'sha256':entry['sha256'],'objects':{},'shaders':[],'materials':[],'settings':[],'bundles':[],'meshes':[],'errors':[]}
  try:
   env=UnityPy.load(str(p));counter=collections.Counter()
   for af in env.assets: r.setdefault('serialized_files',[]).append({'name':af.name,'version':af.unity_version,'platform':str(af.target_platform),'type_tree':getattr(af,'_enable_type_tree',None)})
   for obj in env.objects:
    kind=obj.type.name;counter[kind]+=1
    if kind not in ['Shader','Material','GraphicsSettings','PlayerSettings','BuildSettings','QualitySettings','AssetBundle','Mesh','ComputeShader']:continue
    try:
     t=obj.read_typetree()
     if kind=='Shader':
      parsed=t.get('m_ParsedForm',{});r['shaders'].append({'path_id':obj.path_id,'name':parsed.get('m_Name',t.get('m_Name')),'platforms':t.get('platforms'),'has_source':bool(t.get('m_Script')),'classification':'SOURCE AVAILABLE' if t.get('m_Script') else 'TRANSLATABLE','source_status':'EXPERIMENTAL: compiled data translation unproven' if not t.get('m_Script') else 'VERIFIED'})
     elif kind=='Material':r['materials'].append({'path_id':obj.path_id,'name':t.get('m_Name'),'shader':t.get('m_Shader')})
     elif kind=='Mesh':r['meshes'].append({'path_id':obj.path_id,'name':t.get('m_Name')})
     elif kind=='AssetBundle':r['bundles'].append({'name':t.get('m_Name'),'container':t.get('m_Container'),'dependencies':t.get('m_Dependencies')})
     elif kind=='ComputeShader':r.setdefault('compute',[]).append({'name':t.get('m_Name'),'keys':list(t)})
     else:r['settings'].append({'type':kind,'value':t})
    except Exception as e:r['errors'].append({'path_id':obj.path_id,'type':kind,'error':str(e)})
   r['objects']=dict(counter);del env;gc.collect()
  except Exception as e:r['errors'].append({'error':str(e)})
  write(cache,r);results.append(r)
  if len(results)%100==0:print(len(results),flush=True)
 write(WORK/'inventory/graphics.json',results)
 shaders=[dict(x,file=r['file']) for r in results for x in r['shaders']];
 oldpath=WORK/'inventory/shader-manifest.json'
 if oldpath.exists():
  before=read(oldpath);surfaces=lambda rows:{(x['file'],str(x.get('path_id'))):digest(x) for x in rows};a,b=surfaces(before),surfaces(shaders)
  write(WORK/'inventory/shader-diff.json',{'changed':[list(k) for k in b if a.get(k)!=b[k]],'removed':[list(k) for k in a if k not in b]})
 write(oldpath,shaders)
 summary={'files':len(results),'objects':dict(sum((collections.Counter(r['objects']) for r in results),collections.Counter())),'shaders':len(shaders),'errors':sum(len(r['errors']) for r in results)};write(WORK/'inventory/graphics-summary.json',summary);print(json.dumps(summary,indent=2))
