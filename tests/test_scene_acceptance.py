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
