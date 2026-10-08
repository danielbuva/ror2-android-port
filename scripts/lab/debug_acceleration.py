"""Explicit per-launch debug options and fail-closed normal acceptance labels."""
from common import WORK, read

TOGGLES = ('invincibility', 'highDamage', 'fastCharge', 'movementBoost', 'jumpBoost')
EXCLUDED = {
    'invincibility': ('normal-combat', 'death'),
    'highDamage': ('normal-combat',),
    'fastCharge': ('holdout',),
    'movementBoost': ('movement', 'navigation'),
    'jumpBoost': ('movement', 'navigation'),
}

def validate_options(value):
    if not isinstance(value, dict) or set(value) - set(TOGGLES) - {'purpose'}:
        raise RuntimeError('Unknown debug acceleration options')
    options = {key: value.get(key, False) for key in TOGGLES}
    if any(type(enabled) is not bool for enabled in options.values()):
        raise RuntimeError('Debug toggles must be explicit booleans')
    purpose = value.get('purpose', '')
    if not isinstance(purpose, str) or len(purpose) > 160 or (any(options.values()) and not purpose.strip()):
        raise RuntimeError('Assisted runs require a short experiment purpose')
    return dict(options, purpose=purpose)

def load_options(path):
    from pathlib import Path
    source = Path(path).resolve()
    if not source.is_relative_to(WORK.resolve()):
        raise RuntimeError('Local debug options must stay under ignored work/')
    return validate_options(read(source))

def acceptance_labels(report, requested=None):
    requested = validate_options(requested or {})
    debug = report.get('debugAcceleration')
    wanted = {key for key in TOGGLES if requested[key]}
    if debug is None:
        if wanted:
            raise RuntimeError('APK did not report requested debug acceleration')
        return {'run_kind': 'unassisted', 'normal_game_acceptance_eligible': True,
                'excluded_acceptance': [], 'debug_acceleration': None}
    if debug.get('version') != 1 or debug.get('error'):
        raise RuntimeError('Debug acceleration report failed; inspect runtime evidence')
    events = debug.get('events', [])
    active = validate_options(debug.get('active') or {})
    used = {event.get('toggle') for event in events if event.get('enabled') is True}
    used.update(key for key in TOGGLES if active[key])
    if used - set(TOGGLES) or not wanted.issubset(used):
        raise RuntimeError('Requested debug toggles were not observed')
    grants = debug.get('itemGrants') or []
    if not isinstance(grants, list) or len(grants) > 3 or any(
            not isinstance(entry, dict) or not isinstance(entry.get('item'), str)
            or not entry['item'] or type(entry.get('before')) is not int
            or type(entry.get('after')) is not int or entry['before'] < 0
            or entry['after'] != entry['before'] + 1 for entry in grants):
        raise RuntimeError('Developer item grant evidence is invalid')
    if len({entry['item'] for entry in grants}) != len(grants):
        raise RuntimeError('Duplicate developer item grant evidence')
    if grants and debug.get('everAssisted') is not True:
        raise RuntimeError('Developer item grants were not marked assisted')
    assisted = bool(used or grants or debug.get('everAssisted'))
    if assisted and debug.get('normalGameAcceptanceEligible') is not False:
        raise RuntimeError('Assisted runtime incorrectly claims normal acceptance')
    if not assisted and debug.get('normalGameAcceptanceEligible') is not True:
        raise RuntimeError('Debug acceptance eligibility is missing or contradictory')
    excluded = {'full-normal-run'} if assisted else set()
    for key in used:
        excluded.update(EXCLUDED[key])
    if grants:
        excluded.update(('normal-loot', 'normal-progression'))
    return {'run_kind': 'debug-assisted' if assisted else 'unassisted',
            'normal_game_acceptance_eligible': not assisted,
            'excluded_acceptance': sorted(excluded), 'debug_acceleration': debug}
