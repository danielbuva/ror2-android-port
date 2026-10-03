"""One isolated official-trial comparison and bounded physical-input observation."""
from common import *
import re,time

def attempt():
    out=(ROOT/read(WORK/'experiments/rewired-trial/active.json')['path']).resolve()
    if out.parent != (WORK/'experiments/rewired-trial').resolve():
        raise RuntimeError('Unexpected reference attempt path')
    receipt=read(out/'attempt.json')
    if receipt['input_id'] != read(WORK/'inventory/files.json')['input_id']:
        raise RuntimeError('Reference comparison input changed; review drift first')
    return out

def inventory():
    out=attempt();original=read(out/'original-contract.json');trial=read(out/'trial-public-api.json')
    game=next(a for a in original['assemblies'] if a['file']=='RoR2.dll')
    types={t['type']:t for t in trial['types']}
    members={m['signature']:(t,m) for t in trial['types'] for m in t['methods']+t['fields']}
    definitions={t['type']:t for a in original['assemblies'] for t in a['definitions']}
    old_members={m['signature']:m for t in definitions.values() for m in t['methods']+t['fields']}
    matches=[];missing=[];identity=[];flags=[];bases=[];interfaces=[]
    for member in game['consumedMembers']:
        sig=member['signature']
        if sig not in members:
            missing.append(member);continue
        typ,new=members[sig];matches.append(sig)
        if member['scope']!=typ['assembly']:
            identity.append({'signature':sig,'original':member['scope'],'trial':typ['assembly']})
        old=old_members.get(sig)
        if old is not None and ('Static' in old['attributes']) != new['isStatic']:
            flags.append({'signature':sig,'difference':'static/instance'})
        if old is not None and old.get('genericArity',0)!=new['genericArity']:
            flags.append({'signature':sig,'difference':'generic arity'})
    for typ in game['consumerTypes']:
        parent=types.get(typ['baseType'])
        if parent and parent['isSealed']:
            bases.append({'consumer':typ['type'],'base':typ['baseType'],'difference':'trial base is sealed'})
        for name in typ['interfaces']:
            old=definitions.get(name);new=types.get(name)
            if old and new:
                before={m['signature'] for m in old['methods']};after={m['signature'] for m in new['methods']}
                interfaces.append({'consumer':typ['type'],'interface':name,'removed':sorted(before-after),'added':sorted(after-before)})
    result={'static_probe_complete':True,'drop_in_compatible':False,'original_version':'1.1.47.0.U2021',
        'trial_version':'1.1.65.3.U2021','scanned_original_assemblies':original['scannedAssemblyCount'],
        'consumed_members':len(game['consumedMembers']),'signature_matches':len(matches),
        'missing_or_inaccessible':missing,'assembly_scope_changes':identity,'static_or_generic_changes':flags,
        'inheritance_breaks':bases,'interfaces':interfaces,
        'serialization':read(out/'serialization-comparison.json'),
        'scope':'Public/protected API, inherited game contract and passive serialization only; no game compatibility or controller acceptance'}
    write(out/'comparison.json',result)
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'scanned':result['scanned_original_assemblies'],
        'signature_matches':len(matches),'consumed_members':len(game['consumedMembers']),
        'missing_or_inaccessible':len(missing),'assembly_scope_changes':len(identity),
        'inheritance_breaks':len(bases),'drop_in_compatible':False},indent=2))
    return result

