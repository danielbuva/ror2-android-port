import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
import scene_runtime
from common import write, read

class SceneAcceptanceTests(unittest.TestCase):
 def test_passing_runtime_marker_cannot_mask_failed_required_capture(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);work=root/'work';out=work/'experiments/scene-runtime/attempt'
   write(work/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(root))})
   write(out/'attempt.json',{'stage':str(root/'stage'),'original_assemblies':{},'pose':True})
   write(work/'config/current-build.json',{'success':True,'apk':'mock.apk','payload':{'loadingbasic-lab':'mock'}})
   write(work/'device/runtime.json',{'persistentDataPath':'mock-owned-path'})
   d=MagicMock();d.sync.return_value={};d.exists.return_value=False;d.launch.return_value={'pid':'123'}
   def install(apk):write(work/'device/installed.json',{'test':True});return {'test':True}
   d.install.side_effect=install
   d.sh.return_value=json.dumps({'success':True,'attempt':'attempt','pid':123})
   d.cmd.side_effect=RuntimeError('required capture transfer failed');d.reset.return_value={'removed':True}
   with patch.object(scene_runtime,'ROOT',root),patch.object(scene_runtime,'WORK',work),patch('build.preflight'),patch('device.Device',return_value=d),patch('time.monotonic',side_effect=[0,36,36]):
    with self.assertRaisesRegex(RuntimeError,'Scene probe failed'):scene_runtime.scene_run()
   result=read(out/'runtime-result.json');self.assertFalse(result['success']);self.assertIn('capture transfer failed',result['error']);d.reset.assert_called_once()

 def test_other_foreground_app_cannot_pass_capture_acceptance(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);work=root/'work';out=work/'experiments/scene-runtime/attempt'
   write(work/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(root))})
   write(out/'attempt.json',{'stage':str(root/'stage'),'original_assemblies':{},'startup':True})
   write(work/'config/current-build.json',{'success':True,'apk':'mock.apk','payload':{'loadingbasic-lab':'mock'}})
   write(work/'device/runtime.json',{'persistentDataPath':'mock-owned-path'})
   d=MagicMock();d.exists.return_value=True;d.launch.return_value={'pid':'123'};d.install.return_value={};d.sync.return_value={}
   d.sh.side_effect=lambda *args,**kw: 'mResumedActivity: ActivityRecord{other.app/.Main}' if args[0]=='dumpsys' else json.dumps({'success':True,'attempt':'attempt','pid':123})
   with patch.object(scene_runtime,'ROOT',root),patch.object(scene_runtime,'WORK',work),patch('build.preflight'),patch('device.Device',return_value=d),patch('time.monotonic',side_effect=[0,51,51]):
    with self.assertRaisesRegex(RuntimeError,'Scene probe failed'):scene_runtime.scene_run()
   result=read(out/'runtime-result.json');self.assertFalse(result['success']);self.assertFalse(result['foreground_verified']);self.assertIn('foreground',result['error']);d.reset.assert_not_called()


