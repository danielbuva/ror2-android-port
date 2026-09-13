from common import *
import shutil

def prepare():
 import UnityPy
 dest=WORK/'lab-project'; dest.mkdir(exist_ok=True)
 for name in ['Packages','ProjectSettings']:
  if not (dest/name).exists():shutil.copytree(ROOT/'smoke'/name,dest/name)
 manifest=read(dest/'Packages/manifest.json');manifest['dependencies']['com.unity.modules.assetbundle']='1.0.0';write(dest/'Packages/manifest.json',manifest)
 shutil.copytree(ROOT/'android/Assets',dest/'Assets',dirs_exist_ok=True)
 managed=dest/'Assets/Plugins';managed.mkdir(parents=True,exist_ok=True)
 shutil.copy2(game()/'Risk of Rain 2_Data/Managed/SimpleJSON.dll',managed/'SimpleJSON.dll')
 recovered=dest/'Assets/Recovered';recovered.mkdir(parents=True,exist_ok=True)
 if not (recovered/'geometry.obj').exists():
  bundles=list((game()/'Risk of Rain 2_Data/StreamingAssets').rglob('*commando_assets*.bundle'))
  for p in bundles:
   e=UnityPy.load(str(p))
   meshes=[o for o in e.objects if o.type.name=='Mesh']
   if not meshes:continue
   obj=meshes[0];m=obj.read();(recovered/'geometry.obj').write_text(m.export())
   write(WORK/'inventory/geometry-provenance.json',{'input_id':read(WORK/'inventory/files.json')['input_id'],'bundle':str(p.relative_to(game())),'bundle_sha256':sha(p),'path_id':obj.path_id,'mesh_name':m.m_Name,'output_sha256':sha(recovered/'geometry.obj'),'method':'UnityPy Mesh.export OBJ; no original shaders or scripts'});break
  else:raise RuntimeError('No Commando mesh found')
 write(WORK/'config/lab-project.json',{'project':str(dest),'simplejson_sha256':sha(managed/'SimpleJSON.dll')})
 graphics=read(WORK/'inventory/graphics.json')
 candidates=[r for r in graphics if r['file'].endswith('.bundle') and any(s.get('name','').startswith('Hopoo Games/') for s in r.get('shaders',[]))]
 if not candidates:raise RuntimeError('No original shader candidate; run ./dev graphics and review input')
 sample=min(candidates,key=lambda r:((game()/r['file']).stat().st_size,r['file']))
 payload=WORK/'generated-android-data';payload.mkdir(exist_ok=True);shutil.copy2(game()/sample['file'],payload/'windows-shaders.bundle')
 write(WORK/'inventory/windows-shader-prototype.json',{'source':sample['file'],'sha256':sample['sha256'],'shaders':sample['shaders']})
 print(dest)
