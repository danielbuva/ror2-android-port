"""Rebuild only the fixed presentation bundle for an installed integrated APK."""
from common import *
import shutil,time

NAMES=['AndroidSurfacePresentation','AndroidTerrainPresentation','AndroidParticlePresentation','AndroidWaterPresentation','AndroidColorGrade','AndroidBillboardPresentation','AndroidOpaqueParticlePresentation','AndroidDistortionPresentation','AndroidIntersectionPresentation']

def build_payload(stages=False,recovered=False):
 from build import preflight,editor
 from device import Device
 preflight();d=Device();owned=d.owned();base=read(WORK/'config/current-build.json')
 if not base.get('success') or base.get('graphics_api')!='vulkan' or owned['apk_sha256']!=base['apk_sha256'] or sha(base['apk'])!=base['apk_sha256']:
  raise RuntimeError('Presentation update requires the installed receipted Vulkan APK')
 if 'android-presentation-lab' not in base.get('payload',{}):raise RuntimeError('APK recipe does not provide the presentation bundle contract')
 for name,h in base['payload'].items():
  if sha(WORK/'generated-android-data'/name)!=h:raise RuntimeError('Unattributed payload drift before presentation build: '+name)
 recovered_sources=None;recovery_receipt=None
 if recovered:
  if stages:raise RuntimeError('Recovered programs require the existing scene payload, without scene changes')
  from shader_source import generate
  recovered_sources=generate();recovery_receipt=read(recovered_sources/'receipt.json')
  if not recovery_receipt.get('success') or set(recovery_receipt['source_sha256_by_file'])!={'AndroidIntersectionPresentation.shader'}:raise RuntimeError('Recovered shader source contract changed')
 out=WORK/'experiments/android-presentation'/now();out.mkdir(parents=True);sources=out/'sources';sources.mkdir()
 stage=WORK/'lab-project/Assets/LabLoadingScene/Resources'
 previous=out/'previous';previous.mkdir()
 write(previous/'selected-build.json',base)
 for name in ['android-presentation-lab','android-presentation-lab.manifest']:shutil.copy2(WORK/'generated-android-data'/name,previous/name)
 for name in NAMES:
  source=ROOT/'tools/unity'/(name+'.shader')
  if recovered and name=='AndroidIntersectionPresentation':
   source=recovered_sources/'sources'/source.name
   if sha(source)!=recovery_receipt['source_sha256_by_file'][source.name]:raise RuntimeError('Recovered shader source drift')
  existing=stage/source.name
  if existing.exists():shutil.copy2(existing,previous/source.name)
  shutil.copy2(source,sources/source.name);shutil.copy2(source,existing)
 include=ROOT/'tools/unity/AndroidRecoveredReflections.cginc';shutil.copy2(include,sources/include.name);shutil.copy2(include,stage/include.name)
 bundles=['android-presentation-lab']
 reflection_guids=[]
 if stages:
  from nova_bridge import stage_first_stage_geometry
  from source_reflections import mappings
  export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
  reflections=mappings(export);write(out/'source-reflection-mapping.json',reflections)
  root=WORK/'lab-project/Assets/LabLoadingScene';previous=out/'previous-scenes';previous.mkdir();bundles=[]
  for name in ['golemplains','foggyswamp','frozenwall','dampcavesimple','skymeadow']:
   scene=root/'StageGeometry'/(name+'.unity');shutil.copy2(scene,previous/scene.name)
   bindings=next(row['probes'] for row in reflections['rows'] if row['stage']==name)
   stage_first_stage_geometry(root,out,original_name=True,scene_name=name,map_zones=True,presentation=True,reflection_bindings=bindings);bundles.append(name+'-spine-lab')
  reflection_guids=sorted({p['cube_guid'] for row in reflections['rows'] for p in row['probes']})
  metas=out/'previous-reflection-metas';metas.mkdir();imports=[]
  for guid in reflection_guids:
   matches=[p for p in root.rglob('*.meta') if '\nguid: '+guid+'\n' in p.read_text()]
   if len(matches)!=1:raise RuntimeError('Reflection import identity ambiguous')
   meta=matches[0];texture=Path(str(meta)[:-5]);binding=next(p for row in reflections['rows'] for p in row['probes'] if p['cube_guid']==guid)
   if texture.suffix!='.exr' or sha(texture)!=binding['exported_cube_sha256']:raise RuntimeError('Staged reflection texture differs from exact source')
   shutil.copy2(meta,metas/(guid+'.meta'));imports.append({'guid':guid,'path':str(texture.relative_to(WORK/'lab-project')),'source_sha256':sha(texture),'before_meta_sha256':sha(meta)})
  write(out/'reflection-import-contract.json',{'textures':imports,'format':'RGBAHalf','source_precision_or_convolution_parity':False,'reason':'Measured default Android import loses exported low-light signal even after native HDR decode'})
 shutil.copy2(ROOT/'android/Assets/Editor/LabBuild.cs',WORK/'lab-project/Assets/Editor/LabBuild.cs')
 transforms=out/'authored-transformations';transforms.mkdir()
 for name in (['nova_bridge.py','source_reflections.py','presentation.py'] if stages else ['presentation.py']):shutil.copy2(ROOT/'scripts/lab'/name,transforms/name)
 if recovered:
  for name in ['shader_source.py','shader_segments.py']:shutil.copy2(ROOT/'scripts/lab'/name,transforms/name)
  write(out/'shader-recovery.json',{'evidence':str(recovered_sources.relative_to(ROOT)),**recovery_receipt})
 shutil.copy2(ROOT/'android/Assets/Editor/LabBuild.cs',transforms/'LabBuild.cs')
 scope='Original base-stage atmosphere/lighting/environment particles and exact floating-point probe texture bindings' if stages else 'Locally generated original intersection bindings/programs, other authored presentation shaders and reflection include' if recovered else 'Authored presentation shaders and reflection include only'
 write(out/'base-build.json',base);write(out/'recipe.json',{'source_sha256':{p.name:sha(p) for p in sources.iterdir()},'transformation_sha256':{p.name:sha(p) for p in transforms.iterdir()},'apk_sha256':base['apk_sha256'],'scope':scope,'no_APK_installation':True,'gameplay_callbacks_unchanged':True})
 terminal=WORK/'presentation-build-result.json'
 if terminal.exists():terminal.rename(terminal.with_name('previous-presentation-'+now()+'.json'))
 request={'request_id':out.name,'api':'vulkan','presentationOnly':True,'stagePresentation':stages,'output':str(out/'bundle'),'reflectionTextureGuids':reflection_guids};write(WORK/'presentation-build-request.json',request)
 print(editor('lab','refresh'),flush=True);print(editor('lab','presentation-payload'),flush=True)
 deadline=time.monotonic()+300
 while time.monotonic()<deadline:
  if terminal.exists():break
  time.sleep(2)
 else:raise RuntimeError('Presentation build timeout; preserve request and inspect editor')
 result=read(terminal);write(out/'terminal.json',result)
 if result.get('request_id')!=out.name or not result.get('success'):raise RuntimeError('Presentation build failed or unattributed: '+str(result))
 started=read(out/'bundle/started.json')
 if started!=request:raise RuntimeError('Presentation build start identity differs')
 # Retain the original full-build/cache receipt and publish a separate payload variant.
 updated=dict(base);updated['payload']=dict(base['payload']);updated['presentation_payload_attempt']=str(out.relative_to(ROOT))
 if recovered:updated['recovered_shader_sources']=str(recovered_sources.relative_to(ROOT))
 elif not stages:updated.pop('recovered_shader_sources',None)
 for name in [filename for bundle in bundles for filename in [bundle,bundle+'.manifest']]:
  source=out/'bundle'/name
  if not source.is_file():raise RuntimeError('Presentation output missing: '+name)
  shutil.copy2(source,WORK/'generated-android-data'/name);updated['payload'][name]=sha(source)
 for name,h in updated['payload'].items():
  if sha(WORK/'generated-android-data'/name)!=h:raise RuntimeError('Unrelated payload changed during presentation build: '+name)
 if sha(base['apk'])!=owned['apk_sha256']:raise RuntimeError('Installed APK identity changed during presentation build')
 write(out/'selected-build.json',updated);write(WORK/'config/current-build.json',updated)
 print(json.dumps({'success':True,'evidence':str(out.relative_to(ROOT)),'apk_unchanged':True,'device_rendering_verified':False},indent=2))
