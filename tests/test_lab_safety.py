import unittest,tempfile,json,zipfile,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
import device
from common import write
class SafetyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.patcher=patch.object(device,'WORK',self.root);self.patcher.start()
  self.d=object.__new__(device.Device);self.d.serial='authorized-test';self.d.base=['must-not-execute-adb']
 def tearDown(self):self.patcher.stop();self.temp.cleanup()
 def apk(self,abi='arm64-v8a'):
  p=self.root/'test.apk'
  with zipfile.ZipFile(p,'w') as z:z.writestr('lib/'+abi+'/libtest.so',b'not executable')
  return p
 def test_existing_unreceipted_package_is_never_modified(self):
  self.d.exists=lambda:True
  with self.assertRaisesRegex(RuntimeError,'ownership receipt'):self.d.install(self.apk())
 def test_low_internal_space_blocks_before_install(self):
  self.d.exists=lambda:False;self.d.storage=lambda:{'internal':{'free_bytes':128},'adopted':{'free_bytes':10**12}}
  with patch.object(device,'config',return_value={'internal_reserve_mib':1024}):
   with self.assertRaisesRegex(RuntimeError,'Insufficient internal'):self.d.install(self.apk())
 def test_wrong_abi_blocks_before_install(self):
  self.d.exists=lambda:False;self.d.storage=lambda:{}
  with self.assertRaisesRegex(RuntimeError,'only arm64-v8a'):self.d.install(self.apk('x86_64'))
 def test_ownership_receipt_bound_to_device_and_placement(self):
  write(self.root/'device/installed.json',{'serial':'someone-else','package':device.PACKAGE,'package_path':'old'})
  with self.assertRaisesRegex(RuntimeError,'ownership changed'):self.d.owned()
 def test_sync_rejects_arbitrary_destination(self):
  self.d.owned=lambda:{};self.d.storage=lambda:{}
  write(self.root/'device/runtime.json',{'persistentDataPath':'/data/local/tmp/another-game'})
  with self.assertRaisesRegex(RuntimeError,'Unexpected runtime'):self.d.sync()
 def test_reset_absent_package_does_not_call_adb_uninstall(self):
  self.d.exists=lambda:False
  self.assertFalse(self.d.reset()['removed'])
if __name__=='__main__':unittest.main()