def controller_run():
    from build import preflight
    from device import Device,PACKAGE
    out=attempt();comparison=inventory()
    if not comparison['static_probe_complete']:raise RuntimeError('Finish reference comparison before runtime')
    built=read(out/'trial-build-result.json');apk=Path(built['apk']).resolve()
    if not built['success'] or built['errors'] or apk != out/'rewired-trial-arm64.apk' or not apk.is_file():
        raise RuntimeError('No successful terminal reference build')
    validate_apk(apk)
    preflight();runout=out/'device'/now();runout.mkdir(parents=True)
    d=Device();previous=d.owned() if d.exists() else None
    if d.sh('getprop','ro.product.model')!='Retroid Pocket Nova':
        raise RuntimeError('Trial device work is authorized only on Nova')
    if previous:
        if not Path(previous['apk']).is_file() or sha(previous['apk'])!=previous['apk_sha256']:
            raise RuntimeError('Installed lab rollback APK unavailable or hash changed')
        write(runout/'installed-before-trial.json',previous)
    result={'attempt':out.name,'apk_sha256':sha(apk),'scope':'Trial SDK/controller data only. No RoR2 execution or formal controller acceptance.',
        'technical_observation_pass':False,'human_mapping_accepted':False,'game_integration_accepted':False}
    installed=False
    try:
        # Placement verification may fail after Android has already updated the app.
        installed=True
        result['install']=d.install(apk)
        result['runtime']=d.launch();runtime=read(WORK/'device/runtime.json')
        path=runtime['persistentDataPath']
        if not path.endswith('/Android/data/'+PACKAGE+'/files'):raise RuntimeError('Unexpected reference data path')
        result['backing_df']=d.sh('df','-k',path)
        write(runout/'phase.json',{'phase':'ready','pid':result['runtime']['pid']})
        print('REWIRED_PHYSICAL_CAPTURE_READY: 90-second bounded observation',flush=True)
        deadline=time.monotonic()+105
        while time.monotonic()<deadline:
            text=d.sh('cat',path+'/rewired-trial-controller.json');report=json.loads(text)
            write(runout/'controller.json',report)
            if report['attempt']!=out.name or str(report['pid'])!=result['runtime']['pid']:
                raise RuntimeError('Stale or incorrect trial report')
            if report.get('error'):raise RuntimeError(report['error'])
            if report['complete']:break
            if d.sh('pidof',PACKAGE,check=False).strip()!=result['runtime']['pid']:
                raise RuntimeError('Reference process exited')
            time.sleep(2)
        else:raise RuntimeError('Reference observation did not complete within bound')
        expected=read(out/'original-manager-parsed.json')['MonoBehaviour']['_userData']
        if {a['id']:a['name'] for a in report['actions']}!={a['_id']:a['_name'] for a in expected['actions']}:
            raise RuntimeError('Runtime action identity changed')
        # Original core creates System at 9999999 and other players by ordinal,
        # independently of the serialized Player_Editor definition IDs (8/10).
        expected_players={9999999 if i==0 else i-1:p['_name'] for i,p in enumerate(expected['players'])}
        if {p['id']:p['name'] for p in report['players']}!=expected_players:
            raise RuntimeError('Runtime player identity changed')
        if not report['ready'] or report['joystickCount']!=1 or report['playerId']!=0:
            raise RuntimeError('Required SDK/controller/player initialization failed')
        categories={m['categoryId'] for m in report['maps']}
        if not {0,2}.issubset(categories):raise RuntimeError('Original gameplay/UI map categories did not load')
        result['technical_observation_pass']=True
        result['events']=len(report['events']);result['elapsed']=report['elapsed']
    except Exception as e:
        result['first_failure']=str(e)
        # Keep the SDK's own first failure even when the generic launch guard never passes.
        try:
            launch=read(WORK/'device/last-run.json');runtime=read(WORK/'device/runtime.json')
            if str(runtime.get('pid'))==launch.get('pid'):
                report=json.loads(d.sh('cat',runtime['persistentDataPath']+'/rewired-trial-controller.json'))
                if report['attempt']==out.name and str(report['pid'])==launch['pid']:
                    write(runout/'controller.json',report)
                    result['first_runtime_failure']=report.get('error')
        except Exception:pass
    finally:
        if installed:
            try:result['capture']=d.collect('all',runout)
            except Exception as e:
                result['capture_error']=str(e)
                result.setdefault('first_failure','Required device capture failed: '+str(e))
            try:d.sh('am','force-stop',PACKAGE)
            except Exception as e:result['stop_error']=str(e)
            try:
                result['rollback']=d.install(previous['apk']) if previous else d.reset()
            except Exception as e:result['rollback_error']=str(e)
        try:d.display(False)
        except Exception as e:result['display_error']=str(e)
        write(runout/'result.json',result);write(out/'device-latest.json',{'path':str(runout.relative_to(ROOT))})
    print(json.dumps({'evidence':str(runout.relative_to(ROOT)),
        'technical_observation_pass':result['technical_observation_pass'],
        'first_failure':result.get('first_failure'),'rollback_error':result.get('rollback_error'),
        'human_mapping_accepted':False,'game_integration_accepted':False},indent=2))
    if not result['technical_observation_pass'] or any(result.get(k) for k in ['capture_error','rollback_error','display_error','stop_error']):
        raise RuntimeError('Trial observation failed; inspect first failure in preserved evidence')

def validate_apk(apk):
    from device import PACKAGE
    aapt=Path('/Applications/Unity/Hub/Editor/2021.3.33f1/PlaybackEngines/AndroidPlayer/SDK/build-tools/30.0.2/aapt')
    text=run([aapt,'dump','badging',apk]).stdout.decode()
    package=re.search(r"^package: name='([^']+)'",text,re.M)
    if not package or package[1]!=PACKAGE:
        raise RuntimeError('Reference APK is not the owned disposable lab package')
