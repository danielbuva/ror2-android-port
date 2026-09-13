from common import *
import importlib.metadata

def doctor(as_json=False):
 p=run([ROOT/'scripts/doctor.sh','--json'],timeout=90,check=False)
 try:bootstrap=json.loads(p.stdout)
 except ValueError:bootstrap={'raw':p.stdout.decode(errors='replace')}
 checks=[]
 def check(name,fn):
  try:value=fn();checks.append({'name':name,'ok':bool(value),'detail':value})
  except Exception as e:checks.append({'name':name,'ok':False,'detail':str(e)})
 check('legitimate input',lambda:str(game()))
 check('inventory exists',lambda:read(WORK/'inventory/summary.json')['input_id'])
 check('accepted input',lambda:read(WORK/'config/accepted-input.json')['input_id']==read(WORK/'inventory/files.json')['input_id'])
 check('UnityPy pin',lambda:importlib.metadata.version('UnityPy')=='1.25.3')
 check('PE parser pin',lambda:importlib.metadata.version('pefile')=='2024.8.26')
 check('lab source project',lambda:(WORK/'lab-project/Assets/LabDiagnostics.cs').exists())
 check('last passing lab checkpoint',lambda:any(read(x).get('success') for x in (WORK/'runs').glob('*/result.json')))
 result={'success':p.returncode==0 and all(x['ok'] for x in checks),'bootstrap':bootstrap,'lab':checks,'limits':['RoR2 gameplay has not booted','Full-game native/AOT/shader compatibility unresolved']}
 write(WORK/'doctor.json',result)
 if as_json:print(json.dumps(result,indent=2))
 else:
  for c in checks:print(('OK   ' if c['ok'] else 'FAIL ')+c['name']+': '+str(c['detail']))
  print('Bootstrap: '+('PASS' if p.returncode==0 else 'FAIL; ./scripts/doctor.sh for details'))
  print('LAB READY' if result['success'] else 'LAB BLOCKED')
 return 0 if result['success'] else 1
