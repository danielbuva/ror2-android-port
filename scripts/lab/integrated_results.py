"""Source ending definitions for the composed Android results flow; inputs stay ignored."""
from common import *
import re
import shutil

def stage_results(stage, out, previous):
    from scene_closure import REFERENCE
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    source_assets=export/'Assets'
    index={}
    for meta in source_assets.rglob('*.meta'):
        match=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
        if match:index[match[1]]=Path(str(meta)[:-5])
    existing={}
    for meta in stage.rglob('*.meta'):
        match=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
        if match:existing[match[1]]=Path(str(meta)[:-5])
    folder=source_assets/'RoR2/Base/GameModes/ClassicRun/Endings'
    roots=[folder/(name+'.asset') for name in ['MainEnding','EscapeSequenceFailed','StandardLoss']]
    remaps={x['from']:x['to'] for x in previous.get('ui_remaps',[])}
    pending=list(roots);seen=set();rows=[];staged={}
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src);guid=re.search(r'^guid: ([a-f0-9]{32})',Path(str(src)+'.meta').read_text(),re.M)[1]
        if src.suffix=='.dll':
            if src.name=='UnityEngine.UI.dll' and remaps:continue
            if guid not in existing:raise RuntimeError('Unprovided original ending assembly: '+src.name)
            continue
        if src.suffix=='.unity':raise RuntimeError('Ending definition unexpectedly requires another scene')
        dst=existing.get(guid,stage/'ResultsClosure'/src.relative_to(source_assets))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(Path(str(src)+'.meta'),Path(str(dst)+'.meta'));existing[guid]=dst
        staged[src]=str(dst.relative_to(WORK/'lab-project'))
        rows.append(dict(source=str(src.relative_to(export)),source_sha256=sha(src),staged=staged[src]))
        if src.read_bytes()[:5]==b'%YAML':
            text=src.read_text()
            if any(old in text for old in remaps):
                generated=dst.read_text()
                for old,new in remaps.items():generated=generated.replace(old,new)
                dst.write_text(generated)
            for _,g,_ in REFERENCE.findall(text):
                if g and not g.startswith('0000000000000000'):
                    if g not in index:raise RuntimeError('Unresolved ending definition GUID')
                    pending.append(index[g])
    assets=[staged[x] for x in roots];recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+assets));write(WORK/'scene-probe-build.json',recipe)
    write(out/'integrated-results-contract.json',dict(closure=rows,scope='Original game-ending definitions; original report/statistics and Android presentation/run ledger. No platform identity, stock profile, unlock or ending fabrication.',prior_art='ProperSave d20c6c8 owned persistent filesystem separation; exact Run.BeginGameOver/GameOverController/RunReport/StatManager source inspected. No implementation copied.'))
    return dict(integratedResults=True,resultsEndingAssets=[x.lower() for x in assets])