class MovementBatchTests(unittest.TestCase):
 def test_failed_launch_does_not_hide_later_probes(self):
  import itertools
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);work=root/'work';out=work/'experiments/scene-runtime/attempt'
   write(work/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(root))})
   write(out/'attempt.json',{'stage':str(root/'stage'),'original_assemblies':{},'movement_batch':True})
   write(work/'config/current-build.json',{'success':True,'apk':'mock.apk','apk_sha256':'hash'})
   write(work/'lab-build/result.json',{'success':True,'apk':'mock.apk'})
   write(work/'device/runtime.json',{'persistentDataPath':'mock-owned-path'})
   d=MagicMock();d.install.return_value={};d.launch.side_effect=[{'pid':'1'},RuntimeError('first process crashed'),{'pid':'3'},{'pid':'4'},{'pid':'5'}]
   current={}
   def command(*args,**kwargs):
    if args[0]=='push':current.update(read(Path(args[1])))
   d.cmd.side_effect=command
   def shell(*args,**kwargs):
    if args[0]=='cat':
     ids={'buttons':2,'input':3,'motor-output':4,'motor-acceleration':5}
     return json.dumps(dict(current,pid=ids[current['id']],success=True,phase='complete'))
    return ''
   d.sh.side_effect=shell
   with patch.object(scene_runtime,'ROOT',root),patch.object(scene_runtime,'WORK',work),patch.object(scene_runtime,'sha',return_value='hash'),patch('build.preflight'),patch('device.Device',return_value=d),patch('time.monotonic',side_effect=itertools.count(0,30)):
    with self.assertRaisesRegex(RuntimeError,'Batch completed with failed probes'):scene_runtime.movement_batch_run()
   results=read(out/'batch-result.json')
   self.assertFalse(results['buttons']['success'])
   self.assertIn('crashed',results['buttons']['error'])
   self.assertTrue(all(results[k]['success'] for k in ['input','motor-output','motor-acceleration']))
   self.assertEqual(d.collect.call_count,4)

 def test_missing_layer_log_rejects_true_runtime_result(self):
  import itertools
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);work=root/'work';out=work/'experiments/scene-runtime/attempt'
   write(work/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(root))})
   write(out/'attempt.json',{'stage':str(root/'stage'),'original_assemblies':{},'movement_batch':True,'batch_ids':['input']})
   write(work/'config/current-build.json',{'success':True,'apk':'mock.apk','apk_sha256':'hash'})
   write(work/'lab-build/result.json',{'success':True,'apk':'mock.apk'})
   write(work/'device/runtime.json',{'persistentDataPath':'mock-owned-path'})
   d=MagicMock();d.install.return_value={};d.launch.return_value={'pid':'123'}
   d.sh.return_value=json.dumps({'id':'input','attempt':'attempt','pid':123,'success':True,'phase':'complete'})
   def collect(kind,directory):
    directory.mkdir(parents=True);(directory/'unity.log').write_text('09-19 12:00:00.000 123 124 E Unity : Layer "FakeActor" is not defined in this project')
   d.collect.side_effect=collect
   with patch.object(scene_runtime,'ROOT',root),patch.object(scene_runtime,'WORK',work),patch.object(scene_runtime,'sha',return_value='hash'),patch('build.preflight'),patch('device.Device',return_value=d),patch('time.monotonic',side_effect=itertools.count(0,30)):
    with self.assertRaisesRegex(RuntimeError,'Batch completed with failed probes'):scene_runtime.movement_batch_run()
   self.assertFalse(read(out/'batch-result.json')['input']['success'])

 def test_unfinished_or_stale_build_cannot_install_previous_apk(self):
  import os
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);work=root/'work';out=work/'experiments/scene-runtime/attempt'
   write(work/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(root))})
   write(out/'attempt.json',{'movement_batch':True})
   write(work/'config/current-build.json',{'success':True,'apk':'previous.apk','apk_sha256':'old'})
   terminal=work/'lab-build/result.json'
   with patch.object(scene_runtime,'ROOT',root),patch.object(scene_runtime,'WORK',work),patch('build.preflight'),patch('device.Device') as device:
    with self.assertRaisesRegex(RuntimeError,'No completed forced build'):scene_runtime.movement_batch_run()
    write(terminal,{'success':True,'apk':'previous.apk'});os.utime(terminal,(1,1))
    with self.assertRaisesRegex(RuntimeError,'No completed forced build'):scene_runtime.movement_batch_run()
    os.utime(terminal,None)
    with patch.object(scene_runtime,'sha',return_value='different'):
     with self.assertRaisesRegex(RuntimeError,'does not match'):scene_runtime.movement_batch_run()
    device.assert_not_called()

 def test_retry_keeps_original_failure_and_uses_original_attempt_identity(self):
  import itertools
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);work=root/'work';out=work/'experiments/scene-runtime/attempt'
   write(work/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(root))})
   write(out/'attempt.json',{'movement_batch':True,'original_assemblies':{}})
   write(out/'batch-result.json',{'input':{'success':False}})
   write(work/'config/current-build.json',{'success':True,'apk':'mock.apk','apk_sha256':'hash'})
   write(work/'lab-build/result.json',{'success':True,'apk':'mock.apk'})
   write(work/'device/runtime.json',{'persistentDataPath':'mock-owned-path'})
   d=MagicMock();d.install.return_value={};d.launch.return_value={'pid':'123'}
   d.sh.return_value=json.dumps({'id':'input','attempt':'attempt','pid':123,'success':True,'phase':'complete'})
   with patch.object(scene_runtime,'ROOT',root),patch.object(scene_runtime,'WORK',work),patch.object(scene_runtime,'sha',return_value='hash'),patch('build.preflight'),patch('device.Device',return_value=d),patch('time.monotonic',side_effect=itertools.count(0,30)):
    scene_runtime.movement_batch_run(cases=['input'],retry=True)
   self.assertFalse(read(out/'batch-result.json')['input']['success'])
   retry=next((out/'verification').iterdir())
   self.assertTrue(read(retry/'batch-result.json')['input']['success'])
   self.assertEqual(read(retry/'input/selection.json')['attempt'],'attempt')
