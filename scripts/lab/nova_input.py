"""One bounded read-only physical-input observation on the authorized Nova."""
from common import *
from device import Device, PACKAGE
import re


def observe(capture=False):
    d=Device()
    if d.sh('getprop','ro.product.model')!='Retroid Pocket Nova':
        raise RuntimeError('This physical-control experiment requires the configured Nova')
    d.owned()
    if capture:d.display(True)
    capabilities=d.sh('getevent','-lp')
    blocks=re.split(r'(?=add device \d+:)',capabilities)
    candidates=[b for b in blocks if all(label in b for label in ['BTN_GAMEPAD','ABS_X','ABS_Y'])]
    if len(candidates)!=1:raise RuntimeError('Expected one measured gamepad; inspect capabilities before capture')
    match=re.search(r'/dev/input/event\d+\b',candidates[0])
    if not match:raise RuntimeError('Measured gamepad event path unavailable')
    if not d.sh('command','-v','timeout'):raise RuntimeError('Bounded device-side capture timeout unavailable')
    out=WORK/'experiments/nova-input'/now();out.mkdir(parents=True)
    (out/'capabilities.txt').write_text(capabilities)
    write(out/'target.json',{'serial':d.serial,'model':'Retroid Pocket Nova','event_path':match[0]})
    result={'success':True,'evidence':str(out.relative_to(ROOT)),'scope':'Kernel gamepad observation only; physical mapping and game binding unproven'}
    if not capture:
        runtime=read(WORK/'device/runtime.json')['persistentDataPath']
        if not runtime.endswith('/Android/data/'+PACKAGE+'/files'):raise RuntimeError('Unexpected lab runtime path')
        if d.sh('ls',runtime+'/movement-batch-selection.json',check=False):
            raise RuntimeError('An experiment selector remains; finish that attempt before physical input preparation')
        result['lab_ready']=d.launch()['checkpoint']
        result['next']='Owned lab screen ready; physical control presses required for nova-input-capture'
    foreground=d.sh('dumpsys','activity','activities')
    (out/'foreground.txt').write_text(foreground)
    resumed=[line for line in foreground.splitlines() if 'mResumedActivity:' in line or 'topResumedActivity=' in line]
    result['lab_foreground']=bool(resumed) and all(PACKAGE+'/' in line for line in resumed)
    if not result['lab_foreground']:raise RuntimeError('Owned Lab must be foreground before physical input capture')
    if capture:
        # Device-side timeout terminates getevent; no controller input is injected and no other device is queried.
        process=run(d.base+['shell','timeout','60','getevent','-lt',match[0]],check=False,timeout=75)
        (out/'events.txt').write_bytes(process.stdout);(out/'stderr.txt').write_bytes(process.stderr)
        events=sum('EV_' in line for line in process.stdout.decode(errors='replace').splitlines())
        result.update({'success':process.returncode in [0,124] and events>0,'events':events,'returncode':process.returncode,'seconds':60,'acceptance':'Human control labels must be compared with events; no automatic mapping acceptance'})
    write(out/'result.json',result);write(WORK/'experiments/nova-input/current.json',{'path':result['evidence']})
    return result
