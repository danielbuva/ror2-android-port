#!/usr/bin/env python3
"""Bounded local reconstruction repair; no game source included or overwritten in the installation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
from common import *
from build import preflight
preflight()
p=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
if WORK not in p.resolve().parents:raise RuntimeError('Only ignored reconstruction may be transformed')
rules=[('Assets/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs','private Event ','private AK.Wwise.Event ',2),('Assets/Scripts/Assembly-CSharp/Properties/AssemblyInfo.cs','typeof(Monitor)','typeof(EntityStates.QuestVolatileBattery.Monitor)',1),('Assets/Scripts/Assembly-CSharp/Properties/AssemblyInfo.cs','typeof(DebugOverlay)','typeof(RoR2.DebugOverlay)',1)]
rows=[]
for name,old,new,count in rules:
 f=p/name;text=f.read_text();before=sha(f)
 if text.count(new)==count and old not in text:rows.append({'file':name,'already_applied':True});continue
 if text.count(old)!=count:raise RuntimeError('Semantic match count changed: '+name)
 text=text.replace(old,new);f.write_text(text);rows.append({'file':name,'before':before,'after':sha(f),'matches':count})
write(WORK/'experiments/reconstruction-patches.json',rows)
print(json.dumps(rows,indent=2))
