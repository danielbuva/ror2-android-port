import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
import build
import device
import rewired_trial as trial
from common import sha,write

class TrialSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.out=self.root/'attempt';self.out.mkdir()
        self.apk=self.out/'rewired-trial-arm64.apk';self.apk.write_bytes(b'fixture')
        write(self.out/'trial-build-result.json',{'success':True,'errors':0,'apk':str(self.apk)})
        self.patches=[patch.object(trial,'ROOT',self.root),patch.object(trial,'WORK',self.root/'work'),
            patch.object(trial,'attempt',return_value=self.out),patch.object(trial,'inventory',return_value={'static_probe_complete':True}),
            patch.object(build,'preflight'),patch('sys.stdout',new=io.StringIO())]
        for item in self.patches:item.start()
    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()
    def test_wrong_package_is_rejected_before_any_device_work(self):
        with patch.object(trial,'run',return_value=SimpleNamespace(stdout=b"package: name='unrelated.app'\n")),patch.object(device,'Device') as android:
            with self.assertRaisesRegex(RuntimeError,'owned disposable lab package'):trial.controller_run()
            android.assert_not_called()
    def test_failed_terminal_build_cannot_install(self):
        write(self.out/'trial-build-result.json',{'success':False,'errors':1,'apk':str(self.apk)})
        with patch.object(device,'Device') as android:
            with self.assertRaisesRegex(RuntimeError,'successful terminal'):trial.controller_run()
            android.assert_not_called()
    def test_startup_failure_restores_previous_apk_sleeps_and_preserves_error(self):
        previous=self.out/'previous.apk';previous.write_bytes(b'previous fixture')
        write(self.root/'work/device/runtime.json',{'persistentDataPath':'unused'})
        calls=[]
        class Android:
            def exists(self):return True
            def owned(self):return {'apk':str(previous),'apk_sha256':sha(previous)}
            def sh(self,*args,**kwargs):return 'Retroid Pocket Nova' if args[0]=='getprop' else ''
            def install(self,apk):calls.append(('install',str(apk)));return {'installed':True}
            def launch(self):raise RuntimeError('deliberate SDK startup failure')
            def collect(self,*args):raise RuntimeError('capture also failed')
            def display(self,awake):calls.append(('display',awake))
        with patch.object(trial,'validate_apk'),patch.object(device,'Device',Android):
            with self.assertRaisesRegex(RuntimeError,'Trial observation failed'):trial.controller_run()
        self.assertEqual(calls,[('install',str(self.apk)),('install',str(previous)),('display',False)])
        record=json.loads(next((self.out/'device').glob('*/result.json')).read_text())
        self.assertEqual(record['first_failure'],'deliberate SDK startup failure')
        self.assertEqual(record['capture_error'],'capture also failed')
        self.assertFalse(record['technical_observation_pass'])

    def test_unready_current_process_preserves_sdk_error(self):
        write(self.root/'work/device/runtime.json',{'persistentDataPath':'/fixture/files','pid':42})
        write(self.root/'work/device/last-run.json',{'pid':'42'})
        report={'attempt':self.out.name,'pid':42,'error':'SDK initialization failed'}
        class Android:
            def exists(self):return False
            def sh(self,*args,**kwargs):
                if args[0]=='getprop':return 'Retroid Pocket Nova'
                if args[0]=='cat':return json.dumps(report)
                return ''
            def install(self,apk):return {}
            def launch(self):raise RuntimeError('Runtime checkpoint failed')
            def collect(self,*args):return {}
            def reset(self):return {}
            def display(self,awake):pass
        with patch.object(trial,'validate_apk'),patch.object(device,'Device',Android):
            with self.assertRaisesRegex(RuntimeError,'Trial observation failed'):trial.controller_run()
        record=json.loads(next((self.out/'device').glob('*/result.json')).read_text())
        self.assertEqual(record['first_failure'],'Runtime checkpoint failed')
        self.assertEqual(record['first_runtime_failure'],'SDK initialization failed')
        self.assertEqual(json.loads(next((self.out/'device').glob('*/controller.json')).read_text()),report)

    def test_post_install_verification_failure_still_restores_previous_apk(self):
        previous=self.out/'previous.apk';previous.write_bytes(b'previous fixture')
        calls=[]
        class Android:
            def exists(self):return True
            def owned(self):return {'apk':str(previous),'apk_sha256':sha(previous)}
            def sh(self,*args,**kwargs):return 'Retroid Pocket Nova' if args[0]=='getprop' else ''
            def install(self,apk):
                calls.append(str(apk))
                if apk==self_apk:raise RuntimeError('Placement verification failed after update')
                return {}
            def collect(self,*args):return {}
            def display(self,awake):pass
        self_apk=self.apk
        with patch.object(trial,'validate_apk'),patch.object(device,'Device',Android):
            with self.assertRaisesRegex(RuntimeError,'Trial observation failed'):trial.controller_run()
        self.assertEqual(calls,[str(self.apk),str(previous)])
        record=json.loads(next((self.out/'device').glob('*/result.json')).read_text())
        self.assertEqual(record['first_failure'],'Placement verification failed after update')
        self.assertNotIn('rollback_error',record)

    def test_completed_sdk_report_cannot_hide_required_capture_failure(self):
        path='/storage/emulated/0/Android/data/'+device.PACKAGE+'/files'
        write(self.root/'work/device/runtime.json',{'persistentDataPath':path,'pid':42})
        write(self.out/'original-manager-parsed.json',{'MonoBehaviour':{'_userData':{
            'actions':[], 'players':[{'_name':'System'},{'_name':'PlayerMain'}]}}})
        report={'attempt':self.out.name,'pid':42,'error':'','complete':True,'ready':True,
            'actions':[],'players':[{'id':9999999,'name':'System'},{'id':0,'name':'PlayerMain'}],
            'joystickCount':1,'playerId':0,'maps':[{'categoryId':0},{'categoryId':2}],
            'events':[],'elapsed':90}
        class Android:
            def exists(self):return False
            def sh(self,*args,**kwargs):
                if args[0]=='getprop':return 'Retroid Pocket Nova'
                if args[0]=='cat':return json.dumps(report)
                return ''
            def install(self,apk):return {}
            def launch(self):return {'pid':'42'}
            def collect(self,*args):raise RuntimeError('Required screenshot transfer failed')
            def reset(self):return {}
            def display(self,awake):pass
        with patch.object(trial,'validate_apk'),patch.object(device,'Device',Android):
            with self.assertRaisesRegex(RuntimeError,'Trial observation failed'):trial.controller_run()
        record=json.loads(next((self.out/'device').glob('*/result.json')).read_text())
        self.assertTrue(record['technical_observation_pass'])
        self.assertEqual(record['first_failure'],'Required device capture failed: Required screenshot transfer failed')

if __name__=='__main__':unittest.main()
