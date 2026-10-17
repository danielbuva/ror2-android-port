"""Standard device check: 35 s of live first-stage play on the installed APK.

Commando is chosen from the ordinary offline menu with invincibility as the only
(diagnostic) assist, so the run never grants permanent progression. The check stops at
35 s of world play or on leaving the first stage; it never routes onward, and it always
force-stops the app and turns the display off.
"""
import json
import time

from common import WORK, now, read, write
from device import Device, PACKAGE

SPINE_ID = 'body-state-spawn-state-auto-nova-spine-bringup'
WORLD_SECONDS = 35
DEADLINE_SECONDS = 370
DEBUG_OPTIONS = ('invincibility', 'highDamage', 'fastCharge', 'movementBoost', 'jumpBoost')


def selection(attempt):
    """The attempt-bound selection Start reads from movement-batch-selection.json."""
    debug = {key: False for key in DEBUG_OPTIONS}
    debug['invincibility'] = True
    debug['purpose'] = 'Standard baseline check; diagnostic assist, no permanent progression'
    return {'attempt': attempt, 'id': SPINE_ID, 'freePlay': True, 'selectedSurvivor': 'Commando',
            'developerSurvivorOverride': False, 'runSeedOverride': '2', 'goldshoresRoute': False,
            'debugOptions': debug}


def assess(stop, first, final):
    """Return the failed criteria (empty when the check passes) for one run.

    `first` is the first report taken during live world play, `final` the last one.
    """
    failures = []
    if stop != 'world-35s':
        failures.append('stopped: '+stop)
    if not final:
        return failures+['no final report']
    if final.get('error') or final.get('firstFailure'):
        failures.append('report error: '+(final.get('firstFailure') or final.get('error'))[:200])
    if (final.get('world') or {}).get('seconds', 0) < WORLD_SECONDS:
        failures.append('world play under %d s' % WORLD_SECONDS)
    if (final.get('stage') or {}).get('scene') != 'lakes':
        failures.append('not on Lakes')
    if not (final.get('debugAcceleration') or {}).get('everAssisted'):
        failures.append('run not marked assisted')
    runs = (final.get('profile') or {}).get('appliedRuns')
    if runs is None or runs != ((first or {}).get('profile') or {}).get('appliedRuns'):
        failures.append('profile run count changed or missing')
    return failures


def check_baseline():
    installed = read(WORK/'device/installed.json')
    if installed['storage']['mode'] != 'adopted':
        raise RuntimeError('Owned APK is not on adopted storage')
    attempt = read(WORK/'lab-project/Assets/LabLoadingScene/Resources/MovementBatchProbe.json')['attempt']
    out = WORK/'experiments/baseline'/now(); out.mkdir(parents=True)
    d = Device(); runtime = read(WORK/'device/runtime.json')['persistentDataPath']
    selector = runtime+'/movement-batch-selection.json'; report_path = runtime+'/movement-batch-'+SPINE_ID+'.json'
    if d.sh('sh', '-c', 'test -e '+selector+' && echo present', check=False).strip():
        raise RuntimeError('Existing diagnostic selector')
    write(out/'selection.json', selection(attempt))
    pid = None; started = False; stop = 'deadline'; first = None; began = time.monotonic()
    try:
        d.sh('rm', '-f', report_path)
        d.cmd('push', str(out/'selection.json'), selector)
        pid = d.launch()['pid']
        while time.monotonic()-began < DEADLINE_SECONDS:
            if d.sh('pidof', PACKAGE, check=False).strip() != pid:
                stop = 'process-exited'; break
            try:
                r = json.loads(d.sh('cat', report_path, check=False))
            except ValueError:
                r = None
            if r and str(r.get('pid')) == pid:
                phase = r.get('phase'); world = (r.get('world') or {}).get('seconds', 0)
                if phase == 'integrated-world-playing' and first is None:
                    first = r  # the profile is loaded by now; earlier reports predate it
                if r.get('error') or r.get('firstFailure'):
                    stop = 'first-failure'; break
                if phase == 'offline-start-menu' and not started:
                    h = r['hud']; d.sh('input', 'tap', str(round(h['menuStartX'])), str(round(h['menuStartY']))); started = True
                if (r.get('stageProgress') or {}).get('transitions', 0):
                    stop = 'left-first-stage'; break
                if phase == 'integrated-world-playing' and world >= WORLD_SECONDS:
                    stop = 'world-35s'; break
                if phase in ('commando-defeated', 'complete') and started:
                    stop = 'ordinary-result'; break
            time.sleep(2)
        try:
            final = json.loads(d.sh('cat', report_path, check=False))
        except ValueError:
            final = None
        write(out/'final-report.json', final)
        d.collect('logs', out/'capture')
        d.collect('screenshot', out/'capture')
    finally:
        d.sh('rm', '-f', selector, check=False)
        d.sh('am', 'force-stop', PACKAGE, check=False)
        d.display(False)
    failures = assess(stop, first, final)
    result = {'success': not failures, 'failures': failures, 'stop': stop, 'pid': pid,
              'apk_sha256': installed['apk_sha256'],
              'is_current_build': installed['apk_sha256'] == read(WORK/'config/current-build.json')['apk_sha256'],
              'world_seconds': ((final or {}).get('world') or {}).get('seconds'),
              'applied_runs': ((final or {}).get('profile') or {}).get('appliedRuns'),
              'evidence': str(out.relative_to(WORK.parent))}
    write(out/'result.json', result)
    return result
