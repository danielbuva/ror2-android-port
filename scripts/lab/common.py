"""Shared local-only configuration, content addressing, and safe subprocess helpers."""
import hashlib,json,os,subprocess,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'work'
def read(p): return json.loads(Path(p).read_text())
def write(p,v):
 p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n'); tmp.replace(p)
def config(): return read(WORK/'config/local.json')
def game():
 p=Path(config()['game_path']).expanduser().resolve()
 if not (p/'Risk of Rain 2_Data/Managed/RoR2.dll').is_file(): raise RuntimeError('Configured legitimate game installation missing RoR2.dll')
 if p==ROOT or ROOT in p.parents and WORK not in p.parents: raise RuntimeError('Game inputs must be external or under ignored work/')
 return p
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
 return h.hexdigest()
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run(args,timeout=120,check=True,**kw):
 p=subprocess.run([str(a) for a in args],capture_output=True,timeout=timeout,**kw)
 if check and p.returncode: raise RuntimeError(f'{args[0]} exited {p.returncode}: '+p.stderr.decode(errors='replace')[-2000:]+p.stdout.decode(errors='replace')[-2000:])
 return p
def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
def stamp(stage,inputs): return digest({'stage':stage,'inputs':inputs,'code':{p.name:sha(p) for p in sorted((ROOT/'scripts/lab').glob('*.py'))}})
