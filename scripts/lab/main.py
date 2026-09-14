import argparse,sys
from common import *
p=argparse.ArgumentParser(description='Local RoR2 porting laboratory; generated evidence lives under ignored work/.')
p.add_argument('command',choices=['diagnostics','test','doctor','inspect','decompile','export-project','preflight','build','install','sync-data','run','logs','crash','screenshot','reset','smoke','storage','perf','graphics','editor','prototype'])
p.add_argument('--full',action='store_true');p.add_argument('--force',action='store_true');p.add_argument('--json',action='store_true');p.add_argument('--assembly');p.add_argument('--target',default='lab');p.add_argument('--action',default='inspect')
p.add_argument('--subtree',default='');p.add_argument('--fields',action='store_true');p.add_argument('--disable',action='store_true')
a=p.parse_args()
try:
 if a.command=='test':sys.exit(subprocess.call([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v']))
 elif a.command=='doctor':
  from health import doctor
  sys.exit(doctor(a.json))
 elif a.command=='inspect':
  from inventory import inspect
  inspect(a.full)
 elif a.command in ['decompile','export-project']:
  from recovery import decompile,export_project
  decompile(a.assembly,a.force) if a.command=='decompile' else export_project(a.force)
 elif a.command=='graphics':
  from graphics import graphics
  graphics()
 elif a.command=='prototype':
  if a.action=='profile-binding-prepare':
   from scene_runtime import profile_binding_prepare
   profile_binding_prepare()
  elif a.action=='audio-guard-prepare':
   from scene_runtime import audio_guard_prepare
   audio_guard_prepare()
  elif a.action=='audio-native-prepare':
   from scene_runtime import audio_assets_prepare
   audio_assets_prepare(native_availability=True)
  elif a.action=='audio-assets-prepare':
   from scene_runtime import audio_assets_prepare
   audio_assets_prepare()
  elif a.action=='startup-integration-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(integration=True)
  elif a.action=='startup-ngss-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True,application_awake=True,global_textures=True,interpolation=True,fps_queue=True,volume=True,volume_order=True,ngss=True)
  elif a.action=='startup-volume-order-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True,application_awake=True,global_textures=True,interpolation=True,fps_queue=True,volume=True,volume_order=True)
  elif a.action=='startup-volume-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True,application_awake=True,global_textures=True,interpolation=True,fps_queue=True,volume=True)
  elif a.action=='startup-fps-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True,application_awake=True,global_textures=True,interpolation=True,fps_queue=True)
  elif a.action=='startup-interpolation-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True,application_awake=True,global_textures=True,interpolation=True)
  elif a.action=='startup-textures-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True,application_awake=True,global_textures=True)
  elif a.action=='startup-application-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True,application_awake=True)
  elif a.action=='startup-scene-prepare':
   from scene_runtime import startup_prepare
   startup_prepare(loading_scene=True)
  elif a.action=='startup-prepare':
   from scene_runtime import startup_prepare
   startup_prepare()
  elif a.action=='startup-run':
   from scene_runtime import scene_run
   scene_run()
  elif a.action=='skin-apply-prepare':
   from scene_runtime import skin_apply_prepare
   skin_apply_prepare()
  elif a.action=='skin-prepare':
   from scene_runtime import skin_prepare
   skin_prepare()
  elif a.action=='avatar-prepare':
   from scene_runtime import avatar_prepare
   avatar_prepare()
  elif a.action=='controller-prepare':
   from scene_runtime import controller_prepare
   controller_prepare()
  elif a.action=='controller-run':
   from scene_runtime import scene_run
   scene_run()
  elif a.action=='pose-prepare':
   from scene_runtime import pose_prepare
   pose_prepare()
  elif a.action=='prefab-bind':
   from scene_runtime import prefab_bind
   prefab_bind()
  elif a.action=='prefab-prepare':
   from scene_runtime import scene_prepare
   scene_prepare(include_prefab=True)
  elif a.action=='scene-arm':
   from scene_runtime import scene_arm
   scene_arm()
  elif a.action=='scene-run':
   from scene_runtime import scene_run
   scene_run()
  elif a.action=='scene-prepare':
   from scene_runtime import scene_prepare
   scene_prepare()
  elif a.action=='scene-closure':
   from scene_closure import scene_closure
   scene_closure()
  elif a.action=='dependency-boundaries':
   from boundaries import dependency_boundaries
   dependency_boundaries()
  elif a.action=='rewired-original':
   from boundaries import rewired_original
   rewired_original()
  elif a.action=='collections-runtime':
   from boundaries import collections_runtime
   collections_runtime()
  elif a.action=='ror2-slice':
   from boundaries import ror2_slice
   ror2_slice()
  elif a.action=='original-closure-runtime':
   from boundaries import ror2_slice
   ror2_slice(full_original=True)
  elif a.action=='original-closure-prepare':
   from boundaries import original_closure_prepare
   original_closure_prepare()
  elif a.action=='original-closure-build':
   from boundaries import original_closure_build
   original_closure_build()
  elif a.action=='recompile':
   from experiments import recompile
   recompile()
  elif a.action=='middleware':
   from experiments import middleware
   middleware()
  elif a.action=='repair-reconstruction':
   sys.exit(subprocess.call([sys.executable,str(ROOT/'patches/reconstruction-ambiguities.py')]))
  elif a.action=='storage-lifecycle':
   from lifecycle import lifecycle
   lifecycle()
  elif a.action=='references':
   from experiments import references
   references()
  elif a.action=='reconstruction':
   from experiments import reconstruction_report
   reconstruction_report()
  else:
   from prepare import prepare
   prepare()
 elif a.command=='diagnostics':
  from device import Device
  d=Device();d.owned();path=read(WORK/'device/runtime.json')['persistentDataPath']
  if not path.endswith('/Android/data/'+__import__('device').PACKAGE+'/files'):raise RuntimeError('Unexpected diagnostics path')
  payload=WORK/'device/diagnostics.json';write(payload,{'enabled':not a.disable,'subtree':a.subtree,'fields':a.fields})
  d.cmd('push',str(payload),path+'/diagnostics.json');print(json.dumps({'success':True,'config':read(payload)}))
 elif a.command=='preflight':
  from build import preflight
  print(json.dumps(preflight(),indent=2))
 elif a.command=='build':
  from build import build
  build(a.target,a.force)
 elif a.command=='editor':
  from build import editor
  print(editor(a.target,a.action))
 elif a.command in ['install','sync-data','run','logs','crash','screenshot','reset','smoke','storage','perf']:
  from device import Device,smoke
  d=Device()
  if a.command=='smoke':
   from build import build
   r=build(a.target,a.force);smoke(r['apk'])
  elif a.command=='install':print(json.dumps(d.install(read(WORK/'config/current-build.json')['apk']),indent=2))
  elif a.command=='sync-data':print(json.dumps(d.sync(),indent=2))
  elif a.command=='run':print(json.dumps(d.launch(),indent=2))
  elif a.command=='storage':print(json.dumps(d.storage(),indent=2))
  elif a.command=='reset':print(json.dumps(d.reset(),indent=2))
  else:print(json.dumps(d.collect(a.command,WORK/'captures'/now()),indent=2))
 else: raise RuntimeError('Unknown command')
except Exception as e:
 print(json.dumps({'success':False,'command':a.command,'error':str(e)}),file=sys.stderr);sys.exit(1)
